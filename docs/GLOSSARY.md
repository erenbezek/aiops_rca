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
