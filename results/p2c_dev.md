# P2c dev koşuları

Komutla üretilir: `python tools/agent_report.py --report p2c_dev` (kaynak `eval_responses/`'teki dev koşuları, `results/p2c_dev_calls.json` sha256 `3624d8c6fe13cf61fd59627c4598264bf4299bac2e6097c23a42b45e38065bc3`, `results/p1_runs.json`'daki P1 dev koşuları). Tasarım donmuş (DECISIONS 2026-11-14); okuma kuralları koşudan önce yazıldı. Resmî sonuç P2d'deki test koşusudur; dev okuması tasarımı değiştirmez.

## Koşular

| Koşu | Klasör | Bitişler | Geçerli son cevap | Araç sayısı (vaka) | İstek | Token giriş / çıkış | Süre ort / en çok (sn) | En uzun mesaj | Kırpmalı vaka | Bütçe bitişi | Tekrar | Araç hatası | Kesilen sonuç | HTTP | top-1 (dev) | top-3 (dev) | Yeniden deneme (istek / bekleme sn) | Taşıma hatasıyla cevapsız |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini, dosya, 1. koşu (resmî) | `20261114T194507Z-agent` | answer 9, schema_answer 1, step_limit 8 | 17/18 | 3: 3, 5: 2, 6: 2, 7: 3, 8: 8 | 144 | 412936 / 21914 | 15.1 / 19.8 | 5728 | 0 | 0 | 0 | 0 | 28 | 200: 144 | 9/18 | 14/18 | 0 / 0 | 0 |
| Gemini, dosya, 2. koşu (gürültü tabanı) | `20261114T200540Z-agent` | answer 8, step_limit 10 | 18/18 | 5: 2, 6: 2, 7: 4, 8: 10 | 156 | 459495 / 23640 | 16.1 / 17.7 | 5571 | 0 | 0 | 0 | 0 | 26 | 200: 156 | 9/18 | 15/18 | 0 / 0 | 0 |
| qwen3.5-4b, dosya | `20261114T202141Z-agent` | schema_answer 1, step_limit 17 | 17/18 | 8: 18 | 162 | 493556 / 22151 | 287.9 / 488.2 | 5998 | 4 | 0 | 12 | 0 | 21 | 200: 162 | 4/18 | 9/18 | 0 / 0 | 0 |
| Gemini, canlı | `20261115T153308Z-agent` | answer 11, step_limit 7 | 18/18 | 4: 2, 5: 3, 6: 2, 7: 4, 8: 7 | 148 | 430891 / 21831 | 50.6 / 118.6 | 5361 | 0 | 0 | 0 | 0 | 28 | 200: 148, 503: 6 | 9/18 | 14/18 | 6 / 180 | 0 |
| qwen3.5-4b, canlı | `20261115T153310Z-agent` | schema_answer 1, step_limit 17 | 17/18 | 8: 18 | 162 | 493556 / 22151 | 367.5 / 610.6 | 5998 | 4 | 0 | 12 | 0 | 21 | 200: 162 | 4/18 | 9/18 | 0 / 0 | 0 |

Süre sütunu kayıttaki `duration_s` (yeniden deneme beklemesi içinde; istek aralığı beklemesi hariç); yeniden deneme beklemesi ayrı sütunda.

- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09): Gemini, dosya, 1. koşu (resmî) 0/18; Gemini, dosya, 2. koşu (gürültü tabanı) 0/18; qwen3.5-4b, dosya 0/18; Gemini, canlı 0/18; qwen3.5-4b, canlı 0/18 → **tetiklenmedi**.
- **Kod:** Gemini, dosya, 1. koşu (resmî) `e9324b7`; Gemini, dosya, 2. koşu (gürültü tabanı) `e9324b7`; qwen3.5-4b, dosya `e9324b7`; Gemini, canlı `0ac4edc`; qwen3.5-4b, canlı `0ac4edc`. Dosya koşuları ile canlı koşu arasındaki kod farkı yalnız canlı koşucu (`tools/agent_live.py`: yerel sunucu her oynatmadan önce yeniden açılır, başta takas denetimi); `src/` ve istem aynı.
- **Teknik kesinti:** 2 (puanlanmadı; canlı koşu baştan koşuldu): `20261115T132147Z-agent` / `20261115T132149Z-agent`, 5 vaka, takas koruması (boş takas < 1 GB) kalan 13 vakayı oynatmadı; `20261115T141055Z-agent` / `20261115T141057Z-agent`, 2 vaka, durduruldu (yerel sunucunun istem önbelleği vaka başına büyüyordu).
- **Okuma notu (sonuçtan önce yazıldı, DECISIONS 2026-11-15):** 4B dosya koşusunda yerel sunucunun istem önbelleği önceki vakalardan doluydu, canlıda her vaka boş önbellekle başladı; "çıktı aynı, model ayrıştı" çıkarsa sayılır ve bu fark olası neden olarak sınırlamalara yazılır.

## Dosya ↔ canlı (DECISIONS 2026-11-14, üç katman)

### gemini-3.5-flash-lite

- **(1) Çağrı düzeyi:** 119 canlı çağrı (18 vaka): aynı 119, bilinen tür (`zero_duration`) 0, **açıklanamayan 0** (beklenen 0).
- **(2) Sonuç düzeyi, top-3 (eşleştirilmiş kesin işaret testi):** dosya 14 / 18, canlı 14 / 18; yalnız dosya 2, yalnız canlı 2; p = 1.0 → **ayırt edilemedi**.

### qwen3.5-4b

- **(1) Çağrı düzeyi:** 144 canlı çağrı (18 vaka): aynı 144, bilinen tür (`zero_duration`) 0, **açıklanamayan 0** (beklenen 0).
- **4B denetimi:** 18 vakada çıktı aynıyken model ayrıştı: 0 (-); bir araç çıktısı farklı: 0; baştan sona aynı: 18.
- **(2) Sonuç düzeyi, top-3 (eşleştirilmiş kesin işaret testi):** dosya 9 / 18, canlı 9 / 18; yalnız dosya 0, yalnız canlı 0; p = 1.0 → **ayırt edilemedi**.

- **(3) Gürültü tabanı (Gemini, betimsel):** top-3 sonucu ayrışan vaka: dosya 1 ↔ dosya 2 3 / 18, dosya 1 ↔ canlı 4 / 18.

## Ajan ↔ P1 (DECISIONS 2026-11-14, model başına iki hücre)

Ajan tarafı dosya modunun ilk koşusu; P1 tarafı aynı modelin dev koşuları (P1d a1, gerçek ad). Geçerli cevabı olmayan vaka bilinmemiş. Dört hücrede çoklu karşılaştırma düzeltmesi yok.

- **gemini-3.5-flash-lite, (a) ajan ↔ ham, top-3:** ajan 14 / 18, ham 7 / 18; yalnız ajan 8, yalnız ham 1; p = 0.0391 → **fark: ajan lehine**.
- **gemini-3.5-flash-lite, (b) ajan ↔ daraltma, top-1:** ajan 9 / 18, daraltma 17 / 18; yalnız ajan 0, yalnız daraltma 8; p = 0.0078 → **fark: daraltma lehine**.
- **qwen3.5-4b, (a) ajan ↔ ham, top-3:** ajan 9 / 18, ham 6 / 18; yalnız ajan 5, yalnız ham 2; p = 0.4531 → **ayırt edilemedi**.
- **qwen3.5-4b, (b) ajan ↔ daraltma, top-1:** ajan 4 / 18, daraltma 13 / 18; yalnız ajan 0, yalnız daraltma 9; p = 0.0039 → **fark: daraltma lehine**.

## Öteki ölçüler (yalnız sayı; dev, 18 vaka)

