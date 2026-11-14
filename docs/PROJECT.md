# PROJECT

## Ne
Mikroservis ortamına (OpenTelemetry Demo + kendi Python servisim) bilerek hata enjekte edip,
kök nedeni bulan yöntemleri aynı vakalar üzerinde ölçen bir altyapı ve üzerinde iki proje:

- **Proje 1:** CPU'da çalışan küçük lokal model (`small_local_model`) + istatistiksel daraltma (hibrit),
  kanıt/yol doğrulaması ve "emin değilim" diyebilme (kalibrasyon).
- **Proje 2:** Araçlı ajan (tek ajan, sabit sorgu araçları; model kod çalıştırmaz). Ana model Gemini 3.5 Flash Lite (`large_api_model`); yerel qwen3.5-4b (`small_local_model`) ikinci model adayı (DECISIONS 2026-11-09).

Tüm yöntemler aynı vakalarda baseline'lara (kural, BARO) karşı ölçülür.
Proje 1'de `large_api_model` satırları iki modelle koşuldu (Groq gpt-oss-120b, Gemini 3.5 Flash Lite), ayarlar birebir aynı. Proje 2'de yalnız Gemini (Groq kotası ajana yetmiyor, para harcanmıyor; DECISIONS 2026-11-09).

## Neden
Logların dışarı çıkamadığı bir ortamda küçük lokal model, doğru desteklenirse
kök neden analizinde ne kadar iş görür?

## Bitti sayılması için
- [ ] Otomatik vaka üretimi: enjekte et → kaydet → temizle (gece boyu çalışabilir)
- [x] En az 30 vakalık snapshot seti; bir kısmı geliştirmede hiç görülmemiş test seti
  - V3 (2026-10-30): 36 geçerli vaka, dev 18 / test 18. Testte 5 birim geliştirmede hiç görülmedi (ayrılan). Düşen 4 giriş ve boşluklar DECISIONS 2026-10-30'da.
- [x] Sonuç tablosu: baseline'lar, `small_local_model` / `large_api_model` × ham log / daraltma
  - P1e (2026-11-05): `results/p1_table.md` / `.json`, `python -m aiops_rca.results`; kural, BARO, daraltma referansı, 4B / gpt-oss / Gemini × ham / özet / daraltma, 9B bilgi satırı.
- [x] Ölçütler: top-1/top-3, kanıt geçerliliği, kalibrasyon, süre, token
  - P1e: tablonun ayrıntı bölümlerinde top-1/3, kanıt, örtüşme, Brier, seçici doğruluk ve kapsama, süre, token.
- [ ] Canlı demo: hata enjekte et → kanıtlı olay raporu (+ bir sonraki adım önerisi)
- [x] CI yeşil: birim testler + sabit snapshot'larda baseline regresyonu + servis imajı (GHCR)
  - Servis imajı (GHCR) tamam (2026-10-29): iki imaj CI'da derlenip main'de gönderiliyor (`images.yml`), koşular digest'le sabit.
  - Baseline regresyonu tamam (2026-10-31): kural (`rule_expected.json`, P1a) ve BARO (`baro_expected.json`, P1b) beklenen çıktı testleri CI'da koşuyor (main push run 41178530691: 464 geçti, 3 atlandı; atlananlar demo klonu isteyen `test_replay_config`). Sınırlama: 4 kırpılmış pilot örneği; yalnız CPU ve bellek metrikleri (ağ sütunu yok), izler seyreltilmiş. Kodun aynı kaldığının kontrolü, tam vakadaki sonucun değil.
- [ ] Sızıntı kontrolü: snapshot'larda cevabı ele veren veri yok (flagd vb.), testle doğrulandı
- [x] Vaka çeşitliliği: set en az zincirleme hata, sessiz hata (log yok, sadece metrik) ve yanıltıcı gürültü içeriyor
  - V3 test: cascading 17, silent 8, partial 3, noisy 1. Dev: cascading 17, silent 10, partial 3, noisy 2.
