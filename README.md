# aiops_rca

**In English:** This is a root cause analysis (RCA) for microservices. Faults are injected into the OpenTelemetry Demo plus one of our own services, each incident is recorded as a snapshot of logs, metrics and traces, and RCA methods are scored on the same incidents against rule and BARO baselines. Project 1 tests whether a small local model, helped by statistical narrowing, can find the root cause when logs may not leave the machine; Project 2 tests a tool-using agent on the same incidents, both from the recorded files and from a live monitoring stack.

## Amaç

Mikroservis ortamına (OpenTelemetry Demo ve kendi Python servisimiz) bilerek hata enjekte edip kök nedeni bulan yöntemleri aynı vakalar üzerinde ölçen bir altyapı. Üzerinde iki proje var: **Proje 1**, CPU'da çalışan küçük yerel model ile istatistiksel daraltmanın birlikte (hibrit) kullanımı, kanıt ve yol doğrulaması ve "emin değilim" diyebilme (kalibrasyon); **Proje 2**, sabit sorgu araçlarıyla çalışan tek bir ajan. Bütün yöntemler aynı vakalarda kural ve BARO baseline'larına karşı ölçülür. Soru: logların dışarı çıkamadığı bir ortamda küçük yerel model, doğru desteklenirse kök neden analizinde ne kadar iş görür?

## Durum

- **Proje 1 bitti:** sonuç tablosu, dev hata analizi ve sınırlamalar `results/` altında.
- **Proje 2 bitti:** sabit sorgu araçlarıyla çalışan tek ajan, dosyadan ve canlı izleme sisteminden koşuldu; test raporu, iki test hata analizi ve sınırlamalar `results/` altında (aşağıda).
- **Canlı demo bitti:** çalışan yığına hata uygulanır, ajan canlı izleme sisteminden kanıtlı bir rapor ve sonraki adım önerisi verir; komut ve web arayüzü (aşağıda).
- **Snapshot seti henüz yayınlanmadı.** Vakaların ham kayıtları repo dışında; proje sonunda GitHub Releases'te sıkıştırılmış olarak yayınlanacak (tekrarlanabilirlik seviye 2). O zamana kadar deneyi baştan koşmak mümkün değil; aşağıdaki komutlar repodaki kayıtlardan sonuçları yeniden üretir.

## Akış

Tam ve güncel hali [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)'de; buradaki kopya zamanla ondan ayrışabilir. Makineye özel yollar genel adlarla yazıldı.

