# OTEL DEMO

OpenTelemetry Demo hakkında keşif notları. Kaynak: `open-telemetry/opentelemetry-demo` etiket **3.1.0** (2026-09-18, commit `dedc0178918e260823323b8d95005a8cb924b007`), dosyalar okunarak çıkarıldı (2026-10-14); 2026-10-18'de minimal modda çalıştırıldı (bkz. "Çalıştırma").
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

- Minimal mod limit toplamı ~6,8 GB. Gerçek kullanım (2026-10-18, açılıştan ~2 dk sonra): toplam 2,87 GiB; bkz. "Çalıştırma".
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
- Yazma işlemi flagd'nin bağlı klasöründeki `demo.flagd.json`'u değiştirir. C1'den beri bu klasör klon dışında, `~/cerebrum2/runtime/flagd/` (her `up`'ta klondan sıfırlanır); klon kirlenmez. flagd-ui dosyayı yeniden biçimlendirdiği için flag kapatılınca dosya ilk haline dönmez (SHA farklı); başlangıç hali yalnız `up` ile gelir.

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

## Süzme kuralları (C1, 2026-10-20; `deploy/otel-demo/otelcol-config-extras.yml`)

`filter/sim_world` düşürür, `transform/scrub` temizler ve yeniden yazar; ikisi de upstream processor'larından sonra, iki çıkıştan (dosya ve izleme sistemi) önce. Kurallar 2026-10-20 keşif koşusunun envanterine dayanır (10 dk, flag'ler kapalı).

