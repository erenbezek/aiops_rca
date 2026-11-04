"""LLM yöntemi (HANDOFF 2026-11-01 5. adım planı 5b): sahte llama-server (`/apply-template`, `/tokenize`,
`/v1/chat/completions`) ile uçtan uca `evaluate run --method llm`. Ağ, docker ve anahtar yok."""
import dataclasses
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aiops_rca import evaluate, llm_client
from aiops_rca.inputs import DATA_BUDGET
from aiops_rca.methods import llm
from aiops_rca.runs import read_run
from test_evaluate import label, snapshot

ALARM_S = 1_800_000_000
APPROVED_PROMPT_SHA256 = "6d05378eba8c386d3e5e32638997a1302dd0de625abd60a160f90396b7f1e3ce"  # HANDOFF 2026-11-01


def answer(services, conf=(0.7, 0.2, 0.1)):
    return {"candidates": [{"service": s, "confidence": c, "evidence_path": [s], "rationale": "r"}
                           for s, c in zip(services, conf)], "unsure": False}


def completion(obj, finish="stop", prompt=1500, out=120):
    content = obj if isinstance(obj, str) else json.dumps(obj)
    return 200, {"choices": [{"message": {"content": content}, "finish_reason": finish}],
                 "usage": {"prompt_tokens": prompt, "completion_tokens": out}}


