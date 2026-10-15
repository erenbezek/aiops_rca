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
| `positive_control` | Pozitif kontrol: dedektörün bilinen bir sızıntıyı gerçek veride gerçekten bulduğunu gösteren kontrol (süzme kapalı) |
| `model_view` | Model görünümü: bir incident için yöntemlere verilen veri; etiketler ve cevabı ele veren adlar içermez |
| `task/<konu>` | Görev kartı dalı; her kart bir dal ve bir PR (ör. `task/line-endings`) |