| Model | Satır | Koşu | top-1 | top-3 | Şema dışı | Cevapsız | Kanıt geçerli | Brier | Süre toplam (sn) | Token giriş / çıkış |
|---|---|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | Gemini, dosya, 1. koşu (resmî) | `20261114T194507Z-agent` | 9 | 14 | 1 | 0 | 11 | 0.2854 | 271.403 | 412936 / 21914 |
| gemini-3.5-flash-lite | Gemini, canlı | `20261115T153308Z-agent` | 9 | 14 | 0 | 0 | 10 | 0.3239 | 910.251 | 430891 / 21831 |
| gemini-3.5-flash-lite | rule | `20261030T104544Z-rule` | 9 | 15 | 0 | None | 0 | None | 29.436 | None / None |
| gemini-3.5-flash-lite | baro | `20261031T060600Z-baro` | 5 | 10 | 0 | None | 0 | None | 23.143 | None / None |
| gemini-3.5-flash-lite | narrowing | `20261104T085716Z-narrowing` | 15 | 17 | 0 | 0 | 0 | None | 48.128 | None / None |
| gemini-3.5-flash-lite | raw | `20261101T114830Z-llm` | 7 | 7 | 2 | 0 | 4 | 0.0713 | 19.11 | 37510 / 2359 |
| gemini-3.5-flash-lite | summary | `20261101T114947Z-llm` | 12 | 16 | 1 | 0 | 9 | 0.1828 | 33.906 | 48741 / 3864 |
| gemini-3.5-flash-lite | narrowed | `20261101T115120Z-llm` | 17 | 18 | 0 | 0 | 15 | 0.0632 | 34.267 | 48091 / 3760 |
| qwen3.5-4b | qwen3.5-4b, dosya | `20261114T202141Z-agent` | 4 | 9 | 1 | 0 | 8 | 0.5872 | 5182.639 | 493556 / 22151 |
| qwen3.5-4b | qwen3.5-4b, canlı | `20261115T153310Z-agent` | 4 | 9 | 1 | 0 | 8 | 0.5872 | 6615.628 | 493556 / 22151 |
| qwen3.5-4b | rule | `20261030T104544Z-rule` | 9 | 15 | 0 | None | 0 | None | 29.436 | None / None |
| qwen3.5-4b | baro | `20261031T060600Z-baro` | 5 | 10 | 0 | None | 0 | None | 23.143 | None / None |
| qwen3.5-4b | narrowing | `20261104T085716Z-narrowing` | 15 | 17 | 0 | 0 | 0 | None | 48.128 | None / None |
| qwen3.5-4b | raw | `20261101T063855Z-llm` | 6 | 6 | 2 | 0 | 2 | 0.2275 | 1021.351 | 35932 / 2336 |
| qwen3.5-4b | summary | `20261101T065655Z-llm` | 9 | 15 | 0 | 0 | 6 | 0.4436 | 1212.372 | 40514 / 3720 |
| qwen3.5-4b | narrowed | `20261101T071807Z-llm` | 13 | 16 | 0 | 0 | 14 | 0.2347 | 1231.681 | 41866 / 3799 |

## Vakalar

