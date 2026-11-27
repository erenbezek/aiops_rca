"""Canlı demo web arayüzü (`tools/live_demo.py serve`) testleri: FastAPI test istemcisiyle; ağ ve Docker yok."""
import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import live_demo as ld  # noqa: E402

PORT, TOKEN = 8765, "tok"
BASE = f"http://127.0.0.1:{PORT}"


class FakeProc:
    def __init__(self):
        self.pid, self.returncode, self.signals = 4242, None, []

    def poll(self):
        return self.returncode

    def send_signal(self, sig):
        self.signals.append(sig)
        self.returncode = -sig


def client(tmp_path, spawned=None):
    spawned = [] if spawned is None else spawned

    def spawn(key, model):
        p = FakeProc()
        spawned.append((key, model, p))
        return p
    app = ld.make_app(TOKEN, PORT, spawn=spawn, root=tmp_path)
    return TestClient(app, base_url=BASE), spawned


H = {ld.TOKEN_HEADER: TOKEN}


def test_page_and_lists(tmp_path):
    c, _ = client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200 and "Canlı demo" in r.text and "X-Demo-Token" in r.text
    f = c.get("/api/faults").json()
    assert {x["key"] for x in f["faults"]} == set(ld.faults()) and f["default_model"] == ld.DEFAULT_MODEL
    assert c.get("/api/status").json()["running"] is False


@pytest.mark.parametrize("headers, status", [
    ({}, 403),                                                     # belirteç yok
    ({ld.TOKEN_HEADER: "wrong"}, 403),                             # yanlış belirteç
    ({**H, "Origin": "http://evil.example"}, 403),                 # başka bir sayfadan
    ({**H, "Origin": BASE}, 200),
    (H, 200),                                                      # Origin yoksa (curl) belirteç yeter
])
def test_run_requires_token_and_origin(tmp_path, headers, status):
    c, spawned = client(tmp_path)
    r = c.post("/api/run", json={"key": "containerStop:recommendation"}, headers=headers)
    assert r.status_code == status and len(spawned) == (status == 200)


def test_run_rejects_bad_host(tmp_path):
    app = ld.make_app(TOKEN, PORT, spawn=lambda k, m: FakeProc(), root=tmp_path)
    c = TestClient(app, base_url="http://attacker.example:8765")   # DNS yeniden bağlama
    assert c.post("/api/run", json={"key": "containerStop:recommendation"}, headers=H).status_code == 403


@pytest.mark.parametrize("path", ["/", "/api/faults", "/api/status", "/api/report"])
def test_read_endpoints_check_host(tmp_path, path):
    app = ld.make_app(TOKEN, PORT, spawn=lambda k, m: FakeProc(), root=tmp_path)
    assert TestClient(app, base_url="http://evil.example:8765").get(path).status_code == 403


def test_run_body_must_be_object(tmp_path):
    c, spawned = client(tmp_path)
    assert c.post("/api/run", json=[1], headers=H).status_code == 400
    assert c.post("/api/run", content=b"not json", headers=H).status_code == 400 and spawned == []


def test_run_accepted_list_and_lock(tmp_path):
    c, spawned = client(tmp_path)
    assert c.post("/api/run", json={"key": "rm -rf /"}, headers=H).status_code == 400
    assert c.post("/api/run", json={"key": "adFailure_on", "model": "gpt-5"}, headers=H).status_code == 400
    assert c.post("/api/run", json={"key": "adFailure_on", "model": "qwen3.5-4b"}, headers=H).status_code == 200
    assert c.post("/api/run", json={"key": "adFailure_on"}, headers=H).status_code == 409    # tek demo
    assert spawned[0][:2] == ("adFailure_on", "qwen3.5-4b")
    spawned[0][2].returncode = 0                                   # bitti → yeniden başlatılabilir
    assert c.post("/api/run", json={"key": "adFailure_on"}, headers=H).status_code == 200


