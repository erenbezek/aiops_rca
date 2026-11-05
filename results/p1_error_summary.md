# P1e hata analizi özeti

Üreten: `python -m aiops_rca.error_analysis summary`. Etiketler `results/p1_error_labels.json` sha256 `59a21fa8ab28278b60c104ff43861643b41220c5ba1cdcde8d9a4227b2f58b4a`, sorular sha256 `dc58d84a1ea8e092b507c905be0573d2efc2bb176c72d53688de03bf77b687f7` (tam metin etiket dosyasında). Kapsam: dev, P1d a1 (gerçek ad), 4B / gpt-oss / Gemini × ham / özet / daraltma; girdi sorulmuş, şema içi, top-1'i ıskalayan 29 satır.

## 1. Otomatik türler (dev, satır başına 18 vaka)

| Satır | boş | bütçe aşımı | cevapsız | şema dışı | tekrar döngüsü | top-1 isabet | etiketlenen |
|---|---|---|---|---|---|---|---|
| qwen3.5-4b ham | 8 | 0 | 0 | 2 | 0 | 6 | 2 |
| qwen3.5-4b özet | 0 | 0 | 0 | 0 | 0 | 9 | 9 |
| qwen3.5-4b daraltma | 0 | 0 | 0 | 0 | 0 | 13 | 5 |
| gpt-oss-120b ham | 8 | 0 | 0 | 2 | 0 | 7 | 1 |
| gpt-oss-120b özet | 0 | 0 | 0 | 3 | 0 | 12 | 3 |
| gpt-oss-120b daraltma | 0 | 0 | 0 | 1 | 0 | 15 | 2 |
| gemini-3.5-flash-lite ham | 8 | 0 | 0 | 2 | 0 | 7 | 1 |
| gemini-3.5-flash-lite özet | 0 | 0 | 0 | 1 | 0 | 12 | 5 |
| gemini-3.5-flash-lite daraltma | 0 | 0 | 0 | 0 | 0 | 17 | 1 |

## 2. Tuzaklar (evet / hayır / belirlenemez)

| Satır | n | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|---|
| qwen3.5-4b ham | 2 | 1/1/0 | 1/0/1 | 1/1/0 | 0/0/2 | 0/2/0 | 0/2/0 |
| qwen3.5-4b özet | 9 | 3/6/0 | 2/6/1 | 9/0/0 | 0/8/1 | 0/9/0 | 3/6/0 |
| qwen3.5-4b daraltma | 5 | 2/3/0 | 2/3/0 | 4/1/0 | 0/5/0 | 1/4/0 | 2/3/0 |
| gpt-oss-120b ham | 1 | 0/1/0 | 1/0/0 | 1/0/0 | 0/0/1 | 0/1/0 | 0/1/0 |
| gpt-oss-120b özet | 3 | 1/2/0 | 0/3/0 | 2/1/0 | 0/3/0 | 0/3/0 | 2/1/0 |
| gpt-oss-120b daraltma | 2 | 0/2/0 | 0/2/0 | 2/0/0 | 0/2/0 | 0/2/0 | 1/1/0 |
| gemini-3.5-flash-lite ham | 1 | 0/1/0 | 1/0/0 | 1/0/0 | 0/0/1 | 0/1/0 | 0/1/0 |
| gemini-3.5-flash-lite özet | 5 | 0/5/0 | 1/4/0 | 4/1/0 | 0/3/2 | 0/5/0 | 3/2/0 |
| gemini-3.5-flash-lite daraltma | 1 | 0/1/0 | 0/1/0 | 1/0/0 | 0/1/0 | 0/1/0 | 1/0/0 |
| toplam | 29 | 7/22/0 | 8/19/2 | 25/4/0 | 0/22/7 | 1/28/0 | 12/17/0 |

## 3. Kökün görünürlüğüne göre T3

| Görünürlük | n | T3 evet | T3 hayır | T3 belirlenemez |
|---|---|---|---|---|
| direct | 22 | 20 | 2 | 0 |
| indirect | 3 | 3 | 0 | 0 |
| absent | 4 | 2 | 2 | 0 |

## 4. Ad eşlenmemesiyle ıskalama sayılan satırlar (LLM, dev ve test)

Kök ilk 3'te eşlenmemiş bir adla geçiyor (`name_key` aynı: küçük harf, son nokta parçası, `/` öncesi, sondaki `service` atılır, yalnız harfler) ve satır ıskalama sayılmış. Puanlama değişmez; hücre başına sayım, vaka yok. "1. sırada": o ad 1. adaydı.

| Satır | dev | dev 1. sırada | test | test 1. sırada |
|---|---|---|---|---|
| qwen3.5-4b ham | 1 | 0 | 1 | 0 |
| qwen3.5-4b özet | 0 | 0 | 0 | 0 |
| qwen3.5-4b daraltma | 0 | 0 | 0 | 0 |
| gpt-oss-120b ham | 1 | 0 | 3 | 1 |
| gpt-oss-120b özet | 0 | 0 | 0 | 0 |
| gpt-oss-120b daraltma | 0 | 0 | 0 | 0 |
| gemini-3.5-flash-lite ham | 0 | 0 | 2 | 2 |
| gemini-3.5-flash-lite özet | 0 | 0 | 0 | 0 |
| gemini-3.5-flash-lite daraltma | 0 | 0 | 0 | 0 |
| qwen3.5-9b ham | 0 | 0 | 1 | 0 |
| qwen3.5-9b özet | 0 | 0 | 0 | 0 |
| qwen3.5-9b daraltma | 0 | 0 | 0 | 0 |
| toplam | 2 | 0 | 7 | 3 |

## 5. Eren doğrulaması

Örneklem 10 satır (tohum 20261104); işaretlenen 10, katılmıyorum 1. Okuma: tamam (< 3 katılmıyorum).
