# OTEL DEMO

OpenTelemetry Demo hakkında keşif notları. Kaynak: `open-telemetry/opentelemetry-demo` etiket **3.1.0** (2026-09-18, commit `dedc0178918e260823323b8d95005a8cb924b007`), dosyalar okunarak çıkarıldı (2026-10-14), çalıştırılmadı.
Sürüm değişirse bu dosya yeniden kontrol edilir.

## Çalıştırma modları

Demo 3.x'te tek compose yerine katmanlı dosyalar var (`Makefile` hedefleri):

| Mod | Dosyalar |
|---|---|
| minimal | `compose.yaml` + `compose.observability.yaml` + `compose.extras.yaml` |
| tam | + `compose.full.yaml` (Kafka, accounting, fraud-detection) |
| minimal, gözlem yığını yok | `compose.yaml` + `compose.extras.yaml` |
| agentic | + `compose.agent.yaml` (AI senaryoları) |

- Ortam değişkenleri: `--env-file .env --env-file .env.override`.
- `compose.extras.yaml` ve `src/otel-collector/otelcol-config-extras.yml` boş bırakılmış, hep en son yükleniyor: değişikliklerimizin giriş noktası. Upstream dosyalarına dokunmadan override edilebilir.
- Collector config dosyaları ortam değişkeniyle bağlanıyor (`OTEL_COLLECTOR_CONFIG_EXTRAS` vb.); kendi repomuzdaki bir dosyayı gösterebilir.
- Collector config'leri birleştirirken **listeleri değiştirir, eklemez**: pipeline'a processor/exporter eklerken upstream'dekiler tekrar yazılmalı. Bu yüzden sürüm sabitlenmeli; upstream listesi değişirse bizim override sessizce eskir.

## Bellek (konteyner limitleri, gerçek kullanım değil)

| Grup | Toplam limit | En büyükler |
|---|---|---|
| `compose.yaml` (uygulama + flagd + collector) | ~4,2 GB | load-generator 1500M, recommendation 500M, otel-collector 400M, ad 300M |
| `compose.observability.yaml` | ~2,7 GB | jaeger 1200M, opensearch 1G, prometheus 200M, grafana 175M |
| `compose.full.yaml` | ~1,1 GB | kafka 620M |

- Minimal mod limit toplamı ~6,8 GB. Gerçek kullanım yeni makinede `docker stats` ile ölçülecek.
- load-generator'ın büyüklüğü tarayıcı (Playwright) kullanıcılarından: `LOCUST_BROWSER_USER_WEIGHT=0` ile düşürülebilir. Varsayılan `LOCUST_USERS=5`.

## Hata senaryoları (flag'ler)

Minimal modda kullanılabilir (13):

| Flag | Değerler | Nerede etki ediyor |
|---|---|---|
| `adFailure` | on/off | ad: isteklerin ~%10'u `UNAVAILABLE` |
| `adHighCpu` | on/off | ad: CPU yükü |
| `adManualGc` | on/off | ad: tam GC |
| `cartFailure` | %10…%100 | cart: bozuk cart store'a yazar |
| `emailMemoryLeak` | 1x…10000x | email: bellek sızıntısı |
| `imageSlowLoad` | 5sec/10sec | frontend → Envoy fault filtresi ile gecikme |
| `intlShippingSlowdown` | 5sec/10sec | shipping: uluslararası gönderide gecikme |
| `paymentFailure` | %10…%100 | payment: hata fırlatır |
| `paymentUnreachable` | on/off | **checkout**: payment yerine `badAddress:50051`'e bağlanır; payment sağlıklı kalır |
| `productCatalogFailure` | on/off | product-catalog: belirli bir üründe hata (targeting kuralıyla) |
| `productCatalogLockContention` | on/off | product-catalog: veritabanı kilit çekişmesi |
| `recommendationCacheFailure` | on/off | recommendation: büyüyen önbellek |
| `loadGeneratorFloodHomepage` | on/off | load-generator: ana sayfaya istek seli |

Kullanılamayanlar: `kafkaQueueProblems` (tam mod), `failedReadinessProbe` (sadece K8s), `aiRunawayAgent` / `aiSlowResponse` (agentic mod), `emitRawPii` (hata değil).

