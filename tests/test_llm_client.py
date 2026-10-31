"""LLM çağrı katmanı (HANDOFF 2026-10-30 P1c kartı 1. madde, bitti ölçütü "LLM katmanı"): sahte sunucuyla şema
dönüşümü, şema dışı kaydı, yeniden deneme, token ve süre. Ağ yok: sahte sunucu `127.0.0.1`'de, anahtar sahte."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aiops_rca import llm_client
from aiops_rca.answer import validate_answer
from aiops_rca.llm_client import MODELS, RESPONSE_FORMAT, Pacer, chat, parse_content

GOOD = {"candidates": [
    {"service": "payment", "confidence": 0.7, "evidence_path": ["payment", "checkout", "frontend"], "rationale": "a"},
    {"service": "checkout", "confidence": 0.2, "evidence_path": ["checkout"], "rationale": "b"},
    {"service": "cart", "confidence": 0.1, "evidence_path": ["cart", "frontend"], "rationale": "c"}],
    "unsure": False}
MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


def completion(content, finish="stop", prompt=1200, completion_tokens=150, reasoning=None):
    usage = {"prompt_tokens": prompt, "completion_tokens": completion_tokens, "total_tokens": prompt + completion_tokens}
    if reasoning is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    return 200, {"choices": [{"message": {"content": content}, "finish_reason": finish}], "usage": usage}


class FakeServer:
    """Sıradaki cevabı (durum, gövde) döndürür; gelen istekleri (başlık, gövde) saklar."""

    def __init__(self, replies):
        self.replies, self.requests = list(replies), []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"headers": dict(self.headers), "body": body, "path": self.path})
                status, payload = fake.replies.pop(0)
                data = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1/chat/completions"
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    made = []

    def make(*replies):
        s = FakeServer(replies)
        made.append(s)
        return s
    yield make
    for s in made:
        s.close()


def run(spec_label, srv, **kw):
    sleeps = []
    rec = chat(MODELS[spec_label], MESSAGES, url=srv.url, key=kw.pop("key", "test-key"), sleep=sleeps.append, **kw)
    return rec, sleeps


# --- model tablosu ve şema dönüşümü ---

def test_models_fixed_settings():
    """DECISIONS 2026-10-30 "LLM ayarları", 2026-10-31 "Çıktı sınırı"."""
    assert list(MODELS) == ["qwen3.5-2b", "qwen3.5-4b", "qwen3.5-9b", "gpt-oss-120b", "gemini-3.5-flash-lite"]
    for label in ("qwen3.5-2b", "qwen3.5-4b", "qwen3.5-9b"):
        m = MODELS[label]
        assert (m.provider, m.max_tokens, m.extra) == ("local", 800, {"chat_template_kwargs": {"enable_thinking": False}})
        assert m.gguf == m.model_id and m.model_id.endswith("-Q4_K_M.gguf")
    assert (MODELS["gpt-oss-120b"].provider, MODELS["gpt-oss-120b"].model_id, MODELS["gpt-oss-120b"].max_tokens,
            MODELS["gpt-oss-120b"].extra) == ("groq", "openai/gpt-oss-120b", 1600, {"reasoning_effort": "low"})
    g = MODELS["gemini-3.5-flash-lite"]
    assert (g.provider, g.max_tokens, g.extra) == ("gemini", 1600, {"reasoning_effort": "minimal"})
    assert g.gguf is None


def test_local_server_command_pinned():
    args = llm_client.docker_run_args("Qwen3.5-4B-Q4_K_M.gguf")
    assert llm_client.IMAGE.startswith("ghcr.io/ggml-org/llama.cpp@sha256:")
    assert llm_client.IMAGE in args
    assert args[args.index("-c") + 1] == "8192" and args[args.index("-t") + 1] == "4"
    assert args[args.index("-p") + 1].startswith("127.0.0.1:")
    assert args[args.index("-m") + 1] == "/models/Qwen3.5-4B-Q4_K_M.gguf"


def walk_objects(schema):
    if schema.get("type") == "object":
        yield schema
        for sub in schema["properties"].values():
            yield from walk_objects(sub)
    elif schema.get("type") == "array":
        yield from walk_objects(schema["items"])


def test_answer_schema_strict_and_matches_answer_module():
    """Şema dönüşümü: LLM şeması P1a şemasının alanlarını taşır; strict kuralları (hepsi zorunlu, fazladan alan yok)."""
    assert RESPONSE_FORMAT["type"] == "json_schema" and RESPONSE_FORMAT["json_schema"]["strict"] is True
    schema = RESPONSE_FORMAT["json_schema"]["schema"]
    for obj in walk_objects(schema):
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"])
    from aiops_rca.answer import ANSWER_KEYS, CANDIDATE_KEYS, N_CANDIDATES
    assert set(schema["properties"]) == ANSWER_KEYS
    cands = schema["properties"]["candidates"]
    assert cands["minItems"] == cands["maxItems"] == N_CANDIDATES
    assert set(cands["items"]["properties"]) == CANDIDATE_KEYS
    assert cands["items"]["properties"]["confidence"] == {"type": "number"}  # LLM güven verir (null değil)


def test_request_body(server):
    srv = server(completion(json.dumps(GOOD)))
    run("qwen3.5-4b", srv)
    req = srv.requests[0]
    body = req["body"]
    assert body["model"] == "Qwen3.5-4B-Q4_K_M.gguf" and body["messages"] == MESSAGES
    assert body["temperature"] == 0 and body["max_tokens"] == 800
    assert body["response_format"] == RESPONSE_FORMAT
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert req["headers"]["Authorization"] == "Bearer test-key"


def test_request_body_api_models(server):
    srv = server(completion(json.dumps(GOOD)), completion(json.dumps(GOOD)))
    run("gpt-oss-120b", srv)
    run("gemini-3.5-flash-lite", srv)
    assert srv.requests[0]["body"]["reasoning_effort"] == "low" and srv.requests[0]["body"]["max_tokens"] == 1600
    assert srv.requests[1]["body"]["reasoning_effort"] == "minimal" and srv.requests[1]["body"]["max_tokens"] == 1600
    assert "chat_template_kwargs" not in srv.requests[0]["body"]


def test_no_key_no_auth_header(server):
    srv = server(completion(json.dumps(GOOD)))
    chat(MODELS["qwen3.5-2b"], MESSAGES, url=srv.url, key="", sleep=lambda s: None)
    assert "Authorization" not in srv.requests[0]["headers"]


# --- geçerli cevap, token ve süre ---

def test_valid_answer_tokens_and_duration(server):
    srv = server(completion(json.dumps(GOOD), prompt=5100, completion_tokens=420, reasoning=180))
    ticks = iter([10.0, 13.25])
    rec, sleeps = run("gpt-oss-120b", srv, clock=lambda: next(ticks))
    assert rec["schema_valid"] is True and rec["schema_errors"] == [] and rec["error"] is None
    assert rec["answer"] == GOOD and validate_answer(rec["answer"]) == []
    assert rec["tokens"] == {"input": 5100, "output": 420, "reasoning": 180}
    assert rec["duration_s"] == 3.25 and rec["finish_reason"] == "stop"
    assert rec["raw_output"] == json.dumps(GOOD)
    assert len(rec["attempts"]) == 1 and len(srv.requests) == 1 and sleeps == []


def test_reasoning_text_kept(server):
    status, payload = completion(json.dumps(GOOD))
    payload["choices"][0]["message"]["reasoning"] = "thinking..."
    srv = server((status, payload))
    rec, _ = run("gpt-oss-120b", srv)
    assert rec["attempts"][0]["reasoning_text"] == "thinking..."


def test_fenced_json_read_like_trials(server):
    srv = server(completion("```json\n" + json.dumps(GOOD) + "\n```"))
    rec, _ = run("qwen3.5-2b", srv)
    assert rec["schema_valid"] is True and rec["answer"] == GOOD


# --- şema dışı: kaydedilir, yeniden sorulmaz ---

def bad(**changes):
    obj = json.loads(json.dumps(GOOD))
    for path, value in changes.items():
        i, key = path.split("_", 1)
        obj["candidates"][int(i)][key] = value
    return obj


@pytest.mark.parametrize("content,needle", [
    ("not json at all", "no JSON object"),
    ("{\"candidates\": [", "invalid JSON"),
    ("", "empty content"),
    (json.dumps(bad(**{"0_confidence": 1.5})), "confidence"),
    (json.dumps(bad(**{"1_evidence_path": ["frontend", "checkout"]})), "evidence_path must start"),
    (json.dumps(bad(**{"2_service": "payment", "2_evidence_path": ["payment"]})), "distinct"),
    (json.dumps({"candidates": GOOD["candidates"][:2], "unsure": False}), "exactly 3"),
    (json.dumps({**GOOD, "extra": 1}), "answer keys"),
])
def test_schema_invalid_recorded_not_reasked(server, content, needle):
    srv = server(completion(content))
    rec, sleeps = run("qwen3.5-9b", srv)
    assert rec["schema_valid"] is False and rec["answer"] is None
    assert any(needle in e for e in rec["schema_errors"]), rec["schema_errors"]
    assert rec["raw_output"] == content
    assert len(srv.requests) == 1 and sleeps == []


def test_length_is_schema_invalid_even_if_parseable(server):
    srv = server(completion(json.dumps(GOOD), finish="length"))
    rec, sleeps = run("qwen3.5-2b", srv)
    assert rec["schema_valid"] is False and rec["answer"] is None
    assert rec["schema_errors"][0].startswith("finish_reason length")
    assert rec["tokens"]["output"] == 150  # token yine kayda
    assert len(srv.requests) == 1 and sleeps == []


def test_parse_content_unit():
    assert parse_content(json.dumps(GOOD)) == (GOOD, [])
    assert parse_content(None) == (None, ["empty content"])


# --- yeniden deneme ---

@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transport_error_retried_once(server, status):
    srv = server((status, "busy"), completion(json.dumps(GOOD)))
    rec, sleeps = run("gemini-3.5-flash-lite", srv)
    assert len(srv.requests) == 2 and sleeps == [30]
    assert rec["schema_valid"] is True and len(rec["attempts"]) == 2
    assert rec["attempts"][0]["status"] == status and rec["attempts"][0]["error"] == "busy"


def test_groq_retry_waits_gap(server):
    srv = server((429, "rate"), completion(json.dumps(GOOD)))
    _, sleeps = run("gpt-oss-120b", srv)
    assert sleeps == [65]


def test_transport_error_twice_gives_up(server):
    srv = server((503, "busy"), (503, "still busy"), completion(json.dumps(GOOD)))
    rec, sleeps = run("qwen3.5-4b", srv)
    assert len(srv.requests) == 2 and sleeps == [30]
    assert rec["schema_valid"] is False and rec["answer"] is None and rec["error"] == "still busy"
    assert rec["schema_errors"] == ["no answer: HTTP 503"] and rec["tokens"] is None


@pytest.mark.parametrize("status", [400, 401, 413])
def test_other_http_errors_not_retried(server, status):
    srv = server((status, "rejected"), completion(json.dumps(GOOD)))
    rec, sleeps = run("gpt-oss-120b", srv)
    assert len(srv.requests) == 1 and sleeps == []
    assert rec["error"] == "rejected" and rec["schema_valid"] is False


def test_connection_error_retried_once():
    """Bağlantı reddi (-1) taşıma hatası: bir yeniden deneme, iki deneme de kayda."""
    s = FakeServer([])
    url = s.url
    s.close()  # port artık kapalı
    sleeps = []
    rec = chat(MODELS["qwen3.5-2b"], MESSAGES, url=url, key="", sleep=sleeps.append, timeout=2)
    assert [a["status"] for a in rec["attempts"]] == [-1, -1] and sleeps == [30]
    assert rec["schema_valid"] is False and rec["error"]


def test_malformed_200_not_crash(server):
    srv = server((200, {"unexpected": True}))
    rec, _ = run("qwen3.5-2b", srv)
    assert rec["schema_valid"] is False and rec["error"].startswith("malformed response")


# --- Groq aralığı, anahtarlar ---

def test_pacer_keeps_gap():
    now = [100.0]
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        now[0] += s
    p = Pacer(65, sleep=sleep, clock=lambda: now[0])
    assert p.wait() == 0.0  # ilk istek beklemez
    now[0] += 5
    p.done()  # istek 105'te bitti
    now[0] += 20
    p.wait()
    assert sleeps == [45.0]
    p.done()
    now[0] += 70
    assert p.wait() == 0.0 and sleeps == [45.0]


def test_api_key_from_env_then_file(tmp_path, monkeypatch):
    f = tmp_path / "keys.env"
    f.write_text("# yorum\nexport GROQ_API_KEY=from-file\nGEMINI_API_KEY='quoted'\n", encoding="utf-8")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_client.api_key("groq", keys_file=f) == "from-file"
    assert llm_client.api_key("gemini", keys_file=f) == "quoted"
    assert llm_client.api_key("local", keys_file=f) is None
    monkeypatch.setenv("GROQ_API_KEY", "from-env")
    assert llm_client.api_key("groq", keys_file=f) == "from-env"
    assert llm_client.api_key("gemini", keys_file=tmp_path / "missing") is None


def test_key_not_in_record(server):
    srv = server(completion(json.dumps(GOOD)))
    rec, _ = run("gpt-oss-120b", srv, key="secret-value-123")
    assert "secret-value-123" not in json.dumps(rec)


def test_count_tokens_uses_tokenize_endpoint(server):
    srv = server((200, {"tokens": [1, 2, 3, 4]}))
    base = srv.url.rsplit("/v1/", 1)[0]
    assert llm_client.count_tokens(base, "merhaba dünya") == 4
    assert srv.requests[0]["path"] == "/tokenize" and srv.requests[0]["body"] == {"content": "merhaba dünya"}
    assert llm_client.count_tokens(base, "") == 0 and len(srv.requests) == 1  # boş metin sunucuya gitmez
