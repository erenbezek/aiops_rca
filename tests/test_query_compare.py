"""P2a 4. madde: çağrı listesi, eşitlik ve ham kayıt karşılaştırması (`tools/query_compare.py`), sahte arka uçlarla.

- Çağrı listesi belirlenimli ve tanımdaki bileşimde (HANDOFF 2026-11-11).
- Aynı veri iki tarafta → bütün çağrılar ve ham kayıtlar eşit.
- Prometheus'ta kasıtlı eksik örnek → yalnız ilgili çağrılar farklı, ham kayıtta "yalnız dosyada" 1.
"""
import sys
from pathlib import Path

from test_store_live import S, T0, backends, dataset, stores  # noqa: F401 (backends: fikstür)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import query_compare as qc  # noqa: E402

from aiops_rca import query  # noqa: E402


def test_call_list_composition_and_determinism(tmp_path, backends):  # noqa: F811
    fs, _, _ = stores(tmp_path, backends)
    case = fs.case
    calls = qc.call_list(case, fs)
    assert calls == qc.call_list(case, fs)
    assert [c["id"] for c in calls] == list(range(len(calls)))
    services = [s["service"] for s in query.list_services(fs)["services"]]
    assert services == ["cart", "frontend", "frontend-proxy", "valkey-cart"]
    n = len(services)
    lo, hi = fs.window()
    traces = {s.trace_id for s in fs.spans(lo, hi)}
    errors = {s["trace_id"] for s in query.search_spans(fs, lo, hi, status="error", limit=None)["spans"]}
    want = {"list_services": 1, "metric_series": n * 9 * 3, "search_spans": 3 * (2 + n) + 1,
            "get_trace": len(errors | traces), "search_logs": 3 * (1 + 3 + n + 2), "service_dependencies": 3}
    got = {}
    for c in calls:
        got[c["fn"]] = got.get(c["fn"], 0) + 1
    assert got == want
    assert all(c["args"].get("limit", "none") is None for c in calls if "limit" in c["args"])
    ms = [c for c in calls if c["fn"] == "metric_series"]
    assert {c["args"]["step_s"] for c in ms} == {60}
    assert {(c["args"]["start"], c["args"]["end"]) for c in ms} == {
        (case.alarm_ns - 600 * S, case.alarm_ns), (case.alarm_ns, case.alarm_ns + 600 * S), (lo, hi)}


def test_equal_data_all_calls_equal(tmp_path, backends):  # noqa: F811
    fs, ls, _ = stores(tmp_path, backends, enum_strings=True)
    calls = qc.call_list(fs.case, fs)
    for c in calls:
        a, b = qc.run_call(fs, c), qc.run_call(ls, c)
        assert a == b, (c, qc.first_diff(a, b))
        assert qc.digest(a) == qc.digest(b)
    lo, hi = fs.window()
    raw = qc.raw_compare(fs, ls, lo, hi)
    assert all(v["equal"] for v in raw.values()), raw
    assert raw["spans"]["file"] == 7 and raw["logs"]["file"] == 3


def test_missing_live_sample_detected(tmp_path, backends):  # noqa: F811
    traces, logs, metrics = dataset()
    view_root = tmp_path
    fs, _, _ = stores(view_root, backends, (traces, logs, metrics))
    from test_store_live import FakeBackends  # noqa: E402
    from aiops_rca.store_live import LiveStore  # noqa: E402
    b = FakeBackends(traces, logs, metrics, drop_prom="container_network_io_usage_rx_bytes_total")
    try:
        ls = LiveStore(fs.case, b.ends)
        differ = [c for c in qc.call_list(fs.case, fs) if qc.run_call(fs, c) != qc.run_call(ls, c)]
        assert differ and {(c["fn"], c["args"].get("metric")) for c in differ} == {("metric_series",
                                                                                     "net_rx_bytes_per_s")}
        lo, hi = fs.window()
        raw = qc.raw_compare(fs, ls, lo, hi)
        rx = raw["container.network.io.usage.rx_bytes"]
        assert (rx["equal"], rx["only_file"], rx["only_live"]) == (False, 1, 0)
        assert all(v["equal"] for k, v in raw.items() if k != "container.network.io.usage.rx_bytes")
    finally:
        b.close()


def test_errors_are_outputs(tmp_path, backends):  # noqa: F811
    fs, _, _ = stores(tmp_path, backends)
    out = qc.run_call(fs, {"fn": "metric_series", "args": {"service": "jaeger", "metric": "requests",
                                                           "start": T0, "end": T0 + S}})
    assert out == {"error": "ValueError: service 'jaeger' is excluded (tooling / routine)"}


def test_first_diff():
    assert qc.first_diff({"a": [1, 2, {"b": 3}]}, {"a": [1, 2, {"b": 3}]}) is None
    assert qc.first_diff({"a": [1, 2, {"b": 3}]}, {"a": [1, 2, {"b": 4}]}) == ".a[2].b: 3 != 4"
    assert qc.first_diff([1, 2], [1, 2, 3]) == ": length 2 != 3"
    assert qc.first_diff({"a": 1}, {"b": 1}) == ".a: 1 != missing"
    assert qc.first_diff(1.0, 1) == ".: 1.0 != 1"


def test_diff_paths_and_changed_fields():
    a = {"spans": [{"d": 0.0, "x": 1}, {"d": 2.0, "x": 1}], "total": 2}
    b = {"spans": [{"d": 1e-06, "x": 1}, {"d": 2.0, "x": 3}], "total": 2}
    assert qc.diff_paths(a, b) == {".spans[].d": 1, ".spans[].x": 1}
    assert qc.diff_paths([1], [1, 2]) == {" (length)": 1}
    r = qc._multiset_diff([("t", "s", 10, 10), ("t", "u", 5, 6)], [("t", "s", 10, 11), ("t", "u", 5, 6)],
                          key=lambda t: (t[0], t[1]), fields=("trace", "span", "start", "end"))
    assert (r["only_file"], r["only_live"], r["changed_ids"], r["changed_fields"]) == (1, 1, 1, {"end +1": 1})
