# P2c-0 pilot tasarım turu

Komutla üretilir: `python tools/agent_report.py --report p2c0` (kaynak `eval_responses/`'teki altı pilot koşusu). Tek tur (DECISIONS 2026-11-13): onaylı iki değişiklik (A zaman varsayılanı ve görev cümlesi, B servissiz `metric_series`), pilot bir kez yeniden koşuldu; bu koşudan sonra istem, araçlar ve sınırlar donar. **Pilot tasarım setidir: isabet (top-1 / top-3) iki turda da iyimser okunur ve hiçbir karara girmez.**

## Eski ve yeni pilot

| Koşu | Klasör | Bitişler | Geçerli son cevap | Araç sayısı (vaka) | İstek | Token giriş / çıkış | Süre ort / en çok (sn) | En uzun mesaj | Kırpmalı vaka | Bütçe bitişi | Tekrar | Araç hatası | Kesilen sonuç | HTTP | top-1 (iyimser) | top-3 (iyimser) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini, dosya, 25 vaka: eski (P2b, `a2fa4331`) | `20261113T075333Z-agent` | answer 10, no_answer 1, step_limit 14 | 24/25 | 3: 1, 5: 2, 6: 4, 7: 3, 8: 15 | 213 | 486420 / 31682 | 34.7 / 192.2 | 4418 | 0 | 0 | 0 | 0 | 6 | 200: 212, 503: 10 | 6/25 | 11/25 |
| Gemini, dosya, 25 vaka: yeni (P2c-0, `5e259201`) | `20261113T125627Z-agent` | answer 18, step_limit 7 | 25/25 | 2: 1, 4: 4, 5: 3, 6: 1, 7: 9, 8: 7 | 201 | 581800 / 29620 | 27.0 / 51.0 | 5963 | 0 | 0 | 0 | 0 | 44 | 200: 201, 503: 8 | 14/25 | 22/25 |
| qwen3.5-4b, dosya, 25 vaka: eski (P2b, `a2fa4331`) | `20261113T083032Z-agent` | answer 1, schema_answer 5, step_limit 19 | 20/25 | 7: 1, 8: 24 | 225 | 594889 / 31416 | 260.0 / 421.7 | 5955 | 3 | 0 | 7 | 10 | 33 | 200: 225 | 3/25 | 6/25 |
| qwen3.5-4b, dosya, 25 vaka: yeni (P2c-0, `5e259201`) | `20261113T182857Z-agent` | answer 1, schema_answer 3, step_limit 21 | 22/25 | 6: 1, 8: 24 | 224 | 658321 / 31019 | 292.8 / 526.5 | 5974 | 4 | 0 | 10 | 0 | 27 | 200: 224 | 6/25 | 13/25 |
| Gemini, canlı, 3 vaka: eski (P2b, `a2fa4331`) | `20261113T102704Z-agent` | answer 3 | 3/3 | 5: 1, 6: 1, 7: 1 | 24 | 63270 / 3601 | 25.1 / 31.6 | 4026 | 0 | 0 | 0 | 0 | 4 | 200: 24 | 2/3 | 3/3 |
| Gemini, canlı, 3 vaka: yeni (P2c-0, `5e259201`) | `20261113T211812Z-agent` | answer 3 | 3/3 | 5: 1, 6: 1, 7: 1 | 24 | 70507 / 3710 | 38.4 / 45.2 | 5327 | 0 | 0 | 0 | 0 | 6 | 200: 24 | 2/3 | 3/3 |

## Servissiz `metric_series` (yeni koşular)

| Koşu | Çağrı | Verilen step_s (çağrı) | Kesilen | Araç hatası |
|---|---|---|---|---|
| Gemini, dosya, 25 vaka | 43 | 60: 33, 300: 9, default: 1 | 20 | 0 |
| qwen3.5-4b, dosya, 25 vaka | 62 | 10: 2, 30: 3, 60: 17, 300: 40 | 18 | 0 |
| Gemini, canlı, 3 vaka | 3 | 60: 2, default: 1 | 2 | 0 |

## Kurallar (yeni koşulara, aynen)

- **4B kuralı** (DECISIONS 2026-11-13, koşudan önce; `20261113T182857Z-agent`): geçerli son cevap 22 / 25 (≥ 20) ve ortalama vaka süresi 4.88 dk (≤ 20) → **geçti: 4B P2’de kalır**.
- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09: vakaların yarısından çoğu bütçe yüzünden biterse): `20261113T125627Z-agent` 0/25; `20261113T182857Z-agent` 0/25; `20261113T211812Z-agent` 0/3 → **tetiklenmedi**.

