"""LLM yöntemi (HANDOFF 2026-10-30 P1c kartı 4. madde; HANDOFF 2026-11-01 5. adım planı; DECISIONS 2026-10-30 "LLM
ayarları", 2026-10-31 "İstem payı", "Boş ham girdi", "Çıktı sınırı", 2026-11-01 "Bütçeyi aşan girdi", "İstem metni").

Bir koşu = bir model × bir girdi seviyesi × gerçek ya da takma ad (`llm_method`). Vaka başına:
1. Girdi `inputs.<seviye>_input` (takma adlı koşuda `alias.<seviye>_input`) ile üretilir; token sayımı yerel Qwen
   tokenizer'ıyla (`/tokenize`). Boş ham girdi modele sorulmaz (`input_status: empty`).
2. Mesajlar onaylı istemle kurulur (`build_messages`; seviyeler arasında yalnız tarif ve veri bloğu değişir). Tam mesaj
   (sohbet şablonu + istem + veri) yerel olarak sayılır (`/apply-template` + `/tokenize`); `TOTAL_BUDGET`'ı aşarsa
   sorulmaz (`input_status: over_budget`). API modellerinde de ölçü yerel sayım; sağlayıcının sayısı yalnız kayda.
3. `llm_client.chat` ile bir kez sorulur (taşıma hatasında bir yeniden deneme; Groq'ta `Pacer` aralığı).

Yerel sunucu koşu başında bir kez açılır: yerel modelde modelin kendi sunucusu (sorma ve sayım), API modellerinde yalnız
sayım için Qwen 4B. GGUF dosyalarının SHA256'sı koşu başında `ModelSpec.gguf_sha256` ile karşılaştırılır; uyuşmazsa koşu
başlamaz (`ValueError`). Yöntem yalnız `Case`'i alır; etiket yönteme gitmez.
"""
from __future__ import annotations

import functools
import hashlib
import json
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from aiops_rca import alias as alias_inputs
from aiops_rca import inputs
from aiops_rca.cases import Case
from aiops_rca.inputs import DATA_BUDGET, LEVELS
from aiops_rca.llm_client import (ENDPOINTS, GROQ_GAP, IMAGE, MODELS, MODELS_DIR, LocalServer, Pacer, chat,
                                  count_tokens, post)

TOTAL_BUDGET = 6000  # sohbet şablonu + istem + veri (DECISIONS 2026-10-31 "İstem payı")
TOKENIZER = "qwen3.5-4b"  # API modellerinde sayım; yerel modelde modelin kendi sunucusu (üç Qwen tokenizer'ı aynı)

# İstem (Onay 3; DECISIONS 2026-11-01 "İstem metni"). Metin onaylı metnin birebiri; sha256 testte sabit
# (`json.dumps([SYSTEM_PROMPT, LEVEL_TEXT, USER_TEMPLATE])`). Değişirse yeniden onay.
SYSTEM_PROMPT = "You are an SRE assistant doing root cause analysis for a microservice-based online shop."

LEVEL_TEXT = {
    "raw": (
        "Below are the warning and error log records and the failed spans of the shop from the 10 minutes before "
        "to the 10 minutes after the alert, one per line, in time order: \"HH:MM:SS.mmm <service> log <message>\" or "
        "\"HH:MM:SS.mmm <service> error-span <span name>\" (UTC). If there were too many lines, the list is cut and "
        "its last line is \"[truncated: later lines omitted]\"."),
    "summary": (
        "Below is a telemetry summary of the shop for the 10 minutes before and the 10 minutes after the alert, as "
        "JSON: for each service, the number of incoming requests, the error rate and the p95 latency in "
        "milliseconds; for each container, the CPU usage (percent of one core, average and maximum) and the memory "
        "usage in MB (average); and the most frequent warning and error log messages after the alert. Some rows, "
        "such as databases, have only some of these fields."),
    "narrowed": (
        "Below are 5 candidate services chosen by an automatic pre-filter from the telemetry of the 10 minutes "
        "before and the 10 minutes after the alert, as JSON (the order is not a ranking). "
        "For each candidate: the same fields as in a service summary (incoming requests, error rate and p95 latency "
        "in milliseconds; container CPU as percent of one core, average and maximum; memory in MB, average); its "
        "incoming operations with the same request fields; the calls it receives from other services, per caller "
        "and call name, with the same fields as measured by the caller; and its 3 most frequent warning and error log messages after the alert, with counts before and after. "
        "\"calls\" lists the calls between the candidates as [caller, callee]."),
}

USER_TEMPLATE = """An alert fired at {alarm_time} (UTC). {level_text}

Find the root cause service: the service where the problem started, not a service that only shows symptoms of a \
problem elsewhere.

Give exactly 3 different candidate services, most likely first, using service names exactly as they appear in the \
data. For each candidate:
- "confidence": the probability (0 to 1) that this candidate is the root cause.
- "evidence_path": how the problem spread, as service names from the candidate to the service where the symptom \
shows; the first name is the candidate itself. If you see no spread, give only the candidate.
- "rationale": one short sentence.
Set "unsure" to true if the data is not enough to choose with reasonable confidence, otherwise false.

Answer with JSON only, no other text:
{{"candidates": [{{"service": "<name>", "confidence": <0-1>, "evidence_path": ["<name>", ...], "rationale": \
"<one sentence>"}}, ... 3 candidates], "unsure": <true or false>}}

Data:
{data}"""


