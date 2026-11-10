"""P2a sorgu katmanı: altı sorgu fonksiyonu ve ortak hesap (HANDOFF 2026-11-10, P2a 1. madde; DECISIONS 2026-11-09
"Canlı taraf: vaka başına boş hedef ve aynı tanım").

Fonksiyonlar depolamadan bağımsızdır: her biri bir okuyucu (`Store`) alır. Okuyucu yalnız ham kayıt verir (span,
log, metrik noktası, tek iz, ad kümeleri); hesap burada yapılır. Okuyucuya inen süzgeçler (servis, zaman aralığı,
metrik adı, konteyner adı) üst küme döndürebilir; buradaki kod bütün süzgeçleri iki tarafta da yeniden uygular.

Ortak kurallar:
- Zaman: fonksiyonlar mutlak ns aralık `[start, end)` alır; aralık snapshot penceresine (`window.json`) kırpılır,
  çıktıda `clipped`. Metrik ve log zamanı ms'ye indirilir (`ns // 10**6`, sonra tekrar ns); Prometheus ve OpenSearch
  ms tutuyor. Span zamanı ns kalır.
- Dışlama: `TOOLING_CONTAINERS` ve `ROUTINE_SERVICES` (`signals.py`) bütün fonksiyonlarda; bu adlar sorulursa
  `ValueError`.
- Adet sınırı: `limit=None` sınırsız; çıktıda `total` (eşleşen sayı) ve `truncated`.
- Ad eşleme tek tabloda: `METRIC_NAMES` (OTel adı → OTLP türü, Prometheus adı).
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from aiops_rca.signals import (EDGE_NS, INCOMING_KINDS, MESSAGE_CHARS, ROUTINE_SERVICES, STATUS_ERROR,
                               TOOLING_CONTAINERS, log_message, pct)

# OTel metrik adı → (OTLP türü, Prometheus adı). Prometheus adları canlı volume'den doğrulandı (HANDOFF 2026-11-10);
# histogramda karşılaştırılan veri noktasının sayısı (`_count`).
METRIC_NAMES = {
    "container.cpu.usage.total": ("sum", "container_cpu_usage_nanoseconds_total"),
    "container.memory.usage.total": ("sum", "container_memory_usage_total_bytes"),
    "container.network.io.usage.rx_bytes": ("sum", "container_network_io_usage_rx_bytes_total"),
    "container.network.io.usage.tx_bytes": ("sum", "container_network_io_usage_tx_bytes_total"),
    "container.memory.percent": ("gauge", "container_memory_percent_ratio"),
    "traces.span.metrics.duration": ("histogram", "traces_span_metrics_duration_milliseconds_count"),
}

EXCLUDED = TOOLING_CONTAINERS | ROUTINE_SERVICES
MS = 10**6

# Konteyner metriklerinden seriler: anahtar → (OTel adı, hesap, ölçek). "rate": birikimli sayaçtan ardışık iki
# noktanın hızı (Δdeğer / Δzaman ns) × ölçek; "mean": kovadaki noktaların ortalaması / bölen.
CONTAINER_SERIES = {
    "cpu_pct": ("container.cpu.usage.total", "rate", 100),
    "mem_mb": ("container.memory.usage.total", "mean", 2**20),
    "net_rx_bytes_per_s": ("container.network.io.usage.rx_bytes", "rate", 10**9),
    "net_tx_bytes_per_s": ("container.network.io.usage.tx_bytes", "rate", 10**9),
}
# Servisin gelen (SERVER / CONSUMER) span'lerinden seriler (`signals` tanımları).
SPAN_SERIES = ("requests", "errors", "error_rate", "p95_ms", "p99_ms")
SERIES = tuple(CONTAINER_SERIES) + SPAN_SERIES

# Span özetinde durum kodu: sırayla ilk bulunan anahtar. Karşı taraf: `server.address`.
STATUS_CODE_KEYS = ("http.response.status_code", "http.status_code", "rpc.grpc.status_code",
                    "rpc.response.status_code", "grpc.status_code")
PEER_KEY = "server.address"
SPAN_STATUS = {"unset": 0, "ok": 1, "error": STATUS_ERROR}
_KIND_NAMES = {"SPAN_KIND_UNSPECIFIED": 0, "SPAN_KIND_INTERNAL": 1, "SPAN_KIND_SERVER": 2, "SPAN_KIND_CLIENT": 3,
               "SPAN_KIND_PRODUCER": 4, "SPAN_KIND_CONSUMER": 5}
_STATUS_NAMES = {"STATUS_CODE_UNSET": 0, "STATUS_CODE_OK": 1, "STATUS_CODE_ERROR": 2}


# --- Ham kayıtlar (depolamadan bağımsız) ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    service: str
    name: str
    kind: int
    start_ns: int
    end_ns: int
    status: int  # 0 unset, 1 ok, 2 error
    status_code: int | str | None
    peer: str | None
    error_text: str | None


@dataclass(frozen=True, slots=True)
class LogRecord:
    time_ns: int  # ms'ye indirilmiş
    service: str | None
    severity_number: int
    severity_text: str
    message: str  # tam mesaj (`signals.log_message`)
    trace_id: str | None


@dataclass(frozen=True, slots=True)
class MetricPoint:
    name: str  # OTel adı
    container: str
    interface: str | None
    time_ns: int  # ms'ye indirilmiş
    value: float


class Store(Protocol):
    """Okuyucu: bir vakanın ham kayıtları. Süzgeçler üst küme döndürebilir (ortak kod yeniden uygular)."""

    def window(self) -> tuple[int, int]:
        """Snapshot penceresi `[start, end)`, ns (`window.json`)."""

    def names(self) -> dict[str, set[str]]:
        """Bütün snapshot'ta ad kümeleri: {"spans": servisler, "logs": servisler, "metrics": konteynerler}."""

    def spans(self, lo: int, hi: int, service: str | None = None) -> Iterable[Span]:
        """Başlangıcı `[lo, hi)` aralığında olan span'ler (üst küme olabilir)."""

    def trace(self, trace_id: str) -> Iterable[Span]:
        """Bir izin bütün span'leri (üst küme olabilir)."""

    def logs(self, lo: int, hi: int, service: str | None = None) -> Iterable[LogRecord]:
        """Zamanı `[lo, hi)` aralığında olan loglar (üst küme olabilir)."""

    def metric_points(self, name: str, lo: int, hi: int, container: str | None = None) -> Iterable[MetricPoint]:
        """OTel adı `name` olan, zamanı `[lo, hi)` aralığında noktalar (üst küme olabilir)."""


