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
  - Servis imajı (GHCR) tamam (2026-10-29): iki imaj CI'da derlenip main'de gönderiliyor (`images.yml`), koşular digest'le sabit. Açık kalan: baseline regresyonu.
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
| Dockerfile, imaj oluşturma | Kendi Python servisim | [x] quote-gateway ve netem: sabit taban (digest) ve sabit bağımlılıklar, root olmayan kullanıcı; CI'da derleme ve kontrol (`pip freeze` = requirements, `tc -V`), GHCR'da açık paket, koşular digest'le |
| OTel instrumentation | Kendi Python servisim | [ ] |
| Docker Compose, kaynak limitleri | OTel Demo yığını | [ ] |
| Telemetri hattı (collector) | Sızıntı süzmesi, dosyaya ve izleme sistemine çift çıkış | [ ] |
| Kalıcı depolama, saklama süresi | Jaeger diske, Prometheus/OpenSearch saklama | [ ] kısmen: isimli volume, Jaeger diske, 7 gün + boyut sınırları, canlı = dosya doğrulandı; saklamanın silmesi henüz gözlenmedi |
| PromQL, Jaeger ve log sorguları | Snapshot kaydedici, ajan araçları | [ ] |
| Linux ağ/kaynak hataları (tc netem, CPU/bellek, kill) | Hata enjeksiyonu | [x] tc netem (gecikme, kayıp; kendi yardımcı imajla), CPU sınırı, durdurma, dondurma; uygula, geri al, doğrula; bellek sınırı denendi, bu demoda belirti vermediği için çıktı (INCIDENT_CATALOG) |
| Otomasyon betikleri | Gece boyu vaka üretim hattı | [x] koşucu (`scenario_runner.py incidents`: korumalar, enjeksiyon, geri alma ve doğrulama, snapshot, etiket) ve systemd birim şablonu (`deploy/systemd/aiops-incidents@.service`): tek komutla başlar; `systemctl stop`'ta yarıdaki vaka temizlenir (SIGTERM → hata geri alınır, flag kapanır, demo kapanır); kapanmada ya da oturumdan çıkışta temizlik kesilir (kullanıcı yöneticisi 5 sn verir), sonraki koşu kalıntı denetiminde başlamaz; zamanlayıcı yok |
| Grafana dashboard | Canlı demo | [ ] |
| CI/CD (GitHub Actions, GHCR) | Testler, regresyon, imaj | [ ] kısmen: testler PR'da ve main'de (`.github/workflows/ci.yml`); imajlar PR'da derlenip kontrol ediliyor, main'de GHCR'a gönderiliyor (`.github/workflows/images.yml`, üçüncü taraf eylem yok); baseline regresyonu yok |
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
OTel Demo 3.1.0 minimal modda çalışıyor (`tools/otel_demo.sh`, `task/otel-demo-setup`): 25 konteyner ~2,9 GiB, imaj sürümü sabit, log sınırlı, portlar sadece `127.0.0.1`.
Lokal model hız ölçümü yapıldı (`task/local-model-bench`, `docs/LOCAL_MODEL_BENCH.md`): llama.cpp b11723, Qwen3.5 Q4_K_M; 2048+300 bütçesine 2B (30 sn) ve 4B (73 sn) sığıyor, 9B (127 sn) sığmıyor; en iyi ayar 4 iş parçacığı; ısınmayla yavaşlama yok. Şarj sınırı birimi var (`battery-charge-limit.service`), günlükte kapalı, uzun koşudan önce açılır.
Model seçimi (boyut ve aile) kalite ölçülmeden yapılmaz.
Collector C1 yapıldı (`task/collector-filter`): süzme (flag/flagd/load-generator izleri, host süreç metrikleri, collector logları), dosya çıkışı `~/cerebrum2/telemetry/filtered/` (~630 MB/saat), `--raw` süzülmemiş kopya, flag dosyası klon dışında. 30 dk normal koşuda sızıntı testi 0 bulgu. Planlama 2026-10-21'de makinede yeniden ölçtü (PR #12, main `b232f03`).
Kaba kalite denemesi yapıldı (`task/quality-trial`, 2 vaka, kaba sinyal, rapora girmez): 2B, 4B ve iki `large_api_model` iki vakada doğru servisi top-1 buldu; 9B iki cevapta JSON biçimini bozdu (çözemedi sayıldı). Vakalar kolaydı (özet cevaba çok yakındı): boyut farkı ve hibritin gereği görülmedi, model seçimine tek başına girmez. 9B elenmedi; asıl koşularda JSON şeması zorlanır.
Zor deneme yapıldı (`task/quality-trial-2`, 4 vaka, kaba sinyal, rapora girmez): özete konteyner CPU/bellek (CPU birikimli sayaçtan; `container.cpu.utilization` bu sürümde anlık değil), JSON şeması beş modelde çalıştı (20/20 geçerli). Belirtili 3 vakada (ad, product-catalog ×2) büyük modeller ve 4B/9B doğru servisi ilk 3'te buldu, 2B birinde: kural "umut var". Örnek küçük ve iki vaka aynı servis; `intlShippingSlowdown` belirtisiz (gecikme shipping isteklerinin ~%2'sinde, p95 göremiyor; C2 kalibrasyonunda karar).
Takma ad ön denemesi yapıldı (`task/alias-trial`, 6 özet, kaba sinyal, rapora girmez): gerçek adla iki koşu (gürültü 0) ve takma adla bir koşu; beş modelde de belirtili 5 vakada çözülen sayı takma adla aynı ya da 1 eksik (9B): kural "ezber bu vakalarda görülmedi". Bilgi yoklamasında hiçbir model demonun flag'lerini bilmedi (en iyi 1/13).
Collector C2 yapıldı (PR #16, main `9cf8e6e`): senaryo koşucusu ve ölçüm, 15 senaryo (gece + gözetimli + recommendation yeniden koşusu). Süzme 15/15'te sızıntıyı temizledi, aşırı süzme yok (raw = filtered belirtiler), collector kayıpsız. Belirtili 10 senaryo koşusu, basit kural top-1 8, top-3 10/10. Kural testi betiği geçiyor (53 kural: delete 18, alone 18, örneksiz 17). `telemetry/raw/` boş; `c2_runs/` raw kopyaları planlama doğrulamasından sonra silinecek.
C2 doğrulandı (planlama, 2026-10-24): kalibrasyon kararlaştı (payment %50, email 1000x, cartFailure %50 zincirleme, intlShipping 10sec; INCIDENT_CATALOG, DECISIONS); belirti kontrolü vaka üretiminden itibaren işlem (span adı) düzeyinde de. `c2_runs/` süzülmemiş kopyaları ve `samples/` silindi, `productCatalogFailure_on_2` geçersiz işaretlendi.
Depolama kartı yapıldı (`task/depolama`, 2026-10-25): izleme sistemi kalıcı (isimli volume, Jaeger diske, 7 gün, Prometheus 2GB, OpenSearch ISM, volume toplamı ≤ 40 GB koruması), OpenSearch log kaybı düzeldi (`transform/backend_compat`), canlı = dosya doğrulandı; döndürme kalıcı 300 MB × 2 yedek. Yeniden oynatma (D3) iki C2 penceresinde geçti: Prometheus eski zamanı kabul ediyor, Proje 2'nin canlı tarafı snapshot'lardan doldurulabilir. Disk bütçesi HANDOFF'ta.
Vaka üretimi V1 yapıldı (`task/vaka-hatti`, 2026-10-26): `scenario_runner.py incidents` (collector yeniden başlatma, taban sağlık, enjeksiyon, anonim volume silme, snapshot kesimi, kontroller, etiket); snapshot = `model_view` (`~/cerebrum2/snapshots/inc-…/`), etiketler `incidents/`; eşikler C2'den (M = 10, taban 25,3 ms). Pilot gece 13/13 geçerli, sızıntı 0, hepsi belirtili, ~27,4 dk/vaka (40 vaka ≈ 18 saat). Açık risk: Jaeger belleği sınırın %84–91'i.
Vaka üretimi V2 yapıldı (`task/vaka-v2`, `task/vaka-v2c`, 2026-10-28): altı altyapı hatası koşucuda (uygula, geri al, doğrula; ağ hatası yardımcı imajı `aiops-netem:1`), kalibrasyon gecesi 16/16 geçerli, sızıntı 0. Katalogda 5 hata, 10 çift (seçilen parametre, belirtinin yeri, izlerde yayılım yolu, kategori); koşucuda eşi `INFRA_ANSWERS`. memoryLimit denendi, V3'e girmez. Jaeger 2500M + `GOMEMLIMIT=2000MiB` (uzun sınama Python servisi koşusunda), boş swap koruması 1 GB. Pilot set 31 vaka (`incidents/`, hepsi `set: pilot`).
Kendi Python servisi quote-gateway yapıldı (`task/quote-gateway`, 2026-10-29): shipping → quote-gateway → quote (Flask, OTel otomatik, flag'ler flagd'den; imaj yerelde `aiops-quote-gateway:1`, 128M, swap kapalı). Üç hata: misroute (cascading), gecikme 30 ms (cascading, silent), sızıntı 384 KB (silent) / 1024 KB (OOM ve yeniden başlama). quote'un iki çifti yeni topolojide belirtili (çağıran eşleşmesi URL'den). Jaeger'de swap şartı kalktı. Pilot set 38 vaka.
İmajlar GHCR'da (`task/ghcr-ci`, 2026-10-29): `ghcr.io/erenbezek/aiops-quote-gateway` ve `aiops-netem` CI'da derleniyor, main'de `sha-<commit>` etiketiyle gönderiliyor; koşucu ve compose digest'le sabit. Canlı kontrol geçti (girişsiz çekme, 23 konteyner, zincir, netem, taban sağlık 34,0 ms prizde).
Gece koşusu systemd biriminde (`task/systemd-unit`, 2026-10-29): `systemctl --user start aiops-incidents@<liste>`; `systemctl stop`'ta temizlenir, canlıda geçti (~65 sn, SIGKILL yok); kapanmada kesilir, sonraki koşu başlamaz (kalıntı denetimi).
V3 resmî set sürüyor (`task/vaka-v3`, kart HANDOFF 2026-10-29): 40 vaka (19 dev / 21 test), iki gece. V3a hazırlık bitti. 1. gece 20/20 geçerli (planlamada kontrol edildi). 2. gece (2a + 2b) 16/20: 2b'de taban sağlık üç kez düştü (product-catalog yavaşlaması, neden bilinmiyor), koşu durduruldu. Toplam 36 geçerli (dev 18, test 18), etiketler `incidents/`'ta.
2. gece planlamada kontrol edildi.
V3c taban ölçümü gündüz kaldı (36,6 ms; product-catalog yavaşlaması, kök bilinmiyor).
Sıradaki: makine yeniden başlatılır, tek ölçüm; geçerse `v3_retry`, kalırsa V3 36 vakayla kapanır.
