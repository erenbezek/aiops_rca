# P2c hata analizi özeti

Üreten: `python tools/agent_error_analysis.py summary`. Etiketler `results/p2c_error_labels.json` sha256 `71ba4cc6b7a39ff336fa2af31f163ca86bec629bd52ff06dc5d2806ee860a492`, sorular sha256 `b887cbbb9a7a199b1cd1aee6c3efcee68573b09f753152283a677d86f2e07cbd` (tam metin etiket dosyasında; DECISIONS 2026-11-14). Kapsam: dev, resmî dosya koşuları (Gemini 1. koşu, 4B), top-1'i ıskalayan 23 satır. T10 uygulanamaz.

## 1. Tuzaklar, ıskalanan satırlar (evet / hayır / belirlenemez)

| Model | n | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | 9 | 1/7/1 | 6/3/0 | 1/7/1 | 0/9/0 | 2/7/0 | 0/8/1 | 7/1/1 | 0/9/0 | 0/9/0 | 0/9/0 | 5/4/0 |
| qwen3.5-4b | 14 | 6/7/1 | 11/3/0 | 10/3/1 | 0/14/0 | 11/3/0 | 3/10/1 | 12/1/1 | 0/14/0 | 3/11/0 | 3/11/0 | 13/1/0 |
| toplam | 23 | 7/14/2 | 17/6/0 | 11/10/2 | 0/23/0 | 13/10/0 | 3/18/2 | 19/2/2 | 0/23/0 | 3/20/0 | 3/20/0 | 18/5/0 |

## 2. Kodla sayılan tuzaklar, 18 vakanın tümü (bilgi)

| Model | n | T2 | T3 | T4 | T5 | T7 | T9 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | 18 | 11/7/0 | 1/16/1 | 0/18/0 | 3/15/0 | 13/4/1 | 0/18/0 | 0/18/0 | 8/10/0 |
| qwen3.5-4b | 18 | 13/5/0 | 10/7/1 | 0/18/0 | 12/6/0 | 14/3/1 | 5/13/0 | 4/14/0 | 17/1/0 |

## 3. Eren doğrulaması

Örneklem 10 satır (tohum 20261104); işaretlenen 10, katılmıyorum 0. Okuma: tamam (< 3 katılmıyorum).
