"""Depolama kartı ölçümleri: canlı izleme sisteminin (Jaeger, Prometheus, OpenSearch) kaybı, büyümesi ve belleği.

Depolama kartı (HANDOFF 2026-10-25 "Planlama → Uygulama (depolama kartı)"), D1; D2'de aynı izleme tekrar koşar.

Kullanım:
  python tools/storage_check.py watch [--minutes 60] [--keep-up]
      gnome-session-inhibit ve systemd-inhibit altında kendini yeniden çalıştırır (koşucunun engelleri).
      Korumalar (tools/scenario_runner.py guards) → `otel_demo.sh up` (süzülmemiş çıkış kapalı) → 22 konteyner
      (6 dk içinde olmazsa collector yeniden başlatılır, 4 dk daha) → 5 dk ısınma → izleme penceresi → 90 sn
      bekleme (collector'ın kendi metrikleri dosyaya düşsün) → sayaçlar → `down` (`--keep-up` ile açık kalır).

İzleme penceresinde (çıktı `~/cerebrum2/storage_runs/<UTC zaman>-watch/`, repo dışı):
  - Dakikada bir: jaeger, prometheus, opensearch, otel-collector belleği (`docker stats`) → `mem.tsv`.
  - 5 dk'da bir: veri klasörlerinin disk kullanımı (konteyner içinde `du -sk`) → `sizes.tsv`; OpenSearch heap;
    collector logunun son 5 dk'sı (`docker logs --since`; Docker logu 5 MB × 2 ile döndüğü için parça parça).
  - Başta ve sonda: OpenSearch node stats (`_nodes/stats`) ve indeksler (`_cat/indices`) → `opensearch_start.json`,
    `opensearch_end.json`; bütün konteynerlerin yeniden başlama / OOM durumu.
  - Sonda: collector sayaçları süzülmüş metrik dosyalarından (`telemetry/filtered/metrics*.jsonl`): exporter başına
    sent, send_failed, enqueue_failed artışı (c2_measure.increase: pencere sonundaki son değer − pencere başından
    önceki son değer; seri yoksa 0).
Sonuç `watch.json` ve kısa özet. Collector logundan opensearch'le ilgili satırlar `collector_errors.json`'da:
OpenSearch'ün `reason` metinleri olduğu gibi ve sayıları; mesaj grupları (sayılar `#`) sayı ve ilk tam satırla.
Sonda `_refresh` (saymadan önce) ve `otel-logs-*` indekslerinin eşlemesi `opensearch_mapping.json`'a.
Saatlik büyüme = (son boyut − ilk boyut) / pencere saati, ondalık GB.

  python tools/storage_check.py compare --run <watch klasörü> [--tag <ad>]
      Canlı = dosya (D2 ölçütü): aralık `watch.json`'daki pencerenin kenarlarından 2 dk içeride; aralık sonundan en
      az 2 dk geçmeden sorgulamaz. Demo açık olmalı (`watch --keep-up`). Sonuç `compare.json` (`--tag x` ile
      `compare_x.json`).
      - İzler: `telemetry/filtered/traces*.jsonl`'daki span'ler (başlangıcı aralıkta) servis başına; Jaeger v3 API
        (`raw_traces`, 8080 üzerinden) servis × 1 dk dilim, dilim `search_depth`'e takılırsa ikiye bölünür; span'ler
        (traceId, spanId) ile tekilleştirilir, başlangıcı aralıkta olanlar servis başına sayılır.
      - Loglar: `logs*.jsonl`'daki kayıtlar (zaman `timeUnixNano`, 0 ise `observedTimeUnixNano`; ms) servis başına;
        OpenSearch `_refresh` sonrası `otel-logs-*`'ta `@timestamp` aralıkta, servis başına.
      - Metrikler (`METRICS`: gauge, sum, histogram sayısı): dosyadaki veri noktaları (zaman ms, değer) çoklu kümesi;
        Prometheus'ta aynı aralığın ham örnekleri (`ad[<süre>ms]`), bütün seriler.
      - Dosya kapsaması: her sinyalde dosyalardaki en eski kayıt aralık başından önce olmalı (döndürme).

Çıkış kodu (watch): 0 ölçüm tamam, 1 koruma tutmadı / demo açılmadı / makine uyudu, 2 kullanım hatası.
Çıkış kodu (compare): 0 üç sistemde de eşit (ve dosyada kayıt var), 1 fark var, boş ya da kapsama eksik,
2 kullanım hatası.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scenario_runner as sr  # noqa: E402
from c2_measure import increase, read_otelcol, SENT, SEND_FAILED, ENQUEUE_FAILED  # noqa: E402

OUT = Path.home() / "cerebrum2" / "storage_runs"
OPENSEARCH = "http://127.0.0.1:9200"
WATCHED = ["jaeger", "prometheus", "opensearch", "otel-collector"]
# Konteyner → veri klasörü = isimli volume'ün bağlandığı yer (D2; D1'de Jaeger bellekteydi)
DATA_DIRS = {"prometheus": "/prometheus", "opensearch": "/usr/share/opensearch/data", "jaeger": "/tmp"}
WARMUP_S = 300
SIZE_EVERY_S = 300
SETTLE_S = 90
NODE_STATS = "/_nodes/stats/thread_pool,indices,jvm,breaker,indexing_pressure"


def mem_mib() -> dict[str, float | None]:
    out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}", *WATCHED],
                         capture_output=True, text=True, timeout=60).stdout
    units = {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "KB": 1 / 1024, "MB": 1, "GB": 1024, "B": 1 / 2**20}
    result = {c: None for c in WATCHED}
    for line in out.splitlines():
        name, usage = line.split("\t")
        m = re.match(r"([\d.]+)\s*([KMG]?i?B)", usage)
        if m:
            result[name] = float(m.group(1)) * units[m.group(2)]
    return result


def disk_bytes(container: str, path: str) -> int | None:
    p = subprocess.run(["docker", "exec", container, "du", "-sk", path], capture_output=True, text=True, timeout=120)
    m = re.match(r"(\d+)", p.stdout)
    return int(m.group(1)) * 1024 if p.returncode == 0 and m else None


def sizes() -> dict[str, int | None]:
    return {c: disk_bytes(c, path) for c, path in DATA_DIRS.items()}


def opensearch_snapshot() -> dict:
    snap = {}
    for key, path in (("node_stats", NODE_STATS), ("indices", "/_cat/indices?format=json&bytes=b"),
                      ("health", "/_cluster/health")):
        try:
            snap[key] = sr.http("GET", OPENSEARCH + path, timeout=30)
        except OSError as e:
            snap[key] = {"error": str(e)}
    return snap


def os_numbers(snap: dict) -> dict:
    """Node stats'tan kayıp nedenine bakılan sayılar (tek düğüm)."""
    try:
        node = next(iter(snap["node_stats"]["nodes"].values()))
    except (KeyError, StopIteration, TypeError, AttributeError):
        return {}
    write = node.get("thread_pool", {}).get("write", {})
    idx = node.get("indices", {}).get("indexing", {})
    jvm = node.get("jvm", {}).get("mem", {})
    pressure = node.get("indexing_pressure", {}).get("memory", {}).get("total", {})
    gc = node.get("jvm", {}).get("gc", {}).get("collectors", {})
    return {
        "write_pool_rejected": write.get("rejected"), "write_pool_completed": write.get("completed"),
        "write_pool_queue": write.get("queue"), "write_pool_threads": write.get("threads"),
        "index_total": idx.get("index_total"), "index_failed": idx.get("index_failed"),
        "heap_used_pct": jvm.get("heap_used_percent"), "heap_max_bytes": jvm.get("heap_max_in_bytes"),
        "pressure_coordinating_rejections": pressure.get("coordinating_rejections"),
        "pressure_primary_rejections": pressure.get("primary_rejections"),
        "breakers_tripped": {k: v.get("tripped") for k, v in node.get("breakers", {}).items()},
        "gc": {k: {"count": v.get("collection_count"), "ms": v.get("collection_time_in_millis")}
               for k, v in gc.items()},
    }


