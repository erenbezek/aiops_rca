# INCIDENT CATALOG

Hangi hatalar enjekte edilir, doğru cevap ne sayılır, belirti nerede beklenir.
Kaynak: OTel Demo 3.1.0 kodu (bkz. `OTEL_DEMO.md`). Belirtiler ve yollar koddan çıkarılan **beklentidir**; yeni makinede kalibrasyonla doğrulanacak.

## Kurallar

- **Kök neden** = hatanın enjekte edildiği, kodu veya ayarı bozulan servis. Belirtinin çıktığı servis değil.
- **load-generator telemetrisi snapshot'a girmez.** Gerçek ortamda kullanıcıların telemetrisi elde olmaz; ayrıca senaryoyu ele veriyor ve minimal modda sürekli agent bağlantı hatası üretiyor.
- **`loadGeneratorFloodHomepage` tek başına vaka değildir**, `noise_layer`'dır: başka bir hatayla aynı anda açılır, doğru cevap o diğer hatadır.
- **Test setinde ağırlık kendi altyapı hatalarımızda.** Büyük modeller OTel Demo flag senaryolarını belgelerden tanıyabilir; kendi hatalarımız ezberlenemez.

## Doğru cevap kaydı (her incident için)

| Alan | Açıklama |
|---|---|
| `incident_id` | Vaka kimliği |
| senaryo, varyant | Ör. `paymentFailure`, `50%`; altyapı hatasında hata türü ve parametresi |
| başlangıç, bitiş | Enjeksiyon ve temizleme zamanı |
| kök neden servisi | Yukarıdaki kurala göre |
| hata tipi | `error` / `latency` / `resource` / `unavailable` / `misconfig` |
| yayılım yolu | Kök nedenden belirtilere, ör. `payment → checkout → frontend` (Proje 1 yol doğrulaması bunu kontrol eder) |
| kategori | `cascading` / `silent` / `noisy` / `partial` (birden fazla olabilir) |
| set | `dev` / `test` |

Alan adları ve dosya biçimi uygulamada önerilir, Eren onaylar.

## Flag senaryoları (14)

