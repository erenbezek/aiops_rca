# P2d test hata analizi özeti

Üreten: `python tools/agent_error_analysis.py summary --set test`. Etiketler `results/p2d_error_labels.json` sha256 `77386f46126875e1e2c8c2f4de1a1855991cbb336933d9d4d4e6cf2021351706`, sorular sha256 `b887cbbb9a7a199b1cd1aee6c3efcee68573b09f753152283a677d86f2e07cbd` (tam metin etiket dosyasında; DECISIONS 2026-11-14). Kapsam: test, resmî dosya koşuları (Gemini 1. koşu, 4B), top-1'i ıskalayan 22 satır. T10 uygulanamaz.

## 1. Tuzaklar, ıskalanan satırlar (evet / hayır / belirlenemez)

| Model | n | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | 8 | 2/6/0 | 6/2/0 | 4/4/0 | 0/8/0 | 1/7/0 | 0/8/0 | 7/1/0 | 0/8/0 | 0/8/0 | 0/8/0 | 2/6/0 |
| qwen3.5-4b | 14 | 9/3/2 | 13/1/0 | 8/4/2 | 0/14/0 | 6/8/0 | 2/10/2 | 7/5/2 | 2/12/0 | 3/11/0 | 2/12/0 | 12/2/0 |
| toplam | 22 | 11/9/2 | 19/3/0 | 12/8/2 | 0/22/0 | 7/15/0 | 2/18/2 | 14/6/2 | 2/20/0 | 3/19/0 | 2/20/0 | 14/8/0 |

## 2. Kodla sayılan tuzaklar, 18 vakanın tümü (bilgi)

| Model | n | T2 | T3 | T4 | T5 | T7 | T9 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | 18 | 11/7/0 | 4/14/0 | 0/18/0 | 2/16/0 | 15/3/0 | 0/18/0 | 0/18/0 | 7/11/0 |
| qwen3.5-4b | 18 | 13/5/0 | 8/8/2 | 0/18/0 | 9/9/0 | 10/6/2 | 4/14/0 | 2/16/0 | 16/2/0 |

## 3. Eren doğrulaması

Örneklem 10 satır (tohum 20261104); işaretlenen 10, katılmıyorum 4. Okuma: yeniden etiketleme (≥ 3 katılmıyorum).

2. tur (1. tur yeniden etiketleme okudu; yeniden etiketlemeden sonra örneklem dışındaki 12 satırın tümü): işaretlenen 12, katılmıyorum 0. Okuma: tamam (< 3 katılmıyorum).
