"""Summarizes tools/local_model_bench.sh runs into markdown tables.

Kullanım: python tools/bench_summary.py <koşu klasörü>...
- cells.csv olan klasörler tablo (matrix) koşusu sayılır; geçerli hücreleri birleştirilir.
- iterations.csv olan klasör (en fazla bir) sürekli yük koşusudur; verilirse ısınmış süre hesaplanır:
  ölçülen modelde doğrudan, diğerlerinde yavaşlama oranı varsayımıyla.
Geçerli ölçüm: çıkış kodu 0 ve ölçüm boyunca izlemede priz hep takılı.
Bütçe kararı (HANDOFF 2026-10-20): süre = (girdi + üretim) / hız; 2048+300 için ≤ 120 sn GEÇER.
"""
import csv
import json
import statistics
import sys
from pathlib import Path

BUDGET_SECS = 120
TESTS = {  # (n_prompt, n_gen) -> etiket
    (2048, 0): "pp2048",
    (0, 300): "tg300",
    (2048, 300): "pg2048+300",
    (6144, 300): "pg6144+300",
}
TEMP_LIMIT_C = 95
SAMPLE_SECS = 10


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("{"):
            rows.append(json.loads(line))
    return rows


def mean_sd(values):
    if not values:
        return None, None
    m = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return m, sd


def fmt(m, sd, digits=1):
    if m is None:
        return "-"
    return f"{m:.{digits}f} ± {sd:.{digits}f}"


def size_key(model):
    return float(model.rstrip("B"))


def window(monitor, start, end):
    return [r for r in monitor if start <= int(r["ts"]) <= end]


def ac_ok(rows):
    return all(r["ac_online"] == "1" for r in rows)


def peak_gb(rows):
    """llama-bench sürecinin en yüksek belleği (VmHWM). Eski izleme dosyalarında bu sütun yok."""
    vals = [int(r["hwm_kb"]) for r in rows if r.get("hwm_kb")]
    return max(vals) * 1024 / 1e9 if vals else None


def machine_lines(run, monitor):
    env = dict(
        line.split("=", 1) for line in (run / "env.txt").read_text(encoding="utf-8").splitlines() if "=" in line
    )
    lines = [
        f"- `{run.name}`: başlangıç {env.get('date')}, AC {env.get('ac_online')}, profil "
        f"{env.get('platform_profile')}, {env.get('pkg_temp_c')} °C, çalışan konteyner {env.get('docker_running')}, "
        f"imaj {env.get('image_tag')}"
    ]
    if monitor:
        temps = [int(r["pkg_temp_c"]) for r in monitor]
        swaps = [int(r["swap_used_kb"]) for r in monitor]
        hot = sum(1 for t in temps if t > TEMP_LIMIT_C) * SAMPLE_SECS
        ac_off = sum(1 for r in monitor if r["ac_online"] != "1")
        freqs = [int(r["freq_avg_mhz"]) for r in monitor if r["container"]]
        freq_txt = f"{statistics.mean(freqs):.0f} MHz" if freqs else "-"
        lines.append(
            f"  - izleme {len(monitor)} örnek ({SAMPLE_SECS} sn): en yüksek {max(temps)} °C; {TEMP_LIMIT_C} °C üstü "
            f"~{hot} sn; yük altında ortalama frekans {freq_txt}; AC kapalı örnek {ac_off}"
        )
        lines.append(
            f"  - takas: başta {swaps[0]} kB, en çok {max(swaps)} kB, sonda {swaps[-1]} kB "
            f"(artış en çok {max(swaps) - swaps[0]:+d} kB)"
        )
    for name in ("ABORT",):
        if (run / name).exists():
            lines.append(f"  - **DURDURULDU:** {(run / name).read_text(encoding='utf-8').strip()}")
    if (run / "events.log").exists():
        for event in (run / "events.log").read_text(encoding="utf-8").splitlines():
            lines.append(f"  - olay: {event}")
    return lines


