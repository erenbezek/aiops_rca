"""P2a 3. madde: canlı okuyucu (`store_live.py`) ve `storage_check.py` uyarlaması, sahte arka uçlarla (CI'da ağ yok).

`FakeBackends`: tek bir `127.0.0.1` sunucusunda Jaeger v3 (`/jaeger/api/v3`), OpenSearch (`/os`) ve Prometheus
(`/prom`) taklidi. Yalnız bizim kodun gönderdiği istekleri anlar:
- Jaeger: `/services`; `/traces?query.service_name&start_time_min&start_time_max&search_depth&raw_traces` → o
  serviste başlangıcı aralıkta span'i olan izlerin bütün span'leri, en çok `search_depth` iz, yoksa 404;
  `/traces/{id}` → izin span'leri ya da 404. `enum_strings` ile tür ve durum kodu `SPAN_KIND_*` / `STATUS_CODE_*`.
- OpenSearch: `_refresh`; `_search` toplamalı (servis başına sayım) ya da ham (range + isteğe bağlı servis terimi,
  `size`, `track_total_hits`); `@timestamp` ms ile süzülür, `_source`'ta ns'li dizgi.
- Prometheus: `/api/v1/query?query=<ad>[{container_name="x"}][<N>ms]&time=<sn>` → (time − N, time] aralığındaki
  ham örnekler; `/api/v1/label/container_name/values`.

1. `storage_check.compare_interval` çıktısı, değişiklikten önceki koddan kaydedilmiş değerle aynı (`STORAGE_CHECK_EXPECTED`;
   zamana bağlı alanlar hariç).
2. `LiveStore`: ham kayıtlar `FileStore`'unkilerle aynı (aynı veri iki tarafta); Jaeger dilim bölme ve tekrar ayıklama,
   enum dizgileri, OpenSearch dilim bölme, Prometheus aralık uçları, ad kümeleri, `get_trace` 404.
"""
import json
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from aiops_rca.query import METRIC_NAMES

REPO = Path(__file__).resolve().parents[1]
S = 10**9
MS = 10**6
T0 = 1_767_225_600 * S  # 2026-01-01T00:00:00Z


# --- veri ---------------------------------------------------------------------------------------------------------

def _res(key, name):
    return {"attributes": [{"key": key, "value": {"stringValue": name}}]}


def _span(trace, sid, name, start, dur_ms, kind=2, parent="", status=0, attrs=None, message=None, events=None):
    st = {"code": status} if status else {}
    if message:
        st["message"] = message
    return {"traceId": trace, "spanId": sid, "parentSpanId": parent, "name": name, "kind": kind,
            "startTimeUnixNano": str(start), "endTimeUnixNano": str(start + int(dur_ms * MS)), "status": st,
            "attributes": [{"key": k, "value": {"intValue": str(v)} if isinstance(v, int) else {"stringValue": v}}
                           for k, v in (attrs or {}).items()], "events": events or []}


