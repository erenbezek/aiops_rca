"""Canlı demo (`tools/live_demo.py`) testleri: sahte koşucu işlevleri ve sahte ajanla; ağ, Docker ve anahtar yok."""
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import live_demo as ld  # noqa: E402
import scenario_runner as sr  # noqa: E402

from aiops_rca.store_live import MAIN_ENDS, REPLAY_ENDS, LiveStore  # noqa: E402

T0 = 1_800_000_000 * 10**9


def test_main_ends_loopback_and_differ_from_replay():
    assert all(re.match(r"http://127\.0\.0\.1:\d+(/|$)", u) for u in MAIN_ENDS.values())
    assert set(MAIN_ENDS) == set(REPLAY_ENDS) and MAIN_ENDS != REPLAY_ENDS
    assert MAIN_ENDS["jaeger"].endswith("/jaeger/ui/api/v3")


def test_accepted_faults_from_runner_tables():
    f = ld.faults()
    infra = {k: v for k, v in f.items() if v["kind"] == "infra"}
    assert len(infra) == len(sr.INFRA_ANSWERS) == len(ld.INFRA_PARAMS)
    for v in infra.values():
        assert re.fullmatch(sr.PARAM_RE[v["fault"]], v["param"]) and v["answer"]["root_cause_service"] == v["target"]
    flags = {k for k, v in f.items() if v["kind"] == "flag"}
    assert flags == {k for k, s in sr.BY_ID.items() if "fault_type" in s}
    assert "loadGeneratorFloodHomepage_on" not in f and "paymentFailure_10pct" in f


def _guards(left):
    return {"problems": ["leftovers from a previous run: ..."] if left else [], "leftovers": left}


@pytest.mark.parametrize("left, bad", [
    ([{"name": "cart", "state": "running", "paused": False, "nano_cpus": 0}], False),
    ([{"name": "cart", "state": "running", "paused": True, "nano_cpus": 0}], True),
    ([{"name": "ad", "state": "running", "paused": False, "nano_cpus": 30000000}], True),
    ([{"name": "currency", "state": "exited", "paused": False, "nano_cpus": 0}], True),
    ([{"name": "aiops-netem", "state": "running", "paused": False, "nano_cpus": 0}], True),
])
def test_demo_guards_allow_running_demo_only(monkeypatch, left, bad):
    monkeypatch.setattr(sr, "guards", lambda: _guards(left))
    monkeypatch.setattr(ld, "netem_leftovers", lambda running: [])
    assert bool(ld.demo_guards()["problems"]) is bad