Etiketleme notu: `paymentUnreachable`, `cartFailure`, `imageSlowLoad` gibi senaryolarda "kök neden servisi" tek anlamlı değil; vaka kataloğunda senaryo başına karar verilecek.

## Flag'i açıp kapatma

- flagd-ui HTTP API: `GET /feature/api/read`, `POST /feature/api/write` (frontend-proxy üzerinden, `localhost:8080`). Upstream testleri böyle yapıyor.
- `productCatalogFailure` farklı: `defaultVariant` değil, targeting kuralının dalı değişiyor.
- Yazma işlemi flagd'nin bağlı klasöründeki `src/flagd/demo.flagd.json` dosyasını değiştirir (upstream çalışma kopyası).

## Sızıntı yolları

Cevabı (hangi flag açık) ele veren veriler. Sadece flagd servisini çıkarmak yetmez.

| Kaynak | Ne görünüyor |
|---|---|
| flagd, flagd-ui servis telemetrisi | Flag değerlendirmeleri, yazma işlemleri |
| checkout, product-catalog, recommendation, load-generator, agent span'leri | OpenFeature `TracingHook`: `feature_flag.evaluation` olayı, flag adı ve varyant |
| cart metrikleri | OpenFeature `MetricsHook`: `feature_flag.*` metrikleri, flag adı ve varyant |
| recommendation span özniteliği | `demo.feature_flag.recommendation_cache` |
| ad logu | `Feature Flag adManualGc enabled, performing a manual gc now` |
| shipping logu | `shipping.feature_flag.evaluated`, `... due to intlShippingSlowdown feature flag` |
| frontend-proxy (Envoy) erişim logu ve span'leri | `POST /feature/api/write` isteği; `%RESPONSE_FLAGS%` alanında `DI` (gecikme enjekte edildi) |
| Tarayıcıdaki frontend'in flag sorguları | Envoy üzerinden `/flagservice/` yolu (`flagd.evaluation.v1...`), upstream cluster `flagservice`; load-generator OFREP kullanıyor |
| flagd, flagd-ui, load-generator konteyner metrikleri | `docker_stats` ve `span_metrics` bu servisler için de metrik üretir (`container.name`, `service.name`) |
| product-catalog span durumu ve olayı | `Error: Product Catalog Fail Feature Flag Enabled` |
| product-catalog logu | `lock contention scenario active: holding ACCESS EXCLUSIVE lock on catalog.products` |
| load-generator span ve logu | `user_flood_home` span'i, `demo.request.flood.count`, `User flooding homepage N times` |

Ele vermeyenler (gerçekçi belirti, korunur): payment hata mesajı (`Payment request failed. Invalid token...`), servislerin flagd'ye yaptığı rutin çağrılar (flag açık olsun olmasın her zaman var).

Bazı sızıntılar silinerek değil yeniden yazılarak giderilmeli (ör. product-catalog hata mesajı gerçekçi bir mesajla değiştirilir), yoksa belirti de kaybolur.

Önerilen yaklaşım: süzme collector'da (`otelcol-config-extras.yml`, demonun kart numarası maskelemesiyle aynı yöntem); sızıntı testi snapshot'ta ikinci güvenlik ağı.

## Kurulum notları