# --- OTLP JSON'dan ham kayda (dosya ve Jaeger ikisi de OTLP JSON veriyor) -------------------------------------------

def otlp_value(value: dict):
    """OTLP JSON öznitelik değeri → Python değeri (`intValue` JSON'da dizgi)."""
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return bool(value["boolValue"])
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value else None


def _enum(value, names: dict[str, int]) -> int:
    if isinstance(value, str):
        return names.get(value, int(value) if value.isdigit() else 0)
    return int(value or 0)


def span_from_otlp(service: str, sp: dict) -> Span:
    attrs = {a["key"]: a.get("value", {}) for a in sp.get("attributes", [])}
    status_code = next((otlp_value(attrs[k]) for k in STATUS_CODE_KEYS if k in attrs), None)
    peer = otlp_value(attrs[PEER_KEY]) if PEER_KEY in attrs else None
    status = sp.get("status") or {}
    error_text = status.get("message") or None
    if error_text is None:
        for ev in sp.get("events", []):
            msg = next((a.get("value", {}) for a in ev.get("attributes", []) if a.get("key") == "exception.message"),
                       None)
            if msg is not None:
                error_text = otlp_value(msg)
                break
    start = int(sp.get("startTimeUnixNano", 0))
    return Span(trace_id=sp.get("traceId", ""), span_id=sp.get("spanId", ""),
                parent_span_id=sp.get("parentSpanId") or None, service=service, name=sp.get("name", ""),
                kind=_enum(sp.get("kind"), _KIND_NAMES), start_ns=start,
                end_ns=int(sp.get("endTimeUnixNano", start) or start), status=_enum(status.get("code"), _STATUS_NAMES),
                status_code=status_code, peer=peer, error_text=error_text)


