# P1 test hata analizi özeti (P2d)

Üreten: `python -m aiops_rca.error_analysis summary --set test`. Etiketler `results/p1_test_error_labels.json` sha256 `51d637d9e794e4ae9da57b68472b50b6bc27fbd6ab6deaee54a8b0eaa91740b7`, sorular sha256 `dc58d84a1ea8e092b507c905be0573d2efc2bb176c72d53688de03bf77b687f7` (tam metin etiket dosyasında). Kapsam: test, P1e test koşuları, 4B / gpt-oss / Gemini × ham / özet / daraltma; girdi sorulmuş, şema içi, top-1'i ıskalayan 54 satır.

## 1. Otomatik türler (test, satır başına 18 vaka)

| Satır | boş | bütçe aşımı | cevapsız | şema dışı | tekrar döngüsü | top-1 isabet | etiketlenen |
|---|---|---|---|---|---|---|---|
| qwen3.5-4b ham | 8 | 0 | 0 | 1 | 0 | 6 | 3 |
| qwen3.5-4b özet | 0 | 0 | 0 | 0 | 0 | 7 | 11 |
| qwen3.5-4b daraltma | 0 | 0 | 0 | 1 | 0 | 9 | 8 |
| gpt-oss-120b ham | 8 | 0 | 0 | 1 | 0 | 3 | 6 |
| gpt-oss-120b özet | 0 | 0 | 0 | 2 | 0 | 10 | 6 |
| gpt-oss-120b daraltma | 0 | 0 | 0 | 1 | 0 | 12 | 5 |
| gemini-3.5-flash-lite ham | 8 | 0 | 0 | 0 | 0 | 6 | 4 |
| gemini-3.5-flash-lite özet | 0 | 0 | 0 | 0 | 0 | 10 | 8 |
| gemini-3.5-flash-lite daraltma | 0 | 0 | 0 | 0 | 0 | 15 | 3 |

## 2. Tuzaklar (evet / hayır / belirlenemez)

| Satır | n | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|---|
| qwen3.5-4b ham | 3 | 1/2/0 | 1/1/1 | 3/0/0 | 0/0/3 | 0/3/0 | 0/3/0 |
| qwen3.5-4b özet | 11 | 6/5/0 | 4/4/3 | 11/0/0 | 0/8/3 | 0/11/0 | 3/8/0 |
| qwen3.5-4b daraltma | 8 | 4/4/0 | 1/5/2 | 8/0/0 | 0/6/2 | 0/8/0 | 2/6/0 |
| gpt-oss-120b ham | 6 | 1/5/0 | 4/1/1 | 3/0/3 | 0/1/5 | 0/6/0 | 0/6/0 |
| gpt-oss-120b özet | 6 | 1/5/0 | 0/2/4 | 4/2/0 | 0/2/4 | 0/6/0 | 1/5/0 |
| gpt-oss-120b daraltma | 5 | 1/4/0 | 0/3/2 | 4/1/0 | 0/3/2 | 0/5/0 | 1/4/0 |
| gemini-3.5-flash-lite ham | 4 | 0/4/0 | 3/0/1 | 2/0/2 | 0/0/4 | 0/4/0 | 0/4/0 |
| gemini-3.5-flash-lite özet | 8 | 1/7/0 | 3/1/4 | 6/2/0 | 0/4/4 | 0/8/0 | 1/7/0 |
| gemini-3.5-flash-lite daraltma | 3 | 0/3/0 | 0/1/2 | 3/0/0 | 0/1/2 | 0/3/0 | 0/3/0 |
| toplam | 54 | 15/39/0 | 16/18/20 | 44/5/5 | 0/25/29 | 0/54/0 | 8/46/0 |

## 3. Kökün görünürlüğüne göre T3

| Görünürlük | n | T3 evet | T3 hayır | T3 belirlenemez |
|---|---|---|---|---|
| direct | 25 | 21 | 3 | 1 |
| indirect | 9 | 5 | 0 | 4 |
| absent | 20 | 18 | 2 | 0 |

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

Örneklem 10 satır (tohum 20261104); işaretlenen 10, katılmıyorum 4. Okuma: yeniden etiketleme (≥ 3 katılmıyorum).

2. tur (1. tur yeniden etiketleme okudu; yeniden etiketlemeden sonra örneklem dışındaki 44 satırın tümü): işaretlenen 0, katılmıyorum 0. Okuma: bekliyor.
