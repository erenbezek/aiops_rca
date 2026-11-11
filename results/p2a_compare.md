# P2a: dosya ↔ canlı karşılaştırması

Komutla üretilir: `python tools/query_compare.py report <koşu klasörü>...` (kayıtlar repo dışında, `~/cerebrum2/p2a_compare/`). Çağrı listesi, eşitlik tanımı ve OOM kuralı ölçmeden önce yazıldı (HANDOFF 2026-11-11); fark türlerinin kararı sonuç görüldükten sonra (DECISIONS 2026-11-11).

Eşitlik: çağrı çıktısı iki tarafta birebir aynı (tolerans yok). Fark türü kodla: dosya okuyucusuna Jaeger'in bilinen dönüşümleri uygulanıp çağrı yeniden koşulur; canlıyla eşitleyen dönüşüm türdür.

## Koşular

| Koşu | Kod | Vaka | Süre (sa) |
|---|---|---|---|
| `20261110T2204Z-pilot` | `583fb0c` | 25 | 3.95 |

## pilot

- Vaka: 25; oynatılan 25; yeniden denenen 0.
- Çağrı: 16993; eşit 15995, farklı 998.
- Sızıntı bulgusu (canlı çıktılar): 0.
- Exemplar reddi (vaka başına): 5–26, toplam 390 (şart değil; DECISIONS 2026-11-10).
- Jaeger bellek tepesi: 1636.4 MiB (sınır 2000 MiB).
- Karşılaştırma süresi (vaka başına, oynatma hariç): 283–464 sn.

| Fonksiyon | Eşit | Farklı |
|---|---|---|
| `get_trace` | 1555 | 622 |
| `list_services` | 25 | 0 |
| `metric_series` | 11497 | 32 |
| `search_logs` | 1731 | 0 |
| `search_spans` | 1112 | 344 |
| `service_dependencies` | 75 | 0 |

| Fark türü | Çağrı |
|---|---|
| `error_tag` | 322 |
| `error_tag+zero_duration` | 18 |
| `zero_duration` | 658 |

Açıklanamayan farklı çağrı: 0.

Ham kayıt (C aralığı; span, log, dört metrik) farkları; listede olmayan sinyal ve sayaç 0:

- spans: aynı kimlikte farklı (end_ns +1): 171342
- spans: aynı kimlikte farklı (status +2): 1829

## Fark türlerinin açıklaması

- `zero_duration`: Jaeger süresi 0 olan span'i bitiş + 1 ns ile döndürüyor (depolama; duration_ms 0 ↔ 1e-06).
- `error_tag`: Jaeger error="true" etiketini hata durumuna çeviriyor (depolama); Envoy yanıtsız isteklerde (http.status_code 0) yalnız bu etiketi koyuyor, P1 / P2 hata tanımı (OTLP durumu) bunları hata saymıyor (tanım).

## Vakalar

| Vaka | Set | Deneme | Eşit | Farklı | Türler | Exemplar | Jaeger MiB (oynatma / karş.) |
|---|---|---|---|---|---|---|---|
| `inc-01a609bb` | pilot | 1 | 796 | 43 | error_tag 16, error_tag+zero_duration 2, zero_duration 25 | 12 | 1365 / 1063 |
| `inc-01dd32ce` | pilot | 1 | 616 | 24 | zero_duration 24 | 19 | 1592 / 1144 |
| `inc-072897d4` | pilot | 1 | 611 | 29 | zero_duration 29 | 9 | 1270 / 1165 |
| `inc-07533a0a` | pilot | 1 | 640 | 29 | zero_duration 29 | 11 | 1280 / 1070 |
| `inc-09516b21` | pilot | 1 | 608 | 32 | zero_duration 32 | 14 | 1354 / 1135 |
| `inc-0f31ed0e` | pilot | 1 | 606 | 115 | error_tag 91, error_tag+zero_duration 2, zero_duration 22 | 15 | 1091 / 927 |
| `inc-110f3aba` | pilot | 1 | 619 | 21 | zero_duration 21 | 22 | 1337 / 1066 |
| `inc-12813456` | pilot | 1 | 633 | 31 | zero_duration 31 | 13 | 1381 / 1159 |
| `inc-2a87f603` | pilot | 1 | 607 | 74 | error_tag 51, error_tag+zero_duration 2, zero_duration 21 | 23 | 1364 / 1103 |
| `inc-2dd806a2` | pilot | 1 | 641 | 32 | zero_duration 32 | 5 | 1433 / 1032 |
| `inc-2e5706ab` | pilot | 1 | 612 | 28 | zero_duration 28 | 20 | 1466 / 1212 |
| `inc-3967c278` | pilot | 1 | 618 | 22 | zero_duration 22 | 5 | 1457 / 1213 |
| `inc-48be145f` | pilot | 1 | 614 | 26 | zero_duration 26 | 14 | 1317 / 1044 |
| `inc-78df5642` | pilot | 1 | 612 | 56 | error_tag 30, error_tag+zero_duration 2, zero_duration 24 | 14 | 1239 / 1000 |
| `inc-79cab5da` | pilot | 1 | 606 | 34 | error_tag 9, error_tag+zero_duration 2, zero_duration 23 | 26 | 1636 / 1239 |
| `inc-8ceb7ae5` | pilot | 1 | 630 | 22 | zero_duration 22 | 16 | 1293 / 1040 |
| `inc-91bf76d4` | pilot | 1 | 845 | 23 | zero_duration 23 | 9 | 1506 / 1116 |
| `inc-91c1ad44` | pilot | 1 | 607 | 33 | zero_duration 33 | 22 | 1440 / 1017 |
| `inc-93c4ca55` | pilot | 1 | 630 | 27 | zero_duration 27 | 20 | 1267 / 1135 |
| `inc-af671750` | pilot | 1 | 622 | 29 | zero_duration 29 | 20 | 1634 / 1177 |
| `inc-b03ccffb` | pilot | 1 | 801 | 37 | error_tag 8, error_tag+zero_duration 2, zero_duration 27 | 20 | 1304 / 1091 |
| `inc-c775923b` | pilot | 1 | 603 | 38 | error_tag 10, error_tag+zero_duration 2, zero_duration 26 | 20 | 1397 / 969 |
| `inc-d8f67a48` | pilot | 1 | 614 | 26 | zero_duration 26 | 6 | 1572 / 1210 |
| `inc-ef72f574` | pilot | 1 | 598 | 58 | error_tag 21, error_tag+zero_duration 2, zero_duration 35 | 25 | 1355 / 1026 |
| `inc-f20daed8` | pilot | 1 | 606 | 109 | error_tag 86, error_tag+zero_duration 2, zero_duration 21 | 10 | 1300 / 1245 |
