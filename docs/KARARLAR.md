# KARARLAR

| Tarih | Karar | Neden |
|---|---|---|
| 2026-10-13 | İki proje sırayla yapılır (önce lokal, sonra ajan), ortak altyapı üzerinde | Paralel yapmak süreyi böler; problem tarafı (ortam, hata, etiket, ölçüm) çözücüden bağımsız |
| 2026-10-13 | Snapshot'lar ham veri saklar (log, metrik, trace); her proje kendi yoluyla okur | Snapshot bir projeye göre şekillenirse diğeri zorlama olur (ör. ajan keşif yapamaz) |
| 2026-10-13 | Değerlendirme offline, snapshot'lar üzerinde | Tekrarlanabilir, ucuz, adil karşılaştırma |
| 2026-10-13 | Proje 1: küçük lokal model + hibrit daraltma + kanıt/yol doğrulaması + kalibrasyon | API yok, GPU yok; "loglar dışarı çıkamaz" senaryosu gerçek bir endüstri sorusu |
| 2026-10-13 | Karşılaştırma tasarımı: tek pipeline, model ve daraltma birer ayar | Aynı anda iki değişken değişirse fark nereden geldi bilinmez |
| 2026-10-13 | Büyük API modeli satırları iki modelle koşulur, ayarlar birebir aynı; vakalar modeller arasında bölünmez | Bulgunun modele özgü olup olmadığını gösterir (replikasyon) |
| 2026-10-13 | Ajanın her çağrısı ~6K token sınırında tasarlanır | Groq dakikada 8K token; iki modelde ayarlar aynı kalmalı |
| 2026-10-13 | "Güçlü model" yerine "büyük API modeli" ifadesi | "Güçlü" sonucu önceden söylüyor gibi; olgusal tarif önyargıyı azaltır |
| 2026-10-13 | API adayları: Groq gpt-oss-120b, Gemini 3.5 Flash Lite | Duman testi (2 koşu): ikisi de tool calling 6/6, ~6K girdi geçti; kart gerekmez |
| 2026-10-13 | Elenenler: Gemini Flash 3.x (günde 20 istek), Gemma 4 31B (12 native isteğin 9'u sunucu hatası, ~1 dk gecikme) | Ajan için kullanılamaz kota / erişilebilirlik |
| 2026-10-13 | Birden fazla hesapla kota aşılmaz; resmi koşular tek sağlayıcı + tek model sürümüyle | Kullanım şartları; adillik |
| 2026-10-13 | Model kimliği sabit yazılır (`-latest` takma adı kullanılmaz); her koşuda model, sağlayıcı, temperature, tarih kaydedilir | Ücretsiz katman modelleri proje ortasında değişebilir |
| 2026-10-13 | Demo uygulama: OpenTelemetry Demo + kendi Python servisim | Hazır 16 hata senaryosu, hazır telemetri, ~3 GB minimal mod, OpenRCA 2.0 ile ortak sistem; kendi servis DevOps deneyimini ve ezberlenemeyen vakaları sağlar |
| 2026-10-13 | flagd telemetrisi snapshot'a girmez | Ajan açılan flag'i okuyup cevabı kopyalayabilir |
| 2026-10-13 | Baseline: kural + BARO (RCAEval) | LLM'in gerçekten katkı yapıp yapmadığını inandırıcı ölçmek için güçlü LLM'siz referans |
| 2026-10-13 | Proje 1'e yol doğrulaması eklenir (kök neden → belirti yolu bağımlılık grafiğinde var mı) | OpenRCA 2.0: doğru servisi bulup yayılımı gösteremeyen "kanıtsız teşhis" ~14,5 puan |
| 2026-10-13 | CI/CD kapsamda (GitHub Actions + GHCR) | ~1 gün; değerlendirme kodunu regresyona karşı korur |
| 2026-10-13 | Kubernetes şartlı ek, yeni makine gelince karar | İki ortam iki kat iş; 8 GB'ta pratik değil |
| 2026-10-13 | Web arayüzü şartlı ek, ana tablo dolduktan sonra | Demoya değer katar, ölçüme katmaz; cilalama zaman yer |
| 2026-10-13 | Bulut kapsam dışı, staj sonrası ayrı proje | Zorunlu değil; kart/koşul belirsizliği; ayrı öğrenme eğrisi |
| 2026-10-13 | HolmesGPT geri planda | Ana sorular için gerekli değil; ortamımızda çalışıp çalışmayacağı belirsiz |
| 2026-10-13 | Otomatik düzeltme yok; ajan sadece sonraki adımı önerir | Riskli, ölçmesi zor, kapsamı ikiye katlar |
| 2026-10-13 | Kod ve klasör isimleri İngilizce, `docs/` Türkçe | Portföy ve araç ekosistemi uyumu |
| 2026-10-13 | Klasörler ihtiyaç doğdukça, her biri onayla açılır | Boş iskeletin faydası yok |
| 2026-10-13 | Oturumlar ayrı: planlama, uygulama, test | proje-akisi skill'i |
| 2026-10-13 | Bitti ölçütlerine eklendi: sızıntı kontrolü, vaka çeşitliliği, tekrarlanabilirlik, hata analizi | Sonuçların geçerliliği (sızıntı), problemin kolay kalmaması (çeşitlilik), API modelleri değişebilir (tekrarlanabilirlik), rapor için başarısızlık analizi |
| 2026-10-13 | Repoya girenler: resmî değerlendirme koşularının LLM cevapları (geliştirme + test vakaları), etiketler, snapshot meta verisi, baseline çıktıları, CI için 3-5 incident'lık sabit snapshot alt kümesi. Girmeyenler: `llm_cache/` (geliştirme denemeleri), tam snapshot seti (lokalde; proje sonunda GitHub Releases) | Tablo her yerde yeniden üretilebilsin (seviye 1); snapshot'lar git için fazla büyük; geliştirme cevapları gürültü |
| 2026-10-13 | Sonuç tablosu geliştirme ve test setini yan yana gösterir | Aradaki fark geliştirme vakalarına aşırı uyumu gösterir |
| 2026-10-13 | CI snapshot alt kümesi ayrı klasörde (`tests/fixtures/snapshots/`), `.gitignore` istisnası değil | `snapshots/` kuralı klasörü tümden dışlar, `!` ile geri alınamaz; istisna kuralı kırılgan, bozulursa CI verisi sessizce düşer |
| 2026-10-13 | Duman testinde yorum ve ekran çıktısı Türkçe kaldı, sadece tanımlayıcılar İngilizce | Taşıma "aynı tablo formatı" ölçütünü bozmamalı |
| 2026-10-14 | `.gitattributes`: tüm metin dosyaları LF, sadece `.bat`/`.cmd` CRLF; enjeksiyon betiklerinden önce eklenir | `core.autocrlf` açık; Windows klasöründen Docker'a giden `.sh` ve shebang'li `.py` dosyaları CRLF ile container'da bozulur. Şimdi eklemek yeniden normalize etmeyi gereksiz kılar |
| 2026-10-14 | `.editorconfig` eklenir (LF, UTF-8, sonda boş satır; `.bat`/`.cmd` CRLF); girinti kuralı yok | `.gitattributes` sadece commit/checkout'u kapsar; editörde oluşturulup commit edilmeden Docker'a bağlanan dosya boşluğunu kapatır |
| 2026-10-14 | VS Code için eklenti kurulmaz; `.vscode/settings.json` içinde `"files.eol": "\n"` | Yeni araç gerektirmez, VS Code yerleşik ayarı; `.editorconfig` diğer editörler ve GitHub için kalır |
