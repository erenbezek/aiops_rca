# LOCAL MODEL BENCH

Lokal model hız ölçümü (kart: HANDOFF 2026-10-20 · Planlama → Uygulama; yöntemler ölçmeden önce aynı dosyada).
Amaç: model seçiminden önce bu makinede hangi boyutun süre bütçesine sığdığı. **Kalite ölçülmedi.**

## Kurulum

- Makine: ASUS ExpertBook B1403CVA, Intel Core 5 210H (4 performans + 4 verimlilik çekirdeği, 12 iş parçacığı; AVX2, AVX-VNNI), 16 GB RAM, Ubuntu 24.04, güç profili `balanced`, prizde, şarj sınırı %80.
- llama.cpp: `ghcr.io/ggml-org/llama.cpp:full-b11723`, digest `sha256:8f3c2cd0808a394d1e7ce02f025f453caacbf163389fe6b6443ec3a1efff96a0` (build 11723, commit `31288c9c6`, 2026-10-19). CPU sürümü `alderlake`; `system_info`: `AVX2 = 1`, `AVX_VNNI = 1`.
- Modeller (Qwen3.5, `Q4_K_M`, Hugging Face `unsloth/Qwen3.5-<boyut>-GGUF`, Apache-2.0; nicemleme üçüncü taraf), `~/cerebrum2/models/`:

| Dosya | Repo commit | Boyut | SHA256 |
|---|---|---|---|
| `Qwen3.5-2B-Q4_K_M.gguf` | `f6d5376be1edb4d416d56da11e5397a961aca8ae` | 1,28 GB | `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223` |
| `Qwen3.5-4B-Q4_K_M.gguf` | `e87f176479d0855a907a41277aca2f8ee7a09523` | 2,74 GB | `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4` |
| `Qwen3.5-9B-Q4_K_M.gguf` | `3885219b6810b007914f3a7950a8d1b469d598a5` | 5,68 GB | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |

## Yöntem

