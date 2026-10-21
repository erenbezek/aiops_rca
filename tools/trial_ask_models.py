"""Kaba kalite denemesi: aynı istem ve özeti beş modele sorar (HANDOFF 2026-10-21, DECISIONS 2026-10-21).

Kullanım: python tools/trial_ask_models.py <vaka klasörü>... [--models qwen3.5-2b,gpt-oss-120b,...]
          python tools/trial_ask_models.py <vaka klasörü>... --score   # sadece kayıtlı cevaplardan tablo

Vaka klasörü: `view/summary.json` (modele giden özet) ve `case.json` (doğru cevap; sadece puanlamada okunur,
modele gitmez). Her cevap `answers/<model>.json`'a yazılır; mevcut cevap üzerine yazılmaz (silinip tekrar koşulur).

Modeller:
- Yerel: llama.cpp sunucusu (hız ölçümündeki `full` imajı, digest ile), her model bir kez açılır ve bütün vakalara
  sorulur; 4 iş parçacığı; düşünme kapalı (`enable_thinking: false`); çıktı sınırı 300.
- API: Groq gpt-oss-120b (`reasoning_effort: low`, en düşük; kapatılamıyor) ve Gemini 3.5 Flash Lite
  (`reasoning_effort: minimal`, en düşük; kapatılamıyor). Düşünme token'ları çıktı sınırından düşüyor (Groq'ta
  20 sınırla boş cevap ölçüldü), bu yüzden sınır 2000. Anahtarlar ortamdan (`keys.env`); ekrana basılmaz.
- Beşinde aynı: istem, girdi, temperature 0. JSON modu zorlanmaz; cevaptaki ilk JSON nesnesi okunur (``` dahil).

Kurallar (kart ölçütü):
- Cevap token sınırına takıldı (`finish_reason: length`) ve okunamadıysa sınır bir kez iki katına çıkarılıp
  tekrar sorulur; iki deneme de kayda, puan ikinciden.
- Okunamayan cevap "çözemedi". Doğru servis ilk 3'te → çözdü; top-1 ayrıca yazılır.
- Groq dakikada 8K token: Groq istekleri arasında 65 sn beklenir. Gemini 503/429'da bir kez 30 sn sonra tekrar.
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

# İstem taslağı: Eren onaylayınca değişmez (kart madde 5).
SYSTEM_PROMPT = "You are an SRE assistant doing root cause analysis for a microservice-based online shop."
USER_TEMPLATE = """An alert fired at {alarm_time}. Below is a telemetry summary of the shop for the 10 minutes before \
and the 10 minutes after the alert: for each service, the number of incoming requests, the error rate and the p95 \
latency in milliseconds, and the most frequent warning and error log messages after the alert.

Find the root cause service: the service whose own code or configuration is faulty, not a service that only shows \
symptoms of a problem elsewhere. List the 3 most likely services, most likely first, using service names exactly as \
they appear in the summary, with a one-sentence reason for each.

Answer with JSON only, no other text:
{{"candidates": [{{"service": "<name>", "reason": "<one sentence>"}}, {{"service": "<name>", "reason": "<one sentence>"}}, {{"service": "<name>", "reason": "<one sentence>"}}]}}

Summary:
{summary}"""


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


def ask(kind: str, model: str, max_tokens: int, extra: dict, messages: list[dict]) -> dict:
    url, key_env = ENDPOINTS[kind]
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens, **extra}
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
    attempt["parsed"] = parse_answer(attempt["content"])
    return attempt


def run_model(label: str, kind: str, model: str, max_tokens: int, extra: dict, cases: list[Path]) -> bool:
    ok = True
    for case in cases:
        out = case / "answers" / f"{label}.json"
        if out.exists():
            print(f"skip: {out} exists")
            continue
        messages = build_messages((case / "view" / "summary.json").read_text(encoding="utf-8"))
        attempts = [ask(kind, model, max_tokens, extra, messages)]
        last = attempts[-1]
        if last.get("finish_reason") == "length" and last.get("parsed") is None:
            if kind == "groq":
                time.sleep(GROQ_GAP)
            attempts.append(ask(kind, model, max_tokens * 2, extra, messages))
        record = {"model": label, "kind": kind, "model_id": model, "request": {
            "temperature": 0, **extra}, "system_prompt": SYSTEM_PROMPT, "attempts": attempts}
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


def score(cases: list[Path]) -> None:
    print("\t".join(["case", "model", "top1", "top3", "parsed", "elapsed_s", "input", "reasoning", "answer",
                     "attempts", "answer_services"]))
    for case in cases:
        truth = json.loads((case / "case.json").read_text(encoding="utf-8"))["root_cause_service"].lower()
        for label, *_ in MODELS:
            path = case / "answers" / f"{label}.json"
            if not path.exists():
                continue
            attempts = json.loads(path.read_text(encoding="utf-8"))["attempts"]
            final = attempts[-1]
            services = [s.lower() for s in (final.get("parsed") or [])]
            print("\t".join(str(x) for x in [
                case.name, label, bool(services[:1]) and services[0] == truth, truth in services[:3],
                final.get("parsed") is not None, final.get("elapsed_s"), final.get("input_tokens"),
                final.get("reasoning_tokens"), final.get("answer_tokens"), len(attempts), services]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="+", help="case folders (with view/summary.json)")
    parser.add_argument("--models", help="comma-separated labels; default all")
    parser.add_argument("--score", action="store_true", help="only print the table from saved answers")
    args = parser.parse_args(argv)

    cases = [Path(c).expanduser() for c in args.cases]
    for case in cases:
        if not (case / "view" / "summary.json").is_file():
            print(f"error: {case}/view/summary.json not found", file=sys.stderr)
            return 2
    if args.score:
        score(cases)
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
        if all((case / "answers" / f"{label}.json").exists() for case in cases):
            print(f"skip: {label} already answered every case")
            continue
        try:
            if kind == "local":
                start_local(model)
                for case in cases:
                    text = (case / "view" / "summary.json").read_text(encoding="utf-8")
                    prompt = "\n".join(m["content"] for m in build_messages(text))
                    print(f"{case.name}: summary {count_tokens(text)} tokens, prompt {count_tokens(prompt)} tokens")
            ok &= run_model(label, kind, model, max_tokens, extra, cases)
        except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
            print(f"error: {label}: {e}", file=sys.stderr)
            ok = False
        finally:
            if kind == "local":
                stop_local()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
