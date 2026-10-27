"""Altyapı hataları (vaka üretimi V2) için Docker gerektirmeyen testler.

Mekanizmanın kendisi (docker update/stop/pause, tc netem) Docker ister; V2a'da geçici konteynerde ve kuru denemede
sınandı (HANDOFF). Burada: dondurmanın yeniden başlama kaydında görünmesi, parametre biçimleri (katalog uyumu
tests/test_catalog.py'de).
"""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import scenario_runner as sr  # noqa: E402

def state(**kw) -> dict:
    base = {"restarts": 0, "oom": False, "running": True, "started": "t0", "paused": False}
    return {**base, **kw}


def test_paused_target_is_a_change():
    unexpected, expected = sr.split_restarts({"payment": state()}, {"payment": state(paused=True)}, {"payment"})
    assert unexpected == [] and [e["container"] for e in expected] == ["payment"]


def test_paused_non_target_is_unexpected():
    unexpected, _ = sr.split_restarts({"cart": state()}, {"cart": state(paused=True)}, {"payment"})
    assert [e["container"] for e in unexpected] == ["cart"]


def test_unchanged_container_not_reported():
    assert sr.split_restarts({"cart": state()}, {"cart": state()}, set()) == ([], [])


@pytest.mark.parametrize("fault,param,ok", [
    ("cpuThrottle", "0.1", True), ("cpuThrottle", "2", True), ("cpuThrottle", "0.1cpu", False),
    ("memoryLimit", "0.8", True), ("memoryLimit", "1.2", False), ("memoryLimit", "80%", False),
    ("networkDelay", "200ms", True), ("networkDelay", "200", False),
    ("packetLoss", "20%", True), ("packetLoss", "2.5%", True), ("packetLoss", "20", False),
    ("containerStop", "on", True), ("containerPause", "off", False),
])
def test_param_formats(fault, param, ok):
    assert bool(re.fullmatch(sr.PARAM_RE[fault], param)) is ok


def test_every_fault_has_param_rule_and_type():
    assert set(sr.PARAM_RE) == set(sr.INFRA_FAULTS)
    assert set(sr.NETEM_WORD) <= set(sr.INFRA_FAULTS)


def test_schedule_ranges_v2_decision():
    # DECISIONS 2026-10-26 (düzeltme b5740e8): normal 10–14 dk, kuyruk 1–3 dk.
    assert sr.NORMAL_RANGE_S == (600, 840) and sr.TAIL_RANGE_S == (60, 180)


def test_schedule_within_ranges_and_spread():
    runs = [sr.schedule(seed) for seed in range(2000)]
    normals, tails = [r["normal_s"] for r in runs], [r["tail_s"] for r in runs]
    assert min(normals) >= 600 and max(normals) <= 840 and min(tails) >= 60 and max(tails) <= 180
    # Saniye çözünürlüğünde düzgün: aralığın iki ucuna da yakın değerler çıkar, tek bir değere yığılmaz.
    assert min(normals) < 610 and max(normals) > 830 and len(set(normals)) > 200
    assert min(tails) < 65 and max(tails) > 175


def test_same_seed_same_schedule():
    assert sr.schedule(12345) == sr.schedule(12345) == {"seed": 12345, **{k: sr.schedule(12345)[k]
                                                                            for k in ("normal_s", "tail_s")}}
    assert sr.schedule(1) != sr.schedule(2)


# --- çağıran kuralı (durdurma, dondurma): incident_checks.caller_rows / caller_symptom_check ---

import json  # noqa: E402

import incident_checks as ic  # noqa: E402
from trial_summary import Window  # noqa: E402

ALARM = 1_800_000_000 * 10**9
MS = 10**6


def cspan(name, t, dur_ms, attrs, kind=3, error=False):
    s = {"name": name, "kind": kind, "startTimeUnixNano": str(t), "endTimeUnixNano": str(t + int(dur_ms * MS)),
         "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in attrs.items()]}
    if error:
        s["status"] = {"code": 2}
    return s


def doc(service, spans):
    return {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
                               "scopeSpans": [{"spans": spans}]}]}


def calls(name, attrs, n_before, n_after, ms_after=5.0, err_after=0):
    before = [cspan(name, ALARM - 60 * 10**9 + i * MS, 5, attrs) for i in range(n_before)]
    after = [cspan(name, ALARM + 60 * 10**9 + i * MS, ms_after, attrs, error=i < err_after) for i in range(n_after)]
    return before + after


def rows_for(tmp_path, docs, target="payment", ips=()):
    f = tmp_path / "traces.jsonl"
    f.write_text("".join(json.dumps(d) + "\n" for d in docs))
    return ic.caller_rows([f], Window(ALARM), target, ips)


TARGET_SERVER = doc("payment", [cspan("oteldemo.PaymentService/Charge", ALARM - 10**9, 3,
                                      {"rpc.service": "oteldemo.PaymentService"}, kind=2)])