### Gemini, dosya, 1. koşu (resmî)

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-0c4902c3` | answer | 6 | 8 | 15.891 | 4523 | 0 | 0 | 0 | evet / evet |
| `inc-230c9d46` | answer | 3 | 5 | 10.214 | 3095 | 0 | 0 | 0 | evet / evet |
| `inc-234d34cf` | schema_answer | 3 | 5 | 10.586 | 3057 | 0 | 0 | 0 | hayır / hayır |
| `inc-320c56f9` | answer | 7 | 9 | 16.024 | 4117 | 0 | 0 | 0 | evet / evet |
| `inc-4a62b9bb` | answer | 5 | 7 | 12.94 | 4066 | 0 | 0 | 0 | hayır / evet |
| `inc-5cb2c977` | step_limit | 8 | 9 | 16.362 | 5105 | 0 | 0 | 0 | hayır / evet |
| `inc-73ac64e9` | step_limit | 8 | 9 | 16.63 | 4429 | 0 | 0 | 0 | hayır / hayır |
| `inc-8069b709` | step_limit | 8 | 9 | 17.789 | 4269 | 0 | 0 | 0 | hayır / hayır |
| `inc-86d286ea` | step_limit | 8 | 9 | 16.4 | 4250 | 0 | 0 | 0 | evet / evet |
| `inc-9292257f` | answer | 7 | 9 | 16.155 | 4600 | 0 | 0 | 0 | hayır / evet |
| `inc-ac155a23` | answer | 3 | 5 | 9.52 | 3044 | 0 | 0 | 0 | hayır / evet |
| `inc-ac820869` | answer | 5 | 7 | 13.398 | 3547 | 0 | 0 | 0 | evet / evet |
| `inc-ae15665a` | step_limit | 8 | 9 | 17.645 | 5105 | 0 | 0 | 0 | hayır / hayır |
| `inc-b4d12a5e` | step_limit | 8 | 9 | 15.607 | 4824 | 0 | 0 | 0 | hayır / evet |
| `inc-bfbbd586` | step_limit | 8 | 9 | 19.77 | 5224 | 0 | 0 | 0 | evet / evet |
| `inc-d6d5f1b2` | answer | 6 | 8 | 14.551 | 4364 | 0 | 0 | 0 | evet / evet |
| `inc-d9ea423d` | answer | 7 | 9 | 15.624 | 4578 | 0 | 0 | 0 | evet / evet |
| `inc-fa775703` | step_limit | 8 | 9 | 16.297 | 5728 | 0 | 0 | 0 | evet / evet |

### Gemini, dosya, 2. koşu (gürültü tabanı)

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-0c4902c3` | answer | 5 | 7 | 13.179 | 4021 | 0 | 0 | 0 | evet / evet |
| `inc-230c9d46` | answer | 7 | 9 | 16.999 | 4476 | 0 | 0 | 0 | evet / evet |
| `inc-234d34cf` | answer | 7 | 9 | 16.902 | 4692 | 0 | 0 | 0 | hayır / evet |
| `inc-320c56f9` | answer | 7 | 9 | 16.896 | 4374 | 0 | 0 | 0 | evet / evet |
| `inc-4a62b9bb` | answer | 5 | 7 | 12.852 | 4041 | 0 | 0 | 0 | hayır / evet |
| `inc-5cb2c977` | step_limit | 8 | 9 | 17.737 | 5571 | 0 | 0 | 0 | hayır / evet |
| `inc-73ac64e9` | step_limit | 8 | 9 | 15.811 | 4440 | 0 | 0 | 0 | evet / evet |
| `inc-8069b709` | step_limit | 8 | 9 | 15.964 | 5000 | 0 | 0 | 0 | hayır / hayır |
| `inc-86d286ea` | answer | 6 | 8 | 14.724 | 4542 | 0 | 0 | 0 | evet / evet |
| `inc-9292257f` | step_limit | 8 | 9 | 15.695 | 4944 | 0 | 0 | 0 | hayır / evet |
| `inc-ac155a23` | step_limit | 8 | 9 | 17.335 | 4570 | 0 | 0 | 0 | hayır / evet |
| `inc-ac820869` | answer | 6 | 8 | 15.985 | 4404 | 0 | 0 | 0 | evet / evet |
| `inc-ae15665a` | step_limit | 8 | 9 | 17.271 | 4322 | 0 | 0 | 0 | hayır / hayır |
| `inc-b4d12a5e` | step_limit | 8 | 9 | 15.873 | 4371 | 0 | 0 | 0 | hayır / hayır |
| `inc-bfbbd586` | step_limit | 8 | 9 | 16.971 | 4845 | 0 | 0 | 0 | evet / evet |
| `inc-d6d5f1b2` | answer | 7 | 9 | 16.479 | 3902 | 0 | 0 | 0 | evet / evet |
| `inc-d9ea423d` | step_limit | 8 | 9 | 16.901 | 4775 | 0 | 0 | 0 | hayır / evet |
| `inc-fa775703` | step_limit | 8 | 9 | 17.081 | 4715 | 0 | 0 | 0 | evet / evet |

