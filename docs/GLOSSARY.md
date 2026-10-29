# GLOSSARY

Sadece Eren'in onayladığı isimler.

| İsim | Anlamı |
|---|---|
| `aiops_rca` | Proje kök klasörü ve repo adı |
| `small_local_model` | Küçük lokal model: CPU'da, makinede çalışan küçük dil modeli (Proje 1) |
| `large_api_model` | Büyük API modeli: ücretsiz API üzerinden kullanılan büyük model (Groq gpt-oss-120b, Gemini 3.5 Flash Lite) |
| `incident` | Vaka: tek bir hata enjeksiyonu ve onun kaydı (kodda `incident_id`, `incidents/`) |
| `snapshot` | Bir incident'ın ham log/metrik/trace kaydı + doğru cevap (ground truth) |
| `candidate_narrowing` | Hibrit daraltma: istatistiğin aday servisleri azaltıp sadece onları LLM'e vermesi (Proje 1) |
| `baseline` | LLM'siz karşılaştırma yöntemleri (kural, BARO) |
| `tools/` | Hattın parçası olmayan yardımcı ve tek seferlik betikler |
| `api_smoke_test` | API duman testi: aday modellerin teknik uygunluk kontrolü (`tools/api_smoke_test.py`) |
| `llm_cache/` | Geliştirme denemelerinin LLM cevapları; git dışı |
| `eval_responses/` | Resmî değerlendirme koşusunun LLM cevapları; repoda tutulur |
| `tests/fixtures/snapshots/` | CI için 3-5 incident'lık sabit snapshot alt kümesi; repoda tutulur |
| `docs/OTEL_DEMO.md` | OpenTelemetry Demo keşif notları: modlar, bellek, senaryolar, sızıntı yolları |
| `docs/INCIDENT_CATALOG.md` | Enjekte edilecek hatalar, doğru cevap kuralı, beklenen belirti ve yayılım yolları |
| `noise_layer` | Gürültü katmanı: asıl hatayla aynı anda açılan, yanıltıcı ama kök neden olmayan etki (ör. trafik seli) |
| `src/aiops_rca/` | Projenin Python paketi (src düzeni) |
| `src/aiops_rca/leakage.py` | Sızıntı testi: modele verilecek görünümde cevabı ele veren iz arar |
| `tests/fixtures/leakage/` | Sızıntı testinin sahte OTLP JSON dosyaları |
| `gen_leakage_fixtures` | Sızıntı testinin sahte dosyalarını üreten betik (`tools/gen_leakage_fixtures.py`) |
| `leak_<kaynak>.jsonl`, `clean_symptoms.jsonl`, `clean_false_alarms.jsonl` | Sızıntı testi sahte dosyaları: sızıntı tablosunun bir satırı / normal trafik ve gerçekçi belirtiler / yanlış alarm adayları |
| `Finding` | Sızıntı testinin tek bulgusu: `file`, `line`, `signal`, `service`, `json_path`, `rule`, `match` |
| `LeakageInputError` | Sızıntı testinde girdi hatası (çıkış kodu 2); sonuç asla temiz sayılmaz |
| `scan_model_view` | Bir `model_view` klasörünü tarayıp bulgu listesini dönen fonksiyon |
| `flag_name`, `feature_flag_phrase`, `flagd_term`, `feature_path`, `envoy_fault_flag`, `excluded_service`, `known_phrase` | Sızıntı testi kural adları (her biri OTEL_DEMO.md sızıntı tablosundaki satırlara bağlı) |
| `make_view`, `log_line`, `view_with_lines`, `leak_table_rows`, `LEAK_FIXTURES`, `CLEAN_FIXTURES`, `ALL_FLAGS` | `tests/test_leakage.py` yardımcıları ve test tabloları |
| `positive_control` | Pozitif kontrol: dedektörün bilinen bir sızıntıyı gerçek veride gerçekten bulduğunu gösteren kontrol (süzme kapalı) |
| `model_view` | Model görünümü: bir incident için yöntemlere verilen veri; etiketler ve cevabı ele veren adlar içermez |
| `task/<konu>` | Görev kartı dalı; her kart bir dal ve bir PR (ör. `task/line-endings`) |
| `.github/workflows/ci.yml` | CI workflow dosyası (GitHub Actions) |
| `CI` | Workflow adı; GitHub Actions sekmesinde görünür |
| `test` | CI job'u; main dal korumasında zorunlu kontrol bu adla seçilir |
| `tools/otel_demo.sh` | OTel Demo betiği: demoyu repo dışına sabit sürümde getirir ve minimal modda çalıştırır |
| `fetch`, `up`, `down`, `config` | `tools/otel_demo.sh` komutları: klonla ve doğrula / başlat / durdur (volume silmez) / birleşik compose ayarını bas |
| `deploy/otel-demo/compose.extras.yaml` | Bizim compose katmanımız (`deploy/`: demo ortamının bizim yapılandırma dosyaları); upstream dosyalarına dokunmadan en son yüklenir |
| `tools/local_model_bench.sh` | Lokal model hız ölçümü betiği (llama-bench, sabit Docker imajı) |
| `matrix`, `sustained`, `--resume` | `local_model_bench.sh` komutları: model × iş parçacığı tablosu turlar halinde / 30 dk sürekli yük / yarım kalan tablo koşusunu eksik hücrelerden sürdür |
| `tools/bench_summary.py` | Hız ölçümü koşularının özetini (tablo, bütçe kararı) üreten betik |
| `docs/LOCAL_MODEL_BENCH.md` | Lokal model hız ölçümünün kurulumu, yöntemi ve sonuçları |
| `~/cerebrum2/models/` | GGUF model dosyaları; repo dışı |
| `~/cerebrum2/bench_runs/` | Hız ölçümü ham çıktıları (`<tarih-saat>-matrix/`, `<tarih-saat>-sustained/`); repo dışı |
| `battery-charge-limit.service` | Makinedeki systemd birimi: açılışta ve uykudan dönüşte şarj sınırını %80'e yazar (repoda değil) |
| `~/cerebrum2/telemetry/` | Collector dosya çıkışı (`filtered/` süzülmüş, `raw/` süzülmemiş kopya); repo dışı |
| `~/cerebrum2/runtime/flagd/` | flagd ve flagd-ui'nin bağladığı flag dosyası; her `up`'ta klondan sıfırlanır; repo ve klon dışı |
| `deploy/otel-demo/otelcol-config-extras.yml` | Bizim collector katmanımız: süzme ve dosya çıkışı |
| `deploy/otel-demo/otelcol-config-raw.yml`, `deploy/otel-demo/compose.raw.yaml` | Süzülmemiş paralel çıkışın collector ve compose katmanları |
| `--raw` | `tools/otel_demo.sh up`/`config` seçeneği: süzülmemiş kopyayı da yaz (varsayılan kapalı) |
| `OTEL_COLLECTOR_CONFIG_RAW`, `OTEL_COLLECTOR_USER` | `otel_demo.sh`'in compose'a geçirdiği değişkenler: süzülmemiş katman dosyası / collector kullanıcısı (`uid:docker gid`) |
| `tools/check_collector_pipelines.py` | Upstream ve bizim collector pipeline listelerini karşılaştıran betik |
| `filter/sim_world`, `transform/scrub` | Collector processor adları: "simüle edilen dünyada flagd yok" düşürmesi / kalan izleri temizleme ve mesaj yeniden yazma |
| `tools/trial_summary.py` | Kaba kalite denemesi: süzülmüş dosyalardan alarm öncesi/sonrası 10 dk'lık vaka özeti (JSON) |
| `tools/trial_ask_models.py` | Kaba kalite denemesi: aynı istemi ve özeti beş modele sorar, cevapları kaydeder |
| `alarm_time_utc`, `window_minutes`, `requests_before/after`, `error_rate_before/after`, `p95_ms_before/after`, `top_warning_and_error_logs_after_alarm` | `trial_summary.py` özetinin JSON alanları: alarm zamanı / pencere uzunluğu / servise gelen istek sayısı / hatalı istek oranı / istek süresinin 95. yüzdeliği (ms) / alarm sonrası en sık WARN+ log mesajları |
| `cpu_pct_avg_before/after`, `cpu_pct_max_before/after`, `mem_mb_avg_before/after` | `trial_summary.py` özetinin konteyner alanları: CPU (bir çekirdeğin yüzdesi) ortalaması / en yüksek değeri / bellek ortalaması (MB) |
| `tools/trial_symptoms.py`, `symptoms.json` | Zor deneme belirti kontrolü: kök neden servisinde özetteki değerler normal döneme göre sapıyor mu; sonuç vaka klasöründe, `view/` dışında |
| `symptomatic`, `no_symptom` | `trial_symptoms.py` kararı: belirtili / belirtisiz (belirtisiz vakanın model sonucu yoruma girmez) |
| `error_rate`, `p95_ms`, `cpu_pct_avg`, `mem_mb_avg`, `new_warn_log`, `request_drop` | `symptoms.json` sinyal adları: hata oranı / p95 süre / CPU ortalaması / bellek ortalaması / önceki pencerede olmayan WARN+ log / istek düşüşü |
| `qwen3.5-2b`, `qwen3.5-4b`, `qwen3.5-9b`, `gpt-oss-120b`, `gemini-3.5-flash-lite` | `trial_ask_models.py` model etiketleri; `answers/<etiket>.json` dosya adları |
| `--score` | `trial_ask_models.py` seçeneği: model çağırmadan kayıtlı cevaplardan puan tablosu basar |
| `unmatched` | `--score` tablosunun son sütunu: cevaptaki, özetteki hiçbir servise uymayan adlar (harf dışı karakterler atılıp küçük harfle karşılaştırılır) |
| `root_cause_candidates` | `trial_ask_models.py`'nin modellere zorladığı JSON şemasının adı: tam 3 `{service, reason}` adayı |
| `trial-llama` | `trial_ask_models.py`'nin açtığı llama.cpp sunucu konteyneri (`127.0.0.1:8081`) |
| `~/cerebrum2/quality_trial/` | Kaba kalite denemesi çıktıları; `case1/`, `case2/` altında `view/summary.json` (modele giden, sızıntı CLI'ın taradığı), `answers/` (model cevapları), `case.json` (doğru cevap, `view/` dışında); repo dışı |
| `task/ci-red-check` | Kasıtlı kırmızı dalı: CI'ın bozuk testte ve hiç test toplanmadığında kırmızı olduğunu gösterir; birleştirilmez |
| takma ad | Modele giden girdide servis adlarının (ve log mesajlarındaki tanımlayıcı biçimlerinin: tireli, CamelCase, `…Service`; sıradan kelimeler değil) yerine konan, OTel Demo'yu ve Online Boutique'i çağrıştırmayan anlamlı adlar; ezber etkisini kaldırmak ve ölçmek için. Cevap eşleme tablosuyla gerçek ada çevrilip puanlanır. Kod adı uygulamada önerilir |
| takma ad eşlemesi (2026-10-23) | frontend → storefront, frontend-proxy → edge-gateway, ad → promotions, cart → basket, checkout → order-processor, payment → billing, product-catalog → inventory, recommendation → suggestions, shipping → logistics, quote → rate-calculator, currency → fx-rates, email → notifier, image-provider → media-server, telemetry-docs → docs-site, astronomy-db → main-db, valkey-cart → session-cache |
| `tools/trial_alias.py`, `ALIASES` | Takma ad ön denemesi: `view/summary.json`'dan takma adlı kopya üretir ve kontrol eder / koddaki eşleme tablosu (GLOSSARY eşlemesinin aynısı) |
| `view_alias/` | Vaka klasöründe takma adlı özetin klasörü (`view_alias/summary.json`; modele giden, sızıntı CLI'ın taradığı) |
| `answers_a1/`, `answers_a2/`, `answers_alias/` | Takma ad ön denemesinin cevap klasörleri: gerçek adla 1. ve 2. koşu / takma adla koşu (eski `answers/` yerinde) |
| `--view`, `--answers`, `--alias`, `--probe` | `trial_ask_models.py` seçenekleri: özetin okunduğu klasör / cevapların yazıldığı klasör / puanlamada takma adları gerçek ada çevir / bilgi yoklaması kipi (cevaplar verilen klasöre) |
| `feature_flag_scenarios` | Bilgi yoklamasının JSON şemasının adı: `scenarios` listesi, öğeleri `{flag, service}` |
| `~/cerebrum2/quality_trial_probe/` | Bilgi yoklaması cevapları (OTel Demo flag senaryoları; cevap içerir, `quality_trial` dışında); repo dışı |
| `tools/scenario_runner.py` | Senaryo koşucusu (C2, vaka üretiminde de): korumalar → `up --raw` → 10 dk normal + 10 dk flag → kayıt ve telemetri penceresinin kopyası; `list`, `guards`, `run <id>… \| all` |
| `tools/c2_measure.py` | C2 ölçümü: koşu klasöründen sızıntı (`positive_control`), belirti ve güç (raw/filtered), yeniden yazımlar, basit kural, collector sayaçları; model yok |
| `~/cerebrum2/c2_runs/` | Koşucu çıktıları, koşu başına `<senaryo>_<varyant>_<deneme>/` (`%` → `pct`); cevap ve süzülmemiş veri içerir, repo dışı; süzülmemiş kısmı planlama doğrulamasından sonra Eren onayıyla silinir |
| `run.json` | Koşu kaydı: senaryo, flag, varyant, kök neden, zamanlar (UTC), konteyner sayıları, zamanlayıcı, pencerede yeniden başlama/OOM, korumalar, en yüksek sıcaklık, collector en yüksek bellek, pencere kapsaması (sinyal başına en eski kayıt, MB/dk), geçerli/geçersiz ve sebep |
| `measure.json` | `c2_measure.py`'nin koşu başına sonucu (koşu klasöründe) |
| `samples/` | Koşu klasöründe kural testi için aday kayıtlar (raw bulgularından tek kayda indirilmiş OTLP satırları ve `index.tsv`); repoya girmeden önce Eren görür |
| `samples/index.tsv` | `samples/` dizini: satır başına örnek konumu (`<sinyal>.jsonl:<n>`), sinyal, CLI kuralı, servis, eşleşen metin, senaryoya özgü mü (`specific`/`routine`), pencere |
| `window/raw/`, `window/filtered/` | Koşu klasöründe telemetri penceresinin kopyası (normal − 2 dk … flag kapanışı + 1 dk), sinyal başına `traces.jsonl`, `metrics.jsonl`, `logs.jsonl`; `raw/` cevap içerir, planlama doğrulamasından sonra Eren onayıyla silinir |
| `collector_mem.tsv` | Koşu klasöründe collector belleği, dakikada bir (UTC zaman, MiB) |
| `containers_start.txt`, `containers_end.txt` | Koşu klasöründe normal başında ve flag kapanışında konteyner durumu (yeniden başlama sayısı, OOM, çalışıyor mu, başlama zamanı) |
| `tools/test_collector_rules.sh` | Collector kural testi: geçici collector'a (demonun imajı) bizim ayarımız ve fixture kayıtları; kapsam, girdi sızıntılı, tam ayarda çıktı temiz ve temiz kontroller aynı, kural başına `delete`/`alone` testi (kasıtlı kırmızı). Docker ister, CI'da koşmaz |
| `tests/fixtures/collector_rules/` | Kural testi girdisi: `traces.jsonl`, `metrics.jsonl`, `logs.jsonl` (C2 raw verisinden tek kayıtlık, elle gözden geçirilmiş, makine bilgisi temizlenmiş OTLP istekleri; Eren onaylı, 2026-10-24) ve `rules.tsv` |
| `rules.tsv` | Kural testi listesi: `section` (ayardaki bölüm yolu), `rule` (kural metni), `test` (`delete`: tek sorumlu, silinince kırmızı; `alone`: yedekli, kuralsız kırmızı / tek başına yeşil; `none`: örneksiz, `note`'ta gerekçe; `clean`: temiz kontrol), `sample` (`<dosya>:<satır>`), `note` |
| `yeniden oynatma` | Snapshot dosyalarını boş bir izleme sistemine (Jaeger, Prometheus, OpenSearch) orijinal zaman damgalarıyla gönderip canlı tarafı doldurma; Proje 2'de kullanılır |
| `tools/storage_check.py` | Depolama kartı ölçüm betiği: canlı izleme sisteminin (Jaeger, Prometheus, OpenSearch) kaybı, büyümesi, belleği |
| `watch`, `--minutes`, `--keep-up` | `storage_check.py` komutu: demoyu açıp izleme sistemini bir pencere boyunca izler / pencere uzunluğu (dk) / iş bitince demoyu açık bırak |
| `~/cerebrum2/storage_runs/` | `storage_check.py` çıktıları, koşu başına `<UTC zaman>-watch/` ya da `<UTC zaman>-replay/`; repo dışı |
| `watch.json`, `watch.log` | `watch` koşusunun sonuç kaydı / günlüğü |
| `mem.tsv`, `sizes.tsv` | `watch` koşusunda dakikalık bellek (jaeger, prometheus, opensearch, otel-collector) / 5 dakikalık veri klasörü boyutları |
| `opensearch_start.json`, `opensearch_end.json`, `opensearch_mapping.json` | `watch` koşusunda OpenSearch'ün ham istatistikleri (başta, sonda) / sonda `otel-logs-*` indekslerinin eşlemesi |
| `collector_errors.json` | `watch` koşusunda collector logundaki opensearch satırları: OpenSearch'ün `reason` metinleri ve sayıları, mesaj grupları |
| `prometheus-data`, `jaeger-data`, `opensearch-data` | İzleme sisteminin isimli Docker volume'leri (compose adı; Docker'da `otel-demo_` önekiyle); `down` silmez |
| `deploy/otel-demo/jaeger-config-extras.yml`, `JAEGER_CONFIG_EXTRAS` | Jaeger katmanımız (diske yazma, 7 gün) / `otel_demo.sh`'in onun yolunu compose'a geçirdiği değişken |
| `badger_main` | Jaeger ayarında diskteki (badger) izleme deposunun adı |
| `otel-logs-retention` | OpenSearch ISM kuralı: 7 günden eski `otel-logs-*` indeksini siler; `otel_demo.sh up` yükler |
| `transform/backend_compat` | Collector processor'ı (süzmeden sonra, iki çıkıştan önce): izleme sistemi uyumu; sızıntı kuralı değil |
| `http_ports` | cart'ın .NET açılış uyarısındaki düz `http` özniteliğinin `transform/backend_compat` sonrası adı |
| `compare`, `--run`, `--tag` | `storage_check.py` komutu: canlı = dosya karşılaştırması / aralığın alındığı `watch` klasörü / ikinci karşılaştırmanın adı |
| `compare.json`, `compare_<tag>.json` | `compare` sonucu (`watch` klasöründe) |
| `NOT_LEAK` | `test_collector_rules.sh`'te testin hatlarına girmeyen (sızıntı kuralı taşımayan) processor'lar |
| `monitoring_gb`, `MAX_MONITORING_GB` | Koşucu korumasında izleme volume'lerinin toplamı (GB, ondalık; `guards()` çıktısında alan) / üst sınırı (40 GB); aşılırsa koşu başlamaz |
| `AIOPS_MAX_MONITORING_GB` | `MAX_MONITORING_GB`'yi ezen ortam değişkeni; yalnız kasıtlı kırmızı için (düşük sahte sınır) |
| `MONITORING_VOLUMES` | Korumanın topladığı üç Docker volume adı (`otel-demo_prometheus-data`, `otel-demo_jaeger-data`, `otel-demo_opensearch-data`) |
| `deploy/replay/` | Yeniden oynatma denemesinin (depolama D3) ayar klasörü: `compose.yaml`, `otelcol-replay.yml` |
| `deploy/replay/compose.yaml` | Yeniden oynatma yığını: Jaeger, Prometheus, OpenSearch (upstream tanımından `extends`) ve tek alıcısı dosya olan collector; canlı demodan ayrı compose projesi |
| `otelcol-replay.yml` | Yeniden oynatma collector'ının ayarı: `otlpjsonfile` alıcıları, `transform/backend_compat` kopyası, upstream'in üç exporter'ının kopyası (izinli farklarla) |
| `otel-replay` | Yeniden oynatma yığınının compose proje adı; konteynerler `otel-replay-<servis>-1`, volume'ler `otel-replay_*` (canlı demonunkilerden ayrı) |
| `REPLAY_WINDOW` | Yeniden oynatılan pencerenin klasörü (`traces/metrics/logs.jsonl`); collector'a `/replay` olarak salt okunur bağlanır |
| `replay` | `storage_check.py` komutu: C2 pencerelerini boş ve ayrı izleme sistemine zaman sırasıyla yeniden oynatıp dosyayla karşılaştırır |
| `replay.json`, `replay.log` | `replay` koşusunun sonuç kaydı (`<UTC zaman>-replay/` klasöründe): pencereler, sayaçlar, karşılaştırmalar, bloklar, ölçütler / günlüğü |
| `tests/test_replay_config.py` | `otelcol-replay.yml`'daki kopyaların kaynaklarıyla aynı olduğu (upstream exporter'ları `REPLAY_ONLY` dışında) ve alıcıların yalnız dosya olduğu testi |
| `REPLAY_ONLY` | `test_replay_config.py`'de yeniden oynatma ayarının upstream'den bilerek farklı satırları; her biri ayarda olmalı, listede olmayan fark kırmızı |
| `collector_<koşu>.log` | `replay` koşu klasöründe, o pencereyi oynatan collector'ın logu (collector durdurulmadan önce yazılır) |
| `collector_error_lines` | `replay.json`'da pencere başına collector logundaki hata satırı sayısı |
| `metrics_oldest_ms`, `metrics_newest_ms` | `replay.json`'da pencere dosyasındaki en eski / en yeni metrik zamanı (ms); blok kontrolünün ölçüsü |
| `~/cerebrum2/snapshots/` | Snapshot kökü (repo dışı, sıkıştırmasız); vaka başına `<incident_id>/` = o vakanın `model_view`'ı |
| `inc-<8 hex>` | `incident_id` biçimi: rastgele (`secrets`), senaryo, sıra ve tarih içermez |
| `window.json` | `model_view` içinde pencere sınırları (`start`, `end`, UTC); başka bilgi yok |
| `incidents/<incident_id>.json` | Repoda etiket ve koşu kaydı (yalnız geçerli vakalar): `answer`, `window`, `checks`, `valid`, `invalid_reasons`, `marks`, `run` |
| `answer` | Etiketin doğru cevap bölümü: `scenario`, `variant`, `noise_layer`, `injection_start`, `injection_end`, `root_cause_service`, `fault_type`, `propagation_path` (kenar listesi), `categories` |
| `set`, `pilot` | Etiketin set alanı (`dev` / `test` / `pilot`) / resmî sete girmeyen pilot vakaların değeri |
| `checks` | Etiketin kontrol sonuçları: `coverage`, `leakage`, `baseline_health`, `symptom`, `event`, `monitoring_health` |
| `marks` | Geçerli ama işaretli vaka: `no_symptom`, `borderline`, `not_measurable` (set kararı V3'te) |
| `run` | Etiketin koşu kaydı: `versions`, `guards`, `times`, `containers`, `duration_s`, `snapshot_bytes`, `list_entry`, `collector_restarted`, `scheduler`, `memory`, `anonymous_volumes_removed`, `overheat`, `baseline_failed`, `coverage_short`, `leakage_found` ve C2'den `restarts_in_window`, `expected_restarts`, `suspended_s`, `max_pkg_temp_c` |
| `incident_lists/`, `pilot.json` | Repoda koşulacak vaka listeleri (öğe: `scenario` = koşucu senaryo kimliği, `noise_layer`) / pilot gece listesi (13 vaka) |
| `incident_lists/v2_dry.json` | V2a kuru deneme listesi (altı hata, her biri bir hedefte, `"dry": true`) |
| `incident_lists/v2b.json` | V2b kalibrasyon gecesi listesi (16 vaka; bellek adayları taban altında kaldığı için yok) |
| `~/cerebrum2/incident_runs/` | Vaka üretimi çalışma dosyaları, gece başına `<UTC>-<liste>/`: `runner.log`, `ism.json`, her denemenin etiketi `<incident_id>.json`, vaka klasöründe bellek ve konteyner dökümleri; geçersiz vakanın snapshot'ı `<incident_id>/model_view/`'a taşınır; repo dışı |
| `ism.json` | Gece klasöründe OpenSearch ISM kontrolü (her `otel-logs` indeksinde `otel-logs-retention` mı) |
| `fault_type`, `propagation_path`, `categories` | `SCENARIOS`'taki doğru cevap alanları (INCIDENT_CATALOG tablosunun aynısı) |
| `MAX_SNAPSHOT_GB`, `AIOPS_MAX_SNAPSHOT_GB` | Snapshot kökünün üst sınırı (20 GB; korumada `snapshot_gb`) / yalnız kasıtlı kırmızı için ezen ortam değişkeni |
| `incidents` | `scenario_runner.py` komutu: bir listedeki vakaları sırayla üretir (V1 akışı) |
| `tools/incident_checks.py` | Vaka kontrolleri: `operation_rows`, `symptom_check`, `baseline_check`, `event_check`, `monitoring_health` |
| `operation_rows`, `symptom_check`, `event_check` | Servis + span adı başına istek/hata/süre / servis ve işlem düzeyinde belirti (en güçlü sinyal) / enjeksiyon döneminde olay var mı (en az M istek) |
| `baseline_check`, `monitoring_health` | Normal dönem frontend p95 ≤ 2 × referans / collector exporter sayaçları (kayıt) |
| `MIN_OP_REQUESTS`, `BASELINE_P95_MS`, `BASELINE_FACTOR` | M (10) / taban referansı (25,3 ms) / taban eşiğinin çarpanı (2) |
| `RESOURCE_SIGNALS`, `_op_signals`, `_operation_best`, `_service_best` | `incident_checks.py` iç adları: kaynak sinyalleri (`cpu_pct`, `mem_mb`) / işlem sinyalleri / servisin en güçlü işlem sinyali / servis düzeyi en güçlü sinyal |
| `WARMUP_S`, `SNAPSHOTS`, `INCIDENTS`, `INCIDENT_RUNS`, `OPENSEARCH` | Koşucu sabitleri: ısınma (300 sn, `up`'tan) / snapshot kökü / etiket klasörü / gece klasörlerinin kökü / OpenSearch adresi |
| `snapshot_gb`, `anonymous_volumes`, `remove_volumes`, `ism_explain`, `new_incident_id`, `cut_snapshot` | Koşucu fonksiyonları: snapshot kökünün boyutu / projenin konteynerlerine bağlı anonim volume'ler / onları silme / ISM kontrolü / rastgele kimlik / pencereyi snapshot'a yazma |
| `run_incident`, `cmd_incidents`, `cgroup_memory`, `versions` | Tek vaka / liste koşusu / cgroup bellek tepesi, anon ve `memory.events` / repo ve demo commit'i, imaj sürümleri |
| `tests/test_catalog.py`, `tests/test_incident_checks.py` | `SCENARIOS` ↔ INCIDENT_CATALOG senkron testi / kontrol modülünün testleri |
| `containerStop`, `containerPause`, `cpuThrottle`, `memoryLimit`, `networkDelay`, `packetLoss` | Altyapı hatası senaryoları (V2): `docker stop` / `docker pause` / `docker update --cpus` / `docker update --memory --memory-swap` / `tc netem delay` / `tc netem loss` |
| `deploy/netem/Dockerfile`, `aiops-netem:1`, `aiops-netem` | Ağ hatası yardımcı imajının tarifi (sabit alpine + iproute2, giriş `tc`) / yerel deneme imajının adı (koşular GHCR'daki `ghcr.io/erenbezek/aiops-netem`'i çeker) / hedefin ağ ad alanında koşan, iş bitince silinen yardımcı konteyner |
| `{"fault","target","param","noise_layer"}`, `"dry": true` | Vaka listesinde altyapı hatası öğesi / kuru deneme işareti (snapshot gece klasöründe, `incidents/`'a etiket yazılmaz, taban sağlık engellemez) |
| `INFRA_FAULTS`, `NETEM_IMAGE`, `NETEM_WORD`, `PARAM_RE` | Koşucu: hata → `fault_type` ve yöntem / yardımcı imaj adı / netem hatası → `tc` sözcüğü / parametre biçimleri |
| `apply_fault`, `revert_fault`, `_inspect`, `_tc`, `cleanup_failed` | Hatayı uygulayıp geri okur / geri alıp doğrular / hedefin `docker inspect` durumu / yardımcı imajla `tc` / temizlik doğrulanamadı mı (gece durur) |
| `STABLE_S` | Temizlikte yeniden başlama sayısının sabit kalması gereken süre (30 sn) |
| `schedule`, `NORMAL_RANGE_S`, `TAIL_RANGE_S` | Tohumdan normal dönem ve kuyruk süresi / 600–840 sn / 60–180 sn |
| `DRY_NORMAL_S`, `DRY_FAULT_S`, `DRY_TAIL_S` | Kuru denemenin sabit süreleri (180 / 180 / 60 sn) |
| `prom_max` | Prometheus'ta son N saniyedeki tepe değer (`max_over_time`) |
| `current_mib`, `file_mib`, `swap_mib`, `swap_peak_mib` | `cgroup_memory` çıktısında `memory.current` (bellek sınırının saydığı toplam) / dosya sayfaları / `memory.swap.current` / `memory.swap.peak` |
| `run.schedule`, `run.fault_state`, `run.target_ips` | Etikette tohum ve süreler / hata durum kaydı / hedefin IP'leri (`before` enjeksiyondan önce, `after` geri almadan sonra) |
| `before`, `applied`, `applied_ok`, `reverted`, `after`, `stable`, `verified` | `fault_state` alanları: önceki durum / uygulama sonucu (bellekte `usage_mib`) / uygulandı mı / geri alma sonucu / son okuma / `{restarts_start, restarts_end, seconds}` / temizlik doğrulandı mı |
| `usage_mib` | Bellek hatasında sınırın hesaplandığı toplam kullanım (`memory.current`) |
| `run.times.fault_on_<hata>`, `fault_off_<hata>`, `tail_end` | Hatanın uygulandığı / geri alındığı an, kuyruğun sonu |
| `paused` | `containers()` kaydında dondurulmuş mu; `split_restarts` değişimi görür |
| `run.memory.jaeger_swap_peak_mib`, `jaeger_heap_peak_mib` | Jaeger swap tepesi (dakikalık örnek) / Go yığını tepesi (`otelcol_process_runtime_heap_alloc_bytes`, Prometheus) |
| `infra_term`, `leak_infra_helper.jsonl` | Sızıntı tarayıcısında yardımcı konteyner ve `netem`/`qdisc` deseni / sahte satır dosyası |
| `caller_rows`, `caller_symptom_check`, `SPAN_KIND_CLIENT`, `_span_attrs`, `_rpc_service` | Hedefi çağıranların hedefe giden istemci span'leri / onlarda belirti / istemci span türü (3) / span özniteliklerini okuma / gRPC servis adı |
| `callers_measured`, `matched_ips`, `matched_rpc_services`, `caller` | `checks.symptom`'da ölçülen çağıran işlem sayısı / eşleşen IP'ler / eşleşen gRPC adları; karar düzeyi `caller` (`deciding.caller`) |
| `tests/test_infra_faults.py` | Altyapı hatalarının Docker'sız testleri |
| `V2c` | Vaka üretimi V2'nin üçüncü adımı: ağ belirtisi, bellek kalibrasyonu, Jaeger `GOMEMLIMIT` denemesi |
| `incident_lists/v2c.json` | V2c kısa koşu listesi (bellek hatası) |
| `checks.symptom_target`, `checks.symptom_callers` | Ağ hatalarında hedefin kendi belirti ölçümü / çağıranlardaki ölçüm; `symptom` güçlü olanın kopyası |
| `stronger_symptom` | `incident_checks.py`: iki belirti ölçümünden karar sinyali güçlü olan (eşitlikte ilki) |
| `MIN_SWAP_FREE_GB`, `swap_free_gb` | Boş swap koruma eşiği (1 GB) / `/proc/meminfo` SwapFree okuması (korumalar çıktısında da alan) |
| `run.min_swap_free_gb` | Vaka boyunca en düşük boş swap (dakikalık örnek) |
| `run.memory.jaeger_cpu_avg_cores`, `_cpu_usec` | Jaeger CPU ortalaması (normal başından demo kapanışına, çekirdek) / cgroup `cpu.stat` usage_usec okuması |
| `run.export_failures`, `EXPORT_FAILURE_QUERIES`, `_SIGNALS` | `otlp_grpc_jaeger`, `jaeger_storage_exporter`, `collector_refused` artışı (Prometheus, normal başından vaka sonuna) / onların sorgu listeleri / spans, metric_points, log_records |
| `prom_increase` | Prometheus'ta son N saniyedeki sayaç artışı (seri yoksa 0, okunamazsa None) |
| `INFRA_ANSWERS` | Koşucuda altyapı vakalarının doğru cevap alanları (`SCENARIOS`'un eşi): (hata, hedef) → `propagation_path`, `categories`; kaynağı INCIDENT_CATALOG altyapı tablosu |
| `quote-gateway`, `services/quote-gateway/`, `aiops-quote-gateway:1`, `task/quote-gateway` | Kendi Python servisimiz (shipping → quote-gateway → quote) / klasörü / yerel deneme imajı (koşular GHCR'daki `ghcr.io/erenbezek/aiops-quote-gateway`'i çeker) / dalı |
| `services/quote-gateway/app.py`, `gateway.py`, `requirements.txt`, `Dockerfile` | Flask katmanı ve flag okuma / iş mantığı (`QuoteCache`) / sabit bağımlılıklar / imaj tarifi |
| `QuoteCache` | quote-gateway'in kısa ömürlü (1 sn), sınırlı (64 kayıt) önbelleği; sızıntı kipinde istek başına blok saklar, bırakmaz |
| `quoteGatewayMisroute`, `quoteGatewaySlowdown`, `quoteGatewayMemoryLeak` | quote-gateway flag'leri: yanlış yapılandırma (misconfig) / gecikme (ms, latency) / bellek sızıntısı (KB/istek, resource) |
| `deploy/otel-demo/flagd-extras.json` | Bizim flag'lerimiz; `otel_demo.sh` upstream flag dosyasıyla birleştirir (aynı ad iki dosyada da varsa hata) |
| `GATEWAY_IMAGE`, `QUOTE_GATEWAY_PORT` | Koşucuda quote-gateway imajı, GHCR digest'iyle (yoksa koşu başlamaz, `docker pull` komutu yazılır) / quote-gateway'in dinlediği port (8090) |
| `tests/test_quote_gateway.py` | quote-gateway iş mantığı, flag birleştirme ve koşucunun yeni flag'leri açıp kapatması |
| `incident_lists/quote_gateway.json` | quote-gateway kalibrasyon listesi (7 vaka) |
| `incident_lists/quote_gateway_leak.json` | quote-gateway kısa koşu listesi (1024 KB sızıntı, swap kapalı; 1 vaka) |
| `merge_flag_files`, `FLAGD_EXTRAS` | `otel_demo.sh`: upstream flag dosyasıyla `flagd-extras.json`'ı birleştiren fonksiyon / bizim flag dosyamızın yolu |
| `parse_items`, `CACHE_TTL_S`, `CACHE_MAX_ENTRIES`, `retained_bytes` | `gateway.py`: `numberOfItems` kontrolü / önbellek ömrü (1 sn) / kayıt sınırı (64) / sızıntıda tutulan toplam bayt |
| `UPSTREAM`, `ALT_UPSTREAM`, `TIMEOUT_S`, `PORT` | `app.py`: quote adresi (`QUOTE_ADDR`) / yanlış yapılandırmanın hedefi (`http://quote-svc:8090`) / iletim zaman aşımı (10 sn) / dinlenen port |
| `task/systemd-unit`, `deploy/systemd/aiops-incidents@.service`, `aiops-incidents@<ad>` | systemd kartının dalı / gece koşusu birim şablonu / örnek: `<ad>` = `incident_lists/<ad>.json` |
| `Stopped`, `signals_deferred` | Koşucu: SIGTERM/SIGINT ile durdurulan vakanın hatası / korunan bölüm (içeride gelen sinyal not edilir, çıkışta `Stopped`) |
| `inhibited()`, `INHIBIT_WHO`, `INHIBIT_WHY` | Koşucu: bizim systemd uyku engelimiz listede mi / engelin kimliği / kabul edilen neden metinleri |
| `leftovers()`, `leftovers` (koruma alanı), `DEMO_PROJECT` | Koşucu: önceki koşudan kalan demo (`otel-demo` projesi) ya da `aiops-netem` konteynerleri; varsa koşu başlamaz / demonun compose proje adı |
| `session_pids` | Koşucu: bir oturumdaki yaşayan süreçler (`/proc`); uyku engeli zincirini çıkışta kapatmak için |
| `incident_lists/systemd_stop.json` | systemd kartı canlı kontrol listesi (containerPause cart, 1 vaka) |
