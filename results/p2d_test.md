# P2d test koşuları

Komutla üretilir: `python tools/agent_report.py --report p2d` (kaynak `eval_responses/`'teki test ve dev koşuları, `results/p2d_test_calls.json` sha256 `638699fa607e0164c332ab60831480b3f7923648701feb280068735080592e75`, `results/p1_runs.json`'daki P1 koşuları). Tasarım donmuş (DECISIONS 2026-11-14); okuma kuralları koşudan önce yazıldı (DECISIONS 2026-11-14, 2026-11-16). **Resmî sonuç budur.** Testte yalnız toplamlar: vaka başına sonuç yok.

## Koşular

| Koşu | Klasör | Bitişler | Geçerli son cevap | Araç sayısı (vaka) | İstek | Token giriş / çıkış | Süre ort / en çok (sn) | En uzun mesaj | Kırpmalı vaka | Bütçe bitişi | Tekrar | Araç hatası | Kesilen sonuç | HTTP | top-1 (test) | top-3 (test) | Yeniden deneme (istek / bekleme sn) | Taşıma hatasıyla cevapsız |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini, dosya, 1. koşu (resmî) | `20261116T230248Z-agent` | answer 11, step_limit 7 | 18/18 | 4: 2, 5: 2, 7: 7, 8: 7 | 152 | 449326 / 22418 | 89.6 / 287.3 | 5702 | 0 | 0 | 0 | 0 | 31 | 200: 152, 503: 24 | 10/18 | 14/18 | 21 / 870 | 0 |
| Gemini, dosya, 2. koşu (gürültü tabanı) | `20261117T000232Z-agent` | answer 11, step_limit 7 | 18/18 | 4: 2, 5: 3, 7: 6, 8: 7 | 150 | 444887 / 22338 | 73.0 / 181.9 | 5897 | 0 | 0 | 1 | 0 | 30 | 200: 150, 503: 20 | 10/18 | 15/18 | 18 / 660 | 0 |
| qwen3.5-4b, dosya | `20261117T003612Z-agent` | schema_answer 2, step_limit 16 | 16/18 | 7: 1, 8: 17 | 162 | 485924 / 21632 | 263.0 / 364.7 | 5968 | 2 | 0 | 10 | 0 | 27 | 200: 162 | 4/18 | 7/18 | 0 / 0 | 0 |
| Gemini, canlı | `20261117T080509Z-agent` | answer 8, schema_answer 1, step_limit 9 | 17/18 | 3: 1, 4: 1, 5: 1, 6: 3, 7: 3, 8: 9 | 150 | 448931 / 21716 | 122.5 / 321.5 | 5961 | 3 | 0 | 0 | 0 | 37 | 200: 150, 503: 32 | 5/18 | 12/18 | 27 / 1170 | 0 |
| qwen3.5-4b, canlı | `20261117T080511Z-agent` | schema_answer 2, step_limit 16 | 16/18 | 7: 1, 8: 17 | 162 | 485924 / 21632 | 339.6 / 577.1 | 5968 | 2 | 0 | 10 | 0 | 27 | 200: 162 | 4/18 | 7/18 | 0 / 0 | 0 |

Süre sütunu kayıttaki `duration_s` (yeniden deneme beklemesi içinde; istek aralığı beklemesi hariç); yeniden deneme beklemesi ayrı sütunda.

- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09; testte yalnız sayılır, tasarım donmuş): Gemini, dosya, 1. koşu (resmî) 0/18; Gemini, dosya, 2. koşu (gürültü tabanı) 0/18; qwen3.5-4b, dosya 0/18; Gemini, canlı 0/18; qwen3.5-4b, canlı 0/18 → tetiklenmedi.
- **Kod:** Gemini, dosya, 1. koşu (resmî) `416044e`; Gemini, dosya, 2. koşu (gürültü tabanı) `9562f2e`; qwen3.5-4b, dosya `b06f334`; Gemini, canlı `2a8f4ca`; qwen3.5-4b, canlı `2a8f4ca`; istem `5e259201`.
- **Teknik kesinti:** 0.
- **Okuma notu (sonuçtan önce yazıldı, DECISIONS 2026-11-15):** 4B dosya koşusunda yerel sunucunun istem önbelleği önceki vakalardan doluydu, canlıda her vaka boş önbellekle başladı; "çıktı aynı, model ayrıştı" çıkarsa sayılır ve bu fark olası neden olarak sınırlamalara yazılır.

## Dosya ↔ canlı (DECISIONS 2026-11-14, üç katman)

### gemini-3.5-flash-lite