def to_ms_ns(t: int) -> int:
    """ns zamanı ms'ye indirir (Prometheus ve OpenSearch'in hassasiyeti), yine ns olarak."""
    return t // MS * MS


def log_from_otlp(service: str | None, rec: dict) -> LogRecord:
    t = int(rec.get("timeUnixNano") or 0) or int(rec.get("observedTimeUnixNano") or 0)
    return LogRecord(time_ns=to_ms_ns(t), service=service, severity_number=int(rec.get("severityNumber") or 0),
                     severity_text=rec.get("severityText", "") or "", message=log_message(rec),
                     trace_id=rec.get("traceId") or None)


def read_window(view: Path) -> tuple[int, int]:
    w = json.loads((view / "window.json").read_text(encoding="utf-8"))
    return tuple(int(datetime.fromisoformat(w[k].replace("Z", "+00:00")).timestamp()) * 10**9
                 for k in ("start", "end"))


# --- Ortak yardımcılar ---------------------------------------------------------------------------------------------

def _clip(store: Store, start: int, end: int) -> tuple[int, int, bool]:
    lo, hi = store.window()
    a, b = max(start, lo), min(end, hi)
    clipped = a != start or b != end
    return a, max(a, b), clipped


def _check_service(service: str | None) -> None:
    if service is not None and service in EXCLUDED:
        raise ValueError(f"service {service!r} is excluded (tooling / routine)")


def _limited(items: list, limit: int | None) -> dict:
    total = len(items)
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0 or None")
    shown = items if limit is None else items[:limit]
    return {"total": total, "truncated": limit is not None and total > limit, "items": shown}


def span_summary(s: Span) -> dict:
    return {"trace_id": s.trace_id, "span_id": s.span_id, "parent_span_id": s.parent_span_id, "service": s.service,
            "operation": s.name, "kind": s.kind, "start_ns": s.start_ns,
            "duration_ms": (s.end_ns - s.start_ns) / MS, "status": s.status, "status_code": s.status_code,
            "peer": s.peer, "error_text": s.error_text}


def _span_key(s: Span) -> tuple:
    return (s.start_ns, s.trace_id, s.span_id)


# --- Sorgu fonksiyonları -------------------------------------------------------------------------------------------

def list_services(store: Store) -> dict:
    """Servisler (izlerdeki servisler ∪ metriklerdeki konteynerler ∪ log servisleri; dışlamalar hariç) ve her birinde
    hangi sinyal var. Bütün snapshot. (25 pilot vakada yalnız logda görülen servis yok; HANDOFF 2026-11-10.)"""
    n = store.names()
    spans, logs, metrics = (set(n.get(k, ())) - EXCLUDED for k in ("spans", "logs", "metrics"))
    logs.discard(None)
    services = sorted(spans | metrics | logs)
    return {"services": [{"service": s, "spans": s in spans, "logs": s in logs, "metrics": s in metrics}
                         for s in services]}


def _buckets(lo: int, hi: int, step_ns: int) -> list[int]:
    return list(range(lo, hi, step_ns))


def _bucket_index(t: int, lo: int, step_ns: int) -> int:
    return (t - lo) // step_ns


