"""Senaryo koşucusu: demoyu açar, 10 dk normal + 10 dk flag koşturur, kaydı ve telemetri penceresini saklar.

C2 kartı (HANDOFF 2026-10-23 "Planlama → Uygulama (collector C2)", 2026-10-24 "Uygulama → Uygulama (C2, ölçmeden
önce)"); vaka üretiminde de bu koşucu kullanılır.

Kullanım:
  python tools/scenario_runner.py list                 senaryoları basar
  python tools/scenario_runner.py guards               makine korumalarını basar (koşmaz)
  python tools/scenario_runner.py run <id>... | all    koşuları sırayla yürütür (gnome-session-inhibit ve
                                                       systemd-inhibit altında)
  python tools/scenario_runner.py incidents <liste>    vaka üretimi (V1): listedeki vakaları sırayla üretir
                                                       (`incident_lists/*.json`; uyku engelleri yan süreçte)

Gece koşusu systemd birimiyle (DECISIONS 2026-10-29 "Gece koşusu için systemd birimi"; örnek adı = liste adı):
  systemctl --user link ~/cerebrum2/aiops_rca/deploy/systemd/aiops-incidents@.service   (bir kez)
  systemctl --user start aiops-incidents@<ad>      incident_lists/<ad>.json
  systemctl --user stop aiops-incidents@<ad>       güvenli durdurma: hata geri alınır, flag kapanır, demo kapanır
  systemctl --user status aiops-incidents@<ad>; journalctl --user -u aiops-incidents@<ad>; gece klasöründe runner.log

Koşu başına (`~/cerebrum2/c2_runs/<senaryo>_<varyant>_<deneme>/`, repo dışı, cevap içerir):
  korumalar → `otel_demo.sh up --raw` → 22 konteyner (V2 sonrası 23: + quote-gateway) (6 dk içinde olmazsa collector yeniden başlatılır, 4 dk daha)
  → flagd-ui zamanlayıcısı kapalı ve flag kapalı → 10 dk normal → flag yaz, flagd'den doğrula → 10 dk → flag kapat,
  doğrula → konteyner yeniden başlama / OOM → `down` → telemetri penceresi `window/raw/` ve `window/filtered/`'a
  kopyalanır (döndürme eski veriyi siler; DECISIONS 2026-10-21). Ölçüm ayrı: `tools/c2_measure.py`.
  Vaka penceresinde 8080'e sadece flag yazma ve doğrulama gider; sayım 9090'dan (Prometheus).
  Koşu boyunca 10 sn'de bir `x86_pkg_temp`, dakikada bir collector belleği.

Kayıt: `run.json` (alanlar aşağıda `record`), `runner.log`, `collector_mem.tsv`, `containers_start.txt`,
`containers_end.txt`, `window/`.

Geçersiz koşu: flag doğrulanamadı, beklenen konteyner sayısı (`CONTAINERS`) yok, pencerede kök neden servisi dışında bir konteyner yeniden
başladı ya da durdu (kök neden servisinin yeniden başlaması beklenir, `expected_restarts`'a yazılır; Eren,
2026-10-24), makine normal başlangıcı ile flag kapanışı arasında 1 dk'dan uzun uyudu (`suspended_s`: CLOCK_BOOTTIME
uykuda ilerler, CLOCK_MONOTONIC ilerlemez; farkın artışı uyku süresidir), ısınma (95 °C üstünde 1 dk'dan fazla), pencere döndürmeyle kısaldı (bir {raw, filtered} × {traces, metrics,
logs} için kaynak dosyalardaki en eski kaydın kendi zamanı normal başlangıcından sonra).
Isınmada koşu kesilir, soğuyunca (90 °C altında 2 dk) baştan; döndürmede baştan. İkinci kez de olursa üçüncü kez
koşulmaz, kayda (Eren, 2026-10-24). Korumalardan biri koşu öncesi tutmazsa sıra durur.

Vaka üretimi (`incidents`, V1): akış aşağıda "vaka üretimi" bölümünde. Vaka başına snapshot
`~/cerebrum2/snapshots/<incident_id>/` (= model_view: süzülmüş `traces/metrics/logs.jsonl` + `window.json`), etiket
repoda `incidents/<incident_id>.json` (yalnız geçerli vakalar), gece klasörü `~/cerebrum2/incident_runs/<UTC>-<liste>/`
(`runner.log`, `ism.json`, her denemenin etiketi `<incident_id>.json` ve çalışma dosyaları). Geçersiz: korumalar,
konteyner sayısı (`CONTAINERS`) tutmadı, taban sağlık (enjeksiyon yapılmaz), flag doğrulanamadı, pencerede beklenmeyen yeniden başlama, uyku,
döndürme, sızıntı (gece durur), olay yok. Belirtisiz / sınırda vaka geçerli, `marks`'ta işaretli.
Taban sağlık, ısınma ve döndürmede bir kez daha.

Durdurma (`incidents`): SIGTERM ya da SIGINT gelince yarıdaki vaka "stopped by SIGTERM" sebebiyle geçersiz kaydedilir,
var olan temizlik yolundan geçilir (hata geri alınır, flag kapanır, demo kapanır), sıradaki vakaya geçilmez. Hata
uygulama, flag açma/kapama, geri alma, temizlik ve etiket yazımı korunan bölümdedir (`signals_deferred`): orada gelen
sinyal yalnız not edilir, bölüm bitince işlenir; temizlik sırasında gelen ikinci sinyal temizliği kesmez, kayda geçer.
Snapshot kesimi sırasında gelen durdurmada yarım snapshot, geçersiz vakalardaki gibi gece klasörüne taşınır.
Başlangıç kontrolü: demo konteyneri ya da `aiops-netem` yardımcı konteyneri varsa (kalıntı: duraklatılmış konteyner,
CPU sınırı, netem kuralı konteynerle yaşar) koşu başlamaz; elle temizlik komutu yazılır, koşucu silmez.

Çıkış kodu: 0 bütün koşular geçerli, 1 en az biri geçersiz ya da sıra durdu, 2 kullanım hatası, 128 + sinyal
numarası sinyalle durduruldu (143 SIGTERM, 130 SIGINT).
"""
from __future__ import annotations

import json
import os
import random
import re
import secrets
import shutil
import signal
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
CONTAINERS = 23  # 22 demo + quote-gateway (DECISIONS 2026-10-28)
WAIT_CONTAINERS_S = (360, 240)  # ilk bekleme, collector yeniden başlatıldıktan sonra
WINDOW_MARGIN_NS = (120 * 10**9, 60 * 10**9)  # normal başlangıcından önce, flag kapanışından sonra

# Makine sınırları (DECISIONS 2026-10-20)
MIN_FREE_GB = 30
MIN_SWAP_FREE_GB = 1  # DECISIONS 2026-10-27 (Jaeger): boş swap bunun altındaysa yeni vakaya başlanmaz
# İzleme volume'lerinin toplamı (depolama D2, Eren onayı 2026-10-25): ölçülen büyüme ~0,85 GB/saat, 40 GB ≈ 7 günlük
# saklamada haftada ~47 saat demo. Aşılırsa koşu başlamaz; saklama süresi eskiyi silene kadar bekle ya da volume'leri
# elle sil. AIOPS_MAX_MONITORING_GB yalnız kasıtlı kırmızı için (düşük sahte sınır).
MAX_MONITORING_GB = float(os.environ.get("AIOPS_MAX_MONITORING_GB", "40"))
MONITORING_VOLUMES = ("otel-demo_prometheus-data", "otel-demo_jaeger-data", "otel-demo_opensearch-data")
# Snapshot kökü (V1, Eren onayı 2026-10-25): toplam ≤ 20 GB (~85 vaka, ~0,23 GB/vaka); aşılırsa koşu başlamaz.
# AIOPS_MAX_SNAPSHOT_GB yalnız kasıtlı kırmızı için.
SNAPSHOTS = Path.home() / "cerebrum2" / "snapshots"
MAX_SNAPSHOT_GB = float(os.environ.get("AIOPS_MAX_SNAPSHOT_GB", "20"))
CHARGE_LIMIT = 80
POWER_PROFILE = "balanced"
HOT_C, HOT_S = 95, 60
COOL_C, COOL_S = 90, 120
TEMP_EVERY_S, MEM_EVERY_S = 10, 60
SUSPEND_MAX_S = 60
# GNOME boşta uyutması systemd-inhibit'i dinlemiyor (gece koşusu 2026-10-24: 2 saat uyudu). `--inhibit` listesi
# iki nokta üst üsteyle ayrılır (yardım metni virgül diyor ama virgüllü liste yok sayılıyor).
GNOME_INHIBIT = ["gnome-session-inhibit", "--inhibit", "suspend:idle", "--reason", "aiops_rca scenario_runner"]
INHIBIT_WHO = "aiops_rca scenario_runner"
INHIBIT_WHY = ("incident runs", "C2 scenario runs", "storage card")  # incidents / run / tools/storage_check.py
DEMO_PROJECT = "otel-demo"  # demonun compose proje adı (klon klasörü); kalıntı denetimi bu etiketle

