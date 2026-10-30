"""Vaka sinyalleri: pencere, dosya okuma, servis satırları, sinyaller ve güç, basit kural, işlem ve çağıran satırları.

Ölçüler `tools/trial_summary.py`, `tools/c2_measure.py` ve `tools/incident_checks.py`'den olduğu gibi taşındı
(DECISIONS 2026-10-30 "P1a kararları"); o modüller bu adları buradan içe aktarır, koşucu ve eski sonuçlar aynı kalır
(eşitlik testi: HANDOFF P1a 1. adım).

- Pencere (`Window`): alarmdan önceki 10 dk ("before") ve sonraki 10 dk ("after"). Kaydın zamanı: span'de
  `startTimeUnixNano`; logda `timeUnixNano`, 0 ya da yoksa `observedTimeUnixNano`; metrikte veri noktasının
  `timeUnixNano`'su.
- `summarize`: servis başına gelen istek (SERVER, CONSUMER span'leri), hata, süre; konteyner CPU (birikimli sayaçtan)
  ve bellek; WARN+ log mesajları (sadeleşmiş). `service_rows`: servis başına önce/sonra değerleri.
- `signals`: sinyal başına güç (HANDOFF 2026-10-24): T = eşiğin iki koşulunun büyüğü; güç = (sonra − önce) / (T − önce);
  istek düşüşünde (önce − sonra) / (önce − T). Eşikler (zor deneme, Eren 2026-10-21) + p99: hata oranı +0,05; p95 ve
  p99 ×1,5 ve +20 ms; CPU ×1,5 ve +5 puan; bellek ×1,2; yeni WARN+ log ≥ 5; istek düşüşü önce ≥ 20 iken ×0,5.
  `classify`: < 0,8 belirtisiz, < 1,2 sınırda, üstü belirtili.
- `rule_check`: C2'nin basit kuralı (HANDOFF 2026-10-23 C2 kartı 4. madde): aynı sinyaller ve eşikler bütün servislere;
  puan = gücü ≥ 1 olan sinyal sayısı, eşitlikte en büyük güç, sonra servis adı; ilk 3. astronomy-db ve valkey-cart
  yalnız CPU/bellek; izleme araçları ve rutin servisler (flagd, flagd-ui, load-generator) yok.
- `operation_rows`: servis + span adı başına gelen istek, hata, süre. `caller_rows`: çağıranların hedefe giden istemci
  span'leri (eşleşme kuralı `tools/incident_checks.py` belgesinde).
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit


WINDOW_NS = 10 * 60 * 10**9
EDGE_NS = 60 * 10**9  # pencere uçlarında kayıt aranan aralık
INCOMING_KINDS = {2, 5}  # SPAN_KIND_SERVER, SPAN_KIND_CONSUMER
STATUS_ERROR = 2
SEVERITY_WARN = 13
MESSAGE_CHARS = 200
MESSAGE_KEYS = ("exception.message", "err.message", "error.message", "error", "err", "message")
CPU_METRIC = "container.cpu.usage.total"  # birikimli CPU süresi, ns
MEMORY_METRIC = "container.memory.usage.total"
# İzleme araçları (Eren, 2026-10-21): özete girmez. flagd, flagd-ui, load-generator collector'da zaten düşüyor.
TOOLING_CONTAINERS = frozenset({"jaeger", "grafana", "prometheus", "opensearch", "otel-collector", "opamp-server"})
ID_PATTERNS = (
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<id>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "<id>"),
    (re.compile(r"\d+"), "<n>"),
)


def resource_attr(resource: dict, key: str) -> str | None:
    for a in resource.get("attributes", []):
        if a.get("key") == key:
            return a.get("value", {}).get("stringValue")
    return None


def value_text(value: dict) -> str:
    if "stringValue" in value:
        return value["stringValue"]
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def log_message(record: dict) -> str:
    text = value_text(record.get("body", {})).strip()
    if text:
        return text
    attrs = {a.get("key"): a.get("value", {}) for a in record.get("attributes", [])}
    for key in MESSAGE_KEYS:
        if key in attrs and value_text(attrs[key]).strip():
            return value_text(attrs[key]).strip()
    return "<no message>"


def normalize(message: str) -> str:
    message = " ".join(message.split())
    for pattern, repl in ID_PATTERNS:
        message = pattern.sub(repl, message)
    return message[:MESSAGE_CHARS]


def point_value(dp: dict) -> float | None:
    if "asDouble" in dp:
        return float(dp["asDouble"])
    if "asInt" in dp:
        return float(dp["asInt"])
    return None


class Window:
    def __init__(self, alarm_ns: int):
        self.start = alarm_ns - WINDOW_NS
        self.alarm = alarm_ns
        self.end = alarm_ns + WINDOW_NS

    def side(self, t: int) -> str | None:
        if self.start <= t < self.alarm:
            return "before"
        if self.alarm <= t < self.end:
            return "after"
        return None


def iter_lines(paths: list[Path]):
    for path in paths:
        with path.open(encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except ValueError as e:
                        raise ValueError(f"{path}:{n}: {e}") from e


def summarize(paths: list[Path], window: Window) -> tuple[dict, dict]:
    spans = defaultdict(lambda: {"before": [0, 0, []], "after": [0, 0, []]})  # [istek, hata, süreler]
    logs = defaultdict(Counter)  # (servis, mesaj) -> {before, after}
    resources = defaultdict(lambda: {"before": [], "after": []})  # (konteyner, metrik) -> değerler
    cpu_counters = defaultdict(dict)  # konteyner -> {zaman: birikimli CPU ns}
    edges = {"spans": [False, False], "logs": [False, False], "metrics": [False, False]}

    def mark(signal: str, t: int) -> None:
        if window.start <= t < window.start + EDGE_NS:
            edges[signal][0] = True
        if window.end - EDGE_NS <= t < window.end:
            edges[signal][1] = True

    for doc in iter_lines(paths):
        for rs in doc.get("resourceSpans", []):
            svc = resource_attr(rs.get("resource", {}), "service.name")
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    t = int(sp.get("startTimeUnixNano", 0))
                    mark("spans", t)
                    side = window.side(t)
                    if side is None or svc is None or sp.get("kind") not in INCOMING_KINDS:
                        continue
                    row = spans[svc][side]
                    row[0] += 1
                    if sp.get("status", {}).get("code") == STATUS_ERROR:
                        row[1] += 1
                    row[2].append(int(sp.get("endTimeUnixNano", t)) - t)
        for rl in doc.get("resourceLogs", []):
            svc = resource_attr(rl.get("resource", {}), "service.name")
            for sl in rl.get("scopeLogs", []):
                for rec in sl.get("logRecords", []):
                    t = int(rec.get("timeUnixNano", 0)) or int(rec.get("observedTimeUnixNano", 0))
                    mark("logs", t)
                    side = window.side(t)
                    if side is None or rec.get("severityNumber", 0) < SEVERITY_WARN:
                        continue
                    logs[(svc or "<unknown>", normalize(log_message(rec)))][side] += 1
        for rm in doc.get("resourceMetrics", []):
            container = resource_attr(rm.get("resource", {}), "container.name")
            for sm in rm.get("scopeMetrics", []):
                for m in sm.get("metrics", []):
                    if m.get("name") not in (CPU_METRIC, MEMORY_METRIC):
                        continue
                    for dp in (m.get("gauge") or m.get("sum") or {}).get("dataPoints", []):
                        t = int(dp.get("timeUnixNano", 0))
                        mark("metrics", t)
                        side = window.side(t)
                        value = point_value(dp)
                        if not container or container in TOOLING_CONTAINERS or value is None:
                            continue
                        if m["name"] == CPU_METRIC:
                            # Pencereden hemen önceki ölçüm de lazım: ilk hız onunla hesaplanır.
                            if window.start - EDGE_NS <= t < window.end:
                                cpu_counters[container][t] = value
                        elif side is not None:
                            resources[(container, m["name"])][side].append(value)
    for container, points in cpu_counters.items():
        ordered = sorted(points.items())
        for (t1, v1), (t2, v2) in zip(ordered, ordered[1:]):
            side = window.side(t2)
            if side is None or v2 < v1:  # sayaç geriye düştü: konteyner yeniden başladı
                continue
            resources[(container, CPU_METRIC)][side].append((v2 - v1) / (t2 - t1) * 100)
    return {"spans": spans, "logs": logs, "resources": resources}, edges


ROUTINE_SERVICES = frozenset({"flagd", "flagd-ui", "load-generator"})
DB_SERVICES = frozenset({"astronomy-db", "valkey-cart"})


def pct(durations: list[int], q: float) -> float | None:
    if not durations:
        return None
    ordered = sorted(durations)
    return round(ordered[max(0, math.ceil(q * len(ordered)) - 1)] / 1e6, 1)


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def service_rows(result: dict) -> dict[str, dict]:
    """Servis başına önce/sonra değerleri (trial_summary.summarize sonucundan)."""
    rows = defaultdict(dict)
    for svc, sides in result["spans"].items():
        for side, (count, errors, durations) in sides.items():
            r = rows[svc]
            r[f"requests_{side}"] = count
            r[f"error_rate_{side}"] = errors / count if count else None
            r[f"p95_ms_{side}"] = pct(durations, 0.95)
            r[f"p99_ms_{side}"] = pct(durations, 0.99)
    for (container, metric), sides in result["resources"].items():
        for side, values in sides.items():
            if metric == CPU_METRIC:
                rows[container][f"cpu_pct_{side}"] = avg(values)
            elif metric == MEMORY_METRIC:
                a = avg(values)
                rows[container][f"mem_mb_{side}"] = a / 2**20 if a is not None else None
    for (svc, msg), c in result["logs"].items():
        if c["before"] == 0 and c["after"] > 0:
            r = rows[svc]
            if c["after"] > r.get("new_warn_top", (0, ""))[0]:
                r["new_warn_top"] = (c["after"], msg)
    return rows


def ratio_delta(b, a, ratio: float, delta: float):
    if b is None or a is None:
        return None
    t = max(ratio * b, b + delta)
    return {"before": round(b, 4), "after": round(a, 4), "threshold": round(t, 4), "strength": round((a - b) / (t - b), 3)}


def signals(row: dict, only_resources: bool = False) -> tuple[dict[str, dict], list[str]]:
    """(sinyal → değerler ve güç, değeri olmayan sinyaller)."""
    g = row.get
    out, missing = {}, []
    if not only_resources:
        eb, ea = g("error_rate_before"), g("error_rate_after")
        if eb is not None and ea is not None:
            out["error_rate"] = {"before": round(eb, 4), "after": round(ea, 4), "threshold": round(eb + 0.05, 4),
                                 "strength": round((ea - eb) / 0.05, 3)}
        else:
            missing.append("error_rate")
        for p in ("p95_ms", "p99_ms"):
            s = ratio_delta(g(f"{p}_before"), g(f"{p}_after"), 1.5, 20)
            if s:
                out[p] = s
            else:
                missing.append(p)
        rb, ra = g("requests_before"), g("requests_after")
        if rb is not None and ra is not None and rb >= 20:
            out["request_drop"] = {"before": rb, "after": ra, "threshold": rb * 0.5,
                                   "strength": round((rb - ra) / (rb * 0.5), 3)}
        else:
            missing.append("request_drop")
        top = g("new_warn_top", (0, None))
        out["new_warn_log"] = {"before": 0, "after": top[0], "threshold": 5, "strength": round(top[0] / 5, 3),
                               "message": top[1]}
    s = ratio_delta(g("cpu_pct_before"), g("cpu_pct_after"), 1.5, 5)
    if s:
        out["cpu_pct"] = s
    else:
        missing.append("cpu_pct")
    mb, ma = g("mem_mb_before"), g("mem_mb_after")
    if mb is not None and ma is not None and mb > 0:
        out["mem_mb"] = {"before": round(mb, 1), "after": round(ma, 1), "threshold": round(1.2 * mb, 1),
                         "strength": round((ma - mb) / (0.2 * mb), 3)}
    else:
        missing.append("mem_mb")
    return out, missing


def classify(strength: float) -> str:
    if strength < 0.8:
        return "no_symptom"
    return "borderline" if strength < 1.2 else "symptomatic"


def rule_check(rows: dict[str, dict], root: str | None) -> dict:
    scored = []
    for svc, row in rows.items():
        if svc in TOOLING_CONTAINERS or svc in ROUTINE_SERVICES or svc == "<unknown>":
            continue
        sig, _ = signals(row, svc in DB_SERVICES)
        over = [k for k, s in sig.items() if s["strength"] >= 1]
        best = max((s["strength"] for k, s in sig.items() if s["strength"] >= 1), default=0)
        scored.append((len(over), best, svc, over))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    top = [{"service": svc, "score": n, "max_strength": round(b, 3), "signals": over} for n, b, svc, over in scored[:3]]
    names = [t["service"] for t in top]
    return {"top3": top, "top1_hit": bool(names) and names[0] == root if root else None,
            "top3_hit": root in names if root else None}


SPAN_KIND_CLIENT = 3


def operation_rows(paths: list[Path], window: Window) -> dict:
    """(servis, span adı) → {"before"|"after": [istek, hata, süreler (ns)]}; yalnız gelen span'ler."""
    ops = defaultdict(lambda: {"before": [0, 0, []], "after": [0, 0, []]})
    for doc in iter_lines(paths):
        for rs in doc.get("resourceSpans", []):
            svc = resource_attr(rs.get("resource", {}), "service.name")
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    t = int(sp.get("startTimeUnixNano", 0))
                    side = window.side(t)
                    if side is None or svc is None or sp.get("kind") not in INCOMING_KINDS:
                        continue
                    row = ops[(svc, sp.get("name", ""))][side]
                    row[0] += 1
                    if sp.get("status", {}).get("code") == STATUS_ERROR:
                        row[1] += 1
                    row[2].append(int(sp.get("endTimeUnixNano", t)) - t)
    return dict(ops)