| Senaryo | Kök neden | Hata tipi | Ne oluyor | Beklenen yayılım yolu | Beklenen belirti | Kategori |
|---|---|---|---|---|---|---|
| `adFailure` | ad | error | İsteklerin ~%10'u `UNAVAILABLE` | ad → frontend | ad hata span'i ve logu, frontend'de reklam hatası | cascading |
| `adHighCpu` | ad | resource | CPU yükü üreten iş parçacıkları | ad → frontend | ad CPU metriği, gecikme; log yok | silent |
| `adManualGc` | ad | resource | Her istekte tam GC | ad → frontend | JVM GC metrikleri, gecikme sıçramaları | cascading, silent |
| `cartFailure` | cart | misconfig | Sepet boşaltma var olmayan sunucuya (`badhost:1234`) (varyant %50) | cart → checkout → frontend | cart EmptyCart hatası ve uzun bekleme (p99 4 ms → 380 sn; %10'da 75 sn); checkout PlaceOrder gecikir (p95 37 ms → 450 sn), %50'de 31 siparişin 8'i hata; frontend-proxy'de 15 sn zaman aşımı. Cart'ın toplu sinyallerinde görünmez (EmptyCart, cart isteklerinin ~%3'ü) | cascading, partial |
| `emailMemoryLeak` | email | resource | Bellek büyür, 100 MB limitte OOM ve yeniden başlama (varyant 1000x) | email → checkout | email bellek metriği, yeniden başlama; checkout'ta sadece uyarı logu. C2 1000x: email belleği flag açılınca ~2 dk'da 53 → 89 MB, sonra dalgalanır; 10 dk'da OOM ya da yeniden başlama görülmedi. 100x'te artış (~1,8 MB/dk) normal dönem büyümesinden (~0,8 MB/dk) ayrılmıyor. | cascading, silent |
| `paymentFailure` | payment | error | İsteklerin %n'i `Invalid token` (varyant %50) | payment → checkout → frontend | Hata zinciri; hatalar `loyalty_level=gold` ile birlikte (sahte korelasyon). C2 %50: 23 ödemenin 9'u hata; %10: 26'da 1 (10 dk'da 16–43 sipariş). | cascading, noisy |
| `paymentUnreachable` | checkout | misconfig | checkout payment yerine `badAddress:50051`'e bağlanır | checkout → frontend | checkout bağlantı hatası; payment sağlıklı ama trafiği kesilir | cascading |
| `productCatalogFailure` | product-catalog | error | Tek üründe (`OLJCESPC7Z`) hata | product-catalog → frontend, checkout, recommendation | O ürüne ait isteklerde hata zinciri | cascading, partial |
| `productCatalogLockContention` | product-catalog | latency | Kendi işlemi `catalog.products` tablosunu 30 sn kilitler (10 sn'de bir kontrol) | product-catalog → frontend, recommendation, checkout | DB bekleme, product-catalog ve frontend gecikmesi. Zincir dışında frontend-proxy (0 → 81) ve frontend-web (0 → 6) hata span'i var (`inc-0f31ed0e`) | cascading, silent |
| `recommendationCacheFailure` | recommendation | resource | Önbellek sınırsız büyür | recommendation → frontend | recommendation bellek ve gecikme artışı; recommendation'da hata yok, frontend'de hata span'i (0 → 86) ve hata logu (0 → 26), zincir dışında frontend-proxy (0 → 13) (`inc-78df5642`) | cascading |
| `intlShippingSlowdown` | shipping | latency | Yurt dışı gönderide 5/10 sn gecikme (varyant 10sec) | shipping → checkout → frontend | Siparişlerin ~%11'inde gecikme (Gecikme sadece ship-order'da, 10 sn. Servis p95'i yurt dışı sipariş sayısına bağlı: zor denemede ~3 sipariş, görünmedi; C2'de 26'nın 8'i, göründü. ship-order ve checkout PlaceOrder p95/p99'da görünür; zor deneme için hesap, yeniden ölçülmedi.) | cascading, silent, partial |
| `quoteGatewayMisroute` | quote-gateway | misconfig | Kendi servisimiz; fiyat isteğini quote yerine var olmayan bir adrese (`quote-svc:8090`) iletir | quote-gateway → shipping → frontend, checkout | quote-gateway POST /getquote hata oranı 0 → 1 (502) ve hata logu; çağıran shipping→quote-gateway hata oranı 0 → 1; quote'un trafiği kesilir (98 → 0 istek) (`inc-91bf76d4`) | cascading |
| `quoteGatewaySlowdown` | quote-gateway | latency | Kendi servisimiz; iletmeden önce bekler (varyant ms, kalibrasyonda seçilir) | quote-gateway → shipping → frontend, checkout | Seçilen 30 ms: quote-gateway POST /getquote p95 7,2 → 37,5 ms; çağıran shipping→quote-gateway p95 10,1 → 40,2 ms (güç 1,5); hata span'i ve hata logu 0 → 0 (`inc-2dd806a2`) | cascading, silent |
| `quoteGatewayMemoryLeak` | quote-gateway | resource | Kendi servisimiz; her istekte bir blok saklar, hiç bırakmaz (varyant istek başına KB). Bellek sınırı 128M, swap kapalı: 1024 KB'ta ~8. dk'da OOM ve yeniden başlama; 384 KB 10 dk'da sınıra varmaz (tepe 84 MiB) | quote-gateway → shipping → frontend, checkout | 384 KB (seçilen): quote-gateway bellek 43 → 84 MiB (güç 1,87), çağıranda belirti yok (0,14), hata 0 → 0. 1024 KB: OOM ve yeniden başlama (bellek güç 4,85), shipping ve frontend'de hata span'i, çağıranda sınırda (0,81). Kategori varyant başına (DECISIONS 2026-10-29) | `384kb`: silent (`inc-ff3a6614`); `1024kb`: — (`inc-660f7c44`) |

Kategoriler (V3a, DECISIONS 2026-10-29 "Flag kategorileri"; tanımlar aşağıda "Kendi altyapı hatalarımız" altında):
`cascading` ve `silent` pilot snapshot'larından ölçüldü: çağıran kontrolü `symptomatic` ise `cascading`; kök neden ve
katalog yolundaki servislerde (frontend-proxy hariç) enjeksiyon döneminde ERROR span ve severity ≥ 17 log artmıyorsa
`silent`. `partial` ve `noisy` mekanizmadan. `noise_layer`'lı vaka = senaryonun kategorileri + `noisy` (koşucu ekler).
Kanıt: `~/cerebrum2/analysis/v3a_categories.py` ve `.out` (repo dışı; sha256 ve özet HANDOFF 2026-10-29 "V3a 4").
quote-gateway satırları DECISIONS 2026-10-28/29'dan, değişmedi.

Sızıntı notu: `productCatalogFailure` hata mesajı ve `productCatalogLockContention` logu flag'i ele veriyor; silinmez, gerçekçi bir mesajla yeniden yazılır (belirti korunur). Ayrıntı `OTEL_DEMO.md`.

Etiket notu (quote-gateway sızıntısı): `inc-aec7e4ea` (1024 KB, kalibrasyon gecesi) swap açık düzende kaydedildi: bellek 128 MiB'te kaldı, OOM ve yeniden başlama yok. Dosyaya dokunulmadı. Swap kapalı düzende 1024 KB örneği `inc-660f7c44` (enjeksiyonun ~9,5. dk'sında OOM ve yeniden başlama; HANDOFF 2026-10-29).

