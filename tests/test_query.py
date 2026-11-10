"""P2a sorgu katmanı (`query.py`) ve dosya okuyucusu (`store_file.py`), HANDOFF 2026-11-10 P2a 2. madde.

1. Eski çıktıyla eşitlik (CI örnekleri, `tests/fixtures/snapshots/`; ölçütler HANDOFF 2026-11-10 "eşitlik ölçütleri",
   koddan önce yazıldı):
   - `metric_series` (alarm ± 10 dk, `step_s` 600) = `signals.service_rows`: `requests`, `error_rate`, `p95_ms`,
     `p99_ms`, `mem_mb` birebir; `cpu_pct` göreli fark ≤ 1e-4 (hız ms'ye indirilmiş zamanla).
   - `service_dependencies` (`window.json`) = pencereye süzülmüş izlerde `call_graph.service_edges`.
   - `list_services` = izlerdeki servisler ∪ metrik konteynerleri ∪ log servisleri − (araçlar ∪ rutin servisler).
2. Kurallar, sahte veriyle: kırpma, adet sınırı, sıra, süzgeçler, span özeti alanları, log önemi ve metin araması,
   kovalar (sayaç geriye düşmesi, ilk kova, boş kova, arayüz toplamı, ms'ye indirme), bağımlılıklar, dışlamalar.
"""
import json
import math
import sys
import time
from pathlib import Path

import pytest

from aiops_rca import query
from aiops_rca.call_graph import metric_containers, service_edges
from aiops_rca.cases import Case, load_cases
from aiops_rca.query import (EXCLUDED, METRIC_NAMES, get_trace, list_services, metric_series, search_logs,
                             search_spans, service_dependencies)
from aiops_rca.signals import Window, service_rows, summarize
from aiops_rca.store_file import FileStore

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "snapshots"
W = 600 * 10**9
CPU_REL_TOL = 1e-4  # Eren onaylı (HANDOFF 2026-11-10)


# --- 1. Eski çıktıyla eşitlik (CI örnekleri) ------------------------------------------------------------------------

def fixture_cases() -> list[Case]:
    ids = {p.name for p in FIXTURES.iterdir()}
    return [c for c in load_cases(("pilot",), snapshots=FIXTURES) if c.incident_id in ids]


def test_fixture_cases_present():
    assert len(fixture_cases()) == 4


@pytest.mark.parametrize("case", fixture_cases(), ids=lambda c: c.incident_id)
def test_metric_series_equals_p1_service_rows(case):
    rows = service_rows(summarize(sorted(case.view.glob("*.jsonl")), Window(case.alarm_ns))[0])
    store = FileStore(case)
    services = sorted(s for s in rows if s not in EXCLUDED and s != "<unknown>")
    assert services
    checked = 0
    for svc in services:
        row = rows[svc]
        for metric, key in (("requests", "requests"), ("error_rate", "error_rate"), ("p95_ms", "p95_ms"),
                            ("p99_ms", "p99_ms"), ("mem_mb", "mem_mb"), ("cpu_pct", "cpu_pct")):
            res = metric_series(store, svc, metric, case.alarm_ns - W, case.alarm_ns + W, step_s=600)
            assert not res["clipped"]
            assert [p[0] for p in res["points"]] == [case.alarm_ns - W, case.alarm_ns]
            for (_, got), side in zip(res["points"], ("before", "after")):
                want = row.get(f"{key}_{side}", 0 if metric == "requests" else None)
                if metric == "cpu_pct" and want is not None and got is not None:
                    assert math.isclose(got, want, rel_tol=CPU_REL_TOL, abs_tol=0), (svc, side, got, want)
                else:
                    assert got == want, (svc, metric, side, got, want)
                checked += 1
    assert checked > 0