def summarize_matrix(runs):
    data, temps, mem, invalid, machine = {}, {}, {}, [], []
    for run in runs:
        cells = read_csv(run / "cells.csv")
        monitor = read_csv(run / "monitor.csv")
        machine.extend(machine_lines(run, monitor))
        for c in cells:
            key = (c["model"], int(c["threads"]))
            rows = window(monitor, int(c["start_ts"]), int(c["end_ts"]))
            if c["exit_code"] != "0" or not ac_ok(rows):
                reason = c["exit_code"] if c["exit_code"] != "0" else "AC kapalı örnek"
                invalid.append(f"`{run.name}` tur {c['round']} {c['model']} {c['threads']} iş parçacığı: {reason}")
                continue
            temps.setdefault(key, []).append(int(c["start_temp_c"]))
            peak = peak_gb(rows)
            if peak is not None:
                mem[key] = max(mem.get(key, 0), peak)
            raw = run / "raw" / f"r{c['round']}_{c['model']}_t{c['threads']}.jsonl"
            for row in read_jsonl(raw):
                label = TESTS.get((row["n_prompt"], row["n_gen"]))
                if label:
                    data.setdefault(key, {}).setdefault(label, []).append(row["avg_ts"])

    out = ["## Tablo (soğuk; her hücre geçerli turların ortalaması ± sapması)", ""]
    out.append(
        "| Model | İş parçacığı | Tur | pp2048 t/s | tg300 t/s | 2048+300 süre (sn) | 6144+300 süre (sn) "
        "| Başlangıç °C | En yüksek bellek (GB) |"
    )
    out.append("|---|---|---|---|---|---|---|---|---|")
    best = {}
    for key in sorted(data, key=lambda k: (size_key(k[0]), k[1])):
        model, threads = key
        tests = data[key]
        budget = [2348 / ts for ts in tests.get("pg2048+300", [])]
        raw_log = [6444 / ts for ts in tests.get("pg6144+300", [])]
        bm, bsd = mean_sd(budget)
        if bm is not None and (model not in best or bm < best[model][1]):
            best[model] = (threads, bm)
        t = temps[key]
        mem_txt = f"{mem[key]:.2f}" if key in mem else "-"
        out.append(
            f"| {model} | {threads} | {len(budget)} | {fmt(*mean_sd(tests.get('pp2048', [])))} "
            f"| {fmt(*mean_sd(tests.get('tg300', [])), 2)} | {fmt(bm, bsd)} | {fmt(*mean_sd(raw_log))} "
            f"| {min(t)}–{max(t)} | {mem_txt} |"
        )
    out.append("")
    out.append(f"## Soğuk bütçe (en iyi iş parçacığı, 2048+300 ≤ {BUDGET_SECS} sn)")
    out.append("")
    for model, (threads, secs) in sorted(best.items(), key=lambda kv: size_key(kv[0])):
        verdict = "GEÇER" if secs <= BUDGET_SECS else "KALIR"
        out.append(f"- {model}: {threads} iş parçacığı, {secs:.1f} sn → {verdict} (soğuk)")
    if best:
        closest = min(best.items(), key=lambda kv: abs(kv[1][1] - BUDGET_SECS))
        out.append(
            f"- {BUDGET_SECS} sn'ye en yakın: {closest[0]} ({closest[1][0]} iş parçacığı, {closest[1][1]:.1f} sn) "
            "→ sürekli yük bu modelde"
        )
    if invalid:
        out.append("")
        out.append("## Kullanılmayan hücreler")
        out.append("")
        out.extend(f"- {line}" for line in invalid)
    out.append("")
    out.append("## Makine")
    out.append("")
    out.extend(machine)
    return out, best