## Çıkarılanlar

| Senaryo | Neden |
|---|---|
| `imageSlowLoad` | Gerçekçi değil (istemci proxy'ye kendini geciktirmesini söylüyor); sadece tarayıcı kullanıcılarında (1,5 GB); tek iz Envoy `DI` bayrağı, o da sızıntı olarak siliniyor |
| `loadGeneratorFloodHomepage` | Tek başına vaka değil; `noise_layer` olarak kullanılır |
| `kafkaQueueProblems`, `failedReadinessProbe`, `aiRunawayAgent`, `aiSlowResponse`, `emitRawPii` | Minimal modda yok / K8s'e özgü / hata değil (bkz. `OTEL_DEMO.md`) |

## Gürültü katmanı (`noise_layer`)

| Gürültü | Nasıl |
|---|---|
| Trafik seli | `loadGeneratorFloodHomepage` asıl hatayla aynı anda açılır |
| Sahte korelasyon | `paymentFailure` zaten içeriyor (`loyalty_level=gold`) |

Bitti ölçütündeki "yanıltıcı gürültü" şartı için gerekirse kendi servisimizden ilgisiz hata logları eklenir; kendi servis tasarlanınca karar verilir.

## Kendi altyapı hatalarımız (10)

V2 kalibrasyonu (V2b gecesi 2026-10-26, V2c 2026-10-27); quote'un iki çifti quote-gateway eklendikten sonra yeni topolojide (kalibrasyon gecesi 2026-10-28, çağıran eşleşmesi düzeltilip snapshot'tan yeniden hesaplandı). Her çift için belirtili çıkan en hafif aday seçildi; destek
vakası o adayın etiketi (`incidents/`). Koşucudaki eşi `INFRA_ANSWERS` (yol ve kategoriler), `INFRA_FAULTS` (hata
tipi), `PARAM_RE` (parametre biçimi); `tests/test_catalog.py` aynı olduklarını ve her satırın geçerli, belirtili bir
etiketle desteklendiğini sınar.

| Senaryo | Kök neden | Parametre | Hata tipi | Yöntem | Belirti nerede (karar) | İzlerde yayılım yolu | Kategori | Destek vakası |
|---|---|---|---|---|---|---|---|---|
| `networkDelay` | cart | `50ms` | latency | `tc netem delay` | Hedef + çağıran; karar çağıran: frontend AddItem p99 5 → 210 ms | cart → frontend, checkout | cascading, silent | `inc-2e5706ab` |
| `networkDelay` | quote | `50ms` | latency | `tc netem delay` | Hedef + çağıran; karar çağıran: quote-gateway→quote p99 5 → 99 ms (hedefte belirti yok) | quote → quote-gateway → shipping → frontend, checkout | cascading, silent | `inc-1811ae30` |
| `packetLoss` | shipping | `10%` | error | `tc netem loss` | Hedef + çağıran; karar çağıran: frontend→shipping p99 10 → 2.292 ms | shipping → frontend, checkout | cascading, silent | `inc-91c1ad44` |
| `packetLoss` | currency | `10%` | error | `tc netem loss` | Hedef + çağıran; karar çağıran: checkout Convert p99 3 → 419 ms (hedefte belirti yok) | currency → frontend, checkout | cascading, silent | `inc-d1709db7` |
| `cpuThrottle` | product-catalog | `0.09` | resource | `docker update --cpus` | Hedef: GetProduct p99 22 → 1.200 ms | product-catalog → frontend, recommendation, checkout | cascading, silent | `inc-3967c278` |
| `cpuThrottle` | recommendation | `0.03` | resource | `docker update --cpus` | Hedef: servis p99 (güç 840) | recommendation → frontend | cascading | `inc-7e70c5c4` |
| `containerPause` | cart | `on` | unavailable | `docker pause` | Çağıran: frontend GetCart p99 6 ms → 594 sn | cart → frontend, checkout | cascading | `inc-2a87f603` |
| `containerPause` | quote | `on` | unavailable | `docker pause` | Çağıran: quote-gateway→quote p95 4 → 10.017 ms (10 sn zaman aşımı) | quote → quote-gateway → shipping → frontend, checkout | cascading | `inc-58493603` |
| `containerStop` | recommendation | `on` | unavailable | `docker stop` | Çağıran: frontend ListRecommendations p99 13 → 32.092 ms | recommendation → frontend | cascading | `inc-01a609bb` |
| `containerStop` | currency | `on` | unavailable | `docker stop` | Çağıran: frontend GetSupportedCurrencies p99 7 → 71.101 ms | currency → frontend, checkout | cascading | `inc-569a664d` |

