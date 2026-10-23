"""Kaba kalite denemeleri: aynı istem ve özeti beş modele sorar (HANDOFF 2026-10-21, DECISIONS 2026-10-21).

Kullanım: python tools/trial_ask_models.py <vaka klasörü>... [--models qwen3.5-2b,gpt-oss-120b,...]
          python tools/trial_ask_models.py <vaka klasörü>... --score   # sadece kayıtlı cevaplardan tablo
          [--view view_alias] [--answers answers_alias] [--alias]       # takma ad ön denemesi
          python tools/trial_ask_models.py --probe <klasör> [--score]   # bilgi yoklaması

Vaka klasörü: `view/summary.json` (modele giden özet) ve `case.json` (doğru cevap; sadece puanlamada okunur,
modele gitmez). Her cevap `answers/<model>.json`'a yazılır; mevcut cevap üzerine yazılmaz (silinip tekrar koşulur).

Modeller:
- Yerel: llama.cpp sunucusu (hız ölçümündeki `full` imajı, digest ile), her model bir kez açılır ve bütün vakalara
  sorulur; 4 iş parçacığı; düşünme kapalı (`enable_thinking: false`); çıktı sınırı 300.
- API: Groq gpt-oss-120b (`reasoning_effort: low`, en düşük; kapatılamıyor) ve Gemini 3.5 Flash Lite
  (`reasoning_effort: minimal`, en düşük; kapatılamıyor). Düşünme token'ları çıktı sınırından düşüyor (Groq'ta
  20 sınırla boş cevap ölçüldü), bu yüzden sınır 2000. Anahtarlar ortamdan (`keys.env`); ekrana basılmaz.
- Beşinde aynı: istem, girdi, temperature 0, JSON şeması (`response_format` `json_schema`, `strict`; tam 3 aday,
  servis adı serbest metin, enum yok). Şema üç sağlayıcıda denenerek doğrulandı (zor deneme, 2026-10-23).
  İlk denemede şema yoktu; okuyucu hâlâ cevaptaki ilk JSON nesnesini okur (``` dahil).

Kurallar (kart ölçütü):
- Cevap token sınırına takıldı (`finish_reason: length`) ve okunamadıysa sınır bir kez iki katına çıkarılıp
  tekrar sorulur; iki deneme de kayda, puan ikinciden.
- Okunamayan cevap "çözemedi". Doğru servis ilk 3'te → çözdü; top-1 ayrıca yazılır. Adlar harf dışı karakterler
  atılarak karşılaştırılır (`product_catalog` = `product-catalog`); özetteki hiçbir servise uymayan adlar ayrı
  sütunda (`unmatched`). İlk denemenin tablosu aynı kalır (yeni sütun en sonda).
- Groq dakikada 8K token: Groq istekleri arasında 65 sn beklenir. Gemini 503/429'da bir kez 30 sn sonra tekrar.
- Takma ad ön denemesi (HANDOFF/DECISIONS 2026-10-23): `--view` özetin okunduğu klasör (varsayılan `view`),
  `--answers` cevap klasörü (varsayılan `answers`); `--alias` puanlamada cevaptaki takma adları `ALIASES`
  (`tools/trial_alias.py`) ile gerçek ada çevirir. Varsayılanlarla davranış ve tablolar öncekiyle aynı.
- Bilgi yoklaması (`--probe <klasör>`, ölçüte girmez): vaka yok; beş modele OTel Demo'nun flag senaryoları sorulur,
  cevap `<klasör>/<model>.json`. Şema: `scenarios` listesi (`{flag, service}`, sınır yok). Çıktı sınırı yerelde
  600 (13 flag'e 300 yetmeyebilir), API'de 2000. `--score` ile sayım: flag adı ve servis harf dışı karakterler
  atılarak OTEL_DEMO "Hata senaryoları" tablosuyla karşılaştırılır; model başına doğru flag adı ve doğru
  flag→servis çifti (13 üzerinden). `paymentUnreachable` payment ya da checkout, `imageSlowLoad` frontend,
  frontend-proxy ya da image-provider, `loadGeneratorFloodHomepage` load-generator ya da frontend kabul (soru
  demoyu bilmek, kök neden kuralı değil; Eren, 2026-10-23).
Çıkış kodu: 0 tamam, 1 bir model ya da vaka hata verdi, 2 kullanım/girdi hatası.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

IMAGE = "ghcr.io/ggml-org/llama.cpp@sha256:8f3c2cd0808a394d1e7ce02f025f453caacbf163389fe6b6443ec3a1efff96a0"
MODELS_DIR = Path.home() / "cerebrum2/models"
LOCAL_PORT = 8081
LOCAL_NAME = "trial-llama"
THREADS = 4
CONTEXT = 4096
TIMEOUT = 600  # saniye; 9B ~2K girdide ~2 dk
GROQ_GAP = 65
RETRY_WAIT = 30

# (etiket, tür, model, çıktı sınırı, ek gövde alanları)
MODELS = [
    ("qwen3.5-2b", "local", "Qwen3.5-2B-Q4_K_M.gguf", 300, {"chat_template_kwargs": {"enable_thinking": False}}),
    ("qwen3.5-4b", "local", "Qwen3.5-4B-Q4_K_M.gguf", 300, {"chat_template_kwargs": {"enable_thinking": False}}),
    ("qwen3.5-9b", "local", "Qwen3.5-9B-Q4_K_M.gguf", 300, {"chat_template_kwargs": {"enable_thinking": False}}),
    ("gpt-oss-120b", "groq", "openai/gpt-oss-120b", 2000, {"reasoning_effort": "low"}),
    ("gemini-3.5-flash-lite", "gemini", "gemini-3.5-flash-lite", 2000, {"reasoning_effort": "minimal"}),
]

ENDPOINTS = {
    "local": (f"http://127.0.0.1:{LOCAL_PORT}/v1/chat/completions", None),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY"),
}

# İstem: Eren onaylayınca değişmez. İlk denemenin metni git geçmişinde (`7c34225`); bu metin zor deneme için
# CPU ve bellek alanlarını anlatır.
SYSTEM_PROMPT = "You are an SRE assistant doing root cause analysis for a microservice-based online shop."
USER_TEMPLATE = """An alert fired at {alarm_time}. Below is a telemetry summary of the shop for the 10 minutes before \
and the 10 minutes after the alert: for each service, the number of incoming requests, the error rate and the p95 \
latency in milliseconds; for each container, the CPU usage (percent of one core, average and maximum) and the memory \
usage in MB (average); and the most frequent warning and error log messages after the alert. Some rows, such as \
databases, have only some of these fields.

