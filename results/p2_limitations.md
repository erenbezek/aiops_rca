# P2 sınırlamaları

P2 sonuçlarının ([`p2d_test.md`](p2d_test.md), [`p2d_error_summary.md`](p2d_error_summary.md), [`p1_test_error_summary.md`](p1_test_error_summary.md)) sınırlamaları. Elle yazılır; maddeler proje kayıtlarından toplanmıştır, yeni yorum içermez. Her maddede: ne, sayı, okumayı değiştirip değiştirmediği, kaynak (`docs/HANDOFF.md` / `docs/DECISIONS.md` tarihi). Test vakası kimliği yoktur; yalnız toplam. P1'in sınırlamaları ayrıca [`p1_limitations.md`](p1_limitations.md).

## 1. Veri, sağlayıcı ve modeller

- **Ücretsiz katman.** Ücretsiz katmanda girdiler sağlayıcı tarafından kullanılabilir; veri sentetik demo telemetrisi; anahtar ya da kişisel veri girmez. Google ücretsiz katmanın sınırlarını değiştirebilir; aynı koşu ileride aynı kotayla tekrarlanamayabilir. Okumayı değiştirmez. Kaynak: DECISIONS 2026-11-09, HANDOFF 2026-11-12 (planlama hatırlatması).
- **Takma ad yok.** Ajan gerçek adlarla koştu. P1'in takma ad ölçümünde (dev) 15 hücrenin 14'ünde ezber işareti görülmedi, biri belirsiz; test takma adla koşulmadı. Ajan, takma adın zaten gizlemeyeceği ayrıntıları (span adlarındaki gRPC yöntemleri, ayırt edici log ifadeleri) P1'den daha çok görür. Ezber olasılığı açık kalır (`p1_limitations.md` §1). Kaynak: DECISIONS 2026-11-12 (takma ad).
- **Standart araç çağırma özelliği kullanılmadı.** Araçlar sağlayıcının araç çağırma özelliğiyle değil, istem metnindeki tanımlar ve katı JSON eylem şemasıyla çağrılır. Sonuç bu seçime bağlı; okumayı değiştirmez. Kaynak: DECISIONS 2026-11-12 (JSON eylem şeması).
- **İki model.** Ajan yalnız Gemini 3.5 Flash-Lite (API) ve Qwen3.5-4B (yerel) ile koşuldu; ajan etkisi modele özgü olabilir, başka modellere genellenmez. Kaynak: HANDOFF 2026-11-16 (P2d kartı).
- **Gemini belirlenimci değil.** Aynı kod ve sıcaklık 0 ile iki dosya koşusunda top-3 sonucu ayrışan vaka 3 / 18; dosya 1 ↔ canlı 6 / 18 (gürültü tabanı, betimsel). Tek koşunun sonucu bu kadar oynayabilir; okuma kuralları resmî koşuya (dosya, 1. koşu) uygulanır. Kaynak: `p2d_test.md` (Dosya ↔ canlı, (3)), HANDOFF 2026-11-17 (5. madde).

## 2. Örneklem ve okumalar

- **n = 18, tek demo ortamı.** Yalnız büyük farklar görülebilir. Dev–test Fisher'ında "fark" için Gemini'de test ≤ 7 (dev 14), 4B'de test ≤ 2 ya da ≥ 16 (dev 9) gerekir; ikisi de "ayırt edilemedi" (Gemini 14 → 14, p = 1,0; 4B 9 → 7, p = 0,738). "Ayırt edilemedi" "aynı" demek değildir. Kaynak: DECISIONS 2026-11-16 (dev–test okuması), `p2d_test.md` (Dev–test).
- **Çoklu karşılaştırma düzeltmesi yok.** Ajan ↔ P1'de dört hücre; tek "fark" (Gemini ajan ↔ ham top-3, 14 / 6, p = 0,0215) düzeltmesiz. Kaynak: DECISIONS 2026-11-14, `p2d_test.md` (Ajan ↔ P1).
- **Dev–test farkı aşırı uyumla dağılım farkını ayıramaz** (testte 5 görülmemiş birim). Kaynak: DECISIONS 2026-11-16.
- **Pilotta bir tasarım turu yapıldı (P2c-0), dev'de ayar yok.** Tasarım pilot vakalarla ayarlandı ve dondu; dev ve test donmuş tasarımla koşuldu. Kaynak: DECISIONS 2026-11-14 (tasarım dondu).
- **Canlı top-1 düşük, test edilmedi.** Gemini canlı top-1 5 / 18, dosyada 10 / 18. Okuma kuralı top-3'e bakıyor (dosya 14 / 18, canlı 12 / 18, p = 0,6875, ayırt edilemedi); top-1 farkı için test yok, kural sonuçtan sonra değişmez. Kaynak: HANDOFF 2026-11-17 (planlama, 5. madde kontrolü).

