# P2b pilot dumanı

Komutla üretilir: `python tools/agent_report.py` (kaynak `eval_responses/`'teki üç pilot koşusu). Pilot tasarım aşamasıdır: istem, araçlar ve sınırlar pilotta belirlendi; **isabet (top-1 / top-3) yalnız bilgi, iyimser okunur ve hiçbir karara girmez** (P2b kartı).

## Koşular

| Koşu | Klasör | Bitişler | Geçerli son cevap | Araç sayısı (vaka) | İstek | Token giriş / çıkış | Süre ort / en çok (sn) | En uzun mesaj | Kırpmalı vaka | Bütçe bitişi | Tekrar | Araç hatası | Kesilen sonuç | HTTP | top-1 (bilgi) | top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) Gemini, dosya, 25 vaka | `20261113T075333Z-agent` | answer 10, no_answer 1, step_limit 14 | 24/25 | 3: 1, 5: 2, 6: 4, 7: 3, 8: 15 | 213 | 486420 / 31682 | 34.7 / 192.2 | 4418 | 0 | 0 | 0 | 0 | 6 | 200: 212, 503: 10 | 6/25 | 11/25 |
| (c) qwen3.5-4b, dosya, 25 vaka | `20261113T083032Z-agent` | answer 1, schema_answer 5, step_limit 19 | 20/25 | 7: 1, 8: 24 | 225 | 594889 / 31416 | 260.0 / 421.7 | 5955 | 3 | 0 | 7 | 10 | 33 | 200: 225 | 3/25 | 6/25 |
| (d) Gemini, canlı, 3 vaka | `20261113T102704Z-agent` | answer 3 | 3/3 | 5: 1, 6: 1, 7: 1 | 24 | 63270 / 3601 | 25.1 / 31.6 | 4026 | 0 | 0 | 0 | 0 | 4 | 200: 24 | 2/3 | 3/3 |

## Kurallar

- **4B kuralı** (DECISIONS 2026-11-13, koşudan önce): geçerli son cevap 20 / 25 (≥ 20) ve ortalama vaka süresi 4.33 dk (≤ 20) → **geçti: 4B P2’ye girer**.
- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09: vakaların yarısından çoğu bütçe yüzünden biterse): `20261113T075333Z-agent` 0/25; `20261113T083032Z-agent` 0/25; `20261113T102704Z-agent` 0/3 → **tetiklenmedi**.

## Vakalar