### qwen3.5-4b, dosya

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-0c4902c3` | step_limit | 8 | 9 | 211.395 | 4080 | 0 | 0 | 0 | hayır / hayır |
| `inc-230c9d46` | step_limit | 8 | 9 | 259.365 | 5460 | 0 | 0 | 0 | hayır / hayır |
| `inc-234d34cf` | step_limit | 8 | 9 | 262.012 | 5602 | 0 | 0 | 0 | evet / evet |
| `inc-320c56f9` | step_limit | 8 | 9 | 213.141 | 3961 | 0 | 0 | 0 | hayır / hayır |
| `inc-4a62b9bb` | schema_answer | 8 | 9 | 256.385 | 5400 | 0 | 0 | 0 | hayır / hayır |
| `inc-5cb2c977` | step_limit | 8 | 9 | 243.69 | 5200 | 0 | 0 | 0 | hayır / evet |
| `inc-73ac64e9` | step_limit | 8 | 9 | 283.517 | 4922 | 0 | 0 | 0 | hayır / evet |
| `inc-8069b709` | step_limit | 8 | 9 | 379.399 | 5859 | 1 | 0 | 0 | hayır / hayır |
| `inc-86d286ea` | step_limit | 8 | 9 | 305.176 | 5718 | 0 | 0 | 0 | hayır / evet |
| `inc-9292257f` | step_limit | 8 | 9 | 228.55 | 4163 | 0 | 0 | 0 | hayır / evet |
| `inc-ac155a23` | step_limit | 8 | 9 | 269.344 | 5268 | 0 | 1 | 0 | hayır / evet |
| `inc-ac820869` | step_limit | 8 | 9 | 237.004 | 4044 | 0 | 2 | 0 | evet / evet |
| `inc-ae15665a` | step_limit | 8 | 9 | 387.698 | 5780 | 1 | 2 | 0 | hayır / hayır |
| `inc-b4d12a5e` | step_limit | 8 | 9 | 264.955 | 5280 | 0 | 0 | 0 | hayır / hayır |
| `inc-bfbbd586` | step_limit | 8 | 9 | 488.197 | 5683 | 2 | 5 | 0 | hayır / hayır |
| `inc-d6d5f1b2` | step_limit | 8 | 9 | 272.251 | 5245 | 0 | 0 | 0 | evet / evet |
| `inc-d9ea423d` | step_limit | 8 | 9 | 260.729 | 4928 | 0 | 0 | 0 | hayır / hayır |
| `inc-fa775703` | step_limit | 8 | 9 | 359.831 | 5998 | 1 | 2 | 0 | evet / evet |

### Gemini, canlı

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-0c4902c3` | answer | 7 | 9 | 39.449 | 4793 | 0 | 0 | 0 | evet / evet |
| `inc-230c9d46` | answer | 5 | 7 | 33.291 | 4497 | 0 | 0 | 0 | evet / evet |
| `inc-234d34cf` | answer | 4 | 6 | 18.402 | 3281 | 0 | 0 | 0 | hayır / evet |
| `inc-320c56f9` | step_limit | 8 | 9 | 118.589 | 4600 | 0 | 0 | 0 | evet / evet |
| `inc-4a62b9bb` | answer | 4 | 6 | 44.853 | 3742 | 0 | 0 | 0 | hayır / evet |
| `inc-5cb2c977` | step_limit | 8 | 9 | 71.519 | 5361 | 0 | 0 | 0 | hayır / hayır |
| `inc-73ac64e9` | step_limit | 8 | 9 | 51.649 | 4326 | 0 | 0 | 0 | hayır / hayır |
| `inc-8069b709` | step_limit | 8 | 9 | 37.52 | 5118 | 0 | 0 | 0 | evet / evet |
| `inc-86d286ea` | answer | 6 | 8 | 36.805 | 4254 | 0 | 0 | 0 | evet / evet |
| `inc-9292257f` | answer | 7 | 9 | 63.755 | 4326 | 0 | 0 | 0 | hayır / evet |
| `inc-ac155a23` | answer | 5 | 7 | 31.727 | 3644 | 0 | 0 | 0 | hayır / evet |
| `inc-ac820869` | answer | 6 | 8 | 55.635 | 4396 | 0 | 0 | 0 | evet / evet |
| `inc-ae15665a` | step_limit | 8 | 9 | 49.753 | 5291 | 0 | 0 | 0 | hayır / hayır |
| `inc-b4d12a5e` | step_limit | 8 | 9 | 55.443 | 4346 | 0 | 0 | 0 | hayır / evet |
| `inc-bfbbd586` | step_limit | 8 | 9 | 40.602 | 4840 | 0 | 0 | 0 | evet / evet |
| `inc-d6d5f1b2` | answer | 5 | 7 | 20.409 | 4152 | 0 | 0 | 0 | evet / evet |
| `inc-d9ea423d` | answer | 7 | 9 | 70.514 | 3881 | 0 | 0 | 0 | evet / evet |
| `inc-fa775703` | answer | 7 | 9 | 70.336 | 4701 | 0 | 0 | 0 | hayır / hayır |

