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

  python tools/storage_check.py replay <C2 koşu klasörü>...
      Yeniden oynatma denemesi (D3; HANDOFF 2026-10-25 D3 planı ve planlama ekleri). Korumalar; canlı demo kapalı ve
      `otel-replay_*` volume'leri yok olmalı. Canlı volume boyutları başta ve sonda (`docker system df`).
      `deploy/replay/compose.yaml`: Jaeger, Prometheus, OpenSearch açılır; 30 sn sonra Prometheus başı boş olmalı
      (numSeries 0; Jaeger'in ittiği metrik ulaşmıyor). Pencereler zaman sırasıyla, tek tek: collector
      (`REPLAY_WINDOW` = `window/filtered/`) yeniden yaratılır; exporter sayaçları (:18888) dosyadaki kayıt
      sayısına ulaşıp kuyruk boşalınca (en çok 20 dk) 30 sn bekleme, sonra sent = dosya ve send_failed = 0 olmalı
      (fazlası çift okuma); collector'ın logu `collector_<koşu>.log`'a yazılır, sonra durdurulur. Her pencereden sonra Prometheus başının maxTime'ı ≤ pencere sonu +
      1 dk, reddetme sayaçları (out-of-order, out-of-bounds, too-old) kayda; `compare`'in sayımı (aralık: pencerenin
      kendisi, dosya `window/filtered/`, uçlar 16686/19200/19090). İkinci pencereden önce aynı sayım kasıtlı
      kırmızı (eşit olmamalı). Sonra ilk pencerenin metrikleri (dosyadaki en eski ve en yeni zaman) diskteki bir
      bloğa girene kadar (`promtool tsdb list`, en çok 15 dk) ve iki pencere yeniden sayılır. 30 sn'de bir bellek → `mem.tsv`. Sonda `down` (volume'ler kalır).
      Çıktı `~/cerebrum2/storage_runs/<UTC>-replay/replay.json`, `replay.log`, `collector_<koşu>.log`.

Çıkış kodu (watch): 0 ölçüm tamam, 1 koruma tutmadı / demo açılmadı / makine uyudu, 2 kullanım hatası.
Çıkış kodu (compare): 0 üç sistemde de eşit (ve dosyada kayıt var), 1 fark var, boş ya da kapsama eksik,
2 kullanım hatası.
Çıkış kodu (replay): 0 bütün ölçütler geçti, 1 biri geçmedi ya da durdu, 2 kullanım hatası.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
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


def mem_mib(names: list[str] = WATCHED) -> dict[str, float | None]:
    out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}", *names],
                         capture_output=True, text=True, timeout=60).stdout
    units = {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "KB": 1 / 1024, "MB": 1, "GB": 1024, "B": 1 / 2**20}
    result = {c: None for c in names}
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


FILTERED = sr.TELEMETRY / "filtered"
# Sorgulanan uçlar: canlı demo (8080 üzerinden Jaeger) ya da yeniden oynatma projesi (deploy/replay/compose.yaml)
LIVE_ENDS = {"jaeger": JAEGER_V3, "opensearch": OPENSEARCH, "prometheus": sr.PROMETHEUS}
REPLAY_ENDS = {"jaeger": "http://127.0.0.1:16686/jaeger/ui/api/v3", "opensearch": "http://127.0.0.1:19200",
               "prometheus": "http://127.0.0.1:19090"}


def file_docs(signal: str, a: int, b: int, oldest: dict, src: Path = FILTERED):
    """`src`'deki süzülmüş dosyalardan [a, b) aralığına değebilecek satırlar (JSON); en eski kayıt zamanı `oldest`'a."""
    for f in sorted(src.glob(f"{signal}*.jsonl")):
        with f.open("rb") as fh:
            for line in fh:
                ts = [int(x) for x in NS_FIELDS.findall(line) if x != b"0"]
                if not ts:
                    continue
                oldest[signal] = min(oldest.get(signal, ts[0]), min(ts))
                if max(ts) >= a and min(ts) < b:
                    yield json.loads(line)