```mermaid
flowchart LR
    subgraph ortam["Demo ortamı (Docker Compose)"]
        otel["OpenTelemetry Demo"]
        own["Kendi Python servisim<br/>quote-gateway (shipping → quote-gateway → quote)"]
        col["OTel collector<br/>(sızıntı süzmesi: filter/sim_world,<br/>transform/scrub)"]
    end

    inj["Hata enjeksiyonu<br/>(flagd API; altyapı: tc netem (aiops-netem),<br/>docker update --cpus, stop, pause)"]
    raw[("OTLP dosyası (süzülmüş)<br/>repo dışı telemetri klasörü")]
    rawu[("süzülmemiş kopya<br/>telemetry/raw/ (sadece --raw)")]
    mon[("Kalıcı izleme sistemi<br/>Prometheus, Jaeger, OpenSearch<br/>isimli volume, 7 gün, ≤ 40 GB")]
    cut["Snapshot kesici<br/>scenario_runner.py incidents<br/>(dosyadan, vaka penceresi;<br/>systemd birimi aiops-incidents@liste)"]
    snap[("snapshot'lar<br/>repo dışı snapshot klasörü<br/>— git dışı, ≤ 30 GB")]
    labels[("etiketler<br/>incidents/inc-….json — repoda")]
    ichk["tools/incident_checks.py<br/>(belirti, olay, taban sağlık;<br/>ölçüler src/aiops_rca/signals.py)"]
    fix[("CI alt kümesi<br/>tests/fixtures/snapshots/")]
    view["model_view<br/>(= snapshot klasörü: süzülmüş<br/>pencere + window.json; etiketler hariç)"]
    leak["Sızıntı testi<br/>src/aiops_rca/leakage.py"]
    ci["CI (GitHub Actions)<br/>.github/workflows/ci.yml"]
    img["İmajlar (GitHub Actions)<br/>.github/workflows/images.yml"]
    ghcr[("GHCR<br/>aiops-quote-gateway, aiops-netem<br/>— digest'le sabit")]

    base["baseline<br/>(kural: methods/rule.py;<br/>BARO: methods/baro.py;<br/>daraltma referansı: methods/narrowing.py)"]
    nar["candidate_narrowing<br/>(narrowing.py, ilk 5)"]
    inp["Girdi seviyeleri (inputs.py)<br/>ham / özet / daraltma, ≤ 5000 token;<br/>takma ad: alias.py"]
    llm["LLM (methods/llm.py, llm_client.py)<br/>small_local_model / large_api_model;<br/>onaylı istem, tam mesaj ≤ 6000"]
    agent["Proje 2 ajanı"]
    cache[("llm_cache/ — git dışı")]
    evr[("eval_responses/")]
    ev["Değerlendirme (evaluate score, scoring.py)<br/>top-1/3, kanıt, kalibrasyon"]
    tab["Sonuç tablosu<br/>(results.py → results/p1_table.md, .json;<br/>koşu listesi results/p1_runs.json)"]

    inj --> ortam
    otel --> col
    own --> col
    col --> raw
    col -.->|positive_control| rawu
    col --> mon
    raw --> cut --> snap
    snap --> ichk --> labels
    cut --> labels
    snap -.-> fix
    snap --> view
    view -->|"0 bulgu şartı"| leak
    ci -->|"pytest, ekstrasız kurulum"| leak
    fix -.->|baseline regresyonu| ci
    img -->|"main'de gönderim"| ghcr
    ghcr -->|docker pull, digest| ortam
    ghcr -->|netem imajı| inj
    view --> base
    view --> nar --> inp
    view -->|"WARN+ log, hata span'i, özet"| inp
    inp --> llm
    view --> fstore["FileStore (store_file.py)<br/>dosya okuyucusu"]
    fstore --> qry["Sorgu katmanı (query.py)<br/>list_services, metric_series, search_spans,<br/>get_trace, search_logs, service_dependencies;<br/>ortak hesap, METRIC_NAMES"]
    qry -->|"araçlar (P2b)"| agent
    llm -->|"evaluate run --method llm<br/>(duman, denemeler)"| cache
    llm -->|"evaluate run --method llm"| evr
    agent --> evr
    base -->|"evaluate run"| evr
    evr --> ev
    ev --> tab

    smoke["tools/api_smoke_test.py"] -.->|model seçimi| llm
    bench["tools/local_model_bench.sh<br/>+ bench_summary.py"] -.->|hız ölçümü, model boyutu| llm
    demo_sh["tools/otel_demo.sh<br/>fetch / up / down / config"] -->|"repo dışı klon 3.1.0,<br/>minimal mod"| otel
    extras["deploy/otel-demo/compose.extras.yaml<br/>(log 5 MB × 2, 3 port 127.0.0.1)"] -->|son compose katmanı| otel
    runner["tools/scenario_runner.py<br/>(10 dk normal + 10 dk flag, korumalar)"] -->|"flag aç/kapat (flagd-ui API)"| otel
    runner -->|"incidents (V1): kesim"| cut
    runner -->|"pencere kopyası (raw + filtered)"| c2runs[("repo dışı C2 koşu klasörü<br/>repo dışı, cevap içerir")]
    c2runs --> meas["tools/c2_measure.py<br/>(sızıntı, belirti, collector)"]
    meas -->|positive_control| leak
    rtest["tools/test_collector_rules.sh<br/>+ tests/fixtures/collector_rules/"] -.->|"kural testi (geçici collector, Docker)"| col
    c2runs -->|"window/filtered/<br/>(REPLAY_WINDOW)"| replay["tools/storage_check.py replay<br/>+ deploy/replay/ (otel-replay;<br/>collector: yalnız dosya alıcısı)"]
    replay -->|"orijinal zaman damgası,<br/>zaman sırasıyla"| rmon[("Yeniden oynatma hedefi<br/>Jaeger, Prometheus, OpenSearch<br/>otel-replay_* volume'leri, boş başlar")]
    snap --> rcase["tools/storage_check.py replay-case<br/>(vaka başına boş yığın, D3 şartları,<br/>örnek reddi 0, sonda down -v)"]
    rcase -->|"REPLAY_WINDOW = snapshot"| rmon
    rmon --> lstore["LiveStore (store_live.py)<br/>canlı okuyucu; Jaeger dilimleme,<br/>undo_jaeger_error_tag"]
    lstore --> qry
    qcmp["tools/query_compare.py<br/>run / report (LLM'siz)"] -->|"aynı çağrılar iki okuyucuda"| qry
    qcmp --> rcase
    qcmp -->|"fark türü kodla"| p2arep[("results/p2a_compare.md / .json")]
```

