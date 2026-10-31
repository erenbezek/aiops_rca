"""Kaba kalite denemeleri için vaka özeti (HANDOFF 2026-10-21, DECISIONS 2026-10-21).

Kullanım: python tools/trial_summary.py --alarm 2026-10-21T14:00:00+03:00 --out <klasör>/summary.json
          [--input ~/cerebrum2/telemetry/filtered]

Sadece süzülmüş collector dosyalarını (`*.jsonl`, döndürülmüş dosyalar dahil) okur. Pencere: alarmdan önceki
10 dk ("before") ve sonraki 10 dk ("after"). Kaydın zamanı: span'de `startTimeUnixNano`; logda `timeUnixNano`,
0 ya da yoksa `observedTimeUnixNano`; metrikte veri noktasının `timeUnixNano`'su.

İçerik bilerek basit (daraltma değil):
- Servis başına gelen istek sayısı (SERVER ve CONSUMER span'leri), hata oranı (span durumu ERROR), p95 süre (ms),
  önce / sonra.
- Konteyner başına CPU (`docker stats` gibi bir çekirdeğin yüzdesi; ortalama ve en yüksek) ve bellek (`container.memory.usage.total`, MB; sadece ortalama), önce / sonra. Konteyner adı servis adıdır. İzleme
  araçlarının konteynerleri (mağazanın değil ölçüm aracının parçası) yok; mağazanın veritabanları var.
  CPU, birikimli CPU süresi sayacından (`container.cpu.usage.total`, ns) hesaplanır: ardışık iki ölçüm arasındaki
  artış / geçen süre × 100; değer ikinci ölçümün düştüğü pencereye yazılır, sayaç geriye düşerse (yeniden başlama)
  o çift atlanır. `container.cpu.utilization` kullanılmaz: bu collector sürümünde anlık değil, açılıştan beri
  birikmiş bir ortalama gibi davranıyor (zor deneme vaka 3: `ad` %404 iken 0,03 → 3,44 doğrusal arttı).
  Servis satırında olmayan alan (ör. veritabanında istek, tarayıcı tarafında CPU) satırda yok.
- En sık WARN ve üstü log mesajları (sonraki pencerede), servis ve önce / sonra sayısıyla. WARN dahil: payment
  ödeme hatasını WARN seviyesinde logluyor. Mesajlar gruplanmak için sadeleşir: kimlikler ve sayılar yer tutucu olur.

Özete flag adı, senaryo adı ya da kök neden ipucu yazılmaz; çıktı sızıntı CLI'ı ile ayrıca taranır.
Pencerenin iki ucunda span, log ya da metrik kaydı yoksa (dosya döndürmesi silmiş ya da koşu kısa) hata verir,
eksik özet yazmaz.
Çıkış kodu: 0 yazıldı, 1 pencere eksik, 2 kullanım/girdi hatası.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
# Pencere ve okuma çekirdeği pakette (DECISIONS 2026-10-30 "P1a kararları"); adlar buradan da içe aktarılabilir.
from aiops_rca.signals import (  # noqa: E402, F401
    CPU_METRIC, EDGE_NS, ID_PATTERNS, INCOMING_KINDS, MEMORY_METRIC, MESSAGE_CHARS, MESSAGE_KEYS, SEVERITY_WARN,
    STATUS_ERROR, TOOLING_CONTAINERS, WINDOW_NS, Window, iter_lines, log_message, normalize, point_value,
    resource_attr, summarize, value_text,
)

# Özet tablosu da pakette (P1c 2. adım, `inputs.py`); betiğin davranışı ve çıktısı aynı.
from aiops_rca.inputs import TOP_MESSAGES, avg_max, p95_ms, summary_text  # noqa: E402, F401
from aiops_rca.inputs import summary_table as build  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--alarm", required=True, help="ISO 8601 with timezone, e.g. 2026-10-21T14:00:00+03:00")
    parser.add_argument("--out", required=True, help="output JSON file")
    parser.add_argument("--input", default=str(Path.home() / "cerebrum2/telemetry/filtered"))
    args = parser.parse_args(argv)

    try:
        alarm = datetime.fromisoformat(args.alarm)
    except ValueError as e:
        print(f"error: --alarm: {e}", file=sys.stderr)
        return 2
    if alarm.tzinfo is None:
        print("error: --alarm needs a timezone (e.g. +03:00)", file=sys.stderr)
        return 2
    paths = sorted(Path(args.input).expanduser().glob("*.jsonl"))
    if not paths:
        print(f"error: no *.jsonl in {args.input}", file=sys.stderr)
        return 2

    window = Window(int(alarm.timestamp()) * 10**9)
    try:
        result, edges = summarize(paths, window)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    missing = [f"{sig} {end}" for sig, (first, last) in edges.items()
               for end, ok in (("start", first), ("end", last)) if not ok]
    if missing:
        print(f"error: window not covered by data: {', '.join(missing)}", file=sys.stderr)
        return 1

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    text = summary_text(build(result, window))
    out.write_text(text + "\n", encoding="utf-8")
    print(f"ok: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