def file_spans(a: int, b: int, oldest: dict, src: Path = FILTERED) -> Counter:
    c = Counter()
    for d in file_docs("traces", a, b, oldest, src):
        for rs in d.get("resourceSpans", []):
            svc = service_of(rs.get("resource", {}))
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    if a <= int(sp["startTimeUnixNano"]) < b:
                        c[svc] += 1
    return c


def file_logs(a: int, b: int, oldest: dict, src: Path = FILTERED) -> Counter:
    a_ms, b_ms, c = a // 10**6, b // 10**6, Counter()
    for d in file_docs("logs", a, b, oldest, src):
        for rl in d.get("resourceLogs", []):
            svc = service_of(rl.get("resource", {}))
            for sl in rl.get("scopeLogs", []):
                for r in sl.get("logRecords", []):
                    t = int(r.get("timeUnixNano") or 0) or int(r.get("observedTimeUnixNano") or 0)
                    if a_ms <= t // 10**6 < b_ms:
                        c[svc] += 1
    return c


def file_metrics(a: int, b: int, oldest: dict, src: Path = FILTERED) -> dict[str, Counter]:
    wanted = {name: kind for name, kind, _ in METRICS}
    out = {name: Counter() for name in wanted}
    a_ms, b_ms = a // 10**6, b // 10**6
    for d in file_docs("metrics", a, b, oldest, src):
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


def jaeger_slice(base: str, service: str, lo: int, hi: int) -> dict:
    """Bir servis ve zaman dilimindeki izlerin span'leri {(traceId, spanId): (servis, başlangıç)}; derinliğe
    takılan dilim ikiye bölünür."""
    q = urllib.parse.urlencode({"query.service_name": service, "query.start_time_min": rfc3339(lo),
                                "query.start_time_max": rfc3339(hi), "query.search_depth": SEARCH_DEPTH,
                                "query.raw_traces": "true"})
    try:
        d = sr.http("GET", f"{base}/traces?{q}", timeout=300)
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
        return {**jaeger_slice(base, service, lo, mid), **jaeger_slice(base, service, mid, hi)}
    return spans


def jaeger_spans(a: int, b: int, base: str = JAEGER_V3) -> tuple[Counter, int]:
    services = sr.http("GET", f"{base}/services", timeout=60).get("services", [])
    tasks = [(svc, lo, min(lo + SLICE_NS, b)) for svc in services for lo in range(a, b, SLICE_NS)]
    spans = {}
    with ThreadPoolExecutor(4) as pool:
        for part in pool.map(lambda t: jaeger_slice(base, *t), tasks):
            spans.update(part)
    c = Counter(svc for svc, start in spans.values() if a <= start < b)
    return c, len(tasks)