## Proje 1 sonuçları (test seti)

Kaynak: [`results/p1_table.md`](results/p1_table.md) (komutla üretilir; ayrıntı bölümleri, Brier, kanıt, süre ve token oradadır). Sayılar doğru kök nedeni ilk 1'de / ilk 3'te bulan vaka sayısı. "Ham", "özet" ve "daraltma" modele verilen girdi seviyeleri; "daraltma referansı" modelsiz daraltma sırası.

| Yöntem | top-1 test | top-3 test | top-3 dev | Dev–test okuması |
|---|---|---|---|---|
| kural | 6/18 | 11/18 | 15/18 | ayırt edilemedi |
| BARO | 6/18 | 8/18 | 10/18 | ayırt edilemedi |
| daraltma referansı | 11/18 | 13/18 | 17/18 | ayırt edilemedi |
| qwen3.5-4b ham | 6/18 | 7/18 | 6/18 | ayırt edilemedi |
| qwen3.5-4b özet | 7/18 | 11/18 | 15/18 | ayırt edilemedi |
| qwen3.5-4b daraltma | 9/18 | 14/18 | 16/18 | ayırt edilemedi |
| gpt-oss-120b ham | 3/18 | 4/18 | 7/18 | ayırt edilemedi |
| gpt-oss-120b özet | 10/18 | 13/18 | 15/18 | ayırt edilemedi |
| gpt-oss-120b daraltma | 12/18 | 15/18 | 17/18 | ayırt edilemedi |
| gemini-3.5-flash-lite ham | 6/18 | 6/18 | 7/18 | ayırt edilemedi |
| gemini-3.5-flash-lite özet | 10/18 | 13/18 | 16/18 | ayırt edilemedi |
| gemini-3.5-flash-lite daraltma | 15/18 | 16/18 | 18/18 | ayırt edilemedi |

Okurken:

- "Ayırt edilemedi" "aynı" demek değil. Setler küçük olduğu için dev ile test arasında yalnız büyük farklar görülebilir (okuma kuralı tablonun altında).
- Modeller ve yöntemler arasındaki karşılaştırma betimseldir; önceden yazılmış bir karşılaştırma kuralı yok.
- Bilgi amaçlı ek model satırları ve ayrıntılar tabloda.
- Sınırlamalar: [`results/p1_limitations.md`](results/p1_limitations.md).

## Proje 2 sonuçları (test seti)

Kaynak: [`results/p2d_test.md`](results/p2d_test.md) (komutla üretilir; koşular, çağrı düzeyi karşılaştırma, Brier, kanıt, süre ve token oradadır). Sayılar doğru kök nedeni ilk 1'de / ilk 3'te bulan vaka sayısı. Ajan her vakada en çok 8 araç çağrısıyla izleri, metrikleri ve logları sorgular; "dosya" kayıtlı snapshot'tan, "canlı" vakanın yeniden oynatıldığı izleme sisteminden (Prometheus, Jaeger, OpenSearch) okur. Resmî satır Gemini dosya 1. koşu; 2. koşu gürültü tabanı için.

| Ajan | top-1 test | top-3 test | top-1 dev | top-3 dev |
|---|---|---|---|---|
| Gemini, dosya, 1. koşu (resmî) | 10/18 | 14/18 | 9/18 | 14/18 |
| Gemini, dosya, 2. koşu | 10/18 | 15/18 | 9/18 | 15/18 |
| Gemini, canlı | 5/18 | 12/18 | 9/18 | 14/18 |
| qwen3.5-4b, dosya | 4/18 | 7/18 | 4/18 | 9/18 |
| qwen3.5-4b, canlı | 4/18 | 7/18 | 4/18 | 9/18 |

