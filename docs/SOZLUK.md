# SÖZLÜK

Sadece Eren'in onayladığı isimler.

| İsim | Anlamı |
|---|---|
| `aiops_rca` | Proje kök klasörü ve repo adı |
| küçük lokal model | CPU'da, makinede çalışan küçük dil modeli (Proje 1) |
| büyük API modeli | Ücretsiz API üzerinden kullanılan büyük model (Groq gpt-oss-120b, Gemini 3.5 Flash Lite) |
| `incident` | Vaka: tek bir hata enjeksiyonu ve onun kaydı (kodda `incident_id`, `incidents/`) |
| `snapshot` | Bir incident'ın ham log/metrik/trace kaydı + doğru cevap (ground truth) |
| `candidate_narrowing` | Hibrit daraltma: istatistiğin aday servisleri azaltıp sadece onları LLM'e vermesi (Proje 1) |
| `baseline` | LLM'siz karşılaştırma yöntemleri (kural, BARO) |
| `tools/` | Hattın parçası olmayan yardımcı ve tek seferlik betikler |
| `api_smoke_test` | API duman testi: aday modellerin teknik uygunluk kontrolü (`tools/api_smoke_test.py`) |
| `llm_cache/` | Geliştirme denemelerinin LLM cevapları; git dışı |
| `eval_responses/` | Resmî değerlendirme koşusunun LLM cevapları; repoda tutulur |
| `tests/fixtures/snapshots/` | CI için 3-5 incident'lık sabit snapshot alt kümesi; repoda tutulur |
