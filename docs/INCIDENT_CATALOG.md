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

## Flag senaryoları (11)

| Senaryo | Kök neden | Hata tipi | Ne oluyor | Beklenen yayılım yolu | Beklenen belirti | Kategori |
|---|---|---|---|---|---|---|
| `adFailure` | ad | error | İsteklerin ~%10'u `UNAVAILABLE` | ad → frontend | ad hata span'i ve logu, frontend'de reklam hatası | — |
| `adHighCpu` | ad | resource | CPU yükü üreten iş parçacıkları | ad → frontend | ad CPU metriği, gecikme; log yok | silent |
| `adManualGc` | ad | resource | Her istekte tam GC | ad → frontend | JVM GC metrikleri, gecikme sıçramaları | silent |
| `cartFailure` | cart | misconfig | Sepet boşaltma var olmayan sunucuya (`badhost:1234`) | cart → checkout | cart hata span'i; checkout hatayı yok sayar, kullanıcıya yansımaz | silent, partial |
| `emailMemoryLeak` | email | resource | Bellek büyür, 100 MB limitte OOM ve yeniden başlama | email → checkout | email bellek metriği, yeniden başlama; checkout'ta sadece uyarı logu | silent |
| `paymentFailure` | payment | error | İsteklerin %n'i `Invalid token` | payment → checkout → frontend | Hata zinciri; hatalar `loyalty_level=gold` ile birlikte (sahte korelasyon) | cascading, noisy |
| `paymentUnreachable` | checkout | misconfig | checkout payment yerine `badAddress:50051`'e bağlanır | checkout → frontend | checkout bağlantı hatası; payment sağlıklı ama trafiği kesilir | cascading |
| `productCatalogFailure` | product-catalog | error | Tek üründe (`OLJCESPC7Z`) hata | product-catalog → frontend, checkout, recommendation | O ürüne ait isteklerde hata zinciri | cascading, partial |
| `productCatalogLockContention` | product-catalog | latency | Kendi işlemi `catalog.products` tablosunu 30 sn kilitler (10 sn'de bir kontrol) | product-catalog → frontend, recommendation, checkout | DB bekleme, product-catalog ve frontend gecikmesi | cascading |
| `recommendationCacheFailure` | recommendation | resource | Önbellek sınırsız büyür | recommendation → frontend | recommendation bellek ve gecikme artışı | silent |
| `intlShippingSlowdown` | shipping | latency | Yurt dışı gönderide 5/10 sn gecikme | shipping → checkout → frontend | Siparişlerin ~%11'inde gecikme | partial |

Sızıntı notu: `productCatalogFailure` hata mesajı ve `productCatalogLockContention` logu flag'i ele veriyor; silinmez, gerçekçi bir mesajla yeniden yazılır (belirti korunur). Ayrıntı `OTEL_DEMO.md`.

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

## Kendi altyapı hatalarımız (taslak)

| Hata | Hata tipi | Kök neden |
|---|---|---|
| Konteyner öldürme / durdurma | unavailable | Hedef servis |
| CPU baskısı | resource | Hedef servis |
| Bellek baskısı | resource | Hedef servis |
| Ağ gecikmesi / paket kaybı (`tc netem`) | latency / error | Hedef servis |

Açık: hedef servisler, parametreler ve araçlar (`tc` için `NET_ADMIN` yetkisi, CPU/bellek baskısı için araç). Yeni araç gerektirdiği için ilgili kartta Eren'e sorulur.

## Yeni makinede kalibrasyon

Her senaryo için: seçilen varyantla belirti 5-10 dakikalık pencerede görünüyor mu, beklenen yayılım yolu gerçekten görünüyor mu. Varyantlar (yüzde, çarpan) bu ölçümle seçilir ve buraya yazılır.
Geçme ölçütü: kök neden servisinde en az bir sinyalde (hata oranı, gecikme, CPU/bellek) normal döneme göre görünür sapma.