def build_messages(level: str, alarm_time: str, data: str) -> list[dict]:
    user = USER_TEMPLATE.format(alarm_time=alarm_time, level_text=LEVEL_TEXT[level], data=data)
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def prompt_sha256() -> str:
    return hashlib.sha256(json.dumps([SYSTEM_PROMPT, LEVEL_TEXT, USER_TEMPLATE]).encode()).hexdigest()


def _alarm_time(case: Case) -> str:
    """Özetteki `alarm_time_utc` biçimi."""
    return datetime.fromtimestamp(case.alarm_ns / 1e9, tz=timezone.utc).isoformat(timespec="seconds")


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _checked_gguf(label: str, models_dir: Path) -> str:
    spec = MODELS[label]
    got = _file_sha256(models_dir / spec.gguf)
    if got != spec.gguf_sha256:
        raise ValueError(f"{spec.gguf}: sha256 {got} does not match LOCAL_MODEL_BENCH ({spec.gguf_sha256})")
    return got


def _template_tokens(base: str, messages: list[dict]) -> int:
    """Sohbet şablonu dahil tam mesajın token sayısı (yerel Qwen tokenizer'ı; düşünme kapalı şablon)."""
    status, resp = post(f"{base}/apply-template",
                        {"messages": messages, **MODELS[TOKENIZER].extra}, None, 120)
    if status != 200 or not isinstance(resp, dict) or "prompt" not in resp:
        raise RuntimeError(f"apply-template failed: HTTP {status}: {str(resp)[:200]}")
    return count_tokens(base, resp["prompt"])


@contextmanager
def llm_method(label: str, level: str, alias: bool, *, models_dir: Path = MODELS_DIR, base: str | None = None,
               chat_url: str | None = None, key: str | None = None,
               sleep: Callable[[float], None] = time.sleep) -> Iterator[tuple[Callable[[Case], dict], dict]]:
    """(vaka → kayıt satırının alanları, `run.json` ayarları). `base` verilirse sunucu açılmaz (testler: sahte
    sunucu; yerel modelde sorma da oraya gider). `chat_url`/`key` API modellerinde uç nokta ve anahtar (testler)."""
    if label not in MODELS:
        raise ValueError(f"unknown model {label!r}")
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    spec = MODELS[label]
    server_label = label if spec.provider == "local" else TOKENIZER
    settings = {"level": level, "alias": alias, "max_tokens": spec.max_tokens, "extra": spec.extra,
                "prompt_sha256": prompt_sha256(), "data_budget": DATA_BUDGET, "total_budget": TOTAL_BUDGET,
                "image": IMAGE, "gguf": MODELS[server_label].gguf,
                "gguf_sha256": _checked_gguf(server_label, models_dir)}
    if spec.provider != "local":
        settings["tokenizer"] = TOKENIZER
    source = alias_inputs if alias else inputs
    make_input = getattr(source, f"{level}_input")
    pacer = Pacer(GROQ_GAP, sleep=sleep) if spec.provider == "groq" else None
    with ExitStack() as stack:
        if base is None:
            base = stack.enter_context(LocalServer(MODELS[server_label].gguf, models_dir=models_dir)).base
        url = f"{base}/v1/chat/completions" if spec.provider == "local" else (chat_url or ENDPOINTS[spec.provider])
        count = functools.partial(count_tokens, base)

        def ask(case: Case) -> dict:
            inp = make_input(case, count)
            row = {"input_status": "ok", "data_tokens": inp["data_tokens"],
                   "input_sha256": hashlib.sha256(inp["text"].encode()).hexdigest(), "input_tokens_local": None,
                   "answer": None, "schema_valid": None, "schema_errors": [], "raw_output": None,
                   "finish_reason": None, "attempts": [], "tokens": None, "duration_s": None}
            if "alias_lines_dropped" in inp:
                row["alias_lines_dropped"] = inp["alias_lines_dropped"]
            if inp["empty"]:  # DECISIONS 2026-10-31 "Boş ham girdi": sorulmaz
                return {**row, "input_status": "empty"}
            messages = build_messages(level, _alarm_time(case), inp["text"])
            row["input_tokens_local"] = _template_tokens(base, messages)
            if row["input_tokens_local"] > TOTAL_BUDGET:  # DECISIONS 2026-11-01 "Bütçeyi aşan girdi"
                return {**row, "input_status": "over_budget"}
            if pacer:
                pacer.wait()
            rec = chat(spec, messages, url=url, key=key, sleep=sleep)
            if pacer:
                pacer.done()
            return {**row, **{k: rec[k] for k in ("answer", "schema_valid", "schema_errors", "raw_output",
                                                  "finish_reason", "attempts", "tokens", "duration_s")}}

        yield ask, settings