- **(1) Çağrı düzeyi:** 123 canlı çağrı (18 vaka): aynı 123, bilinen tür (`zero_duration`) 0, **açıklanamayan 0** (beklenen 0; ayrıntı yalnız hata analizi maddesinde).
- **(2) Sonuç düzeyi, top-3 (eşleştirilmiş kesin işaret testi):** dosya 14 / 18, canlı 12 / 18; yalnız dosya 4, yalnız canlı 2; p = 0.6875 → **ayırt edilemedi**.

### qwen3.5-4b

- **(1) Çağrı düzeyi:** 143 canlı çağrı (18 vaka): aynı 143, bilinen tür (`zero_duration`) 0, **açıklanamayan 0** (beklenen 0; ayrıntı yalnız hata analizi maddesinde).
- **4B denetimi:** 18 vakada çıktı aynıyken model ayrıştı: 0; bir araç çıktısı farklı: 0; baştan sona aynı: 18.
- **(2) Sonuç düzeyi, top-3 (eşleştirilmiş kesin işaret testi):** dosya 7 / 18, canlı 7 / 18; yalnız dosya 0, yalnız canlı 0; p = 1.0 → **ayırt edilemedi**.

- **(3) Gürültü tabanı (Gemini, betimsel):** top-3 sonucu ayrışan vaka: dosya 1 ↔ dosya 2 3 / 18, dosya 1 ↔ canlı 6 / 18.

## Ajan ↔ P1 (DECISIONS 2026-11-14, model başına iki hücre)

Ajan tarafı dosya modunun ilk koşusu; P1 tarafı aynı modelin test koşuları (P1e). Geçerli cevabı olmayan vaka bilinmemiş. Dört hücrede çoklu karşılaştırma düzeltmesi yok.

- **gemini-3.5-flash-lite, (a) ajan ↔ ham, top-3:** ajan 14 / 18, ham 6 / 18; yalnız ajan 9, yalnız ham 1; p = 0.0215 → **fark: ajan lehine**.
- **gemini-3.5-flash-lite, (b) ajan ↔ daraltma, top-1:** ajan 10 / 18, daraltma 15 / 18; yalnız ajan 1, yalnız daraltma 6; p = 0.125 → **ayırt edilemedi**.
- **qwen3.5-4b, (a) ajan ↔ ham, top-3:** ajan 7 / 18, ham 7 / 18; yalnız ajan 3, yalnız ham 3; p = 1.0 → **ayırt edilemedi**.
- **qwen3.5-4b, (b) ajan ↔ daraltma, top-1:** ajan 4 / 18, daraltma 9 / 18; yalnız ajan 1, yalnız daraltma 6; p = 0.125 → **ayırt edilemedi**.

## Dev–test (DECISIONS 2026-11-16: yalnız iki dosya satırı, top-3, iki yönlü Fisher)

- **gemini-3.5-flash-lite, ajan dosya (1. koşu):** dev 14 / 18, test 14 / 18; p = 1.0 → **ayırt edilemedi** ("fark" için test ≤ 7).
- **qwen3.5-4b, ajan dosya (1. koşu):** dev 9 / 18, test 7 / 18; p = 0.738 → **ayırt edilemedi** ("fark" için test ≤ 2 ya da ≥ 16).

Öteki satırlarda dev ve test yalnız sayı (aşağıdaki tablo).

## Sonuç tablosu (dev ve test yan yana; öteki ölçüler testte, yalnız sayı)

