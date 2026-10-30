"""BARO baseline (HANDOFF 2026-10-30 P1b kartı; DECISIONS 2026-10-30 "BARO uygulaması", "BARO girdisi",
"BARO girdisi düzeltmesi"). RCAEval (MIT) 1.9.0'ın `baro`'su ve değerlendirme akışı (`main.py`) saf Python'a taşınır.

Tablo (`baro_table`), dev'de ayarlanmaz:
- Izgara: alarm − 600 sn'den başlayan 120 kova × 10 sn. `time` = kova başı (unix saniye). Normal `time < alarm` (60 satır),
  anomali `time ≥ alarm` (60 satır).
- Sütunlar `<servis>_<metrik>`; servis adına göre, sonra `METRICS` sırasıyla:
  - `_cpu`: `container.cpu.usage.total` (birikimli ns) → bir çekirdeğin yüzdesi (ardışık iki nokta: fark / süre × 100).
  - `_mem`: `container.memory.usage.total`, bayt (RCAEval `_mem`'i MB'a çevirir).
  - `_net_rx`, `_net_tx`: `container.network.io.usage.{rx,tx}_bytes` (birikimli) → bayt/sn; aynı zamandaki arayüzler
    toplanır.
  - `_latency` (p90, ms), `_requests`, `_errors`: servisin gelen span'leri (SERVER, CONSUMER), başlangıç zamanına göre.
- Kova değeri: bellek kovadaki noktaların ortalaması; CPU ve ağ hızı ikinci noktanın kovasına yazılır (kovada birden çoksa
  ortalama; sayaç geriye düşerse o çift atlanır; ilk kova için pencereden önceki 60 sn'deki son nokta da kullanılır).
  Boş kovada `_requests` ve `_errors` 0, diğerleri NaN.
- Aday kümesi kural baseline'ıyla aynı: izlerdeki ve metriklerdeki adlar; izleme araçları, rutin servisler ve `<unknown>`
  hariç. Sütun yalnız verisi olan için: konteyner sütunu pencerede metrik noktası olan konteynerde, iz sütunu pencerede
  gelen span'i olan serviste (veritabanlarında iz sütunu yok).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from aiops_rca.cases import Case
from aiops_rca.signals import (CPU_METRIC, EDGE_NS, INCOMING_KINDS, MEMORY_METRIC, ROUTINE_SERVICES, STATUS_ERROR,
                               TOOLING_CONTAINERS, iter_lines, pct, resource_attr)

BUCKET_S = 10
HALF_S = 600
N_BUCKETS = 2 * HALF_S // BUCKET_S
NET_RX = "container.network.io.usage.rx_bytes"
NET_TX = "container.network.io.usage.tx_bytes"
METRICS = ("cpu", "mem", "net_rx", "net_tx", "latency", "requests", "errors")
CONTAINER_METRICS = {CPU_METRIC: "cpu", MEMORY_METRIC: "mem", NET_RX: "net_rx", NET_TX: "net_tx"}
NAN = float("nan")


def _excluded(name: str | None) -> bool:
    return not name or name in TOOLING_CONTAINERS or name in ROUTINE_SERVICES or name == "<unknown>"


def _bucket(t_ns: int, start_ns: int) -> int | None:
    k = (t_ns - start_ns) // (BUCKET_S * 10**9)
    return k if 0 <= k < N_BUCKETS else None


def _container_points(paths: list[Path], start_ns: int, end_ns: int) -> dict:
    """(konteyner, metrik) → {zaman: değer}; aynı zamandaki farklı öznitelikli noktalar (arayüzler) toplanır."""
    raw = defaultdict(dict)  # (konteyner, metrik) → {(zaman, öznitelikler): değer}
    for doc in iter_lines(paths):
        for rm in doc.get("resourceMetrics", []):
            c = resource_attr(rm.get("resource", {}), "container.name")
            if _excluded(c):
                continue
            for sm in rm.get("scopeMetrics", []):
                for m in sm.get("metrics", []):
                    metric = CONTAINER_METRICS.get(m.get("name"))
                    if metric is None:
                        continue
                    for dp in (m.get("gauge") or m.get("sum") or {}).get("dataPoints", []):
                        t = int(dp.get("timeUnixNano", 0))
                        v = dp.get("asDouble", dp.get("asInt"))
                        if v is None or not (start_ns - EDGE_NS <= t < end_ns):
                            continue
                        key = json.dumps(dp.get("attributes", []), sort_keys=True)
                        raw[(c, metric)][(t, key)] = float(v)
    out = {}
    for k, pts in raw.items():
        by_t = defaultdict(float)
        for (t, _), v in pts.items():
            by_t[t] += v
        out[k] = dict(by_t)
    return out


def _span_buckets(paths: list[Path], start_ns: int) -> dict:
    """servis → kova → [istek, hata, süreler (ns)] (gelen span'ler)."""
    out = defaultdict(lambda: [[0, 0, []] for _ in range(N_BUCKETS)])
    for doc in iter_lines(paths):
        for rs in doc.get("resourceSpans", []):
            svc = resource_attr(rs.get("resource", {}), "service.name")
            if _excluded(svc):
                continue
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    if sp.get("kind") not in INCOMING_KINDS:
                        continue
                    t = int(sp.get("startTimeUnixNano", 0))
                    k = _bucket(t, start_ns)
                    if k is None:
                        continue
                    b = out[svc][k]
                    b[0] += 1
                    if sp.get("status", {}).get("code") == STATUS_ERROR:
                        b[1] += 1
                    b[2].append(int(sp.get("endTimeUnixNano", t)) - t)
    return out


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else NAN


def baro_table(case: Case) -> dict:
    """{"columns": ["time", "<servis>_<metrik>", ...], "rows": [[time, değer, ...] × 120]}; eksik değer NaN."""
    alarm_s = case.alarm_ns // 10**9
    start_s = alarm_s - HALF_S
    start_ns, end_ns = start_s * 10**9, (start_s + N_BUCKETS * BUCKET_S) * 10**9
    series: dict[tuple[str, str], list[float]] = {}
    for (c, metric), pts in _container_points(sorted(case.view.glob("metrics*.jsonl")), start_ns, end_ns).items():
        per = [[] for _ in range(N_BUCKETS)]
        ordered = sorted(pts.items())
        if metric == "mem":
            for t, v in ordered:
                k = _bucket(t, start_ns)
                if k is not None:
                    per[k].append(v)
        else:
            for (t1, v1), (t2, v2) in zip(ordered, ordered[1:]):
                k = _bucket(t2, start_ns)
                if k is None or v2 < v1 or t2 <= t1:
                    continue
                if metric == "cpu":  # trial_summary ile aynı hesap: birikimli ns farkı / ns × 100
                    per[k].append((v2 - v1) / (t2 - t1) * 100)
                else:  # bayt/sn
                    per[k].append((v2 - v1) / ((t2 - t1) / 1e9))
        if any(per):
            series[(c, metric)] = [_mean(xs) for xs in per]
    for svc, buckets in _span_buckets(sorted(case.view.glob("traces*.jsonl")), start_ns).items():
        series[(svc, "latency")] = [pct(d, 0.90) if d else NAN for _, _, d in buckets]
        series[(svc, "requests")] = [float(n) for n, _, _ in buckets]
        series[(svc, "errors")] = [float(e) for _, e, _ in buckets]
    keys = sorted(series, key=lambda k: (k[0], METRICS.index(k[1])))
    columns = ["time"] + [f"{s}_{m}" for s, m in keys]
    rows = [[float(start_s + i * BUCKET_S)] + [series[k][i] for k in keys] for i in range(N_BUCKETS)]
    return {"columns": columns, "rows": rows}