def _span_attrs(sp: dict, keys: tuple[str, ...]) -> dict:
    return {a["key"]: next(iter(a["value"].values()), None) for a in sp.get("attributes", []) if a["key"] in keys}


def _rpc_service(a: dict) -> str | None:
    method = a.get("rpc.method") or ""
    return a.get("rpc.service") or (method.rsplit("/", 1)[0] if "/" in method else None)


def caller_rows(paths: list[Path], window: Window, target: str, ips: tuple[str, ...] = ()) -> tuple[dict, list]:
    """(çağıran, span adı) → {"before"|"after": [istek, hata, süreler]}: çağıranların hedefe giden istemci span'leri.
    Döner: (satırlar, hedefin gRPC servis adları)."""
    rpc_services, groups = set(), defaultdict(lambda: {"before": [0, 0, []], "after": [0, 0, []]})
    keys = ("server.address", "net.peer.name", "http.url", "url.full", "rpc.service", "rpc.method")
    for doc in iter_lines(paths):
        for rs in doc.get("resourceSpans", []):
            svc = resource_attr(rs.get("resource", {}), "service.name")
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    kind = sp.get("kind")
                    if svc == target and kind in INCOMING_KINDS:
                        rpc = _rpc_service(_span_attrs(sp, ("rpc.service", "rpc.method")))
                        if rpc:
                            rpc_services.add(rpc)
                        continue
                    if kind != SPAN_KIND_CLIENT or svc is None:
                        continue
                    t = int(sp.get("startTimeUnixNano", 0))
                    side = window.side(t)
                    if side is None:
                        continue
                    a = _span_attrs(sp, keys)
                    peer = a.get("server.address") or a.get("net.peer.name")
                    if not peer and (a.get("http.url") or a.get("url.full")):
                        try:
                            peer = urlsplit(a.get("http.url") or a.get("url.full")).hostname
                        except ValueError:
                            peer = None
                    row = groups[(svc, sp.get("name", ""), peer, _rpc_service(a))][side]
                    row[0] += 1
                    if sp.get("status", {}).get("code") == STATUS_ERROR:
                        row[1] += 1
                    row[2].append(int(sp.get("endTimeUnixNano", t)) - t)
    names = {target, *ips}
    out = defaultdict(lambda: {"before": [0, 0, []], "after": [0, 0, []]})
    for (svc, name, peer, rpc), r in groups.items():
        if peer in names or (rpc and rpc in rpc_services):
            for side in ("before", "after"):
                o = out[(svc, name)][side]
                o[0] += r[side][0]
                o[1] += r[side][1]
                o[2].extend(r[side][2])
    return dict(out), sorted(rpc_services)
