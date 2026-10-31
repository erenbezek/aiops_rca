"""LLM çağrı katmanı (HANDOFF 2026-10-30 P1c kartı 1. madde; DECISIONS 2026-10-30 "LLM ayarları", 2026-10-31
"Çıktı sınırı"). `tools/trial_ask_models.py`'den taşındı; deneme betiği olduğu gibi kalır.

- Beş model, sabit kimliklerle (`MODELS`). Hepsi OpenAI uyumlu `chat/completions` ucu: yerel llama.cpp sunucusu,
  Groq, Gemini. Bütün modellerde temperature 0 ve aynı cevap şeması (`ANSWER_SCHEMA`: P1a cevap şemasının LLM
  biçimi, `json_schema` `strict`). Qwen'de düşünme kapalı (`enable_thinking: false`), gpt-oss akıl yürütme `low`,
  Gemini `minimal` (en düşükleri; kapatılamıyor).
- Çıktı sınırı: yerel 800, API 1600 (akıl yürütme dahil). Tek deneme: sınıra takılan cevap (`finish_reason:
  length`) şema dışı sayılır, yeniden sorulmaz.
- Taşıma hatasında (bağlantı/zaman aşımı, 429, 500, 502, 503, 504) bir kez yeniden denenir; ilk deneme kayda girer,
  süre ve cevap ikinci denemedendir. Başka HTTP hatası (ör. 400, 413) yeniden denenmez, kayda girer.
- Şema dışı cevap yeniden sorulmaz: `schema_valid: false`, hatalar `schema_errors`'a. Okuyucu denemelerdeki gibi
  cevaptaki ilk JSON nesnesini okur (``` dahil); nesne `answer.validate_answer`'dan geçmelidir.
- Token (girdi, çıktı, akıl yürütme; sağlayıcının `usage`'ı) ve süre kayda. Kaydı yazmak çağıranın işi (`runs.py`).
- Groq dakikada 8K token: Groq istekleri arasında `GROQ_GAP` sn (`Pacer`).
- Yerel sunucu bir kez açılır (`LocalServer`): digest'le sabit imaj, bağlam 8192, 4 iş parçacığı, `127.0.0.1`.
- API anahtarları ortamdan, yoksa `~/.config/aiops_rca/keys.env`'den; ekrana ve kayda yazılmaz. CI'da anahtar ve ağ
  yok (testler sahte sunucuyla, `127.0.0.1`).
Yeni bağımlılık yok (standart kütüphane).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from aiops_rca.answer import N_CANDIDATES, validate_answer

IMAGE = "ghcr.io/ggml-org/llama.cpp@sha256:8f3c2cd0808a394d1e7ce02f025f453caacbf163389fe6b6443ec3a1efff96a0"
MODELS_DIR = Path.home() / "cerebrum2" / "models"
KEYS_FILE = Path.home() / ".config" / "aiops_rca" / "keys.env"
LOCAL_PORT = 8081
LOCAL_NAME = "aiops-llm"
THREADS = 4
CONTEXT = 8192
TIMEOUT = 900  # saniye; 9B ~6K girdide ~5 dk (LOCAL_MODEL_BENCH), 800 çıktıyla pay
GROQ_GAP = 65
RETRY_WAIT = {"local": 30, "groq": GROQ_GAP, "gemini": 30}
TRANSPORT_ERRORS = frozenset({-1, 429, 500, 502, 503, 504})
LOCAL_MAX_TOKENS = 800
API_MAX_TOKENS = 1600

ENDPOINTS = {
    "local": f"http://127.0.0.1:{LOCAL_PORT}/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
}
KEY_ENV = {"local": None, "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}


@dataclass(frozen=True)
class ModelSpec:
    """Bir model: kayıt etiketi, sağlayıcı, istekteki model kimliği, çıktı sınırı, istek gövdesine eklenen alanlar."""
    label: str
    provider: str
    model_id: str
    max_tokens: int
    extra: dict = field(default_factory=dict)

    @property
    def gguf(self) -> str | None:
        return self.model_id if self.provider == "local" else None


_NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}
MODELS = {m.label: m for m in (
    ModelSpec("qwen3.5-2b", "local", "Qwen3.5-2B-Q4_K_M.gguf", LOCAL_MAX_TOKENS, _NO_THINK),
    ModelSpec("qwen3.5-4b", "local", "Qwen3.5-4B-Q4_K_M.gguf", LOCAL_MAX_TOKENS, _NO_THINK),
    ModelSpec("qwen3.5-9b", "local", "Qwen3.5-9B-Q4_K_M.gguf", LOCAL_MAX_TOKENS, _NO_THINK),
    ModelSpec("gpt-oss-120b", "groq", "openai/gpt-oss-120b", API_MAX_TOKENS, {"reasoning_effort": "low"}),
    ModelSpec("gemini-3.5-flash-lite", "gemini", "gemini-3.5-flash-lite", API_MAX_TOKENS, {"reasoning_effort": "minimal"}),
)}

# P1a cevap şemasının (answer.py) LLM biçimi. strict: bütün alanlar zorunlu, fazladan alan yok (Groq şartı).
# LLM güven verir (sayı; 0–1 aralığı ve diğer kurallar `validate_answer`'da). Servis adı serbest metin, enum yok.
ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["candidates", "unsure"],
    "properties": {
        "candidates": {
            "type": "array", "minItems": N_CANDIDATES, "maxItems": N_CANDIDATES,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["service", "confidence", "evidence_path", "rationale"],
                "properties": {
                    "service": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence_path": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
            },
        },
        "unsure": {"type": "boolean"},
    },
}
RESPONSE_FORMAT = {"type": "json_schema",
                   "json_schema": {"name": "root_cause_answer", "strict": True, "schema": ANSWER_SCHEMA}}


def api_key(provider: str, *, keys_file: Path = KEYS_FILE) -> str | None:
    """Ortam değişkeni, yoksa `keys.env` (`export AD=değer` satırları). Değer hiçbir yere yazılmaz."""
    name = KEY_ENV[provider]
    if name is None:
        return None
    if os.environ.get(name):
        return os.environ[name]
    try:
        lines = keys_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        m = re.fullmatch(r"\s*(?:export\s+)?" + re.escape(name) + r"\s*=\s*(.*?)\s*", line)
        if m:
            return m.group(1).strip("'\"") or None
    return None


def request_body(spec: ModelSpec, messages: list[dict]) -> dict:
    return {"model": spec.model_id, "messages": messages, "temperature": 0, "max_tokens": spec.max_tokens,
            "response_format": RESPONSE_FORMAT, **spec.extra}


def post(url: str, body: dict, key: str | None, timeout: float) -> tuple[int, dict | str]:
    """(HTTP durumu, JSON gövde ya da hata metni); bağlantı/zaman aşımı -1."""
    headers = {"Content-Type": "application/json", "User-Agent": "aiops-rca/0.1"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8")
        try:
            return r.status, json.loads(text)
        except ValueError:
            return r.status, text[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500]
    except Exception as e:  # zaman aşımı, bağlantı reddi
        return -1, f"{type(e).__name__}: {e}"[:500]


def parse_content(content: str | None) -> tuple[dict | None, list[str]]:
    """Cevaptaki ilk JSON nesnesi ve şema hataları. (nesne, []) geçerli; aksi halde (None, hatalar)."""
    if not content:
        return None, ["empty content"]
    text = re.sub(r"```(?:json)?", "", content)
    start = text.find("{")
    if start < 0:
        return None, ["no JSON object in content"]
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError as e:
        return None, [f"invalid JSON: {e}"]
    errors = validate_answer(obj)
    return (None, errors) if errors else (obj, [])


def _attempt(status: int, resp: dict | str, elapsed: float) -> dict:
    out = {"status": status, "elapsed_s": round(elapsed, 3)}
    if status != 200 or not isinstance(resp, dict):
        out["error"] = resp if isinstance(resp, str) else json.dumps(resp)[:500]
        return out
    try:
        choice = resp["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError):
        out["error"] = "malformed response: " + json.dumps(resp)[:500]
        return out
    usage = resp.get("usage") or {}
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    out.update(finish_reason=choice.get("finish_reason"), content=message.get("content"),
               reasoning_text=message.get("reasoning") or message.get("reasoning_content"), usage=usage,
               tokens={"input": usage.get("prompt_tokens"), "output": usage.get("completion_tokens"),
                       "reasoning": reasoning})
    return out


def chat(spec: ModelSpec, messages: list[dict], *, url: str | None = None, key: str | None = None,
         timeout: float = TIMEOUT, sleep: Callable[[float], None] = time.sleep,
         clock: Callable[[], float] = time.monotonic) -> dict:
    """Modele bir kez sorar (taşıma hatasında bir yeniden deneme). Dönen kayıt:
    `attempts` (her deneme: durum, süre, hata ya da içerik/token), `answer` (şemaya uyan nesne ya da None),
    `schema_valid`, `schema_errors`, `raw_output` (son denemenin içeriği), `finish_reason`, `tokens`, `duration_s`
    (son denemenin süresi), `error` (son deneme başarısızsa)."""
    url = url or ENDPOINTS[spec.provider]
    if key is None:
        key = api_key(spec.provider)
    body = request_body(spec, messages)
    attempts = []
    for i in range(2):
        t0 = clock()
        status, resp = post(url, body, key, timeout)
        attempts.append(_attempt(status, resp, clock() - t0))
        if status not in TRANSPORT_ERRORS or i == 1:
            break
        sleep(RETRY_WAIT[spec.provider])
    last = attempts[-1]
    record = {"attempts": attempts, "answer": None, "schema_valid": False, "schema_errors": [],
              "raw_output": last.get("content"), "finish_reason": last.get("finish_reason"),
              "tokens": last.get("tokens"), "duration_s": last["elapsed_s"], "error": last.get("error")}
    if "error" in last:
        record["schema_errors"] = [f"no answer: HTTP {last['status']}"]
        return record
    obj, errors = parse_content(last.get("content"))
    if last.get("finish_reason") == "length":  # sınıra takılan cevap şema dışı (DECISIONS 2026-10-31)
        obj, errors = None, ["finish_reason length (output limit reached)"] + errors
    record.update(answer=obj, schema_valid=obj is not None, schema_errors=errors)
    return record


class Pacer:
    """İki istek arasında en az `gap` sn (Groq dakikalık sınırı). `wait()` istekten önce, `done()` istekten sonra."""

    def __init__(self, gap: float, *, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.gap, self.sleep, self.clock = gap, sleep, clock
        self.last_end: float | None = None

    def wait(self) -> float:
        if self.last_end is None:
            return 0.0
        delay = self.last_end + self.gap - self.clock()
        if delay > 0:
            self.sleep(delay)
            return delay
        return 0.0

    def done(self) -> None:
        self.last_end = self.clock()


def docker_run_args(gguf: str, *, models_dir: Path = MODELS_DIR, port: int = LOCAL_PORT,
                    name: str = LOCAL_NAME) -> list[str]:
    return ["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:8080",
            "-v", f"{models_dir}:/models:ro", IMAGE, "--server", "-m", f"/models/{gguf}",
            "-t", str(THREADS), "-c", str(CONTEXT), "--host", "0.0.0.0", "--port", "8080"]


class LocalServer:
    """Yerel llama.cpp sunucusu; bir model için bir kez açılır, bütün vakalar ona sorulur.

        with LocalServer("Qwen3.5-4B-Q4_K_M.gguf") as srv: ...
    """

    def __init__(self, gguf: str, *, port: int = LOCAL_PORT, name: str = LOCAL_NAME, models_dir: Path = MODELS_DIR):
        self.gguf, self.port, self.name, self.models_dir = gguf, port, name, models_dir
        self.base = f"http://127.0.0.1:{port}"

    def _gone(self, timeout_s: int = 60) -> None:
        # `--rm` silmesi arka planda sürer; bitmeden aynı adla `docker run` çakışır (takma ad ön denemesi).
        for _ in range(timeout_s):
            if subprocess.run(["docker", "inspect", self.name], capture_output=True).returncode != 0:
                return
            time.sleep(1)
        raise RuntimeError(f"container {self.name} still exists after {timeout_s} s")

    def start(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
        self._gone()
        subprocess.run(docker_run_args(self.gguf, models_dir=self.models_dir, port=self.port, name=self.name),
                       check=True, capture_output=True)
        for _ in range(180):
            try:
                with urllib.request.urlopen(f"{self.base}/health", timeout=2) as r:
                    if r.status == 200:
                        return
            except Exception:
                pass
            time.sleep(1)
        self.stop()
        raise RuntimeError(f"llama-server did not become healthy for {self.gguf}")

    def stop(self) -> None:
        subprocess.run(["docker", "stop", self.name], capture_output=True)
        self._gone()

    def __enter__(self) -> "LocalServer":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