class FakeLlama:
    """Sahte llama-server: şablon = mesaj içeriklerinin birleşimi, token = boşlukla ayrılmış parça; sohbet cevapları
    sırayla. Bütün istekler (yol, gövde) saklanır."""

    def __init__(self, replies=()):
        self.replies, self.requests = list(replies), []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append((self.path, body))
                if self.path == "/apply-template":
                    status, payload = 200, {"prompt": "<tpl> " + " ".join(m["content"] for m in body["messages"])}
                elif self.path == "/tokenize":
                    status, payload = 200, {"tokens": list(range(len(body["content"].split())))}
                else:
                    status, payload = fake.replies.pop(0)
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def chats(self):
        return [b for p, b in self.requests if p == "/v1/chat/completions"]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def fake():
    made = []

    def make(*replies):
        f = FakeLlama(replies)
        made.append(f)
        return f
    yield make
    for f in made:
        f.close()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """inc-a (dev, payment hata verir: ham dolu), inc-b (pilot, hata yok: ham boş). Sahte GGUF dosyaları, SHA256'ları
    model tablosuna yazılır (gerçek dosyalar CI'da yok)."""
    from datetime import datetime, timezone
    inc, snaps, models = tmp_path / "incidents", tmp_path / "snapshots", tmp_path / "models"
    inc.mkdir()
    models.mkdir()
    start = datetime.fromtimestamp(ALARM_S, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for iid, set_, root, bad in (("inc-a", "dev", "payment", "payment"), ("inc-b", "pilot", "cart", "none")):
        lab = label(iid, set_, root)
        lab["answer"]["injection_start"] = start
        (inc / f"{iid}.json").write_text(json.dumps(lab))
        snapshot(snaps / iid, bad)
    for lbl in ("qwen3.5-2b", "qwen3.5-4b"):
        spec = llm_client.MODELS[lbl]
        (models / spec.gguf).write_bytes(lbl.encode())
        monkeypatch.setitem(llm_client.MODELS, lbl, dataclasses.replace(
            spec, gguf_sha256=hashlib.sha256(lbl.encode()).hexdigest()))
    return inc, snaps, models, tmp_path / "runs"


def run(world, fake_server, model="qwen3.5-2b", level="summary", alias=False, cases=None, **opts):
    inc, snaps, models, root = world
    return evaluate.cmd_run("llm", ("pilot", "dev"), False, root, incidents=inc, snapshots=snaps, cases=cases,
                            model=model, level=level, alias=alias,
                            llm_options={"models_dir": models, "base": fake_server.base, **opts})


# --- istem ---

def test_prompt_is_the_approved_text():
    assert llm.prompt_sha256() == APPROVED_PROMPT_SHA256
    assert list(llm.LEVEL_TEXT) == ["raw", "summary", "narrowed"]
    assert llm.TOTAL_BUDGET == 6000


def test_build_messages_only_level_text_and_data_change():
    a = llm.build_messages("summary", "2027-01-15T08:00:00+00:00", "DATA-1")
    b = llm.build_messages("raw", "2027-01-15T08:00:00+00:00", "DATA-2")
    assert [m["role"] for m in a] == ["system", "user"] and a[0] == b[0]
    assert a[0]["content"] == llm.SYSTEM_PROMPT
    assert a[1]["content"].startswith("An alert fired at 2027-01-15T08:00:00+00:00 (UTC). " + llm.LEVEL_TEXT["summary"])
    assert a[1]["content"].endswith("Data:\nDATA-1")
    common_a = a[1]["content"].replace(llm.LEVEL_TEXT["summary"], "").replace("DATA-1", "")
    common_b = b[1]["content"].replace(llm.LEVEL_TEXT["raw"], "").replace("DATA-2", "")
    assert common_a == common_b


# --- koşu ---

def test_local_run_rows_settings_and_request(world, fake):
    srv = fake(completion(answer(["payment", "checkout", "frontend"])), completion(answer(["cart", "frontend", "checkout"])))
    meta, rows = read_run(run(world, srv))
    assert (meta["method"], meta["model_id"], meta["provider"], meta["temperature"]) == \
        ("llm", "Qwen3.5-2B-Q4_K_M.gguf", "local", 0)
    s = meta["settings"]
    assert (s["model"], s["level"], s["alias"], s["max_tokens"], s["data_budget"], s["total_budget"]) == \
        ("qwen3.5-2b", "summary", False, 800, DATA_BUDGET, 6000)
    assert s["prompt_sha256"] == APPROVED_PROMPT_SHA256 and s["image"] == llm_client.IMAGE
    assert (s["gguf"], s["gguf_sha256"]) == ("Qwen3.5-2B-Q4_K_M.gguf", llm_client.MODELS["qwen3.5-2b"].gguf_sha256)
    assert s["extra"] == {"chat_template_kwargs": {"enable_thinking": False}} and "tokenizer" not in s
    assert [r["incident_id"] for r in rows] == ["inc-a", "inc-b"]
    for r in rows:
        assert r["input_status"] == "ok" and r["schema_valid"] is True and r["finish_reason"] == "stop"
        assert r["tokens"]["input"] == 1500 and r["input_tokens_local"] > r["data_tokens"] > 0
        assert len(r["input_sha256"]) == 64 and len(r["attempts"]) == 1 and r["duration_s"] is not None
    chat = srv.chats()
    assert len(chat) == 2 and chat[0]["temperature"] == 0 and chat[0]["max_tokens"] == 800
    assert chat[0]["messages"][0]["content"] == llm.SYSTEM_PROMPT
    assert llm.LEVEL_TEXT["summary"] in chat[0]["messages"][1]["content"]
    assert '"service":"payment"' in chat[0]["messages"][1]["content"]  # gerçek adlı veri bloğu
    applied = [b for p, b in srv.requests if p == "/apply-template"]
    assert applied[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_empty_raw_is_not_asked_and_scored_as_abstain(world, fake):
    inc, snaps, _, _ = world
    srv = fake(completion(answer(["payment", "checkout", "frontend"])))
    run_dir = run(world, srv, level="raw")
    _, rows = read_run(run_dir)
    by = {r["incident_id"]: r for r in rows}
    assert by["inc-a"]["input_status"] == "ok" and by["inc-a"]["schema_valid"] is True
    b = by["inc-b"]
    assert (b["input_status"], b["answer"], b["schema_valid"], b["data_tokens"], b["input_tokens_local"],
            b["attempts"], b["tokens"]) == ("empty", None, None, 0, None, [], None)
    assert len(srv.chats()) == 1  # yalnız inc-a soruldu
    out = evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=snaps)
    pilot = out["table"]["pilot"]
    assert (pilot["input_empty"], pilot["top1"], pilot["top3"], pilot["schema_invalid"], pilot["coverage"],
            pilot["brier_n"], pilot["evidence_null"]) == (1, 0, 0, 0, 0.0, 0, 0)
    assert out["table"]["dev"]["top1"] == 1 and "| Boş girdi |" in evaluate.markdown_table(out["table"])


def test_over_budget_is_not_asked(world, fake, monkeypatch):
    inc, snaps, _, _ = world
    monkeypatch.setattr(llm, "TOTAL_BUDGET", 50)
    srv = fake()
    run_dir = run(world, srv)
    _, rows = read_run(run_dir)
    assert all(r["input_status"] == "over_budget" and r["input_tokens_local"] > 50 and r["answer"] is None
               for r in rows)
    assert srv.chats() == []
    t = evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=snaps)["table"]["all"]
    assert (t["input_over_budget"], t["input_empty"], t["top3"], t["schema_invalid"], t["coverage"]) == (2, 0, 0, 0, 0.0)


def test_length_finish_is_schema_invalid_not_retried(world, fake):
    srv = fake(completion(answer(["payment", "checkout", "frontend"]), finish="length"))
    _, rows = read_run(run(world, srv, cases=("inc-a",)))
    r = rows[0]
    assert (r["input_status"], r["schema_valid"], r["answer"], r["finish_reason"]) == ("ok", False, None, "length")
    assert r["schema_errors"][0].startswith("finish_reason length") and len(srv.chats()) == 1


