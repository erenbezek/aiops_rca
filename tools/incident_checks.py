"""Vaka kontrolleri (vaka üretimi V1; HANDOFF 2026-10-25 V1 kartı ve "V1 netleştirmeler").

Ölçüm C2'ninkiyle aynı (`c2_measure`, `trial_summary`): normal = alarmdan (flag yazma anı) önceki 10 dk, enjeksiyon =
sonraki 10 dk; istek = gelen span (SERVER, CONSUMER); p95/p99 = `c2_measure.pct`; eşikler `c2_measure.signals`.
Ölçütler V1a 2. adımda C2 verisiyle seçildi (ölçmeden önce yazılı kurallarla): `MIN_OP_REQUESTS` (M) 10, taban
referansı 25,3 ms (15 geçerli koşunun normal dönem frontend p95 medyanı).

- `operation_rows`: servis + span adı başına istek, hata, süreler (iki dönem).
- `symptom_check`: kök neden servisinde servis düzeyi sinyaller (C2 kuralı) + her işlem için hata oranı +0,05,
  p95 ve p99 ×1,5 ve +20 ms (iki dönemde de en az M istek). Karar en güçlü sinyal: < 0,8 belirtisiz, < 1,2 sınırda,
  üstü belirtili (`c2_measure.classify`).
- `event_check`: enjeksiyon döneminde olay var mı. Karar bir işlemden geldiyse o işlemde, servis düzeyi bir sinyalden
  (kaynak dahil) geldiyse servisin toplamında en az M istek. Servisin hiç izi yoksa uygulanmaz.
- `baseline_check`: normal dönem frontend p95 ≤ `BASELINE_FACTOR` × `BASELINE_P95_MS`.
- `monitoring_health`: collector'ın kendi exporter sayaçları (pencerede artış), kayıt için; vakayı geçersiz kılmaz.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c2_measure as cm  # noqa: E402
from trial_summary import INCOMING_KINDS, STATUS_ERROR, Window, iter_lines, resource_attr  # noqa: E402

MIN_OP_REQUESTS = 10
BASELINE_P95_MS = 25.3
BASELINE_FACTOR = 2
RESOURCE_SIGNALS = ("cpu_pct", "mem_mb")


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


def _op_signals(r: dict) -> dict:
    (nb, eb, db), (na, ea, da) = r["before"], r["after"]
    out = {"error_rate": {"before": round(eb / nb, 4), "after": round(ea / na, 4),
                          "strength": round((ea / na - eb / nb) / 0.05, 3)}}
    for p, q in (("p95_ms", 0.95), ("p99_ms", 0.99)):
        s = cm.ratio_delta(cm.pct(db, q), cm.pct(da, q), 1.5, 20)
        if s:
            out[p] = s
    return out


def _operation_best(ops: dict, svc: str, m: int) -> dict | None:
    best = None
    for (s, name), r in ops.items():
        if s != svc or r["before"][0] < m or r["after"][0] < m:
            continue
        for sig, v in _op_signals(r).items():
            if best is None or v["strength"] > best["strength"]:
                best = {"level": "operation", "operation": name, "signal": sig, "strength": v["strength"],
                        "requests": [r["before"][0], r["after"][0]], "values": [v["before"], v["after"]]}
    return best


def _service_best(row: dict | None, svc: str) -> dict | None:
    if not row:
        return None
    sig, _ = cm.signals(row, svc in cm.DB_SERVICES)
    if not sig:
        return None
    name, v = max(sig.items(), key=lambda kv: kv[1]["strength"])
    return {"level": "service", "signal": name, "strength": v["strength"]}


def symptom_check(rows: dict, ops: dict, svc: str, m: int = MIN_OP_REQUESTS) -> dict:
    """rows: `c2_measure.service_rows` sonucu; ops: `operation_rows` sonucu."""
    sb, ob = _service_best(rows.get(svc), svc), _operation_best(ops, svc, m)
    cand = [x for x in (sb, ob) if x]
    top = max(cand, key=lambda x: x["strength"]) if cand else None
    return {"service": svc, "min_requests": m, "verdict": cm.classify(top["strength"]) if top else "not_measurable",
            "deciding": top, "service_level": sb, "operation_level": ob}


def event_check(symptom: dict, rows: dict, m: int = MIN_OP_REQUESTS) -> dict:
    top, row = symptom["deciding"], rows.get(symptom["service"], {})
    total = row.get("requests_after")
    if top is None or (top["level"] == "service" and total is None):
        return {"applied": False, "pass": None, "reason": "no spans for the service" if top else "no signal"}
    if top["level"] == "operation":
        n, basis = top["requests"][1], f"operation {top['operation']}"
    else:
        n, basis = total, "service total" + (" (resource signal)" if top["signal"] in RESOURCE_SIGNALS else "")
    return {"applied": True, "pass": n >= m, "requests_after": n, "basis": basis, "min_requests": m}


def baseline_check(rows: dict) -> dict:
    p95 = rows.get("frontend", {}).get("p95_ms_before")
    threshold = BASELINE_FACTOR * BASELINE_P95_MS
    return {"frontend_p95_ms": p95, "reference_ms": BASELINE_P95_MS, "threshold_ms": threshold,
            "pass": p95 is not None and p95 <= threshold}


def monitoring_health(metrics_file: Path, lo: int, hi: int) -> dict:
    """Collector exporter sayaçlarının [lo, hi] artışı (kayıt); `opensearch` ayrıca öne çıkar."""
    series, _ = cm.read_otelcol(metrics_file)
    c = cm.collector_counters(series, lo, hi)
    exporters = {**{k: {x: v[x] for x in ("sent", "send_failed", "enqueue_failed")}
                    for k, v in c["file_exporters"].items() if v["sent_series"]},
                 **c["other_exporters_record_only"]}
    return {"opensearch": exporters.get("opensearch"), "exporters": exporters,
            "receiver_refused": c["receiver_refused"]["increase"]}
