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


def test_old_style_client_span_matched_by_url_host(tmp_path):
    # Python requests enstrümantasyonu (0.64b0): adres yalnız http.url'de (quote-gateway → quote).
    docs = [doc("quote-gateway", calls("POST", {"http.url": "http://quote:8090/getquote"}, 20, 20)),
            doc("shipping", calls("POST", {"url.full": "http://quote:8090/getquote"}, 20, 20)),
            doc("frontend", calls("GET", {"http.url": "http://172.18.0.15:8090/x"}, 20, 20)),
            doc("cart", calls("GET", {"http.url": "http://valkey-cart:6379/"}, 20, 20)),
            doc("email", calls("GET", {"http.url": "http://[bad"}, 20, 20))]
    rows, _ = rows_for(tmp_path, docs, target="quote", ips=("172.18.0.15",))
    assert set(rows) == {("quote-gateway", "POST"), ("shipping", "POST"), ("frontend", "GET")}
    assert rows[("quote-gateway", "POST")]["after"][0] == 20


def test_address_field_wins_over_url(tmp_path):
    # Yeni biçimli span'lerde sonuç değişmez: server.address varsa URL'e bakılmaz.
    docs = [doc("shipping", calls("POST", {"server.address": "quote-gateway",
                                           "url.full": "http://quote:8090/getquote"}, 20, 20))]
    assert rows_for(tmp_path, docs, target="quote")[0] == {}
    assert set(rows_for(tmp_path, docs, target="quote-gateway")[0]) == {("shipping", "POST")}


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
                        ("pkg_temp_c", 40.0), ("inhibited", True), ("leftovers", [])):
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


def no_side_effects(monkeypatch):
    """cmd_incidents'in süreç düzeyindeki yan etkileri: uyku engeli yan süreci, sinyal işleyicisi, engel listesi."""
    monkeypatch.setattr(sr.subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.setattr(sr.signal, "signal", lambda *a, **k: None)
    monkeypatch.setattr(sr, "inhibited", lambda: True)
    monkeypatch.setattr(sr, "gnome_inhibited", lambda: True)


# --- liste denetimi: frontend yalnız memoryLimit'te hedef olabilir (DECISIONS 2026-10-27, V2c bellek) ---

@pytest.mark.parametrize("fault,param,want", [("memoryLimit", "0.9", 1), ("cpuThrottle", "0.1", 2),
                                              ("containerStop", "on", 2), ("networkDelay", "50ms", 2)])
def test_frontend_target_only_for_memory(monkeypatch, tmp_path, fault, param, want):
    # Geçerli liste koruma adımına kadar gider (koruma burada durdurur: 1); reddedilen liste 2 döner.
    no_side_effects(monkeypatch)
    monkeypatch.setattr(sr, "INCIDENT_RUNS", tmp_path / "runs")
    monkeypatch.setattr(sr, "versions", lambda: {})
    monkeypatch.setattr(sr, "guards", lambda: {"problems": ["test stop"]})
    monkeypatch.setattr(sr, "run_incident", lambda *a, **k: pytest.fail("must not run"))
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    lst = tmp_path / "l.json"
    lst.write_text(json.dumps([{"fault": fault, "target": "frontend", "param": param, "noise_layer": None}]))
    assert sr.cmd_incidents(lst) == want


# --- güvenli durdurma (DECISIONS 2026-10-29 "Gece koşusu için systemd birimi"): signals_deferred, Stopped ---

import os  # noqa: E402
import signal  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402


@pytest.fixture
def fresh_stop(monkeypatch):
    monkeypatch.setattr(sr.signals_deferred, "signals", [])
    monkeypatch.setattr(sr.signals_deferred, "depth", 0)
    monkeypatch.setattr(sr.signals_deferred, "raised", False)


def test_real_signal_in_protected_section_raises_on_exit(fresh_stop):
    old = signal.signal(signal.SIGTERM, sr.signals_deferred.handle)
    try:
        reached_end = False
        with pytest.raises(sr.Stopped, match="stopped by SIGTERM"):
            with sr.signals_deferred():
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.05)  # işleyici burada çalışır; yalnız not alır
                reached_end = True
        assert reached_end and sr.signals_deferred.signals == ["SIGTERM"]
    finally:
        signal.signal(signal.SIGTERM, old)