def dataset():
    """(izler {servis: [span]}, loglar {servis: [kayıt]}, metrikler {konteyner: {ad: (tür, [nokta])}})."""
    t = T0 + 60 * S
    traces = {
        "frontend": [_span("t1", "f1", "GET /", t + 123, 40), _span("t2", "f2", "GET /cart", t + 5 * S + 7, 25),
                     _span("t3", "f3", "GET /", t + 70 * S, 15)],
        "cart": [_span("t1", "c1", "GetCart", t + 1000, 12, parent="f1", attrs={"rpc.grpc.status_code": 0}),
                 _span("t2", "c2", "GetCart", t + 5 * S + 900, 20, parent="f2", status=2, message="unavailable",
                       attrs={"rpc.grpc.status_code": 14}),
                 _span("t3", "c3", "AddItem", t + 70 * S + 50, 5, parent="f3")],
        "valkey-cart": [_span("t1", "v1", "HGET", t + 2000, 1, kind=3, parent="c1")],
    }
    logs = {
        "cart": [{"timeUnixNano": str(t + 1_500_000), "severityNumber": 9, "severityText": "Information",
                  "body": {"stringValue": "GetCart called"}, "traceId": "t1"},
                 {"timeUnixNano": str(t + 5 * S + 2_345_678), "severityNumber": 17, "severityText": "Error",
                  "body": {"stringValue": "Can't access cart storage: " + "x" * 300}, "traceId": "t2"}],
        "frontend-proxy": [{"timeUnixNano": "0", "observedTimeUnixNano": str(t + 3 * S + 999_999),
                            "severityNumber": 0, "severityText": "",
                            "body": {"stringValue": "[2026-01-01] GET /api/cart 503"}}],
    }
    def pts(base, step, values, iface=None):
        out = []
        for i, v in enumerate(values):
            dp = {"timeUnixNano": str(base + i * step), "asInt": str(v)}
            if iface:
                dp["attributes"] = [{"key": "interface", "value": {"stringValue": iface}}]
            out.append(dp)
        return out
    metrics = {
        "cart": {"container.cpu.usage.total": ("sum", pts(t - 10 * S + 321, 10 * S, [0, 2 * S, 3 * S, 3 * S + 5])),
                 "container.memory.usage.total": ("sum", pts(t + 77, 10 * S, [2**20, 3 * 2**20, 2**21])),
                 "container.network.io.usage.rx_bytes": ("sum", pts(t - 5 * S, 10 * S, [0, 500, 900], "eth0")),
                 "container.memory.percent": ("gauge", [{"timeUnixNano": str(t + 11), "asDouble": 0.25}])},
        "jaeger": {"container.memory.usage.total": ("sum", pts(t, 10 * S, [5 * 2**20]))},
    }
    return traces, logs, metrics


def _line(doc) -> str:
    return json.dumps(doc, separators=(",", ":")) + "\n"  # collector'ın dosyası gibi boşluksuz


def write_view(root: Path, traces, logs, metrics, minutes=30) -> Path:
    view = root / "inc-live"
    view.mkdir()
    iso = lambda ns: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ns // S))  # noqa: E731
    (view / "window.json").write_text(json.dumps({"start": iso(T0), "end": iso(T0 + minutes * 60 * S)}))
    with (view / "traces.jsonl").open("w") as f:
        for svc, sps in traces.items():
            f.write(_line({"resourceSpans": [{"resource": _res("service.name", svc) if svc else {"attributes": []},
                                              "scopeSpans": [{"spans": sps}]}]}))
    with (view / "logs.jsonl").open("w") as f:
        for svc, recs in logs.items():
            f.write(_line({"resourceLogs": [{"resource": _res("service.name", svc),
                                             "scopeLogs": [{"logRecords": recs}]}]}))
    with (view / "metrics.jsonl").open("w") as f:
        for container, by_name in metrics.items():
            ms = []
            for name, (kind, dps) in by_name.items():
                ms.append({"name": name, kind: {"dataPoints": dps}})
            f.write(_line({"resourceMetrics": [{"resource": _res("container.name", container),
                                                "scopeMetrics": [{"metrics": ms}]}]}))
    return view


# --- sahte arka uçlar ---------------------------------------------------------------------------------------------

