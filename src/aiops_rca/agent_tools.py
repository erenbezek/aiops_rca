"""P2b ajan araçları (HANDOFF 2026-11-12, P2b 1. madde önerisi ve planlama düzeltmeleri; Eren onaylı).

Altı araç, P2a'nın sorgu fonksiyonlarıyla aynı adla. Hesap `query.py`'de; burada yalnız parametre çevirisi ve
doğrulama, sorgu çağrısı ve metin biçimi. Araçlar vaka bilgisi taşımaz (genel sorgular).

- Zaman: parametrelerde alarma göre dakika (`from_min`, `to_min`; isteğe bağlı, P2c-0 A); çıktıda alarma göre
  `T-mm:ss.mmm` / `T+mm:ss.mmm` (seride `T-mm:ss`). Eksi işareti ASCII. Pencere dışı kısım `query.py`'deki gibi
  kırpılır; başlıkta işaret. Verilmeyen uç: öteki araçlarda pencerenin tam ucu; `metric_series`'te alarma hizalı
  ızgara, yalnız tam kovalar (DECISIONS 2026-11-13 "alarma hizalı, yalnız tam kovalar").
- `metric_series` `service` verilmezse bütün servisler, servis başına bir satır (P2c-0 B): servis başına
  `query.metric_series` çağrısı, varsayılan adım `ALL_SERVICES_STEP_S`.
- Satır sınırı yok; tek sınır token (`max_tokens`): başlık + sığan kadar tam satır + gerekirse tek işaret
  (`[showing the first N of M ...]`). Sayım dışarıdan verilen `count_tokens` ile (koşuda Qwen'in `/tokenize`'ı).
- Boş alan yazılmaz; sayılar yuvarlanır (P2a'daki 1 ns süre farkı 1 ondalık ms'de görünmez).
- Geçersiz parametre ya da sorgunun reddettiği çağrı tek satırlık `error: ...` sonucudur (`ToolResult.error`).
- `args` düz bir nesne (eylem şeması): aracın kullanmadığı alanlar yok sayılır, `None` alan verilmemiş sayılır.

Açıklama metinleri (`TOOLS`) istemle birlikte Eren onayından sonra donar (P2b 3. madde).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from aiops_rca import query
from aiops_rca.cases import Case

MS = 10**6
MIN_NS = 60 * 10**9
FETCH_LIMIT = 500  # sorgudan istenen en çok kayıt; token sınırına hep yeter (en kısa satır ~10 token)
LOG_LEVELS = {"info": 9, "warn": 13, "error": 17}
ARG_FIELDS = ("service", "metric", "operation", "status", "min_duration_ms", "min_level", "text", "trace_id",
              "from_min", "to_min", "step_s")
KIND_TEXT = {0: "unspecified", 1: "internal", 2: "server", 3: "client", 4: "producer", 5: "consumer"}
STATUS_TEXT = {0: "unset", 1: "ok", 2: "error"}
UNITS = {"cpu_pct": "percent of one CPU core", "mem_mb": "MB", "net_rx_bytes_per_s": "bytes/s received",
         "net_tx_bytes_per_s": "bytes/s sent", "requests": "incoming requests per bucket",
         "errors": "incoming requests with error status per bucket", "error_rate": "errors / requests",
         "p95_ms": "95th percentile latency of incoming requests, ms",
         "p99_ms": "99th percentile latency of incoming requests, ms"}
ERROR_CHARS = 120
ALL_SERVICES_STEP_S = 300  # servissiz metric_series'in varsayılan adımı; pilotta 225 çağrıda satır düşmeyen en küçük

# Parametre: (tür, zorunlu mu, açıklama). Tür: "string", "number", "integer".
_RANGE = {"from_min": ("number", False, "start of the time range, minutes relative to the alert "
                                        "(default: start of the telemetry)"),
          "to_min": ("number", False, "end of the time range, minutes relative to the alert "
                                      "(default: end of the telemetry)")}
TOOLS = {
    "list_services": {
        "description": "List the services and containers seen in this incident and which signals (spans, logs, "
                       "metrics) each one has.",
        "params": {}},
    "metric_series": {
        "description": "Time series of one metric, in buckets of step_s seconds: for one service, or for all "
                       "services at once (one row per service) when service is not given. Without from_min, the "
                       "buckets are aligned to the alert (a bucket starts at T+00:00); without to_min, only full "
                       "buckets are shown.",
        "params": {"service": ("string", False, "service or container name; leave out for all services"),
                   "metric": ("string", True, "one of: " + ", ".join(query.SERIES)),
                   **_RANGE,
                   "step_s": ("integer", False, "bucket size in seconds, 10 to 600 (default 60 for one service, "
                                                "300 for all services)")}},
    "search_spans": {
        "description": "Find spans (one operation of one service) in a time range, in start time order.",
        "params": {**_RANGE,
                   "service": ("string", False, "only spans of this service"),
                   "operation": ("string", False, "only spans with this exact operation name"),
                   "status": ("string", False, "only spans with this status: error, ok or unset"),
                   "min_duration_ms": ("number", False, "only spans at least this long, ms")}},
    "get_trace": {
        "description": "All spans of one trace, in start time order, indented under their parent span.",
        "params": {"trace_id": ("string", True, "trace id from a search_spans result")}},
    "search_logs": {
        "description": "Find log records in a time range, in time order.",
        "params": {**_RANGE,
                   "service": ("string", False, "only logs of this service"),
                   "min_level": ("string", False, "only logs at least this level: info, warn or error"),
                   "text": ("string", False, "only logs whose message contains this text (case-insensitive)")}},
    "service_dependencies": {
        "description": "Calls between services in a time range: caller -> callee with call and error counts.",
        "params": dict(_RANGE)},
}


@dataclass(frozen=True)
class ToolResult:
    text: str
    lines_shown: int
    lines_total: int
    truncated: bool
    error: bool


class _Bad(Exception):
    pass


# --- biçim yardımcıları ---------------------------------------------------------------------------------------------

def rel_time(t_ns: int, alarm_ns: int, ms: bool = True) -> str:
    d = t_ns - alarm_ns
    sign = "-" if d < 0 else "+"
    d = abs(d) // MS  # ms'ye aşağı
    m, rest = divmod(d, 60_000)
    s, msec = divmod(rest, 1000)
    return f"T{sign}{m:02d}:{s:02d}.{msec:03d}" if ms else f"T{sign}{m:02d}:{s:02d}"


def _num(v, digits: int | None) -> str:
    if v is None:
        return "-"
    if digits is None:
        return str(int(round(v)))
    return f"{v:.{digits}f}"


SERIES_DIGITS = {"cpu_pct": 1, "mem_mb": 1, "p95_ms": 1, "p99_ms": 1, "net_rx_bytes_per_s": None,
                 "net_tx_bytes_per_s": None, "error_rate": 3, "requests": None, "errors": None}


def _level_text(n: int) -> str:
    if n <= 0:
        return "UNSET"
    for top, name in ((4, "TRACE"), (8, "DEBUG"), (12, "INFO"), (16, "WARN"), (20, "ERROR")):
        if n <= top:
            return name
    return "FATAL"


def _span_line(s: dict, alarm_ns: int, indent: str = "", show_trace: bool = True) -> str:
    parts = [rel_time(s["start_ns"], alarm_ns), indent + s["service"], s["operation"],
             f"kind={KIND_TEXT.get(s['kind'], s['kind'])}", f"status={STATUS_TEXT.get(s['status'], s['status'])}"]
    if s["status_code"] is not None:
        parts.append(f"code={s['status_code']}")
    parts.append(f"dur={s['duration_ms']:.1f}ms")
    if s["peer"]:
        parts.append(f"peer={s['peer']}")
    if show_trace:
        parts.append(f"trace={s['trace_id']}")
    line = " ".join(str(p) for p in parts)
    if s["error_text"]:
        e = " ".join(str(s["error_text"]).split())
        line += " error: " + (e[:ERROR_CHARS] + "..." if len(e) > ERROR_CHARS else e)
    return line


def _fit(header: str, lines: list[str], total: int, marker: Callable[[int, int], str],
         count_tokens: Callable[[str], int], max_tokens: int) -> tuple[str, int, bool]:
    """Başlık + sığan kadar tam satır (+ fazlası varsa tek işaret) ≤ max_tokens. Döner: (metin, gösterilen, kesildi)."""
    def text(n: int) -> str:
        body = [header, *lines[:n]]
        if n < total:
            body.append(marker(n, total))
        return "\n".join(body)

    # Satır başına sayımla yaklaşık n; sonra tam metinle: aşıyorsa azalt, bir satır daha sığıyorsa artır.
    budget = max_tokens - count_tokens(header) - count_tokens(marker(len(lines), total)) - 2
    n, used = 0, 0
    for line in lines:
        c = count_tokens(line) + 1
        if used + c > budget:
            break
        used += c
        n += 1
    while n > 0 and count_tokens(text(n)) > max_tokens:
        n -= 1
    while n < len(lines) and count_tokens(text(n + 1)) <= max_tokens:  # tahmin eksik kaldıysa: sığan kadar
        n += 1
    return text(n), n, n < total


# --- parametreler --------------------------------------------------------------------------------------------------

def _params(name: str, args: dict | None) -> dict:
    spec = TOOLS[name]["params"]
    args = args or {}
    out = {}
    for key, (kind, required, _) in spec.items():
        v = args.get(key)
        if v is None:
            if required:
                raise _Bad(f"{name} needs {key}")
            continue
        if kind == "string" and not isinstance(v, str):
            raise _Bad(f"{key} must be a string")
        if kind in ("number", "integer") and (isinstance(v, bool) or not isinstance(v, (int, float))):
            raise _Bad(f"{key} must be a number")
        if kind == "integer" and int(v) != v:
            raise _Bad(f"{key} must be a whole number")
        out[key] = v
    if "from_min" in out and "to_min" in out and out["from_min"] >= out["to_min"]:
        raise _Bad("from_min must be smaller than to_min")
    return out


def _at(case: Case, minutes: float) -> int:
    return case.alarm_ns + int(round(minutes * MIN_NS))


def _range(store: query.Store, case: Case, p: dict) -> tuple[int, int]:
    """Verilmeyen uç pencerenin tam ucu (ns)."""
    wlo, whi = store.window()
    lo = wlo if p.get("from_min") is None else _at(case, p["from_min"])
    hi = whi if p.get("to_min") is None else _at(case, p["to_min"])
    if lo >= hi:
        raise _Bad("from_min must be smaller than to_min")
    return lo, hi


def _series_range(store: query.Store, case: Case, p: dict, step_ns: int) -> tuple[int, int]:
    """metric_series aralığı: `from_min` yoksa alarma hizalı ilk sınır (pencere başından küçük olmayan);
    `to_min` yoksa kullanılan ızgarada (kırpılmış başlangıçtan) pencere sonunu aşmayan son sınır."""
    wlo, whi = store.window()
    alarm = case.alarm_ns
    if p.get("from_min") is None:
        lo = alarm - ((alarm - wlo) // step_ns) * step_ns
    else:
        lo = _at(case, p["from_min"])
    if p.get("to_min") is None:
        start = max(lo, wlo)  # query.py ızgarayı kırpılmış başlangıçtan sayar
        hi = start + max(0, (whi - start) // step_ns) * step_ns
    else:
        hi = _at(case, p["to_min"])
    if lo >= hi:
        if p.get("from_min") is not None and p.get("to_min") is not None:
            raise _Bad("from_min must be smaller than to_min")
        raise _Bad("the time range has no full bucket of step_s seconds; use a smaller step_s or give from_min "
                   "and to_min")
    return lo, hi


def _known_service(store: query.Store, service: str) -> None:
    names = {s["service"] for s in query.list_services(store)["services"]}
    if service not in names:
        raise _Bad(f'unknown service "{service}"; call list_services')


def _clip_note(res: dict) -> str:
    return " (clipped to the incident window)" if res.get("clipped") else ""


# --- araçlar -------------------------------------------------------------------------------------------------------

def run_tool(store: query.Store, case: Case, name: str, args: dict | None, count_tokens: Callable[[str], int],
             max_tokens: int) -> ToolResult:
    """Aracı koşar, metne döker, token sınırına sığdırır. Bilinmeyen araç, geçersiz parametre ve sorgunun reddi
    `error: ...` sonucudur."""
    try:
        if name not in TOOLS:
            raise _Bad(f'unknown tool "{name}"; tools: ' + ", ".join(TOOLS))
        p = _params(name, args)
        header, lines, total, marker = _dispatch(store, case, name, p)
    except (_Bad, ValueError) as e:
        text = f"error: {e}"
        return ToolResult(text, 0, 0, False, True)
    text, shown, truncated = _fit(header, lines, total, marker, count_tokens, max_tokens)
    return ToolResult(text, shown, total, truncated, False)


def _dispatch(store, case: Case, name: str, p: dict):
    alarm = case.alarm_ns
    if name == "list_services":
        rows = query.list_services(store)["services"]
        yn = lambda b: "yes" if b else "no"  # noqa: E731
        lines = [f"{r['service']}: spans={yn(r['spans'])} logs={yn(r['logs'])} metrics={yn(r['metrics'])}"
                 for r in rows]
        return (f"{len(rows)} services", lines, len(lines),
                lambda n, m: f"[showing the first {n} of {m} services]")
    if name == "metric_series":
        if p["metric"] not in query.SERIES:
            raise _Bad(f'unknown metric "{p["metric"]}"; metrics: ' + ", ".join(query.SERIES))
        step = p.get("step_s", 60 if p.get("service") is not None else ALL_SERVICES_STEP_S)
        if not 10 <= step <= 600:
            raise _Bad("step_s must be between 10 and 600")
        if p.get("service") is None:
            return _all_services_series(store, case, p["metric"], int(step), p)
        _known_service(store, p["service"])
        lo, hi = _series_range(store, case, p, int(step) * 10**9)
        res = query.metric_series(store, p["service"], p["metric"], lo, hi, step_s=int(step))
        digits = SERIES_DIGITS[p["metric"]]
        lines = [f"{rel_time(t, alarm, ms=False)} {_num(v, digits)}" for t, v in res["points"]]
        header = (f"{p['metric']} of {p['service']} ({UNITS[p['metric']]}), {int(step)} s buckets, "
                  f"bucket start time{_clip_note(res)}:")
        return (header, lines, len(lines),
                lambda n, m: f"[showing the first {n} of {m} buckets; use a larger step_s or a shorter range]")
    if name == "search_spans":
        if p.get("status") is not None and p["status"] not in query.SPAN_STATUS:
            raise _Bad("status must be error, ok or unset")
        if p.get("service") is not None:
            _known_service(store, p["service"])
        lo, hi = _range(store, case, p)
        res = query.search_spans(store, lo, hi, service=p.get("service"), operation=p.get("operation"),
                                 status=p.get("status"), min_duration_ms=p.get("min_duration_ms"), limit=FETCH_LIMIT)
        lines = [_span_line(s, alarm) for s in res["spans"]]
        return (f"{res['total']} spans{_clip_note(res)}", lines, res["total"],
                lambda n, m: f"[showing the first {n} of {m} by start time; narrow the query]")
    if name == "get_trace":
        res = query.get_trace(store, p["trace_id"], limit=FETCH_LIMIT)
        if res["total"] == 0:
            raise _Bad(f'no trace "{p["trace_id"]}" in this incident')
        depth = {}
        by_id = {s["span_id"]: s for s in res["spans"]}
        for s in res["spans"]:  # başlangıç sırası: üst span çoğunlukla önce gelir
            d, cur, seen = 0, s, set()
            while cur["parent_span_id"] in by_id and cur["span_id"] not in seen:
                seen.add(cur["span_id"])
                cur = by_id[cur["parent_span_id"]]
                d += 1
            depth[s["span_id"]] = d
        lines = [_span_line(s, alarm, indent="  " * depth[s["span_id"]], show_trace=False) for s in res["spans"]]
        return (f"trace {p['trace_id']}: {res['total']} spans", lines, res["total"],
                lambda n, m: f"[showing the first {n} of {m} spans of this trace by start time]")
    if name == "search_logs":
        if p.get("min_level") is not None and p["min_level"] not in LOG_LEVELS:
            raise _Bad("min_level must be info, warn or error")
        if p.get("service") is not None:
            _known_service(store, p["service"])
        lo, hi = _range(store, case, p)
        res = query.search_logs(store, lo, hi, service=p.get("service"),
                                min_severity=LOG_LEVELS.get(p.get("min_level")), text=p.get("text"), limit=FETCH_LIMIT)
        lines = []
        for r in res["logs"]:
            msg = " ".join(r["message"].split()) + ("..." if r["truncated_message"] else "")
            lines.append(f"{rel_time(r['time_ms'] * MS, alarm)} {r['service']} {_level_text(r['severity_number'])} "
                         f"{msg}")
        return (f"{res['total']} log records{_clip_note(res)}", lines, res["total"],
                lambda n, m: f"[showing the first {n} of {m} by time; narrow the query]")
    if name == "service_dependencies":
        lo, hi = _range(store, case, p)
        res = query.service_dependencies(store, lo, hi)
        lines = [f"{e['caller']} -> {e['callee']} calls={e['calls']} errors={e['errors']}" for e in res["edges"]]
        return (f"{len(lines)} caller -> callee pairs{_clip_note(res)}", lines, len(lines),
                lambda n, m: f"[showing {n} of {m} edges]")
    raise _Bad(f'unknown tool "{name}"')


def _all_services_series(store, case: Case, metric: str, step: int, p: dict):
    """Servissiz metric_series: servis başına `query.metric_series` (aynı aralık ve adım), `list_services` sırası.
    Konteyner metriğinde `metrics=yes` olup en az bir değeri olan, span metriğinde `spans=yes` olup aralıkta en az bir
    gelen span'i olan servisler; ötekiler başlıkta "no data"."""
    lo, hi = _series_range(store, case, p, step * 10**9)
    container = metric in query.CONTAINER_SERIES
    digits = SERIES_DIGITS[metric]
    lines, no_data, first = [], [], None
    for r in query.list_services(store)["services"]:
        if not (r["metrics"] if container else r["spans"]):
            continue
        res = query.metric_series(store, r["service"], metric, lo, hi, step_s=step)
        if first is None:
            first = res
        values = [v for _, v in res["points"]]
        if container:
            has = any(v is not None for v in values)
        else:
            req = values if metric == "requests" else \
                [v for _, v in query.metric_series(store, r["service"], "requests", lo, hi, step_s=step)["points"]]
            has = sum(req) > 0
        if not has:
            no_data.append(r["service"])
            continue
        lines.append(f"{r['service']}: " + " ".join(_num(v, digits) for v in values))
    if first is None:  # bu sinyali taşıyan servis yok: başlık yine aynı ızgarayı söyler
        wlo, whi = store.window()
        a, b = max(lo, wlo), min(hi, whi)
        first = {"start_ns": a, "clipped": a != lo or b != hi, "points": [[t, None] for t in range(a, b, step * 10**9)]}
    header = (f"{metric} of {len(lines)} services ({UNITS[metric]}), {step} s buckets starting at "
              f"{rel_time(first['start_ns'], case.alarm_ns, ms=False)}, {len(first['points'])} values per row"
              f"{_clip_note(first)}")
    if no_data:
        header += "; no data for: " + ", ".join(no_data)
    header += ":"
    return (header, lines, len(lines),
            lambda n, m: f"[showing the first {n} of {m} services; use a larger step_s, a shorter range or one "
                         f"service]")