def test_signal_outside_protected_section_raises_at_once(fresh_stop):
    with pytest.raises(sr.Stopped, match="stopped by SIGINT"):
        sr.signals_deferred.handle(signal.SIGINT, None)


def test_signal_from_other_thread_still_deferred(fresh_stop):
    # İşleyici hangi iş parçacığına düşerse düşsün Python'da ana iş parçacığında çalışır; bayrak yine tutar.
    old = signal.signal(signal.SIGTERM, sr.signals_deferred.handle)
    try:
        with pytest.raises(sr.Stopped):
            with sr.signals_deferred():
                t = threading.Thread(target=lambda: os.kill(os.getpid(), signal.SIGTERM))
                t.start()
                t.join()
                time.sleep(0.05)
    finally:
        signal.signal(signal.SIGTERM, old)


def test_second_signal_noted_never_raised_twice(fresh_stop):
    with pytest.raises(sr.Stopped):
        sr.signals_deferred.handle(signal.SIGTERM, None)
    with sr.signals_deferred():  # temizlik
        sr.signals_deferred.handle(signal.SIGTERM, None)
    sr.signals_deferred.handle(signal.SIGINT, None)  # korunan bölüm dışında da fırlatılmaz
    assert sr.signals_deferred.signals == ["SIGTERM", "SIGTERM", "SIGINT"]


def test_other_exception_kept_stop_left_pending(fresh_stop):
    with pytest.raises(ValueError):
        with sr.signals_deferred():
            sr.signals_deferred.handle(signal.SIGTERM, None)
            raise ValueError("x")
    with pytest.raises(sr.Stopped):
        sr.signals_deferred.check()


class InstantEvent(threading.Event):
    def wait(self, timeout=None):  # run_incident'in beklemeleri (ısınma, normal dönem) testte anında biter
        return self.is_set()


class DummyMonitor:
    def __init__(self, *a):
        self.hot, self.stop_event = InstantEvent(), threading.Event()
        self.max_temp = self.peak_mem_mib = self.jaeger_anon_peak_mib = None
        self.jaeger_swap_peak_mib = self.min_swap_free_gb = None

    def start(self):
        pass

    def is_alive(self):
        return False


def fake_incident_world(monkeypatch, tmp_path, calls):
    """run_incident'in dış dünyası: demo, Docker, Prometheus, flagd; çağrılar `calls`'a."""
    for name, value in (("guards", {"problems": []}), ("versions", {}), ("container_count", sr.CONTAINERS),
                        ("scheduler_state", "stopped"), ("containers", {}), ("_cpu_usec", 0),
                        ("sleep_offset_s", 0.0), ("cgroup_memory", {}), ("prom_max", None), ("prom_increase", 0.0),
                        ("anonymous_volumes", []), ("remove_volumes", {}), ("_inspect", {"ips": ["172.18.0.9"]})):
        monkeypatch.setattr(sr, name, lambda *a, v=value, **k: v)
    monkeypatch.setattr(sr, "Monitor", DummyMonitor)
    monkeypatch.setattr(sr, "demo", lambda cmd, log, raw=True: calls.append(f"demo {cmd}") or 0)
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    for name in ("TELEMETRY", "SNAPSHOTS", "INCIDENTS"):
        monkeypatch.setattr(sr, name, tmp_path / name.lower())
    (tmp_path / "telemetry" / "filtered").mkdir(parents=True)

    def revert(state):
        calls.append("revert")
        state.update(reverted={"exit": 0}, verified=True, after={"ips": ["172.18.0.9"]})
        return state
    monkeypatch.setattr(sr, "revert_fault", revert)


PAUSE = {"fault": "containerPause", "target": "cart", "param": "on", "noise_layer": None, "dry": True}


def run_stopped(tmp_path, monkeypatch):
    night = tmp_path / "night"
    night.mkdir()
    lines = []
    label = sr.run_incident(PAUSE, night, lines.append, False)
    return label, lines, night