def summarize_sustained(run, best):
    iters = read_csv(run / "iterations.csv")
    monitor = read_csv(run / "monitor.csv")
    valid = [
        it for it in iters
        if it["exit_code"] == "0" and ac_ok(window(monitor, int(it["start_ts"]), int(it["end_ts"])))
    ]
    model = valid[0]["model"]
    threads = int(valid[0]["threads"])
    t0 = int(valid[0]["start_ts"])
    points = []  # (bitiş saniyesi, t/s)
    overhead = []  # iterasyonun ölçülmeyen kısmı: konteyner, model yükleme, llama-bench ısınma turu
    for it in valid:
        rows = [r for r in read_jsonl(run / "raw" / f"i{int(it['iter']):04d}.jsonl") if r["n_gen"] == 300]
        if rows:
            points.append((int(it["end_ts"]) - t0, rows[0]["avg_ts"]))
            overhead.append(int(it["end_ts"]) - int(it["start_ts"]) - rows[0]["avg_ns"] / 1e9)
    gaps = [int(b["start_ts"]) - int(a["end_ts"]) for a, b in zip(valid, valid[1:])]
    total = points[-1][0]
    peak = peak_gb(window(monitor, t0, int(valid[-1]["end_ts"])))

    out = [f"## Sürekli yük ({model}, {threads} iş parçacığı, {total / 60:.1f} dk, {len(points)} iterasyon)", ""]
    out.append("| Dakika | Biten iterasyon | 2048+300 t/s | Süre (sn) | En yüksek °C | Ort. frekans MHz |")
    out.append("|---|---|---|---|---|---|")
    for minute in range(int(total // 60) + 1):
        in_min = [ts for end, ts in points if minute * 60 < end <= (minute + 1) * 60]
        mon = window(monitor, t0 + minute * 60, t0 + (minute + 1) * 60)
        temp = max((int(r["pkg_temp_c"]) for r in mon), default=None)
        freq = statistics.mean(int(r["freq_avg_mhz"]) for r in mon) if mon else None
        speed = statistics.mean(in_min) if in_min else None
        speed_txt = f"{speed:.2f} | {2348 / speed:.1f}" if speed else "- | -"
        freq_txt = f"{freq:.0f}" if freq else "-"
        out.append(f"| {minute + 1} | {len(in_min)} | {speed_txt} | {temp} | {freq_txt} |")
    out.append("")
    discarded = len(iters) - len(valid)
    if discarded:
        out.append(f"- Kullanılmayan deneme: {discarded} (priz kopması ya da hata)")
    out.append(
        f"- İterasyon başına ölçülmeyen süre (konteyner, model yükleme, ısınma turu): ortalama "
        f"{statistics.mean(overhead):.1f} sn; iterasyonlar arası boşluk: ortalama "
        f"{statistics.mean(gaps) if gaps else 0:.1f} sn"
    )
    out.append(f"- En yüksek bellek (llama-bench VmHWM): {peak:.2f} GB" if peak else "- En yüksek bellek: -")
    first = [ts for end, ts in points if end <= 120]
    first_label = "İlk 2 dk"
    if not first:
        # Bir iterasyon 2 dk'dan uzunsa pencere boş kalır; ilk iterasyon kullanılır (Eren onayı, 2026-10-20).
        first = [points[0][1]]
        first_label = f"İlk 2 dk boş (iterasyon {points[0][0] / 60:.1f}. dk'da bitti); ilk iterasyon"
    last = [ts for end, ts in points if end >= total - 600]
    ratio = statistics.mean(last) / statistics.mean(first)
    out.append(
        f"- {first_label} {statistics.mean(first):.2f} t/s ({len(first)} iterasyon), son 10 dk "
        f"{statistics.mean(last):.2f} t/s ({len(last)} iterasyon): hız farkı {(ratio - 1) * 100:+.1f} %"
    )
    out.extend(machine_lines(run, monitor))
    out.append("")
    out.append(f"## Isınmış bütçe (2048+300 ≤ {BUDGET_SECS} sn)")
    out.append("")
    for m, (t, cold) in sorted(best.items(), key=lambda kv: size_key(kv[0])):
        if m == model:
            warm = 2348 / statistics.mean(last)
            how = "ölçüldü (son 10 dk)"
        else:
            warm = cold / ratio
            how = f"varsayım: {model} modelinin yavaşlama oranı uygulandı"
        verdict = "GEÇER" if warm <= BUDGET_SECS else "KALIR"
        out.append(f"- {m}: soğuk {cold:.1f} sn → ısınmış {warm:.1f} sn → {verdict} ({how})")
    return out


def main(argv):
    runs = [Path(a) for a in argv[1:]]
    matrix = [r for r in runs if (r / "cells.csv").exists()]
    sustained = [r for r in runs if (r / "iterations.csv").exists()]
    if not matrix or len(sustained) > 1 or len(matrix) + len(sustained) != len(runs):
        print(__doc__, file=sys.stderr)
        return 2
    lines, best = summarize_matrix(matrix)
    if sustained:
        lines.append("")
        lines.extend(summarize_sustained(sustained[0], best))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