def test_callers_matched_by_name_ip_and_rpc(tmp_path):
    docs = [TARGET_SERVER,
            doc("frontend", calls("A", {"server.address": "payment"}, 20, 20)),
            doc("checkout", calls("B", {"server.address": "172.18.0.14"}, 20, 20)),
            doc("checkout", calls("oteldemo.PaymentService/Charge",
                                  {"server.address": "10.0.0.9", "rpc.method": "oteldemo.PaymentService/Charge"},
                                  20, 20)),
            doc("cart", calls("C", {"server.address": "valkey-cart"}, 20, 20))]
    rows, rpcs = rows_for(tmp_path, docs, ips=("172.18.0.14",))
    assert rpcs == ["oteldemo.PaymentService"]
    assert set(rows) == {("frontend", "A"), ("checkout", "B"), ("checkout", "oteldemo.PaymentService/Charge")}


def test_unknown_ip_not_matched(tmp_path):
    rows, _ = rows_for(tmp_path, [doc("checkout", calls("B", {"server.address": "172.18.0.14"}, 20, 20))])
    assert rows == {}


def test_stop_shows_as_caller_errors(tmp_path):
    rows, _ = rows_for(tmp_path, [doc("checkout", calls("B", {"server.address": "payment"}, 20, 20, err_after=20))])
    s = ic.caller_symptom_check(rows, "payment")
    assert s["verdict"] == "symptomatic" and s["deciding"]["signal"] == "error_rate"
    e = ic.event_check(s, {})
    assert e["applied"] and e["pass"] and e["basis"].startswith("caller checkout")


def test_pause_shows_as_caller_latency(tmp_path):
    rows, _ = rows_for(tmp_path, [doc("frontend", calls("A", {"server.address": "payment"}, 20, 20, ms_after=15000))])
    s = ic.caller_symptom_check(rows, "payment")
    assert s["verdict"] == "symptomatic" and s["deciding"]["signal"] in ("p95_ms", "p99_ms")


def test_caller_below_min_requests_not_measured(tmp_path):
    rows, _ = rows_for(tmp_path, [doc("frontend", calls("A", {"server.address": "payment"}, 20,
                                                        ic.MIN_OP_REQUESTS - 1, err_after=5))])
    s = ic.caller_symptom_check(rows, "payment")
    assert s["verdict"] == "not_measurable" and s["callers_measured"] == 0
    assert ic.event_check(s, {})["applied"] is False


def test_healthy_target_no_symptom(tmp_path):
    rows, _ = rows_for(tmp_path, [doc("frontend", calls("A", {"server.address": "payment"}, 20, 20))])
    assert ic.caller_symptom_check(rows, "payment")["verdict"] == "no_symptom"


# --- temizlik doğrulaması ve bellek parametresi (DECISIONS 2026-10-26 "Bellek hatası"): sahte docker ---

class FakeClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, s):
        self.t += s