def test_sigterm_while_applying_fault_reverts_and_downs(monkeypatch, tmp_path, fresh_stop):
    calls = []
    fake_incident_world(monkeypatch, tmp_path, calls)

    def apply(fault, target, param):  # sinyal hata uygulanırken gelir: korunan bölüm, hata yine kaydedilir
        sr.signals_deferred.handle(signal.SIGTERM, None)
        calls.append("apply")
        return {"fault": fault, "target": target, "param": param, "applied": {"exit": 0}, "applied_ok": True,
                "reverted": None, "verified": None, "after": None}
    monkeypatch.setattr(sr, "apply_fault", apply)
    label, lines, night = run_stopped(tmp_path, monkeypatch)
    assert calls == ["demo up", "apply", "revert", "demo down"]
    assert not label["valid"] and label["invalid_reasons"] == ["stopped by SIGTERM"]
    assert (night / f"{label['incident_id']}.json").exists() and not (tmp_path / "incidents").exists()


def test_sigterm_while_waiting_downs_without_fault(monkeypatch, tmp_path, fresh_stop):
    calls = []
    fake_incident_world(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(sr, "scheduler_state", lambda: sr.signals_deferred.handle(signal.SIGTERM, None))
    monkeypatch.setattr(sr, "apply_fault", lambda *a: pytest.fail("fault must not be applied"))
    label, lines, _ = run_stopped(tmp_path, monkeypatch)
    assert calls == ["demo up", "demo down"] and label["invalid_reasons"] == ["stopped by SIGTERM"]


def test_second_signal_during_cleanup_recorded(monkeypatch, tmp_path, fresh_stop):
    calls = []
    fake_incident_world(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(sr, "scheduler_state", lambda: sr.signals_deferred.handle(signal.SIGTERM, None))
    monkeypatch.setattr(sr, "demo", lambda cmd, log, raw=True: (
        calls.append(f"demo {cmd}"), cmd == "down" and sr.signals_deferred.handle(signal.SIGINT, None))[0] or 0)
    label, lines, _ = run_stopped(tmp_path, monkeypatch)
    assert calls == ["demo up", "demo down"]  # ikinci sinyal temizliği kesmedi
    assert label["invalid_reasons"] == ["stopped by SIGTERM",
                                        "signals during cleanup (cleanup not interrupted): ['SIGINT']"]


def test_first_signal_during_cleanup_finishes_cleanup(monkeypatch, tmp_path, fresh_stop):
    # Vaka başka sebeple biter (zamanlayıcı açık), ilk sinyal temizlikte (`down`) gelir: temizlik sonuna kadar gider.
    calls = []
    fake_incident_world(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(sr, "scheduler_state", lambda: "running")
    monkeypatch.setattr(sr, "demo", lambda cmd, log, raw=True: (
        calls.append(f"demo {cmd}"), cmd == "down" and sr.signals_deferred.handle(signal.SIGTERM, None))[0] or 0)
    label, lines, _ = run_stopped(tmp_path, monkeypatch)
    assert "demo_down" in label["run"]["times"]
    assert label["invalid_reasons"] == ["flagd-ui scheduler running", "stopped by SIGTERM"]


def test_stop_ends_night_with_signal_code(monkeypatch, tmp_path, fresh_stop):
    no_side_effects(monkeypatch)
    monkeypatch.setattr(sr, "INCIDENT_RUNS", tmp_path / "runs")
    monkeypatch.setattr(sr, "versions", lambda: {})
    monkeypatch.setattr(sr, "guards", lambda: {"problems": []})
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    ran = []

    def one(entry, night, log, first):
        ran.append(entry["target"])
        with sr.signals_deferred():  # vaka içinde durduruldu, temizlendi, etiket yazıldı
            sr.signals_deferred.handle(signal.SIGTERM, None)
        return {"valid": False, "run": {"leakage_found": False, "fault_state": None, "baseline_failed": True,
                                        "overheat": False, "coverage_short": False}}

    def one_safe(*a):
        try:
            return one(*a)
        except sr.Stopped:
            return {"valid": False, "run": {"leakage_found": False, "fault_state": None, "baseline_failed": True,
                                            "overheat": False, "coverage_short": False}}
    monkeypatch.setattr(sr, "run_incident", one_safe)
    lst = tmp_path / "l.json"
    lst.write_text(json.dumps([dict(PAUSE, target="cart"), dict(PAUSE, target="quote")]))
    assert sr.cmd_incidents(lst) == 128 + signal.SIGTERM
    assert ran == ["cart"]  # sıradaki vakaya ve taban sağlık tekrarına geçilmedi


def test_stop_between_incidents_returns_signal_code(monkeypatch, tmp_path, fresh_stop):
    no_side_effects(monkeypatch)
    monkeypatch.setattr(sr, "INCIDENT_RUNS", tmp_path / "runs")
    monkeypatch.setattr(sr, "versions", lambda: {})
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    monkeypatch.setattr(sr, "guards", lambda: sr.signals_deferred.handle(signal.SIGINT, None))
    monkeypatch.setattr(sr, "run_incident", lambda *a: pytest.fail("must not run"))
    lst = tmp_path / "l.json"
    lst.write_text(json.dumps([PAUSE]))
    assert sr.cmd_incidents(lst) == 128 + signal.SIGINT


# --- kalıntı ve uyku engeli denetimi ---

def guards_with(monkeypatch, left):
    monkeypatch.setattr(sr, "swap_free_gb", lambda: 3.0)
    for name, value in (("monitoring_gb", 1.0), ("snapshot_gb", 1.0), ("gnome_inhibited", True),
                        ("pkg_temp_c", 40.0), ("inhibited", True), ("leftovers", left)):
        monkeypatch.setattr(sr, name, lambda v=value: v)
    return [p for p in sr.guards()["problems"] if p.startswith("leftover")]


def test_leftovers_block_start_with_cleanup_command(monkeypatch):
    left = [{"name": "cart", "state": "running", "paused": True, "nano_cpus": 0},
            {"name": "aiops-netem", "state": "exited", "paused": False, "nano_cpus": 0},
            {"name": "recommendation", "state": "running", "paused": False, "nano_cpus": 30_000_000}]
    (p,) = guards_with(monkeypatch, left)
    assert "cart (running, paused)" in p and "recommendation (running, cpu limit)" in p
    assert p.endswith("clean up by hand: docker unpause cart; docker rm -f aiops-netem; tools/otel_demo.sh down")
    assert guards_with(monkeypatch, []) == []
    assert guards_with(monkeypatch, None) == ["leftover check failed (docker ps)"]


def test_leftovers_reads_demo_project_and_netem(monkeypatch):
    seen = []

    def fake(cmd, **k):
        seen.append(cmd)
        if cmd[:2] == ["docker", "ps"]:
            out = "a1\nb2\n" if "otel-demo" in cmd[-1] else "c3\n"
        else:
            out = "/cart\trunning\ttrue\t0\n/quote\texited\tfalse\t0\n/aiops-netem\trunning\tfalse\t0\n"
        return sr.subprocess.CompletedProcess(cmd, 0, out, "")
    monkeypatch.setattr(sr.subprocess, "run", fake)
    got = sr.leftovers()
    assert [c["name"] for c in got] == ["aiops-netem", "cart", "quote"] and got[1]["paused"]
    assert ["label=com.docker.compose.project=otel-demo", "name=^aiops-netem$"] == [c[-1] for c in seen[:2]]


LIST_OURS = ("aiops_rca scenario_runner    1000 eren 1737589 systemd-inhibit sleep:idle:handle-lid-switch"
             "        incident runs        block\n")


@pytest.mark.parametrize("out,want", [
    (LIST_OURS, True),
    (LIST_OURS.replace("incident runs", "something else"), False),   # neden metni bizimki değil
    (LIST_OURS.replace("scenario_runner", "storage_check").replace("incident runs", "storage card watch"), True),
    (LIST_OURS.replace("aiops_rca", "otherapp"), False),
    (LIST_OURS.replace("block", "delay"), False),
    (LIST_OURS.replace("sleep:idle:handle-lid-switch", "idle"), False),
    ("ModemManager 0 root 1115 ModemManager sleep ModemManager needs to reset devices delay\n", False)])
def test_inhibited_matched_by_our_reason(monkeypatch, out, want):
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, out, ""))
    assert sr.inhibited() is want