class World:
    """Sahte koşucu ve ajan; çağrıları kaydeder."""

    def __init__(self, monkeypatch, tmp_path, *, applied=True, verified=True, agent_error=None, leak=False):
        self.calls, self.seen = [], {}
        self.now = T0
        monkeypatch.setattr(sr, "utc_ns", self.utc)
        monkeypatch.setattr(ld, "demo_guards", lambda: {"problems": []})
        monkeypatch.setattr(ld, "baseline", lambda now: {"pass": True, "problems": []})
        monkeypatch.setattr(sr, "apply_fault", lambda f, t, p: self.log("apply", f, t, p) or {
            "fault": f, "target": t, "param": p, "before": {"running": True}, "applied_ok": applied})
        monkeypatch.setattr(sr, "revert_fault", lambda st: self.log("revert", st["fault"]) or {**st, "verified": verified})
        monkeypatch.setattr(sr, "resolve", lambda s: {"variant": "off"})
        monkeypatch.setattr(sr, "set_flag", lambda s, v: self.log("flag", s["flag"], v) or (self.utc(), self.utc(), {}))
        monkeypatch.setattr(ld, "agent_method", self.agent_method)
        monkeypatch.setattr(ld, "assess", lambda store, ans, a, b: {"next_step": {"rule": "human"}})  # ağ yok
        monkeypatch.setattr(ld, "load_dashboard", lambda: {"uid": "aiops-demo", "ok": True})
        monkeypatch.setattr(sr, "_inspect", lambda target: {"running": True, "target": target})
        self.containers = [{"cart": {"restarts": 0, "oom": False, "running": True, "started": "a", "paused": False}}]
        monkeypatch.setattr(sr, "containers", lambda: self.containers[min(len(self.calls) and 1, len(self.containers) - 1)])
        self.agent_error, self.leak, self.root = agent_error, leak, tmp_path / "runs"

    def utc(self):
        self.now += 10**9
        return self.now

    def log(self, *a):
        self.calls.append(a)

    def sleep(self, s):
        self.log("sleep", s)
        self.now += int(s * 10**9)

    @contextmanager
    def agent_method(self, label, factory, base=None):
        def ask(case):
            self.log("agent", label)
            store = factory(case)
            self.seen.update(case=case, store=store, base=base,
                             window=json.loads((case.view / "window.json").read_text()),
                             run_json=json.loads((case.view / "run.json").read_text()))
            if self.agent_error:
                raise self.agent_error
            text = "T+00:01.000 ad flagd.evaluation adFailure" if self.leak else "3 services"
            return {"row": {"end_reason": "answer", "schema_valid": True, "n_tool_calls": 1, "duration_s": 1.0,
                            "tokens": {"input": 1, "output": 1}, "answer": None},
                    "turns": [], "tool_outputs": [{"tool": "list_services", "text": text}]}
        yield ask, {"prompt_sha256": "x"}

    def run(self, key="containerStop:recommendation", model="gemini-3.5-flash-lite"):
        code = ld.run(key, model, root=self.root, base="http://127.0.0.1:1", sleep=self.sleep)
        d = next(x for x in self.root.iterdir() if x.is_dir())
        return code, json.loads((d / "run.json").read_text()), d


def test_run_happy_path_infra(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    code, rec, d = w.run()
    assert code == 0 and rec["result"] == "ok"
    names = [c[0] for c in w.calls]
    assert names == ["apply", "sleep", "agent", "revert"] and w.calls[1] == ("sleep", ld.SYMPTOM_S)
    case = w.seen["case"]
    assert case.incident_id.startswith("demo-") and case.view == d
    assert case.alarm_ns == sr_iso_back(rec["times_utc"]["alarm"])
    assert isinstance(w.seen["store"], LiveStore) and w.seen["store"].ends == MAIN_ENDS
    lo = sr_iso_back(w.seen["window"]["start"] + "")
    assert case.alarm_ns - lo < (ld.NORMAL_S + 1) * 10**9 and case.alarm_ns - lo >= ld.NORMAL_S * 10**9
    assert "answer" not in w.seen["run_json"]                      # ajan çalışırken gerçek cevap kayıtta yok
    assert rec["answer"]["root_cause_service"] == "recommendation" and rec["leakage"]["findings"] == 0
    assert (d / "responses.jsonl").exists() and (d / "tool_outputs").is_dir()
    assert {"mem_available_min_mib", "swap_used_peak_mib"} <= set(rec["memory"])


def sr_iso_back(s: str) -> int:
    from datetime import datetime
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 10**9) // 10**9 * 10**9


def test_agent_error_still_reverts(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, agent_error=RuntimeError("boom"))
    code, rec, _ = w.run()
    assert code == 1 and "boom" in rec["error"] and [c[0] for c in w.calls][-1] == "revert"
    assert rec["revert"]["verified"] is True


def test_injection_not_applied_reverts_without_agent(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, applied=False)
    code, rec, _ = w.run()
    assert code == 1 and [c[0] for c in w.calls] == ["apply", "revert"] and "agent" not in rec


def test_revert_not_verified_is_exit_1(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, verified=False)
    code, rec, _ = w.run()
    assert code == 1 and rec["result"] == "finished with problems"