## 3. Canlı ve dosya koşuları

- **Canlı taraf yeniden oynatma.** Canlı koşu, kaydedilmiş vakayı gerçek telemetri yığınına yeniden oynatıp sorgular; arıza o anda üretilmez. Oynatma 18 / 18 geçti, her vaka tek deneme. Kaynak: HANDOFF 2026-11-17 (4. madde (iv)).
- **4B canlıda her vakaya boş istem önbelleğiyle başladı,** dosya koşusunda önbellek önceki vakalardan doluydu. Sonuca yansımadı: 18 vakada çıktı aynıyken model ayrıştı 0, baştan sona aynı 18. Kaynak: DECISIONS 2026-11-15, `p2d_test.md` (4B denetimi).
- **Koşular farklı commit'lerde, kod aynı.** Beş koşunun commit'leri farklı (`416044e`, `9562f2e`, `b06f334`, `2a8f4ca`); `764a796`'dan beri `src/`, `tools/`, `tests/` farkı yok, yalnız docs. Kaynak: HANDOFF 2026-11-17 ((iii), (iv) kontrolleri).
- **Çağrı düzeyi: bilinen tür `zero_duration`** (Jaeger sıfır süreyi 1 ns yapıyor) testte 0; açıklanamayan çağrı 0 (Gemini 123 / 123, 4B 143 / 143 aynı). Kaynak: DECISIONS 2026-11-11, 2026-11-12 (P2a fark türleri), `p2d_test.md`.
- **Gemini canlının 78 çağrısı planlama tarafından bağımsız yeniden kurulmadı** (yerel tokenizer sunucusu ister); 45 çağrının dosya karşılığı aynı. Bu 78 çağrı için uygulamanın 123 / 123 sonucuna dayanılır. Kaynak: HANDOFF 2026-11-17 (planlama, 5. madde kontrolü).

## 4. Taşıma ve kota

- **Gemini 503 yeniden denemeleri.** Dosya 1. koşu 24, 2. koşu 20, canlı 32 adet 503; iki koşuda birer istek ancak 4. (son) denemede cevaplandı. Taşıma hatasıyla cevapsız 0, teknik kesinti 0. Okumayı değiştirmez; bir istek daha düşseydi vaka cevapsız sayılacaktı. Kaynak: `p2d_test.md` (Koşular), HANDOFF 2026-11-17.
- **Kota sıfırlanma saati doğrulanmadı** (11:00 yerel varsayımı). Canlı koşu yeni kota gününde 182 deneme yaptı, 429 yok. Kaynak: HANDOFF 2026-11-17.

## 5. 4B