- **Belirti nerede:** durdurma ve dondurmada hedefin kendi span'leri kesilir, belirti ve olay çağıranlarda ölçülür
  (DECISIONS 2026-10-26). Ağ hatalarında hedef ve çağıranlar ölçülür, güçlü olan karar verir; olay hedefin kendi
  isteğiyle (DECISIONS 2026-10-27). quote ve currency kimseyi çağırmaz: netem yalnız cevaplarını geciktirir, gecikme
  hedefin kendi sunucu span'ine girmez; ayırt edici iz istemci span'i uzun, sunucu span'i kısa.
- **Yayılım yolu:** destek vakasının normal döneminde hedefe gelen sunucu span'lerinin üst span'i hangi serviste ise o
  çağırandır (frontend-proxy hariç, frontend'de durulur). Tek çağıranı olan halkada bir üst seviye de yazılır, ilk dallanmaya kadar (quote →
  quote-gateway → shipping → frontend, checkout; Eren 2026-10-29). quote'un V2b destek vakaları (`inc-d60dcc58`,
  `inc-e23c74cb`) eski topolojide (quote → shipping → frontend, checkout) kalır, değiştirilmedi.
- **Kategoriler (ölçülebilir tanımlar, Eren 2026-10-28; flag tablosunda da aynı tanımlarla
  uygulandı, V3a 2026-10-29):**
  - `cascading`: belirti kök nedenin çağıranlarında ölçülü olarak görünür (çağıran kontrolünde belirtili).
  - `silent`: enjeksiyon döneminde kök neden ve çağıran zincirinde hata span'i ve hata logu (severity ≥ ERROR) artmaz;
    belirti yalnız gecikme ya da kaynak. cpuThrottle recommendation bu yüzden `silent` değil: recommendation 12 hata
    logu yazdı (telemetriyi collector'a gönderemedi, `DEADLINE_EXCEEDED`).
  - `noisy` ve `partial` bu tabloda kullanılmadı (kanıt yok).
- Araçlar ve iz kuralı DECISIONS 2026-10-26'da: `tc netem` kendi yardımcı imajımızla (`ghcr.io/erenbezek/aiops-netem`,
  digest'le sabit; alpine + iproute2), diğerleri araçsız. Mekanizmanın izi sızıntı, hedefteki fiziksel etki belirti.

### Denendi, V3'e girmez: `memoryLimit` (`docker update --memory --memory-swap`, resource)

DECISIONS 2026-10-26 ("Bellek hatası") ve 2026-10-28 ("memoryLimit V2'den çıkar"). Kod ve testleri koşucuda kalır.
Bu demoda iki uç var, arası yok: sınır sürecin kendi belleğinin üstündeyse yalnız dosya önbelleği sıkışır, belirti
zayıf; altındaysa (ya da açılış tepesinin altındaysa) açılışta OOM döngüsü, hata durdurmanın kopyası olur.

| Servis | Taban (ilk 60 sn tepe) | Isınmış kullanım | Sonuç |
|---|---|---|---|
| cart (kuru deneme, anon × 0,8) | — | anon 20,1 MiB | Sınır 16,9 MB: 12 yeniden başlama, kendi span'i 0, olay yok |
| ad | 220,7 MiB | 210,2 MiB (5. dk) | 0,9× ve 0,75× tabanın altında |
| quote | 24,0 MiB | 18,6 MiB (5. dk) | 0,9× ve 0,75× tabanın altında |
| cart | 47,6 MiB | 52,4 MiB (25. dk) | 0,9× tabanın altında (pay 0,991) |
| email | 63,9 MiB | 58,5 MiB | 0,9× tabanın altında |
| recommendation | 53,5 MiB | 47,8 MiB | 0,9× tabanın altında |
| payment | 91,4 MiB | 60,4 MiB | 0,9× tabanın altında |
| frontend | 103,8 MiB | 120,6 MiB | Uydu (pay 1,046); 0,9× koşuldu (`inc-d8f67a48`): enjeksiyonda kullanım 133,8 MiB, sınır 120,4 MiB, OOM 0, belirti sınırda (`POST /api/checkout` p99 82,7 → 122,3 ms, güç 0,958 < 1,2) |

## Yeni makinede kalibrasyon

Her senaryo için: seçilen varyantla belirti 5-10 dakikalık pencerede görünüyor mu, beklenen yayılım yolu gerçekten görünüyor mu. Varyantlar (yüzde, çarpan) bu ölçümle seçilir ve buraya yazılır.
Geçme ölçütü: kök neden servisinde en az bir sinyalde (hata oranı, gecikme, CPU/bellek) normal döneme göre görünür sapma.

## V3 resmî set (kapandı 2026-10-30)

36 geçerli vaka: dev 18, test 18. Etiketler `incidents/`'ta (`set: dev` / `set: test`), snapshot'lar
`~/cerebrum2/snapshots/`. Kart HANDOFF 2026-10-29, kapanış DECISIONS 2026-10-30 ("V3 kapandı"). Test vakaları için
burada yalnız bileşim ve otomatik kontrol sayıları var; sinyal adı, değer ve güç yazılmaz.

| Set | Vaka | Demo flag'i | Altyapı | quote-gateway | cascading | silent | partial | noisy |
|---|---|---|---|---|---|---|---|---|
| dev | 18 | 11 | 5 | 2 | 17 | 10 | 3 | 2 |
| test | 18 | 6 | 10 | 2 | 17 | 8 | 3 | 1 |

Bir vaka birden çok kategoride olabilir. Flood'lu (`noise_layer`) vaka, senaryonun kategorileri + `noisy`.

- **Dev:**
  - Demo: adFailure, adHighCpu, adManualGc, cartFailure 50%, emailMemoryLeak 1000x, intlShippingSlowdown 10sec,
    paymentFailure 50%, paymentUnreachable, productCatalogFailure, productCatalogLockContention,
    recommendationCacheFailure.
  - Altyapı: networkDelay cart 50ms, packetLoss shipping 10%, cpuThrottle product-catalog 0.09, containerPause cart,
    containerStop recommendation.
  - quote-gateway: quoteGatewaySlowdown 30ms, quoteGatewaySlowdown 30ms + flood.
- **Test:**
  - Demo: adHighCpu, cartFailure 50%, intlShippingSlowdown 10sec, paymentUnreachable, productCatalogFailure,
    paymentFailure 50% + flood.
  - Altyapı: dev'deki 5 çift; ayrıca networkDelay quote 50ms, packetLoss currency 10%, cpuThrottle recommendation 0.03,
    containerPause quote, containerStop currency.
  - quote-gateway: quoteGatewayMisroute, quoteGatewaySlowdown 30ms.
- Yalnız testte olan 6 birimden (`HELDOUT_UNITS`) 5'i sette. quoteGatewayMemoryLeak 384kb düştü.
- Otomatik kontroller (36 vaka):
  - `verdict` hepsinde `symptomatic`. Belirtisiz, sınırda ya da işaretli vaka 0.
  - `deciding.level`: dev service 9, operation 5, caller 4; test caller 8, service 6, operation 4.
  - Sızıntı 0. Jaeger OOM, yeniden başlama, gönderim hatası ve reddedilen her vakada 0.
- Koşular:
  - 1. gece (`v3_night1`): 20/20. Bir taban sağlık yeniden denemesi oldu (dosya döndürme yarışı).
  - 2. gece: `v3_night2a` 15/15, `v3_night2b` 1/5. 2b'de taban sağlık üç kez düştü, koşu durduruldu.
  - V3c (`v3_retry`) koşulmadı: iki taban ölçümü kaldı (frontend p95 36,6 ms ve yeniden başlatma sonrası 392,2 ms;
    sınır 30).
- Düşen 4 giriş (`v3_retry.json`, koşulmamış olarak repoda):
  - quoteGatewayMisroute (dev) ve recommendationCacheFailure (test): 2. gecede taban sağlıkta geçersiz.
  - flood + productCatalogLockContention (test) ve quoteGatewayMemoryLeak 384kb (test): hiç koşulmadı.
- Bilinen boşluklar:
  - Testte sızıntı vakası yok.
  - Testte noisy yalnız 1 vaka.
  - Dev'de misroute yok.
  - Test 18 vaka; oran ölçümünde güç ~±23 puan (21 vakada ±21 olurdu).
- Ortam riski (DECISIONS 2026-10-30 "Ortam sorunu açık risk"):
  - 2026-10-30 sabahından beri canlı demoda product-catalog yavaş (normal p95 13–17 ms → 30–354 ms).
  - Set bundan önce üretildi. Proje 1 snapshot'larla çalıştığı için etkilenmez.
  - Canlı demo kullanılmadan (Proje 2'nin canlı tarafı) önce çözülmeli.