def test_alias_run_sends_alias_input_and_scores_back(world, fake):
    inc, snaps, _, _ = world
    srv = fake(completion(answer(["billing", "order-processor", "storefront"])),     # takma adla doğru
               completion(answer(["cart", "basket", "storefront"])))                  # gerçek ad unmatched
    run_dir = run(world, srv, alias=True)
    meta, rows = read_run(run_dir)
    assert meta["settings"]["alias"] is True
    for body in srv.chats():
        user = body["messages"][1]["content"]
        assert '"service":"billing"' in user or '"service":"basket"' in user
        assert '"service":"payment"' not in user and '"service":"checkout"' not in user
    cases = {c["incident_id"]: c for c in evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=snaps)["cases"]}
    assert cases["inc-a"]["top1"] and cases["inc-a"]["matched"] == ["payment", "checkout", "frontend"]
    b = cases["inc-b"]
    assert (b["top1"], b["top3"], b["unmatched"], b["matched"]) == (False, True, ["cart"], [None, "cart", "frontend"])


def test_api_model_counts_locally_and_paces_groq(world, fake):
    srv = fake(completion(answer(["payment", "checkout", "frontend"])), completion(answer(["cart", "frontend", "checkout"])))
    sleeps = []
    meta, rows = read_run(run(world, srv, model="gpt-oss-120b", chat_url=f"{srv.base}/v1/chat/completions",
                              key="test-key", sleep=sleeps.append))
    s = meta["settings"]
    assert (meta["provider"], meta["model_id"], s["tokenizer"], s["gguf"], s["max_tokens"]) == \
        ("groq", "openai/gpt-oss-120b", "qwen3.5-4b", "Qwen3.5-4B-Q4_K_M.gguf", 1600)
    assert all(r["input_tokens_local"] and r["tokens"]["input"] == 1500 for r in rows)  # iki sayı yan yana
    assert len(sleeps) == 1 and 0 < sleeps[0] <= llm_client.GROQ_GAP  # ikinci istekten önce aralık
    assert srv.chats()[0]["reasoning_effort"] == "low"


def test_gguf_mismatch_stops_before_run_dir(world, fake, monkeypatch):
    inc, snaps, models, root = world
    spec = llm_client.MODELS["qwen3.5-2b"]
    monkeypatch.setitem(llm_client.MODELS, "qwen3.5-2b", dataclasses.replace(spec, gguf_sha256="0" * 64))
    srv = fake()
    with pytest.raises(ValueError, match="does not match LOCAL_MODEL_BENCH"):
        run(world, srv)
    assert srv.requests == [] and not root.exists()


def test_cli_options_validation(world, capsys):
    inc, snaps, models, root = world
    assert evaluate.main(["run", "--method", "llm", "--level", "summary", "--root", str(root)]) == 2
    assert "needs --model and --level" in capsys.readouterr().err
    assert evaluate.main(["run", "--method", "rule", "--model", "qwen3.5-2b", "--root", str(root)]) == 2
    assert "only for --method llm" in capsys.readouterr().err
    assert evaluate.main(["run", "--method", "rule", "--alias", "--root", str(root)]) == 2


def test_cases_filter(world):
    inc, snaps, _, root = world
    run_dir = evaluate.cmd_run("rule", ("pilot", "dev"), False, root, incidents=inc, snapshots=snaps, cases=("inc-b",))
    meta, rows = read_run(run_dir)
    assert meta["n_cases"] == 1 and [r["incident_id"] for r in rows] == ["inc-b"]
    with pytest.raises(ValueError, match="not in the selected sets"):
        evaluate.cmd_run("rule", ("pilot",), False, root, incidents=inc, snapshots=snaps, cases=("inc-a",))


# --- planlamanın test açıkları (HANDOFF 2026-11-01 5b kontrolü, ek 1) ---

def test_budget_boundary_6000_asked_6001_not(world, fake, monkeypatch):
    probe = fake(completion(answer(["payment", "checkout", "frontend"])))
    need = read_run(run(world, probe, cases=("inc-a",)))[1][0]["input_tokens_local"]
    monkeypatch.setattr(llm, "TOTAL_BUDGET", need)  # tam sınırda: sorulur
    at = fake(completion(answer(["payment", "checkout", "frontend"])))
    row = read_run(run(world, at, cases=("inc-a",)))[1][0]
    assert (row["input_status"], row["input_tokens_local"], len(at.chats())) == ("ok", need, 1)
    monkeypatch.setattr(llm, "TOTAL_BUDGET", need - 1)  # bir fazlası: sorulmaz
    over = fake()
    row = read_run(run(world, over, cases=("inc-a",)))[1][0]
    assert (row["input_status"], row["input_tokens_local"], over.chats()) == ("over_budget", need, [])