Okumalar (koşudan önce yazıldı):

- **Dosya ↔ canlı, top-3:** Gemini 14 ↔ 12, 4B 7 ↔ 7 → ayırt edilemedi. Canlı araç çağrılarının hepsi dosyadakiyle aynı çıktıyı verdi (Gemini 123, 4B 143).
- **Ajan ↔ P1:** Gemini ajan ↔ ham, top-3: 14 ↔ 6, p = 0.0215 → fark, ajan lehine. Gemini ajan ↔ daraltma, top-1: 10 ↔ 15; 4B ajan ↔ ham, top-3: 7 ↔ 7; 4B ajan ↔ daraltma, top-1: 4 ↔ 9 → üçü ayırt edilemedi.
- **Dev–test** (iki resmî dosya satırı, top-3): Gemini 14 → 14, 4B 9 → 7 → ayırt edilemedi.

Okurken:

- "Ayırt edilemedi" "aynı" demek değil; 18 vakada yalnız büyük farklar görülebilir. Dört ajan ↔ P1 hücresinde çoklu karşılaştırma düzeltmesi yok.
- Gemini aynı ayarla iki koşuda 3 / 18 vakada farklı top-3 sonucu verdi; canlı top-1'in düşüklüğü (5/18) test edilmedi.
- 4B testte 18 vakanın 16'sında adım sınırına takıldı.
- Hata analizleri: [`results/p2d_error_summary.md`](results/p2d_error_summary.md) (ajan ıskaları), [`results/p1_test_error_summary.md`](results/p1_test_error_summary.md) (P1 test başarısızları). Sınırlamalar: [`results/p2_limitations.md`](results/p2_limitations.md).

## Canlı demo

`tools/live_demo.py` çalışan demo yığınında bir hata seçer ve uygular. 10 dk sonra Proje 2'nin donmuş ajanı (Gemini ya da yerel qwen3.5-4b) Prometheus, Jaeger ve OpenSearch'ten canlı okur. Sonra hata geri alınır ve doğrulanır, ajanın gördüğü çıktılarda sızıntı taranır. Rapor: üç aday ve kanıt yolları, araç çağrıları, sonraki adım önerisi (1. adayın canlı verisinden sabit kural tablosuyla; ajan uygulamaz), Grafana panosunun pencereye ayarlı bağlantısı ve doğru cevap (ajandan sonra). `serve` aynı akışı tek sayfalık bir web arayüzünden başlatır (yalnız `127.0.0.1`, aynı anda tek demo). Demo gösterimdir, ölçüm değil; isabeti sonuç tablolarına girmez.

Kabul koşusu (önceden yazılı ölçütler; 8 koşu): bütün koşularda sonuç, geri alma, rapor alanları, sızıntı 0 ve beklenmeyen yeniden başlama 0 tuttu; arayüzden uçtan uca bir demo; 4B'de bellek yetti. Panel ölçütü (panoda hatanın görünmesi) hatanın kendi belirtisiyle tuttu:

| Demo | Model | Panelde görülen |
|---|---|---|
| `containerStop:recommendation` (iki koşu) | Gemini | recommendation istek hızı ~0,8 → ~0,15 /sn, frontend hata oranı 0 → ~0,10 |
| `containerPause:cart` | Gemini | cart istek hızı 1,42 → 0,20 /sn, frontend p95 35 → 2556 ms |
| `networkDelay:quote` | Gemini | quote-gateway p95 7,6 → 90,5 ms (gecikme çağıranda görünür) |
| `containerStop:recommendation` | qwen3.5-4b | recommendation istek hızı 0,85 → 0,15 /sn |
| `paymentFailure_10pct` (üç koşu) | Gemini | eşik üstünde görünmedi (aşağıda) |

Sınırlar:

