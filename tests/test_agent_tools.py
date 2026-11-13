"""P2b 2. madde: ajan araçları (`agent_tools.py`), sahte veriyle (CI'da anahtar ve ağ yok).

- Tanımlar: altı araç, P2a fonksiyonlarıyla aynı ad; parametre türleri; eylem şemasının düz alanları hepsini kapsar.
- Biçim: zaman (`T-mm:ss.mmm`), yuvarlama, boş alanın yazılmaması, hata metninin kısaltılması, iz girintisi, log düzeyi.
- Tek token sınırı: metin ≤ sınır, sığan kadar tam satır, fazlası varsa tek işaret (`[showing the first N of M ...]`).
- Doğrulama: eksik / yanlış türde / bilinmeyen değer → tek satırlık `error: ...`; kullanılmayan alanlar yok sayılır.
- Zaman (P2c-0 A): verilmeyen uç pencerenin ucu; `metric_series`'te alarma hizalı ızgara ve yalnız tam kovalar.
- Servissiz `metric_series` (P2c-0 B): servis başına `query.metric_series` ile aynı değerler, veri yoksa başlıkta.
- Aynı çağrı dosya ve canlı okuyucuda aynı metni verir (sahte arka uçlar, Jaeger'in iki davranışıyla).
- Araç çıktılarının sızıntı taraması.
"""
import json

import pytest

from test_query import MS, S, T0, log, make_store, point, span  # noqa: F401
from test_store_live import backends, dataset, stores  # noqa: F401

from aiops_rca import agent_tools as at
from aiops_rca import query
from aiops_rca.leakage import scan_model_view


