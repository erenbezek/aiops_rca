"""C2 ölçümü: bir koşunun telemetri penceresinden (raw ve filtered ayrı) kartın ölçümlerini çıkarır.

C2 kartı (HANDOFF 2026-10-23 "Planlama → Uygulama (collector C2)", madde 4; 2026-10-24 "Uygulama → Uygulama (C2,
ölçmeden önce)"). Model çalışmaz.

Kullanım: python tools/c2_measure.py <koşu klasörü>...   (tools/scenario_runner.py çıktısı: run.json, window/)
Sonuç `measure.json` (koşu klasörüne) ve kısa özet; kural testi için aday kayıtlar `samples/` altına.

Pencere: normal = flag açılmadan önceki 10 dk, flag = sonraki 10 dk (alarm = flag yazma zamanı; trial_summary.py
ile aynı hesap: istek, hata oranı, p95, CPU sayaçtan, bellek ortalaması, WARN+ loglar) + p99.

1. Sızıntı (aiops_rca.leakage, CLI'ın kullandığı fonksiyon; bulgu var = çıkış 1):
   - raw'da senaryoya özgü bulgu: flag penceresinde, senaryonun beklenen yolundaki serviste (`EXPECTED_PATH`) bir
     CLI bulgusu: `flag_name` kuralıyla senaryonun flag adı ya da bulgunun metninde senaryonun `PHRASES` ifadesi.
     Yolu flagd olmayan senaryolarda flagd bulgusu sayılmaz. loadGeneratorFloodHomepage: load-generator kaydında
     bulgu ve aynı satırda flood ifadesi. Ölçüt flag penceresinde ≥ 1; normal pencere ve servis kırılımı kayda;
     senaryonun flag adı beklenmeyen bir serviste çıkarsa kayda. Bütün flag'lerin `flag_name` bulguları servis
     ve pencereye göre kayda (flag'ler kapalıyken de değerlendirilir: 13 flag'in yolu).
   - filtered: bulgu 0 (`clean`).
2. Belirti: kök neden servisinde sinyal başına güç (HANDOFF 2026-10-24): T = eşiğin iki koşulunun büyüğü;
   güç = (sonra − önce) / (T − önce); istek düşüşünde (önce − sonra) / (önce − T). Eşikler (zor deneme, Eren
   2026-10-21) + p99: hata oranı +0,05; p95 ve p99 ×1,5 ve +20 ms; CPU ortalaması ×1,5 ve +5 puan; bellek ×1,2;
   yeni WARN+ log (normalde 0, flag'de ≥ 5; güç = en sık yeni mesajın sayısı / 5); istek düşüşü önce ≥ 20 iken ×0,5.
   Değeri olmayan sinyal yok sayılır ve kayda. Senaryonun gücü = en büyük güç, karar o sinyale göre: < 0,8
   belirtisiz, 0,8 ≤ güç < 1,2 sınırda, ≥ 1,2 belirtili. Kök neden servisinde CPU ya da bellek iki pencerede de
   değersizse karar "ölçülemedi". raw ve filtered kararı farklıysa `verdicts_differ` (sinyal bazında incelenir).
3. Yeniden yazımlar: orijinal ve yeni metinlerin raw ve filtered'daki sayısı (bütün sinyaller).
4. Basit kural (filtered): aynı sinyaller ve eşikler bütün servislere; puan = eşiği aşan (güç ≥ 1) sinyal sayısı,
   eşitlikte en büyük güç; ilk 3 servis. astronomy-db ve valkey-cart sadece CPU/bellek; izleme araçları yok.
5. Collector (filtered metrikler; pencere normal başı – flag yazılışı + 10 dk sonu, yani flag kapanışı):
   - 6 dosya çıkışımızın (`FILE_EXPORTERS`) her biri için `otelcol_exporter_sent_*` serisi var ve artış > 0;
     `send_failed` ve `enqueue_failed` artışı 0 (seri yoksa 0).
   - `otelcol_receiver_refused_*` serisi var, artışı 0.
   - Diğer exporter'lar (opensearch, otlp_grpc/jaeger, otlp_http/prometheus, span_metrics, debug) sadece kayda:
     sent ve failed artışı birlikte. `otelcol_processor_refused_*` (yoksa) kayda.
   - Artış = pencere sonundaki son değer − pencere başından önceki son değer; pencere başından önce noktası
     olmayan seri 0'dan başlamış sayılır (pencerede doğan seri bütün değeriyle artıştır).
   Bütün `otelcol` metrik adları listelenir. En yüksek bellek koşucunun kaydından.
Çıkış kodu: 0 yazıldı, 2 kullanım/girdi hatası.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aiops_rca.leakage import FLAGS, LeakageInputError, scan_model_view  # noqa: E402
from trial_summary import TOOLING_CONTAINERS, CPU_METRIC, MEMORY_METRIC, Window, summarize  # noqa: E402

ROUTINE_SERVICES = frozenset({"flagd", "flagd-ui", "load-generator"})
DB_SERVICES = frozenset({"astronomy-db", "valkey-cart"})
# Senaryonun beklenen yolu (planlama, Eren onaylı 2026-10-24; OTEL_DEMO sızıntı tablosu): ad, email ve payment
# flag değerlendirme olayı yaymıyor, bu dört senaryonun izi sadece flagd'de.
EXPECTED_PATH = {
    "adManualGc": {"ad"},
    "cartFailure": {"cart"},
    "paymentUnreachable": {"checkout"},
    "productCatalogFailure": {"product-catalog"},
    "productCatalogLockContention": {"product-catalog"},
    "recommendationCacheFailure": {"recommendation"},
    "intlShippingSlowdown": {"shipping"},
    "adFailure": {"flagd"},
    "adHighCpu": {"flagd"},
    "emailMemoryLeak": {"flagd"},
    "paymentFailure": {"flagd"},
    "loadGeneratorFloodHomepage": {"load-generator"},
}
PHRASES = {
    "adManualGc": ["adManualGc enabled"],
    "productCatalogFailure": ["Product Catalog Fail Feature Flag Enabled"],
    "productCatalogLockContention": ["lock contention scenario"],
    "intlShippingSlowdown": ["intlShippingSlowdown feature flag"],
    "recommendationCacheFailure": ["demo.feature_flag.recommendation_cache"],
}
FLOOD_PHRASES = ("user_flood_home", "demo.request.flood.count", "flooding homepage")
FLAG_BY_NORM = {re.sub(r"[_\-]", "", f).lower(): f for f in FLAGS}
# (ad, orijinal, yeni, ilgili flag) — otelcol-config-extras.yml transform/scrub
REWRITES = [
    ("product_catalog_error", "Product Catalog Fail Feature Flag Enabled", "failed to load product from catalog",
     "productCatalogFailure"),
    ("ad_manual_gc", "Feature Flag adManualGc enabled, performing a manual gc now",
     "Performing a full garbage collection now", "adManualGc"),
    ("lock_holding", "lock contention scenario active: holding ACCESS EXCLUSIVE lock on catalog.products",
     "holding ACCESS EXCLUSIVE lock on catalog.products", "productCatalogLockContention"),
    ("lock_failed", "failed to acquire lock for lock contention scenario",
     "failed to acquire ACCESS EXCLUSIVE lock on catalog.products", "productCatalogLockContention"),
    ("shipping_delay", "Delaying international shipment due to intlShippingSlowdown feature flag",
     "Delaying international shipment", "intlShippingSlowdown"),
]
FILE_EXPORTERS = ("file/traces", "file/metrics", "file/logs", "file/raw_traces", "file/raw_metrics", "file/raw_logs")
SENT = re.compile(r"^otelcol[._]exporter[._]sent[._]")
SEND_FAILED = re.compile(r"^otelcol[._]exporter[._]send[._]failed[._]")
ENQUEUE_FAILED = re.compile(r"^otelcol[._]exporter[._]enqueue[._]failed[._]")
RECEIVER_REFUSED = re.compile(r"^otelcol[._]receiver[._]refused[._]")
PROCESSOR_REFUSED = re.compile(r"^otelcol[._]processor[._].*refused[._]")
SAMPLES_PER_KEY = 2
TS = re.compile(r'"(?:startTimeUnixNano|timeUnixNano|observedTimeUnixNano)":"(\d+)"')
PATH_TOKEN = re.compile(r'\.?([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\[("(?:[^"\\]|\\.)*")\]')


def ns(iso_z: str) -> int:
    return int(datetime.fromisoformat(iso_z.replace("Z", "+00:00")).timestamp()) * 10**9


# --- 2. belirti ---------------------------------------------------------------------------------------------

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


def verdict(sig: dict[str, dict], row: dict) -> dict:
    no_cpu = row.get("cpu_pct_before") is None and row.get("cpu_pct_after") is None
    no_mem = row.get("mem_mb_before") is None and row.get("mem_mb_after") is None
    if no_cpu or no_mem or not sig:
        top = max(sig.items(), key=lambda kv: kv[1]["strength"]) if sig else (None, {"strength": None})
        return {"verdict": "not_measurable", "strength": top[1]["strength"], "deciding_signal": top[0],
                "not_measurable_because": [n for n, miss in (("cpu_pct", no_cpu), ("mem_mb", no_mem)) if miss]}
    name, top = max(sig.items(), key=lambda kv: kv[1]["strength"])
    return {"verdict": classify(top["strength"]), "strength": top["strength"], "deciding_signal": name}


def symptoms(base: Path, flag_on_ns: int, root: str | None) -> tuple[dict, dict]:
    paths = sorted(base.glob("*.jsonl"))
    result, edges = summarize(paths, Window(flag_on_ns))
    missing = [f"{sig} {end}" for sig, (first, last) in edges.items()
               for end, ok in (("start", first), ("end", last)) if not ok]
    rows = service_rows(result)
    out = {"window_missing": missing}
    if root is not None:
        row = rows.get(root, {})
        sig, no_value = signals(row, root in DB_SERVICES)
        out.update({"service": root, "row_found": root in rows, **verdict(sig, row),
                    "signals": sig, "signals_without_value": no_value})
    return out, rows


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


# --- 1. sızıntı ---------------------------------------------------------------------------------------------

def norm(text: str) -> str:
    return re.sub(r"[_\-]", "", text).lower()


def resolve_path(doc, path: str):
    node = doc
    for name, index, quoted in PATH_TOKEN.findall(path):
        key = name or (json.loads(quoted) if quoted else None)
        try:
            node = node[int(index)] if index else node[key]
        except (KeyError, IndexError, TypeError):
            return None
    return node


def minimize(doc: dict, path: str) -> dict | None:
    """Bulgunun kaydını tek kayıtlık bir OTLP isteğine indirger (kaynak, kapsam, tek span/log/metrik)."""
    flat = [int(i) if i else (n or json.loads(q)) for n, i, q in PATH_TOKEN.findall(path)]
    if len(flat) < 2 or flat[0] not in ("resourceSpans", "resourceLogs", "resourceMetrics"):
        return None
    top, scope_key = flat[0], flat[0].replace("resource", "scope")
    item_key = {"resourceSpans": "spans", "resourceLogs": "logRecords", "resourceMetrics": "metrics"}[top]
    res = doc[top][flat[1]]
    j = flat[3] if len(flat) > 3 and flat[2] == scope_key else 0
    scopes = res.get(scope_key) or [{}]
    scope = scopes[j] if j < len(scopes) else scopes[0]
    k = flat[5] if len(flat) > 5 and flat[2] == scope_key and flat[4] == item_key else 0
    items = scope.get(item_key) or []
    if not items:
        return None
    item = json.loads(json.dumps(items[k] if k < len(items) else items[0]))
    if item_key == "metrics":  # tek veri noktası
        for mtype in ("sum", "gauge", "histogram", "exponentialHistogram", "summary"):
            dps = item.get(mtype, {}).get("dataPoints")
            if dps:
                n = flat[8] if len(flat) > 8 and flat[6] == mtype and flat[7] == "dataPoints" else 0
                item[mtype]["dataPoints"] = [dps[n] if n < len(dps) else dps[0]]
    out_scope = {key: v for key, v in scope.items() if key != item_key}
    out_scope[item_key] = [item]
    out_res = {key: v for key, v in res.items() if key != scope_key}
    out_res[scope_key] = [out_scope]
    return {top: [out_res]}


def leakage(window: Path, flag: str, flag_on: int, flag_off: int, samples_dir: Path) -> dict:
    out = {}
    expected = EXPECTED_PATH[flag]
    for base in ("raw", "filtered"):
        try:
            findings = scan_model_view(window / base)
        except LeakageInputError as e:
            out[base] = {"error": str(e)}
            continue
        by_key = Counter((f.signal, f.rule, f.service or "-", f.match.lower()) for f in findings)
        out[base] = {"findings": len(findings), "cli_exit": 1 if findings else 0,
                     "by_signal_rule_service_match": [[*k, n] for k, n in by_key.most_common(40)]}
        if base == "filtered":
            continue
        specific = Counter()  # (pencere, servis) → senaryoya özgü bulgu
        own_flag = Counter()  # senaryonun flag adı, (pencere, servis); beklenmeyen servis görülsün
        all_flags = Counter()  # bütün flag_name bulguları (flag, servis, pencere)
        examples = []
        samples = defaultdict(list)
        kept = Counter()
        by_line = defaultdict(list)
        for f in findings:
            if f.line is not None:
                by_line[f.file].append(f)
        for file, items in by_line.items():
            wanted = defaultdict(list)
            for f in items:
                wanted[f.line].append(f)
            path = window / base / Path(file).relative_to(Path(file).parts[0])
            with path.open(encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if n not in wanted:
                        continue
                    doc = json.loads(line)
                    times = [int(t) for t in TS.findall(line)]
                    t = max(times) if times else 0
                    side = "flag" if flag_on <= t <= flag_off else ("normal" if t < flag_on else "other")
                    lower_line = line.lower()
                    for f in wanted[n]:
                        svc = f.service or "-"
                        text = resolve_path(doc, f.json_path) if f.json_path else None
                        text = text if isinstance(text, str) else ""
                        is_own_flag = f.rule == "flag_name" and norm(f.match) == norm(flag)
                        if f.rule == "flag_name":
                            all_flags[(FLAG_BY_NORM.get(norm(f.match), f.match), svc, side)] += 1
                        if is_own_flag:
                            own_flag[(side, svc)] += 1
                        if flag == "loadGeneratorFloodHomepage":
                            hit = svc == "load-generator" and any(p in lower_line for p in FLOOD_PHRASES)
                        else:
                            hit = svc in expected and (
                                is_own_flag or any(p.lower() in text.lower() for p in PHRASES.get(flag, [])))
                        key = (f.signal, f.rule, svc, f.match.lower())
                        if hit:
                            specific[(side, svc)] += 1
                            if len(examples) < 5:
                                examples.append({"side": side, "signal": f.signal, "service": svc,
                                                 "rule": f.rule, "match": f.match, "text": text[:200]})
                        if kept[(key, hit)] < SAMPLES_PER_KEY:
                            small = minimize(doc, f.json_path) if f.json_path else None
                            if small:
                                kept[(key, hit)] += 1
                                samples[f.signal].append((small, [*key, "specific" if hit else "routine", side]))
        out[base]["scenario_specific"] = {
            "expected_path": sorted(expected),
            "flag": sum(n for (side, _), n in specific.items() if side == "flag"),
            "normal": sum(n for (side, _), n in specific.items() if side == "normal"),
            "by_window_service": [[side, svc, n] for (side, svc), n in sorted(specific.items())],
            "examples": examples,
        }
        out[base]["own_flag_name"] = {
            "by_window_service": [[side, svc, n] for (side, svc), n in sorted(own_flag.items())],
            "unexpected_services": sorted({svc for (_, svc) in own_flag if svc not in expected}),
        }
        out[base]["flag_name_by_flag_service_window"] = [[*k, n] for k, n in sorted(all_flags.items())]
        samples_dir.mkdir(exist_ok=True)
        with (samples_dir / "index.tsv").open("w") as idx:
            for signal, entries in sorted(samples.items()):
                with (samples_dir / f"{signal}.jsonl").open("w") as fh:
                    for n, (small, meta) in enumerate(entries, 1):
                        fh.write(json.dumps(small, ensure_ascii=False, separators=(",", ":")) + "\n")
                        idx.write("\t".join([f"{signal}.jsonl:{n}", *map(str, meta)]) + "\n")
    return out


# --- 3. yeniden yazımlar, 5. collector ----------------------------------------------------------------------

def rewrites(window: Path) -> dict:
    counts = {name: {"flag": flag, "original": old, "new": new} for name, old, new, flag in REWRITES}
    for base in ("raw", "filtered"):
        n = {name: [0, 0] for name, *_ in REWRITES}
        for path in sorted((window / base).glob("*.jsonl")):
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    for name, old, new, _ in REWRITES:
                        o = line.count(old)
                        # yeni metin orijinalin içinde de geçiyorsa (shipping, kilit) orijinaller düşülür
                        n[name][0] += o
                        n[name][1] += line.count(new) - (o if new in old else 0)
        for name, (o, nw) in n.items():
            counts[name][base] = {"original": o, "new": nw}
    return counts


def increase(points: list[tuple[int, float]], lo: int, hi: int) -> float:
    """Pencere sonundaki son değer − pencere başından önceki son değer (yoksa 0; planlama 2026-10-24)."""
    before = [v for t, v in points if t < lo]
    upto = [v for t, v in points if t <= hi]
    start = before[-1] if before else 0.0
    end = upto[-1] if upto else start
    return end - start


def read_otelcol(metrics_file: Path) -> tuple[dict, set]:
    series = defaultdict(list)  # (ad, kaynak, öznitelikler) -> [(zaman, değer)]
    names = set()
    with metrics_file.open(encoding="utf-8") as fh:
        for line in fh:
            if "otelcol" not in line:
                continue
            doc = json.loads(line)
            for rm in doc.get("resourceMetrics", []):
                res = json.dumps(sorted((a["key"], a["value"]) for a in rm.get("resource", {}).get("attributes", [])))
                for sm in rm.get("scopeMetrics", []):
                    for m in sm.get("metrics", []):
                        name = m.get("name", "")
                        if not name.startswith("otelcol"):
                            continue
                        names.add(name)
                        for mtype in ("sum", "gauge"):
                            for dp in m.get(mtype, {}).get("dataPoints", []):
                                v = dp.get("asDouble", dp.get("asInt"))
                                if v is None:
                                    continue
                                attrs = {a["key"]: next(iter(a["value"].values()), None)
                                         for a in dp.get("attributes", [])}
                                series[(name, res, json.dumps(sorted(attrs.items())))].append(
                                    (int(dp.get("timeUnixNano", 0)), float(v)))
    return {k: sorted(v) for k, v in series.items()}, names


def collector_counters(series: dict, lo: int, hi: int) -> dict:
    exporters = defaultdict(lambda: {"sent_series": 0, "sent": 0.0, "send_failed": 0.0, "enqueue_failed": 0.0})
    receiver = {"series": 0, "increase": 0.0, "by_component": Counter()}
    processor = {"series": 0, "names": set(), "increase": 0.0}
    for (name, _, attrs), pts in series.items():
        a = dict(json.loads(attrs))
        inc = increase(pts, lo, hi)
        if SENT.match(name):
            e = exporters[a.get("exporter", "-")]
            e["sent_series"] += 1
            e["sent"] += inc
        elif SEND_FAILED.match(name):
            exporters[a.get("exporter", "-")]["send_failed"] += inc
        elif ENQUEUE_FAILED.match(name):
            exporters[a.get("exporter", "-")]["enqueue_failed"] += inc
        elif RECEIVER_REFUSED.match(name):
            receiver["series"] += 1
            receiver["increase"] += inc
            receiver["by_component"][f"{name} {a.get('receiver', '-')}"] += inc
        elif PROCESSOR_REFUSED.match(name):
            processor["series"] += 1
            processor["names"].add(name)
            processor["increase"] += inc
    files = {}
    for e in FILE_EXPORTERS:
        x = exporters.get(e, {"sent_series": 0, "sent": 0.0, "send_failed": 0.0, "enqueue_failed": 0.0})
        files[e] = {**x, "pass": x["sent_series"] > 0 and x["sent"] > 0 and x["send_failed"] == 0
                    and x["enqueue_failed"] == 0}
    others = {e: dict(x) for e, x in sorted(exporters.items()) if e not in FILE_EXPORTERS}
    receiver_pass = receiver["series"] > 0 and receiver["increase"] == 0
    return {
        "pass": all(f["pass"] for f in files.values()) and receiver_pass,
        "file_exporters": files,
        "receiver_refused": {**receiver, "by_component": dict(sorted(receiver["by_component"].items())),
                             "pass": receiver_pass},
        "other_exporters_record_only": others,
        "processor_refused_record_only": {**processor, "names": sorted(processor["names"])},
    }


# --- ana --------------------------------------------------------------------------------------------------

def measure(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if not run.get("valid"):
        raise ValueError(f"run not valid: {run.get('invalid_reasons')}")
    t = run["times_utc"]
    flag_on, flag_off, normal = ns(t["flag_on_write"]), ns(t["flag_off_write"]), ns(t["normal_start"])
    window = run_dir / "window"
    root = run["root_cause_service"]
    result = {"scenario": run["scenario"], "attempt": run["attempt"], "root_cause_service": root}

    result["leakage"] = leakage(window, run["flag"], flag_on, flag_off, run_dir / "samples")
    raw_l, filt_l = result["leakage"]["raw"], result["leakage"]["filtered"]
    raw_specific = raw_l.get("scenario_specific", {}).get("flag", 0)
    result["positive_control"] = {
        "raw_specific_in_flag_window": raw_specific,
        "filtered_clean": filt_l.get("findings") == 0,
        "pass": raw_specific >= 1 and filt_l.get("findings") == 0,
    }
    if root is not None:
        sym_raw, _ = symptoms(window / "raw", flag_on, root)
        sym_filt, rows = symptoms(window / "filtered", flag_on, root)
        result["symptoms"] = {"raw": sym_raw, "filtered": sym_filt,
                              "verdicts_differ": sym_raw.get("verdict") != sym_filt.get("verdict")}
        result["rule_check"] = rule_check(rows, root)
    result["rewrites"] = rewrites(window)
    series, names = read_otelcol(window / "filtered" / "metrics.jsonl")
    result["collector"] = {"peak_mem_mib": run.get("collector_mem_peak_mib"),
                           "restarted_before_normal": run.get("collector_restarted_before_normal"),
                           **collector_counters(series, normal, flag_off), "otelcol_metric_names": sorted(names)}
    return result


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    for arg in argv:
        run_dir = Path(arg).expanduser()
        try:
            result = measure(run_dir)
        except (OSError, ValueError, KeyError) as e:
            print(f"error: {run_dir}: {e}", file=sys.stderr)
            return 2
        (run_dir / "measure.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
        pc, col = result["positive_control"], result["collector"]
        print(f"{result['scenario']}_{result['attempt']}:")
        print(f"  positive_control {'PASS' if pc['pass'] else 'FAIL'}: raw specific (flag window) "
              f"{pc['raw_specific_in_flag_window']}, filtered clean {pc['filtered_clean']}")
        if "symptoms" in result:
            for base in ("raw", "filtered"):
                s = result["symptoms"][base]
                print(f"  symptom {base:8} {s['verdict']:14} strength {s['strength']} ({s['deciding_signal']})"
                      + (f" MISSING {s['window_missing']}" if s["window_missing"] else ""))
            rc = result["rule_check"]
            print(f"  rule top3 {[x['service'] for x in rc['top3']]} top1 {rc['top1_hit']} top3 {rc['top3_hit']}")
        for name, r in result["rewrites"].items():
            if r["raw"]["original"] or r["raw"]["new"] or r["filtered"]["original"] or r["filtered"]["new"]:
                print(f"  rewrite {name}: raw {r['raw']} filtered {r['filtered']}")
        print(f"  collector {'PASS' if col['pass'] else 'FAIL'}: peak {col['peak_mem_mib']} MiB; receiver_refused "
              f"series={col['receiver_refused']['series']} +{col['receiver_refused']['increase']}")
        for e, x in col["file_exporters"].items():
            print(f"    {e:17} {'ok ' if x['pass'] else 'FAIL'} sent_series={x['sent_series']} +{x['sent']:.0f} "
                  f"send_failed +{x['send_failed']:.0f} enqueue_failed +{x['enqueue_failed']:.0f}")
        for e, x in col["other_exporters_record_only"].items():
            print(f"    {e:17} (record) sent +{x['sent']:.0f} send_failed +{x['send_failed']:.0f} "
                  f"enqueue_failed +{x['enqueue_failed']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
