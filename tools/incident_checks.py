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
- `caller_rows`, `caller_symptom_check` (V2, durdurma ve dondurma): hedefin kendi span'leri kesilir ya da azalır;
  belirti ve olay hedefi çağıranların hedefe giden istemci span'lerinde ölçülür (çağıran + span adı başına, aynı
  eşikler, en az M istek). Hedefe giden span: `server.address` ya da `net.peer.name` hedefin adı ya da o vakadaki IP'si
  (enjeksiyondan önce ve geri almadan sonra kaydedilen ikisi de), ya da gRPC servis adı (`rpc.service`; yoksa
  `rpc.method`'un "/" öncesi, ör. checkout'un Go istemcisi) hedefin kendi gelen span'lerinde görülen adlardan biri
  (sabit tablo yok). `server.address` ve `net.peer.name` yoksa adres `http.url` ya da `url.full`'daki ana makine
  adından okunur: Python'ın requests enstrümantasyonu (0.64b0) eski alan adlarını yazıyor, adres yalnız URL'de
  (quote-gateway → quote; DECISIONS 2026-10-28 "Çağıran eşleşmesi URL'deki adresi de okur").
- `stronger_symptom` (V2c, ağ hataları): hedefin kendi ölçümü ile çağıran ölçümünden güçlü olanı.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import c2_measure as cm  # noqa: E402
# İşlem ve çağıran satırları pakette (DECISIONS 2026-10-30 "P1a kararları"); adlar buradan da içe aktarılabilir.
from aiops_rca.signals import (  # noqa: E402, F401
    INCOMING_KINDS, STATUS_ERROR, Window, iter_lines, resource_attr, SPAN_KIND_CLIENT, _rpc_service, _span_attrs,
    caller_rows, operation_rows,
)

MIN_OP_REQUESTS = 10
BASELINE_P95_MS = 25.3
BASELINE_FACTOR = 2
RESOURCE_SIGNALS = ("cpu_pct", "mem_mb")


def caller_symptom_check(callers: dict, target: str, m: int = MIN_OP_REQUESTS) -> dict:
    """Hedefi çağıranların istemci span'lerinde en güçlü işlem sinyali (iki dönemde de en az m istek)."""
    best, measured = None, 0
    for (caller, name), r in callers.items():
        if r["before"][0] < m or r["after"][0] < m:
            continue
        measured += 1
        for sig, v in _op_signals(r).items():
            if best is None or v["strength"] > best["strength"]:
                best = {"level": "caller", "caller": caller, "operation": name, "signal": sig,
                        "strength": v["strength"], "requests": [r["before"][0], r["after"][0]],
                        "values": [v["before"], v["after"]]}
    return {"service": target, "min_requests": m, "callers_measured": measured,
            "verdict": cm.classify(best["strength"]) if best else "not_measurable", "deciding": best,
            "service_level": None, "operation_level": None}


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


def stronger_symptom(a: dict, b: dict) -> dict:
    """İki belirti ölçümünden karar sinyali güçlü olan (ağ hatası: hedef ve çağıranlar); eşitlikte `a`."""
    def strength(s: dict) -> float:
        return s["deciding"]["strength"] if s.get("deciding") else float("-inf")
    return b if strength(b) > strength(a) else a


def event_check(symptom: dict, rows: dict, m: int = MIN_OP_REQUESTS) -> dict:
    top, row = symptom["deciding"], rows.get(symptom["service"], {})
    total = row.get("requests_after")
    if top is None or (top["level"] == "service" and total is None):
        return {"applied": False, "pass": None, "reason": "no spans for the service" if top else "no signal"}
    if top["level"] == "operation":
        n, basis = top["requests"][1], f"operation {top['operation']}"
    elif top["level"] == "caller":
        n, basis = top["requests"][1], f"caller {top['caller']} {top['operation']}"
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
