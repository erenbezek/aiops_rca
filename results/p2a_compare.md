# P2a: dosya ↔ canlı karşılaştırması

Komutla üretilir: `python tools/query_compare.py report <koşu klasörü>...` (kayıtlar repo dışında, `~/cerebrum2/p2a_compare/`). Çağrı listesi, eşitlik tanımı ve OOM kuralı ölçmeden önce yazıldı (HANDOFF 2026-11-11); fark türlerinin kararı sonuç görüldükten sonra (DECISIONS 2026-11-11).

Eşitlik: çağrı çıktısı iki tarafta birebir aynı (tolerans yok). Fark türü kodla: dosya okuyucusuna Jaeger'in bilinen dönüşümleri uygulanıp çağrı yeniden koşulur; canlıyla eşitleyen dönüşüm türdür.

## Koşular

| Koşu | Kod | Vaka | Süre (sa) |
|---|---|---|---|
| `20261111T2333Z-pilot` | `9e44917` | 25 | 3.94 |

## pilot

- Vaka: 25; oynatılan 25; yeniden denenen 0.
- Çağrı: 16993; eşit 16317, farklı 676.
- Sızıntı bulgusu (canlı çıktılar): 0.
- Exemplar reddi (vaka başına): 5–27, toplam 398 (şart değil; DECISIONS 2026-11-10).
- Jaeger bellek tepesi: 1822.7 MiB (sınır 2000 MiB).
- Karşılaştırma süresi (vaka başına, oynatma hariç): 286–464 sn.

| Fonksiyon | Eşit | Farklı |
|---|---|---|
| `get_trace` | 1801 | 376 |
| `list_services` | 25 | 0 |
| `metric_series` | 11529 | 0 |
| `search_logs` | 1731 | 0 |
| `search_spans` | 1156 | 300 |
| `service_dependencies` | 75 | 0 |

| Fark türü | Çağrı |
|---|---|
| `zero_duration` | 676 |

Açıklanamayan farklı çağrı: 0.

Ham kayıt (C aralığı; span, log, dört metrik) farkları; listede olmayan sinyal ve sayaç 0:

- spans: aynı kimlikte farklı (end_ns +1): 171342

## Fark türlerinin açıklaması

- `zero_duration`: Jaeger süresi 0 olan span'i bitiş + 1 ns ile döndürüyor (depolama; duration_ms 0 ↔ 1e-06).
- `error_tag`: Jaeger error="true" etiketini hata durumuna çeviriyor (depolama); canlı okuyucu bunu geri alıyor (store_live.undo_jaeger_error_tag, DECISIONS 2026-11-12), bu tür artık beklenmiyor (tanı olarak sınanır).

## Sınırlamalar

- Jaeger süresi 0 olan span'i bitiş + 1 ns ile döndürüyor; geri çevrilmez (gerçekten 1 ns süren span canlıda aynı görünür). Bu çağrılar farklı sayılır (DECISIONS 2026-11-11).
- Jaeger error="true" etiketini hata durumuna çeviriyor; canlı okuyucu geri alıyor. Kural Jaeger'in bugünkü davranışına (belirtilmemiş + etiket → hata, etiket kalır; hata + etiket → etiket silinir) bağlı (DECISIONS 2026-11-12).
- Hata tanımı (OTLP durumu; P1 ile aynı) Envoy'un yanıtsız isteklerini (http.status_code 0, yalnız error="true" etiketi) hata saymıyor; dosyada da canlıda da (DECISIONS 2026-11-12).
- Exemplar reddi her vakada var ve koşudan koşuya değişiyor; sorgu katmanı exemplar okumuyor (DECISIONS 2026-11-10).
- Çağrı listesi dosya tarafından türetiliyor (servisler, izler); canlıda fazladan olan bir şey yalnız süzgeçsiz çağrılarda ve ham kayıt karşılaştırmasında görünür.

## Vakalar

| Vaka | Set | Deneme | Eşit | Farklı | Türler | Exemplar | Jaeger MiB (oynatma / karş.) |
|---|---|---|---|---|---|---|---|
| `inc-01a609bb` | pilot | 1 | 812 | 27 | zero_duration 27 | 12 | 1455 / 1167 |
| `inc-01dd32ce` | pilot | 1 | 616 | 24 | zero_duration 24 | 19 | 1686 / 1152 |
| `inc-072897d4` | pilot | 1 | 611 | 29 | zero_duration 29 | 10 | 1287 / 1096 |
| `inc-07533a0a` | pilot | 1 | 640 | 29 | zero_duration 29 | 11 | 1270 / 1044 |
| `inc-09516b21` | pilot | 1 | 608 | 32 | zero_duration 32 | 14 | 1366 / 1152 |
| `inc-0f31ed0e` | pilot | 1 | 697 | 24 | zero_duration 24 | 15 | 1054 / 990 |
| `inc-110f3aba` | pilot | 1 | 619 | 21 | zero_duration 21 | 22 | 1307 / 1178 |
| `inc-12813456` | pilot | 1 | 633 | 31 | zero_duration 31 | 13 | 1294 / 1194 |
| `inc-2a87f603` | pilot | 1 | 658 | 23 | zero_duration 23 | 23 | 1356 / 1122 |
| `inc-2dd806a2` | pilot | 1 | 641 | 32 | zero_duration 32 | 5 | 1823 / 1229 |
| `inc-2e5706ab` | pilot | 1 | 612 | 28 | zero_duration 28 | 20 | 1405 / 1161 |
| `inc-3967c278` | pilot | 1 | 618 | 22 | zero_duration 22 | 5 | 1477 / 1205 |
| `inc-48be145f` | pilot | 1 | 614 | 26 | zero_duration 26 | 15 | 1289 / 1197 |
| `inc-78df5642` | pilot | 1 | 642 | 26 | zero_duration 26 | 13 | 1321 / 1121 |
| `inc-79cab5da` | pilot | 1 | 615 | 25 | zero_duration 25 | 24 | 1697 / 1195 |
| `inc-8ceb7ae5` | pilot | 1 | 630 | 22 | zero_duration 22 | 20 | 1241 / 1109 |
| `inc-91bf76d4` | pilot | 1 | 845 | 23 | zero_duration 23 | 11 | 1506 / 1178 |
| `inc-91c1ad44` | pilot | 1 | 607 | 33 | zero_duration 33 | 22 | 1609 / 1302 |
| `inc-93c4ca55` | pilot | 1 | 630 | 27 | zero_duration 27 | 20 | 1280 / 1226 |
| `inc-af671750` | pilot | 1 | 622 | 29 | zero_duration 29 | 21 | 1655 / 1106 |
| `inc-b03ccffb` | pilot | 1 | 809 | 29 | zero_duration 29 | 20 | 1358 / 1088 |
| `inc-c775923b` | pilot | 1 | 613 | 28 | zero_duration 28 | 20 | 1678 / 1289 |
| `inc-d8f67a48` | pilot | 1 | 614 | 26 | zero_duration 26 | 6 | 1564 / 1262 |
| `inc-ef72f574` | pilot | 1 | 619 | 37 | zero_duration 37 | 27 | 1369 / 1126 |
| `inc-f20daed8` | pilot | 1 | 692 | 23 | zero_duration 23 | 10 | 1285 / 1110 |