def delta(a: dict, b: dict) -> dict:
    out = {}
    for k, v in b.items():
        if isinstance(v, dict):
            out[k] = delta(a.get(k) or {}, v)
        elif isinstance(v, (int, float)) and isinstance(a.get(k), (int, float)):
            out[k] = v - a[k]
    return out


NUM = re.compile(r"\d+")
TS_PREFIX = re.compile(r"^\S+\s+")
# OpenSearch hata gövdesindeki "reason" alanları (log satırında JSON iki kez kaçışlı: \"reason\":\"…\")
REASON = re.compile(r'reason\\*":\\*"(.*?)\\*"[,}]')
LEVELS = {"debug", "info", "warn", "error"}


def collector_log(since: str, until: str, errors: dict, reasons: Counter, levels: Counter) -> None:
    """Collector logunun [since, until) parçası: seviye sayıları, opensearch'le ilgili mesaj grupları (sayılar `#`;
    grup başına sayı ve ilk tam satır) ve OpenSearch'ün `reason` metinleri (olduğu gibi)."""
    p = subprocess.run(["docker", "logs", "--since", since, "--until", until, "otel-collector"],
                       capture_output=True, text=True, timeout=120)
    for line in (p.stdout + p.stderr).splitlines():
        parts = line.split("\t")
        levels[parts[1] if len(parts) > 1 and parts[1] in LEVELS else "other"] += 1
        if "opensearch" in line.lower():
            key = NUM.sub("#", TS_PREFIX.sub("", line))
            group = errors.setdefault(key, {"count": 0, "example": line})
            group["count"] += 1
            for r in REASON.findall(line):
                reasons[r] += 1


