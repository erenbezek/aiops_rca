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

Port (`baro_rank`), RCAEval 1.9.0 `main.py` + `e2e/baro.py` + `io/time_series.py` ile aynı adımlar:
1. `main.py` ön adımları, 120 satırlık tabloda: sonsuz → NaN, `ffill` (sütun başına yukarıdan aşağı), `fillna(0)`.
   `baro`'ya NaN gitmez.
2. `baro`: normal `time < alarm`, anomali `time ≥ alarm`. Her dönemde ayrı `preprocess(dataset="re2-ob")`: `drop_time`
   (`time` sütunu), `drop_constant` (bütün değerleri ilk değere eşit sütun), `convert_mem_mb` (`_mem` / 1e6).
   Ortak sütunlar, normal dönemin sırasıyla.
3. Sütun başına sklearn `RobustScaler` normal dönemde: merkez = medyan, ölçek = 75. − 25. yüzdelik (numpy doğrusal yöntemi,
   `_lerp` ile aynı formül); ölçek < 10·eps ise 1. z = (anomali − merkez) / ölçek; puan = Python `max(z)`.
4. `sorted(..., key=puan, reverse=True)` (kararlı). Döner: [(sütun, puan), ...].
"""
from __future__ import annotations

import json
import math
import sys
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


# --- port ----------------------------------------------------------------------------------------------------

EPS = sys.float_info.epsilon  # np.finfo(float64).eps


def _fill(rows: list[list[float]]) -> list[list[float]]:
    """`main.py`: sonsuz → NaN, `ffill`, `fillna(0)`."""
    out, last = [], [math.nan] * (len(rows[0]) if rows else 0)
    for r in rows:
        new = []
        for j, v in enumerate(r):
            v = math.nan if math.isinf(v) else v
            if math.isnan(v):
                v = last[j]
            last[j] = v
            new.append(v)
        out.append(new)
    return [[0.0 if math.isnan(v) else v for v in r] for r in out]


def _preprocess(columns: list[str], rows: list[list[float]]) -> dict[str, list[float]]:
    """`preprocess(dataset="re2-ob", dk_select_useful=False)` = convert_mem_mb(drop_constant(drop_time(df)))."""
    cols = {c: [r[j] for r in rows] for j, c in enumerate(columns) if c != "time"}
    kept = {c: v for c, v in cols.items() if any(x != v[0] for x in v)}  # (df != df.iloc[0]).any()
    return {c: ([x / 1e6 for x in v] if c.endswith("_mem") else v) for c, v in kept.items()}


def _lerp(a: float, b: float, t: float) -> float:
    """numpy `_lerp`: a + (b − a)·t; t ≥ 0,5 ise b − (b − a)·(1 − t)."""
    d = b - a
    return b - d * (1 - t) if t >= 0.5 else a + d * t


def _percentile(sorted_values: list[float], q: float) -> float:
    """numpy `percentile(..., method="linear")`, NaN'sız sıralı değerlerde."""
    n = len(sorted_values)
    virtual = n * (q / 100) + (1 + (q / 100) * (1 - 1 - 1)) - 1  # _compute_virtual_index(n, q, alpha=1, beta=1)
    lo = math.floor(virtual)
    g = virtual - lo
    lo = min(max(lo, 0), n - 1)
    hi = min(lo + 1, n - 1)
    return _lerp(sorted_values[lo], sorted_values[hi], g)


def _median(sorted_values: list[float]) -> float:
    n = len(sorted_values)
    m = n // 2
    return sorted_values[m] if n % 2 else (sorted_values[m - 1] + sorted_values[m]) / 2


def baro_rank(table: dict, alarm_s: int) -> list[tuple[str, float]]:
    """RCAEval `main.py` ön adımları + `baro(data, inject_time=alarm_s, dataset="re2-ob", dk_select_useful=False)`."""
    columns, rows = table["columns"], _fill(table["rows"])
    t = columns.index("time")
    normal = _preprocess(columns, [r for r in rows if r[t] < alarm_s])
    anomal = _preprocess(columns, [r for r in rows if r[t] >= alarm_s])
    ranks = []
    for col in [c for c in normal if c in anomal]:
        a = sorted(normal[col])
        center = _median(a)
        scale = _percentile(a, 75) - _percentile(a, 25)
        if scale < 10 * EPS:
            scale = 1.0
        z = [(x - center) / scale for x in anomal[col]]
        ranks.append((col, max(z)))
    return sorted(ranks, key=lambda x: x[1], reverse=True)