## Vakalar (yeni koşular)

### Gemini, dosya, 25 vaka

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-01a609bb` | answer | 4 | 6 | 12.22 | 4043 | 0 | 0 | 0 | evet / evet |
| `inc-01dd32ce` | answer | 7 | 9 | 18.414 | 5030 | 0 | 0 | 0 | evet / evet |
| `inc-072897d4` | step_limit | 8 | 9 | 16.212 | 4619 | 0 | 0 | 0 | hayır / evet |
| `inc-07533a0a` | answer | 2 | 4 | 8.115 | 2047 | 0 | 0 | 0 | evet / evet |
| `inc-09516b21` | answer | 7 | 9 | 16.494 | 4030 | 0 | 0 | 0 | evet / evet |
| `inc-0f31ed0e` | answer | 4 | 6 | 10.988 | 3759 | 0 | 0 | 0 | hayır / evet |
| `inc-110f3aba` | answer | 6 | 8 | 45.782 | 4345 | 0 | 0 | 0 | evet / evet |
| `inc-12813456` | answer | 5 | 7 | 12.752 | 4024 | 0 | 0 | 0 | evet / evet |
| `inc-2a87f603` | answer | 7 | 9 | 49.274 | 4106 | 0 | 0 | 0 | hayır / evet |
| `inc-2dd806a2` | step_limit | 8 | 9 | 50.191 | 4225 | 0 | 0 | 0 | hayır / hayır |
| `inc-2e5706ab` | answer | 7 | 9 | 17.988 | 4872 | 0 | 0 | 0 | evet / evet |
| `inc-3967c278` | step_limit | 8 | 9 | 49.104 | 5825 | 0 | 0 | 0 | evet / evet |
| `inc-48be145f` | step_limit | 8 | 9 | 16.276 | 4187 | 0 | 0 | 0 | hayır / hayır |
| `inc-78df5642` | answer | 7 | 9 | 16.896 | 4899 | 0 | 0 | 0 | evet / evet |
| `inc-79cab5da` | step_limit | 8 | 9 | 17.41 | 5072 | 0 | 0 | 0 | evet / evet |
| `inc-8ceb7ae5` | answer | 4 | 6 | 43.684 | 3359 | 0 | 0 | 0 | evet / evet |
| `inc-91bf76d4` | answer | 7 | 9 | 16.984 | 5963 | 0 | 0 | 0 | hayır / evet |
| `inc-91c1ad44` | step_limit | 8 | 9 | 48.789 | 5000 | 0 | 0 | 0 | hayır / evet |
| `inc-93c4ca55` | answer | 5 | 7 | 13.03 | 3524 | 0 | 0 | 0 | evet / evet |
| `inc-af671750` | answer | 4 | 6 | 12.486 | 3088 | 0 | 0 | 0 | evet / evet |
| `inc-b03ccffb` | answer | 7 | 9 | 49.814 | 4487 | 0 | 0 | 0 | evet / evet |
| `inc-c775923b` | step_limit | 8 | 9 | 50.978 | 5069 | 0 | 0 | 0 | hayır / evet |
| `inc-d8f67a48` | answer | 7 | 9 | 19.358 | 4946 | 0 | 0 | 0 | hayır / evet |
| `inc-ef72f574` | answer | 5 | 7 | 14.039 | 4267 | 0 | 0 | 0 | hayır / hayır |
| `inc-f20daed8` | answer | 7 | 9 | 47.842 | 4535 | 0 | 0 | 0 | hayır / evet |

### qwen3.5-4b, dosya, 25 vaka

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-01a609bb` | step_limit | 8 | 9 | 376.967 | 5932 | 0 | 0 | 0 | evet / evet |
| `inc-01dd32ce` | schema_answer | 8 | 9 | 526.538 | 5958 | 1 | 0 | 0 | hayır / hayır |
| `inc-072897d4` | schema_answer | 8 | 9 | 282.149 | 3963 | 0 | 0 | 0 | hayır / hayır |
| `inc-07533a0a` | step_limit | 8 | 9 | 307.603 | 4034 | 0 | 0 | 0 | evet / evet |
| `inc-09516b21` | step_limit | 8 | 9 | 293.643 | 4437 | 0 | 1 | 0 | hayır / hayır |
| `inc-0f31ed0e` | schema_answer | 8 | 9 | 307.047 | 4851 | 0 | 0 | 0 | hayır / hayır |
| `inc-110f3aba` | step_limit | 8 | 9 | 258.59 | 5264 | 0 | 0 | 0 | hayır / hayır |
| `inc-12813456` | step_limit | 8 | 9 | 253.524 | 5520 | 0 | 0 | 0 | evet / evet |
| `inc-2a87f603` | step_limit | 8 | 9 | 270.466 | 4750 | 0 | 0 | 0 | hayır / evet |
| `inc-2dd806a2` | step_limit | 8 | 9 | 458.389 | 5845 | 1 | 2 | 0 | hayır / hayır |
| `inc-2e5706ab` | step_limit | 8 | 9 | 203.275 | 3841 | 0 | 0 | 0 | hayır / evet |
| `inc-3967c278` | step_limit | 8 | 9 | 248.266 | 5180 | 0 | 0 | 0 | hayır / hayır |
| `inc-48be145f` | step_limit | 8 | 9 | 233.91 | 3832 | 0 | 0 | 0 | hayır / evet |
| `inc-78df5642` | step_limit | 8 | 9 | 261.021 | 5349 | 0 | 0 | 0 | hayır / hayır |
| `inc-79cab5da` | step_limit | 8 | 9 | 393.75 | 5944 | 1 | 0 | 0 | hayır / hayır |
| `inc-8ceb7ae5` | step_limit | 8 | 9 | 221.81 | 3928 | 0 | 0 | 0 | hayır / evet |
| `inc-91bf76d4` | step_limit | 8 | 9 | 500.083 | 5974 | 2 | 0 | 0 | hayır / evet |
| `inc-91c1ad44` | step_limit | 8 | 9 | 209.986 | 4049 | 0 | 0 | 0 | hayır / evet |
| `inc-93c4ca55` | step_limit | 8 | 9 | 263.475 | 5357 | 0 | 0 | 0 | evet / evet |
| `inc-af671750` | answer | 6 | 8 | 234.05 | 4206 | 0 | 0 | 0 | evet / evet |
| `inc-b03ccffb` | step_limit | 8 | 9 | 229.298 | 3943 | 0 | 0 | 0 | hayır / hayır |
| `inc-c775923b` | step_limit | 8 | 9 | 241.605 | 5262 | 0 | 5 | 0 | evet / evet |
| `inc-d8f67a48` | step_limit | 8 | 9 | 219.335 | 4406 | 0 | 0 | 0 | hayır / hayır |
| `inc-ef72f574` | step_limit | 8 | 9 | 233.137 | 4874 | 0 | 1 | 0 | hayır / evet |
| `inc-f20daed8` | step_limit | 8 | 9 | 291.51 | 5916 | 0 | 1 | 0 | hayır / hayır |

### Gemini, canlı, 3 vaka

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-2a87f603` | answer | 6 | 8 | 45.171 | 3955 | 0 | 0 | 0 | evet / evet |
| `inc-91bf76d4` | answer | 7 | 9 | 33.079 | 5327 | 0 | 0 | 0 | hayır / evet |
| `inc-af671750` | answer | 5 | 7 | 36.818 | 3793 | 0 | 0 | 0 | evet / evet |