def metric_series(store: Store, service: str, metric: str, start: int, end: int, step_s: int = 60) -> dict:
    """Servis × metrik × aralık kovalı seri: `[[kova başı ns, değer]]`.

    Kovalar `[lo + k·step, lo + (k+1)·step)`, `lo` kırpılmış başlangıç; son kova `hi`'de biter; boş kova atlanmaz.
    - `mem_mb`: kovadaki noktaların ortalaması / 2^20.
    - `cpu_pct`, `net_*`: seri (konteyner + arayüz) zamana göre; ardışık iki nokta için hız = Δdeğer / Δzaman,
      aralık ikinci noktanın kovasına; sayaç geriye düşerse çift atlanır; ilk kova için `lo − 60 sn`'den noktalar.
      Kova değeri hızların ortalaması × ölçek; ağda arayüzlerin kova değerleri toplanır.
    - `requests`, `errors`: başlangıcı kovada olan gelen span sayısı / hata span'i sayısı (boş kovada 0);
      `error_rate` = errors / requests (istek 0 ise `None`); `p95_ms`, `p99_ms` `signals.pct` (span yoksa `None`).
    """
    if metric not in SERIES:
        raise ValueError(f"unknown metric {metric!r}; one of {SERIES}")
    if service is None:
        raise ValueError("service is required")
    _check_service(service)
    if int(step_s) != step_s or step_s < 1:
        raise ValueError("step_s must be a positive integer")
    lo, hi, clipped = _clip(store, start, end)
    step_ns = int(step_s) * 10**9
    starts = _buckets(lo, hi, step_ns)
    if metric in CONTAINER_SERIES:
        values = _container_series(store, service, metric, lo, hi, step_ns, len(starts))
    else:
        values = _span_series(store, service, metric, lo, hi, step_ns, len(starts))
    return {"service": service, "metric": metric, "start_ns": lo, "end_ns": hi, "step_s": int(step_s),
            "clipped": clipped, "points": [[b, v] for b, v in zip(starts, values)]}


def _container_series(store: Store, service: str, metric: str, lo: int, hi: int, step_ns: int, n: int) -> list:
    name, how, scale = CONTAINER_SERIES[metric]
    fetch_lo = lo - EDGE_NS if how == "rate" else lo
    series = defaultdict(set)  # arayüz → {(zaman, değer)}
    for p in store.metric_points(name, fetch_lo, hi, service):
        t = to_ms_ns(p.time_ns)
        if p.name == name and p.container == service and fetch_lo <= t < hi:
            series[p.interface].add((t, float(p.value)))
    per_iface = []
    for iface in sorted(series, key=lambda x: (x is not None, x or "")):
        acc = [[] for _ in range(n)]
        points = sorted(series[iface])
        if how == "mean":
            for t, v in points:
                if lo <= t < hi:
                    acc[_bucket_index(t, lo, step_ns)].append(v)
            per_iface.append([sum(a) / len(a) / scale if a else None for a in acc])
        else:
            for (t1, v1), (t2, v2) in zip(points, points[1:]):
                if not lo <= t2 < hi or v2 < v1 or t2 == t1:
                    continue
                acc[_bucket_index(t2, lo, step_ns)].append((v2 - v1) / (t2 - t1) * scale)
            per_iface.append([sum(a) / len(a) if a else None for a in acc])
    out = []
    for k in range(n):
        vals = [col[k] for col in per_iface if col[k] is not None]
        out.append(sum(vals) if vals else None)
    return out


def _span_series(store: Store, service: str, metric: str, lo: int, hi: int, step_ns: int, n: int) -> list:
    counts, errors, durations = [0] * n, [0] * n, [[] for _ in range(n)]
    for s in store.spans(lo, hi, service):
        if s.service != service or s.kind not in INCOMING_KINDS or not lo <= s.start_ns < hi:
            continue
        k = _bucket_index(s.start_ns, lo, step_ns)
        counts[k] += 1
        if s.status == STATUS_ERROR:
            errors[k] += 1
        durations[k].append(s.end_ns - s.start_ns)
    if metric == "requests":
        return counts
    if metric == "errors":
        return errors
    if metric == "error_rate":
        return [e / c if c else None for e, c in zip(errors, counts)]
    q = 0.95 if metric == "p95_ms" else 0.99
    return [pct(d, q) for d in durations]