def opensearch_logs(a: int, b: int, base: str = OPENSEARCH) -> Counter:
    sr.http("POST", base + "/_refresh", timeout=120)
    body = {"size": 0, "track_total_hits": True,
            "query": {"range": {"@timestamp": {"gte": a // 10**6, "lt": b // 10**6, "format": "epoch_millis"}}},
            "aggs": {"svc": {"terms": {"field": "resource.service.name.keyword", "size": 200, "missing": "-"}}}}
    d = sr.http("POST", base + "/otel-logs-*/_search", body, timeout=120)
    c = Counter({x["key"]: x["doc_count"] for x in d["aggregations"]["svc"]["buckets"]})
    total = d["hits"]["total"]["value"]
    if total != sum(c.values()):
        c["(not in service buckets)"] = total - sum(c.values())
    return c


def prometheus_samples(name: str, a: int, b: int, base: str = sr.PROMETHEUS) -> Counter:
    a_ms, b_ms = a // 10**6, b // 10**6
    q = urllib.parse.urlencode({"query": f"{name}[{b_ms - a_ms}ms]", "time": f"{(b_ms - 1) / 1000:.3f}"})
    d = sr.http("GET", f"{base}/api/v1/query?{q}", timeout=120)
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
    part, oldest = compare_interval(a, b, FILTERED, LIVE_ENDS)
    rec = {"run": str(run), "tag": tag, **part}
    rec["coverage_ok"] = all(oldest.get(s, a + 1) <= a for s in ("traces", "logs", "metrics"))
    rec["equal"] = rec["coverage_ok"] and rec["equal"]
    out = run / (f"compare_{tag}.json" if tag else "compare.json")
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    print_compare(rec, out)
    return 0 if rec["equal"] else 1


def compare_interval(a: int, b: int, src: Path, ends: dict) -> tuple[dict, dict]:
    """[a, b) aralığında `src`'deki dosyalar ile `ends`'teki Jaeger, OpenSearch, Prometheus; `equal` kapsama hariç.
    İkinci dönen: sinyal başına dosyadaki en eski kayıt zamanı (ns)."""
    rec = {"interval_utc": [sr.iso(a), sr.iso(b)], "queried_utc": sr.iso(sr.utc_ns())}
    oldest = {}
    t0 = time.monotonic()
    fs = file_spans(a, b, oldest, src)
    js, n_queries = jaeger_spans(a, b, ends["jaeger"])
    rec["traces"] = {**diff_counts(fs, js), "jaeger_queries": n_queries}
    rec["logs"] = diff_counts(file_logs(a, b, oldest, src), opensearch_logs(a, b, ends["opensearch"]))
    fm = file_metrics(a, b, oldest, src)
    rec["metrics"] = {}
    for name, kind, prom in METRICS:
        dc = diff_counts(fm[name], prometheus_samples(prom, a, b, ends["prometheus"]))
        dc["differences"] = dict(list(dc["differences"].items())[:20])  # örnek; tamamı büyük olabilir
        rec["metrics"][name] = {"kind": kind, "prometheus": prom, **dc}
    rec["file_oldest_utc"] = {k: sr.iso(v) for k, v in oldest.items()}
    rec["seconds"] = round(time.monotonic() - t0)
    rec["equal"] = rec["traces"]["equal"] and rec["logs"]["equal"] and all(m["equal"] for m in rec["metrics"].values())
    return rec, oldest


def print_compare(rec: dict, out: Path) -> None:
    print(f"interval {rec['interval_utc']}; coverage {rec.get('coverage_ok')}")
    print(f"traces: file {rec['traces']['file']} jaeger {rec['traces']['live']} equal {rec['traces']['equal']}")
    print(f"logs: file {rec['logs']['file']} opensearch {rec['logs']['live']} equal {rec['logs']['equal']}")
    for name, m in rec["metrics"].items():
        print(f"{m['kind']} {name}: file {m['file']} prometheus {m['live']} equal {m['equal']}")
    print(f"{'EQUAL' if rec['equal'] else 'DIFFERENT'} -> {out} ({rec['seconds']} s)")


def datetime_ns(iso_z: str) -> int:
    return int(datetime.fromisoformat(iso_z.replace("Z", "+00:00")).timestamp()) * 10**9


# --- replay --------------------------------------------------------------------------------------------------

DEMO = Path.home() / "cerebrum2" / "otel-demo"
REPLAY_COMPOSE = sr.REPO / "deploy" / "replay" / "compose.yaml"
REPLAY_PROJECT = "otel-replay"
REPLAY_CONTAINERS = [f"{REPLAY_PROJECT}-{s}-1" for s in ("jaeger", "prometheus", "opensearch", "otel-collector")]
COLLECTOR_METRICS = "http://127.0.0.1:18888/metrics"
REPLAY_TIMEOUT_S = 1200   # pencere başına bitiş beklemesi; dolarsa rapor, beklenmez (planlama ek 2)
DONE_SETTLE_S = 30        # sayaçlar dosyaya ulaştıktan sonra (fazlası çift okuma)
COMPACT_TIMEOUT_S = 900
JAEGER_PUSH_WAIT_S = 30   # Jaeger kendi metriklerini 10 sn'de bir itiyor; Prometheus boş mu, en az iki denemeden sonra
# sinyal → (exporter, otelcol sayaç eki)
SIGNALS = {"traces": ("otlp_grpc/jaeger", "spans"), "metrics": ("otlp_http/prometheus", "metric_points"),
           "logs": ("opensearch", "log_records")}
OTELCOL = re.compile(r"^otelcol_(exporter_(?:sent|send_failed|enqueue_failed)_\w+?|exporter_queue_size"
                     r"|receiver_(?:accepted|refused|failed)_\w+?)(?:_total)?\{([^}]*)\}\s+(\S+)$", re.M)
PROM_REJECT = re.compile(r"^(prometheus_tsdb_\w*(?:out_of_order|out_of_bound|too_old)\w*)(\{[^}]*\})?\s+(\S+)$", re.M)


def replay_compose(args: list[str], window: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, REPLAY_WINDOW=str(window))
    cmd = ["docker", "compose", "--env-file", str(DEMO / ".env"), "--env-file", str(DEMO / ".env.override"),
           "-f", str(REPLAY_COMPOSE), *args]
    return subprocess.run(cmd, cwd=REPLAY_COMPOSE.parent, env=env, capture_output=True, text=True, timeout=900)


def volume_sizes() -> dict[str, str]:
    """Docker volume adı → boyut (`docker system df -v`, ondalık birim)."""
    p = subprocess.run(["docker", "system", "df", "-v", "--format", "json"], capture_output=True, text=True,
                       timeout=120)
    return {v["Name"]: v["Size"] for v in json.loads(p.stdout)["Volumes"]}


def file_totals(src: Path) -> dict:
    """Pencere dosyalarındaki bütün kayıtlar: span, metrik veri noktası, log kaydı; metrikteki en eski ve en yeni
    zaman (ms, Prometheus'un çözünürlüğü)."""
    out = {"traces": 0, "metrics": 0, "logs": 0}
    oldest, newest = None, 0
    with (src / "traces.jsonl").open("rb") as fh:
        for line in fh:
            for rs in json.loads(line).get("resourceSpans", []):
                out["traces"] += sum(len(ss.get("spans", [])) for ss in rs.get("scopeSpans", []))
    with (src / "metrics.jsonl").open("rb") as fh:
        for line in fh:
            for rm in json.loads(line).get("resourceMetrics", []):
                for sm in rm.get("scopeMetrics", []):
                    for m in sm.get("metrics", []):
                        for kind in ("gauge", "sum", "histogram", "exponentialHistogram", "summary"):
                            for dp in m.get(kind, {}).get("dataPoints", []):
                                out["metrics"] += 1
                                ts = int(dp.get("timeUnixNano", 0))
                                newest = max(newest, ts)
                                oldest = ts if oldest is None else min(oldest, ts)
    with (src / "logs.jsonl").open("rb") as fh:
        for line in fh:
            for rl in json.loads(line).get("resourceLogs", []):
                out["logs"] += sum(len(sl.get("logRecords", [])) for sl in rl.get("scopeLogs", []))
    out["metrics_newest_utc"] = sr.iso(newest) if newest else None
    out["metrics_oldest_ms"] = oldest // 10**6 if oldest is not None else None
    out["metrics_newest_ms"] = newest // 10**6 if newest else None
    return out


def otelcol_counters() -> dict[str, float]:
    """Yeniden oynatma collector'ının kendi sayaçları (çekme ucu): '<sayaç>|<exporter ya da receiver>' → değer."""
    text = sr.http("GET", COLLECTOR_METRICS, timeout=10)
    out = Counter()
    for m in OTELCOL.finditer(text):
        labels = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
        out[f"{m.group(1)}|{labels.get('exporter') or labels.get('receiver')}"] += float(m.group(3))
    return dict(out)


def wait_replayed(totals: dict, log) -> dict:
    """Exporter sayaçları (sent + send_failed) her sinyalde dosyadaki sayıya ulaşana ve kuyruk boşalana kadar."""
    deadline, last_log, c = time.monotonic() + REPLAY_TIMEOUT_S, 0.0, {}
    timed_out = True
    while time.monotonic() < deadline:
        time.sleep(10)
        try:
            c = otelcol_counters()
        except OSError:
            continue
        progress = {s: c.get(f"exporter_sent_{n}|{e}", 0) + c.get(f"exporter_send_failed_{n}|{e}", 0)
                    for s, (e, n) in SIGNALS.items()}
        queue = sum(v for k, v in c.items() if k.startswith("exporter_queue_size|"))
        if time.monotonic() - last_log > 60:
            log(f"  progress {({s: int(v) for s, v in progress.items()})} / {totals}; queue {queue:.0f}")
            last_log = time.monotonic()
        if all(progress[s] >= totals[s] for s in SIGNALS) and queue == 0:
            timed_out = False
            break
    time.sleep(DONE_SETTLE_S)
    try:
        c = otelcol_counters()
    except OSError as e:
        log(f"  collector counters unreadable after settle: {e}")
    res = {"timed_out": timed_out, "counters": c}
    for s, (e, n) in SIGNALS.items():
        sent = c.get(f"exporter_sent_{n}|{e}", 0)
        failed = c.get(f"exporter_send_failed_{n}|{e}", 0)
        res[s] = {"file": totals[s], "sent": sent, "send_failed": failed,
                  "enqueue_failed": c.get(f"exporter_enqueue_failed_{n}|{e}", 0),
                  "equal": sent == totals[s] and failed == 0}
    return res


def prometheus_head() -> dict:
    return sr.http("GET", REPLAY_ENDS["prometheus"] + "/api/v1/status/tsdb", timeout=30)["data"]["headStats"]


def prometheus_rejects() -> dict[str, float]:
    text = sr.http("GET", REPLAY_ENDS["prometheus"] + "/metrics", timeout=30)
    return {m.group(1) + (m.group(2) or ""): float(m.group(3)) for m in PROM_REJECT.finditer(text)}


def tsdb_blocks() -> list[dict]:
    """Prometheus'un diskteki blokları (`promtool tsdb list`, konteyner içinde)."""
    p = subprocess.run(["docker", "exec", f"{REPLAY_PROJECT}-prometheus-1", "promtool", "tsdb", "list", "/prometheus"],
                       capture_output=True, text=True, timeout=120)
    blocks = []
    for line in p.stdout.splitlines()[1:]:
        f = line.split()
        if len(f) >= 5 and f[1].isdigit() and f[2].isdigit():
            blocks.append({"ulid": f[0], "min_ms": int(f[1]), "max_ms": int(f[2]), "samples": int(f[4]),
                           "min_utc": sr.iso(int(f[1]) * 10**6), "max_utc": sr.iso(int(f[2]) * 10**6)})
    return blocks


def wait_http(url: str, timeout_s: int) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            sr.http("GET", url, timeout=10)
            return True
        except OSError:
            time.sleep(5)
    return False


def container_states(names: list[str]) -> dict:
    out = {}
    for n in names:
        p = subprocess.run(["docker", "inspect", "-f", "{{.RestartCount}} {{.State.OOMKilled}} {{.State.Status}} "
                            "{{.State.ExitCode}}", n], capture_output=True, text=True, timeout=30)
        f = p.stdout.split()
        out[n] = {"restarts": int(f[0]), "oom_killed": f[1] == "true", "status": f[2], "exit_code": int(f[3])} \
            if p.returncode == 0 and len(f) == 4 else None
    return out


def short(part: dict) -> dict:
    """compare_interval sonucunun sayıları (kayıt ve log için)."""
    return {"equal": part["equal"], "traces": [part["traces"]["file"], part["traces"]["live"]],
            "logs": [part["logs"]["file"], part["logs"]["live"]],
            "metrics": {n: [m["file"], m["live"], m["equal"]] for n, m in part["metrics"].items()}}


def replay(runs: list[Path]) -> int:
    d = OUT / (time.strftime("%Y%m%dT%H%MZ", time.gmtime()) + "-replay")
    d.mkdir(parents=True)
    log_file = (d / "replay.log").open("a")

    def log(msg: str) -> None:
        line = f"{sr.iso(sr.utc_ns())} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    rec = {"runs": [str(r) for r in runs], "guards_before": sr.guards(), "problems": [], "windows": [],
           "checks": {}, "valid": False}
    save = lambda: (d / "replay.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")  # noqa: E731

    def stop(msg: str) -> int:
        rec["problems"].append(msg)
        save()
        log(msg)
        return 1

    if rec["guards_before"]["problems"]:
        return stop("guards: " + "; ".join(rec["guards_before"]["problems"]))
    live = subprocess.run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=otel-demo"],
                          capture_output=True, text=True, timeout=30).stdout.split()
    if live:
        return stop(f"live demo is running ({len(live)} containers); bring it down first")
    sizes0 = volume_sizes()
    if any(n.startswith(REPLAY_PROJECT + "_") for n in sizes0):
        return stop("replay volumes already exist; the target must be empty")
    rec["live_volumes_before"] = {n: sizes0.get(n) for n in sr.MONITORING_VOLUMES}

    windows = []
    for run in runs:
        rj = json.loads((run / "run.json").read_text(encoding="utf-8"))
        t = rj["times_utc"]
        windows.append({"run": run.name, "src": run / "window" / "filtered",
                        "lo": datetime_ns(t["normal_start"]) - sr.WINDOW_MARGIN_NS[0],
                        "hi": datetime_ns(t["flag_off_write"]) + sr.WINDOW_MARGIN_NS[1],
                        "covered": all(v["covered"] for k, v in rj["window"].items() if k.startswith("filtered/"))})
    windows.sort(key=lambda w: w["lo"])  # zaman sırasıyla (planlama ek 4)
    for w in windows:
        w["totals"] = file_totals(w["src"])
        log(f"{w['run']}: [{sr.iso(w['lo'])}, {sr.iso(w['hi'])}] covered {w['covered']} file {w['totals']}")

    peaks, stop_mem = {n: 0.0 for n in REPLAY_CONTAINERS}, threading.Event()

    def sample_mem() -> None:
        with (d / "mem.tsv").open("a") as fh:
            while not stop_mem.wait(30):
                m = mem_mib(REPLAY_CONTAINERS)
                fh.write(sr.iso(sr.utc_ns()) + "\t" + "\t".join(f"{n}={v}" for n, v in m.items()) + "\n")
                fh.flush()
                for n, v in m.items():
                    if v:
                        peaks[n] = max(peaks[n], v)

    mem_thread = threading.Thread(target=sample_mem, daemon=True)
    try:
        p = replay_compose(["up", "-d", "--wait", "--wait-timeout", "300", "jaeger", "prometheus", "opensearch"],
                           windows[0]["src"])
        log(f"replay up (jaeger, prometheus, opensearch): exit {p.returncode}")
        if p.returncode != 0:
            log(p.stderr[-2000:])
            return stop("replay up failed")
        mem_thread.start()
        if not (wait_http(REPLAY_ENDS["prometheus"] + "/-/ready", 300)
                and wait_http(REPLAY_ENDS["jaeger"] + "/services", 300)):
            return stop("replay backends not ready")
        time.sleep(JAEGER_PUSH_WAIT_S)
        head = prometheus_head()
        rec["checks"]["head_before"] = head
        log(f"prometheus head before replay: {head}")
        if head.get("numSeries") != 0:
            return stop(f"prometheus not empty before replay (numSeries {head.get('numSeries')})")

        for i, w in enumerate(windows):
            wr = {"run": w["run"], "interval_utc": [sr.iso(w["lo"]), sr.iso(w["hi"])], "covered": w["covered"],
                  "file": w["totals"]}
            rec["windows"].append(wr)
            if i > 0:
                # Kasıtlı kırmızı: bu pencere oynatılmadan karşılaştırma eşit olmamalı.
                part, _ = compare_interval(w["lo"], w["hi"], w["src"], REPLAY_ENDS)
                wr["red_before_replay"] = short(part)
                log(f"{w['run']} before replay (intentional red): {short(part)}")
            p = replay_compose(["up", "-d", "--force-recreate", "otel-collector"], w["src"])
            log(f"{w['run']}: collector up exit {p.returncode}")
            if p.returncode != 0:
                log(p.stderr[-2000:])
                return stop(f"{w['run']}: collector up failed")
            wr["replayed"] = wait_replayed(w["totals"], log)
            wr["collector_state"] = container_states([f"{REPLAY_PROJECT}-otel-collector-1"])
            # Log, collector yeniden yaratılmadan ya da `down`dan önce (ilk D3 koşusunda hata nedeni böyle kaybolmuştu).
            p = subprocess.run(["docker", "logs", f"{REPLAY_PROJECT}-otel-collector-1"], capture_output=True,
                               text=True, timeout=120)
            (d / f"collector_{w['run']}.log").write_text(p.stdout + p.stderr)
            wr["collector_error_lines"] = sum("\terror\t" in x for x in (p.stdout + p.stderr).splitlines())
            replay_compose(["stop", "otel-collector"], w["src"])
            log(f"{w['run']}: replayed {({s: wr['replayed'][s] for s in SIGNALS})}; "
                f"timed out {wr['replayed']['timed_out']}; collector {wr['collector_state']}; "
                f"error lines {wr['collector_error_lines']}")
            head = prometheus_head()
            wr["head_after"] = head
            wr["head_max_ok"] = head.get("maxTime", 0) <= w["hi"] // 10**6 + 60_000
            wr["prometheus_rejects"] = prometheus_rejects()
            log(f"{w['run']}: head maxTime {sr.iso(head.get('maxTime', 0) * 10**6)} ok {wr['head_max_ok']}; "
                f"rejects {wr['prometheus_rejects']}")
            part, _ = compare_interval(w["lo"], w["hi"], w["src"], REPLAY_ENDS)
            wr["compare"] = part
            log(f"{w['run']}: compare {short(part)}")
            save()

        # Blok: ilk pencerenin metrikleri diskteki bir bloğa girene kadar (baş, aralığı 3 saati aşınca sıkıştırılır).
        # Ölçü dosyadaki en eski ve en yeni metrik zamanı: blok başlangıcı ilk örneğin zamanı, pencere başı (kenar
        # paylı) değil (ikinci D3 koşusunda pencere başıyla karşılaştırmak yanlış kırmızı verdi).
        first = windows[0]
        lo_ms, hi_ms = first["totals"]["metrics_oldest_ms"], first["totals"]["metrics_newest_ms"]

        def covers(b: dict) -> bool:
            return lo_ms is not None and b["min_ms"] <= lo_ms and b["max_ms"] > hi_ms

        deadline, blocks = time.monotonic() + COMPACT_TIMEOUT_S, []
        while time.monotonic() < deadline:
            blocks = tsdb_blocks()
            if any(covers(b) for b in blocks):
                break
            time.sleep(30)
        rec["checks"]["blocks"] = blocks
        rec["checks"]["head_after_compaction"] = prometheus_head()
        rec["checks"]["block_covers_first"] = any(covers(b) for b in blocks)
        log(f"blocks: {[(b['min_utc'], b['max_utc'], b['samples']) for b in blocks]}")
        rec["after_compaction"] = []
        for w in windows:
            part, _ = compare_interval(w["lo"], w["hi"], w["src"], REPLAY_ENDS)
            rec["after_compaction"].append({"run": w["run"], **part})
            log(f"{w['run']} after compaction: {short(part)}")
        rec["opensearch_indices"] = sr.http("GET", REPLAY_ENDS["opensearch"] +
                                            "/_cat/indices/otel-logs-*?format=json&h=index,docs.count", timeout=60)
        save()
    finally:
        stop_mem.set()
        rec["containers"] = container_states(REPLAY_CONTAINERS)
        rec["mem_peak_mib"] = {n: round(v, 1) for n, v in peaks.items()}
        p = replay_compose(["down"], windows[0]["src"])
        log(f"replay down (volumes kept): exit {p.returncode}")
        sizes1 = volume_sizes()
        rec["live_volumes_after"] = {n: sizes1.get(n) for n in sr.MONITORING_VOLUMES}
        rec["replay_volumes"] = {n: s for n, s in sizes1.items() if n.startswith(REPLAY_PROJECT + "_")}
        save()

    ws = rec["windows"]
    crit = {
        "prometheus_empty_before": rec["checks"]["head_before"].get("numSeries") == 0,
        "windows_covered": all(w["covered"] for w in ws),
        "replayed_equal_no_timeout": all(not w["replayed"]["timed_out"] and all(w["replayed"][s]["equal"]
                                                                                 for s in SIGNALS) for w in ws),
        "collector_not_restarted": all(all(v and v["restarts"] == 0 and v["exit_code"] == 0
                                           for v in w["collector_state"].values()) for w in ws),
        "head_max_ok": all(w["head_max_ok"] for w in ws),
        "compare_equal": all(w["compare"]["equal"] for w in ws),
        "intentional_red": all(not w["red_before_replay"]["equal"] for w in ws[1:]) and len(ws) > 1,
        "block_covers_first": rec["checks"]["block_covers_first"],
        "after_compaction_equal": all(x["equal"] for x in rec["after_compaction"]),
        "live_volumes_unchanged": rec["live_volumes_before"] == rec["live_volumes_after"],
        "no_oom": all(v and not v["oom_killed"] and v["restarts"] == 0 for v in rec["containers"].values()),
    }
    rec["criteria"] = crit
    rec["valid"] = all(crit.values())
    save()
    log(f"criteria {crit}")
    log(f"{'PASS' if rec['valid'] else 'FAIL'} -> {d}; mem peak {rec['mem_peak_mib']}")
    log_file.close()
    return 0 if rec["valid"] else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="storage_check.py", description="storage card measurements")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="bring the demo up and watch the monitoring stack")
    w.add_argument("--minutes", type=int, default=60)
    w.add_argument("--keep-up", action="store_true", help="leave the demo running afterwards")
    c = sub.add_parser("compare", help="compare live backends with the file output over a watch window")
    c.add_argument("--run", type=Path, required=True, help="watch run folder (watch.json)")
    c.add_argument("--tag", help="write compare_<tag>.json instead of compare.json")
    r = sub.add_parser("replay", help="replay C2 windows into an empty, separate monitoring stack (deploy/replay)")
    r.add_argument("runs", nargs="+", type=Path, help="C2 run folders (run.json, window/filtered/)")
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        if not (args.run / "watch.json").is_file():
            print(f"error: {args.run}/watch.json not found", file=sys.stderr)
            return 2
        return compare(args.run, args.tag)
    if args.cmd == "replay":
        bad = [r for r in args.runs if not (r / "run.json").is_file()
               or not all((r / "window" / "filtered" / f"{s}.jsonl").is_file() for s in SIGNALS)]
        if bad:
            print(f"error: run.json or window/filtered/*.jsonl missing in {bad}", file=sys.stderr)
            return 2
    if os.environ.get("SCENARIO_RUNNER_INHIBITED") != "1":
        env = dict(os.environ, SCENARIO_RUNNER_INHIBITED="1")
        cmd = [*sr.GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
               "--who=aiops_rca storage_check", f"--why=storage card {args.cmd}", sys.executable, *sys.argv]
        return subprocess.run(cmd, env=env).returncode
    if args.cmd == "replay":
        return replay([r.resolve() for r in args.runs])
    return watch(args.minutes, args.keep_up)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
