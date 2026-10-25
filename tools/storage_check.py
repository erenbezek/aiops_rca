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
Çıkış kodu: 0 ölçüm tamam, 1 koruma tutmadı / demo açılmadı / makine uyudu, 2 kullanım hatası.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scenario_runner as sr  # noqa: E402
from c2_measure import increase, read_otelcol, SENT, SEND_FAILED, ENQUEUE_FAILED  # noqa: E402

OUT = Path.home() / "cerebrum2" / "storage_runs"
OPENSEARCH = "http://127.0.0.1:9200"
WATCHED = ["jaeger", "prometheus", "opensearch", "otel-collector"]
# Konteyner → veri klasörü (D1: Jaeger bellekte, diski yok)
DATA_DIRS = {"prometheus": "/prometheus", "opensearch": "/usr/share/opensearch/data"}
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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="storage_check.py", description="storage card measurements")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="bring the demo up and watch the monitoring stack")
    w.add_argument("--minutes", type=int, default=60)
    w.add_argument("--keep-up", action="store_true", help="leave the demo running afterwards")
    args = ap.parse_args(argv)
    if os.environ.get("SCENARIO_RUNNER_INHIBITED") != "1":
        env = dict(os.environ, SCENARIO_RUNNER_INHIBITED="1")
        cmd = [*sr.GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
               "--who=aiops_rca storage_check", "--why=storage card watch", sys.executable, *sys.argv]
        return subprocess.run(cmd, env=env).returncode
    return watch(args.minutes, args.keep_up)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
