"""API duman testi: aday modellerin ajan projesine teknik olarak uyup uymadığını kontrol eder.

Kalite ölçmez. Üç şeye bakar:
  1. Basit cevap + süre
  2. Tool calling: 3 farklı istemde doğru araç ve doğru argümanlar
  3. Uzun girdi dakikalık token limitine takılıyor mu
       - ~6K token  : kriter
       - ~12K token : sadece bilgi (limitlerde ne kadar boşluk var)

Geçme kriteri: 3/3 tool calling doğru VE ~6K girdi limit hatası vermiyor.

Anahtarlar ortam değişkeninden okunur: GROQ_API_KEY, GEMINI_API_KEY
Sadece standart kütüphane kullanır.

Gemma, Google'ın OpenAI uyumlu katmanında sistematik 500 hatası verdiği için
Google'ın kendi (native) API'si üzerinden çağrılır. Native cevap, testlerin
değişmemesi için OpenAI biçimine çevrilir.

Kullanım:
  python tools/api_smoke_test.py         # testleri çalıştır
  python tools/api_smoke_test.py --list  # Gemini'de erişilebilen model kimliklerini listele
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

PROVIDERS = {
    "groq": {
        "base": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
    },
    "gemini-native": {
        "base": "https://generativelanguage.googleapis.com/v1beta",
        "key_env": "GEMINI_API_KEY",
    },
}

# (etiket, sağlayıcı, model kimliği)
MODELS = [
    ("Groq gpt-oss-120b", "groq", "openai/gpt-oss-120b"),
    ("Gemini 3.5 Flash Lite", "gemini", "gemini-3.5-flash-lite"),
    ("Gemma 4 31B (native)", "gemini-native", "gemma-4-31b-it"),
]

DELAY_BETWEEN_REQUESTS = 5  # saniye; dakikalık istek limitine takılmamak için
DELAY_AFTER_LONG_INPUT = 65  # saniye; dakikalık token sayacının sıfırlanması için
TIMEOUT = 120  # saniye

# Gerçekçi bir log satırı ~30 token (ilk koşuda 400 satır = 11.963 token ölçüldü)
LINES_6K = 200  # kriter
LINES_12K = 400  # bilgi amaçlı

TOOL = {
    "type": "function",
    "function": {
        "name": "query_metrics",
        "description": "Query a time-series metric for a microservice over a recent time window.",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name, e.g. 'checkout'"},
                "metric": {
                    "type": "string",
                    "enum": ["cpu", "memory", "latency_p99", "error_rate"],
                },
                "minutes": {"type": "integer", "description": "Look-back window in minutes"},
            },
            "required": ["service", "metric", "minutes"],
        },
    },
}

# (istem, beklenen argümanlar)
TOOL_CASES = [
    (
        "The checkout service is responding slowly. Get the p99 latency of the checkout service for the last 15 minutes.",
        {"service": "checkout", "metric": "latency_p99", "minutes": 15},
    ),
    (
        "Users report failed payments. Check the error rate of the payment service over the last 5 minutes.",
        {"service": "payment", "metric": "error_rate", "minutes": 5},
    ),
    (
        "I suspect a memory leak in the cart service. Look at its memory usage over the past hour.",
        {"service": "cart", "metric": "memory", "minutes": 60},
    ),
]


def get_key(provider):
    return os.environ.get(PROVIDERS[provider]["key_env"], "")


def send_request(provider, path, body=None):
    """(durum_kodu, json_veya_hata_metni, sure_sn) döndürür."""
    url = PROVIDERS[provider]["base"] + path
    headers = {
        "Content-Type": "application/json",
        # Groq, Python'un varsayılan User-Agent'ını engelleyebiliyor
        "User-Agent": "api-smoke-test/0.1",
    }
    if provider == "gemini-native":
        headers["x-goog-api-key"] = get_key(provider)
    else:
        headers["Authorization"] = "Bearer " + get_key(provider)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8")), time.monotonic() - start
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        return e.code, text, time.monotonic() - start
    except Exception as e:  # zaman aşımı, ağ hatası vb.
        return -1, f"{type(e).__name__}: {e}", time.monotonic() - start


def native_chat(model, messages, tools=None):
    """Google native API çağrısı; cevabı OpenAI biçimine çevirir."""
    body = {
        "contents": [{"role": "user", "parts": [{"text": m["content"]}]} for m in messages],
        "generationConfig": {"temperature": 0},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [t["function"] for t in tools]}]
    status, response, elapsed = send_request("gemini-native", f"/models/{model}:generateContent", body)
    if status != 200:
        return status, response, elapsed
    parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if "text" in p and not p.get("thought"))
    tool_calls = [
        {"function": {"name": p["functionCall"]["name"], "arguments": json.dumps(p["functionCall"].get("args", {}))}}
        for p in parts
        if "functionCall" in p
    ]
    openai_format = {
        "choices": [{"message": {"content": text, "tool_calls": tool_calls}}],
        "usage": {"prompt_tokens": response.get("usageMetadata", {}).get("promptTokenCount", "?")},
    }
    return status, openai_format, elapsed


def chat(provider, model, messages, tools=None):
    if provider == "gemini-native":
        return native_chat(model, messages, tools)
    body = {"model": model, "messages": messages, "temperature": 0}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    return send_request(provider, "/chat/completions", body)


def error_summary(status, body):
    text = re.sub(r"org_\w+", "org_***", str(body))[:300]
    label = "LİMİT" if status in (413, 429) else "HATA"
    return f"{label} {status}: {text}"


def test_simple(provider, model):
    status, body, elapsed = chat(provider, model, [{"role": "user", "content": "Reply with exactly the word: OK"}])
    if status != 200:
        return False, error_summary(status, body)
    content = (body["choices"][0]["message"].get("content") or "").strip()
    return "OK" in content.upper(), f"{elapsed:.1f} sn, cevap: {content[:30]!r}"


def test_tool(provider, model, prompt, expected):
    status, body, elapsed = chat(provider, model, [{"role": "user", "content": prompt}], tools=[TOOL])
    if status != 200:
        return False, error_summary(status, body)
    calls = body["choices"][0]["message"].get("tool_calls") or []
    if not calls:
        return False, "araç çağrılmadı"
    function = calls[0]["function"]
    if function["name"] != "query_metrics":
        return False, f"yanlış araç: {function['name']}"
    try:
        args = json.loads(function["arguments"])
    except (json.JSONDecodeError, TypeError):
        return False, f"geçersiz JSON: {str(function['arguments'])[:60]}"
    diffs = {k: args.get(k) for k, v in expected.items() if args.get(k) != v}
    if diffs:
        return False, f"yanlış argüman: {diffs}"
    return True, f"{elapsed:.1f} sn"


def generate_long_log(line_count):
    """Deterministik sahte log. ERROR satırları sadece 'inventory' servisinde."""
    services = ["frontend", "checkout", "payment", "cart", "shipping", "inventory"]
    lines = []
    for i in range(line_count):
        service = services[i % len(services)]
        # inventory her 6 satırda bir gelir; bunların yarısı ERROR olur
        if service == "inventory" and (i // 6) % 2 == 0:
            lines.append(f"2026-10-13T10:{i // 60:02d}:{i % 60:02d}Z ERROR inventory db connection pool exhausted (active=50/50)")
        else:
            lines.append(f"2026-10-13T10:{i // 60:02d}:{i % 60:02d}Z INFO {service} request handled path=/api/{service} status=200 dur_ms={20 + i % 37}")
    return "\n".join(lines)


def test_long_input(provider, model, line_count):
    prompt = (
        "Below are service logs. Which service produces the ERROR lines? Reply with the service name only.\n\n"
        + generate_long_log(line_count)
    )
    status, body, elapsed = chat(provider, model, [{"role": "user", "content": prompt}])
    if status != 200:
        return False, error_summary(status, body)
    tokens = body.get("usage", {}).get("prompt_tokens", "?")
    content = (body["choices"][0]["message"].get("content") or "").strip()
    # Kriter sadece limit hatası olmaması; cevabın doğruluğu bilgi amaçlı
    return True, f"{tokens} token, {elapsed:.1f} sn, cevap: {content[:30]!r}"


def list_models():
    if not get_key("gemini"):
        print("GEMINI_API_KEY tanımlı değil.")
        return
    status, body, _ = send_request("gemini", "/models")
    if status != 200:
        print(error_summary(status, body))
        return
    for m in body.get("data", []):
        model_id = m.get("id", "")
        if "lite" in model_id or "gemma" in model_id:
            print(model_id)


def main():
    if "--list" in sys.argv:
        list_models()
        return

    results = []
    for label, provider, model in MODELS:
        print(f"\n=== {label} ({model}) ===")
        if not get_key(provider):
            print(f"  ATLANDI: {PROVIDERS[provider]['key_env']} tanımlı değil")
            results.append((label, "-", "-", "-", "-", "ATLANDI"))
            continue

        simple_ok, simple_note = test_simple(provider, model)
        print(f"  Basit cevap : {'✓' if simple_ok else '✗'} {simple_note}")
        time.sleep(DELAY_BETWEEN_REQUESTS)

        tool_correct = 0
        for i, (prompt, expected) in enumerate(TOOL_CASES, 1):
            ok, note = test_tool(provider, model, prompt, expected)
            tool_correct += ok
            print(f"  Tool {i}/3    : {'✓' if ok else '✗'} {note}")
            time.sleep(DELAY_BETWEEN_REQUESTS)

        ok_6k, note_6k = test_long_input(provider, model, LINES_6K)
        print(f"  Girdi ~6K   : {'✓' if ok_6k else '✗'} {note_6k}")
        time.sleep(DELAY_AFTER_LONG_INPUT)

        ok_12k, note_12k = test_long_input(provider, model, LINES_12K)
        print(f"  Girdi ~12K  : {'✓' if ok_12k else '✗'} {note_12k}  (bilgi amaçlı)")
        time.sleep(DELAY_BETWEEN_REQUESTS)

        passed = tool_correct == len(TOOL_CASES) and ok_6k
        results.append((
            label,
            "✓" if simple_ok else "✗",
            f"{tool_correct}/3",
            "✓" if ok_6k else "✗",
            "✓" if ok_12k else "✗",
            "GEÇTİ" if passed else "KALDI",
        ))

    print("\n" + "=" * 80)
    print(f"{'Model':<24}{'Basit':<8}{'Tool':<8}{'~6K':<8}{'~12K*':<8}{'Sonuç':<10}")
    print("-" * 80)
    for r in results:
        print(f"{r[0]:<24}{r[1]:<8}{r[2]:<8}{r[3]:<8}{r[4]:<8}{r[5]:<10}")
    print("* bilgi amaçlı, kriter dışı")


if __name__ == "__main__":
    main()
