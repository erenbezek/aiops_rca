"""Senaryo koşucusu: demoyu açar, 10 dk normal + 10 dk flag koşturur, kaydı ve telemetri penceresini saklar.

C2 kartı (HANDOFF 2026-10-23 "Planlama → Uygulama (collector C2)", 2026-10-24 "Uygulama → Uygulama (C2, ölçmeden
önce)"); vaka üretiminde de bu koşucu kullanılır.

Kullanım:
  python tools/scenario_runner.py list                 senaryoları basar
  python tools/scenario_runner.py guards               makine korumalarını basar (koşmaz)
  python tools/scenario_runner.py run <id>... | all    koşuları sırayla yürütür (gnome-session-inhibit ve
                                                       systemd-inhibit altında)

Koşu başına (`~/cerebrum2/c2_runs/<senaryo>_<varyant>_<deneme>/`, repo dışı, cevap içerir):
  korumalar → `otel_demo.sh up --raw` → 22 konteyner (6 dk içinde olmazsa collector yeniden başlatılır, 4 dk daha)
  → flagd-ui zamanlayıcısı kapalı ve flag kapalı → 10 dk normal → flag yaz, flagd'den doğrula → 10 dk → flag kapat,
  doğrula → konteyner yeniden başlama / OOM → `down` → telemetri penceresi `window/raw/` ve `window/filtered/`'a
  kopyalanır (döndürme eski veriyi siler; DECISIONS 2026-10-21). Ölçüm ayrı: `tools/c2_measure.py`.
  Vaka penceresinde 8080'e sadece flag yazma ve doğrulama gider; sayım 9090'dan (Prometheus).
  Koşu boyunca 10 sn'de bir `x86_pkg_temp`, dakikada bir collector belleği.

Kayıt: `run.json` (alanlar aşağıda `record`), `runner.log`, `collector_mem.tsv`, `containers_start.txt`,
`containers_end.txt`, `window/`.

Geçersiz koşu: flag doğrulanamadı, 22 konteyner yok, pencerede kök neden servisi dışında bir konteyner yeniden
başladı ya da durdu (kök neden servisinin yeniden başlaması beklenir, `expected_restarts`'a yazılır; Eren,
2026-10-24), makine normal başlangıcı ile flag kapanışı arasında 1 dk'dan uzun uyudu (`suspended_s`: CLOCK_BOOTTIME
uykuda ilerler, CLOCK_MONOTONIC ilerlemez; farkın artışı uyku süresidir), ısınma (95 °C üstünde 1 dk'dan fazla), pencere döndürmeyle kısaldı (bir {raw, filtered} × {traces, metrics,
logs} için kaynak dosyalardaki en eski kaydın kendi zamanı normal başlangıcından sonra).
Isınmada koşu kesilir, soğuyunca (90 °C altında 2 dk) baştan; döndürmede baştan. İkinci kez de olursa üçüncü kez
koşulmaz, kayda (Eren, 2026-10-24). Korumalardan biri koşu öncesi tutmazsa sıra durur.
Çıkış kodu: 0 bütün koşular geçerli, 1 en az biri geçersiz ya da sıra durdu, 2 kullanım hatası.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OTEL_DEMO = REPO / "tools" / "otel_demo.sh"
TELEMETRY = Path.home() / "cerebrum2" / "telemetry"
OUT = Path.home() / "cerebrum2" / "c2_runs"
FLAGD_UI = "http://127.0.0.1:8080"
PROMETHEUS = "http://127.0.0.1:9090"

NORMAL_S = 600
FLAG_S = 600
CONTAINERS = 22
WAIT_CONTAINERS_S = (360, 240)  # ilk bekleme, collector yeniden başlatıldıktan sonra
WINDOW_MARGIN_NS = (120 * 10**9, 60 * 10**9)  # normal başlangıcından önce, flag kapanışından sonra

# Makine sınırları (DECISIONS 2026-10-20)
MIN_FREE_GB = 30
# İzleme volume'lerinin toplamı (depolama D2, Eren onayı 2026-10-25): ölçülen büyüme ~0,85 GB/saat, 40 GB ≈ 7 günlük
# saklamada haftada ~47 saat demo. Aşılırsa koşu başlamaz; saklama süresi eskiyi silene kadar bekle ya da volume'leri
# elle sil. AIOPS_MAX_MONITORING_GB yalnız kasıtlı kırmızı için (düşük sahte sınır).
MAX_MONITORING_GB = float(os.environ.get("AIOPS_MAX_MONITORING_GB", "40"))
MONITORING_VOLUMES = ("otel-demo_prometheus-data", "otel-demo_jaeger-data", "otel-demo_opensearch-data")
CHARGE_LIMIT = 80
POWER_PROFILE = "balanced"
HOT_C, HOT_S = 95, 60
COOL_C, COOL_S = 90, 120
TEMP_EVERY_S, MEM_EVERY_S = 10, 60
SUSPEND_MAX_S = 60
# GNOME boşta uyutması systemd-inhibit'i dinlemiyor (gece koşusu 2026-10-24: 2 saat uyudu). `--inhibit` listesi
# iki nokta üst üsteyle ayrılır (yardım metni virgül diyor ama virgüllü liste yok sayılıyor).
GNOME_INHIBIT = ["gnome-session-inhibit", "--inhibit", "suspend:idle", "--reason", "aiops_rca scenario_runner"]

# C2 (DECISIONS 2026-10-23): 11 katalog senaryosu, üçü iki seviyede, + loadGeneratorFloodHomepage = 15 koşu.
# kind: flagd Resolve<kind>; context: doğrulamada flagd'ye giden bağlam; target: defaultVariant yerine yazılan
# targeting dalı (productCatalogFailure tek üründe: OTEL_DEMO "Flag'i açıp kapatma").
PCF_CONTEXT = {"product_id": "OLJCESPC7Z"}
SCENARIOS = [
    {"flag": "adFailure", "variant": "on", "kind": "Boolean", "root": "ad"},
    {"flag": "adHighCpu", "variant": "on", "kind": "Boolean", "root": "ad"},
    {"flag": "adManualGc", "variant": "on", "kind": "Boolean", "root": "ad"},
    {"flag": "cartFailure", "variant": "10%", "kind": "Float", "root": "cart"},
    {"flag": "cartFailure", "variant": "50%", "kind": "Float", "root": "cart"},
    {"flag": "emailMemoryLeak", "variant": "100x", "kind": "Int", "root": "email"},
    {"flag": "emailMemoryLeak", "variant": "1000x", "kind": "Int", "root": "email"},
    {"flag": "paymentFailure", "variant": "10%", "kind": "Float", "root": "payment"},
    {"flag": "paymentFailure", "variant": "50%", "kind": "Float", "root": "payment"},
    {"flag": "paymentUnreachable", "variant": "on", "kind": "Boolean", "root": "checkout"},
    {"flag": "productCatalogFailure", "variant": "on", "kind": "Boolean", "root": "product-catalog",
     "context": PCF_CONTEXT, "target": 1},
    {"flag": "productCatalogLockContention", "variant": "on", "kind": "Boolean", "root": "product-catalog"},
    {"flag": "recommendationCacheFailure", "variant": "on", "kind": "Boolean", "root": "recommendation"},
    {"flag": "intlShippingSlowdown", "variant": "10sec", "kind": "Int", "root": "shipping"},
    # Sadece sızıntı kontrolü (vaka değil, noise_layer); kök neden servisi yok.
    {"flag": "loadGeneratorFloodHomepage", "variant": "on", "kind": "Int", "root": None},
]


def scenario_id(s: dict) -> str:
    return f"{s['flag']}_{s['variant'].replace('%', 'pct')}"


BY_ID = {scenario_id(s): s for s in SCENARIOS}


def utc_ns() -> int:
    return time.time_ns()


def sleep_offset_s() -> float:
    """Açılıştan beri uykuda geçen toplam süre (sn): CLOCK_BOOTTIME − CLOCK_MONOTONIC."""
    return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()


def iso(ns: int | None) -> str | None:
    if ns is None:
        return None
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Invalid(Exception):
    """Koşu geçersiz; sebep mesajda."""


class Overheat(Invalid):
    pass


# --- makine -------------------------------------------------------------------------------------------------

def read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def pkg_temp_c() -> float | None:
    for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
        if read(f"{zone}/type") == "x86_pkg_temp":
            value = read(f"{zone}/temp")
            return int(value) / 1000 if value else None
    return None


def gnome_inhibited() -> bool:
    """Koşucunun GNOME engeli (suspend dahil) şu an listede mi."""
    try:
        out = subprocess.run(["gnome-session-inhibit", "--list"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return any(GNOME_INHIBIT[4] in line and "suspend" in line for line in out.splitlines())


def monitoring_gb() -> float | None:
    """İzleme volume'lerinin toplamı (GB, ondalık); henüz yaratılmamış volume 0. Docker okunamazsa None.

    `docker system df -v` boyutu ondalık birimle yazar (ör. "1.171GB"); geçici konteynerde `du` ile aynı çıktı
    (depolama D2)."""
    try:
        p = subprocess.run(["docker", "system", "df", "-v", "--format", "json"],
                           capture_output=True, text=True, timeout=120)
        volumes = json.loads(p.stdout)["Volumes"] if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
        volumes = None
    if volumes is None:
        return None
    units = {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}
    total = 0.0
    for v in volumes:
        if v.get("Name") in MONITORING_VOLUMES:
            m = re.fullmatch(r"([\d.]+)\s*([kMGT]?B)", v.get("Size", ""))
            if not m:
                return None
            total += float(m.group(1)) * units[m.group(2)]
    return total / 1e9


def guards() -> dict:
    ac = [read(str(p / "online")) for p in Path("/sys/class/power_supply").glob("AC*")]
    try:
        profile = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        profile = None
    free_gb = shutil.disk_usage(Path.home()).free / 1e9
    mon_gb = monitoring_gb()
    g = {
        "ac_online": ac[0] if ac else None,
        "charge_limit": read("/sys/class/power_supply/BAT0/charge_control_end_threshold"),
        "battery_pct": read("/sys/class/power_supply/BAT0/capacity"),
        "pkg_temp_c": pkg_temp_c(),
        "free_disk_gb": round(free_gb, 1),
        "monitoring_gb": round(mon_gb, 2) if mon_gb is not None else None,
        "power_profile": profile,
        "inhibited": os.environ.get("SCENARIO_RUNNER_INHIBITED") == "1",
        "gnome_inhibited": gnome_inhibited(),
    }
    problems = []
    if g["ac_online"] != "1":
        problems.append("not on AC power")
    if g["charge_limit"] != str(CHARGE_LIMIT):
        problems.append(f"charge limit is {g['charge_limit']}, want {CHARGE_LIMIT}")
    if g["pkg_temp_c"] is None or g["pkg_temp_c"] >= COOL_C:
        problems.append(f"x86_pkg_temp {g['pkg_temp_c']} (want < {COOL_C})")
    if free_gb < MIN_FREE_GB:
        problems.append(f"free disk {g['free_disk_gb']} GB < {MIN_FREE_GB}")
    if mon_gb is None:
        problems.append("monitoring volume size unknown (docker system df)")
    elif mon_gb > MAX_MONITORING_GB:
        problems.append(f"monitoring volumes {g['monitoring_gb']} GB > {MAX_MONITORING_GB:g}")
    if profile != POWER_PROFILE:
        problems.append(f"power profile {profile}, want {POWER_PROFILE}")
    if not g["inhibited"]:
        problems.append("not under systemd-inhibit")
    if not g["gnome_inhibited"]:
        problems.append("no gnome-session-inhibit suspend inhibitor")
    g["problems"] = problems
    return g


class Monitor(threading.Thread):
    """10 sn'de bir sıcaklık, dakikada bir collector belleği; 95 °C üstü 1 dk'dan uzun sürerse `hot` kurulur."""

    def __init__(self, mem_file: Path):
        super().__init__(daemon=True)
        self.mem_file = mem_file
        self.stop_event = threading.Event()
        self.hot = threading.Event()
        self.max_temp = None
        self.peak_mem_mib = None
        self.mem_samples = 0

    def run(self) -> None:
        hot_since = None
        last_mem = 0.0
        while not self.stop_event.is_set():
            t = pkg_temp_c()
            if t is not None:
                self.max_temp = t if self.max_temp is None else max(self.max_temp, t)
                if t > HOT_C:
                    hot_since = hot_since or time.monotonic()
                    if time.monotonic() - hot_since > HOT_S:
                        self.hot.set()
                else:
                    hot_since = None
            if time.monotonic() - last_mem >= MEM_EVERY_S:
                last_mem = time.monotonic()
                self.sample_mem()
            self.stop_event.wait(TEMP_EVERY_S)

    def sample_mem(self) -> None:
        try:
            out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", "otel-collector"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return
        m = re.match(r"([\d.]+)\s*([KMG]i?B)", out)
        if not m:
            return
        mib = float(m.group(1)) * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "KB": 1 / 1024, "MB": 1, "GB": 1024}[m.group(2)]
        self.peak_mem_mib = mib if self.peak_mem_mib is None else max(self.peak_mem_mib, mib)
        self.mem_samples += 1
        with self.mem_file.open("a") as f:
            f.write(f"{iso(utc_ns())}\t{mib:.1f}\n")


# --- demo ---------------------------------------------------------------------------------------------------

def http(method: str, url: str, body=None, timeout: int = 20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def container_count() -> int | None:
    try:
        q = urllib.parse.quote("count(container_uptime_seconds)")
        r = http("GET", f"{PROMETHEUS}/api/v1/query?query={q}")
        return int(float(r["data"]["result"][0]["value"][1])) if r["data"]["result"] else None
    except (OSError, ValueError, KeyError, IndexError):
        return None


def scheduler_state() -> str:
    page = http("GET", f"{FLAGD_UI}/feature/scheduler")
    if "Scheduler stopped" in page:
        return "stopped"
    return "RUNNING" if "Scheduler running" in page else "UNKNOWN"


def resolve(s: dict) -> dict:
    return http("POST", f"{FLAGD_UI}/flagservice/flagd.evaluation.v1.Service/Resolve{s['kind']}",
                {"flagKey": s["flag"], "context": s.get("context", {})})


def set_flag(s: dict, variant: str) -> tuple[int, int | None, dict | None]:
    """Flag'i yazar, flagd'den doğrular. (yazma zamanı, doğrulama zamanı ya da None, son cevap)."""
    cfg = http("GET", f"{FLAGD_UI}/feature/api/read")
    flag = cfg["flags"][s["flag"]]
    if "target" in s:
        flag["targeting"]["if"][s["target"]] = variant
    else:
        flag["defaultVariant"] = variant
    written = utc_ns()
    http("POST", f"{FLAGD_UI}/feature/api/write", {"data": cfg})
    answer = None
    for _ in range(15):
        time.sleep(1)
        try:
            answer = resolve(s)
        except OSError:
            continue
        if isinstance(answer, dict) and answer.get("variant") == variant:
            return written, utc_ns(), answer
    return written, None, answer


def split_restarts(start: dict, end: dict, expected: set) -> tuple[list, list]:
    """Başlangıç ve bitiş konteyner durumlarından (beklenmeyen, beklenen) yeniden başlama / durma listeleri."""
    unexpected, seen = [], []
    for name, st in end.items():
        old = start.get(name)
        changed = old is None or st["restarts"] != old["restarts"] or st["started"] != old["started"] \
            or (old["running"] and not st["running"]) or (st["oom"] and not old["oom"])
        if changed:
            (seen if name in expected else unexpected).append({"container": name, "start": old, "end": st})
    return unexpected, seen


def containers() -> dict[str, dict]:
    ids = subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True).stdout.split()
    if not ids:
        return {}
    fmt = "{{.Name}}\t{{.RestartCount}}\t{{.State.OOMKilled}}\t{{.State.Running}}\t{{.State.StartedAt}}"
    out = subprocess.run(["docker", "inspect", "--format", fmt, *ids], capture_output=True, text=True).stdout
    result = {}
    for line in out.splitlines():
        name, restarts, oom, running, started = line.split("\t")
        result[name.lstrip("/")] = {"restarts": int(restarts), "oom": oom == "true", "running": running == "true",
                                    "started": started}
    return result


def demo(cmd: str, log) -> int:
    args = [str(OTEL_DEMO), cmd] + (["--raw"] if cmd == "up" else [])
    p = subprocess.run(args, capture_output=True, text=True)
    log(f"otel_demo.sh {cmd}: exit {p.returncode}")
    for line in (p.stdout + p.stderr).splitlines()[-15:]:
        log(f"  {line}")
    return p.returncode


# --- pencere ------------------------------------------------------------------------------------------------

TS = re.compile(rb'"(?:startTimeUnixNano|timeUnixNano|observedTimeUnixNano)":"(\d+)"')
# Kaydın kendi zamanı (kapsama kontrolü; DECISIONS 2026-10-24): izlerde span başlangıcı, metriklerde veri noktası
# zamanı (startTimeUnixNano süreç başlangıcıdır, sayılmaz). Baştaki tırnak `startTimeUnixNano`'yu dışarıda bırakır.
OWN_TIME = {"traces": re.compile(rb'"startTimeUnixNano":"(\d+)"'), "metrics": re.compile(rb'"timeUnixNano":"(\d+)"')}


def log_times(line: bytes) -> list[int]:
    """Loglarda kaydın zamanı: timeUnixNano, 0 ya da yoksa observedTimeUnixNano."""
    times = []
    for rl in json.loads(line).get("resourceLogs", []):
        for sl in rl.get("scopeLogs", []):
            for rec in sl.get("logRecords", []):
                t = int(rec.get("timeUnixNano", 0)) or int(rec.get("observedTimeUnixNano", 0))
                if t:
                    times.append(t)
    return times


def copy_window(lo: int, hi: int, dest: Path, start: int) -> dict:
    """telemetry/{raw,filtered}/*.jsonl'dan zamanlarından biri [lo, hi] içinde olan satırları kopyalar.

    Döner: {"<base>/<sinyal>": {bytes, mb_per_min, oldest_utc, covered}}. covered: kaynak dosyalardaki en eski
    kaydın kendi zamanı ≤ start (pencere başı = normal başlangıcı; döndürme pencerenin başını silmemiş). Kopya
    lo'dan başlar (normal − 2 dk); bu pay kontrolde aranmaz: koşudan önce raw boşsa ilk kayıt collector açılışıdır.
    """
    info = {}
    minutes = (hi - lo) / 60e9
    for base in ("raw", "filtered"):
        (dest / base).mkdir(parents=True, exist_ok=True)
        outs, oldest = {}, {}
        for path in sorted((TELEMETRY / base).glob("*.jsonl")):
            signal = path.name.split("-")[0].split(".")[0]  # traces.jsonl, traces-<zaman>-size.jsonl
            if signal not in outs:
                outs[signal] = (dest / base / f"{signal}.jsonl").open("wb")
            out = outs[signal]
            with path.open("rb") as f:
                for line in f:
                    own = log_times(line) if signal == "logs" else [int(t) for t in OWN_TIME[signal].findall(line)]
                    if own:
                        oldest[signal] = min(oldest.get(signal, own[0]), *own)
                    if any(lo <= int(t) <= hi for t in TS.findall(line)):
                        out.write(line)
        for signal in ("traces", "metrics", "logs"):
            if signal in outs:
                outs[signal].close()
            size = (dest / base / f"{signal}.jsonl").stat().st_size if signal in outs else 0
            info[f"{base}/{signal}"] = {"bytes": size, "mb_per_min": round(size / 1e6 / minutes, 2),
                                        "oldest_utc": iso(oldest.get(signal)),
                                        "covered": signal in oldest and oldest[signal] <= start}
    return info


# --- koşu ---------------------------------------------------------------------------------------------------

def run_one(s: dict, attempt: int) -> dict:
    sid = scenario_id(s)
    d = OUT / f"{sid}_{attempt}"
    if d.exists():
        raise SystemExit(f"error: {d} exists; not overwriting")
    d.mkdir(parents=True)
    log_file = (d / "runner.log").open("a")

    def log(msg: str) -> None:
        line = f"{iso(utc_ns())} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    record = {
        "scenario": sid, "flag": s["flag"], "variant": s["variant"], "kind": s["kind"],
        "context": s.get("context"), "targeting_index": s.get("target"), "root_cause_service": s["root"],
        "attempt": attempt, "valid": False, "invalid_reasons": [],
        "times_utc": {}, "container_count": {}, "collector_restarted_before_normal": False,
        "scheduler": None, "flag_on": None, "flag_off": None, "restarts_in_window": [], "expected_restarts": [],
        "suspended_s": None, "guards_before": guards(), "max_pkg_temp_c": None, "overheat": False,
        "collector_mem_peak_mib": None, "collector_mem_samples": 0, "window": {}, "coverage_short": False,
    }
    times = record["times_utc"]

    def mark(key: str) -> int:
        ns = utc_ns()
        times[key] = iso(ns)
        log(key)
        return ns

    def save() -> None:
        (d / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n")

    monitor = Monitor(d / "collector_mem.tsv")
    flag_on_set = False
    normal_ns = flag_off_ns = None
    try:
        log(f"run {sid} attempt {attempt}; guards {record['guards_before']}")
        if record["guards_before"]["problems"]:
            raise Invalid("guards: " + "; ".join(record["guards_before"]["problems"]))
        mark("start")
        monitor.start()
        if demo("up", log) != 0:
            raise Invalid("otel_demo.sh up failed")
        mark("demo_up")

        def wait_count(seconds: int) -> int | None:
            end = time.monotonic() + seconds
            n = None
            while time.monotonic() < end:
                n = container_count()
                if n == CONTAINERS:
                    return n
                time.sleep(10)
            return n

        n = wait_count(WAIT_CONTAINERS_S[0])
        if n != CONTAINERS:
            log(f"container count {n}; restarting collector")
            subprocess.run(["docker", "restart", "otel-collector"], capture_output=True)
            record["collector_restarted_before_normal"] = True
            n = wait_count(WAIT_CONTAINERS_S[1])
        record["container_count"]["before_normal"] = n
        if n != CONTAINERS:
            raise Invalid(f"container count {n}, want {CONTAINERS}")
        record["scheduler"] = scheduler_state()
        if record["scheduler"] != "stopped":
            raise Invalid(f"flagd-ui scheduler {record['scheduler']}")
        before = resolve(s)
        if not isinstance(before, dict) or before.get("variant") != "off":
            raise Invalid(f"flag not off before normal: {before}")
        start_state = containers()
        (d / "containers_start.txt").write_text(json.dumps(start_state, indent=1) + "\n")

        def wait(seconds: int) -> None:
            if monitor.hot.wait(seconds):
                raise Overheat(f"x86_pkg_temp above {HOT_C} °C for more than {HOT_S} s")

        normal_ns = mark("normal_start")
        slept_before = sleep_offset_s()
        wait(NORMAL_S)
        record["container_count"]["at_flag_on"] = container_count()
        flag_on_set = True
        written, verified, answer = set_flag(s, s["variant"])
        times["flag_on_write"], times["flag_on_verified"] = iso(written), iso(verified)
        record["flag_on"] = answer
        log(f"flag on {s['flag']}={s['variant']}: verified {iso(verified)} {json.dumps(answer)}")
        if verified is None:
            raise Invalid("flag on not verified")
        wait(FLAG_S)
        record["container_count"]["at_flag_off"] = container_count()
        written, verified, answer = set_flag(s, "off")
        flag_on_set = False
        flag_off_ns = written
        record["suspended_s"] = round(sleep_offset_s() - slept_before, 1)
        times["flag_off_write"], times["flag_off_verified"] = iso(written), iso(verified)
        record["flag_off"] = answer
        log(f"flag off: verified {iso(verified)} {json.dumps(answer)}")
        if verified is None:
            raise Invalid("flag off not verified")

        end_state = containers()
        (d / "containers_end.txt").write_text(json.dumps(end_state, indent=1) + "\n")
        expected = {s["root"]} if s["root"] else set()
        record["restarts_in_window"], record["expected_restarts"] = split_restarts(start_state, end_state, expected)
        reasons = []
        if record["suspended_s"] > SUSPEND_MAX_S:
            reasons.append(f"machine slept {record['suspended_s']} s between normal start and flag off")
        if record["restarts_in_window"]:
            reasons.append("unexpected restart/stop in window: "
                           + ", ".join(e["container"] for e in record["restarts_in_window"]))
        if reasons:
            raise Invalid("; ".join(reasons))
        record["valid"] = True
    except Overheat as e:
        record["overheat"] = True
        record["invalid_reasons"].append(str(e))
        log(f"INVALID: {e}")
    except Invalid as e:
        record["invalid_reasons"].append(str(e))
        log(f"INVALID: {e}")
    except Exception as e:  # beklenmeyen hata da kayda girer, demo kapatılır
        record["invalid_reasons"].append(f"error: {type(e).__name__}: {e}")
        log(f"ERROR: {type(e).__name__}: {e}")
    finally:
        if flag_on_set:
            try:
                written, verified, answer = set_flag(s, "off")
                record["flag_off"] = answer
                times["flag_off_write"], times["flag_off_verified"] = iso(written), iso(verified)
                log(f"flag off after abort: verified {iso(verified)}")
            except Exception as e:
                log(f"flag off after abort failed: {e}")
        if "demo_up" in times or "start" in times:
            demo("down", log)
            mark("demo_down")
        monitor.stop_event.set()
        if monitor.is_alive():
            monitor.join(timeout=60)
        record["max_pkg_temp_c"] = monitor.max_temp
        record["collector_mem_peak_mib"] = monitor.peak_mem_mib
        record["collector_mem_samples"] = monitor.mem_samples
        if record["valid"]:
            lo, hi = normal_ns - WINDOW_MARGIN_NS[0], flag_off_ns + WINDOW_MARGIN_NS[1]
            record["window"] = copy_window(lo, hi, d / "window", normal_ns)
            mark("window_copied")
            short = [k for k, v in record["window"].items() if not v["covered"]]
            if short:
                record["valid"] = False
                record["coverage_short"] = True
                for k in short:
                    record["invalid_reasons"].append(f"pencere döndürmeyle kısaldı ({k})")
                log(f"INVALID: window shortened by rotation: {short}")
        save()
        log(f"run {sid} attempt {attempt}: {'VALID' if record['valid'] else 'INVALID'}")
        log_file.close()
    return record


def next_attempt(sid: str) -> int:
    n = 1
    while (OUT / f"{sid}_{n}").exists():
        n += 1
    return n


def wait_cool() -> None:
    cool_since = None
    while True:
        t = pkg_temp_c()
        if t is not None and t < COOL_C:
            cool_since = cool_since or time.monotonic()
            if time.monotonic() - cool_since >= COOL_S:
                return
        else:
            cool_since = None
        time.sleep(TEMP_EVERY_S)


def cmd_run(ids: list[str]) -> int:
    if os.environ.get("SCENARIO_RUNNER_INHIBITED") != "1":
        env = dict(os.environ, SCENARIO_RUNNER_INHIBITED="1")
        cmd = [*GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
               "--who=aiops_rca scenario_runner", "--why=C2 scenario runs", sys.executable, *sys.argv]
        return subprocess.run(cmd, env=env).returncode
    if ids == ["all"]:
        ids = list(BY_ID)
    unknown = [i for i in ids if i not in BY_ID]
    if unknown:
        print(f"error: unknown scenario {unknown}; see 'list'", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    status = 0
    for sid in ids:
        g = guards()
        if g["problems"]:
            print(f"STOP before {sid}: guards: {'; '.join(g['problems'])}", flush=True)
            return 1
        record = run_one(BY_ID[sid], next_attempt(sid))
        # Isınma ya da döndürmeyle kısalan pencere: bir kez daha; ikincisinde kayda, karar Eren'de (2026-10-24).
        if record["overheat"] or record["coverage_short"]:
            if record["overheat"]:
                print("overheat: waiting to cool, then one more attempt", flush=True)
                wait_cool()
            g = guards()
            if g["problems"]:
                print(f"STOP before retry of {sid}: guards: {'; '.join(g['problems'])}", flush=True)
                return 1
            first = "overheat" if record["overheat"] else "coverage"
            record = run_one(BY_ID[sid], next_attempt(sid))
            if record["overheat"] or record["coverage_short"]:
                print(f"{sid}: {first} then {'overheat' if record['overheat'] else 'coverage'} again; "
                      "not retried (decision: Eren)", flush=True)
        if not record["valid"]:
            status = 1
    return status


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("list", "guards", "run") or (argv[0] == "run" and len(argv) < 2):
        print(__doc__, file=sys.stderr)
        return 2
    if argv[0] == "list":
        for sid, s in BY_ID.items():
            print(f"{sid}\t{s['kind']}\troot={s['root']}")
        return 0
    if argv[0] == "guards":
        print(json.dumps(guards(), ensure_ascii=False, indent=1))
        return 0
    return cmd_run(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