def fake_docker(monkeypatch, reads):
    """`_inspect` sırayla `reads`'i döndürür (son eleman tekrarlanır); docker komutları başarılı; zaman sahte."""
    seq = list(reads)
    monkeypatch.setattr(sr, "_inspect", lambda target: seq.pop(0) if len(seq) > 1 else seq[0])
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    clock = FakeClock()
    monkeypatch.setattr(sr.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(sr.time, "sleep", clock.sleep)
    return clock


def insp(**kw) -> dict:
    base = {"running": True, "paused": False, "restarts": 0, "oom_killed": False, "nano_cpus": 0,
            "memory": 0, "memory_swap": 0, "ips": ["172.18.0.9"]}
    return {**base, **kw}


def paused_state() -> dict:
    return {"fault": "containerPause", "target": "quote", "param": "on", "before": insp(), "applied": {"exit": 0},
            "applied_ok": True, "reverted": None, "after": None, "stable": None, "verified": False}


def test_revert_verified_when_running_with_ip_and_stable(monkeypatch):
    clock = fake_docker(monkeypatch, [insp(), insp()])
    st = sr.revert_fault(paused_state())
    assert st["verified"] and st["stable"] == {"restarts_start": 0, "restarts_end": 0, "seconds": sr.STABLE_S}
    assert clock.t >= sr.STABLE_S


def test_revert_not_verified_without_ip(monkeypatch):
    # Kuru denemedeki cart: çalışıyor görünüyor ama yeniden başlıyor, IP boş.
    fake_docker(monkeypatch, [insp(ips=[])])
    st = sr.revert_fault(paused_state())
    assert not st["verified"] and st["stable"] is None


def test_revert_not_verified_when_restarting_during_stable(monkeypatch):
    fake_docker(monkeypatch, [insp(restarts=3), insp(restarts=4)])
    st = sr.revert_fault(paused_state())
    assert not st["verified"] and st["stable"]["restarts_start"] == 3 and st["stable"]["restarts_end"] == 4


def test_memory_limit_from_total_usage(monkeypatch):
    # Sınır anon'a değil toplam kullanıma (memory.current) göre.
    limit = int(0.8 * 50.0 * 2**20)
    fake_docker(monkeypatch, [insp(), insp(memory=limit, memory_swap=limit)])
    monkeypatch.setattr(sr, "cgroup_memory", lambda c: {"current_mib": 50.0, "anon_mib": 20.0, "file_mib": 28.0})
    st = sr.apply_fault("memoryLimit", "cart", "0.8")
    assert st["applied_ok"] and st["applied"]["limit_bytes"] == limit and st["applied"]["usage_mib"] == 50.0


def test_stable_seconds_decision():
    assert sr.STABLE_S == 30


# --- V2c (DECISIONS 2026-10-27): ağ belirtisinde güçlü olan, boş swap koruması, Jaeger CPU okuması ---

def sym(strength):
    return {"verdict": "x", "deciding": None if strength is None else {"strength": strength}}


@pytest.mark.parametrize("own,callers,pick", [(0.1, 7.2, "callers"), (30.0, 40.0, "callers"), (63.0, 5.0, "own"),
                                              (2.0, 2.0, "own"), (None, 3.0, "callers"), (1.0, None, "own")])
def test_stronger_symptom(own, callers, pick):
    a, b = sym(own), sym(callers)
    assert ic.stronger_symptom(a, b) is (a if pick == "own" else b)


MEMINFO = "MemTotal:       32000000 kB\nSwapTotal:       4194300 kB\nSwapFree:         {} kB\n"


def test_swap_free_gb_reads_meminfo(monkeypatch):
    monkeypatch.setattr(sr, "read", lambda path: MEMINFO.format(976563) if path == "/proc/meminfo" else None)
    assert sr.swap_free_gb() == 1.0  # 976.563 KiB = 1,000 GB (ondalık)


@pytest.mark.parametrize("free,blocked", [(0.99, True), (1.0, False), (2.5, False), (None, True)])
def test_swap_guard(monkeypatch, free, blocked):
    monkeypatch.setattr(sr, "swap_free_gb", lambda: free)
    for name, value in (("monitoring_gb", 1.0), ("snapshot_gb", 1.0), ("gnome_inhibited", True),
                        ("pkg_temp_c", 40.0)):
        monkeypatch.setattr(sr, name, lambda v=value: v)
    g = sr.guards()
    assert g["swap_free_gb"] == free
    assert any(p.startswith("swap free") for p in g["problems"]) is blocked


def test_min_swap_threshold_decision():
    assert sr.MIN_SWAP_FREE_GB == 1


def test_cpu_usec_reads_cpu_stat(monkeypatch):
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "abc\n", ""))
    stat = "usage_usec 123456789\nuser_usec 100\nsystem_usec 23\n"
    monkeypatch.setattr(sr, "read", lambda path: stat if path.endswith("docker-abc.scope/cpu.stat") else None)
    assert sr._cpu_usec("jaeger") == 123456789


def test_export_failure_queries_cover_decision():
    assert set(sr.EXPORT_FAILURE_QUERIES) == {"otlp_grpc_jaeger", "jaeger_storage_exporter", "collector_refused"}
    assert all('exporter="otlp_grpc/jaeger"' in q for q in sr.EXPORT_FAILURE_QUERIES["otlp_grpc_jaeger"])
    assert all('exporter="jaeger_storage_exporter"' in q for q in sr.EXPORT_FAILURE_QUERIES["jaeger_storage_exporter"])
    # Desen yok: her sorgu tek metrik adı (adı düşen seriler çakışmasın).
    assert not any("__name__" in q for qs in sr.EXPORT_FAILURE_QUERIES.values() for q in qs)


@pytest.mark.parametrize("reply,want", [({"status": "success", "data": {"result": []}}, 0.0),
                                        ({"status": "success", "data": {"result": [{"value": [0, "3"]}]}}, 3.0),
                                        ({"status": "error", "error": "same labelset"}, None)])
def test_prom_increase_empty_is_zero_error_is_none(monkeypatch, reply, want):
    monkeypatch.setattr(sr, "http", lambda *a, **k: reply)
    assert sr.prom_increase("x_total", 600) == want


# --- liste denetimi: frontend yalnız memoryLimit'te hedef olabilir (DECISIONS 2026-10-27, V2c bellek) ---

@pytest.mark.parametrize("fault,param,want", [("memoryLimit", "0.9", 1), ("cpuThrottle", "0.1", 2),
                                              ("containerStop", "on", 2), ("networkDelay", "50ms", 2)])
def test_frontend_target_only_for_memory(monkeypatch, tmp_path, fault, param, want):
    # Geçerli liste koruma adımına kadar gider (koruma burada durdurur: 1); reddedilen liste 2 döner.
    monkeypatch.setenv("SCENARIO_RUNNER_INHIBITED", "1")
    monkeypatch.setattr(sr, "INCIDENT_RUNS", tmp_path / "runs")
    monkeypatch.setattr(sr, "versions", lambda: {})
    monkeypatch.setattr(sr, "guards", lambda: {"problems": ["test stop"]})
    monkeypatch.setattr(sr, "run_incident", lambda *a, **k: pytest.fail("must not run"))
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    lst = tmp_path / "l.json"
    lst.write_text(json.dumps([{"fault": fault, "target": "frontend", "param": param, "noise_layer": None}]))
    assert sr.cmd_incidents(lst) == want
