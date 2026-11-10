"""Canlı okuyucu (`LiveStore`, P2a 3. madde): yeniden oynatma yığınındaki Jaeger v3, OpenSearch ve Prometheus'tan
ham kayıt (DECISIONS 2026-11-09 "Canlı taraf: vaka başına boş hedef ve aynı tanım").

Ham veri çekilir; hesap `query.py`'nin ortak kodunda. Okuyucuya inen süzgeçler (servis, zaman, metrik ve konteyner
adı) üst küme döndürebilir; `query.py` hepsini yeniden uygular. Toplama yalnız ad kümelerinde (`names`): küme,
sorgu yönteminden bağımsız aynı sonucu verir.

- Span: Jaeger v3 `traces` araması servis × dilim (`SLICE_NS`); arama derinliğine (`SEARCH_DEPTH` iz) takılan dilim
  ikiye bölünür, 1 sn'lik dilimde de takılırsa hata. Arama izin bütün span'lerini döndürür; dilimler örtüştüğü için
  (iz, span) kimliğiyle tekrarlar ayıklanır. Servis verilmezse `/services`'teki her servis aranır.
- Tek iz: `traces/{id}`; 404 → boş.
- Log: OpenSearch `otel-logs-*`, `@timestamp` (ms) aralığı + isteğe bağlı servis terimi; `track_total_hits` ile
  toplam `PAGE_SIZE`'ı aşarsa aralık ikiye bölünür, 1 ms'lik dilimde de aşarsa hata. `_source`'tan OTLP biçimli
  kayıt kurulur, `query.log_from_otlp` ile ham kayda çevrilir (dosyayla aynı kod). Alanlar iç içe ya da noktalı ad
  olarak okunabilir.
- Metrik: Prometheus `ad{container_name="x"}[<N>ms]`, zaman = aralık sonu − 1 ms → (sonu − 1 − N, sonu − 1] =
  [başı, sonu) ms; seri başına etiketler (`container_name`, `interface`) ve ham örnekler.
- Ad kümeleri: Jaeger `/services`; OpenSearch `resource.service.name.keyword` toplaması; Prometheus `container_name`
  etiket değerleri.

`http` ve `rfc3339` `tools/storage_check.py`'den buraya taşındı (davranış aynı; `storage_check` buradan alır).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from aiops_rca.cases import Case
from aiops_rca.query import METRIC_NAMES, MS, LogRecord, MetricPoint, Span, log_from_otlp, read_window, span_from_otlp
from aiops_rca.signals import MESSAGE_KEYS

# Yeniden oynatma yığınının uçları (deploy/replay/compose.yaml)
REPLAY_ENDS = {"jaeger": "http://127.0.0.1:16686/jaeger/ui/api/v3", "opensearch": "http://127.0.0.1:19200",
               "prometheus": "http://127.0.0.1:19090"}
SLICE_NS = 60 * 10**9
SEARCH_DEPTH = 1000
PAGE_SIZE = 10_000  # OpenSearch'ün varsayılan `max_result_window`'u
LOG_SOURCE = ["@timestamp", "body", "severity", "resource.service.name", "traceId",
              *[f"attributes.{k}" for k in MESSAGE_KEYS]]
_PROM_NAMES = {prom: name for name, (_, prom) in METRIC_NAMES.items()}


def http(method: str, url: str, body=None, timeout: int = 20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def rfc3339(ns: int) -> str:
    return datetime.fromtimestamp(ns // 10**9, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + f".{ns % 10**9:09d}Z"


def parse_time_ns(value) -> int:
    """OpenSearch `@timestamp`: ISO dizgi (en çok 9 kesir basamağı) ya da epoch ms sayısı → ns."""
    if isinstance(value, (int, float)):
        return int(value) * MS
    m = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)", value)
    if not m:
        raise ValueError(f"unexpected timestamp {value!r}")
    tz = "+00:00" if m.group(3) == "Z" else m.group(3)
    base = int(datetime.fromisoformat(m.group(1) + tz).timestamp())
    return base * 10**9 + int((m.group(2) or "0").ljust(9, "0"))


def _lookup(src, dotted: str):
    """İç içe ya da noktalı ad olarak saklanmış alan (ör. `resource.service.name`, `{"resource": {"service.name"}}`)."""
    if not isinstance(src, dict):
        return None
    if dotted in src:
        return src[dotted]
    parts = dotted.split(".")
    for i in range(1, len(parts)):
        head = ".".join(parts[:i])
        if isinstance(src.get(head), dict):
            found = _lookup(src[head], ".".join(parts[i:]))
            if found is not None:
                return found
    return None


def _resource_service(resource: dict) -> str | None:
    for a in resource.get("attributes", []):
        if a.get("key") == "service.name":
            return next(iter(a.get("value", {}).values()), None)
    return None


def jaeger_raw_slice(base: str, service: str, lo: int, hi: int,
                     depth: int = SEARCH_DEPTH) -> list[tuple[str | None, dict]]:
    """Bir servis ve zaman dilimindeki izlerin span'leri `[(servis ya da None, OTLP span)]`; derinliğe takılan dilim
    ikiye bölünür (tekrarlar olabilir)."""
    q = urllib.parse.urlencode({"query.service_name": service, "query.start_time_min": rfc3339(lo),
                                "query.start_time_max": rfc3339(hi), "query.search_depth": depth,
                                "query.raw_traces": "true"})
    try:
        d = http("GET", f"{base}/traces?{q}", timeout=300)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise
    out, traces = [], set()
    for rs in (d.get("result") or {}).get("resourceSpans", []):
        svc = _resource_service(rs.get("resource", {}))
        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                traces.add(sp.get("traceId"))
                out.append((svc, sp))
    if len(traces) >= depth:
        if hi - lo <= 10**9:
            raise RuntimeError(f"jaeger search depth hit in a 1 s slice ({service} {rfc3339(lo)})")
        mid = (lo + hi) // 2
        return jaeger_raw_slice(base, service, lo, mid, depth) + jaeger_raw_slice(base, service, mid, hi, depth)
    return out


class LiveStore:
    def __init__(self, case: Case, ends: dict | None = None, *, slice_ns: int = SLICE_NS,
                 search_depth: int = SEARCH_DEPTH, page_size: int = PAGE_SIZE, workers: int = 4):
        self.case = case
        self.ends = dict(ends or REPLAY_ENDS)
        self.slice_ns, self.search_depth, self.page_size, self.workers = slice_ns, search_depth, page_size, workers
        self.queries = {"jaeger": 0, "opensearch": 0, "prometheus": 0}
        self._refreshed = False
        self._window: tuple[int, int] | None = None

    # --- okuyucu arayüzü (query.Store) ---
    def window(self) -> tuple[int, int]:
        if self._window is None:
            self._window = read_window(self.case.view)
        return self._window

    def names(self) -> dict[str, set[str]]:
        self.queries["jaeger"] += 1
        spans = set(http("GET", f"{self.ends['jaeger']}/services", timeout=60).get("services") or [])
        self._refresh()
        body = {"size": 0, "aggs": {"svc": {"terms": {"field": "resource.service.name.keyword", "size": 1000}}}}
        self.queries["opensearch"] += 1
        d = http("POST", self.ends["opensearch"] + "/otel-logs-*/_search", body, timeout=120)
        logs = {b["key"] for b in d["aggregations"]["svc"]["buckets"]}
        self.queries["prometheus"] += 1
        d = http("GET", self.ends["prometheus"] + "/api/v1/label/container_name/values", timeout=60)
        return {"spans": spans, "logs": logs, "metrics": set(d.get("data") or [])}

    def spans(self, lo: int, hi: int, service: str | None = None) -> list[Span]:
        if hi <= lo:
            return []
        if service is not None:
            services = [service]
        else:
            self.queries["jaeger"] += 1
            services = http("GET", f"{self.ends['jaeger']}/services", timeout=60).get("services") or []
        tasks = [(svc, a, min(a + self.slice_ns, hi)) for svc in services for a in range(lo, hi, self.slice_ns)]
        seen, out = set(), []
        with ThreadPoolExecutor(self.workers) as pool:
            parts = pool.map(lambda t: jaeger_raw_slice(self.ends["jaeger"], *t, depth=self.search_depth), tasks)
            for part in parts:
                self.queries["jaeger"] += 1
                for svc, sp in part:
                    key = (sp.get("traceId"), sp.get("spanId"))
                    if svc is not None and key not in seen:
                        seen.add(key)
                        out.append(span_from_otlp(svc, sp))
        return out

    def trace(self, trace_id: str) -> list[Span]:
        self.queries["jaeger"] += 1
        q = urllib.parse.urlencode({"raw_traces": "true"})
        try:
            d = http("GET", f"{self.ends['jaeger']}/traces/{urllib.parse.quote(trace_id)}?{q}", timeout=120)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            raise
        seen, out = set(), []
        for rs in (d.get("result") or {}).get("resourceSpans", []):
            svc = _resource_service(rs.get("resource", {}))
            if svc is None:
                continue
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    key = (sp.get("traceId"), sp.get("spanId"))
                    if key not in seen:
                        seen.add(key)
                        out.append(span_from_otlp(svc, sp))
        return out

    def _refresh(self) -> None:
        if not self._refreshed:
            self.queries["opensearch"] += 1
            http("POST", self.ends["opensearch"] + "/_refresh", timeout=120)
            self._refreshed = True

    def _log_slice(self, a_ms: int, b_ms: int, service: str | None) -> list[dict]:
        filters = [{"range": {"@timestamp": {"gte": a_ms, "lt": b_ms, "format": "epoch_millis"}}}]
        if service is not None:
            filters.append({"term": {"resource.service.name.keyword": service}})
        body = {"size": self.page_size, "track_total_hits": True, "_source": LOG_SOURCE,
                "query": {"bool": {"filter": filters}}}
        self.queries["opensearch"] += 1
        d = http("POST", self.ends["opensearch"] + "/otel-logs-*/_search", body, timeout=300)
        total = d["hits"]["total"]["value"]
        if total > self.page_size or d["hits"]["total"].get("relation", "eq") != "eq":
            if b_ms - a_ms <= 1:
                raise RuntimeError(f"opensearch: > {self.page_size} logs in a 1 ms slice ({a_ms})")
            mid = (a_ms + b_ms) // 2
            return self._log_slice(a_ms, mid, service) + self._log_slice(mid, b_ms, service)
        hits = [h["_source"] for h in d["hits"]["hits"]]
        if len(hits) != total:
            raise RuntimeError(f"opensearch returned {len(hits)} of {total} hits ({a_ms}–{b_ms})")
        return hits

    def logs(self, lo: int, hi: int, service: str | None = None) -> list[LogRecord]:
        a_ms, b_ms = -(-lo // MS), -(-hi // MS)  # kayıt zamanı ms'ye indirilmiş: t·ms ∈ [lo, hi) ⇔ t ∈ [⌈lo⌉, ⌈hi⌉)
        if b_ms <= a_ms:
            return []
        self._refresh()
        out = []
        for src in self._log_slice(a_ms, b_ms, service):
            t = parse_time_ns(src["@timestamp"])
            body = _lookup(src, "body")
            rec = {"timeUnixNano": str(t), "severityNumber": _lookup(src, "severity.number") or 0,
                   "severityText": _lookup(src, "severity.text") or "",
                   "body": {"stringValue": body} if isinstance(body, str) else ({} if body is None else
                                                                                {"kvlistValue": body}),
                   "attributes": [{"key": k, "value": {"stringValue": str(v)}}
                                  for k in MESSAGE_KEYS if (v := _lookup(src, f"attributes.{k}")) is not None],
                   "traceId": _lookup(src, "traceId") or ""}
            out.append(log_from_otlp(_lookup(src, "resource.service.name"), rec))
        return out

    def metric_points(self, name: str, lo: int, hi: int, container: str | None = None) -> list[MetricPoint]:
        a_ms, b_ms = -(-lo // MS), -(-hi // MS)
        if b_ms <= a_ms:
            return []
        prom = METRIC_NAMES[name][1]
        sel = prom + (f'{{container_name="{container}"}}' if container is not None else "")
        q = urllib.parse.urlencode({"query": f"{sel}[{b_ms - a_ms}ms]", "time": f"{(b_ms - 1) / 1000:.3f}"})
        self.queries["prometheus"] += 1
        d = http("GET", f"{self.ends['prometheus']}/api/v1/query?{q}", timeout=300)
        out = []
        for series in d["data"]["result"]:
            labels = series.get("metric", {})
            cont = labels.get("container_name")
            if not cont:
                continue
            for ts, v in series.get("values", []):
                out.append(MetricPoint(_PROM_NAMES.get(labels.get("__name__"), name), cont, labels.get("interface"),
                                       round(float(ts) * 1000) * MS, float(v)))
        return out