def counters(lo: int, hi: int) -> dict:
    series = {}
    for f in sorted((sr.TELEMETRY / "filtered").glob("metrics*.jsonl")):
        part, _ = read_otelcol(f)
        for k, pts in part.items():
            series.setdefault(k, []).extend(pts)
    exporters: dict[str, dict] = {}
    for (name, _, attrs), pts in series.items():
        exporter = dict(json.loads(attrs)).get("exporter")
        if exporter is None:
            continue
        kind = "sent" if SENT.match(name) else "send_failed" if SEND_FAILED.match(name) \
            else "enqueue_failed" if ENQUEUE_FAILED.match(name) else None
        if kind:
            e = exporters.setdefault(exporter, {"sent": 0.0, "send_failed": 0.0, "enqueue_failed": 0.0,
                                                "series": []})
            e[kind] += increase(sorted(pts), lo, hi)
            e["series"].append(name)
    for e in exporters.values():
        e["series"] = sorted(set(e["series"]))
        total = e["sent"] + e["send_failed"]
        e["failed_share"] = round(e["send_failed"] / total, 4) if total else None
    return dict(sorted(exporters.items()))


def wait_containers(log) -> tuple[int | None, bool]:
    def wait(seconds: int) -> int | None:
        end, n = time.monotonic() + seconds, None
        while time.monotonic() < end:
            n = sr.container_count()
            if n == sr.CONTAINERS:
                return n
            time.sleep(10)
        return n
    n = wait(sr.WAIT_CONTAINERS_S[0])
    if n == sr.CONTAINERS:
        return n, False
    log(f"container count {n}; restarting collector")
    subprocess.run(["docker", "restart", "otel-collector"], capture_output=True)
    return wait(sr.WAIT_CONTAINERS_S[1]), True