- `tools/local_model_bench.sh matrix`: her hücre (model × iş parçacığı) tek `llama-bench -r 1` çağrısı: `-p 2048`, `-n 300`, `-pg 2048,300`, `-pg 6144,300`. Tablo baştan sona 3 tur; hücre başında `x86_pkg_temp` kayda.
- Bütçe süresi = 2348 / `pg2048+300` hızı; ham log = 6444 / `pg6144+300` hızı. Karar: ısınmış 2048+300 ≤ 120 sn GEÇER.
- `tools/local_model_bench.sh sustained 9B 4`: 30 dk `-pg 2048,300` döngüsü (soğuk sonucu 120 sn'ye en yakın model, en iyi iş parçacığı).
- Yavaşlama oranı: ilk 2 dk ile son 10 dk. 9B'de bir iterasyon ~203 sn (75 sn llama-bench ısınma turu + 128 sn ölçüm) olduğu için ilk 2 dk boş kaldı; **ilk iterasyon kullanıldı** (Eren onayı, 2026-10-20). Oran diğer modellere **varsayım** olarak uygulandı.
- İzleme 10 sn'de bir (sıcaklık, frekans, takas, priz, llama-bench `VmRSS`/`VmHWM`); ölçüm `systemd-inhibit` altında, makine boşta, demo kapalı.
- Koşular: `bench_runs/20261020-015311-matrix` (tur 1; tur 2'nin ilk hücresi priz kopması nedeniyle kullanılmadı) + `20261020-033005-matrix` (tur 2–3) + `20261020-065636-sustained`. Özet: `tools/bench_summary.py <üç klasör>`.

## Tablo (soğuk; 3 turun ortalaması ± sapması)

| Model | İş parçacığı | pp2048 t/s | tg300 t/s | 2048+300 süre (sn) | 6144+300 süre (sn) | Başlangıç °C |
|---|---|---|---|---|---|---|
| 2B | 4 | 146,9 ± 0,7 | 23,26 ± 0,48 | 29,9 ± 0,9 | 68,8 ± 0,7 | 51–59 |
| 2B | 8 | 120,9 ± 2,4 | 18,30 ± 0,55 | 35,1 ± 0,2 | 75,9 ± 0,8 | 67–73 |
| 2B | 12 | 122,4 ± 2,4 | 15,23 ± 0,22 | 39,1 ± 0,6 | 85,5 ± 0,6 | 62–68 |
| 4B | 4 | 49,2 ± 0,3 | 10,51 ± 0,05 | 73,0 ± 0,4 | 177,0 ± 1,1 | 58–65 |
| 4B | 8 | 50,1 ± 0,4 | 8,19 ± 0,17 | 102,6 ± 29,4 | 203,7 ± 4,6 | 66–72 |
| 4B | 12 | 50,3 ± 0,4 | 5,76 ± 0,92 | 100,2 ± 6,6 | 218,4 ± 3,5 | 58–63 |
| 9B | 4 | 27,7 ± 0,2 | 6,00 ± 0,11 | 126,9 ± 0,6 | 295,9 ± 2,4 | 57–59 |
| 9B | 8 | 28,5 ± 0,2 | 4,50 ± 0,86 | 151,6 ± 14,2 | 329,1 ± 12,8 | 65–72 |
| 9B | 12 | 28,7 ± 0,2 | 4,77 ± 0,88 | 142,5 ± 17,7 | 323,7 ± 16,8 | 57–59 |

- Üç modelde de en iyi ayar 4 iş parçacığı (performans çekirdekleri). 8 ve 12'de verimlilik çekirdekleri katılıyor: girdi okuma aynı kalıyor, üretim yavaşlıyor ve sapma büyüyor.

## Sürekli yük (9B, 4 iş parçacığı, 30,4 dk, 9 iterasyon)

- 2048+300 hızı 18,23–18,46 t/s (127,2–128,8 sn). İlk iterasyon 18,23 t/s, son 10 dk 18,43 t/s: **+1,1 %** (ısınmayla yavaşlama yok).
- Sıcaklık: ilk dakika 93 °C, sonra ~77 °C sabit; ortalama frekans ~2250 MHz. 95 °C hiç aşılmadı.

## Bütçe sonucu (2048+300 ≤ 120 sn)

| Model | Soğuk | Isınmış | Karar | Not |
|---|---|---|---|---|
| 2B | 29,9 sn | 29,6 sn | GEÇER | ısınmış: varsayım (9B oranı) |
| 4B | 73,0 sn | 72,3 sn | GEÇER | ısınmış: varsayım (9B oranı) |
| 9B | 126,9 sn | 127,4 sn | KALIR | ısınmış: ölçüldü (son 10 dk) |

- Ham log (6144+300, kriter dışı): 2B 68,8 sn, 4B 177,0 sn, 9B 295,9 sn (soğuk).

## Sınırlar

- Bellek (llama-bench `VmHWM`, model dosyası dahil): 9B 6144 bağlamda **8,93 GB** (ayrı test hücresi), 2048 bağlamda 8,79 GB (sürekli yük). ≤ 10 GB GEÇER; pay ~1 GB. 2B ve 4B yeni yöntemle tabloda ölçülmedi (model dosyaları küçük olduğu için 9B'nin altında kalır; çıkarım). Tablodaki ilk bellek sütunu (konteyner cgroup `memory.peak`) eşlenen model dosyasını yanlış konteynere yazdığı için kullanılmadı.
- Sıcaklık: en yüksek 94 °C (tablo), 93 °C (sürekli yük); 95 °C üstünde hiç örnek yok.
- Takas: arttı. Koşu başı → en çok: 60 kB → 328 kB (tur 1), 4,5 MB → 20,5 MB (tur 2–3), 47,7 MB → 116,5 MB (sürekli yük). Bellek darlığı gözlenmedi (en düşük `MemAvailable` ~10,4 GB); boşta duran masaüstü sayfalarının takasa gitmesine benziyor, kanıtlanmadı.
- Priz: tablo koşularında prizden kopma yalnızca tur 2'nin ilk hücresinde (kullanılmadı).

## Dikkat

- 2048 token "daraltılmış girdi" bir varsayım; daraltma yazılınca gerçek uzunluk ölçülür ve bütçe yeniden hesaplanır.
- Isınma turu (`llama-bench` warmup) girdi okuma süresi kadar ek iş; tablo ve sürekli yük sürelerine dahil değil.
- Asıl koşular OpenAI uyumlu sunucuyla olacak: hız ölçümüyle aynı kod için `server-b11723` imajı. Not (2026-10-21): `full-b11723` imajında da `llama-server` var; kaba kalite denemesi onu kullanıyor (yeni indirme ve digest yok). Asıl koşulardaki imaj o kartta kesinleşir.
- Kalite ölçülmedi; nicemleme üçüncü taraf (unsloth). Model seçimi ayrı kararla.