Find the root cause service: the service whose own code or configuration is faulty, not a service that only shows \
symptoms of a problem elsewhere. List the 3 most likely services, most likely first, using service names exactly as \
they appear in the summary, with a one-sentence reason for each.

Answer with JSON only, no other text:
{{"candidates": [{{"service": "<name>", "reason": "<one sentence>"}}, {{"service": "<name>", "reason": "<one sentence>"}}, {{"service": "<name>", "reason": "<one sentence>"}}]}}

Summary:
{summary}"""


# Beş modelde aynı şema (DECISIONS 2026-10-21). strict: bütün alanlar zorunlu, fazladan alan yok (Groq şartı).
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["candidates"],
    "properties": {"candidates": {
        "type": "array", "minItems": 3, "maxItems": 3,
        "items": {"type": "object", "additionalProperties": False, "required": ["service", "reason"],
                  "properties": {"service": {"type": "string"}, "reason": {"type": "string"}}}}},
}
RESPONSE_FORMAT = {"type": "json_schema",
                   "json_schema": {"name": "root_cause_candidates", "strict": True, "schema": SCHEMA}}

# Bilgi yoklaması (Eren onayı 2026-10-23; sistem mesajı yok).
PROBE_PROMPT = ("The OpenTelemetry Demo (Astronomy Shop) has built-in failure scenarios that are turned on with "
                "feature flags. List every such feature flag you know, with the exact flag name and the service it "
                "affects. Leave out flags you are not sure about. Answer with JSON only: "
                '{"scenarios": [{"flag": "<flag name>", "service": "<service name>"}]}')
PROBE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["scenarios"],
    "properties": {"scenarios": {
        "type": "array",
        "items": {"type": "object", "additionalProperties": False, "required": ["flag", "service"],
                  "properties": {"flag": {"type": "string"}, "service": {"type": "string"}}}}},
}
PROBE_FORMAT = {"type": "json_schema",
                "json_schema": {"name": "feature_flag_scenarios", "strict": True, "schema": PROBE_SCHEMA}}
PROBE_LOCAL_MAX_TOKENS = 600
# OTEL_DEMO "Hata senaryoları" (minimal mod, 13 flag): flag -> kabul edilen servisler.
PROBE_TRUTH = {
    "adFailure": {"ad"}, "adHighCpu": {"ad"}, "adManualGc": {"ad"}, "cartFailure": {"cart"},
    "emailMemoryLeak": {"email"}, "imageSlowLoad": {"frontend", "frontend-proxy", "image-provider"},
    "intlShippingSlowdown": {"shipping"}, "paymentFailure": {"payment"}, "paymentUnreachable": {"payment", "checkout"},
    "productCatalogFailure": {"product-catalog"}, "productCatalogLockContention": {"product-catalog"},
    "recommendationCacheFailure": {"recommendation"}, "loadGeneratorFloodHomepage": {"load-generator", "frontend"},
}


def build_messages(summary_text: str) -> list[dict]:
    summary = json.loads(summary_text)
    user = USER_TEMPLATE.format(alarm_time=summary["alarm_time_utc"], summary=summary_text.strip())
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def post(url: str, body: dict, key_env: str | None) -> tuple[int, dict | str, float]:
    headers = {"Content-Type": "application/json", "User-Agent": "aiops-rca-trial/0.1"}
    if key_env:
        headers["Authorization"] = "Bearer " + os.environ.get(key_env, "")
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode("utf-8")), time.monotonic() - start
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500], time.monotonic() - start
    except Exception as e:  # zaman aşımı, ağ
        return -1, f"{type(e).__name__}: {e}", time.monotonic() - start


def parse_answer(content: str | None) -> list[str] | None:
    """Cevaptaki ilk JSON nesnesinden servis listesi; okunamazsa None."""
    if not content:
        return None
    text = re.sub(r"```(?:json)?", "", content)
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        services = [str(c["service"]).strip() for c in obj["candidates"]]
    except (ValueError, KeyError, TypeError):
        return None
    return services or None


def ask(kind: str, model: str, max_tokens: int, extra: dict, messages: list[dict],
        response_format: dict = RESPONSE_FORMAT, parse=None) -> dict:
    url, key_env = ENDPOINTS[kind]
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens,
            "response_format": response_format, **extra}
    status, resp, elapsed = post(url, body, key_env)
    retried = None
    if kind == "gemini" and status in (429, 503):
        # İlk hata kayda girer; süre ikinci çağrının süresidir.
        retried = {"status": status, "elapsed_s": round(elapsed, 1), "error": str(resp)[:500]}
        time.sleep(RETRY_WAIT)
        status, resp, elapsed = post(url, body, key_env)
    attempt = {"max_tokens": max_tokens, "status": status, "elapsed_s": round(elapsed, 1), "retried_after": retried}
    if status != 200 or not isinstance(resp, dict):
        attempt["error"] = resp if isinstance(resp, str) else json.dumps(resp)[:500]
        return attempt
    choice = resp["choices"][0]
    usage = resp.get("usage", {})
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
    attempt.update(
        finish_reason=choice.get("finish_reason"),
        content=choice["message"].get("content"),
        reasoning_text=choice["message"].get("reasoning") or choice["message"].get("reasoning_content"),
        input_tokens=usage.get("prompt_tokens"),
        reasoning_tokens=reasoning,
        answer_tokens=(usage.get("completion_tokens") or 0) - reasoning,
        usage=usage,
    )
    attempt["parsed"] = (parse or parse_answer)(attempt["content"])
    return attempt


def parse_probe(content: str | None) -> list[list[str]] | None:
    """Bilgi yoklaması cevabı: [[flag, servis], ...]; okunamazsa None."""
    if not content:
        return None
    text = re.sub(r"```(?:json)?", "", content)
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return [[str(s["flag"]).strip(), str(s["service"]).strip()] for s in obj["scenarios"]]
    except (ValueError, KeyError, TypeError):
        return None


def run_model(label: str, kind: str, model: str, max_tokens: int, extra: dict, cases: list[Path],
              view: str = "view", answers: str = "answers") -> bool:
    ok = True
    for case in cases:
        out = case / answers / f"{label}.json"
        if out.exists():
            print(f"skip: {out} exists")
            continue
        messages = build_messages((case / view / "summary.json").read_text(encoding="utf-8"))
        attempts = [ask(kind, model, max_tokens, extra, messages)]
        last = attempts[-1]
        if last.get("finish_reason") == "length" and last.get("parsed") is None:
            if kind == "groq":
                time.sleep(GROQ_GAP)
            attempts.append(ask(kind, model, max_tokens * 2, extra, messages))
        record = {"model": label, "kind": kind, "model_id": model, "view": view, "request": {
            "temperature": 0, "response_format": RESPONSE_FORMAT, **extra}, "system_prompt": SYSTEM_PROMPT,
            "user_template": USER_TEMPLATE, "attempts": attempts}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        final = attempts[-1]
        if "error" in final:
            ok = False
        print(f"{case.name} {label}: status {final['status']}, {final['elapsed_s']} s, parsed {final.get('parsed')}")
        if kind == "groq":
            time.sleep(GROQ_GAP)
    return ok


def start_local(gguf: str) -> None:
    subprocess.run(["docker", "rm", "-f", LOCAL_NAME], capture_output=True)
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", LOCAL_NAME, "-p", f"127.0.0.1:{LOCAL_PORT}:8080",
         "-v", f"{MODELS_DIR}:/models:ro", IMAGE, "--server", "-m", f"/models/{gguf}",
         "-t", str(THREADS), "-c", str(CONTEXT), "--host", "0.0.0.0", "--port", "8080"],
        check=True, capture_output=True)
    for _ in range(180):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"llama-server did not become healthy for {gguf}")


def stop_local() -> None:
    subprocess.run(["docker", "stop", LOCAL_NAME], capture_output=True)


def count_tokens(text: str) -> int:
    body = json.dumps({"content": text}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{LOCAL_PORT}/tokenize", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return len(json.loads(r.read())["tokens"])


def name_key(name: str) -> str:
    """Ad karşılaştırması: harf dışı karakterler atılır, küçük harf (Eren, 2026-10-21)."""
    return re.sub(r"[^a-z]", "", name.lower())


def score(cases: list[Path], view: str = "view", answers: str = "answers", alias: bool = False) -> None:
    back = {}
    if alias:  # takma ad -> gerçek ad (aynı ad karşılaştırmasıyla)
        from trial_alias import ALIASES
        back = {name_key(a): name_key(r) for r, a in ALIASES.items()}
    print("\t".join(["case", "model", "top1", "top3", "parsed", "elapsed_s", "input", "reasoning", "answer",
                     "attempts", "answer_services", "unmatched"]))
    for case in cases:
        truth = name_key(json.loads((case / "case.json").read_text(encoding="utf-8"))["root_cause_service"])
        summary = json.loads((case / view / "summary.json").read_text(encoding="utf-8"))
        known = {name_key(r["service"]) for r in summary["services"]}
        for label, *_ in MODELS:
            path = case / answers / f"{label}.json"
            if not path.exists():
                continue
            attempts = json.loads(path.read_text(encoding="utf-8"))["attempts"]
            final = attempts[-1]
            services = [s.lower() for s in (final.get("parsed") or [])]
            # Özette olmayan ad (takma adlı koşuda gerçek ad dahil) unmatched; doğru sayılmaz.
            unmatched = [s for s in services if name_key(s) not in known]
            keys = [back.get(name_key(s), name_key(s)) if name_key(s) in known else None for s in services]
            print("\t".join(str(x) for x in [
                case.name, label, bool(keys[:1]) and keys[0] == truth, truth in keys[:3],
                final.get("parsed") is not None, final.get("elapsed_s"), final.get("input_tokens"),
                final.get("reasoning_tokens"), final.get("answer_tokens"), len(attempts), services, unmatched]))


def run_probe(label: str, kind: str, model: str, max_tokens: int, extra: dict, out_dir: Path) -> bool:
    out = out_dir / f"{label}.json"
    if out.exists():
        print(f"skip: {out} exists")
        return True
    if kind == "local":
        max_tokens = PROBE_LOCAL_MAX_TOKENS
    messages = [{"role": "user", "content": PROBE_PROMPT}]
    attempts = [ask(kind, model, max_tokens, extra, messages, PROBE_FORMAT, parse_probe)]
    last = attempts[-1]
    if last.get("finish_reason") == "length" and last.get("parsed") is None:
        if kind == "groq":
            time.sleep(GROQ_GAP)
        attempts.append(ask(kind, model, max_tokens * 2, extra, messages, PROBE_FORMAT, parse_probe))
    record = {"model": label, "kind": kind, "model_id": model, "request": {
        "temperature": 0, "response_format": PROBE_FORMAT, **extra}, "prompt": PROBE_PROMPT, "attempts": attempts}
    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    final = attempts[-1]
    print(f"probe {label}: status {final['status']}, {final['elapsed_s']} s, "
          f"{len(final.get('parsed') or [])} scenarios")
    return "error" not in final


def score_probe(out_dir: Path) -> None:
    truth = {name_key(f): {name_key(s) for s in svcs} for f, svcs in PROBE_TRUTH.items()}
    print("\t".join(["model", "parsed", "listed", "flags_correct", "pairs_correct", "of", "unknown_flags"]))
    for label, *_ in MODELS:
        path = out_dir / f"{label}.json"
        if not path.exists():
            continue
        final = json.loads(path.read_text(encoding="utf-8"))["attempts"][-1]
        pairs = final.get("parsed") or []
        flags_ok, pairs_ok, unknown = set(), set(), []
        for flag, service in pairs:
            f = name_key(flag)
            if f in truth:
                flags_ok.add(f)
                if name_key(service) in truth[f]:
                    pairs_ok.add(f)
            else:
                unknown.append(flag)
        print("\t".join(str(x) for x in [label, final.get("parsed") is not None, len(pairs), len(flags_ok),
                                          len(pairs_ok), len(truth), unknown]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="*", help="case folders (with <view>/summary.json)")
    parser.add_argument("--models", help="comma-separated labels; default all")
    parser.add_argument("--score", action="store_true", help="only print the table from saved answers")
    parser.add_argument("--view", default="view", help="folder in each case with summary.json (default view)")
    parser.add_argument("--answers", default="answers", help="answer folder in each case (default answers)")
    parser.add_argument("--alias", action="store_true", help="score: map alias names back to real names")
    parser.add_argument("--probe", metavar="DIR", help="knowledge probe: ask the flag question, answers to DIR")
    args = parser.parse_args(argv)

    if args.probe:
        if args.cases:
            print("error: --probe takes no case folders", file=sys.stderr)
            return 2
        if args.score:
            score_probe(Path(args.probe).expanduser())
            return 0
    elif not args.cases:
        print("error: case folders required (or --probe)", file=sys.stderr)
        return 2
    cases = [Path(c).expanduser() for c in args.cases]
    for case in cases:
        if not (case / args.view / "summary.json").is_file():
            print(f"error: {case}/{args.view}/summary.json not found", file=sys.stderr)
            return 2
    if args.score:
        score(cases, args.view, args.answers, args.alias)
        return 0
    wanted = set(args.models.split(",")) if args.models else {m[0] for m in MODELS}
    unknown = wanted - {m[0] for m in MODELS}
    if unknown:
        print(f"error: unknown models {sorted(unknown)}", file=sys.stderr)
        return 2
    for env in {ENDPOINTS[m[1]][1] for m in MODELS if m[0] in wanted} - {None}:
        if not os.environ.get(env):
            print(f"error: {env} not set (source ~/.config/aiops_rca/keys.env)", file=sys.stderr)
            return 2

    ok = True
    for label, kind, model, max_tokens, extra in MODELS:
        if label not in wanted:
            continue
        if args.probe:
            if (Path(args.probe).expanduser() / f"{label}.json").exists():
                print(f"skip: {label} already answered the probe")
                continue
        elif all((case / args.answers / f"{label}.json").exists() for case in cases):
            print(f"skip: {label} already answered every case")
            continue
        try:
            if kind == "local":
                start_local(model)
            if args.probe:
                ok &= run_probe(label, kind, model, max_tokens, extra, Path(args.probe).expanduser())
                continue
            if kind == "local":
                for case in cases:
                    text = (case / args.view / "summary.json").read_text(encoding="utf-8")
                    prompt = "\n".join(m["content"] for m in build_messages(text))
                    print(f"{case.name}: summary {count_tokens(text)} tokens, prompt {count_tokens(prompt)} tokens")
            ok &= run_model(label, kind, model, max_tokens, extra, cases, args.view, args.answers)
        except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
            print(f"error: {label}: {e}", file=sys.stderr)
            ok = False
        finally:
            if kind == "local":
                stop_local()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