| Model | Satır | Koşu (test) | dev top-1 | dev top-3 | test top-1 | test top-3 | Şema dışı | Cevapsız | Kanıt geçerli | Brier | Süre toplam (sn) | Token giriş / çıkış |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | ajan, Gemini, dosya, 1. koşu (resmî) | `20261116T230248Z-agent` | 9 / 18 | 14 / 18 | 10 / 18 | 14 / 18 | 0 | 0 | 12 | 0.3211 | 1612.075 | 449326 / 22418 |
| gemini-3.5-flash-lite | ajan, Gemini, dosya, 2. koşu (gürültü tabanı) | `20261117T000232Z-agent` | 9 / 18 | 15 / 18 | 10 / 18 | 15 / 18 | 0 | 0 | 10 | 0.2364 | 1313.946 | 444887 / 22338 |
| gemini-3.5-flash-lite | ajan, Gemini, canlı | `20261117T080509Z-agent` | 9 / 18 | 14 / 18 | 5 / 18 | 12 / 18 | 1 | 0 | 9 | 0.4235 | 2204.353 | 448931 / 21716 |
| gemini-3.5-flash-lite | P1 rule | `20261104T191843Z-rule` | 9 / 18 | 15 / 18 | 6 / 18 | 11 / 18 | 0 | 0 | 0 | None | 28.119 | None / None |
| gemini-3.5-flash-lite | P1 baro | `20261104T191911Z-baro` | 5 / 18 | 10 / 18 | 6 / 18 | 8 / 18 | 0 | 0 | 0 | None | 23.919 | None / None |
| gemini-3.5-flash-lite | P1 narrowing | `20261105T064023Z-narrowing` | 15 / 18 | 17 / 18 | 11 / 18 | 13 / 18 | 0 | 0 | 0 | None | 47.506 | None / None |
| gemini-3.5-flash-lite | P1 raw | `20261104T202442Z-llm` | 7 / 18 | 7 / 18 | 6 / 18 | 6 / 18 | 0 | 0 | 5 | 0.2863 | 19.842 | 42756 / 2169 |
| gemini-3.5-flash-lite | P1 summary | `20261104T202536Z-llm` | 12 / 18 | 16 / 18 | 10 / 18 | 13 / 18 | 0 | 0 | 8 | 0.2749 | 39.904 | 48934 / 3707 |
| gemini-3.5-flash-lite | P1 narrowed | `20261104T202649Z-llm` | 17 / 18 | 18 / 18 | 15 / 18 | 16 / 18 | 0 | 0 | 15 | 0.1242 | 33.572 | 48985 / 3967 |
| qwen3.5-4b | ajan, qwen3.5-4b, dosya | `20261117T003612Z-agent` | 4 / 18 | 9 / 18 | 4 / 18 | 7 / 18 | 2 | 0 | 6 | 0.5873 | 4733.994 | 485924 / 21632 |
| qwen3.5-4b | ajan, qwen3.5-4b, canlı | `20261117T080511Z-agent` | 4 / 18 | 9 / 18 | 4 / 18 | 7 / 18 | 2 | 0 | 6 | 0.5873 | 6112.801 | 485924 / 21632 |
| qwen3.5-4b | P1 rule | `20261104T191843Z-rule` | 9 / 18 | 15 / 18 | 6 / 18 | 11 / 18 | 0 | 0 | 0 | None | 28.119 | None / None |
| qwen3.5-4b | P1 baro | `20261104T191911Z-baro` | 5 / 18 | 10 / 18 | 6 / 18 | 8 / 18 | 0 | 0 | 0 | None | 23.919 | None / None |
| qwen3.5-4b | P1 narrowing | `20261105T064023Z-narrowing` | 15 / 18 | 17 / 18 | 11 / 18 | 13 / 18 | 0 | 0 | 0 | None | 47.506 | None / None |
| qwen3.5-4b | P1 raw | `20261104T191940Z-llm` | 6 / 18 | 6 / 18 | 6 / 18 | 7 / 18 | 1 | 0 | 5 | 0.3025 | 1169.673 | 40945 / 2476 |
| qwen3.5-4b | P1 summary | `20261104T193944Z-llm` | 9 / 18 | 15 / 18 | 7 / 18 | 11 / 18 | 0 | 0 | 8 | 0.5425 | 1209.223 | 40686 / 3654 |
| qwen3.5-4b | P1 narrowed | `20261104T200033Z-llm` | 13 / 18 | 16 / 18 | 9 / 18 | 14 / 18 | 1 | 0 | 13 | 0.4154 | 1255.071 | 42595 / 3812 |
| gpt-oss-120b | P1 raw (bilgi) | `20261104T222149Z-llm` | 7 / 18 | 7 / 18 | 3 / 18 | 4 / 18 | 1 | 0 | 2 | 0.489 | 16.406 | 34673 / 3616 |
| gpt-oss-120b | P1 summary (bilgi) | `20261104T223304Z-llm` | 12 / 18 | 15 / 18 | 10 / 18 | 13 / 18 | 2 | 0 | 6 | 0.2907 | 26.761 | 38013 / 6616 |
| gpt-oss-120b | P1 narrowed (bilgi) | `20261104T225308Z-llm` | 15 / 18 | 17 / 18 | 12 / 18 | 15 / 18 | 1 | 0 | 10 | 0.2618 | 26.936 | 39828 / 6266 |
| qwen3.5-9b | P1 raw (bilgi) | `20261104T203043Z-llm` | 7 / 18 | 7 / 18 | 6 / 18 | 7 / 18 | 0 | 0 | 7 | 0.3625 | 1971.858 | 40945 / 2383 |
| qwen3.5-9b | P1 summary (bilgi) | `20261104T210418Z-llm` | 8 / 18 | 14 / 18 | 8 / 18 | 13 / 18 | 0 | 0 | 9 | 0.4825 | 2149.18 | 40686 / 3838 |
| qwen3.5-9b | P1 narrowed (bilgi) | `20261104T214129Z-llm` | 11 / 18 | 16 / 18 | 11 / 18 | 16 / 18 | 0 | 0 | 16 | 0.3525 | 2224.676 | 42595 / 3966 |