def _window_filtered_traces(case: Case, out: Path) -> Path:
    lo, hi = query.read_window(case.view)
    with (case.view / "traces.jsonl").open(encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            doc = json.loads(line)
            for rs in doc.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    ss["spans"] = [sp for sp in ss.get("spans", []) if lo <= int(sp["startTimeUnixNano"]) < hi]
            dst.write(json.dumps(doc) + "\n")
    return out


@pytest.mark.parametrize("case", fixture_cases(), ids=lambda c: c.incident_id)
def test_service_dependencies_equals_call_graph(case, tmp_path):
    want, _ = service_edges([_window_filtered_traces(case, tmp_path / "traces.jsonl")])
    lo, hi = query.read_window(case.view)
    res = service_dependencies(FileStore(case), lo, hi)
    got = {(e["caller"], e["callee"]): e["calls"] for e in res["edges"]}
    assert want and got == dict(want)


@pytest.mark.parametrize("case", fixture_cases(), ids=lambda c: c.incident_id)
def test_list_services_equals_p1_names(case):
    _, span_names = service_edges([case.view / "traces.jsonl"])
    log_names = set()
    for line in (case.view / "logs.jsonl").open(encoding="utf-8"):
        if line.strip():
            for rl in json.loads(line).get("resourceLogs", []):
                for a in rl.get("resource", {}).get("attributes", []):
                    if a["key"] == "service.name":
                        log_names.add(a["value"]["stringValue"])
    want = (span_names | metric_containers([case.view / "metrics.jsonl"]) | log_names) - EXCLUDED
    got = list_services(FileStore(case))["services"]
    assert {s["service"] for s in got} == want
    assert [s["service"] for s in got] == sorted(want)


def test_metric_names_table_matches_storage_check():
    assert len(METRIC_NAMES) == 6
    sys.path.insert(0, str(REPO / "tools"))
    import storage_check  # noqa: E402
    for name, kind, prom in storage_check.METRICS:
        assert METRIC_NAMES[name] == (kind, prom)


# --- 2. Kurallar, sahte veriyle ------------------------------------------------------------------------------------

T0 = 1_767_225_600 * 10**9  # 2026-01-01T00:00:00Z
S = 10**9
MS = 10**6


def sv(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    return {"stringValue": v}


def span(trace, sid, name, start, dur_ms, kind=2, parent="", status=0, attrs=None, events=None, message=None):
    st = {"code": status} if status else {}
    if message is not None:
        st["message"] = message
    return {"traceId": trace, "spanId": sid, "parentSpanId": parent, "name": name, "kind": kind,
            "startTimeUnixNano": str(start), "endTimeUnixNano": str(start + int(dur_ms * MS)), "status": st,
            "attributes": [{"key": k, "value": sv(v)} for k, v in (attrs or {}).items()], "events": events or []}


def log(t, sev, text, msg, trace=None, observed=None):
    r = {"timeUnixNano": str(t), "severityNumber": sev, "severityText": text, "body": {"stringValue": msg}}
    if observed is not None:
        r["observedTimeUnixNano"] = str(observed)
    if trace:
        r["traceId"] = trace
    return r


def point(t, v, iface=None):
    dp = {"timeUnixNano": str(t), "asInt": str(v)} if isinstance(v, int) else {"timeUnixNano": str(t), "asDouble": v}
    if iface:
        dp["attributes"] = [{"key": "interface", "value": {"stringValue": iface}}]
    return dp


def make_store(tmp: Path, spans=None, logs=None, metrics=None, minutes=30) -> FileStore:
    """spans/logs: {servis: [kayıt]}; metrics: {konteyner: {OTel adı: [veri noktası]}}."""
    view = tmp / "inc-test"
    view.mkdir()
    end = T0 + minutes * 60 * S
    iso = lambda ns: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ns // S))  # noqa: E731
    (view / "window.json").write_text(json.dumps({"start": iso(T0), "end": iso(end)}))
    res = lambda key, name: {"attributes": [{"key": key, "value": {"stringValue": name}}]}  # noqa: E731
    with (view / "traces.jsonl").open("w") as f:
        for svc, sps in (spans or {}).items():
            f.write(json.dumps({"resourceSpans": [{"resource": res("service.name", svc),
                                                   "scopeSpans": [{"spans": sps}]}]}) + "\n")
    with (view / "logs.jsonl").open("w") as f:
        for svc, recs in (logs or {}).items():
            f.write(json.dumps({"resourceLogs": [{"resource": res("service.name", svc),
                                                  "scopeLogs": [{"logRecords": recs}]}]}) + "\n")
    with (view / "metrics.jsonl").open("w") as f:
        for container, by_name in (metrics or {}).items():
            ms = [{"name": n, "sum": {"dataPoints": dps}} for n, dps in by_name.items()]
            f.write(json.dumps({"resourceMetrics": [{"resource": res("container.name", container),
                                                     "scopeMetrics": [{"metrics": ms}]}]}) + "\n")
    return FileStore(Case("inc-test", view, T0 + 15 * 60 * S))


def test_clip_and_outside_range(tmp_path):
    st = make_store(tmp_path, spans={"cart": [span("t1", "a", "op", T0 + S, 5)]})
    r = search_spans(st, T0 - 60 * S, T0 + 60 * S)
    assert r["clipped"] and r["start_ns"] == T0 and r["total"] == 1
    r = search_spans(st, T0 + 31 * 60 * S, T0 + 40 * 60 * S)
    assert r["clipped"] and r["total"] == 0 and r["spans"] == []
    assert not search_spans(st, T0, T0 + 60 * S)["clipped"]


def test_search_spans_filters_order_and_limit(tmp_path):
    t = T0 + 60 * S
    st = make_store(tmp_path, spans={
        "cart": [span("tb", "s2", "GetCart", t, 50), span("ta", "s9", "GetCart", t, 5, status=2),
                 span("ta", "s1", "GetCart", t, 300), span("tc", "s3", "AddItem", t - S, 1, status=1)],
        "ad": [span("td", "s4", "GetAds", t + S, 400, status=2)]})
    r = search_spans(st, T0, T0 + 10 * 60 * S, limit=None)
    assert [s["span_id"] for s in r["spans"]] == ["s3", "s1", "s9", "s2", "s4"]  # başlangıç, trace_id, span_id
    assert not r["truncated"] and r["total"] == 5
    assert [s["span_id"] for s in search_spans(st, T0, T0 + 600 * S, service="cart", limit=None)["spans"]] == \
        ["s3", "s1", "s9", "s2"]
    assert [s["span_id"] for s in search_spans(st, T0, T0 + 600 * S, status="error", limit=None)["spans"]] == \
        ["s9", "s4"]
    assert [s["span_id"] for s in search_spans(st, T0, T0 + 600 * S, status="ok", limit=None)["spans"]] == ["s3"]
    assert len(search_spans(st, T0, T0 + 600 * S, status="unset", limit=None)["spans"]) == 2
    assert [s["span_id"] for s in search_spans(st, T0, T0 + 600 * S, min_duration_ms=50, limit=None)["spans"]] == \
        ["s1", "s2", "s4"]
    assert [s["span_id"] for s in search_spans(st, T0, T0 + 600 * S, operation="AddItem")["spans"]] == ["s3"]
    r = search_spans(st, T0, T0 + 600 * S, limit=2)
    assert r["total"] == 5 and r["truncated"] and [s["span_id"] for s in r["spans"]] == ["s3", "s1"]
    r = search_spans(st, T0, T0 + 600 * S, limit=5)
    assert not r["truncated"]


def test_span_summary_fields(tmp_path):
    t = T0 + 60 * S
    exc = [{"name": "log", "attributes": []},
           {"name": "exception", "attributes": [{"key": "exception.message", "value": {"stringValue": "boom"}}]}]
    sp1 = span("t1", "a", "Charge", t, 12.5, attrs={"http.status_code": 500, "http.response.status_code": 404,
                                                     "server.address": "payment"}, events=exc, status=2, message="")
    sp2 = span("t1", "b", "Charge", t + 1, 1, parent="a", attrs={"rpc.grpc.status_code": 13}, status=2,
               message="deadline", events=exc)
    sp2["kind"], sp2["status"]["code"] = "SPAN_KIND_CLIENT", "STATUS_CODE_ERROR"
    st = make_store(tmp_path, spans={"checkout": [sp1, sp2]})
    a, b = search_spans(st, T0, T0 + 600 * S)["spans"]
    assert a == {"trace_id": "t1", "span_id": "a", "parent_span_id": None, "service": "checkout",
                 "operation": "Charge", "kind": 2, "start_ns": t, "duration_ms": 12.5, "status": 2,
                 "status_code": 404, "peer": "payment", "error_text": "boom"}
    assert (b["kind"], b["status"], b["status_code"], b["error_text"], b["parent_span_id"], b["peer"]) == \
        (3, 2, 13, "deadline", "a", None)


def test_get_trace(tmp_path):
    st = make_store(tmp_path, spans={
        "frontend": [span("t1", "b", "x", T0 + 2 * S, 1), span("t2", "c", "y", T0 + S, 1),
                     span("t1", "z", "w", T0 + 40 * 60 * S, 1)],  # pencere dışında: yine de izde
        "cart": [span("t1", "a", "z", T0 + S, 1, parent="b")]})
    r = get_trace(st, "t1")
    assert [s["span_id"] for s in r["spans"]] == ["a", "b", "z"] and r["total"] == 3 and not r["truncated"]
    r = get_trace(st, "t1", limit=1)
    assert r["truncated"] and [s["span_id"] for s in r["spans"]] == ["a"]
    assert get_trace(st, "nope")["total"] == 0


def test_search_logs_rules(tmp_path):
    t = T0 + 60 * S
    long_msg = "x" * 220 + "Needle in the tail" + "y" * 30
    st = make_store(tmp_path, logs={
        "frontend-proxy": [log(t, 0, "", "GET /api/cart 503"), log(t + 999_999, 0, "", "GET / 200")],
        "cart": [log(t, 9, "INFO", "ok"), log(t + 5 * MS, 17, "error", long_msg, trace="tr1"),
                 log(0, 13, "WARN", "observed only", observed=t + 2 * MS)],
        "email": [log(t, 0, "INFO", "sent")]})
    r = search_logs(st, T0, T0 + 600 * S, limit=None)
    assert r["total"] == 6
    # zaman ms'ye iner: t + 999_999 ns → t'nin ms'si; eşitlikte servis, sonra mesaj
    assert [(x["time_ms"], x["service"], x["message"][:9]) for x in r["logs"][:4]] == [
        (t // MS, "cart", "ok"), (t // MS, "email", "sent"), (t // MS, "frontend-proxy", "GET / 200"),
        (t // MS, "frontend-proxy", "GET /api/")]
    assert r["logs"][4]["message"] == "observed only" and r["logs"][4]["time_ms"] == t // MS + 2
    # numarası 0 olanlar yalnız min_severity yokken
    r = search_logs(st, T0, T0 + 600 * S, min_severity=9, limit=None)
    assert {x["service"] for x in r["logs"]} == {"cart"} and r["total"] == 3
    assert search_logs(st, T0, T0 + 600 * S, min_severity=13, limit=None)["total"] == 2
    # tam mesajda arar, ilk 200 karakteri gösterir
    r = search_logs(st, T0, T0 + 600 * S, text="NEEDLE")
    assert r["total"] == 1
    hit = r["logs"][0]
    assert len(hit["message"]) == 200 and hit["truncated_message"] and hit["trace_id"] == "tr1"
    assert hit["severity_number"] == 17 and hit["severity_text"] == "error"
    assert search_logs(st, T0, T0 + 600 * S, service="cart", limit=1)["truncated"]
    assert search_logs(st, T0, T0 + 600 * S, text="503")["logs"][0]["service"] == "frontend-proxy"


def test_metric_series_container_rules(tmp_path):
    cpu, mem = "container.cpu.usage.total", "container.memory.usage.total"
    rx = "container.network.io.usage.rx_bytes"
    lo = T0 + 60 * S
    st = make_store(tmp_path, metrics={"cart": {
        # lo − 10 sn'deki nokta ilk kovanın ilk hızını verir; ms altı kısım hesaba girmez (ms'ye iner)
        cpu: [point(lo - 10 * S + 123, 0), point(lo + 10 * S + 456, 5 * S), point(lo + 20 * S, 7 * S),
              point(lo + 30 * S, 1 * S),  # sayaç geriye düştü: çift atlanır
              point(lo + 40 * S, 2 * S), point(lo + 130 * S, 3 * S)],
        mem: [point(lo + 5 * S, 2**20), point(lo + 15 * S, 3 * 2**20), point(lo + 70 * S, 2**21)],
        rx: [point(lo - 5 * S, 0, "eth0"), point(lo + 5 * S, 1000, "eth0"),
             point(lo - 5 * S, 0, "eth1"), point(lo + 5 * S, 3000, "eth1")]}})
    r = metric_series(st, "cart", "cpu_pct", lo, lo + 180 * S, step_s=60)
    assert [p[0] for p in r["points"]] == [lo, lo + 60 * S, lo + 120 * S]
    b0, b1, b2 = (p[1] for p in r["points"])
    # kova 0: (5e9 / 20 sn), (2e9 / 10 sn), (1e9 / 10 sn) → %25, %20, %10
    assert b0 == pytest.approx((25 + 20 + 10) / 3) and b1 is None and b2 == pytest.approx(100 / 90)
    # ms'ye indirme: lo − 10 sn + 123 ns → lo − 10 sn; lo + 10 sn + 456 ns → lo + 10 sn
    first_rate = (5 * S - 0) / (20 * S) * 100
    r2 = metric_series(st, "cart", "cpu_pct", lo, lo + 15 * S, step_s=15)
    assert r2["points"][0][1] == first_rate
    r = metric_series(st, "cart", "mem_mb", lo, lo + 120 * S, step_s=60)
    assert [p[1] for p in r["points"]] == [2.0, 2.0]
    r = metric_series(st, "cart", "net_rx_bytes_per_s", lo, lo + 60 * S, step_s=60)
    assert r["points"] == [[lo, 100.0 + 300.0]]  # arayüzler toplanır
    assert metric_series(st, "cart", "net_tx_bytes_per_s", lo, lo + 60 * S)["points"] == [[lo, None]]


def test_metric_series_span_rules(tmp_path):
    lo = T0 + 60 * S
    st = make_store(tmp_path, spans={
        "cart": [span("t", "a", "op", lo + S, 10), span("t", "b", "op", lo + 2 * S, 30, status=2),
                 span("t", "c", "op", lo + 3 * S, 1000, kind=3),  # istemci span'i sayılmaz
                 span("t", "d", "op", lo + 4 * S, 20, kind=5)],  # CONSUMER sayılır
        "ad": [span("t", "e", "op", lo + S, 99)]})
    get = lambda m: [p[1] for p in metric_series(st, "cart", m, lo, lo + 120 * S, step_s=60)["points"]]  # noqa: E731
    assert get("requests") == [3, 0]
    assert get("errors") == [1, 0]
    assert get("error_rate") == [1 / 3, None]
    assert get("p95_ms") == [30.0, None] and get("p99_ms") == [30.0, None]


def test_service_dependencies_rules(tmp_path):
    t = T0 + 60 * S
    st = make_store(tmp_path, spans={
        "frontend": [span("t1", "f1", "GET", t, 10), span("t1", "f2", "inner", t + 1, 1, parent="f1", kind=1),
                     span("t2", "f3", "GET", T0 - 5 * S, 10)],  # pencere dışı üst
        "cart": [span("t1", "c1", "GetCart", t + 2, 1, parent="f1"),
                 span("t1", "c2", "GetCart", t + 3, 1, parent="f2", status=2),
                 span("t2", "c3", "GetCart", T0 + S, 1, parent="f3")],  # üstü kümede değil
        "valkey-cart": [span("t1", "v1", "HGET", t + 4, 1, parent="c1")]})
    r = service_dependencies(st, T0, T0 + 600 * S)
    assert r["edges"] == [{"caller": "cart", "callee": "valkey-cart", "calls": 1, "errors": 0},
                          {"caller": "frontend", "callee": "cart", "calls": 2, "errors": 1}]


def test_exclusions_and_validation(tmp_path):
    t = T0 + 60 * S
    st = make_store(tmp_path, spans={"cart": [span("t", "a", "op", t, 1)], "jaeger": [span("t", "j", "op", t, 1)]},
                    logs={"flagd": [log(t, 9, "INFO", "flag")], "cart": [log(t, 9, "INFO", "x")]},
                    metrics={"otel-collector": {"container.memory.usage.total": [point(t, 1)]},
                             "astronomy-db": {"container.memory.usage.total": [point(t, 1)]}})
    assert list_services(st)["services"] == [
        {"service": "astronomy-db", "spans": False, "logs": False, "metrics": True},
        {"service": "cart", "spans": True, "logs": True, "metrics": False}]
    assert [s["service"] for s in search_spans(st, T0, T0 + 600 * S)["spans"]] == ["cart"]
    assert [x["service"] for x in search_logs(st, T0, T0 + 600 * S)["logs"]] == ["cart"]
    with pytest.raises(ValueError):
        metric_series(st, "jaeger", "requests", T0, T0 + 60 * S)
    with pytest.raises(ValueError):
        search_spans(st, T0, T0 + 60 * S, service="flagd")
    with pytest.raises(ValueError):
        search_logs(st, T0, T0 + 60 * S, service="load-generator")
    with pytest.raises(ValueError):
        metric_series(st, "cart", "nope", T0, T0 + 60 * S)
    with pytest.raises(ValueError):
        metric_series(st, "cart", "requests", T0, T0 + 60 * S, step_s=0)
    with pytest.raises(ValueError):
        search_spans(st, T0, T0 + 60 * S, status="failed")
    with pytest.raises(ValueError):
        search_logs(st, T0, T0 + 60 * S, min_severity=0)
    with pytest.raises(ValueError):
        search_spans(st, T0, T0 + 60 * S, limit=-1)


class SupersetStore:
    """Süzgeç kullanmayan okuyucu: her çağrıda bütün kayıtlar. Ortak kod süzgeçleri yeniden uygulamalı."""

    def __init__(self, inner: FileStore):
        self.inner = inner

    def window(self):
        return self.inner.window()

    def names(self):
        return self.inner.names()

    def spans(self, lo, hi, service=None):
        return self.inner._load_spans()

    def trace(self, trace_id):
        return self.inner._load_spans()

    def logs(self, lo, hi, service=None):
        return self.inner._load_logs()

    def metric_points(self, name, lo, hi, container=None):
        return [p for pts in self.inner._load_metrics().values() for p in pts]


def test_store_superset_is_refiltered(tmp_path):
    lo = T0 + 60 * S
    fs = make_store(tmp_path, spans={
        "cart": [span("t1", "a", "op", lo + S, 10, parent="f"), span("t2", "b", "op", T0 - S, 5, status=2),
                 span("t3", "c", "other", lo + 700 * S, 50)],
        "frontend": [span("t1", "f", "GET", lo, 20), span("t4", "g", "GET", lo + 2 * S, 1, kind=3)]},
        logs={"cart": [log(lo, 9, "INFO", "a"), log(T0 - S, 17, "error", "b")], "ad": [log(lo, 13, "WARN", "c")]},
        metrics={"cart": {"container.cpu.usage.total": [point(lo - 10 * S, 0), point(lo + 10 * S, S)],
                          "container.memory.usage.total": [point(lo, 2**20)]},
                 "ad": {"container.cpu.usage.total": [point(lo - 10 * S, 0), point(lo + 10 * S, 3 * S)],
                        "container.memory.usage.total": [point(lo, 2**21)]}})
    ss = SupersetStore(fs)
    a, b = T0 + 30 * S, T0 + 600 * S
    for st_call in (
        lambda st: search_spans(st, a, b, limit=None),
        lambda st: search_spans(st, a, b, service="cart", limit=None),
        lambda st: get_trace(st, "t1"),
        lambda st: search_logs(st, a, b, limit=None),
        lambda st: search_logs(st, a, b, service="cart", limit=None),
        lambda st: service_dependencies(st, a, b),
        *[(lambda m: lambda st: metric_series(st, "cart", m, a, b, step_s=60))(m) for m in query.SERIES],
    ):
        assert st_call(ss) == st_call(fs)