### qwen3.5-4b, canlı

| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | Araç hatası | top-1 / top-3 (bilgi) |
|---|---|---|---|---|---|---|---|---|---|
| `inc-0c4902c3` | step_limit | 8 | 9 | 265.034 | 4080 | 0 | 0 | 0 | hayır / hayır |
| `inc-230c9d46` | step_limit | 8 | 9 | 302.654 | 5460 | 0 | 0 | 0 | hayır / hayır |
| `inc-234d34cf` | step_limit | 8 | 9 | 436.604 | 5602 | 0 | 0 | 0 | evet / evet |
| `inc-320c56f9` | step_limit | 8 | 9 | 314.512 | 3961 | 0 | 0 | 0 | hayır / hayır |
| `inc-4a62b9bb` | schema_answer | 8 | 9 | 292.079 | 5400 | 0 | 0 | 0 | hayır / hayır |
| `inc-5cb2c977` | step_limit | 8 | 9 | 386.335 | 5200 | 0 | 0 | 0 | hayır / evet |
| `inc-73ac64e9` | step_limit | 8 | 9 | 333.638 | 4922 | 0 | 0 | 0 | hayır / evet |
| `inc-8069b709` | step_limit | 8 | 9 | 438.355 | 5859 | 1 | 0 | 0 | hayır / hayır |
| `inc-86d286ea` | step_limit | 8 | 9 | 380.675 | 5718 | 0 | 0 | 0 | hayır / evet |
| `inc-9292257f` | step_limit | 8 | 9 | 282.236 | 4163 | 0 | 0 | 0 | hayır / evet |
| `inc-ac155a23` | step_limit | 8 | 9 | 294.561 | 5268 | 0 | 1 | 0 | hayır / evet |
| `inc-ac820869` | step_limit | 8 | 9 | 315.51 | 4044 | 0 | 2 | 0 | evet / evet |
| `inc-ae15665a` | step_limit | 8 | 9 | 495.4 | 5780 | 1 | 2 | 0 | hayır / hayır |
| `inc-b4d12a5e` | step_limit | 8 | 9 | 385.691 | 5280 | 0 | 0 | 0 | hayır / hayır |
| `inc-bfbbd586` | step_limit | 8 | 9 | 610.563 | 5683 | 2 | 5 | 0 | hayır / hayır |
| `inc-d6d5f1b2` | step_limit | 8 | 9 | 371.75 | 5245 | 0 | 0 | 0 | evet / evet |
| `inc-d9ea423d` | step_limit | 8 | 9 | 289.538 | 4928 | 0 | 0 | 0 | hayır / hayır |
| `inc-fa775703` | step_limit | 8 | 9 | 420.493 | 5998 | 1 | 2 | 0 | evet / evet |