def search_spans(store: Store, start: int, end: int, service: str | None = None, operation: str | None = None,
                 status: str | None = None, min_duration_ms: float | None = None, limit: int | None = 20) -> dict:
    """Süzgeçli span arama; sıra başlangıç artan, eşitlikte `trace_id`, `span_id`."""
    _check_service(service)
    if status is not None and status not in SPAN_STATUS:
        raise ValueError(f"status must be one of {tuple(SPAN_STATUS)} or None")
    lo, hi, clipped = _clip(store, start, end)
    want = SPAN_STATUS.get(status) if status is not None else None
    min_ns = None if min_duration_ms is None else min_duration_ms * MS
    found = []
    for s in store.spans(lo, hi, service):
        if not lo <= s.start_ns < hi or s.service in EXCLUDED:
            continue
        if service is not None and s.service != service:
            continue
        if operation is not None and s.name != operation:
            continue
        if want is not None and s.status != want:
            continue
        if min_ns is not None and s.end_ns - s.start_ns < min_ns:
            continue
        found.append(s)
    found.sort(key=_span_key)
    res = _limited(found, limit)
    return {"start_ns": lo, "end_ns": hi, "clipped": clipped, "total": res["total"], "truncated": res["truncated"],
            "spans": [span_summary(s) for s in res["items"]]}


def get_trace(store: Store, trace_id: str, limit: int | None = 200) -> dict:
    """Bir izin snapshot'taki bütün span'leri (pencereye kırpılmaz); sıra `search_spans` ile aynı."""
    found = sorted((s for s in store.trace(trace_id) if s.trace_id == trace_id and s.service not in EXCLUDED),
                   key=_span_key)
    res = _limited(found, limit)
    return {"trace_id": trace_id, "total": res["total"], "truncated": res["truncated"],
            "spans": [span_summary(s) for s in res["items"]]}


def search_logs(store: Store, start: int, end: int, service: str | None = None, min_severity: int | None = None,
                text: str | None = None, limit: int | None = 20) -> dict:
    """Süzgeçli log arama. `min_severity` önem numarasına göre (numarası 0 olan kayıt yalnız `min_severity` yokken);
    `text` tam mesajda büyük-küçük harf duyarsız alt dize. Sıra zaman artan, eşitlikte servis, mesaj, `trace_id`."""
    _check_service(service)
    if min_severity is not None and not 1 <= min_severity <= 24:
        raise ValueError("min_severity must be 1..24 or None")
    lo, hi, clipped = _clip(store, start, end)
    needle = text.casefold() if text is not None else None
    found = []
    for r in store.logs(lo, hi, service):
        t = to_ms_ns(r.time_ns)
        if not lo <= t < hi or r.service in EXCLUDED:
            continue
        if service is not None and r.service != service:
            continue
        if min_severity is not None and r.severity_number < min_severity:
            continue
        if needle is not None and needle not in r.message.casefold():
            continue
        found.append((t, r))
    found.sort(key=lambda x: (x[0], x[1].service or "", x[1].message, x[1].trace_id or ""))
    res = _limited(found, limit)
    return {"start_ns": lo, "end_ns": hi, "clipped": clipped, "total": res["total"], "truncated": res["truncated"],
            "logs": [{"time_ms": t // MS, "service": r.service, "severity_number": r.severity_number,
                      "severity_text": r.severity_text, "message": r.message[:MESSAGE_CHARS],
                      "truncated_message": len(r.message) > MESSAGE_CHARS, "trace_id": r.trace_id}
                     for t, r in res["items"]]}


def service_dependencies(store: Store, start: int, end: int) -> dict:
    """Çağıran → çağrılan kenarları. Küme: başlangıcı aralıkta olan span'ler; kenar: alt span'in üst span'i bu
    kümede ve başka serviste (`call_graph.service_edges` tanımı). Sayı = alt span sayısı; hata = alt span ERROR."""
    lo, hi, clipped = _clip(store, start, end)
    span_svc, children = {}, []
    for s in store.spans(lo, hi, None):
        if not lo <= s.start_ns < hi:
            continue
        span_svc[s.span_id] = s.service
        if s.parent_span_id:
            children.append((s.parent_span_id, s.service, s.status == STATUS_ERROR))
    calls, errs = defaultdict(int), defaultdict(int)
    for parent, svc, is_err in children:
        p = span_svc.get(parent)
        if p is None or p == svc or p in EXCLUDED or svc in EXCLUDED:
            continue
        calls[(p, svc)] += 1
        errs[(p, svc)] += is_err
    return {"start_ns": lo, "end_ns": hi, "clipped": clipped,
            "edges": [{"caller": a, "callee": b, "calls": calls[(a, b)], "errors": errs[(a, b)]}
                      for a, b in sorted(calls)]}