def test_local_count_includes_template_and_system_message(world, fake):
    srv = fake(completion(answer(["payment", "checkout", "frontend"])))
    row = read_run(run(world, srv, cases=("inc-a",)))[1][0]
    msgs = srv.chats()[0]["messages"]
    # sahte şablon = "<tpl>" işareti + bütün mesajların içeriği; sahte tokenizer boşlukla ayrılmış parçayı sayar
    assert row["input_tokens_local"] == 1 + len(msgs[0]["content"].split()) + len(msgs[1]["content"].split())
    assert row["input_tokens_local"] > len(msgs[1]["content"].split()) + len(llm.SYSTEM_PROMPT.split())


def test_prompt_alarm_time_same_format_as_summary(world, fake):
    srv = fake(completion(answer(["payment", "checkout", "frontend"])))
    run(world, srv, cases=("inc-a",))
    user = srv.chats()[0]["messages"][1]["content"]
    summary = json.loads(user.split("Data:\n", 1)[1])
    assert summary["alarm_time_utc"] == "2027-01-15T08:00:00+00:00"
    assert user.startswith(f"An alert fired at {summary['alarm_time_utc']} (UTC). ")


# --- cevapsız satır (P1d; DECISIONS 2026-11-01 "Cevapsız satır", "… kapsamı ve adı") ---

def no_answer_row(world, fake, *replies):
    sleeps = []
    srv = fake(*replies)
    run_dir = run(world, srv, cases=("inc-a",), sleep=sleeps.append)
    return run_dir, read_run(run_dir)[1][0], srv, sleeps


def test_two_transport_errors_is_no_answer_not_schema_invalid(world, fake):
    inc, snaps, _, _ = world
    run_dir, row, srv, sleeps = no_answer_row(world, fake, (503, "busy"), (503, "busy"))
    assert (row["no_answer"], row["schema_valid"], row["answer"], [a["status"] for a in row["attempts"]]) == \
        (True, None, None, [503, 503])
    assert row["schema_errors"] == ["no answer: HTTP 503"] and len(sleeps) == 1
    t = evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=snaps)["table"]["all"]
    assert (t["no_answer"], t["schema_invalid"], t["top3"], t["coverage"], t["brier_n"], t["evidence_null"]) == \
        (1, 0, 0, 0.0, 0, 0)
    assert "| Cevapsız |" in evaluate.markdown_table(evaluate.cmd_score(run_dir, False, incidents=inc,
                                                                         snapshots=snaps)["table"])


def test_retry_then_answer_is_not_no_answer(world, fake):
    _, row, _, _ = no_answer_row(world, fake, (503, "busy"), completion(answer(["payment", "checkout", "frontend"])))
    assert (row["no_answer"], row["schema_valid"], [a["status"] for a in row["attempts"]]) == (False, True, [503, 200])


def test_single_400_is_no_answer_without_retry(world, fake):
    _, row, srv, sleeps = no_answer_row(world, fake, (400, "bad request"))
    assert (row["no_answer"], row["schema_valid"], len(row["attempts"]), sleeps) == (True, None, 1, [])
    assert len(srv.chats()) == 1


def test_malformed_200_is_no_answer(world, fake):
    _, row, _, _ = no_answer_row(world, fake, (200, {"usage": {"prompt_tokens": 10}}))
    assert (row["no_answer"], row["schema_valid"], len(row["attempts"])) == (True, None, 1)
    assert row["attempts"][0]["error"].startswith("malformed response")


def test_length_finish_has_content_so_not_no_answer(world, fake):
    _, row, _, _ = no_answer_row(world, fake, completion(answer(["payment", "checkout", "frontend"]), finish="length"))
    assert (row["no_answer"], row["schema_valid"], row["finish_reason"]) == (False, False, "length")


def test_groq_json_validate_failed_row_is_schema_invalid_not_no_answer(world, fake):
    body = {"error": {"code": "json_validate_failed", "type": "invalid_request_error",
                      "failed_generation": '{"candidates": [{"confidence": 0. nine'}}
    _, row, srv, sleeps = no_answer_row(world, fake, (400, body))
    assert (row["no_answer"], row["schema_valid"], len(row["attempts"]), sleeps) == (False, False, 1, [])
    assert row["raw_output"].endswith("0. nine") and row["schema_errors"][0].startswith("json_validate_failed")