| Sızıntı tablosu satırı | Kural |
|---|---|
| flagd, flagd-ui servis telemetrisi | `service.name` flagd/flagd-ui/load-generator → span, log, metrik düşer (flagd-ui'nin kendi telemetrisi yok; konteyner metrikleri aşağıda) |
| OpenFeature `TracingHook` `feature_flag.evaluation` olayı | span olayı düşer (span kalır); OpenFeature kapsamlı span ve loglar düşer; span ve olay özniteliklerinde `feature_flag.*` silinir |
| cart `MetricsHook` `feature_flag.*` metrikleri | `feature_flag.` ile başlayan metrikler ve OpenFeature kapsamlı metrikler düşer |
| recommendation `demo.feature_flag.recommendation_cache` | öznitelik silinir |
| ad logu (`adManualGc`) | yeniden yazılır: `Performing a full garbage collection now` (WARN korunur) |
| shipping logu | `shipping.feature_flag.evaluated/evaluation_failed` kayıtları düşer; gecikme logu `Delaying international shipment` olur (`delay_secs` korunur) |
| frontend-proxy erişim logu ve span'leri (`/feature`, `DI`) | `/flagservice`, `/feature`, `/loadgen` yolları ve `flagservice`/`flagd-ui`/`loadgen` cluster'ı → log ve span düşer; `DI` yanıt bayrağı (gövdenin 6. alanı ve span `response_flags`) `-` olur ya da listeden çıkarılır |
| Tarayıcının flag sorguları (`/flagservice/`, OFREP) | `frontend-web` dahil `url.full`/`http.url`/`url.path` kuralı → span düşer; OFREP kullanan load-generator tümden düşüyor |
| flagd, flagd-ui, load-generator konteyner metrikleri | `container.name` kuralı (`docker_stats`); `span_metrics` için flagd'ye giden span'ler bağlayıcıdan önce düştüğü için metrik üretilmez, kalanlar `span.name` veri noktası kuralıyla düşer |
| product-catalog span durumu ve olayı | yeniden yazılır: `Error: failed to load product from catalog` (durum, olay adı, olay ve span öznitelikleri, loglar; çağıran servislere yayılan hali dahil) |
| product-catalog kilit logu | yeniden yazılır: `holding ACCESS EXCLUSIVE lock on catalog.products`; hata hali `failed to acquire ACCESS EXCLUSIVE lock on catalog.products` |
| load-generator span ve logu | `service.name` kuralı (tümden düşer) |
| *Tabloda yoktu:* servislerin flagd'ye rutin çağrıları | span adı, `server.address`/`net.peer.name` = flagd, `rpc.service`, `original_span_name`, `thread.name` → span düşer; RPC istemci metriklerinde `rpc.service`/`server.address` → veri noktası düşer |
| *Tabloda yoktu:* host süreç metrikleri (`host_metrics` process) | bütün süreçlerin komut satırını taşıyordu (flagd, locust, masaüstü, enjeksiyon komutları) → `processscraper` kapsamlı metrikler tümden düşer (Eren onayı); sistem metrikleri kalır |
| *Tabloda yoktu:* collector'ın kendi logları | ayar ve kural metinlerini (yeniden yazılan mesajlar) logluyordu → `service.name = otelcol-contrib` logları düşer; `otelcol_*` metrikleri kalır |

- Flag açıkken görünen kurallar (yeniden yazımlar, `DI`, olaylar) C1'de sentetik kayıtlarla sınandı (girdide 43 bulgu, çıktıda 0); gerçek veride C2'de.
- `transform/scrub` yolları bağlam ön ekli (`span.`, `spanevent.`, `log.`): ön eksiz yazılınca collector açılışta ifadeleri kendi loguna basıyordu.
- Sınır: kurallar alan adlarına dayanır (OTTL'de "her alanda ara" yok); yeni bir alan çıkarsa sızıntı testi yakalar.

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

## Çalıştırma (2026-10-18, Ubuntu 24.04, Docker 29.9.1, Compose v5.6.0)

```
tools/otel_demo.sh fetch    # ~/cerebrum2/otel-demo'ya 3.1.0 klonu (71 MB), sonra commit + temizlik doğrulaması
tools/otel_demo.sh up       # minimal mod: compose.yaml + compose.observability.yaml + deploy/otel-demo/compose.extras.yaml
tools/otel_demo.sh config   # up'ın kullandığı birleşik ayar (ek argümanlar docker compose config'e geçer)
tools/otel_demo.sh down     # durdurur, volume silmez; klon kirli olsa da çalışır
```

- Adresler (sadece bu makineden): mağaza `http://127.0.0.1:8080/`, Jaeger `/jaeger/ui`, Grafana `/grafana`; Prometheus `127.0.0.1:9090`, OpenSearch `127.0.0.1:9200`.
- Makine ayarı `/etc/docker/daemon.json` (repoda değil): `{"log-driver": "json-file", "log-opts": {"max-size": "5m", "max-file": "2"}, "ip": "127.0.0.1"}`. Compose dışı konteynerlere de uygulanır.
- İlk `up` 15 dk 17 sn: ~14,7 dk 12,2 GB imaj indirme, ~42 sn açılış. İmajlar inmişken `up` 83 sn.
- 25 konteyner; 19'unda healthcheck var (cart, flagd, grafana, jaeger, otel-collector, prometheus'ta yok).
- Bellek (açılıştan ~2 dk sonra, `docker stats`): toplam 2,87 GiB. En büyükler: opensearch 860 MiB / 1 GiB, load-generator 583 MiB / 1,47 GiB, ad 223 MiB / 300 MiB, otel-collector 195 MiB / 400 MiB, flagd-ui 175 MiB / 200 MiB. `free -h`: kullanılan 4,7 → 7,4 GiB, kullanılabilir 7,9 GiB.
- Disk: imajlar 12,2 GB, isimsiz volume'ler 66 MB (prometheus `/prometheus`, jaeger `/tmp`, astronomy-db).
- Kalıcılık (`up` her seferinde `--force-recreate`): Prometheus verisi imajın isimsiz volume'ü sayesinde yeniden kurulumda kalıyor; OpenSearch verisi siliniyor (volume yok); Jaeger zaten bellekte. `down`/`up` sonrası ölçülmedi.
- OpenSearch'te zaman damgası 0 (1970) olan loglar var (ilk ~4 dk'da 53 belge).
- Collector (C1, 2026-10-20): dosya çıkışı `~/cerebrum2/telemetry/filtered/{traces,metrics,logs}.jsonl` (100 MB'ta döner, 2 yedek). `tools/otel_demo.sh up --raw` ayrıca süzülmemiş kopyayı `raw/`'a yazar (iş bitince silinir). Collector `eren:docker` kullanıcısıyla. Flag dosyası `~/cerebrum2/runtime/flagd/demo.flagd.json`, her `up`'ta klondan sıfırlanır.
- Hacim (30 dk, süzme açık): traces ~389 MB/saat, logs ~131, metrics ~108 → ~630 MB/saat. Süzülmemiş kopya açıkken toplam ~1,5 GB/saat. Şimdiki döndürmeyle dosyalar traces'te ~46 dk, logs'ta ~2,3 saat, metrics'te ~2,8 saat geriye gidiyor.
- Zaman damgası 0 (dosya çıkışı, 30 dk): logların 2.716 / 55.965'i (currency 1.973, shipping 743); span ve metrik veri noktalarında 0.
- Collector belleği: süzme açık ~107 MiB, süzülmemiş kopya da açıkken ~239 MiB (limit 400M).

## Açık kararlar

- ~~Docker kurulumu~~ → karar verildi (2026-10-18): Ubuntu'ya doğrudan Docker Engine, resmî apt deposundan. Bkz. DECISIONS.md.
- ~~Demonun repoya girişi~~ → karar verildi (2026-10-18): `tools/otel_demo.sh fetch`, repo dışı `~/cerebrum2/otel-demo`. Bkz. DECISIONS.md.
- ~~Snapshot alma yöntemi~~ → karar verildi (2026-10-14): collector dosyaya ve izleme sistemine birlikte yazar, snapshot dosyadan kesilir. Bkz. DECISIONS.md.

## Sonraki kartlar için notlar

- **Collector kartı:** flagd, flagd-ui, load-generator konteyner metrikleri (`docker_stats`) ve `span_metrics` çıktıları da düşürülür. Ayrıca belirti korunuyor mu kontrolü: süzme açıkken her senaryoda kök neden servisinde belirti hâlâ görünüyor (aşırı süzme sızıntı testinden geçer ama kanıtı siler).
- **Enjeksiyon kartı:** flagd telemetrisi her yerden silindiği için flag'in açıldığı Jaeger'dan doğrulanamaz; betik `/feature/api/read` ile geri okuyup doğrular. `docker logs flagd` OTel dışında kalır, sorun gidermede kullanılabilir.
- **Enjeksiyon kartı (flag, 2026-10-20 ölçüldü):** flagd dosyayı ~1 sn aralıkla okuyor; betik flag'i değiştirdikten sonra flagd'ye sorarak doğrulamalı (`POST /flagservice/flagd.evaluation.v1.Service/ResolveBoolean`, `{"flagKey": ..., "context": {}}`), flagd-ui'nin `/feature/api/read`'i yetmez. flagd-ui dosyayı root olarak yeni dosya halinde yazıyor. flagd-ui'de rastgele flag açan bir zamanlayıcı var (`FlagdUi.Scheduler`, 15 dk'da bir 1–3 dk); varsayılan kapalı, sadece arayüzden başlıyor: her vakadan önce kapalı olduğu kontrol edilmeli.
- **Vaka üretim kartı (collector açılış yarışı, 2026-10-20):** collector ile diğer konteynerler aynı anda başlıyor; `docker_stats` açılışta bir konteyneri kaçırabiliyor (ölçümde `ad` 5 dk boyunca yoktu, collector yeniden başlayınca geldi; 2026-10-21 planlama ölçümünde `image-provider` 10 dk boyunca yoktu; upstream'de de aynı yarış). Vaka öncesi kontrol: Prometheus'ta `count(container_uptime_seconds)` = beklenen konteyner sayısı (minimal modda 25; süzme açıkken flagd, flagd-ui ve load-generator düştüğü için 22); değilse collector yeniden başlatılır.
- **Upstream notu:** birleşik upstream ayarında (`otelcol-config-full.yml` metrik alıcı listesini değiştirdiği için) `prometheus/ad` alıcısı kullanılmıyor; ad'nin Prometheus metrikleri demonun kendisinde de toplanmıyor. Bizim katman bunu değiştirmez.
- **Proje 1 yol doğrulaması:** bağımlılık grafiği trace'lerden çıkarılırsa flagd zaten görünmez; compose `depends_on`'dan çıkarılırsa flagd, flagd-ui, load-generator elle çıkarılır.
- **Rapor:** "son değişiklik" (deploy/config/flag) ipucu bilerek gizli; yöntemler sadece belirtiden teşhis koyuyor. Sınırlama olarak yazılır.