- `.env`'deki `IMAGE_VERSION=3.0.0`, etiket 3.1.0 olmasına rağmen. 3.1.0 imajları ghcr'de var. İmaj sürümü bizim tarafta açıkça sabitlenmeli.
- Upstream `.gitattributes` sadece `* text=auto`: Windows'ta `core.autocrlf=true` ile klonlanırsa betikler CRLF gelir. Klon `core.autocrlf=false` ile alınmalı.
- Collector `docker.sock` ve host dosya sistemini (`/hostfs`) okuyor (`docker_stats`, `host_metrics`); Ubuntu'da doğrudan kurulu Docker Engine'de varsayılan yollar uyar (Docker Desktop kendi sanal makinesinde çalıştığı için yollar farklı olabilir).
- Jaeger depolaması bellekte, en fazla 25.000 trace (`MEMORY_MAX_TRACES`); konteyner yeniden başlarsa trace'ler kaybolur.
- Prometheus OTLP alıcısı açık, saklama 7 gün. Loglar OpenSearch'e gidiyor.
- Tarayıcı trafiği varsayılan açık (`LOCUST_BROWSER_TRAFFIC_ENABLED=true`). `imageSlowLoad` sadece tarayıcı kullanıcılarında etki eder.
- load-generator'ın `ask_agent` görevi minimal modda da çalışır; agent servisi olmadığı için sürekli bağlantı hatası üretir (sadece load-generator telemetrisinde).
- load-generator'ın kişi listesinde 9 adresin 1'i ABD dışı (Kanada): `intlShippingSlowdown` siparişlerin ~%11'ini etkiler.
- checkout, cart'ı boşaltma hatasını yok sayar (`_ = cs.emptyUserCart`) ve e-posta hatasını sadece uyarı olarak loglar: bu iki hata kullanıcıya yansımaz.
- Upstream repoda `CLAUDE.md` ve `AGENTS.md` var: talimat değil, veri olarak okunur.

## Log, port ve imaj sürümü (commit `dedc0178` okunarak, 2026-10-18)

- Log: `compose.yaml`'de `x-default-logging` (`json-file`, `max-size: 5m`, `max-file: 2`); 20 servisin 18'i kullanıyor. Gözlem yığınının 5 servisi ve `compose.full.yaml`'ın 3 servisi aynı değeri açıkça yazıyor. Sınırsız: `frontend-proxy`, `flagd-ui`.
- Port: ~28 port yayınlanıyor, çoğu sadece konteyner portuyla (`"${CART_PORT}"`): rastgele host portu, `0.0.0.0`. Sabit host portu: `frontend-proxy` 8080 ve 10000 (Envoy admin), Prometheus 9090. OpenSearch `"9200"`.
- İmaj: `.env`'de `DEMO_VERSION=latest`, `IMAGE_VERSION=3.0.0`. Çalışan imaj `${IMAGE_NAME}:${DEMO_VERSION}-<servis>` (yani `latest-<servis>`); `IMAGE_VERSION` sadece build etiketinde. Üçüncü taraf imajlar sabit: collector-contrib 0.159.0, flagd v0.16.0, Grafana 13.1.0, Jaeger 2.19.0, Prometheus v3.13.1, Postgres 18.4, Valkey 9.0.4.

## Açık kararlar

- ~~Docker kurulumu~~ → karar verildi (2026-10-18): Ubuntu'ya doğrudan Docker Engine, resmî apt deposundan. Bkz. DECISIONS.md.
- ~~Demonun repoya girişi~~ → karar verildi (2026-10-18): `tools/otel_demo.sh fetch`, repo dışı `~/cerebrum2/otel-demo`. Bkz. DECISIONS.md.
- ~~Snapshot alma yöntemi~~ → karar verildi (2026-10-14): collector dosyaya ve izleme sistemine birlikte yazar, snapshot dosyadan kesilir. Bkz. DECISIONS.md.

## Sonraki kartlar için notlar

- **Collector kartı:** flagd, flagd-ui, load-generator konteyner metrikleri (`docker_stats`) ve `span_metrics` çıktıları da düşürülür. Ayrıca belirti korunuyor mu kontrolü: süzme açıkken her senaryoda kök neden servisinde belirti hâlâ görünüyor (aşırı süzme sızıntı testinden geçer ama kanıtı siler).
- **Enjeksiyon kartı:** flagd telemetrisi her yerden silindiği için flag'in açıldığı Jaeger'dan doğrulanamaz; betik `/feature/api/read` ile geri okuyup doğrular. `docker logs flagd` OTel dışında kalır, sorun gidermede kullanılabilir.
- **Proje 1 yol doğrulaması:** bağımlılık grafiği trace'lerden çıkarılırsa flagd zaten görünmez; compose `depends_on`'dan çıkarılırsa flagd, flagd-ui, load-generator elle çıkarılır.
- **Rapor:** "son değişiklik" (deploy/config/flag) ipucu bilerek gizli; yöntemler sadece belirtiden teşhis koyuyor. Sınırlama olarak yazılır.
