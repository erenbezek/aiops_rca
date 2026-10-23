"""Zor deneme belirti kontrolü: kök neden servisinde özetteki değerler normal döneme göre sapıyor mu?
(HANDOFF 2026-10-21 zor deneme, madde 4; eşikler Eren onayı 2026-10-21, ölçmeden önce.)

Kullanım: python tools/trial_symptoms.py <vaka klasörü>...
Vaka klasöründen `view/summary.json` (modele giden özet) ve `case.json`'daki `root_cause_service` okunur. Sadece
özetteki değerlere bakılır (ham veriye değil). Modeller koşmadan önce çalıştırılır; sonuç `case.json` yanına,
`symptoms.json` olarak yazılır (`view/` dışında).

Kök neden servisinde aşağıdakilerden biri varsa vaka "belirtili", hiçbiri yoksa "belirtisiz":
- hata oranı: sonra − önce ≥ 0,05
- p95: sonra ≥ 1,5 × önce ve sonra − önce ≥ 20 ms
- CPU ortalaması: sonra ≥ 1,5 × önce ve sonra − önce ≥ 5 puan
- bellek ortalaması: sonra ≥ 1,2 × önce
- WARN+ log: o servisin, önceki pencerede olmayan (`count_before` 0) ve sonraki pencerede ≥ 5 kez görülen bir
  mesajı
- istek düşüşü: önceki pencerede ≥ 20 istek ve sonra ≤ 0,5 × önce
Değeri olmayan sinyal (ör. veritabanında istek) "yok" sayılır, sapma sayılmaz.
Çıkış kodu: 0 yazıldı, 2 kullanım/girdi hatası.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def ratio_and_delta(before, after, ratio: float, delta: float) -> bool | None:
    if before is None or after is None:
        return None
    return after >= ratio * before and after - before >= delta


def check(summary: dict, service: str) -> dict:
    row = next((r for r in summary["services"] if r["service"] == service), {})
    g = row.get
    signals = {}

    eb, ea = g("error_rate_before"), g("error_rate_after")
    signals["error_rate"] = {"before": eb, "after": ea,
                             "deviates": None if eb is None or ea is None else ea - eb >= 0.05}
    pb, pa = g("p95_ms_before"), g("p95_ms_after")
    signals["p95_ms"] = {"before": pb, "after": pa, "deviates": ratio_and_delta(pb, pa, 1.5, 20)}
    cb, ca = g("cpu_pct_avg_before"), g("cpu_pct_avg_after")
    signals["cpu_pct_avg"] = {"before": cb, "after": ca, "deviates": ratio_and_delta(cb, ca, 1.5, 5)}
    mb, ma = g("mem_mb_avg_before"), g("mem_mb_avg_after")
    signals["mem_mb_avg"] = {"before": mb, "after": ma,
                             "deviates": None if mb is None or ma is None else ma >= 1.2 * mb}
    new_logs = [m for m in summary.get("top_warning_and_error_logs_after_alarm", [])
                if m["service"] == service and m["count_before"] == 0 and m["count_after"] >= 5]
    signals["new_warn_log"] = {"messages": [(m["message"], m["count_after"]) for m in new_logs],
                               "deviates": bool(new_logs)}
    rb, ra = g("requests_before"), g("requests_after")
    signals["request_drop"] = {"before": rb, "after": ra,
                               "deviates": None if rb is None or ra is None else rb >= 20 and ra <= 0.5 * rb}

    verdict = "symptomatic" if any(s["deviates"] for s in signals.values()) else "no_symptom"
    return {"service": service, "row_found": bool(row), "signals": signals, "verdict": verdict}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    for case in (Path(a).expanduser() for a in argv):
        try:
            summary = json.loads((case / "view" / "summary.json").read_text(encoding="utf-8"))
            service = json.loads((case / "case.json").read_text(encoding="utf-8"))["root_cause_service"]
        except (OSError, ValueError, KeyError) as e:
            print(f"error: {case}: {e}", file=sys.stderr)
            return 2
        result = check(summary, service)
        (case / "symptoms.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
        print(f"{case.name}: {service}: {result['verdict']}" + ("" if result["row_found"] else " (no row)"))
        for name, s in result["signals"].items():
            values = s.get("messages") if name == "new_warn_log" else (s["before"], s["after"])
            print(f"  {name:13} {str(s['deviates']):5} {values}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