- **Adım sınırı.** Testte 4B'nin 18 vakasının 16'sı adım sınırında bitti (8 araç çağrısı; Gemini resmî koşuda 7, canlıda 9). Turların bir kısmı israf: kesilen tablo yüzünden servis servis sorgu (mesaj sınırı 6.000), aynı çağrının tekrarı (kodla anlamsız tekrar 4B'de 4 / 18 vaka; koşu tablosunda tekrar 10). Kaynak: `p2d_test.md`, `p2d_error_summary.md` §2, HANDOFF 2026-11-18 (6. madde).
- **4B'nin gerekçeleri güvenilmez.** Ajan ıskalarının hata analizinde 4B'de T1 (yorumda uydurma) 14 satırın 9'unda evet, T12 (adım sınırı) 12'sinde. 4B'nin gerekçesi, cevabın neden verildiğini açıklamak için okunmamalı. Kaynak: `p2d_error_summary.md` §1.
- **Şema dışı son cevap** 4B'de 2 / 18 (var olmayan servis adı; aynı aday iki kez). Kaynak: `p2d_test.md`, HANDOFF 2026-11-18 (6. madde).

## 6. Puanlama

- **Ad eşlenmemesi; puanlama katı.** P1 test satırlarında kök ilk 3'te eşlenmemiş bir adla (ör. işlem adı biçimi) geçtiği hâlde ıskalama sayılan satır 7 (1. sırada 3; dev'de 2). Puanlama değişmedi. Kaynak: `p1_test_error_summary.md` §4.
- **Puanlama CI'da yeniden yapılmıyor.** CI raporu ve özetleri kayıtlardaki `scores.json`'dan bayt aynı yeniden üretir; puanlamanın kendisi planlamanın bağımsız yeniden puanlamasıyla doğrulandı (fark 0). Kaynak: HANDOFF 2026-11-17 (planlama, 5. madde kontrolü).
- **Bütçe Qwen tokenizer'ıyla sayılıyor** (her istek ≤ 6.000; en uzun mesaj 5.968). Sağlayıcının sayımıyla birebir değil (P1'de oran 1,03–1,20, `p1_limitations.md` §2). Kaynak: DECISIONS 2026-11-01 (bütçeyi aşan girdi), 2026-11-09 (P2'de çağrı bütçesi).

## 7. Hata analizi

- **Etiketleyen bir LLM; doğrulamada çapa etkisi.** Etiketler uygulama oturumunun (Claude Code); Eren etiketi ve dayanağını görerek doğruladı. Planlama test satırlarını okumadı, yalnız toplamları ve kodla sayılanları denetledi. Kaynak: DECISIONS 2026-11-16 (P2d test hata analizi).
- **İki analizde de 1. tur doğrulama düştü.** Ajan ıskaları (22 satır): 1. tur 4 / 10 katılmıyorum, 2. tur (örneklem dışı 12) 0. P1 test başarısızları (54 satır): 1. tur 4 / 10, 2. tur (örneklem dışı 44) 0. İkisinde de yeniden etiketleme sonrası 2. tur geçti. Kaynak: DECISIONS 2026-11-18, `p2d_error_summary.md` §3, `p1_test_error_summary.md` §5.
- **Okumalar sonuçtan sonra soru metnine göre düzeltildi.** Soru metni değişmedi; Eren'in kontrol okumaları metinden dar ya da geniş bulununca metne döndürüldü (DECISIONS 2026-11-18 "okuma düzeltmesi"). Ajan analizinde T1 9 → 11, T6 1 → 2, T8 1 → 2; P1 test analizinde T1 kontrol öncesi 10 → 15. Eski sayılar git geçmişinde. Kaynak: DECISIONS 2026-11-18, HANDOFF 2026-11-18.
- **Dev P1e T1 etiketleri eski okumayla.** Dev ↔ test T1 doğrudan karşılaştırılamaz. Kaynak: DECISIONS 2026-11-18 (A satırı).
- **Kapsam.** P1 analizi 12 tuzağın P1'e uyan 6'sı (T1–T6); ajan analizinde T10 (yanlış atfedilen kanıt) uygulanamaz (tek ajan). Kaynak: DECISIONS 2026-11-04, 2026-11-14.

## 8. Not (sınırlama değil)

- **Kayıtlarda yerel mutlak yol.** Canlı kayıtlarda makineye özel yol var (`/home/…/storage_runs/…`). Sonucu etkilemez; kapanışta ayrı karar. Kaynak: HANDOFF 2026-11-18 (planlama, 6. madde kontrolü).