- [ ] Tekrarlanabilirlik:
  - Not (P1e): seviye 1 P1 için tamam; CI tabloyu kayıtlardan yeniden üretip bayt aynı buluyor (`tests/test_results.py`). Seviye 2 proje sonunda.
  - Seviye 1 (her makinede ve CI'da): Sonuç tablosu, repodaki resmî koşu cevapları + etiketler + baseline çıktılarından tek komutla yeniden üretilir
  - Seviye 2 (deneyi baştan koşmak): Tam snapshot seti proje sonunda GitHub Releases'te sıkıştırılmış olarak yayınlandı
- [x] Sonuç tablosu geliştirme ve test setini yan yana gösteriyor
  - P1e: tablo 1. bölüm dev–test yan yana (Fisher, iki yönlü); 3. ve 4. bölüm dev ve test ayrıntısı, demo / kendi hatalarımız ayrımıyla.
- [ ] Hata analizi: başarısız vakalar 12'li hata sınıflandırmasıyla etiketlendi (arXiv 2602.09937)
  - Not (P1e): kısmen. Yalnız dev (29 satır) ve 12 tuzağın P1'e uyan 6'sı (T1–T6); Eren 10 satırı doğruladı (`results/p1_error_summary.md`). Test analizi ve 12'nin tamamı P2'de (DECISIONS 2026-11-04).
- [ ] DevOps kontrol listesi dolduruldu (aşağıda)
- [ ] Proje 2 (ajan): Proje 1 bittikten sonra
  - Ajan aynı vakalarda hem dosyadan hem canlı izleme sisteminden (Prometheus, Jaeger, OpenSearch) koşuldu, iki satır tabloda yan yana
  - Aynı araç çağrılarının dosya ve canlı çıktıları karşılaştırıldı, farklar açıklandı
    - Araç düzeyi tamam (P2a, 2026-11-12; `results/p2a_compare.md`): pilot 25 + dev 18 vakada çağrıların hepsi eşit; kalan tek fark Jaeger'in sıfır süreli span'e 1 ns eklemesi (DECISIONS 2026-11-11), `error="true"` çevirisi okuyucuda geri alınıyor (DECISIONS 2026-11-12). Ajan düzeyi P2c'de.

### DevOps kontrol listesi
Proje sonunda her satır için: gerçekten yaptım mı?

| Beceri | Projede nerede | Yapıldı |
|---|---|---|
| Dockerfile, imaj oluşturma | Kendi Python servisim | [x] quote-gateway ve netem: sabit taban (digest) ve sabit bağımlılıklar, root olmayan kullanıcı; CI'da derleme ve kontrol (`pip freeze` = requirements, `tc -V`), GHCR'da açık paket, koşular digest'le |
| OTel instrumentation | Kendi Python servisim | [ ] |
| Docker Compose, kaynak limitleri | OTel Demo yığını | [ ] |
| Telemetri hattı (collector) | Sızıntı süzmesi, dosyaya ve izleme sistemine çift çıkış | [ ] |
| Kalıcı depolama, saklama süresi | Jaeger diske, Prometheus/OpenSearch saklama | [ ] kısmen: isimli volume, Jaeger diske, 7 gün + boyut sınırları, canlı = dosya doğrulandı; saklamanın silmesi henüz gözlenmedi |
| PromQL, Jaeger ve log sorguları | Snapshot kaydedici, ajan araçları | [ ] kısmen (P2a, 2026-11-12): Jaeger API v3 araması (zaman dilimleme, derinlik sınırında bölme) ve tek iz, OpenSearch sorguları (sayfalama, servis süzgeci), Prometheus ham aralık sorguları; canlı = dosya doğrulandı (`results/p2a_compare.md`). PromQL işlevleri (rate, histogram_quantile) canlı demonun Grafana panosunda (DECISIONS 2026-11-09) |
| Linux ağ/kaynak hataları (tc netem, CPU/bellek, kill) | Hata enjeksiyonu | [x] tc netem (gecikme, kayıp; kendi yardımcı imajla), CPU sınırı, durdurma, dondurma; uygula, geri al, doğrula; bellek sınırı denendi, bu demoda belirti vermediği için çıktı (INCIDENT_CATALOG) |
| Otomasyon betikleri | Gece boyu vaka üretim hattı | [x] koşucu (`scenario_runner.py incidents`: korumalar, enjeksiyon, geri alma ve doğrulama, snapshot, etiket) ve systemd birim şablonu (`deploy/systemd/aiops-incidents@.service`): tek komutla başlar; `systemctl stop`'ta yarıdaki vaka temizlenir (SIGTERM → hata geri alınır, flag kapanır, demo kapanır); kapanmada ya da oturumdan çıkışta temizlik kesilir (kullanıcı yöneticisi 5 sn verir), sonraki koşu kalıntı denetiminde başlamaz; zamanlayıcı yok |
| Grafana dashboard | Canlı demo | [ ] |
| CI/CD (GitHub Actions, GHCR) | Testler, regresyon, imaj | [x] testler PR'da ve main'de (`.github/workflows/ci.yml`); imajlar PR'da derlenip kontrol ediliyor, main'de GHCR'a gönderiliyor (`.github/workflows/images.yml`, üçüncü taraf eylem yok); baseline regresyonu: kural ve BARO'nun beklenen çıktısı 4 kırpılmış pilot örneğinde (kodun aynı kaldığının kontrolü, tam vaka sonucu değil) |
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
V3 resmî set kapandı (`task/vaka-v3`, 2026-10-30): 36 geçerli vaka (dev 18, test 18), etiketler `incidents/`'ta. 1. gece 20/20, 2. gece 16/20; V3c'nin taban ölçümü iki kez kaldı, kalan 4 giriş düştü (DECISIONS). Açık risk: 30 Ekim sabahından beri product-catalog yavaş (kök bilinmiyor); canlı demodan önce çözülmeli.
V3 kapanışı birleşti (PR #28). product-catalog bellek sınaması sonuçsuz; müdahale sınaması canlı demo kartında.
Proje 1 P1a bitti (`task/p1-eval`, 2026-10-30): değerlendirme çatısı (`src/aiops_rca/`: erişim, şema, puanlama, koşu kaydı) ve kural baseline'ı; pilot + dev'de top-1 22/43, top-3 36/43 (`eval_responses/`). Ham log penceresi ~53 M token: "ham log" koşulu P1c'de yeniden tanımlanacak.
P1a birleşti (PR #29).
P1b bitti (`task/p1-baro`, PR #30, 2026-10-31): BARO, RCAEval 1.9.0'ın saf Python portu (5 dev vakasında bit düzeyinde eşit); pilot + dev'de top-1 11/43, top-3 27/43 (`eval_responses/`); CI'da 4 örnekte beklenen çıktı testi. Üç sınırlama notu P1e'de tabloyla (HANDOFF 2026-10-31).
P1c bitti (`task/p1-llm`, 2026-11-01): LLM katmanı (`llm_client.py`, beş model), girdi seviyeleri ham / özet / daraltma (`inputs.py`; 43 vakada veri ≤ 5000, tam mesaj ≤ 6000, en çok 5.384), daraltma (`narrowing.py`; dev'de kök ilk 5'te 18/18), takma ad üç seviyede (`alias.py`; gerçek ad 0, sızıntı 0; `quote-svc` tek pilot vakada kaldı, P1e notu), LLM yöntemi (`methods/llm.py`, `evaluate run --method llm`; boş ve bütçeyi aşan girdi sorulmaz). Üç onay alındı (kesme kuralı, öne alma, istem). Duman 30 çağrı, şemaya uygun 29/30 (`llm_cache/`). Dev'de model koşulmadı.
P1c birleşti (PR #31).
P1d bitti (`task/p1-dev-runs`, 2026-11-04): dev'de 36 resmî LLM turu (a1 gerçek ad 15, b takma ad 15, a2 API ikinci tur 6; `eval_responses/`), yerel tekrar 18/18 aynı. Resmî analiz (repo dışı betik, planlama bağımsız doğruladı; HANDOFF 2026-11-04): yerel model **qwen3.5-4b** (9 zor vakada top-3: 2B 6, 4B 9, 9B 9); takma ad etkisi görülmedi (gpt-oss ham belirsiz, gürültü 2). Daraltma top-3: Gemini 18, gpt-oss 17, 4B ve 9B 16 / 18. Groq `json_validate_failed` şema dışı sayılıyor (`eafc491`).
P1e bitti (`task/p1-test`, 2026-11-05): test setinde 15 koşu (kural, BARO, daraltma referansı, 4B / gpt-oss / Gemini / 9B × üç seviye; temiz klonda), sonuç tablosu `results/p1_table.md` (`python -m aiops_rca.results`, CI bayt aynı). Dev–test bütün satırlarda "ayırt edilemedi" (en küçük p 0,1774); 9B bilgi satırı 2 / 0 / 14, ayırt edilemedi. Dev hata analizi: 29 satır, 6 tuzak, Eren doğrulaması 9 / 1 (`results/p1_error_summary.md`). Sınırlamalar `results/p1_limitations.md`.
P1e birleşti (PR #33, main `b4878eb`).
Proje 2 çerçevesi (DECISIONS 2026-11-09): P2a sorgu araçları → P2b ajan döngüsü + pilot dumanı → P2c dev koşuları → P2d test koşusu ve analiz. Tek ajan + sabit sorgu araçları; model Gemini 3.5 Flash Lite (4B adayı P2b'de); canlı taraf vaka başına boş yeniden oynatma, dosyayla aynı tanım; çağrı bütçesi 6K. P2a kartı HANDOFF'ta, dal `task/p2a`. P2'den sonra canlı demo (product-catalog sınaması orada), sonra kapanış.
P2a bitti (`task/p2a`, 2026-11-12): sorgu katmanı (`query.py`, altı fonksiyon, ortak hesap), dosya ve canlı okuyucu (`store_file.py`, `store_live.py`), vaka başına boş yeniden oynatma (`storage_check.py replay-case`), LLM'siz karşılaştırma (`tools/query_compare.py`). Pilot 25 + dev 18 vakada çağrıların hepsi eşit; kalan tek fark Jaeger'in sıfır süreli span'e 1 ns eklemesi (DECISIONS 2026-11-11); Jaeger'in `error="true"` → hata çevirisi okuyucuda geri alınıyor (DECISIONS 2026-11-12). Sızıntı 0, OOM 0; Jaeger tepesi sınırın %96'sı (P2c'den önce karar). Rapor `results/p2a_compare.md`. Sıradaki: PR birleşince P2b kartı (planlama).
P2b bitti (`task/p2b`, 2026-11-13): ajan araçları (`agent_tools.py`), ajan döngüsü (`methods/agent.py`; katı JSON eylem şeması, en çok 8 araç + P1 cevap turu, 6K bütçe ve kırpma; istem Eren onaylı, sha256 testte), dosya modu `evaluate run --method agent`, canlı mod `tools/agent_live.py`. Pilot dumanı: Gemini 25 vakada geçerli cevap 24/25, 4B 20/25 (4B kuralı geçti, sınırda; 4,33 dk / vaka), canlı 3/3; bütçe bitişi 0. Pilot isabeti düşük (yalnız bilgi; `results/p2b_pilot.md`). Sıradaki: PR birleşince P2c kartı (planlama).
P2c-0 bitti (`task/p2c`, 2026-11-14): tek pilot tasarım turu; onaylı iki değişiklik (zaman uçları isteğe bağlı, `metric_series`'te alarma hizalı tam kovalar ve görev cümlesi; servissiz `metric_series`, 300 sn), pilot bir kez yeniden koşuldu (Gemini 25, 4B 25, canlı 3): geçerli son cevap 25 / 25, 22 / 25, 3 / 3; 4B kuralı geçti, bütçe kuralı tetiklenmedi (`results/p2c0_pilot.md`). Tasarım dondu (DECISIONS 2026-11-14; `src/` `c988c55`, istem `5e259201…`). PR #41 birleşti (main `01ad031`).
P2c dev koşuları kartı yazıldı (`task/p2c-dev`, HANDOFF 2026-11-14). Koşudan önceki beş karar DECISIONS 2026-11-14'te: Gemini taşıma hatasında 3 yeniden deneme; oynatma Jaeger'i 2500M + `GOMEMLIMIT=2000MiB` (oynatma tepesi 1.970 MiB kesin sınır 2000M'nin %98,5'iydi; önceki "`GOMEMLIMIT`'in" ifadesi yanlıştı); dosya ↔ canlı okuma kuralı (üç katman); ajan ↔ P1 okuma kuralı (iki hücre, eşleştirilmiş kesin işaret testi); 12 tuzağın uyarlanmış soruları. Sıradaki: uygulama kartın 1. maddesi (öneri, kod yok).