def test_guard_or_baseline_problem_no_injection(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    monkeypatch.setattr(ld, "demo_guards", lambda: {"problems": ["not on AC power"]})
    code, rec, _ = w.run()
    assert code == 2 and w.calls == [] and rec["result"].startswith("guards")
    w2 = World(monkeypatch, tmp_path / "b")
    monkeypatch.setattr(ld, "baseline", lambda now: {"pass": False, "problems": ["frontend p95 408 ms > 50.6"]})
    code, rec, _ = w2.run()
    assert code == 2 and w2.calls == [] and rec["result"].startswith("baseline")


def test_leakage_stops_demo(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, leak=True)
    code, rec, _ = w.run()
    assert code == 3 and rec["leakage"]["findings"] > 0 and rec["result"].startswith("leakage")
    assert [c[0] for c in w.calls][-1] == "revert"                  # geri alma sızıntıdan önce, her durumda


def test_flag_scenario_on_then_off(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    code, rec, _ = w.run("paymentFailure_10pct", "qwen3.5-4b")
    assert code == 0
    flags = [c for c in w.calls if c[0] == "flag"]
    assert flags == [("flag", "paymentFailure", "10%"), ("flag", "paymentFailure", "off")]
    assert ("agent", "qwen3.5-4b") in w.calls and rec["answer"]["root_cause_service"] == "payment"


def test_flag_not_off_before_is_baseline_problem(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    monkeypatch.setattr(sr, "resolve", lambda s: {"variant": "10%"})
    code, rec, _ = w.run("paymentFailure_10pct")
    assert code == 2 and w.calls == []


def test_cli_rejects_unknown_fault(capsys):
    assert ld.main(["run", "--fault", "containerStop", "--target", "frontend"]) == 2
    assert ld.main(["run", "--scenario", "adFailure_on", "--fault", "containerStop", "--target", "cart"]) == 2
    assert ld.main(["run", "--scenario", "x", "--model", "gemini-3.5-flash-lite"]) == 2


# --- NEXT_STEPS ve değerlendirme (planlama 2026-11-19, 1. düzeltme) ---

BASE_ROW = {"requests_before": 600, "requests_after": 600, "error_rate_before": 0.0, "error_rate_after": 0.0,
            "p95_ms_before": 10.0, "p95_ms_after": 10.0, "cpu_pct_before": 2.0, "cpu_pct_after": 2.0,
            "mem_mb_before": 50.0, "mem_mb_after": 50.0, "new_warn_top": (0, None)}


@pytest.mark.parametrize("service, change, rule", [
    ("valkey-cart", {}, "database"),
    ("cart", {"cpu_pct_after": 30.0}, "resource"),
    ("cart", {"mem_mb_after": 80.0}, "resource"),
    ("cart", {"error_rate_after": 0.2}, "error"),
    ("cart", {"new_warn_top": (40, "redis down")}, "error"),
    ("cart", {"p95_ms_after": 400.0}, "latency"),
    ("cart", {"requests_after": 10}, "down"),
    ("cart", {"requests_after": None, "p95_ms_after": None, "error_rate_after": None}, "down"),
    ("cart", {}, "human"),
    (None, {}, "human"),
])
def test_next_step_rules(service, change, rule):
    ns = ld.next_step(service, {**BASE_ROW, **change} if service else None)
    assert ns["rule"] == rule and ns["text"] == dict((r[0], r[2]) for r in ld.NEXT_STEPS)[rule]
    if rule in ("resource", "error", "latency"):
        assert ns["signals"] and all(v["strength"] >= ld.FIRE for v in ns["signals"].values())


def test_next_step_order_resource_before_error():
    ns = ld.next_step("cart", {**BASE_ROW, "cpu_pct_after": 30.0, "error_rate_after": 0.5})
    assert ns["rule"] == "resource" and set(ns["signals"]) == {"cpu_pct"}


class FakeStore:
    """`query.Store` arayüzü: cart'a frontend'den istek; alarmdan sonra cart'ın p95'i yükselir."""

    def __init__(self, alarm):
        from aiops_rca.query import LogRecord, Span
        self.alarm, self.sp, self.lg = alarm, [], []
        lo = alarm - ld.NORMAL_S * 10**9
        for k in range(1200):
            t = lo + k * 10**9
            slow = t >= alarm
            pid = f"p{k}"
            self.sp.append(Span("t", pid, None, "frontend", "GET", 2, t, t + 30 * 10**6, 0, None, None, None))
            self.sp.append(Span("t", f"c{k}", pid, "cart", "GetCart", 2, t + 1, t + (500 if slow else 5) * 10**6,
                                0, None, None, None))
        for k in range(20):
            self.lg.append(LogRecord(alarm + k * 10**9, "cart", 17, "ERROR", "Wasn't able to connect to redis", None))

    def window(self):
        return self.alarm - 3600 * 10**9, self.alarm + 3600 * 10**9

    def names(self):
        return {"spans": {"frontend", "cart"}, "logs": {"cart"}, "metrics": {"cart", "frontend"}}

    def spans(self, lo, hi, service=None):
        return [s for s in self.sp if lo <= s.start_ns < hi and (service is None or s.service == service)]

    def logs(self, lo, hi, service=None):
        return [r for r in self.lg if lo <= r.time_ns < hi and (service is None or r.service == service)]

    def metric_points(self, name, lo, hi, container=None):
        return []

    def trace(self, trace_id):
        return []


def test_assess_from_live_data():
    alarm = T0
    st = FakeStore(alarm)
    ans = {"candidates": [{"service": "Cart", "confidence": 0.9, "evidence_path": ["cart", "frontend"],
                           "rationale": "x"},
                          {"service": "frontend", "confidence": 0.1, "evidence_path": ["frontend"], "rationale": "y"}],
           "unsure": False}
    a = ld.assess(st, ans, alarm, alarm + ld.SYMPTOM_S * 10**9)
    assert a["matched"] == "cart" and a["row"]["requests_before"] == 600 and a["row"]["requests_after"] == 600
    assert a["row"]["p95_ms_after"] > 400 and a["row"]["new_warn_top"] == (20, "Wasn't able to connect to redis")
    assert a["next_step"]["rule"] == "error" and "new_warn_log" in a["next_step"]["signals"]
    assert a["evidence"][0]["valid"] is True and a["evidence"][1]["valid"] is None
    unknown = ld.assess(st, {**ans, "candidates": [{**ans["candidates"][0], "service": "oteldemo.CartService"}]},
                        alarm, alarm + ld.SYMPTOM_S * 10**9)
    assert unknown["matched"] is None and unknown["next_step"]["rule"] == "human"
    assert ld.assess(st, None, alarm, alarm + 1)["next_step"]["rule"] == "human"


def test_run_records_assessment_after_agent(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    monkeypatch.setattr(ld, "assess", lambda store, ans, a, b: w.log("assess") or {"next_step": {"rule": "human"}})
    code, rec, _ = w.run()
    assert code == 0 and rec["assessment"]["next_step"]["rule"] == "human"
    assert [c[0] for c in w.calls] == ["apply", "sleep", "agent", "revert", "assess"]


def test_next_step_needs_strength_one():
    # hata oranı 0 → 0,03: güç 0,6 (< 1) → yanmaz; 0 → 0,05: güç 1 → yanar
    assert ld.next_step("cart", {**BASE_ROW, "error_rate_after": 0.03})["rule"] == "human"
    assert ld.next_step("cart", {**BASE_ROW, "error_rate_after": 0.05})["rule"] == "error"


def test_report_fields_and_order(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    ans = {"candidates": [{"service": "recommendation", "confidence": 0.8, "evidence_path": ["recommendation",
                                                                                              "frontend"],
                           "rationale": "errors on ListRecommendations"}], "unsure": False}
    turns = [{"kind": "action", "call": "list_services()", "action": {"reason": "start"}},
             {"kind": "answer", "call": None}]
    outs = [{"turn": 0, "call": "list_services()", "text": "18 services\nad: spans=yes\ncart: spans=yes\nx"}]

    @contextmanager
    def agent_method(label, factory, base=None):
        yield (lambda case: {"row": {"end_reason": "answer", "schema_valid": True, "n_tool_calls": 1,
                                     "duration_s": 2.0, "tokens": {"input": 5, "output": 3}, "answer": ans},
                             "turns": turns, "tool_outputs": outs}), {}
    monkeypatch.setattr(ld, "agent_method", agent_method)
    monkeypatch.setattr(ld, "assess", lambda store, a, x, y: {
        "matched": "recommendation", "evidence": [{"valid": True}],
        "next_step": {"rule": "down", "condition": "c", "text": ld.NEXT_STEPS[4][2],
                      "signals": {"request_drop": {"before": 600, "after": 0, "strength": 2.0}}}})
    code, rec, d = w.run()
    r = json.loads((d / "report.json").read_text())
    assert code == 0 and r["candidates"][0]["evidence_valid"] is True and r["next_step"]["rule"] == "down"
    assert r["tool_calls"] == [{"turn": 0, "reason": "start", "call": "list_services()",
                                "output_head": ["18 services", "ad: spans=yes", "cart: spans=yes"]}]
    assert r["note"] == ld.NOTE and r["revert_verified"] is True
    md = (d / "report.md").read_text()
    i = md.index("## Gerçek cevap")
    assert md.index("## Adaylar") < md.index("## Sonraki adım") < md.index("## Araç çağrıları") < i
    assert "recommendation" in md[i:] and "request_drop: önce 600, sonra 0, güç 2.0" in md


def test_no_report_on_leakage(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, leak=True)
    code, _, d = w.run()
    assert code == 3 and not (d / "report.md").exists()


def test_dashboard_file():
    d = json.loads(ld.DASHBOARD.read_text(encoding="utf-8"))
    assert d["uid"] == "aiops-demo" and len(d["panels"]) == 5
    exprs = [t["expr"] for p in d["panels"] for t in p["targets"]]
    assert all(p["datasource"]["uid"] == "webstore-metrics" for p in d["panels"])
    metrics = {"traces_span_metrics_calls_total", "traces_span_metrics_duration_milliseconds_bucket",
               "container_cpu_usage_nanoseconds_total", "container_memory_usage_total_bytes"}
    assert all(any(m in e for m in metrics) for e in exprs)
    assert sum("histogram_quantile(0.95" in e for e in exprs) == 1 and sum("rate(" in e for e in exprs) == 4
    # CPU birikimli sayacın hızı, bir çekirdeğin yüzdesi (P1 / ajan `cpu_pct` ile aynı birim; planlama 2026-11-19).
    # `container_cpu_utilization_ratio` bu collector sürümünde açılıştan beri ortalama: kullanılmaz.
    assert exprs[3] == 'rate(container_cpu_usage_nanoseconds_total{container_name=~"$service"}[3m]) / 1e9 * 100'
    assert not any("utilization_ratio" in e for e in exprs)
    assert d["templating"]["list"][0]["name"] == "service" and all("$service" in e for e in exprs)


def test_load_dashboard_posts_overwrite(monkeypatch):
    seen = {}
    monkeypatch.setattr(sr, "http", lambda m, u, b=None: seen.update(m=m, u=u, b=b) or
                        {"status": "success", "url": "/grafana/d/aiops-demo/x"})
    r = ld.load_dashboard()
    assert r["ok"] and seen["m"] == "POST" and seen["u"] == "http://127.0.0.1:8080/grafana/api/dashboards/db"
    assert seen["b"]["overwrite"] is True and seen["b"]["dashboard"]["uid"] == "aiops-demo"
    monkeypatch.setattr(sr, "http", lambda *a, **k: (_ for _ in ()).throw(OSError("refused")))
    assert ld.load_dashboard()["ok"] is False


def test_dashboard_url_window():
    u = ld.dashboard_url(T0, T0 + 600 * 10**9)
    assert u.startswith("http://127.0.0.1:8080/grafana/d/aiops-demo?") and f"from={T0 // 10**6}" in u



# --- sinyal koruması ve kalıntılar (planlama 2026-11-19, zorunlu düzeltme) ---

def test_sigterm_during_symptom_still_reverts(monkeypatch, tmp_path):
    import os
    import signal
    w = World(monkeypatch, tmp_path)
    monkeypatch.setattr(w, "sleep", lambda s: w.log("sleep", s) or os.kill(os.getpid(), signal.SIGTERM))
    code, rec, _ = w.run()
    assert code == 1 and rec["stopped"] == "stopped by SIGTERM"
    assert [c[0] for c in w.calls] == ["apply", "sleep", "revert"] and rec["revert"]["verified"] is True
    assert signal.getsignal(signal.SIGTERM) is not sr.signals_deferred.handle   # eski işleyici geri kuruldu


def test_signal_during_injection_is_deferred(monkeypatch, tmp_path):
    import os
    import signal
    w = World(monkeypatch, tmp_path)

    def apply(f, t, p):
        os.kill(os.getpid(), signal.SIGINT)            # korunan bölümde: yalnız not edilir
        w.log("apply", f, t, p)
        return {"fault": f, "target": t, "param": p, "before": {"running": True}, "applied_ok": True}
    monkeypatch.setattr(sr, "apply_fault", apply)
    code, rec, _ = w.run()
    assert code == 1 and rec["stopped"] == "stopped by SIGINT" and rec["injection"]["applied_ok"] is True
    assert [c[0] for c in w.calls] == ["apply", "revert"]


def test_injection_error_after_apply_reverts_with_prior_state(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)

    def apply(f, t, p):
        w.log("apply", f, t, p)
        raise OSError("tc show timed out")             # uygulandı, sonra hata
    monkeypatch.setattr(sr, "apply_fault", apply)
    seen = {}
    monkeypatch.setattr(sr, "revert_fault", lambda st: seen.update(st) or w.log("revert") or {**st, "verified": True})
    code, rec, _ = w.run("networkDelay:quote")
    assert code == 1 and "tc show timed out" in rec["error"] and [c[0] for c in w.calls] == ["apply", "revert"]
    assert seen["fault"] == "networkDelay" and seen["target"] == "quote" and seen["before"] == {"running": True,
                                                                                               "target": "quote"}


def test_netem_leftover_stops_guards(monkeypatch):
    left = [{"name": n, "state": "running", "paused": False, "nano_cpus": 0} for n in ("cart", "quote", "ad")]
    monkeypatch.setattr(sr, "guards", lambda: _guards(left))
    shown = {"cart": "qdisc netem 8001: root refcnt 2 limit 1000 delay 50ms", "quote": "qdisc noqueue 0: root"}
    asked = []
    monkeypatch.setattr(sr, "_tc", lambda t, *a: asked.append(t) or type("P", (), {"stdout": shown.get(t, "")})())
    g = ld.demo_guards()
    assert g["netem_leftovers"] == ["cart"] and any(p.startswith("netem rule left on: cart") for p in g["problems"])
    assert sorted(asked) == ["cart", "quote"]                    # yalnız çalışan netem hedefleri; ad değil



def test_sigterm_during_agent_is_deferred(monkeypatch, tmp_path):
    """Ajan aşamasında sinyal ajanın hata yakalayıcısına (`llm_client.post`) düşmez: not edilir, ajan biter, kaydı
    yazılır, sonra durdurma işlenir ve geri alma çalışır."""
    import os
    import signal
    w = World(monkeypatch, tmp_path)

    @contextmanager
    def agent_method(label, factory, base=None):
        def ask(case):
            w.log("agent", label)
            try:  # llm_client.post gibi: her Exception'ı yakalar
                os.kill(os.getpid(), signal.SIGTERM)
                text = "ok"
            except Exception as e:  # noqa: BLE001
                text = f"swallowed {e}"
            return {"row": {"end_reason": "answer", "schema_valid": False, "n_tool_calls": 1, "duration_s": 1.0,
                            "tokens": {"input": 1, "output": 1}, "answer": None},
                    "turns": [], "tool_outputs": [{"turn": 0, "tool": "list_services", "text": text}]}
        yield ask, {}
    monkeypatch.setattr(ld, "agent_method", agent_method)
    code, rec, d = w.run()
    outs = (d / "tool_outputs").read_text() if (d / "tool_outputs").is_file() else \
        "".join(p.read_text() for p in (d / "tool_outputs").iterdir())
    assert code == 1 and rec["stopped"] == "stopped by SIGTERM" and "swallowed" not in outs and '"ok"' in outs
    assert [c[0] for c in w.calls] == ["apply", "sleep", "agent", "revert"] and rec["agent"]["end_reason"] == "answer"


def test_signal_after_revert_recorded(monkeypatch, tmp_path):
    import os
    import signal
    w = World(monkeypatch, tmp_path)
    monkeypatch.setattr(ld, "assess", lambda *a: os.kill(os.getpid(), signal.SIGINT) or {"next_step": {}})
    code, rec, _ = w.run()
    assert code == 1 and rec["stopped"] == "stopped by SIGINT" and rec["result"] == "stopped after revert"
    assert rec["revert"]["verified"] is True



def test_second_run_blocked_by_process_lock(monkeypatch, tmp_path):
    import fcntl
    w = World(monkeypatch, tmp_path)
    w.root.mkdir(parents=True)
    with (w.root / ld.LOCK_NAME).open("a") as held:                # başka bir demo kilidi tutuyor
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert ld.run("adFailure_on", "gemini-3.5-flash-lite", root=w.root, base="x", sleep=w.sleep) == 2
        assert w.calls == [] and not [x for x in w.root.iterdir() if x.is_dir()]
    code, _, _ = w.run()                                           # kilit bırakılınca çalışır
    assert code == 0



def test_restarts_recorded_and_unexpected_fails(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    ok = {"cart": {"restarts": 0, "oom": False, "running": True, "started": "a", "paused": False},
          "recommendation": {"restarts": 0, "oom": False, "running": True, "started": "a", "paused": False}}
    after = {**ok, "recommendation": {**ok["recommendation"], "started": "b"}}        # durdur / başlat: beklenen
    w.containers = [ok, after]
    code, rec, _ = w.run()
    assert code == 0 and rec["restarts"]["unexpected"] == [] and len(rec["restarts"]["expected"]) == 1
    w2 = World(monkeypatch, tmp_path / "b")
    w2.containers = [ok, {**ok, "cart": {**ok["cart"], "restarts": 1, "oom": True}}]  # başka konteynerde OOM
    code, rec, _ = w2.run()
    assert code == 1 and rec["restarts"]["unexpected"][0]["container"] == "cart"


def test_ten_minutes_after_previous_revert(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    code, rec, _ = w.run()
    assert code == 0
    w.now += (ld.NORMAL_S - 60) * 10**9                         # önceki geri almadan 9 dk sonra
    assert ld.run("adFailure_on", "gemini-3.5-flash-lite", root=w.root, base="x", sleep=w.sleep) == 2
    w.now += 120 * 10**9                                        # 11 dk
    assert ld.run("adFailure_on", "gemini-3.5-flash-lite", root=w.root, base="x", sleep=w.sleep) == 0