# C2 (DECISIONS 2026-10-23): 11 katalog senaryosu, üçü iki seviyede, + loadGeneratorFloodHomepage = 15 koşu.
# kind: flagd Resolve<kind>; context: doğrulamada flagd'ye giden bağlam; target: defaultVariant yerine yazılan
# targeting dalı (productCatalogFailure tek üründe: OTEL_DEMO "Flag'i açıp kapatma").
# Doğru cevap alanları (V1; INCIDENT_CATALOG "Flag senaryoları" tablosunun aynısı, tests/test_catalog.py kontrol
# eder): fault_type, propagation_path (kenar listesi [kaynak, hedef]; dallanan yollar için), categories.
PCF_CONTEXT = {"product_id": "OLJCESPC7Z"}
SCENARIOS = [
    {"flag": "adFailure", "variant": "on", "kind": "Boolean", "root": "ad", "fault_type": "error",
     "propagation_path": [["ad", "frontend"]], "categories": []},
    {"flag": "adHighCpu", "variant": "on", "kind": "Boolean", "root": "ad", "fault_type": "resource",
     "propagation_path": [["ad", "frontend"]], "categories": ["silent"]},
    {"flag": "adManualGc", "variant": "on", "kind": "Boolean", "root": "ad", "fault_type": "resource",
     "propagation_path": [["ad", "frontend"]], "categories": ["silent"]},
    {"flag": "cartFailure", "variant": "10%", "kind": "Float", "root": "cart", "fault_type": "misconfig",
     "propagation_path": [["cart", "checkout"], ["checkout", "frontend"]], "categories": ["cascading", "partial"]},
    {"flag": "cartFailure", "variant": "50%", "kind": "Float", "root": "cart", "fault_type": "misconfig",
     "propagation_path": [["cart", "checkout"], ["checkout", "frontend"]], "categories": ["cascading", "partial"]},
    {"flag": "emailMemoryLeak", "variant": "100x", "kind": "Int", "root": "email", "fault_type": "resource",
     "propagation_path": [["email", "checkout"]], "categories": ["silent"]},
    {"flag": "emailMemoryLeak", "variant": "1000x", "kind": "Int", "root": "email", "fault_type": "resource",
     "propagation_path": [["email", "checkout"]], "categories": ["silent"]},
    {"flag": "paymentFailure", "variant": "10%", "kind": "Float", "root": "payment", "fault_type": "error",
     "propagation_path": [["payment", "checkout"], ["checkout", "frontend"]], "categories": ["cascading", "noisy"]},
    {"flag": "paymentFailure", "variant": "50%", "kind": "Float", "root": "payment", "fault_type": "error",
     "propagation_path": [["payment", "checkout"], ["checkout", "frontend"]], "categories": ["cascading", "noisy"]},
    {"flag": "paymentUnreachable", "variant": "on", "kind": "Boolean", "root": "checkout", "fault_type": "misconfig",
     "propagation_path": [["checkout", "frontend"]], "categories": ["cascading"]},
    {"flag": "productCatalogFailure", "variant": "on", "kind": "Boolean", "root": "product-catalog",
     "context": PCF_CONTEXT, "target": 1, "fault_type": "error",
     "propagation_path": [["product-catalog", "frontend"], ["product-catalog", "checkout"],
                          ["product-catalog", "recommendation"]],
     "categories": ["cascading", "partial"]},
    {"flag": "productCatalogLockContention", "variant": "on", "kind": "Boolean", "root": "product-catalog",
     "fault_type": "latency",
     "propagation_path": [["product-catalog", "frontend"], ["product-catalog", "recommendation"],
                          ["product-catalog", "checkout"]],
     "categories": ["cascading"]},
    {"flag": "recommendationCacheFailure", "variant": "on", "kind": "Boolean", "root": "recommendation",
     "fault_type": "resource", "propagation_path": [["recommendation", "frontend"]], "categories": ["silent"]},
    {"flag": "intlShippingSlowdown", "variant": "10sec", "kind": "Int", "root": "shipping", "fault_type": "latency",
     "propagation_path": [["shipping", "checkout"], ["checkout", "frontend"]], "categories": ["partial"]},
    # Kendi servisimiz quote-gateway (deploy/otel-demo/flagd-extras.json). Varyantlar c adımındaki ölçümden (Eren
    # onayı 2026-10-28): gecikme eşiği normal p95 + 20 ms (30 ms ≈ güç 1,5; 100 ms ≈ 5); sızıntı 384 KB/istek 10 dk'da
    # ~39 MiB (OOM yok, sınır 128M), 1024 KB/istek ~105 MiB (OOM). Yol ve kategoriler kalibrasyondan (HANDOFF
    # 2026-10-29); 100 ms ölçülemedi, 30 ms'ninkiyle aynı. Sızıntının kategorisi varyant başına
    # (DECISIONS 2026-10-29): 384 KB silent, 1024 KB boş (OOM yeniden başlaması çağıranlarda hata span'i üretir).
    {"flag": "quoteGatewayMisroute", "variant": "on", "kind": "Boolean", "root": "quote-gateway",
     "fault_type": "misconfig", "propagation_path": [["quote-gateway", "shipping"], ["shipping", "frontend"], ["shipping", "checkout"]], "categories": ["cascading"]},
    {"flag": "quoteGatewaySlowdown", "variant": "30ms", "kind": "Int", "root": "quote-gateway",
     "fault_type": "latency", "propagation_path": [["quote-gateway", "shipping"], ["shipping", "frontend"], ["shipping", "checkout"]], "categories": ["cascading", "silent"]},
    {"flag": "quoteGatewaySlowdown", "variant": "100ms", "kind": "Int", "root": "quote-gateway",
     "fault_type": "latency", "propagation_path": [["quote-gateway", "shipping"], ["shipping", "frontend"], ["shipping", "checkout"]], "categories": ["cascading", "silent"]},
    {"flag": "quoteGatewayMemoryLeak", "variant": "384kb", "kind": "Int", "root": "quote-gateway",
     "fault_type": "resource", "propagation_path": [["quote-gateway", "shipping"], ["shipping", "frontend"], ["shipping", "checkout"]], "categories": ["silent"]},
    {"flag": "quoteGatewayMemoryLeak", "variant": "1024kb", "kind": "Int", "root": "quote-gateway",
     "fault_type": "resource", "propagation_path": [["quote-gateway", "shipping"], ["shipping", "frontend"], ["shipping", "checkout"]], "categories": []},
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


class Stopped(Invalid):
    """Koşu SIGTERM ya da SIGINT ile durduruldu (systemctl stop, kapanma, Ctrl-C); vaka bu sebeple geçersiz."""


class signals_deferred:
    """Korunan bölüm: içerideyken gelen SIGTERM/SIGINT yalnız not edilir, bölümden çıkarken `Stopped` fırlatılır.

    Bekletme bayrakla (pthread_sigmask değil): sinyal izleme iş parçacığına düşebilir, Python işleyicisi yine ana iş
    parçacığında çalışır. Korunan bölüm dışında işleyici `Stopped`'ı hemen fırlatır. `Stopped` süreç başına bir kez
    fırlatılır; sonraki sinyaller (temizlik sırasında ikinci sinyal) yalnız `signals`'a eklenir. Bölümden başka bir
    hatayla çıkılıyorsa o hata korunur; bekleyen durdurmayı `check` ya da döngü işler."""
    signals: list[str] = []
    depth = 0
    raised = False

    @classmethod
    def handle(cls, signum, frame) -> None:
        cls.signals.append(signal.Signals(signum).name)
        if cls.depth == 0 and not cls.raised:
            cls.raised = True
            raise Stopped(f"stopped by {cls.signals[0]}")

    @classmethod
    def check(cls) -> None:
        """Bekleyen, henüz fırlatılmamış durdurma varsa (korunan bölüm dışında) fırlatır."""
        if cls.signals and not cls.raised and cls.depth == 0:
            cls.raised = True
            raise Stopped(f"stopped by {cls.signals[0]}")

    def __enter__(self) -> "signals_deferred":
        type(self).depth += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        type(self).depth -= 1
        if exc_type is None:
            type(self).check()
        return False


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


def inhibited() -> bool:
    """Bizim systemd engelimiz (sleep, block) şu an listede mi: kimlik "aiops_rca …" ve neden metni bizimkilerden biri
    (incidents, C2 run, storage_check)."""
    try:
        out = subprocess.run(["systemd-inhibit", "--list", "--no-pager", "--no-legend"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return any(line.startswith("aiops_rca ") and any(why in line for why in INHIBIT_WHY) and "sleep" in line
               and line.rstrip().endswith("block") for line in out.splitlines())


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


def swap_free_gb() -> float | None:
    """Sistemde boş swap (`/proc/meminfo` SwapFree), ondalık GB."""
    for line in (read("/proc/meminfo") or "").splitlines():
        if line.startswith("SwapFree:"):
            return round(int(line.split()[1]) * 1024 / 1e9, 2)
    return None


def snapshot_gb() -> float:
    """Snapshot kökündeki dosyaların toplamı (GB, ondalık); kök yoksa 0."""
    return sum(f.stat().st_size for f in SNAPSHOTS.rglob("*") if f.is_file()) / 1e9 if SNAPSHOTS.exists() else 0.0


def guards() -> dict:
    ac = [read(str(p / "online")) for p in Path("/sys/class/power_supply").glob("AC*")]
    try:
        profile = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        profile = None
    free_gb = shutil.disk_usage(Path.home()).free / 1e9
    mon_gb = monitoring_gb()
    snap_gb = snapshot_gb()
    swap_gb = swap_free_gb()
    g = {
        "ac_online": ac[0] if ac else None,
        "charge_limit": read("/sys/class/power_supply/BAT0/charge_control_end_threshold"),
        "battery_pct": read("/sys/class/power_supply/BAT0/capacity"),
        "pkg_temp_c": pkg_temp_c(),
        "free_disk_gb": round(free_gb, 1),
        "monitoring_gb": round(mon_gb, 2) if mon_gb is not None else None,
        "snapshot_gb": round(snap_gb, 2),
        "swap_free_gb": swap_gb,
        "power_profile": profile,
        "inhibited": inhibited(),
        "gnome_inhibited": gnome_inhibited(),
        "leftovers": leftovers(),
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
    if snap_gb > MAX_SNAPSHOT_GB:
        problems.append(f"snapshots {g['snapshot_gb']} GB > {MAX_SNAPSHOT_GB:g}")
    if swap_gb is None or swap_gb < MIN_SWAP_FREE_GB:
        problems.append(f"swap free {swap_gb} GB < {MIN_SWAP_FREE_GB}")
    if profile != POWER_PROFILE:
        problems.append(f"power profile {profile}, want {POWER_PROFILE}")
    if not g["inhibited"]:
        problems.append("not under systemd-inhibit")
    if not g["gnome_inhibited"]:
        problems.append("no gnome-session-inhibit suspend inhibitor")
    if g["leftovers"] is None:
        problems.append("leftover check failed (docker ps)")
    elif g["leftovers"]:
        paused = [c["name"] for c in g["leftovers"] if c["paused"]]
        problems.append("leftovers from a previous run: " + ", ".join(
            f"{c['name']} ({c['state']}{', paused' if c['paused'] else ''}{', cpu limit' if c['nano_cpus'] else ''})"
            for c in g["leftovers"]) + "; clean up by hand: "
            + "".join(f"docker unpause {n}; " for n in paused)
            + ("docker rm -f aiops-netem; " if any(c["name"] == "aiops-netem" for c in g["leftovers"]) else "")
            + "tools/otel_demo.sh down")
    g["problems"] = problems
    return g


def leftovers() -> list[dict] | None:
    """Demo projesinin konteynerleri (her durumda) ve `aiops-netem` yardımcı konteyneri. Boş liste: temiz; okunamazsa
    None. netem kuralı ve CPU sınırı konteynerle yaşar: konteyner yoksa onlar da yok."""
    try:
        ids = []
        for flt in (f"label=com.docker.compose.project={DEMO_PROJECT}", "name=^aiops-netem$"):
            p = subprocess.run(["docker", "ps", "-aq", "--filter", flt], capture_output=True, text=True, timeout=30)
            if p.returncode != 0:
                return None
            ids += p.stdout.split()
        if not ids:
            return []
        fmt = "{{.Name}}\t{{.State.Status}}\t{{.State.Paused}}\t{{.HostConfig.NanoCpus}}"
        p = subprocess.run(["docker", "inspect", "--format", fmt, *dict.fromkeys(ids)],
                           capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            return None
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = []
    for line in p.stdout.splitlines():
        name, state, paused, nano = line.split("\t")
        out.append({"name": name.lstrip("/"), "state": state, "paused": paused == "true", "nano_cpus": int(nano)})
    return sorted(out, key=lambda c: c["name"])


class Monitor(threading.Thread):
    """10 sn'de bir sıcaklık, dakikada bir collector belleği ve Jaeger'in kendi belleği (cgroup anon; dosya önbelleği
    hariç, depolama D2 ölçüsü) ile swap'i (`memory.swap.current`; DECISIONS 2026-10-26 Jaeger ölçütü düzeltmesi);
    95 °C üstü 1 dk'dan uzun sürerse `hot` kurulur."""

    def __init__(self, mem_file: Path):
        super().__init__(daemon=True)
        self.mem_file = mem_file
        self.stop_event = threading.Event()
        self.hot = threading.Event()
        self.max_temp = None
        self.peak_mem_mib = None
        self.mem_samples = 0
        self.min_swap_free_gb = None
        self.jaeger_anon_peak_mib = None
        self.jaeger_swap_peak_mib = None

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
        s = swap_free_gb()
        if s is not None:
            self.min_swap_free_gb = s if self.min_swap_free_gb is None else min(self.min_swap_free_gb, s)
        jaeger = cgroup_memory("jaeger")
        if jaeger and jaeger["anon_mib"] is not None:
            a = jaeger["anon_mib"]
            self.jaeger_anon_peak_mib = a if self.jaeger_anon_peak_mib is None else max(self.jaeger_anon_peak_mib, a)
        if jaeger and jaeger["swap_mib"] is not None:
            w = jaeger["swap_mib"]
            self.jaeger_swap_peak_mib = w if self.jaeger_swap_peak_mib is None else max(self.jaeger_swap_peak_mib, w)
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


def prom_max(query_metric: str, seconds: int) -> float | None:
    """Prometheus'ta son `seconds` saniyedeki tepe değer (`max_over_time`); okunamazsa None."""
    try:
        q = urllib.parse.quote(f"max(max_over_time({query_metric}[{max(int(seconds), 60)}s]))")
        r = http("GET", f"{PROMETHEUS}/api/v1/query?query={q}")
        return float(r["data"]["result"][0]["value"][1]) if r["data"]["result"] else None
    except (OSError, ValueError, KeyError, IndexError):
        return None


def prom_increase(expr: str, seconds: float) -> float | None:
    """Prometheus'ta son `seconds` saniyedeki sayaç artışı (`sum(increase(...))`). Seri yoksa 0: hata sayaçları
    (`send_failed`) hata olmadıkça hiç yazılmıyor (V2c canlı kontrol; `monitoring_health` de seri yoksa 0 sayar).
    Okunamazsa None."""
    try:
        q = urllib.parse.quote(f"sum(increase({expr}[{max(int(seconds), 60)}s]))")
        r = http("GET", f"{PROMETHEUS}/api/v1/query?query={q}")
        if r.get("status") != "success":
            return None
        return round(float(r["data"]["result"][0]["value"][1]), 1) if r["data"]["result"] else 0.0
    except (OSError, ValueError, KeyError, IndexError):
        return None


# Jaeger denemesinin gönderim sayaçları (DECISIONS 2026-10-27). Snapshot'taki `checks.monitoring_health` aynı
# sayaçları normal başı → hata kapanışı için ve yalnız geçerli vakada verir; bu okuma normal başı → vaka sonu
# (kuyruk ve geçersiz vaka dahil). Reddedilenler `monitoring_health` gibi bütün `otelcol_receiver_refused_*` (Jaeger'in
# kendi alıcısı dahil). Her metrik adı ayrı sorgulanır: `__name__` deseniyle `increase` adı düşürünce aynı etiketli
# seriler çakışıyor ve sorgu hata veriyor (V2c canlı kontrol).
_SIGNALS = ("spans", "metric_points", "log_records")
EXPORT_FAILURE_QUERIES = {
    "otlp_grpc_jaeger": [f'otelcol_exporter_send_failed_{s}_total{{exporter="otlp_grpc/jaeger"}}' for s in _SIGNALS],
    "jaeger_storage_exporter": [f'otelcol_exporter_send_failed_{s}_total{{exporter="jaeger_storage_exporter"}}'
                                for s in _SIGNALS],
    "collector_refused": [f"otelcol_receiver_refused_{s}_total" for s in _SIGNALS],
}


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
            or (old["running"] and not st["running"]) or (st["oom"] and not old["oom"]) \
            or st.get("paused", False) != old.get("paused", False)
        if changed:
            (seen if name in expected else unexpected).append({"container": name, "start": old, "end": st})
    return unexpected, seen


def containers() -> dict[str, dict]:
    ids = subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True).stdout.split()
    if not ids:
        return {}
    fmt = "{{.Name}}\t{{.RestartCount}}\t{{.State.OOMKilled}}\t{{.State.Running}}\t{{.State.StartedAt}}\t{{.State.Paused}}"
    out = subprocess.run(["docker", "inspect", "--format", fmt, *ids], capture_output=True, text=True).stdout
    result = {}
    for line in out.splitlines():
        name, restarts, oom, running, started, paused = line.split("\t")
        result[name.lstrip("/")] = {"restarts": int(restarts), "oom": oom == "true", "running": running == "true",
                                    "started": started, "paused": paused == "true"}
    return result


def demo(cmd: str, log, raw: bool = True) -> int:
    args = [str(OTEL_DEMO), cmd] + (["--raw"] if cmd == "up" and raw else [])
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


def copy_window(lo: int, hi: int, dest: Path, start: int, bases: tuple[str, ...] = ("raw", "filtered")) -> dict:
    """telemetry/{raw,filtered}/*.jsonl'dan zamanlarından biri [lo, hi] içinde olan satırları kopyalar.

    Döner: {"<base>/<sinyal>": {bytes, mb_per_min, oldest_utc, covered}}. covered: kaynak dosyalardaki en eski
    kaydın kendi zamanı ≤ start (pencere başı = normal başlangıcı; döndürme pencerenin başını silmemiş). Kopya
    lo'dan başlar (normal − 2 dk); bu pay kontrolde aranmaz: koşudan önce raw boşsa ilk kayıt collector açılışıdır.
    """
    info = {}
    minutes = (hi - lo) / 60e9
    for base in bases:
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


# --- vaka üretimi (V1) -----------------------------------------------------------------------------------------
# HANDOFF 2026-10-25 "Planlama → Uygulama (vaka üretimi V1)" ve "V1 netleştirmeler"; adlar Eren onaylı.
# Akış: korumalar → `up` (süzülmemiş kopya yok) → collector yeniden başlatılır (açılış yarışı: konteyner metrik
# alıcısı collector'dan hemen sonra başlayan konteyneri kaçırabiliyor; V1a 3. adım) → `CONTAINERS` konteyner → ısınma (up'tan
# WARMUP_S) → flag'ler kapalı, zamanlayıcı durmuş → 10 dk normal → taban sağlık (geçmezse enjeksiyon yok) → flag
# (ve noise_layer) açık 10 dk → kapat, doğrula → anonim volume'ler kaydedilir → `down` → silinir → kesim
# (snapshot = model_view: süzülmüş pencere + window.json) → kontroller → etiket.

# Zaman kalıbı yok (DECISIONS 2026-10-26, düzeltme b5740e8): normal dönem 10–14 dk, flag/hata kapandıktan sonraki
# kuyruk 1–3 dk, saniye çözünürlüğünde düzgün; tohum ve süreler etikette (`run.schedule`). Kuyruk boyunca demo açık
# kalır: veri pencere sonuna kadar sürer (kapanıştan hemen sonra biterse bitiş anı okunurdu). Kontrol pencereleri
# 10 dk kalır (C2 ölçüsü).
NORMAL_RANGE_S = (600, 840)
TAIL_RANGE_S = (60, 180)
# Kuru deneme (liste öğesinde "dry": true; V2a): kısa sabit süreler; snapshot gece klasöründe (`<id>/model_view/`),
# etiket `incidents/`'a girmez; taban sağlık kaydedilir ama enjeksiyonu durdurmaz. Sete girmez.
DRY_NORMAL_S, DRY_FAULT_S, DRY_TAIL_S = 180, 180, 60


def schedule(seed: int) -> dict:
    rnd = random.Random(seed)
    return {"seed": seed, "normal_s": rnd.randint(*NORMAL_RANGE_S), "tail_s": rnd.randint(*TAIL_RANGE_S)}


INCIDENTS = REPO / "incidents"
INCIDENT_RUNS = Path.home() / "cerebrum2" / "incident_runs"
WARMUP_S = 300
OPENSEARCH = "http://127.0.0.1:9200"


def anonymous_volumes() -> list[str]:
    """otel-demo konteynerlerine bağlı, Docker'ın anonim diye etiketlediği volume'ler (isimli volume'ler hariç)."""
    ids = subprocess.run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=otel-demo"],
                         capture_output=True, text=True).stdout.split()
    if not ids:
        return []
    out = subprocess.run(["docker", "inspect", "--format",
                          '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}', *ids],
                         capture_output=True, text=True).stdout.split()
    anon = []
    for name in sorted(set(out)):
        labels = subprocess.run(["docker", "volume", "inspect", "--format", "{{json .Labels}}", name],
                                capture_output=True, text=True).stdout.strip()
        if labels and labels != "null" and "com.docker.volume.anonymous" in json.loads(labels):
            anon.append(name)
    return anon


def remove_volumes(names: list[str]) -> dict[str, int]:
    """Volume'leri tek tek siler; ad → `docker volume rm` çıkış kodu."""
    return {n: subprocess.run(["docker", "volume", "rm", n], capture_output=True).returncode for n in names}


def ism_explain() -> dict:
    """OpenSearch ISM: her otel-logs indeksine bağlı kural (gecede bir, ilk `up`'tan sonra)."""
    try:
        r = http("GET", f"{OPENSEARCH}/_plugins/_ism/explain/otel-logs-*", timeout=30)
    except OSError as e:
        return {"error": str(e), "pass": False}
    indices = {k: v.get("index.plugins.index_state_management.policy_id") or v.get("policy_id")
               for k, v in r.items() if isinstance(v, dict)}
    return {"indices": indices, "pass": bool(indices) and all(v == "otel-logs-retention" for v in indices.values()),
            "raw": r}


def new_incident_id() -> str:
    while True:
        iid = "inc-" + secrets.token_hex(4)
        if not (SNAPSHOTS / iid).exists() and not (INCIDENTS / f"{iid}.json").exists():
            return iid


def cut_snapshot(lo: int, hi: int, work: Path, snap: Path, start: int) -> dict:
    """Süzülmüş pencereyi kopyalar (work/filtered/), sonra snapshot klasörüne taşır; window.json yazar.
    Döner: sinyal başına kopya bilgisi (copy_window), kapsama dahil."""
    info = copy_window(lo, hi, work, start, bases=("filtered",))
    snap.mkdir(parents=True)
    for signal in ("traces", "metrics", "logs"):
        src = work / "filtered" / f"{signal}.jsonl"
        if src.exists():
            shutil.move(src, snap / f"{signal}.jsonl")
    (work / "filtered").rmdir()
    (snap / "window.json").write_text(json.dumps({"start": iso(lo), "end": iso(hi)}) + "\n")
    return {k.split("/", 1)[1]: v for k, v in info.items()}


def cgroup_memory(container: str) -> dict | None:
    """Konteynerin cgroup v2 belleği (MiB): tepe (`memory.peak`, dosya önbelleği dahil), şu anki toplam
    (`memory.current`; bellek sınırının saydığı, cgroup v2'de `container.memory.usage.total`), anon, dosya, swap
    (`memory.swap.current`) ve swap tepesi (`memory.swap.peak`), memory.events (max, oom, oom_kill). Konteyner
    yoksa None."""
    cid = subprocess.run(["docker", "inspect", "--format", "{{.Id}}", container],
                         capture_output=True, text=True).stdout.strip()
    base = Path(f"/sys/fs/cgroup/system.slice/docker-{cid}.scope")
    peak, events, stat, current, swap, swap_peak = (
        read(str(base / f)) for f in ("memory.peak", "memory.events", "memory.stat", "memory.current",
                                      "memory.swap.current", "memory.swap.peak"))
    if not cid or peak is None or events is None:
        return None
    ev = dict(line.split() for line in events.splitlines())
    st = dict(line.split() for line in (stat or "").splitlines())

    def mib(v: str | None) -> float | None:
        return round(int(v) / 2**20, 1) if v is not None else None
    return {"peak_mib": mib(peak), "current_mib": mib(current), "anon_mib": mib(st.get("anon")),
            "file_mib": mib(st.get("file")), "swap_mib": mib(swap), "swap_peak_mib": mib(swap_peak),
            "max": int(ev.get("max", 0)), "oom": int(ev.get("oom", 0)), "oom_kill": int(ev.get("oom_kill", 0))}


def _cpu_usec(container: str) -> int | None:
    """Konteynerin cgroup v2 `cpu.stat` usage_usec değeri; yoksa None."""
    cid = subprocess.run(["docker", "inspect", "--format", "{{.Id}}", container],
                         capture_output=True, text=True).stdout.strip()
    for line in (read(f"/sys/fs/cgroup/system.slice/docker-{cid}.scope/cpu.stat") or "").splitlines():
        if cid and line.startswith("usage_usec "):
            return int(line.split()[1])
    return None


def versions() -> dict:
    def git(path: Path) -> str | None:
        p = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
        return p.stdout.strip() or None
    demo_dir = Path.home() / "cerebrum2" / "otel-demo"
    env = {}
    for line in (demo_dir / ".env").read_text().splitlines():
        m = re.match(r"^(\w+_IMAGE|IMAGE_VERSION|DEMO_VERSION)=(.*)$", line)
        if m:
            env[m.group(1)] = m.group(2)
    return {"repo_commit": git(REPO), "demo_commit": git(demo_dir), "demo_env": env}


# Altyapı hataları (V2; DECISIONS 2026-10-26 "Altyapı hata yöntemleri", "Ağ hatası aracı", "Enjeksiyon izi kuralı";
# adlar Eren onaylı). Her hata: önce hedefin durumu okunur, uygulanır ve geri okunur; temizlikte önceki değer geri
# yazılır, geri okunur; hedef çalışıyor, dondurulmamış, IP'si var ve `STABLE_S` boyunca yeniden başlama sayısı sabit
# olmalı (DECISIONS 2026-10-26 "Bellek hatası"). Temizlik doğrulanamazsa vaka geçersiz, gece durur.
# param: cpuThrottle CPU sayısı ("0.1"); memoryLimit toplam kullanıma (`memory.current`: anon + dosya + çekirdek payı;
# sınırın saydığı) oran ("0.8"; --memory-swap = --memory);
# networkDelay "200ms"; packetLoss "20%"; containerStop ve containerPause "on".
# CPU'nun geri alınması: `docker update --cpus 0` sınırı kaldırmıyor (V2a denemesi: çıkış 0, NanoCpus değişmedi);
# önceki değer 0 (sınırsız) ise makinenin çekirdek sayısı yazılır. Konteynerler her vakanın sonunda `down` ile
# silindiği için bir sonraki vakaya taşınmaz.
INFRA_FAULTS = {
    "containerStop": {"fault_type": "unavailable", "method": "docker stop"},
    "containerPause": {"fault_type": "unavailable", "method": "docker pause"},
    "cpuThrottle": {"fault_type": "resource", "method": "docker update --cpus"},
    "memoryLimit": {"fault_type": "resource", "method": "docker update --memory --memory-swap"},
    "networkDelay": {"fault_type": "latency", "method": "tc netem delay"},
    "packetLoss": {"fault_type": "error", "method": "tc netem loss"},
}
# Altyapı vakalarının doğru cevap alanları (`SCENARIOS`'un eşi; DECISIONS 2026-10-28, Eren seçenek A). Kaynak
# INCIDENT_CATALOG "Kendi altyapı hatalarımız" tablosu (yol V2b destek vakalarının izlerinden, kategoriler katalogdaki
# tanımlarla); tests/test_catalog.py ikisinin aynı olduğunu sınar. Tabloda olmayan (hata, hedef) çiftinde boş kalır.
INFRA_ANSWERS = [
    {"fault": "networkDelay", "target": "cart",
     "propagation_path": [["cart", "frontend"], ["cart", "checkout"]], "categories": ["cascading", "silent"]},
    {"fault": "networkDelay", "target": "quote",
     "propagation_path": [["quote", "quote-gateway"], ["quote-gateway", "shipping"], ["shipping", "frontend"],
                          ["shipping", "checkout"]],
     "categories": ["cascading", "silent"]},
    {"fault": "packetLoss", "target": "shipping",
     "propagation_path": [["shipping", "frontend"], ["shipping", "checkout"]], "categories": ["cascading", "silent"]},
    {"fault": "packetLoss", "target": "currency",
     "propagation_path": [["currency", "frontend"], ["currency", "checkout"]], "categories": ["cascading", "silent"]},
    {"fault": "cpuThrottle", "target": "product-catalog",
     "propagation_path": [["product-catalog", "frontend"], ["product-catalog", "recommendation"],
                          ["product-catalog", "checkout"]], "categories": ["cascading", "silent"]},
    {"fault": "cpuThrottle", "target": "recommendation",
     "propagation_path": [["recommendation", "frontend"]], "categories": ["cascading"]},
    {"fault": "containerPause", "target": "cart",
     "propagation_path": [["cart", "frontend"], ["cart", "checkout"]], "categories": ["cascading"]},
    {"fault": "containerPause", "target": "quote",
     "propagation_path": [["quote", "quote-gateway"], ["quote-gateway", "shipping"], ["shipping", "frontend"],
                          ["shipping", "checkout"]],
     "categories": ["cascading"]},
    {"fault": "containerStop", "target": "recommendation",
     "propagation_path": [["recommendation", "frontend"]], "categories": ["cascading"]},
    {"fault": "containerStop", "target": "currency",
     "propagation_path": [["currency", "frontend"], ["currency", "checkout"]], "categories": ["cascading"]},
]
# İmajlar CI'da derlenir, GHCR'da; digest'le sabit (DECISIONS 2026-10-29 "İmajlar GHCR'da"; .github/workflows/images.yml,
# ilk gönderim main 1b33aab). GATEWAY_IMAGE compose.extras.yaml'dakiyle aynı olmalı (tests/test_quote_gateway.py).
GATEWAY_IMAGE = "ghcr.io/erenbezek/aiops-quote-gateway@sha256:333902cf518d8c059b2a880c753a0515f61350762e8859dbc5f65e9a7d83c9e9"
NETEM_IMAGE = "ghcr.io/erenbezek/aiops-netem@sha256:2651be1375920341fb2cc508bb29a42569d8e93723610763689943e403fa6201"
NETEM_WORD = {"networkDelay": "delay", "packetLoss": "loss"}
STABLE_S = 30
PARAM_RE = {"containerStop": r"on", "containerPause": r"on", "cpuThrottle": r"\d+(\.\d+)?",
            "memoryLimit": r"0\.\d+", "networkDelay": r"\d+ms", "packetLoss": r"\d+(\.\d+)?%"}


def _inspect(target: str) -> dict | None:
    """Hedefin hata için gereken durumu; konteyner yoksa None."""
    p = subprocess.run(["docker", "inspect", target], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    d = json.loads(p.stdout)[0]
    st, hc = d["State"], d["HostConfig"]
    return {"running": st["Running"], "paused": st["Paused"], "restarts": d["RestartCount"],
            "oom_killed": st["OOMKilled"], "nano_cpus": hc["NanoCpus"], "memory": hc["Memory"],
            "memory_swap": hc["MemorySwap"],
            "ips": sorted(n["IPAddress"] for n in d["NetworkSettings"]["Networks"].values() if n.get("IPAddress"))}


def _tc(target: str, *args: str) -> subprocess.CompletedProcess:
    """Yardımcı imajla hedefin ağ ad alanında `tc`; yalnız NET_ADMIN, iş bitince konteyner silinir."""
    return subprocess.run(["docker", "run", "--rm", "--name", "aiops-netem", "--network", f"container:{target}",
                           "--cap-add", "NET_ADMIN", NETEM_IMAGE, *args], capture_output=True, text=True, timeout=120)


def apply_fault(fault: str, target: str, param: str) -> dict:
    """Hatayı uygular. Döner: durum kaydı (`run.fault_state`); `applied_ok` False ise vaka geçersiz sayılmalı."""
    before = _inspect(target)
    state = {"fault": fault, "target": target, "param": param, "before": before, "applied": None,
             "applied_ok": False, "reverted": None, "after": None, "stable": None, "verified": False}
    if before is None or not before["running"] or before["paused"]:
        state["applied"] = {"error": "target not running before fault"}
        return state
    if fault in NETEM_WORD:
        word = NETEM_WORD[fault]
        shown = _tc(target, "qdisc", "show", "dev", "eth0").stdout.strip()
        before["qdisc"] = shown
        if "netem" in shown:
            state["applied"] = {"error": "netem already present", "qdisc": shown}
            return state
        p = _tc(target, "qdisc", "add", "dev", "eth0", "root", "netem", word, param)
        shown = _tc(target, "qdisc", "show", "dev", "eth0").stdout.strip()
        state["applied"] = {"exit": p.returncode, "stderr": p.stderr.strip()[-300:], "qdisc": shown}
        state["applied_ok"] = p.returncode == 0 and f"{word} {param}" in shown
        return state
    if fault == "containerStop":
        cmd = ["docker", "stop", target]
    elif fault == "containerPause":
        cmd = ["docker", "pause", target]
    elif fault == "cpuThrottle":
        cmd = ["docker", "update", "--cpus", param, target]
    else:  # memoryLimit
        mem = cgroup_memory(target) or {}
        usage = mem.get("current_mib")
        if usage is None:
            state["applied"] = {"error": "memory usage unreadable"}
            return state
        limit = max(int(float(param) * usage * 2**20), 6 * 2**20)  # Docker'ın alt sınırı 6 MiB
        state["applied"] = {"usage_mib": usage, "anon_mib": mem.get("anon_mib"), "file_mib": mem.get("file_mib"),
                            "limit_bytes": limit}
        cmd = ["docker", "update", "--memory", str(limit), "--memory-swap", str(limit), target]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    a = _inspect(target) or {}
    state["applied"] = {**(state["applied"] or {}), "exit": p.returncode, "stderr": p.stderr.strip()[-300:],
                        "state": a}
    state["applied_ok"] = p.returncode == 0 and {
        "containerStop": lambda: not a.get("running"),
        "containerPause": lambda: bool(a.get("paused")),
        "cpuThrottle": lambda: a.get("nano_cpus") == round(float(param) * 1e9),
        "memoryLimit": lambda: a.get("memory") == state["applied"]["limit_bytes"]
        and a.get("memory_swap") == state["applied"]["limit_bytes"],
    }[fault]()
    return state


def revert_fault(state: dict) -> dict:
    """Hatayı geri alır, geri okur; `verified`: önceki değer geri geldi, hedef çalışıyor, dondurulmamış, IP'si var ve
    `STABLE_S` boyunca yeniden başlama sayısı değişmedi (`stable`; `after` bu sürenin sonundaki okuma)."""
    fault, target, before = state["fault"], state["target"], state["before"]
    spec_ok, extra = False, {}
    if fault in NETEM_WORD:
        p = _tc(target, "qdisc", "del", "dev", "eth0", "root")
        shown = _tc(target, "qdisc", "show", "dev", "eth0").stdout.strip()
        extra, spec_ok = {"qdisc": shown}, "netem" not in shown
    else:
        if fault == "containerStop":
            cmd = ["docker", "start", target]
        elif fault == "containerPause":
            cmd = ["docker", "unpause", target]
        elif fault == "cpuThrottle":
            value = before["nano_cpus"] or (os.cpu_count() or 1) * 10**9
            extra = {"nano_cpus_written": value}
            cmd = ["docker", "update", "--cpus", f"{value / 1e9:g}", target]
        else:  # memoryLimit: bellek ve swap birlikte
            cmd = ["docker", "update", "--memory", str(before["memory"]), "--memory-swap",
                   str(before["memory_swap"]), target]
        for _ in range(3):  # OOM döngüsünde konteyner o an yeniden başlıyor olabilir
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if p.returncode == 0:
                break
            time.sleep(5)
    def up(x: dict | None) -> bool:
        return bool(x and x["running"] and not x["paused"] and x["ips"])
    deadline, a = time.monotonic() + 90, _inspect(target)
    while time.monotonic() < deadline and not up(a):
        time.sleep(2)
        a = _inspect(target)
    if up(a):
        r0 = a["restarts"]
        time.sleep(STABLE_S)
        a = _inspect(target)
        state["stable"] = {"restarts_start": r0, "restarts_end": a["restarts"] if a else None, "seconds": STABLE_S}
    if fault not in NETEM_WORD and a:
        spec_ok = p.returncode == 0 and {
            "containerStop": True, "containerPause": True,
            "cpuThrottle": a["nano_cpus"] == extra.get("nano_cpus_written"),
            "memoryLimit": a["memory"] == before["memory"] and a["memory_swap"] == before["memory_swap"],
        }[fault]
    state["reverted"] = {"exit": p.returncode, "stderr": p.stderr.strip()[-300:], **extra}
    state["after"] = a
    stable = state["stable"] or {}
    steady = stable.get("restarts_end") is not None and stable["restarts_end"] == stable["restarts_start"]
    state["verified"] = bool(spec_ok and up(a) and steady)
    return state


def run_incident(entry: dict, night: Path, log, first: bool) -> dict:
    """Tek vaka. Döner: etiket (geçerli ya da değil); geçerliyse snapshot SNAPSHOTS'ta, etiket INCIDENTS'ta."""
    sys.path.insert(0, str(REPO / "src"))
    import c2_measure as cm  # noqa: PLC0415
    import incident_checks as ic  # noqa: PLC0415
    from aiops_rca.leakage import LeakageInputError, scan_model_view  # noqa: PLC0415
    from trial_summary import Window, summarize  # noqa: PLC0415

    infra = "fault" in entry
    dry = bool(entry.get("dry"))
    s = None if infra else BY_ID[entry["scenario"]]
    root = entry["target"] if infra else s["root"]
    noise = BY_ID[entry["noise_layer"]] if entry.get("noise_layer") else None
    ia = next((x for x in INFRA_ANSWERS if infra and (x["fault"], x["target"]) == (entry["fault"], root)),
              {"propagation_path": [], "categories": []})
    iid = new_incident_id()
    work = night / iid
    snap = work / "model_view" if dry else SNAPSHOTS / iid
    work.mkdir(parents=True)
    t0 = time.monotonic()
    label = {
        "incident_id": iid, "set": entry.get("set", "pilot"),
        "answer": {"scenario": entry["fault"] if infra else s["flag"],
                   "variant": entry["param"] if infra else s["variant"],
                   "noise_layer": noise["flag"] if noise else None,
                   "injection_start": None, "injection_end": None, "root_cause_service": root,
                   "fault_type": INFRA_FAULTS[entry["fault"]]["fault_type"] if infra else s["fault_type"],
                   "propagation_path": ia["propagation_path"] if infra else s["propagation_path"],
                   "categories": ia["categories"] if infra else s["categories"]},
        "window": None, "checks": {}, "valid": False, "invalid_reasons": [], "marks": [],
        "run": {"list_entry": entry, "versions": versions(), "guards": guards(), "times": {}, "containers": {},
                "collector_restarted": False, "restarts_in_window": [], "expected_restarts": [],
                "suspended_s": None, "max_pkg_temp_c": None, "memory": {}, "anonymous_volumes_removed": {},
                "duration_s": None, "snapshot_bytes": None, "overheat": False, "baseline_failed": False,
                "coverage_short": False, "leakage_found": False, "fault_state": None, "target_ips": None,
                "min_swap_free_gb": None, "export_failures": None,
                "schedule": {"seed": None, "normal_s": DRY_NORMAL_S, "tail_s": DRY_TAIL_S, "dry": True} if dry
                else schedule(secrets.randbits(32))},
    }
    run, times, checks = label["run"], label["run"]["times"], label["checks"]

    def mark(key: str) -> int:
        ns = utc_ns()
        times[key] = iso(ns)
        log(f"{iid} {key}")
        return ns

    def wait(seconds: float) -> None:
        if monitor.hot.wait(max(0.0, seconds)):
            raise Overheat(f"x86_pkg_temp above {HOT_C} °C for more than {HOT_S} s")

    monitor = Monitor(work / "collector_mem.tsv")
    flags_on: list[dict] = []
    fault_state = None
    normal_ns = flag_on_ns = flag_off_ns = up_ns = None
    jaeger_cpu_start = (None, None)
    try:
        try:
            log(f"{iid} {entry}; guards {run['guards']}")
            if run["guards"]["problems"]:
                raise Invalid("guards: " + "; ".join(run["guards"]["problems"]))
            mark("start")
            monitor.start()
            if demo("up", log, raw=False) != 0:
                raise Invalid("otel_demo.sh up failed")
            up_ns = mark("demo_up")
            if first:
                time.sleep(10)
                ism = ism_explain()
                (night / "ism.json").write_text(json.dumps(ism, ensure_ascii=False, indent=1) + "\n")
                log(f"ISM {ism.get('indices')} pass {ism.get('pass')}")
            subprocess.run(["docker", "restart", "otel-collector"], capture_output=True)
            run["collector_restarted"] = True
            mark("collector_restarted")
            end = time.monotonic() + WAIT_CONTAINERS_S[1]
            n = container_count()
            while n != CONTAINERS and time.monotonic() < end:
                time.sleep(10)
                n = container_count()
            run["containers"]["after_collector_restart"] = n
            if n != CONTAINERS:
                raise Invalid(f"container count {n}, want {CONTAINERS}")
            wait(WARMUP_S - (utc_ns() - up_ns) / 1e9)
            run["scheduler"] = scheduler_state()
            if run["scheduler"] != "stopped":
                raise Invalid(f"flagd-ui scheduler {run['scheduler']}")
            for f in ([] if infra else [s]) + ([noise] if noise else []):
                before = resolve(f)
                if not isinstance(before, dict) or before.get("variant") != "off":
                    raise Invalid(f"flag {f['flag']} not off before normal: {before}")
            start_state = containers()
            (work / "containers_start.txt").write_text(json.dumps(start_state, indent=1) + "\n")
            normal_ns = mark("normal_start")
            jaeger_cpu_start = (_cpu_usec("jaeger"), time.monotonic())
            slept_before = sleep_offset_s()
            wait(run["schedule"]["normal_s"])

            # Taban sağlık: normal dönemin verisi (dosya), C2 analiziyle aynı ölçü; alarm = şimdi.
            alarm = utc_ns()
            recent = [f for f in sorted((TELEMETRY / "filtered").glob("*.jsonl"))
                      if f.stat().st_mtime_ns >= normal_ns - 60 * 10**9]
            rows_now = cm.service_rows(summarize(recent, Window(alarm))[0])
            checks["baseline_health"] = {**ic.baseline_check(rows_now), "measured_at": iso(alarm)}
            log(f"{iid} baseline {checks['baseline_health']}")
            if not checks["baseline_health"]["pass"] and not dry:
                run["baseline_failed"] = True
                raise Invalid(f"baseline health: frontend p95 {checks['baseline_health']['frontend_p95_ms']} ms > "
                              f"{checks['baseline_health']['threshold_ms']} ms")

            run["containers"]["at_flag_on"] = container_count()
            if infra:
                run["target_ips"] = {"before": (_inspect(root) or {}).get("ips"), "after": None}
                with signals_deferred():  # uygulanmış ama kaydı tutulmamış hata kalmasın
                    flag_on_ns = mark(f"fault_on_{entry['fault']}")
                    fault_state = run["fault_state"] = apply_fault(entry["fault"], root, entry["param"])
                    log(f"{iid} fault {entry['fault']} on {root} ({entry['param']}): applied {fault_state['applied_ok']} "
                        f"{json.dumps(fault_state['applied'])}")
                if not fault_state["applied_ok"]:
                    raise Invalid(f"fault not applied: {fault_state['applied']}")
            for f in ([] if infra else [s]) + ([noise] if noise else []):
                with signals_deferred():
                    flags_on.append(f)
                    written, verified, answer = set_flag(f, f["variant"])
                    times[f"flag_on_write_{f['flag']}"], times[f"flag_on_verified_{f['flag']}"] = iso(written), iso(verified)
                    log(f"{iid} flag on {f['flag']}={f['variant']}: verified {iso(verified)} {json.dumps(answer)}")
                if verified is None:
                    raise Invalid(f"flag on {f['flag']} not verified")
                if f is s:
                    flag_on_ns = written
            label["answer"]["injection_start"] = iso(flag_on_ns)
            wait(DRY_FAULT_S if dry else FLAG_S)
            run["containers"]["at_flag_off"] = container_count()
            for f in list(flags_on):
                with signals_deferred():
                    written, verified, answer = set_flag(f, "off")
                    flags_on.remove(f)
                    times[f"flag_off_write_{f['flag']}"], times[f"flag_off_verified_{f['flag']}"] = iso(written), iso(verified)
                    log(f"{iid} flag off {f['flag']}: verified {iso(verified)} {json.dumps(answer)}")
                if f is s:
                    flag_off_ns = written
                if verified is None:
                    raise Invalid(f"flag off {f['flag']} not verified")
            if infra:
                with signals_deferred():
                    flag_off_ns = mark(f"fault_off_{entry['fault']}")
                    revert_fault(fault_state)
                    run["target_ips"]["after"] = (fault_state["after"] or {}).get("ips")
                    log(f"{iid} fault reverted: verified {fault_state['verified']} {json.dumps(fault_state['reverted'])}")
                if not fault_state["verified"]:
                    raise Invalid(f"cleanup not verified: {fault_state['reverted']} {fault_state['after']}")
            label["answer"]["injection_end"] = iso(flag_off_ns)
            wait(run["schedule"]["tail_s"] - (utc_ns() - flag_off_ns) / 1e9)
            mark("tail_end")
            run["suspended_s"] = round(sleep_offset_s() - slept_before, 1)

            end_state = containers()
            (work / "containers_end.txt").write_text(json.dumps(end_state, indent=1) + "\n")
            target_restarts = not infra or entry["fault"] in ("containerStop", "containerPause", "memoryLimit")
            expected = {root} if root and target_restarts else set()
            run["restarts_in_window"], run["expected_restarts"] = split_restarts(start_state, end_state, expected)
            reasons = []
            if run["suspended_s"] > SUSPEND_MAX_S:
                reasons.append(f"machine slept {run['suspended_s']} s between normal start and tail end")
            if run["restarts_in_window"]:
                reasons.append("unexpected restart/stop in window: "
                               + ", ".join(e["container"] for e in run["restarts_in_window"]))
            if reasons:
                raise Invalid("; ".join(reasons))
            label["valid"] = True
        except Overheat as e:
            run["overheat"] = True
            label["invalid_reasons"].append(str(e))
            log(f"{iid} INVALID: {e}")
        except Invalid as e:
            label["invalid_reasons"].append(str(e))
            log(f"{iid} INVALID: {e}")
        except Exception as e:  # beklenmeyen hata da kayda girer, demo kapatılır
            label["invalid_reasons"].append(f"error: {type(e).__name__}: {e}")
            log(f"{iid} ERROR: {type(e).__name__}: {e}")
        finally:
            try:
                with signals_deferred():  # temizlik sinyalle kesilmez; ikinci sinyal kayda geçer
                    for f in list(flags_on):
                        try:
                            written, verified, _ = set_flag(f, "off")
                            times[f"flag_off_write_{f['flag']}"] = iso(written)
                            log(f"{iid} flag off {f['flag']} after abort: verified {iso(verified)}")
                            if f is s:
                                flag_off_ns = written
                        except Exception as e:
                            log(f"{iid} flag off {f['flag']} after abort failed: {e}")
                    if fault_state and "exit" in (fault_state["applied"] or {}) and fault_state["reverted"] is None:
                        try:
                            flag_off_ns = flag_off_ns or utc_ns()
                            revert_fault(fault_state)
                            log(f"{iid} fault reverted after abort: verified {fault_state['verified']}")
                        except Exception as e:
                            log(f"{iid} fault revert after abort failed: {e}")
                    if "start" in times:
                        run["memory"] = {c: cgroup_memory(c) for c in ("jaeger", "otel-collector")}
                        if up_ns:  # Jaeger'in kendi Go yığını (collector üzerinden Prometheus'a gelir), demo açık kaldığı süre
                            heap = prom_max('otelcol_process_runtime_heap_alloc_bytes{job="jaeger"}', (utc_ns() - up_ns) / 1e9)
                            run["memory"]["jaeger_heap_peak_mib"] = round(heap / 2**20, 1) if heap is not None else None
                        if normal_ns:  # normal başından buraya (demo kapanmadan önce)
                            usec, t_start = jaeger_cpu_start
                            usec_end = _cpu_usec("jaeger")
                            run["memory"]["jaeger_cpu_avg_cores"] = (
                                round((usec_end - usec) / 1e6 / (time.monotonic() - t_start), 3)
                                if usec is not None and usec_end is not None and usec_end >= usec else None)
                            since = (utc_ns() - normal_ns) / 1e9
                            run["export_failures"] = {}
                            for k, qs in EXPORT_FAILURE_QUERIES.items():
                                vals = [prom_increase(q, since) for q in qs]
                                run["export_failures"][k] = None if None in vals else round(sum(vals), 1)
                        anon = anonymous_volumes()
                        if demo("down", log) == 0:
                            run["anonymous_volumes_removed"] = remove_volumes(anon)
                            log(f"{iid} anonymous volumes removed {run['anonymous_volumes_removed']}")
                        mark("demo_down")
                    monitor.stop_event.set()
                    if monitor.is_alive():
                        monitor.join(timeout=60)
                    run["max_pkg_temp_c"] = monitor.max_temp
                    run["memory"]["collector_sampled_peak_mib"] = monitor.peak_mem_mib
                    run["memory"]["jaeger_anon_peak_mib"] = monitor.jaeger_anon_peak_mib
                    run["memory"]["jaeger_swap_peak_mib"] = monitor.jaeger_swap_peak_mib
                    run["min_swap_free_gb"] = monitor.min_swap_free_gb

            except Stopped as e:  # sinyal temizlik sırasında geldi: temizlik bitti, vaka durduruldu
                label["valid"] = False
                label["invalid_reasons"].append(str(e))
                log(f"{iid} INVALID: {e} (during cleanup)")
    except Stopped as e:  # except gövdesinde gelen ilk sinyal; temizlik yukarıda yapıldı
        label["valid"] = False
        label["invalid_reasons"].append(str(e))
        log(f"{iid} INVALID: {e}")
    if len(signals_deferred.signals) > 1:
        label["invalid_reasons"].append(f"signals during cleanup (cleanup not interrupted): "
                                       f"{signals_deferred.signals[1:]}")
        log(f"{iid} signals during cleanup: {signals_deferred.signals[1:]}")

    if label["valid"]:
        try:
            lo, hi = normal_ns - WINDOW_MARGIN_NS[0], flag_off_ns + run["schedule"]["tail_s"] * 10**9
            label["window"] = {"start": iso(lo), "end": iso(hi)}
            checks["coverage"] = cut_snapshot(lo, hi, work, snap, normal_ns)
            mark("snapshot_cut")
            short = [k for k, v in checks["coverage"].items() if not v["covered"]]
            if short:
                run["coverage_short"] = True
                label["invalid_reasons"].append(f"window shortened by rotation: {short}")
            try:
                findings = scan_model_view(snap)
                checks["leakage"] = {"findings": len(findings), "first": [str(f) for f in findings[:5]]}
            except LeakageInputError as e:
                checks["leakage"] = {"findings": None, "error": str(e)}
            if checks["leakage"]["findings"] != 0:
                run["leakage_found"] = True
                label["invalid_reasons"].append(f"leakage: {checks['leakage']}")
            w = Window(flag_on_ns)
            paths = sorted(snap.glob("*.jsonl"))
            rows = cm.service_rows(summarize(paths, w)[0])
            ops = ic.operation_rows([snap / "traces.jsonl"], w)
            if root and infra and entry["fault"] in ("containerStop", "containerPause"):
                # Hedefin kendi span'leri kesilir: belirti ve olay çağıranların hedefe giden istemci span'lerinde.
                ips = tuple(sorted(set((run["target_ips"] or {}).get("before") or [])
                                   | set((run["target_ips"] or {}).get("after") or [])))
                callers, rpcs = ic.caller_rows([snap / "traces.jsonl"], w, root, ips)
                checks["symptom"] = {**ic.caller_symptom_check(callers, root), "matched_ips": list(ips),
                                     "matched_rpc_services": rpcs}
                checks["event"] = ic.event_check(checks["symptom"], rows)
                if checks["event"]["applied"] and not checks["event"]["pass"]:
                    label["invalid_reasons"].append(f"no event: {checks['event']}")
                if checks["symptom"]["verdict"] in ("no_symptom", "borderline", "not_measurable"):
                    label["marks"].append(checks["symptom"]["verdict"])
            elif root and infra and entry["fault"] in NETEM_WORD:
                # Ağ hatası: hedefin kendisi ve çağıranları; güçlü olan karar verir. Olay hedefin kendi isteğiyle
                # (DECISIONS 2026-10-27 "Ağ hatalarında belirti").
                own = checks["symptom_target"] = ic.symptom_check(rows, ops, root)
                ips = tuple(sorted(set((run["target_ips"] or {}).get("before") or [])
                                   | set((run["target_ips"] or {}).get("after") or [])))
                callers, rpcs = ic.caller_rows([snap / "traces.jsonl"], w, root, ips)
                checks["symptom_callers"] = {**ic.caller_symptom_check(callers, root), "matched_ips": list(ips),
                                             "matched_rpc_services": rpcs}
                checks["symptom"] = ic.stronger_symptom(own, checks["symptom_callers"])
                checks["event"] = ic.event_check(own, rows)
                if checks["event"]["applied"] and not checks["event"]["pass"]:
                    label["invalid_reasons"].append(f"no event: {checks['event']}")
                if checks["symptom"]["verdict"] in ("no_symptom", "borderline", "not_measurable"):
                    label["marks"].append(checks["symptom"]["verdict"])
            elif root:
                checks["symptom"] = ic.symptom_check(rows, ops, root)
                checks["event"] = ic.event_check(checks["symptom"], rows)
                if checks["event"]["applied"] and not checks["event"]["pass"]:
                    label["invalid_reasons"].append(f"no event: {checks['event']}")
                if checks["symptom"]["verdict"] in ("no_symptom", "borderline", "not_measurable"):
                    label["marks"].append(checks["symptom"]["verdict"])
            checks["monitoring_health"] = ic.monitoring_health(snap / "metrics.jsonl", normal_ns, flag_off_ns)
            run["snapshot_bytes"] = sum(f.stat().st_size for f in snap.iterdir())
            label["valid"] = not label["invalid_reasons"]
            if not label["valid"] and not dry:
                shutil.move(snap, work / "model_view")  # geçersiz snapshot kökte kalmaz (sızıntılı olabilir)
                log(f"{iid} INVALID after cut: {label['invalid_reasons']}; snapshot moved to {work / 'model_view'}")
        except Stopped as e:  # snapshot kesimi ya da kontroller sırasında: geçersiz yolla aynı
            label["valid"] = False
            label["invalid_reasons"].append(str(e))
            if snap.exists() and not dry:
                shutil.move(snap, work / "model_view")
            log(f"{iid} INVALID: {e} (during snapshot/checks); partial snapshot in {work}")
    with signals_deferred():  # etiket yarım yazılmasın; burada gelen sinyal döngüde işlenir
        run["duration_s"] = round(time.monotonic() - t0)
        text = json.dumps(label, ensure_ascii=False, indent=1) + "\n"
        (night / f"{iid}.json").write_text(text)
        if label["valid"] and not dry:
            INCIDENTS.mkdir(exist_ok=True)
            (INCIDENTS / f"{iid}.json").write_text(text)
        what = f"{entry['fault']}:{root}:{entry['param']}" if infra else entry["scenario"]
        log(f"{iid} {what}: {'VALID' if label['valid'] else 'INVALID'} marks {label['marks']} "
            f"symptom {checks.get('symptom', {}).get('verdict')} duration {run['duration_s']} s")
    return label


def cleanup_failed(label: dict) -> bool:
    """Bir hata komutu çalıştı ama temizlik doğrulanamadı."""
    fs = label["run"]["fault_state"]
    return bool(fs and "exit" in (fs["applied"] or {}) and not fs["verified"])


def cmd_incidents(list_path: Path) -> int:
    entries = json.loads(list_path.read_text(encoding="utf-8"))
    def bad(e: dict) -> bool:
        if e.get("noise_layer") and e["noise_layer"] not in BY_ID:
            return True
        if "fault" in e:
            # frontend hedef seçilmez: frontend-proxy span'lerinde hedef alanı yok, çağıran ölçümü yapılamaz (Eren).
            # İstisna memoryLimit: belirti ve olay hedefin kendi span'lerinde (DECISIONS 2026-10-27, V2c bellek).
            return e["fault"] not in INFRA_FAULTS or not e.get("target") \
                or (e["target"] == "frontend" and e["fault"] != "memoryLimit") \
                or not re.fullmatch(PARAM_RE[e["fault"]], str(e.get("param", "")))
        return e.get("scenario") not in BY_ID or BY_ID[e["scenario"]]["root"] is None

    unknown = [e for e in entries if bad(e)]
    if unknown:
        print(f"error: unknown or non-incident entries {unknown}", file=sys.stderr)
        return 2
    if subprocess.run(["docker", "image", "inspect", GATEWAY_IMAGE], capture_output=True).returncode != 0:
        print(f"error: {GATEWAY_IMAGE} missing; pull: docker pull {GATEWAY_IMAGE}", file=sys.stderr)
        return 2
    if any(e.get("fault") in NETEM_WORD for e in entries) and subprocess.run(
            ["docker", "image", "inspect", NETEM_IMAGE], capture_output=True).returncode != 0:
        print(f"error: {NETEM_IMAGE} missing; pull: docker pull {NETEM_IMAGE}", file=sys.stderr)
        return 2
    night = INCIDENT_RUNS / f"{time.strftime('%Y%m%dT%H%MZ', time.gmtime())}-{list_path.stem}"
    night.mkdir(parents=True)
    log_file = (night / "runner.log").open("a")

    def log(msg: str) -> None:
        line = f"{iso(utc_ns())} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    # Durdurma: SIGTERM (systemctl stop, kapanma) ve SIGINT (Ctrl-C) yarıdaki vakayı temizlik yolundan geçirir.
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, signals_deferred.handle)
    # Uyku engelleri yan süreçte: koşucu ana süreç kalır, SIGTERM yalnız ona gider (birimde KillMode=mixed). Engel
    # koşucu çıkana kadar durur (`tail --pid`), koşucu çökse bile kendiliğinden kalkar; ayrı oturum: Ctrl-C ona gitmez.
    try:
        subprocess.Popen([*GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
                          f"--who={INHIBIT_WHO}", f"--why={INHIBIT_WHY[0]}", "tail", f"--pid={os.getpid()}", "-f",
                          "/dev/null"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        log(f"inhibitor could not start: {e}")
    end = time.monotonic() + 10
    while time.monotonic() < end and not (inhibited() and gnome_inhibited()):
        time.sleep(0.5)

    def stop_code() -> int:
        sigs = signals_deferred.signals
        log(f"STOP: {sigs[0]} received; night stopped, no further incidents (signals {sigs})")
        return 128 + signal.Signals[sigs[0]].value

    try:
        log(f"list {list_path} ({len(entries)} entries); versions {versions()}")
        status, first = 0, True
        for entry in entries:
            g = guards()
            if g["problems"]:
                log(f"STOP before {entry}: guards: {'; '.join(g['problems'])}")
                return 1
            label = run_incident(entry, night, log, first)
            first = False
            if signals_deferred.signals:
                return stop_code()
            if label["run"]["leakage_found"]:
                log("STOP: leakage found (may be systematic); night stopped")
                return 1
            if cleanup_failed(label):
                log("STOP: fault cleanup not verified (may affect the next incident); night stopped")
                return 1
            # Taban sağlık, ısınma ya da döndürme: bir kez daha (kart; C2 kuralı).
            if label["run"]["baseline_failed"] or label["run"]["overheat"] or label["run"]["coverage_short"]:
                if label["run"]["overheat"]:
                    log("overheat: waiting to cool, then one more attempt")
                    wait_cool()
                g = guards()
                if g["problems"]:
                    log(f"STOP before retry of {entry}: guards: {'; '.join(g['problems'])}")
                    return 1
                label = run_incident(entry, night, log, False)
                if signals_deferred.signals:
                    return stop_code()
                if label["run"]["leakage_found"]:
                    log("STOP: leakage found (may be systematic); night stopped")
                    return 1
                if cleanup_failed(label):
                    log("STOP: fault cleanup not verified (may affect the next incident); night stopped")
                    return 1
            if not label["valid"]:
                status = 1
        log("list done")
        return status
    except Stopped:  # vaka dışında (korumalar, bekleme) ya da etiket yazıldıktan sonra gelen sinyal
        return stop_code()
    finally:
        log_file.close()


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("list", "guards", "run", "incidents") \
            or (argv[0] == "run" and len(argv) < 2) or (argv[0] == "incidents" and len(argv) != 2):
        print(__doc__, file=sys.stderr)
        return 2
    if argv[0] == "incidents":
        return cmd_incidents(Path(argv[1]))
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