def _iso_ns(ns: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ns // S)) + f".{ns % S:09d}Z"


def _parse_rfc3339(s: str) -> int:
    m = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", s)
    base = int(datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    return base * S + int((m.group(2) or "0").ljust(9, "0"))


class FakeBackends:
    KINDS = {0: "SPAN_KIND_UNSPECIFIED", 1: "SPAN_KIND_INTERNAL", 2: "SPAN_KIND_SERVER", 3: "SPAN_KIND_CLIENT",
             4: "SPAN_KIND_PRODUCER", 5: "SPAN_KIND_CONSUMER"}
    STATUS = {0: "STATUS_CODE_UNSET", 1: "STATUS_CODE_OK", 2: "STATUS_CODE_ERROR"}

    def __init__(self, traces, logs, metrics, *, enum_strings=False, drop_prom=None, nested_resource=False,
                 jaeger_quirks=False):
        self.spans = [(svc, sp) for svc, sps in traces.items() for sp in sps]
        self.enum_strings = enum_strings
        self.jaeger_quirks = jaeger_quirks  # gerçek Jaeger'deki iki dönüşüm (DECISIONS 2026-11-11)
        self.requests: list[str] = []
        self.docs = []
        for svc, recs in logs.items():
            for r in recs:
                t = int(r.get("timeUnixNano") or 0) or int(r.get("observedTimeUnixNano") or 0)
                res = {"service": {"name": svc}} if nested_resource else {"service.name": svc}
                src = {"@timestamp": _iso_ns(t), "observedTimestamp": _iso_ns(t), "body": r["body"]["stringValue"],
                       "severity": {"number": r.get("severityNumber", 0), "text": r.get("severityText", "")},
                       "resource": res, "traceId": r.get("traceId", "")}
                self.docs.append((t // MS, svc, src))
        self.series = []
        for container, by_name in metrics.items():
            for name, (kind, dps) in by_name.items():
                prom = METRIC_NAMES[name][1]
                by_labels = {}
                for dp in dps:
                    labels = {"__name__": prom, "container_name": container, "host_name": "h"}
                    for a in dp.get("attributes", []):
                        labels[a["key"]] = a["value"]["stringValue"]
                    v = float(dp.get("asInt", dp.get("asDouble")))
                    by_labels.setdefault(tuple(sorted(labels.items())), []).append((int(dp["timeUnixNano"]) // MS, v))
                for labels, values in by_labels.items():
                    self.series.append((dict(labels), sorted(values)))
        if drop_prom:  # kasıtlı fark: Prometheus'ta bu adın ilk serisinde son örnek yok
            next(v for lab, v in self.series if lab["__name__"] == drop_prom).pop()
        backends = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                backends.requests.append(self.path)
                self._send(*backends.route("GET", self.path, None))

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n)) if n else None
                backends.requests.append(self.path)
                self._send(*backends.route("POST", self.path, body))

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.ends = {"jaeger": self.base + "/jaeger/api/v3", "opensearch": self.base + "/os",
                     "prometheus": self.base + "/prom"}
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    # --- yönlendirme ---
    def route(self, method, path, body):
        u = urllib.parse.urlsplit(path)
        q = dict(urllib.parse.parse_qsl(u.query))
        p = u.path
        if p.startswith("/jaeger/api/v3"):
            return self.jaeger(p[len("/jaeger/api/v3"):], q)
        if p.startswith("/os"):
            return self.opensearch(p[len("/os"):], body)
        if p.startswith("/prom"):
            return self.prometheus(p[len("/prom"):], q)
        return 404, {"error": "no route"}

    def _otlp(self, spans):
        by_svc = {}
        for svc, sp in spans:
            sp = dict(sp)
            if self.jaeger_quirks:
                if sp["endTimeUnixNano"] == sp["startTimeUnixNano"]:
                    sp["endTimeUnixNano"] = str(int(sp["endTimeUnixNano"]) + 1)
                tag = any(a["key"] == "error" and a["value"].get("stringValue") == "true" for a in sp["attributes"])
                if tag and not sp["status"].get("code"):  # belirtilmemiş + etiket → hata, etiket kalır
                    sp["status"] = {**sp["status"], "code": 2}
                elif tag:  # hata + etiket → etiket silinir
                    sp["attributes"] = [a for a in sp["attributes"] if a["key"] != "error"]
            if self.enum_strings:
                sp["kind"] = self.KINDS[sp["kind"]]
                if sp["status"].get("code"):
                    sp["status"] = {**sp["status"], "code": self.STATUS[sp["status"]["code"]]}
            by_svc.setdefault(svc, []).append(sp)
        return {"result": {"resourceSpans": [{"resource": _res("service.name", s) if s else {"attributes": []},
                                              "scopeSpans": [{"spans": v}]} for s, v in by_svc.items()]}}

    def jaeger(self, p, q):
        if p == "/services":
            return 200, {"services": sorted({svc for svc, _ in self.spans if svc})}
        if p == "/traces":
            svc, lo = q["query.service_name"], _parse_rfc3339(q["query.start_time_min"])
            hi, depth = _parse_rfc3339(q["query.start_time_max"]), int(q["query.search_depth"])
            hits = sorted({sp["traceId"] for s, sp in self.spans
                           if s == svc and lo <= int(sp["startTimeUnixNano"]) <= hi})[:depth]
            if not hits:
                return 404, {"error": {"httpCode": 404, "message": "trace not found"}}
            return 200, self._otlp([(s, sp) for s, sp in self.spans if sp["traceId"] in hits])
        if p.startswith("/traces/"):
            tid = p[len("/traces/"):]
            spans = [(s, sp) for s, sp in self.spans if sp["traceId"] == tid]
            return (200, self._otlp(spans)) if spans else (404, {"error": {"httpCode": 404}})
        return 404, {}

    def _matches(self, body):
        f = body["query"]
        filters = f["bool"]["filter"] if "bool" in f else [f]
        out = []
        for t_ms, svc, src in self.docs:
            ok = True
            for c in filters:
                if "range" in c:
                    r = c["range"]["@timestamp"]
                    ok &= r["gte"] <= t_ms < r["lt"]
                if "term" in c:
                    ok &= c["term"]["resource.service.name.keyword"] == svc
            if ok:
                out.append((t_ms, svc, src))
        return out

    def opensearch(self, p, body):
        if p == "/_refresh":
            return 200, {}
        if p == "/otel-logs-*/_search":
            if "query" not in body:
                body = {**body, "query": {"bool": {"filter": []}}}
            m = self._matches(body)
            if "aggs" in body:
                agg = body["aggs"]["svc"]["terms"]
                counts = {}
                for _, svc, _ in m:
                    counts[svc] = counts.get(svc, 0) + 1
                buckets = [{"key": k, "doc_count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
                return 200, {"hits": {"total": {"value": len(m)}, "hits": []},
                             "aggregations": {"svc": {"buckets": buckets[:agg["size"]]}}}
            size = body.get("size", 10)
            return 200, {"hits": {"total": {"value": len(m), "relation": "eq"},
                                  "hits": [{"_source": src} for _, _, src in m[:size]]}}
        return 404, {}

    def prometheus(self, p, q):
        if p == "/api/v1/label/container_name/values":
            return 200, {"status": "success", "data": sorted({s["container_name"] for s, _ in self.series})}
        if p == "/api/v1/query":
            m = re.fullmatch(r'(\w+)(?:\{container_name="([^"]*)"\})?\[(\d+)ms\]', q["query"])
            name, container, rng = m.group(1), m.group(2), int(m.group(3))
            t_ms = round(float(q["time"]) * 1000)
            result = []
            for labels, values in self.series:
                if labels["__name__"] != name or (container is not None and labels["container_name"] != container):
                    continue
                vals = [[ts / 1000, repr(v)] for ts, v in values if t_ms - rng < ts <= t_ms]
                if vals:
                    result.append({"metric": labels, "values": vals})
            return 200, {"status": "success", "data": {"resultType": "matrix", "result": result}}
        return 404, {}


@pytest.fixture
def backends():
    made = []

    def make(*a, **kw):
        b = FakeBackends(*a, **kw)
        made.append(b)
        return b
    yield make
    for b in made:
        b.close()


# --- 1. storage_check çıktısı değişmedi --------------------------------------------------------------------------

def storage_check_dataset():
    """`dataset()` + servis adı olmayan resource'ta bir span (izi cart'ta) + aralık sonundan 1 ns önce başlayan span."""
    traces, logs, metrics = dataset()
    traces = {**traces, "": [_span("t2", "u1", "anon", T0 + 65 * S, 1, parent="c2")]}
    traces["cart"] = traces["cart"] + [_span("t9", "c9", "Edge", T0 + 20 * 60 * S - 1, 1)]
    return traces, logs, metrics


def storage_check_result(tmp_path, make, module=None):
    if module is None:
        sys.path.insert(0, str(REPO / "tools"))
        import storage_check as module  # noqa: E402
    storage_check = module
    traces, logs, metrics = storage_check_dataset()
    view = write_view(tmp_path, traces, logs, metrics)
    b = make(traces, logs, metrics, drop_prom="container_network_io_usage_rx_bytes_total")
    rec, oldest = storage_check.compare_interval(T0 + 30 * S, T0 + 20 * 60 * S, view, b.ends)
    for k in ("queried_utc", "seconds"):
        rec.pop(k)
    return json.loads(json.dumps({"rec": rec, "oldest": oldest}))


# Değişiklikten önceki `storage_check.py` (main b4878eb'deki hali) ile `storage_check_dataset()` verisinde kaydedildi
# (HANDOFF 2026-11-10).
STORAGE_CHECK_EXPECTED = json.loads(
    '{"oldest": {"logs": 1767225660001500000, "metrics": 1767225650000000321, "traces": 1767225660000000123}, "rec": {"equal": false, "file_oldest_utc": {"logs": "2026-01-01T00:01:00Z", "metrics": "2026-01-01T00:00:50Z", "traces": "2026-01-01T00:01:00Z"}, "interval_utc": ["2026-01-01T00:00:30Z", "2026-01-01T00:20:00Z"], "logs": {"differences": {}, "equal": true, "file": 3, "live": 3}, "metrics": {"container.memory.percent": {"differences": {}, "equal": true, "file": 1, "kind": "gauge", "live": 1, "prometheus": "container_memory_percent_ratio"}, "container.network.io.usage.rx_bytes": {"differences": {"(1767225675000, 900.0)": {"file": 1, "live": 0}}, "equal": false, "file": 3, "kind": "sum", "live": 2, "prometheus": "container_network_io_usage_rx_bytes_total"}, "traces.span.metrics.duration": {"differences": {}, "equal": false, "file": 0, "kind": "histogram", "live": 0, "prometheus": "traces_span_metrics_duration_milliseconds_count"}}, "traces": {"differences": {}, "equal": true, "file": 9, "jaeger_queries": 60, "live": 9}}}')


def test_storage_check_compare_unchanged(tmp_path, backends):
    assert storage_check_result(tmp_path, backends) == STORAGE_CHECK_EXPECTED


# --- 2. LiveStore ------------------------------------------------------------------------------------------------

from aiops_rca import query  # noqa: E402
from aiops_rca.cases import Case  # noqa: E402
from aiops_rca.store_file import FileStore  # noqa: E402
from aiops_rca.store_live import LiveStore, _lookup, parse_time_ns  # noqa: E402


def stores(tmp_path, make, data=None, **kw):
    traces, logs, metrics = data or dataset()
    view = write_view(tmp_path, traces, logs, metrics)
    case = Case("inc-live", view, T0 + 15 * 60 * S)
    b = make(traces, logs, metrics, **{k: v for k, v in kw.items()
                                       if k in ("enum_strings", "nested_resource", "jaeger_quirks", "drop_prom")})
    live_kw = {k: v for k, v in kw.items() if k in ("search_depth", "page_size", "slice_ns")}
    return FileStore(case), LiveStore(case, b.ends, **live_kw), b


def by_key(records):
    return sorted(records, key=repr)


@pytest.mark.parametrize("variant", [{}, {"enum_strings": True, "nested_resource": True}], ids=["plain", "variant"])
def test_live_raw_records_equal_file(tmp_path, backends, variant):
    fs, ls, _ = stores(tmp_path, backends, **variant)
    lo, hi = fs.window()
    assert ls.window() == (lo, hi)
    assert ls.names() == fs.names()
    assert by_key(ls.spans(lo, hi)) == by_key(fs.spans(lo, hi))
    assert len(ls.spans(lo, hi)) == 7  # tekrar yok
    assert by_key(s for s in ls.spans(lo, hi, "cart") if s.service == "cart") == by_key(fs.spans(lo, hi, "cart"))
    assert by_key(ls.trace("t1")) == by_key(fs.trace("t1")) and len(fs.trace("t1")) == 3
    assert ls.trace("nope") == []
    assert by_key(ls.logs(lo, hi)) == by_key(fs.logs(lo, hi)) and len(fs.logs(lo, hi)) == 3
    assert by_key(ls.logs(lo, hi, "cart")) == by_key(fs.logs(lo, hi, "cart"))
    for name in {n for n, _, _ in query.CONTAINER_SERIES.values()}:
        assert by_key(ls.metric_points(name, lo - 60 * S, hi)) == by_key(fs.metric_points(name, lo - 60 * S, hi))
        assert by_key(ls.metric_points(name, lo - 60 * S, hi, "cart")) == \
            by_key(fs.metric_points(name, lo - 60 * S, hi, "cart"))


def test_live_query_results_equal_file(tmp_path, backends):
    fs, ls, _ = stores(tmp_path, backends, enum_strings=True)
    lo, hi = fs.window()
    calls = [lambda st: query.list_services(st),
             lambda st: query.search_spans(st, lo, hi, limit=None),
             lambda st: query.search_spans(st, lo, hi, service="cart", status="error", limit=None),
             lambda st: query.get_trace(st, "t2"),
             lambda st: query.search_logs(st, lo, hi, limit=None),
             lambda st: query.search_logs(st, lo, hi, min_severity=9, text="cart", limit=None),
             lambda st: query.service_dependencies(st, lo, hi)]
    calls += [(lambda m: lambda st: query.metric_series(st, "cart", m, lo, lo + 5 * 60 * S, step_s=30))(m)
              for m in query.SERIES]
    for call in calls:
        assert call(ls) == call(fs)


def test_jaeger_depth_split_and_dedup(tmp_path, backends):
    t = T0 + 60 * S
    traces = {"cart": [_span(f"t{i}", f"s{i}", "op", t + i * 7 * S, 1) for i in range(6)]}
    fs, ls, b = stores(tmp_path, backends, (traces, {}, {}), search_depth=2, slice_ns=60 * S)
    lo, hi = fs.window()
    got = ls.spans(lo, hi)
    assert by_key(got) == by_key(fs.spans(lo, hi)) and len(got) == 6
    assert sum("/traces?" in r for r in b.requests) > 30  # 30 dilim + bölünenler
    # aynı saniyede derinliği aşan iki iz → hata
    traces = {"cart": [_span("ta", "a", "op", t, 1), _span("tb", "b", "op", t + 10, 1)]}
    (tmp_path / "x").mkdir()
    _, ls2, _ = stores(tmp_path / "x", backends, (traces, {}, {}), search_depth=1)
    with pytest.raises(RuntimeError, match="search depth"):
        ls2.spans(t, t + S // 2, "cart")


def test_opensearch_split(tmp_path, backends):
    t = T0 + 60 * S
    recs = [{"timeUnixNano": str(t + i * 3 * MS), "severityNumber": 9, "severityText": "INFO",
             "body": {"stringValue": f"m{i}"}} for i in range(5)]
    fs, ls, b = stores(tmp_path, backends, ({}, {"cart": recs}, {}), page_size=2)
    lo, hi = fs.window()
    assert by_key(ls.logs(lo, hi)) == by_key(fs.logs(lo, hi)) and len(fs.logs(lo, hi)) == 5
    assert sum(r.endswith("_search") for r in b.requests) > 3
    same_ms = [{"timeUnixNano": str(t + k), "severityNumber": 9, "body": {"stringValue": "x"}} for k in (1, 2, 3)]
    (tmp_path / "y").mkdir()
    _, ls2, _ = stores(tmp_path / "y", backends, ({}, {"cart": same_ms}, {}), page_size=2)
    with pytest.raises(RuntimeError, match="1 ms slice"):
        ls2.logs(lo, hi)


def test_prometheus_range_bounds(tmp_path, backends):
    t = T0 + 60 * S
    m = {"cart": {"container.memory.usage.total": ("sum", [{"timeUnixNano": str(t + k * S), "asInt": str(k)}
                                                         for k in range(4)])}}
    fs, ls, _ = stores(tmp_path, backends, ({}, {}, m))
    name = "container.memory.usage.total"
    got = ls.metric_points(name, t + S, t + 3 * S)  # [başı, sonu): t+1 sn ve t+2 sn
    assert [(p.time_ns, p.value) for p in sorted(got, key=lambda p: p.time_ns)] == [(t + S, 1.0), (t + 2 * S, 2.0)]
    assert by_key(got) == by_key(fs.metric_points(name, t + S, t + 3 * S))
    assert ls.metric_points(name, t + S, t + S) == []
    # ms altı sınır: başlangıç t + 1 sn + 1 ns → ilk ms'den sonraki noktalar
    assert [p.value for p in ls.metric_points(name, t + S + 1, t + 3 * S)] == [2.0]


def test_parse_time_and_lookup():
    assert parse_time_ns("2026-01-01T00:00:01.123456789Z") == T0 + S + 123_456_789
    assert parse_time_ns("2026-01-01T00:00:01.5Z") == T0 + S + 500 * MS
    assert parse_time_ns("2026-01-01T03:00:01+03:00") == T0 + S
    assert parse_time_ns(1_767_225_601_250) == T0 + S + 250 * MS
    with pytest.raises(ValueError):
        parse_time_ns("yesterday")
    assert _lookup({"resource": {"service.name": "a"}}, "resource.service.name") == "a"
    assert _lookup({"resource": {"service": {"name": "b"}}}, "resource.service.name") == "b"
    assert _lookup({"resource.service.name": "c"}, "resource.service.name") == "c"
    assert _lookup({"severity": {"number": 9}}, "severity.number") == 9
    assert _lookup({"severity": {"number": 9}}, "severity.text") is None


def test_range_end_not_rounded_down(tmp_path, backends):
    """Kayıt zamanı ms'ye iner: aralık sonu ms ortasındaysa o ms'deki kayıt aralıktadır (log ve metrik)."""
    t = T0 + 60 * S
    logs = {"cart": [{"timeUnixNano": str(t), "severityNumber": 9, "body": {"stringValue": "x"}}]}
    m = {"cart": {"container.memory.usage.total": ("sum", [{"timeUnixNano": str(t), "asInt": "1"}])}}
    fs, ls, _ = stores(tmp_path, backends, ({}, logs, m))
    assert len(ls.logs(t - S, t + 1)) == 1 == len(fs.logs(t - S, t + 1))
    assert len(ls.metric_points("container.memory.usage.total", t - S, t + 1)) == 1
    assert len(fs.metric_points("container.memory.usage.total", t - S, t + 1)) == 1


def test_sample_rejects_ok():
    sys.path.insert(0, str(REPO / "tools"))
    import storage_check  # noqa: E402
    ok = {'prometheus_tsdb_out_of_bound_samples_total{type="float"}': 0.0,
          'prometheus_tsdb_out_of_order_samples_total{type="float"}': 0.0,
          'prometheus_tsdb_out_of_order_samples_total{type="histogram"}': 0.0,
          'prometheus_tsdb_too_old_samples_total{type="float"}': 0.0,
          "prometheus_tsdb_exemplar_out_of_order_exemplars_total": 5.0,  # şart değil (DECISIONS 2026-11-10)
          'prometheus_tsdb_out_of_order_wbl_fsync_duration_seconds{quantile="0.5"}': float("nan"),
          'prometheus_tsdb_head_out_of_order_samples_appended_total{type="float"}': 13290.0}
    assert storage_check.sample_rejects_ok(ok)
    assert not storage_check.sample_rejects_ok({**ok, 'prometheus_tsdb_out_of_order_samples_total{type="histogram"}': 1.0})
    assert not storage_check.sample_rejects_ok({**ok, 'prometheus_tsdb_too_old_samples_total{type="float"}': 2.0})
    missing = {k: v for k, v in ok.items() if "too_old" not in k}
    assert not storage_check.sample_rejects_ok(missing)  # sayaç yoksa geçmez


def test_undo_jaeger_error_tag(tmp_path, backends):
    """Gerçek Jaeger'in iki davranışı taklit edilir; canlı okuyucu dosyayla aynı durumu verir (DECISIONS 2026-11-12)."""
    t = T0 + 60 * S
    traces = {"frontend-proxy": [
        _span("ta", "a1", "router frontend egress", t, 3, kind=3, attrs={"error": "true", "http.status_code": "0"}),
        _span("tb", "b1", "GET", t + S, 4, status=2, attrs={"error": "true", "http.status_code": 503}),
        _span("tc", "c1", "GET", t + 2 * S, 5, status=2, attrs={"http.status_code": 500}),
        _span("td", "d1", "GET", t + 3 * S, 6, attrs={"error": "false"})]}
    fs, ls, _ = stores(tmp_path, backends, (traces, {}, {}), jaeger_quirks=True)
    lo, hi = fs.window()
    assert by_key(ls.spans(lo, hi)) == by_key(fs.spans(lo, hi))
    assert [s.status for s in sorted(ls.spans(lo, hi), key=lambda s: s.start_ns)] == [0, 2, 2, 0]
    assert by_key(ls.trace("ta")) == by_key(fs.trace("ta")) and ls.trace("ta")[0].status == 0
    assert by_key(ls.trace("tb")) == by_key(fs.trace("tb")) and ls.trace("tb")[0].status == 2
    from aiops_rca.store_live import undo_jaeger_error_tag
    sp = {"status": {"code": "STATUS_CODE_ERROR", "message": "m"},
          "attributes": [{"key": "error", "value": {"stringValue": "true"}}]}
    assert undo_jaeger_error_tag(sp)["status"] == {"message": "m"}
    assert undo_jaeger_error_tag({"status": {}, "attributes": sp["attributes"]})["status"] == {}