### (b) Gemini, dosya, 25 vaka

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-01a609bb` | step_limit | 8 | 9 | 192.16 | 3360 | 0 | 0 | 0 | hayır / hayır |
| `inc-01dd32ce` | answer | 7 | 9 | 19.763 | 2970 | 0 | 0 | 0 | hayır / hayır |
| `inc-072897d4` | step_limit | 8 | 9 | 18.405 | 4267 | 0 | 0 | 0 | hayır / hayır |
| `inc-07533a0a` | no_answer | 8 | 9 | 85.257 | 3240 | 0 | 0 | 0 | hayır / hayır |
| `inc-09516b21` | answer | 7 | 9 | 83.892 | 3043 | 0 | 0 | 0 | hayır / hayır |
| `inc-0f31ed0e` | answer | 5 | 7 | 13.773 | 3541 | 0 | 0 | 0 | evet / evet |
| `inc-110f3aba` | step_limit | 8 | 9 | 19.029 | 3367 | 0 | 0 | 0 | hayır / hayır |
| `inc-12813456` | answer | 6 | 8 | 48.229 | 3778 | 0 | 0 | 0 | evet / evet |
| `inc-2a87f603` | answer | 6 | 8 | 16.636 | 3438 | 0 | 0 | 0 | evet / evet |
| `inc-2dd806a2` | step_limit | 8 | 9 | 18.368 | 3520 | 0 | 0 | 0 | hayır / hayır |
| `inc-2e5706ab` | step_limit | 8 | 9 | 18.267 | 4418 | 0 | 0 | 0 | hayır / hayır |
| `inc-3967c278` | step_limit | 8 | 9 | 17.843 | 3331 | 0 | 0 | 0 | hayır / hayır |
| `inc-48be145f` | step_limit | 8 | 9 | 49.009 | 3276 | 0 | 0 | 0 | hayır / evet |
| `inc-78df5642` | step_limit | 8 | 9 | 50.011 | 3260 | 0 | 0 | 0 | hayır / evet |
| `inc-79cab5da` | step_limit | 8 | 9 | 19.207 | 3518 | 0 | 0 | 0 | hayır / evet |
| `inc-8ceb7ae5` | step_limit | 8 | 9 | 49.308 | 3310 | 0 | 0 | 0 | hayır / hayır |
| `inc-91bf76d4` | step_limit | 8 | 9 | 17.359 | 3278 | 0 | 0 | 0 | hayır / hayır |
| `inc-91c1ad44` | answer | 7 | 9 | 17.681 | 3250 | 0 | 0 | 0 | hayır / hayır |
| `inc-93c4ca55` | answer | 6 | 8 | 16.62 | 3955 | 0 | 0 | 0 | evet / evet |
| `inc-af671750` | answer | 6 | 8 | 16.06 | 3567 | 0 | 0 | 0 | evet / evet |
| `inc-b03ccffb` | step_limit | 8 | 9 | 19.341 | 4022 | 0 | 0 | 0 | hayır / hayır |
| `inc-c775923b` | step_limit | 8 | 9 | 18.167 | 3561 | 0 | 0 | 0 | hayır / hayır |
| `inc-d8f67a48` | step_limit | 8 | 9 | 21.014 | 4099 | 0 | 0 | 0 | evet / evet |
| `inc-ef72f574` | answer | 3 | 5 | 9.642 | 2541 | 0 | 0 | 0 | hayır / evet |
| `inc-f20daed8` | answer | 5 | 7 | 13.201 | 3934 | 0 | 0 | 0 | hayır / evet |

### (c) qwen3.5-4b, dosya, 25 vaka

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-01a609bb` | answer | 7 | 9 | 265.076 | 4275 | 0 | 0 | 0 | evet / evet |
| `inc-01dd32ce` | step_limit | 8 | 9 | 276.888 | 5414 | 0 | 0 | 0 | hayır / hayır |
| `inc-072897d4` | step_limit | 8 | 9 | 202.001 | 3341 | 0 | 0 | 1 | evet / evet |
| `inc-07533a0a` | step_limit | 8 | 9 | 232.338 | 4595 | 0 | 0 | 1 | evet / evet |
| `inc-09516b21` | step_limit | 8 | 9 | 212.386 | 3381 | 0 | 0 | 1 | hayır / hayır |
| `inc-0f31ed0e` | step_limit | 8 | 9 | 200.93 | 3343 | 0 | 0 | 1 | hayır / evet |
| `inc-110f3aba` | step_limit | 8 | 9 | 207.281 | 3554 | 0 | 0 | 1 | hayır / hayır |
| `inc-12813456` | step_limit | 8 | 9 | 262.075 | 4857 | 0 | 0 | 0 | hayır / hayır |
| `inc-2a87f603` | step_limit | 8 | 9 | 228.732 | 4084 | 0 | 0 | 1 | hayır / evet |
| `inc-2dd806a2` | schema_answer | 8 | 9 | 230.859 | 3857 | 0 | 0 | 0 | hayır / hayır |
| `inc-2e5706ab` | schema_answer | 8 | 9 | 256.355 | 4590 | 0 | 0 | 0 | hayır / hayır |
| `inc-3967c278` | step_limit | 8 | 9 | 388.68 | 5589 | 1 | 1 | 0 | hayır / hayır |
| `inc-48be145f` | schema_answer | 8 | 9 | 272.716 | 4953 | 0 | 0 | 0 | hayır / hayır |
| `inc-78df5642` | schema_answer | 8 | 9 | 405.229 | 5909 | 1 | 0 | 0 | hayır / hayır |
| `inc-79cab5da` | step_limit | 8 | 9 | 273.281 | 5052 | 0 | 0 | 0 | hayır / hayır |
| `inc-8ceb7ae5` | step_limit | 8 | 9 | 217.241 | 3814 | 0 | 0 | 0 | hayır / hayır |
| `inc-91bf76d4` | step_limit | 8 | 9 | 300.378 | 5932 | 0 | 2 | 0 | hayır / hayır |
| `inc-91c1ad44` | step_limit | 8 | 9 | 274.434 | 5421 | 0 | 0 | 0 | hayır / hayır |
| `inc-93c4ca55` | step_limit | 8 | 9 | 206.053 | 3370 | 0 | 0 | 1 | hayır / hayır |
| `inc-af671750` | schema_answer | 8 | 9 | 305.022 | 5910 | 0 | 2 | 0 | hayır / hayır |
| `inc-b03ccffb` | step_limit | 8 | 9 | 198.392 | 3080 | 0 | 2 | 1 | hayır / hayır |
| `inc-c775923b` | step_limit | 8 | 9 | 262.343 | 4594 | 0 | 0 | 0 | hayır / hayır |
| `inc-d8f67a48` | step_limit | 8 | 9 | 421.728 | 5955 | 1 | 0 | 0 | hayır / hayır |
| `inc-ef72f574` | step_limit | 8 | 9 | 200.024 | 3348 | 0 | 0 | 1 | hayır / hayır |
| `inc-f20daed8` | step_limit | 8 | 9 | 200.495 | 3339 | 0 | 0 | 1 | hayır / evet |

### (d) Gemini, canlı, 3 vaka

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-2a87f603` | answer | 7 | 9 | 24.777 | 4026 | 0 | 0 | 0 | evet / evet |
| `inc-91bf76d4` | answer | 6 | 8 | 18.991 | 3982 | 0 | 0 | 0 | hayır / evet |
| `inc-af671750` | answer | 5 | 7 | 31.612 | 4024 | 0 | 0 | 0 | evet / evet |