def watch(minutes: int, keep_up: bool) -> int:
    d = OUT / f"{time.strftime('%Y%m%dT%H%MZ', time.gmtime())}-watch"
    d.mkdir(parents=True)
    log_file = (d / "watch.log").open("a")

    def log(msg: str) -> None:
        line = f"{sr.iso(sr.utc_ns())} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    rec = {"minutes": minutes, "guards_before": sr.guards(), "times_utc": {}, "valid": False, "problems": []}
    save = lambda: (d / "watch.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")  # noqa: E731
    if rec["guards_before"]["problems"]:
        rec["problems"].append("guards: " + "; ".join(rec["guards_before"]["problems"]))
        save()
        log(rec["problems"][-1])
        return 1
    p = subprocess.run([str(sr.OTEL_DEMO), "up"], capture_output=True, text=True)
    log(f"otel_demo.sh up: exit {p.returncode}")
    if p.returncode != 0:
        rec["problems"].append("otel_demo.sh up failed")
        save()
        return 1
    n, restarted = wait_containers(log)
    rec["container_count"], rec["collector_restarted_before_window"] = n, restarted
    if n != sr.CONTAINERS:
        rec["problems"].append(f"container count {n}, want {sr.CONTAINERS}")
    log(f"containers {n}; warm-up {WARMUP_S} s")
    time.sleep(WARMUP_S)

    start_state = sr.containers()
    os_start = opensearch_snapshot()
    (d / "opensearch_start.json").write_text(json.dumps(os_start, indent=1) + "\n")
    size_start = sizes()
    sleep0 = sr.sleep_offset_s()
    lo = sr.utc_ns()
    rec["times_utc"]["window_start"] = sr.iso(lo)
    log(f"window start; sizes {size_start}")
    peak = {c: None for c in WATCHED}
    errors, reasons, levels = {}, Counter(), Counter()
    heap_max_pct, max_temp = None, None
    mem_f, size_f = (d / "mem.tsv").open("a"), (d / "sizes.tsv").open("a")
    size_f.write(f"{sr.iso(lo)}\t" + "\t".join(f"{k}={v}" for k, v in size_start.items()) + "\n")
    last_size, log_since = time.monotonic(), lo
    end = time.monotonic() + minutes * 60
    while time.monotonic() < end:
        m = mem_mib()
        now = sr.utc_ns()
        mem_f.write(f"{sr.iso(now)}\t" + "\t".join(f"{c}={m[c]:.1f}" if m[c] else f"{c}=-" for c in WATCHED) + "\n")
        mem_f.flush()
        for c, v in m.items():
            if v is not None:
                peak[c] = v if peak[c] is None else max(peak[c], v)
        t = sr.pkg_temp_c()
        max_temp = t if max_temp is None else max(max_temp, t or 0)
        if time.monotonic() - last_size >= SIZE_EVERY_S:
            last_size = time.monotonic()
            s = sizes()
            size_f.write(f"{sr.iso(now)}\t" + "\t".join(f"{k}={v}" for k, v in s.items()) + "\n")
            size_f.flush()
            pct = os_numbers(opensearch_snapshot()).get("heap_used_pct")
            if pct is not None:
                heap_max_pct = pct if heap_max_pct is None else max(heap_max_pct, pct)
            collector_log(str(log_since // 10**9), str(now // 10**9), errors, reasons, levels)
            log_since = now // 10**9 * 10**9
            log(f"mem {m}; sizes {s}; heap {pct}%")
        time.sleep(60)
    hi = sr.utc_ns()
    rec["times_utc"]["window_end"] = sr.iso(hi)
    collector_log(str(log_since // 10**9), str(hi // 10**9), errors, reasons, levels)
    rec["suspended_s"] = round(sr.sleep_offset_s() - sleep0, 1)
    if rec["suspended_s"] > sr.SUSPEND_MAX_S:
        rec["problems"].append(f"machine slept {rec['suspended_s']} s in window")
    size_end = sizes()
    size_f.write(f"{sr.iso(hi)}\t" + "\t".join(f"{k}={v}" for k, v in size_end.items()) + "\n")
    # Sorgulanmayan indeks yenilenmiyor (search idle; D1: _cat/indices 1.038 kayıt gösterdi): saymadan önce _refresh.
    try:
        sr.http("POST", OPENSEARCH + "/_refresh", timeout=60)
        (d / "opensearch_mapping.json").write_text(
            json.dumps(sr.http("GET", OPENSEARCH + "/otel-logs-*/_mapping", timeout=60), indent=1) + "\n")
    except OSError as e:
        rec["problems"].append(f"opensearch refresh/mapping: {e}")
    os_end = opensearch_snapshot()
    (d / "opensearch_end.json").write_text(json.dumps(os_end, indent=1) + "\n")
    end_state = sr.containers()
    unexpected, _ = sr.split_restarts(start_state, end_state, set())
    hours = (hi - lo) / 3.6e12
    rec["sizes_bytes"] = {"start": size_start, "end": size_end}
    rec["growth_gb_per_hour"] = {c: round((size_end[c] - size_start[c]) / 1e9 / hours, 3)
                                 if size_end[c] is not None and size_start[c] is not None else None
                                 for c in DATA_DIRS}
    rec["mem_peak_mib"] = {c: round(v, 1) if v else None for c, v in peak.items()}
    rec["opensearch_heap_max_pct"] = heap_max_pct
    rec["max_pkg_temp_c"] = max_temp
    rec["restarts_or_oom"] = unexpected
    rec["opensearch"] = {"start": os_numbers(os_start), "end": os_numbers(os_end),
                         "delta": delta(os_numbers(os_start), os_numbers(os_end)),
                         "indices_end": [{k: i.get(k) for k in ("index", "docs.count", "store.size", "health")}
                                         for i in os_end.get("indices", []) if isinstance(i, dict)]}
    rec["collector_log_levels"] = dict(levels)
    (d / "collector_errors.json").write_text(json.dumps({
        "reasons": [{"count": c, "reason": r} for r, c in reasons.most_common()],
        "messages": sorted(({"count": g["count"], "message": k, "example": g["example"]} for k, g in errors.items()),
                           key=lambda x: -x["count"]),
    }, ensure_ascii=False, indent=1) + "\n")
    log(f"window end; settle {SETTLE_S} s for collector metrics")
    time.sleep(SETTLE_S)
    rec["exporters"] = counters(lo, hi)
    rec["valid"] = not rec["problems"]
    save()
    if not keep_up:
        p = subprocess.run([str(sr.OTEL_DEMO), "down"], capture_output=True, text=True)
        log(f"otel_demo.sh down: exit {p.returncode}")
    os_exp = rec["exporters"].get("opensearch", {})
    log(f"done: {d}; valid {rec['valid']}; opensearch sent {os_exp.get('sent')} failed {os_exp.get('send_failed')}; "
        f"growth {rec['growth_gb_per_hour']} GB/h; peak {rec['mem_peak_mib']}; distinct opensearch msgs {len(errors)}")
    return 0 if rec["valid"] else 1


# --- compare -------------------------------------------------------------------------------------------------

JAEGER_V3 = "http://127.0.0.1:8080/jaeger/ui/api/v3"
EDGE_NS = 120 * 10**9
SETTLE_NS = 120 * 10**9
SLICE_NS = 60 * 10**9
SEARCH_DEPTH = 1000
# (dosyadaki ad, OTLP türü, Prometheus'taki ad); histogramda karşılaştırılan veri noktasının sayısı (_count)
METRICS = [
    ("container.memory.percent", "gauge", "container_memory_percent_ratio"),
    ("container.network.io.usage.rx_bytes", "sum", "container_network_io_usage_rx_bytes_total"),
    ("traces.span.metrics.duration", "histogram", "traces_span_metrics_duration_milliseconds_count"),
]
NS_FIELDS = re.compile(rb'"(?:startTimeUnixNano|timeUnixNano|observedTimeUnixNano)":"(\d+)"')


def service_of(resource: dict) -> str:
    for a in resource.get("attributes", []):
        if a["key"] == "service.name":
            return next(iter(a["value"].values()), "-")
    return "-"


def file_docs(signal: str, a: int, b: int, oldest: dict):
    """Süzülmüş dosyalardan [a, b) aralığına değebilecek satırlar (JSON); en eski kayıt zamanı `oldest`'a."""
    for f in sorted((sr.TELEMETRY / "filtered").glob(f"{signal}*.jsonl")):
        with f.open("rb") as fh:
            for line in fh:
                ts = [int(x) for x in NS_FIELDS.findall(line) if x != b"0"]
                if not ts:
                    continue
                oldest[signal] = min(oldest.get(signal, ts[0]), min(ts))
                if max(ts) >= a and min(ts) < b:
                    yield json.loads(line)


def file_spans(a: int, b: int, oldest: dict) -> Counter:
    c = Counter()
    for d in file_docs("traces", a, b, oldest):
        for rs in d.get("resourceSpans", []):
            svc = service_of(rs.get("resource", {}))
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    if a <= int(sp["startTimeUnixNano"]) < b:
                        c[svc] += 1
    return c


def file_logs(a: int, b: int, oldest: dict) -> Counter:
    a_ms, b_ms, c = a // 10**6, b // 10**6, Counter()
    for d in file_docs("logs", a, b, oldest):
        for rl in d.get("resourceLogs", []):
            svc = service_of(rl.get("resource", {}))
            for sl in rl.get("scopeLogs", []):
                for r in sl.get("logRecords", []):
                    t = int(r.get("timeUnixNano") or 0) or int(r.get("observedTimeUnixNano") or 0)
                    if a_ms <= t // 10**6 < b_ms:
                        c[svc] += 1
    return c


def file_metrics(a: int, b: int, oldest: dict) -> dict[str, Counter]:
    wanted = {name: kind for name, kind, _ in METRICS}
    out = {name: Counter() for name in wanted}
    a_ms, b_ms = a // 10**6, b // 10**6
    for d in file_docs("metrics", a, b, oldest):
        for rm in d.get("resourceMetrics", []):
            for sm in rm.get("scopeMetrics", []):
                for m in sm.get("metrics", []):
                    kind = wanted.get(m.get("name"))
                    if kind is None or kind not in m:
                        continue
                    for dp in m[kind].get("dataPoints", []):
                        t = int(dp.get("timeUnixNano", 0)) // 10**6
                        if not a_ms <= t < b_ms:
                            continue
                        v = float(dp["count"]) if kind == "histogram" else float(dp.get("asDouble", dp.get("asInt", 0)))
                        out[m["name"]][(t, v)] += 1
    return out


def rfc3339(ns: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ns // 10**9)) + f".{ns % 10**9:09d}Z"


def jaeger_slice(service: str, lo: int, hi: int) -> dict:
    """Bir servis ve zaman dilimindeki izlerin span'leri {(traceId, spanId): (servis, başlangıç)}; derinliğe
    takılan dilim ikiye bölünür."""
    q = urllib.parse.urlencode({"query.service_name": service, "query.start_time_min": rfc3339(lo),
                                "query.start_time_max": rfc3339(hi), "query.search_depth": SEARCH_DEPTH,
                                "query.raw_traces": "true"})
    try:
        d = sr.http("GET", f"{JAEGER_V3}/traces?{q}", timeout=300)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    spans, traces = {}, set()
    for rs in (d.get("result") or {}).get("resourceSpans", []):
        svc = service_of(rs.get("resource", {}))
        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                traces.add(sp["traceId"])
                spans[(sp["traceId"], sp["spanId"])] = (svc, int(sp["startTimeUnixNano"]))
    if len(traces) >= SEARCH_DEPTH:
        if hi - lo <= 10**9:
            raise SystemExit(f"error: jaeger search depth hit in a 1 s slice ({service} {rfc3339(lo)})")
        mid = (lo + hi) // 2
        return {**jaeger_slice(service, lo, mid), **jaeger_slice(service, mid, hi)}
    return spans


def jaeger_spans(a: int, b: int) -> tuple[Counter, int]:
    services = sr.http("GET", f"{JAEGER_V3}/services", timeout=60).get("services", [])
    tasks = [(svc, lo, min(lo + SLICE_NS, b)) for svc in services for lo in range(a, b, SLICE_NS)]
    spans = {}
    with ThreadPoolExecutor(4) as pool:
        for part in pool.map(lambda t: jaeger_slice(*t), tasks):
            spans.update(part)
    c = Counter(svc for svc, start in spans.values() if a <= start < b)
    return c, len(tasks)


def opensearch_logs(a: int, b: int) -> Counter:
    sr.http("POST", OPENSEARCH + "/_refresh", timeout=120)
    body = {"size": 0, "track_total_hits": True,
            "query": {"range": {"@timestamp": {"gte": a // 10**6, "lt": b // 10**6, "format": "epoch_millis"}}},
            "aggs": {"svc": {"terms": {"field": "resource.service.name.keyword", "size": 200, "missing": "-"}}}}
    d = sr.http("POST", OPENSEARCH + "/otel-logs-*/_search", body, timeout=120)
    c = Counter({x["key"]: x["doc_count"] for x in d["aggregations"]["svc"]["buckets"]})
    total = d["hits"]["total"]["value"]
    if total != sum(c.values()):
        c["(not in service buckets)"] = total - sum(c.values())
    return c


def prometheus_samples(name: str, a: int, b: int) -> Counter:
    a_ms, b_ms = a // 10**6, b // 10**6
    q = urllib.parse.urlencode({"query": f"{name}[{b_ms - a_ms}ms]", "time": f"{(b_ms - 1) / 1000:.3f}"})
    d = sr.http("GET", f"{sr.PROMETHEUS}/api/v1/query?{q}", timeout=120)
    c = Counter()
    for series in d["data"]["result"]:
        for ts, v in series["values"]:
            c[(round(float(ts) * 1000), float(v))] += 1
    return c


def diff_counts(file_c: Counter, live_c: Counter) -> dict:
    keys = sorted(set(file_c) | set(live_c), key=str)
    rows = {str(k): {"file": file_c.get(k, 0), "live": live_c.get(k, 0)} for k in keys
            if file_c.get(k, 0) != live_c.get(k, 0)}
    # Boş aralık eşit sayılmaz: dosyada en az bir kayıt olmalı.
    return {"file": sum(file_c.values()), "live": sum(live_c.values()),
            "equal": not rows and sum(file_c.values()) > 0, "differences": rows}


def compare(run: Path, tag: str | None) -> int:
    w = json.loads((run / "watch.json").read_text(encoding="utf-8"))
    start = int(datetime_ns(w["times_utc"]["window_start"]))
    end = int(datetime_ns(w["times_utc"]["window_end"]))
    a, b = start + EDGE_NS, end - EDGE_NS
    if b <= a:
        print("error: window too short for 2 min edges", file=sys.stderr)
        return 2
    wait_s = (b + SETTLE_NS - sr.utc_ns()) / 1e9
    if wait_s > 0:
        print(f"waiting {wait_s:.0f} s (2 min after interval end)", flush=True)
        time.sleep(wait_s)
    rec = {"run": str(run), "tag": tag, "interval_utc": [sr.iso(a), sr.iso(b)], "queried_utc": sr.iso(sr.utc_ns())}
    oldest = {}
    t0 = time.monotonic()
    fs = file_spans(a, b, oldest)
    js, n_queries = jaeger_spans(a, b)
    rec["traces"] = {**diff_counts(fs, js), "jaeger_queries": n_queries}
    rec["logs"] = diff_counts(file_logs(a, b, oldest), opensearch_logs(a, b))
    fm = file_metrics(a, b, oldest)
    rec["metrics"] = {}
    for name, kind, prom in METRICS:
        dc = diff_counts(fm[name], prometheus_samples(prom, a, b))
        dc["differences"] = dict(list(dc["differences"].items())[:20])  # örnek; tamamı büyük olabilir
        rec["metrics"][name] = {"kind": kind, "prometheus": prom, **dc}
    rec["file_oldest_utc"] = {k: sr.iso(v) for k, v in oldest.items()}
    rec["coverage_ok"] = all(oldest.get(s, a + 1) <= a for s in ("traces", "logs", "metrics"))
    rec["seconds"] = round(time.monotonic() - t0)
    rec["equal"] = rec["coverage_ok"] and rec["traces"]["equal"] and rec["logs"]["equal"] \
        and all(m["equal"] for m in rec["metrics"].values())
    out = run / (f"compare_{tag}.json" if tag else "compare.json")
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    print(f"interval {rec['interval_utc']}; coverage {rec['coverage_ok']}")
    print(f"traces: file {rec['traces']['file']} jaeger {rec['traces']['live']} equal {rec['traces']['equal']}")
    print(f"logs: file {rec['logs']['file']} opensearch {rec['logs']['live']} equal {rec['logs']['equal']}")
    for name, m in rec["metrics"].items():
        print(f"{m['kind']} {name}: file {m['file']} prometheus {m['live']} equal {m['equal']}")
    print(f"{'EQUAL' if rec['equal'] else 'DIFFERENT'} -> {out} ({rec['seconds']} s)")
    return 0 if rec["equal"] else 1


def datetime_ns(iso_z: str) -> int:
    return int(datetime.fromisoformat(iso_z.replace("Z", "+00:00")).timestamp()) * 10**9


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="storage_check.py", description="storage card measurements")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="bring the demo up and watch the monitoring stack")
    w.add_argument("--minutes", type=int, default=60)
    w.add_argument("--keep-up", action="store_true", help="leave the demo running afterwards")
    c = sub.add_parser("compare", help="compare live backends with the file output over a watch window")
    c.add_argument("--run", type=Path, required=True, help="watch run folder (watch.json)")
    c.add_argument("--tag", help="write compare_<tag>.json instead of compare.json")
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        if not (args.run / "watch.json").is_file():
            print(f"error: {args.run}/watch.json not found", file=sys.stderr)
            return 2
        return compare(args.run, args.tag)
    if os.environ.get("SCENARIO_RUNNER_INHIBITED") != "1":
        env = dict(os.environ, SCENARIO_RUNNER_INHIBITED="1")
        cmd = [*sr.GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
               "--who=aiops_rca storage_check", "--why=storage card watch", sys.executable, *sys.argv]
        return subprocess.run(cmd, env=env).returncode
    return watch(args.minutes, args.keep_up)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
