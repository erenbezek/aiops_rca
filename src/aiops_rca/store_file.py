"""Dosya okuyucusu (`FileStore`, P2a 2. madde): bir vakanın `model_view` snapshot'ından ham kayıt.

Her sinyal ilk istendiğinde bir kez okunur ve bellekte tutulur (bir vakada çok sayıda çağrı yapılır). Okuma
`signals.iter_lines` ve `signals.resource_attr` ile; OTLP JSON → ham kayıt dönüşümü `query.py`'de (canlı taraf da
aynısını kullanır). Süzgeçler burada da uygulanır ama sonuç `query.py`'de yeniden süzülür.

- Span: `service.name`'i olmayan resource atlanır (`call_graph.service_edges` gibi).
- Log: `service.name` yoksa servis `None`.
- Metrik: yalnız `query.CONTAINER_SERIES`'teki OTel adları noktalara alınır (konteyner adı ve `interface`);
  ad kümesi için bütün metriklerdeki `container.name` okunur (`call_graph.metric_containers` gibi, araçlar dahil;
  dışlama `query.py`'de).
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from aiops_rca.cases import Case
from aiops_rca.query import (CONTAINER_SERIES, LogRecord, MetricPoint, Span, log_from_otlp, read_window,
                             span_from_otlp, to_ms_ns)
from aiops_rca.signals import iter_lines, point_value, resource_attr

_POINT_NAMES = frozenset(name for name, _, _ in CONTAINER_SERIES.values())


class FileStore:
    def __init__(self, case: Case):
        self.case = case
        self.view: Path = case.view
        self._window: tuple[int, int] | None = None
        self._spans: list[Span] | None = None
        self._by_trace: dict[str, list[Span]] | None = None
        self._logs: list[LogRecord] | None = None
        self._points: dict[str, list[MetricPoint]] | None = None
        self._containers: set[str] | None = None

    # --- yükleme (bir kez) ---
    def _load_spans(self) -> list[Span]:
        if self._spans is None:
            out = []
            for doc in iter_lines([self.view / "traces.jsonl"]):
                for rs in doc.get("resourceSpans", []):
                    svc = resource_attr(rs.get("resource", {}), "service.name")
                    if svc is None:
                        continue
                    for ss in rs.get("scopeSpans", []):
                        for sp in ss.get("spans", []):
                            out.append(span_from_otlp(svc, sp))
            self._spans = out
        return self._spans

    def _load_logs(self) -> list[LogRecord]:
        if self._logs is None:
            out = []
            for doc in iter_lines([self.view / "logs.jsonl"]):
                for rl in doc.get("resourceLogs", []):
                    svc = resource_attr(rl.get("resource", {}), "service.name")
                    for sl in rl.get("scopeLogs", []):
                        for rec in sl.get("logRecords", []):
                            out.append(log_from_otlp(svc, rec))
            self._logs = out
        return self._logs

    def _load_metrics(self) -> dict[str, list[MetricPoint]]:
        if self._points is None:
            points, containers = defaultdict(list), set()
            for doc in iter_lines([self.view / "metrics.jsonl"]):
                for rm in doc.get("resourceMetrics", []):
                    container = resource_attr(rm.get("resource", {}), "container.name")
                    if container:
                        containers.add(container)
                    for sm in rm.get("scopeMetrics", []):
                        for m in sm.get("metrics", []):
                            name = m.get("name")
                            if name not in _POINT_NAMES or not container:
                                continue
                            for dp in (m.get("gauge") or m.get("sum") or {}).get("dataPoints", []):
                                value = point_value(dp)
                                if value is None:
                                    continue
                                iface = next((a.get("value", {}).get("stringValue") for a in dp.get("attributes", [])
                                              if a.get("key") == "interface"), None)
                                points[name].append(MetricPoint(name, container, iface,
                                                                to_ms_ns(int(dp.get("timeUnixNano", 0))), value))
            self._points, self._containers = dict(points), containers
        return self._points

    # --- okuyucu arayüzü (query.Store) ---
    def window(self) -> tuple[int, int]:
        if self._window is None:
            self._window = read_window(self.view)
        return self._window

    def names(self) -> dict[str, set[str]]:
        self._load_metrics()
        return {"spans": {s.service for s in self._load_spans()},
                "logs": {r.service for r in self._load_logs() if r.service is not None},
                "metrics": set(self._containers)}

    def spans(self, lo: int, hi: int, service: str | None = None) -> list[Span]:
        return [s for s in self._load_spans()
                if lo <= s.start_ns < hi and (service is None or s.service == service)]

    def trace(self, trace_id: str) -> list[Span]:
        if self._by_trace is None:
            idx = defaultdict(list)
            for s in self._load_spans():
                idx[s.trace_id].append(s)
            self._by_trace = dict(idx)
        return list(self._by_trace.get(trace_id, ()))

    def logs(self, lo: int, hi: int, service: str | None = None) -> list[LogRecord]:
        return [r for r in self._load_logs()
                if lo <= r.time_ns < hi and (service is None or r.service == service)]

    def metric_points(self, name: str, lo: int, hi: int, container: str | None = None) -> list[MetricPoint]:
        return [p for p in self._load_metrics().get(name, ())
                if lo <= p.time_ns < hi and (container is None or p.container == container)]