def count(text: str) -> int:
    """Sahte token sayacı (CI): 4 karakter ≈ 1 token."""
    return max(1, len(text) // 4)


BIG = 100_000


def test_tool_definitions():
    assert list(at.TOOLS) == ["list_services", "metric_series", "search_spans", "get_trace", "search_logs",
                              "service_dependencies"]
    assert all(hasattr(query, name) for name in at.TOOLS)
    used = set()
    for spec in at.TOOLS.values():
        assert spec["description"].endswith(".")
        for key, (kind, required, doc) in spec["params"].items():
            assert kind in ("string", "number", "integer") and isinstance(required, bool) and doc
            used.add(key)
    assert used == set(at.ARG_FIELDS)


def test_rel_time():
    a = T0 + 15 * 60 * S
    assert at.rel_time(a, a) == "T+00:00.000"
    assert at.rel_time(a - 1, a) == "T-00:00.000"
    assert at.rel_time(a + 65 * S + 123_999_999, a) == "T+01:05.123"
    assert at.rel_time(a - 600 * S, a, ms=False) == "T-10:00"
    assert at.rel_time(a + 12 * 60 * S, a) == "T+12:00.000"


def _store(tmp_path):
    a = T0 + 15 * 60 * S
    err = "connection refused: " + "x" * 200
    st = make_store(tmp_path, spans={
        "frontend": [span("t1", "f1", "GET /", a - 61 * S, 40.04, attrs={"http.response.status_code": 200}),
                     span("t1", "f2", "grpc.Cart/GetCart", a - 61 * S + 1000, 30, kind=3, parent="f1",
                          attrs={"server.address": "cart"})],
        "cart": [span("t1", "c1", "GetCart", a - 61 * S + 2000, 25, parent="f2", status=2, message=err,
                      attrs={"rpc.grpc.status_code": 14}),
                 span("t2", "c2", "GetCart", a + 30 * S, 12, status=2, message="boom"),
                 span("t3", "c3", "AddItem", a + 31 * S, 5)]},
        logs={"cart": [log(a + 5 * S + 120 * MS, 17, "error", "Can't access   cart\nstorage"),
                       log(a + 6 * S, 9, "INFO", "ok " + "y" * 300)],
              "frontend-proxy": [log(a + 7 * S, 0, "", "GET /api/cart 503")]},
        metrics={"cart": {"container.memory.usage.total": [point(a - 120 * S, 2**20), point(a - 60 * S, 3 * 2**20)],
                          "container.cpu.usage.total": [point(a - 130 * S, 0), point(a - 120 * S, 2 * S)]}})
    return st, st.case


def run(st, case, name, args=None, max_tokens=BIG):
    return at.run_tool(st, case, name, args, count, max_tokens)


def test_list_services(tmp_path):
    st, case = _store(tmp_path)
    r = run(st, case, "list_services")
    assert r.text.splitlines() == ["3 services", "cart: spans=yes logs=yes metrics=yes",
                                   "frontend: spans=yes logs=no metrics=no",
                                   "frontend-proxy: spans=no logs=yes metrics=no"]
    assert (r.lines_shown, r.lines_total, r.truncated, r.error) == (3, 3, False, False)


def test_metric_series(tmp_path):
    st, case = _store(tmp_path)
    r = run(st, case, "metric_series", {"service": "cart", "metric": "mem_mb", "from_min": -3, "to_min": 0})
    assert r.text.splitlines() == ["mem_mb of cart (MB), 60 s buckets, bucket start time:",
                                   "T-03:00 -", "T-02:00 1.0", "T-01:00 3.0"]
    r = run(st, case, "metric_series", {"service": "cart", "metric": "cpu_pct", "from_min": -2, "to_min": -1,
                                        "step_s": 30})
    assert r.text.splitlines()[1:] == ["T-02:00 20.0", "T-01:30 -"]
    r = run(st, case, "metric_series", {"service": "cart", "metric": "requests", "from_min": -20, "to_min": 20})
    assert "(clipped to the incident window)" in r.text.splitlines()[0]


@pytest.mark.parametrize("args,msg", [
    ({"service": "cart", "metric": "mem_mb", "from_min": 0, "to_min": 0}, "from_min must be smaller than to_min"),
    ({"service": "cart", "metric": "memory", "from_min": -1, "to_min": 0}, 'unknown metric "memory"'),
    ({"service": "nope", "metric": "mem_mb", "from_min": -1, "to_min": 0}, 'unknown service "nope"; call list_services'),
    ({"service": "cart", "metric": "mem_mb", "from_min": 14, "step_s": 600}, "no full bucket of step_s seconds"),
    ({"service": "cart", "metric": "mem_mb", "to_min": -15.5}, "no full bucket of step_s seconds"),
    ({"metric": "mem_mb", "from_min": 14}, "no full bucket of step_s seconds"),
    ({"metric": "mem_mb", "step_s": 700}, "step_s must be between"),
    ({"service": "cart", "metric": "mem_mb", "from_min": "-1", "to_min": 0}, "from_min must be a number"),
    ({"service": "cart", "metric": "mem_mb", "from_min": -1, "to_min": 0, "step_s": 5}, "step_s must be between"),
    ({"service": "cart", "metric": "mem_mb", "from_min": -1, "to_min": 0, "step_s": 30.5}, "step_s must be a whole"),
    ({"service": "jaeger", "metric": "mem_mb", "from_min": -1, "to_min": 0}, 'unknown service "jaeger"'),
])
def test_metric_series_errors(tmp_path, args, msg):
    st, case = _store(tmp_path)
    r = run(st, case, "metric_series", args)
    assert r.error and r.text.startswith("error: ") and msg in r.text and "\n" not in r.text


def _starts(text):
    return [line.split()[0] for line in text.splitlines()[1:]]


def test_metric_series_default_range_aligned_full_buckets(tmp_path):
    """Pencere T-15:00 … T+15:00. 420 sn adımda: başlangıç alarma hizalı ilk sınır (T-14:00), bitiş son tam kova;
    T+00:00 bir sınır; her kova tam adım; değerler query.metric_series'in aynı aralıktaki çıktısı."""
    st, case = _store(tmp_path)
    a = case.alarm_ns
    r = run(st, case, "metric_series", {"service": "cart", "metric": "requests", "step_s": 420})
    assert not r.error and _starts(r.text) == ["T-14:00", "T-07:00", "T+00:00", "T+07:00"]
    assert "clipped" not in r.text
    q = query.metric_series(st, "cart", "requests", a - 840 * S, a + 840 * S, step_s=420)
    assert [line.split()[1] for line in r.text.splitlines()[1:]] == [str(v) for _, v in q["points"]]
    # from_min verildi: ızgara oradan; to_min yok: son tam kova (T-13:30 + 4 × 7 dk = T+14:30)
    r = run(st, case, "metric_series", {"service": "cart", "metric": "requests", "step_s": 420, "from_min": -13.5})
    assert _starts(r.text) == ["T-13:30", "T-06:30", "T+00:30", "T+07:30"]
    # from_min pencereden önce: kırpılır, ızgara pencere başından, son kova yine tam (T-15:00 + 4 × 7 dk)
    r = run(st, case, "metric_series", {"service": "cart", "metric": "requests", "step_s": 420, "from_min": -20})
    assert _starts(r.text) == ["T-15:00", "T-08:00", "T-01:00", "T+06:00"] and "clipped" in r.text
    # to_min verildi: o uç aynen (yarım son kova olabilir), başlangıç hizalı
    r = run(st, case, "metric_series", {"service": "cart", "metric": "requests", "step_s": 420, "to_min": 1})
    assert _starts(r.text) == ["T-14:00", "T-07:00", "T+00:00"]
    # varsayılan 60 sn: hizalı pencerede bütün pencere
    r = run(st, case, "metric_series", {"service": "cart", "metric": "mem_mb"})
    assert _starts(r.text)[0] == "T-15:00" and _starts(r.text)[-1] == "T+14:00" and len(_starts(r.text)) == 30


def test_metric_series_explicit_range_unchanged(tmp_path):
    """Aralığı verilmiş tek servisli çağrı eski koddaki metni verir (P2b'deki beklenen metinler)."""
    st, case = _store(tmp_path)
    r = run(st, case, "metric_series", {"service": "cart", "metric": "mem_mb", "from_min": -3, "to_min": 0})
    assert r.text == "mem_mb of cart (MB), 60 s buckets, bucket start time:\nT-03:00 -\nT-02:00 1.0\nT-01:00 3.0"


def test_other_tools_default_range_is_window(tmp_path):
    st, case = _store(tmp_path)
    for name in ("search_spans", "search_logs", "service_dependencies"):
        full = run(st, case, name, {"from_min": -15, "to_min": 15}).text
        assert run(st, case, name, {}).text == full, name
        assert run(st, case, name, {"from_min": -15}).text == full, name
        assert run(st, case, name, {"to_min": 15}).text == full, name
    assert run(st, case, "search_logs", {"from_min": 0}).text.splitlines()[0] == "3 log records"
    # pencere uçlarına yakın kayıtlar: varsayılan aralık bunları da kapsamalı (ör. -10 / 0 gibi bir varsayılan değil)
    a = T0 + 15 * 60 * S
    (tmp_path / "edge").mkdir()
    edge = make_store(tmp_path / "edge", spans={"cart": [span("e1", "s1", "Early", T0 + S, 5),
                                                          span("e2", "s2", "Late", T0 + 30 * 60 * S - S, 5)]},
                      logs={"cart": [log(T0 + S, 17, "error", "early"), log(T0 + 30 * 60 * S - S, 17, "error", "late")]})
    assert run(edge, edge.case, "search_spans", {}).text.splitlines()[0] == "2 spans"
    assert run(edge, edge.case, "search_logs", {}).text.splitlines()[0] == "2 log records"
    assert run(edge, edge.case, "search_logs", {"to_min": 0}).text.splitlines()[1:] == ["T-14:59.000 cart ERROR early"]
    assert run(edge, edge.case, "search_logs", {"from_min": 0}).text.splitlines()[1:] == ["T+14:59.000 cart ERROR late"]
    assert a == edge.case.alarm_ns
    r = run(st, case, "search_spans", {"from_min": 20})
    assert r.error and "from_min must be smaller than to_min" in r.text


def test_metric_series_all_services(tmp_path):
    st, case = _store(tmp_path)
    a = case.alarm_ns
    r = run(st, case, "metric_series", {"metric": "requests"})
    lines = r.text.splitlines()
    assert lines[0] == ("requests of 2 services (incoming requests per bucket), 300 s buckets starting at T-15:00, "
                        "6 values per row:")
    for line, svc in zip(lines[1:], ("cart", "frontend")):
        q = query.metric_series(st, svc, "requests", a - 900 * S, a + 900 * S, step_s=300)
        assert line == f"{svc}: " + " ".join(str(v) for _, v in q["points"])
    assert len(lines) == 3
    # konteyner metriği: yalnız metriği olan servisler (frontend'in metriği yok, adı da geçmez)
    r = run(st, case, "metric_series", {"metric": "mem_mb", "from_min": -3, "to_min": 0, "step_s": 60})
    assert r.text.splitlines() == ["mem_mb of 1 services (MB), 60 s buckets starting at T-03:00, 3 values per row:",
                                   "cart: - 1.0 3.0"]
    # aralıkta gelen span'i olmayan servis: satırı yok, adı başlıkta
    r = run(st, case, "metric_series", {"metric": "errors", "from_min": 0, "to_min": 1, "step_s": 30})
    assert r.text.splitlines() == ["errors of 1 services (incoming requests with error status per bucket), 30 s "
                                   "buckets starting at T+00:00, 2 values per row; no data for: frontend:",
                                   "cart: 0 1"]
    # bu sinyali taşıyan servis hiç yok
    r = run(st, case, "metric_series", {"metric": "cpu_pct", "from_min": 5, "to_min": 6, "step_s": 30})
    assert r.text.splitlines() == ["cpu_pct of 0 services (percent of one CPU core), 30 s buckets starting at "
                                   "T+05:00, 2 values per row; no data for: cart:"]


def test_metric_series_all_services_token_cap(tmp_path):
    st, case = _store(tmp_path)
    full = run(st, case, "metric_series", {"metric": "requests", "step_s": 10})
    marker = "[showing the first 1 of 2 services; use a larger step_s, a shorter range or one service]"
    cap = count("\n".join([*full.text.splitlines()[:2], marker]))  # tam olarak başlık + 1 satır + işaret
    r = run(st, case, "metric_series", {"metric": "requests", "step_s": 10}, max_tokens=cap)
    assert count(r.text) <= cap and r.truncated and r.lines_shown == 1 and r.lines_total == 2
    assert r.text.splitlines()[1] == full.text.splitlines()[1]
    assert r.text.splitlines()[-1] == marker


def test_unknown_tool_and_unused_fields(tmp_path):
    st, case = _store(tmp_path)
    r = run(st, case, "run_shell", {})
    assert r.error and r.text.startswith('error: unknown tool "run_shell"')
    flat = {k: None for k in at.ARG_FIELDS} | {"from_min": -2, "to_min": 0, "trace_id": "ignored", "metric": "x"}
    r = run(st, case, "service_dependencies", flat)
    assert not r.error and r.text.splitlines()[1:] == ["frontend -> cart calls=1 errors=1"]


def test_search_spans(tmp_path):
    st, case = _store(tmp_path)
    r = run(st, case, "search_spans", {"from_min": -2, "to_min": 1})
    lines = r.text.splitlines()
    assert lines[0] == "5 spans"
    assert lines[1] == "T-01:01.000 frontend GET / kind=server status=unset code=200 dur=40.0ms trace=t1"
    assert lines[2] == "T-01:00.999 frontend grpc.Cart/GetCart kind=client status=unset dur=30.0ms peer=cart trace=t1"
    assert lines[3].startswith("T-01:00.999 cart GetCart kind=server status=error code=14 dur=25.0ms trace=t1 "
                               "error: connection refused: ")
    assert lines[3].endswith("x...") and len(lines[3].split(" error: ")[1]) == at.ERROR_CHARS + 3
    assert "code=None" not in r.text and "peer=None" not in r.text
    r = run(st, case, "search_spans", {"from_min": -2, "to_min": 1, "service": "cart", "status": "error"})
    assert r.text.splitlines()[0] == "2 spans" and len(r.text.splitlines()) == 3
    r = run(st, case, "search_spans", {"from_min": -2, "to_min": 1, "status": "failed"})
    assert r.error and "status must be error, ok or unset" in r.text


def test_token_cap_and_single_marker(tmp_path):
    st, case = _store(tmp_path)
    full = run(st, case, "search_spans", {"from_min": -2, "to_min": 1})
    for cap in (40, 60, 80, 120):
        r = run(st, case, "search_spans", {"from_min": -2, "to_min": 1}, max_tokens=cap)
        assert count(r.text) <= cap
        lines = r.text.splitlines()
        assert lines[1:1 + r.lines_shown] == full.text.splitlines()[1:1 + r.lines_shown]  # tam satırlar
        assert r.truncated and lines[-1] == f"[showing the first {r.lines_shown} of 5 by start time; narrow the query]"
        assert sum("[showing" in x for x in lines) == 1 and "more lines" not in r.text
    assert not full.truncated and "[showing" not in full.text


def test_get_trace_indent(tmp_path):
    st, case = _store(tmp_path)
    r = run(st, case, "get_trace", {"trace_id": "t1"})
    lines = r.text.splitlines()
    assert lines[0] == "trace t1: 3 spans"
    assert lines[1].startswith("T-01:01.000 frontend GET /")
    assert lines[2].startswith("T-01:00.999   frontend grpc.Cart/GetCart")
    assert lines[3].startswith("T-01:00.999     cart GetCart")
    assert "trace=" not in r.text
    r = run(st, case, "get_trace", {"trace_id": "zz"})
    assert r.error and 'no trace "zz"' in r.text


def test_search_logs(tmp_path):
    st, case = _store(tmp_path)
    r = run(st, case, "search_logs", {"from_min": 0, "to_min": 1})
    lines = r.text.splitlines()
    assert lines[0] == "3 log records"
    assert lines[1] == "T+00:05.120 cart ERROR Can't access cart storage"
    assert lines[2].startswith("T+00:06.000 cart INFO ok yyy") and lines[2].endswith("y...")
    assert lines[3] == "T+00:07.000 frontend-proxy UNSET GET /api/cart 503"
    r = run(st, case, "search_logs", {"from_min": 0, "to_min": 1, "min_level": "warn"})
    assert r.text.splitlines() == ["1 log records", "T+00:05.120 cart ERROR Can't access cart storage"]
    r = run(st, case, "search_logs", {"from_min": 0, "to_min": 1, "text": "API/CART"})
    assert r.text.splitlines()[1:] == ["T+00:07.000 frontend-proxy UNSET GET /api/cart 503"]
    r = run(st, case, "search_logs", {"from_min": 0, "to_min": 1, "min_level": "critical"})
    assert r.error and "min_level must be info, warn or error" in r.text


def test_service_dependencies(tmp_path):
    st, case = _store(tmp_path)
    r = run(st, case, "service_dependencies", {"from_min": -2, "to_min": 1})
    assert r.text.splitlines() == ["1 caller -> callee pairs", "frontend -> cart calls=1 errors=1"]


def test_file_and_live_same_text(tmp_path, backends):  # noqa: F811
    fs, ls, _ = stores(tmp_path, backends, enum_strings=True, jaeger_quirks=True)
    case = fs.case
    calls = [("list_services", {}),
             ("metric_series", {"service": "cart", "metric": "cpu_pct", "from_min": -15, "to_min": 15}),
             ("metric_series", {"service": "cart", "metric": "errors", "from_min": -15, "to_min": 15, "step_s": 30}),
             ("metric_series", {"service": "cart", "metric": "cpu_pct", "step_s": 420}),
             ("metric_series", {"metric": "cpu_pct"}),
             ("metric_series", {"metric": "errors", "step_s": 120}),
             ("search_spans", {}),
             ("search_spans", {"from_min": -15, "to_min": 15}),
             ("search_spans", {"from_min": -15, "to_min": 15, "status": "error"}),
             ("get_trace", {"trace_id": "t2"}),
             ("search_logs", {"from_min": -15, "to_min": 15}),
             ("search_logs", {"from_min": -15, "to_min": 15, "min_level": "error", "text": "cart"}),
             ("service_dependencies", {"from_min": -15, "to_min": 15})]
    for name, args in calls:
        for cap in (BIG, 30):
            assert at.run_tool(fs, case, name, args, count, cap) == at.run_tool(ls, case, name, args, count, cap), name


def test_tool_outputs_leakage_scan(tmp_path):
    st, case = _store(tmp_path)
    out = tmp_path / "tool_outputs"
    out.mkdir()
    with (out / "outputs.jsonl").open("w") as f:
        for name, args in (("list_services", {}), ("search_spans", {"from_min": -2, "to_min": 1}),
                           ("search_logs", {"from_min": 0, "to_min": 1})):
            f.write(json.dumps({"tool": name, "text": run(st, case, name, args).text}) + "\n")
    assert scan_model_view(out) == []
    with (out / "outputs.jsonl").open("a") as f:  # kasıtlı: flag adı araç çıktısında
        f.write(json.dumps({"tool": "search_spans", "text": "T+00:01.000 ad flagd.evaluation adFailure"}) + "\n")
    assert scan_model_view(out)


def test_token_cap_with_non_additive_counter(tmp_path):
    """Gerçek tokenizer'da birleşik metin parçaların toplamından farklı sayılabilir: satır satır tahmin sınırı aşsa da
    tam metin doğrulaması sınırın altına indirir."""
    st, case = _store(tmp_path)
    newline_heavy = lambda t: max(1, len(t) // 4) + 5 * t.count("\n")  # noqa: E731
    for cap in (60, 90, 140):
        r = at.run_tool(st, case, "search_spans", {"from_min": -2, "to_min": 1}, newline_heavy, cap)
        assert newline_heavy(r.text) <= cap and r.truncated


def test_token_cap_fills_when_estimate_is_pessimistic(tmp_path):
    """Birleşik metin parçaların toplamından ucuz sayılırsa (çağrı başına sabit ek), satır satır tahmin eksik kalır;
    artırma adımı sığan kadar tam satırı gösterir: bir satır daha sınırı aşar."""
    st, case = _store(tmp_path)
    overhead = lambda t: max(1, len(t) // 4) + 6  # noqa: E731
    full = at.run_tool(st, case, "search_spans", {"from_min": -2, "to_min": 1}, overhead, BIG).text.splitlines()
    for cap in (60, 90, 120):
        r = at.run_tool(st, case, "search_spans", {"from_min": -2, "to_min": 1}, overhead, cap)
        assert overhead(r.text) <= cap and r.truncated
        more = "\n".join([full[0], *full[1:2 + r.lines_shown],
                           f"[showing the first {r.lines_shown + 1} of 5 by start time; narrow the query]"])
        assert overhead(more) > cap