1. Panodaki p95 (span metriklerinin histogramından) raporun p95'inden (izlerden, pencerenin iki yarısı) farklı olabilir. `containerPause:cart`'ta duraklatmada bekleyen istekler izlerde ~301 sn, panoda 2,6 sn.
2. Durdurma, ajan çalışıyorsa en çok ajanın süresi kadar bekler; sonra hata geri alınır.
3. `serve` açık kaldıkça makinenin uyku kilitleri tutulur.
4. `--live` ile bile bir hata panelde ~35 sn'ye kadar gecikir (ölçülen en çok 33,9 sn); yeni bir hata serisi bir gönderim geç sayılır. Ajanın başlamasından önceki son ~35 sn'deki hatalar panel penceresine girmeyebilir.
5. Düşük hacimli hatalar panelde görünmeyebilir. `paymentFailure_10pct` üç denemede panelde eşik üstünde görünmedi: ilkinde gecikme yüzünden hata pencereye girmedi; canlı demo katmanından (15 sn) sonra hata görünür oldu ama oran 0,044 < 0,05; son denemede pencerede hiç hata yoktu ve panel ölçütü bellek gürültüsüyle biçimsel olarak tuttu. Düşük hacimli (~30 istek / 10 dk) %10 hata bu demo süresinde güvenilir bir belirti üretmiyor.
6. Konteyner sayısı 23 değilse (collector'ın açılışta bir konteyneri kaçırması) `run` collector'ı bir kez yeniden başlatır; demo ~10 dk geç başlar.

## Tekrar üretme

Kurulum CI'daki gibi (`pyproject.toml`'daki Python sürümü):

```
python -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
python -m aiops_rca.results --check
python -m aiops_rca.error_analysis summary --check
python -m aiops_rca.error_analysis summary --set test --check
python tools/agent_report.py --report p2d --check
python tools/agent_error_analysis.py summary --set test --check
python -m pytest
```

`--check` komutları sonuç tablolarını ve hata analizi özetlerini repodaki kayıtlardan yeniden üretip repodakilerle karşılaştırır; CI hepsini bayt aynı üretir. Snapshot, API anahtarı ve ağ gerekmez.

Canlı demo, demo yığınını canlı demo katmanıyla ister (span metrikleri 15 sn'de bir; vaka hattının `up`'ı bu katmanı yüklemez, katmansız açılmış yığında demo korumada durur):

```
python -m pip install -e ".[dev,demo]"
tools/otel_demo.sh up --live          # sonra en az 10 dk normal dönem
python tools/live_demo.py serve       # ya da: python tools/live_demo.py run --fault containerStop --target recommendation
tools/otel_demo.sh down
```

## Repo haritası

| Klasör | İçerik |
|---|---|
| `src/aiops_rca/` | Paket: vaka erişimi, sinyaller, yöntemler (kural, BARO, LLM, daraltma), puanlama, sonuç tablosu, hata analizi, sorgu katmanı |
| `tools/` | Betikler: vaka üretim hattı, ölçümler, yeniden oynatma, dosya ↔ canlı karşılaştırması, canlı demo ve arayüzü |
| `tests/` | Testler ve CI'daki küçük sabit örnekler |
| `incidents/` | Vaka etiketleri (doğru cevap ve set) |
| `incident_lists/` | Gece koşularının vaka listeleri |
| `eval_responses/` | Resmî koşuların kayıtları |
| `results/` | Sonuç tabloları, hata analizleri, sınırlamalar, P2 raporları |
| `deploy/` | Demo katmanları (collector süzmesi, compose, canlı demo katmanı), Grafana panosu, yeniden oynatma yığını, systemd birimi, yardımcı imaj |
| `services/` | Kendi servisimiz (quote-gateway) |
| `docs/` | Proje hafızası (aşağıda) |
| `.github/workflows/` | CI: testler; imajların derlenmesi ve GHCR'a gönderimi |

## Belgeler

- [`docs/PROJECT.md`](docs/PROJECT.md): ne, neden, bitti ölçütleri, şu an
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): akış şeması ve dosya tablosu
- [`docs/DECISIONS.md`](docs/DECISIONS.md): kararlar ve gerekçeleri
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md): adlar
- [`docs/HANDOFF.md`](docs/HANDOFF.md): oturumlar arası kayıtlar
- [`docs/INCIDENT_CATALOG.md`](docs/INCIDENT_CATALOG.md): hata kataloğu
- [`docs/OTEL_DEMO.md`](docs/OTEL_DEMO.md): OpenTelemetry Demo kurulumu ve veri akışı
- [`docs/LOCAL_MODEL_BENCH.md`](docs/LOCAL_MODEL_BENCH.md): yerel model hız ölçümü
