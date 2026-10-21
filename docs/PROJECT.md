# PROJECT

## Ne
Mikroservis ortamına (OpenTelemetry Demo + kendi Python servisim) bilerek hata enjekte edip,
kök nedeni bulan yöntemleri aynı vakalar üzerinde ölçen bir altyapı ve üzerinde iki proje:

- **Proje 1:** CPU'da çalışan küçük lokal model (`small_local_model`) + istatistiksel daraltma (hibrit),
  kanıt/yol doğrulaması ve "emin değilim" diyebilme (kalibrasyon).
- **Proje 2:** Büyük API modeli (`large_api_model`) ile araçlı ajan (Proje 1 bittikten sonra).

Tüm yöntemler aynı vakalarda baseline'lara (kural, BARO) karşı ölçülür.
`large_api_model` satırları iki modelle koşulur (Groq gpt-oss-120b, Gemini 3.5 Flash Lite), ayarlar birebir aynı.

## Neden
Logların dışarı çıkamadığı bir ortamda küçük lokal model, doğru desteklenirse
kök neden analizinde ne kadar iş görür?

## Bitti sayılması için
- [ ] Otomatik vaka üretimi: enjekte et → kaydet → temizle (gece boyu çalışabilir)
- [ ] En az 30 vakalık snapshot seti; bir kısmı geliştirmede hiç görülmemiş test seti
- [ ] Sonuç tablosu: baseline'lar, `small_local_model` / `large_api_model` × ham log / daraltma
- [ ] Ölçütler: top-1/top-3, kanıt geçerliliği, kalibrasyon, süre, token
- [ ] Canlı demo: hata enjekte et → kanıtlı olay raporu (+ bir sonraki adım önerisi)
- [ ] CI yeşil: birim testler + sabit snapshot'larda baseline regresyonu + servis imajı (GHCR)
- [ ] Sızıntı kontrolü: snapshot'larda cevabı ele veren veri yok (flagd vb.), testle doğrulandı
- [ ] Vaka çeşitliliği: set en az zincirleme hata, sessiz hata (log yok, sadece metrik) ve yanıltıcı gürültü içeriyor
- [ ] Tekrarlanabilirlik:
  - Seviye 1 (her makinede ve CI'da): Sonuç tablosu, repodaki resmî koşu cevapları + etiketler + baseline çıktılarından tek komutla yeniden üretilir
  - Seviye 2 (deneyi baştan koşmak): Tam snapshot seti proje sonunda GitHub Releases'te sıkıştırılmış olarak yayınlandı
- [ ] Sonuç tablosu geliştirme ve test setini yan yana gösteriyor
- [ ] Hata analizi: başarısız vakalar 12'li hata sınıflandırmasıyla etiketlendi (arXiv 2602.09937)
- [ ] DevOps kontrol listesi dolduruldu (aşağıda)
- [ ] Proje 2 (ajan): Proje 1 bittikten sonra
  - Ajan aynı vakalarda hem dosyadan hem canlı izleme sisteminden (Prometheus, Jaeger, OpenSearch) koşuldu, iki satır tabloda yan yana
  - Aynı araç çağrılarının dosya ve canlı çıktıları karşılaştırıldı, farklar açıklandı

### DevOps kontrol listesi
Proje sonunda her satır için: gerçekten yaptım mı?

| Beceri | Projede nerede | Yapıldı |
|---|---|---|
| Dockerfile, imaj oluşturma | Kendi Python servisim | [ ] |
| OTel instrumentation | Kendi Python servisim | [ ] |
| Docker Compose, kaynak limitleri | OTel Demo yığını | [ ] |
| Telemetri hattı (collector) | Sızıntı süzmesi, dosyaya ve izleme sistemine çift çıkış | [ ] |
| Kalıcı depolama, saklama süresi | Jaeger diske, Prometheus/OpenSearch saklama | [ ] |
| PromQL, Jaeger ve log sorguları | Snapshot kaydedici, ajan araçları | [ ] |
| Linux ağ/kaynak hataları (tc netem, CPU/bellek, kill) | Hata enjeksiyonu | [ ] |
| Otomasyon betikleri | Gece boyu vaka üretim hattı | [ ] |
| Grafana dashboard | Canlı demo | [ ] |
| CI/CD (GitHub Actions, GHCR) | Testler, regresyon, imaj | [ ] kısmen: testler PR'da ve main'de (`.github/workflows/ci.yml`); baseline regresyonu ve GHCR imajı yok |
| Dağıtık sistemde sorun giderme | Kurulum ve işletme | [ ] |

## Kapsam dışı
- Otomatik düzeltme (ajan sadece bir sonraki adımı önerir, uygulamaz)
- Bulut (staj sonrası ayrı proje)
- HolmesGPT (geri planda, ileride tekrar gündeme gelebilir)

### Şartlı ekler
- **Kubernetes** (kind + OTel Demo Helm): yeni makine gelince karar verilecek.
  Önerilen kural: 3. hafta sonunda ana sonuç tablosu dolu değilse yapılmaz.
- **Web arayüzü** (tek sayfa: hata seç + buton + kanıtlı rapor): ana sonuç tablosu dolduktan sonra.
  Kütüphane seçimi o zaman sorulacak.

## Şu an
Repo GitHub'da (erenbezek/aiops_rca), açık; iş akışı: görev başına `task/<konu>` dalı + PR, merge Eren'de.
Hazır olanlar: duman testi, satır sonları, OTel Demo keşfi ve veri akışı kararı, vaka kataloğu, sızıntı testi (PR #3; `positive_control` yeni makinede).
CI iskeleti PR #4 ile birleşti: main push koşusu yeşil, dal koruması açık, kasıtlı kırmızı gösterildi (PR #5). CI `ubuntu-24.04`e sabit (PR #6).
Makine değişimi yapıldı: proje Ubuntu 24.04'te `~/cerebrum2/aiops_rca`, `pytest` 190 yeşil, CI ve paket Python 3.12 (PR #8). API anahtarları `~/.config/aiops_rca/keys.env`'de, duman testi Groq ve Gemini'de geçti.
Docker Engine 29.9.1 kurulu (resmî apt deposu, Compose v5.6.0), sudo'suz çalışıyor, açılışta başlıyor (PR #9).
OTel Demo 3.1.0 minimal modda çalışıyor (`tools/otel_demo.sh`, `task/otel-demo-setup`): 25 konteyner ~2,9 GiB, imaj sürümü sabit, log sınırlı, portlar sadece `127.0.0.1`. Collector süzmesi/dosya çıkışı ve kalıcı depolama henüz yok.
Lokal model hız ölçümü yapıldı (`task/local-model-bench`, `docs/LOCAL_MODEL_BENCH.md`): llama.cpp b11723, Qwen3.5 Q4_K_M; 2048+300 bütçesine 2B (30 sn) ve 4B (73 sn) sığıyor, 9B (127 sn) sığmıyor; en iyi ayar 4 iş parçacığı; ısınmayla yavaşlama yok. Şarj sınırı %80 kalıcı (`battery-charge-limit.service`).
Sıradaki karar: model seçimi (boyut ve aile; kalite ölçülmedi).
Collector C1 yapıldı (`task/collector-filter`): süzme (flag/flagd/load-generator izleri, host süreç metrikleri, collector logları), dosya çıkışı `~/cerebrum2/telemetry/filtered/` (~630 MB/saat), `--raw` süzülmemiş kopya, flag dosyası klon dışında. 30 dk normal koşuda sızıntı testi 0 bulgu.
Sıradaki: C2 (`positive_control` + belirti korunması, kalibrasyonla aynı gece); depolama kartı (isimli volume); vaka üretimi (gece koşucusu).