def test_stop_sends_sigterm_to_demo_process(tmp_path):
    import signal
    c, spawned = client(tmp_path)
    assert c.post("/api/stop", json={}, headers=H).status_code == 409
    c.post("/api/run", json={"key": "containerStop:recommendation"}, headers=H)
    assert c.post("/api/stop", json={}).status_code == 403
    assert c.post("/api/stop", json={}, headers=H).status_code == 200
    assert spawned[0][2].signals == [signal.SIGTERM]


def test_spawn_targets_python_demo_process(monkeypatch):
    seen = {}
    monkeypatch.setattr(ld.subprocess, "Popen", lambda cmd, env: seen.update(cmd=cmd, env=env) or FakeProc())
    ld.spawn_run("networkDelay:quote", "gemini-3.5-flash-lite")
    assert seen["cmd"][0] == sys.executable and seen["cmd"][2:] == [
        "run", "--fault", "networkDelay", "--target", "quote", "--model", "gemini-3.5-flash-lite"]
    assert seen["env"]["SCENARIO_RUNNER_INHIBITED"] == "1"         # sarmalayıcı yok: sinyal doğrudan python'a
    ld.spawn_run("paymentFailure_10pct", "qwen3.5-4b")
    assert seen["cmd"][2:5] == ["run", "--scenario", "paymentFailure_10pct"]


def test_serve_binds_loopback_only(monkeypatch):
    import uvicorn
    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(kw))
    assert ld.serve(9999) == 0 and seen["host"] == "127.0.0.1" and seen["port"] == 9999


CHILD = textwrap.dedent('''
    import sys, time
    sys.path.insert(0, {tools!r})
    import live_demo as ld, scenario_runner as sr
    from contextlib import contextmanager
    ld.SYMPTOM_S = 60
    ld.demo_guards = lambda: {{"problems": []}}
    ld.baseline = lambda now: {{"pass": True, "problems": []}}
    ld.load_dashboard = lambda: {{"ok": True}}
    sr._inspect = lambda t: {{"running": True}}
    sr.container_count = lambda: sr.CONTAINERS
    sr.apply_fault = lambda f, t, p: {{"fault": f, "target": t, "param": p, "before": {{"running": True}},
                                      "applied_ok": True}}
    sr.revert_fault = lambda st: {{**st, "verified": True, "reverted_by": "child"}}
    @contextmanager
    def am(label, factory, base=None):
        yield (lambda case: None), {{}}
    ld.agent_method = am
    sys.exit(ld.run("containerStop:recommendation", "gemini-3.5-flash-lite", root=__import__("pathlib").Path({root!r}),
                    base="http://127.0.0.1:1"))
''')


def test_stop_reaches_revert_in_real_process(tmp_path):
    """Gerçek alt süreç (`run`, sahte koşucu): arayüzün durdurması belirti sırasında SIGTERM gönderir, demo geri alır."""
    root = tmp_path / "runs"
    code = CHILD.format(tools=str(TOOLS), root=str(root))
    procs = []

    def spawn(key, model):
        p = subprocess.Popen([sys.executable, "-c", code])
        procs.append(p)
        return p
    c = TestClient(ld.make_app(TOKEN, PORT, spawn=spawn, root=root), base_url=BASE)
    assert c.post("/api/run", json={"key": "containerStop:recommendation"}, headers=H).status_code == 200
    deadline = time.time() + 30
    while time.time() < deadline and not ((c.get("/api/status").json().get("times_utc") or {}).get("alarm")):
        time.sleep(0.2)
    time.sleep(0.5)                                                # belirti beklemesinde
    assert c.post("/api/stop", json={}, headers=H).status_code == 200
    assert procs[0].wait(timeout=30) == 1
    rec = json.loads(next(x for x in root.iterdir() if x.is_dir()).joinpath("run.json").read_text())
    assert rec["stopped"] == "stopped by SIGTERM" and rec["revert"]["reverted_by"] == "child"
    assert rec["revert"]["verified"] is True and "agent_start" not in rec["times_utc"]
    s = c.get("/api/status").json()
    assert s["running"] is False and s["exit"] == 1 and s["stopped"] == "stopped by SIGTERM"
