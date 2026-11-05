# P1 sınırlamaları

P1 sonuçlarının ([`p1_table.md`](p1_table.md), [`p1_error_summary.md`](p1_error_summary.md)) sınırlamaları. Elle yazılır; maddeler proje kayıtlarından toplanmıştır, yeni yorum içermez. Her maddede: ne, sayı, okumayı değiştirip değiştirmediği, kaynak (`docs/HANDOFF.md` / `docs/DECISIONS.md` tarihi).

## 1. Veri ve setler

- **Set karışımı farklı.** Dev 11 demo / 7 kendi senaryomuz, test 6 demo / 12 kendi. Toplamdaki dev–test okuması bu farkı ayırmaz; grup tabloları (tablo bölüm 3 ve 4) yan yana okunur. Kaynak: HANDOFF 2026-11-05 (planlama, test puanlaması kontrolü).
- **Ham seviyede 8 / 18 vaka boş girdi** (her modelde, dev ve testte): ham hücrelerde 10 vaka soruldu, boş girdi ıskalama sayılır. Kaynak: HANDOFF 2026-11-04 (P1d resmî analiz), test koşusu sayımları (HANDOFF 2026-11-05).
- **Ezber.** Büyük modeller OTel Demo'yu eğitimde görmüş olabilir (flag senaryoları upstream'de açık). Log mesajlarındaki ayırt edici ifadeler (ör. `Invalid token`) belirtidir, girdide kalır; model demoyu bunlardan tanıyabilir. Kaynak: HANDOFF 2026-10-23 (zor deneme; takma ad ön denemesi).

## 2. Yöntemler ve referanslar

- **BARO'nun üç sınırlaması** (okumayı değiştirmez; port RCAEval 1.9.0 ile bit düzeyinde aynı, dev'de ayar yok):
  1. Bellek ve ağ kayması: demo her vakadan ~5 dk önce yeniden başlıyor; yeni konteynerlerin belleği ve ağ trafiği artıyor, BARO yalnız artışı puanladığı için bunu yakalıyor. En üst sütun 16 / 43 vakada `telemetry-docs` (bellek 11, ağ 5). RCAEval veri setlerinde bu etki yok.
  2. Normal dönemde sabit sütun atılır (`drop_constant`): normalde hep 0 olan hata sayısı düşer, alarmdan sonra başlayan hata BARO'ya girmez.
  3. Yalnız artış puanlanır: durdurulan ya da dondurulan konteynerin düşüşü görünmez; çağıranların gecikmesi öne çıkar.

  Kaynak: HANDOFF 2026-10-31 (P1b 1–3 kontrolü).
- **Daraltmanın öne alma kuralı (v0) ve v1 mekanizması.** Kural yalnız pilot 25 vakada ayarlandı. v0'da kökün çağırdığı servis yalnız istek düşüşüyle anormalse (kök hata verince arkasına daha az istek gider) kök "derin" sayılmaz ve geri düşer (pilotta 3 vaka). v1 bunu engellemez, pilotta top-1 21 → 22, ama kökün tek belirtisi istek düşüşü olan durdurulan servis vakasını 1. sıradan 2.'ye geriletir: mekanizma iki yönlü; önceden yazılı v0 kaldı. Kaynak: DECISIONS 2026-10-31 "Daraltmanın öne alma kuralı", HANDOFF 2026-10-31 (P1c 3. adım).
- **Daraltma referansı güçlü ve geliştirilirken pilot ve dev görülmüştü.** Modelsiz daraltma referansı dev'de top-1 15 / 18, top-3 17 / 18 (4B daraltma 13 / 16, gpt-oss 15 / 17, Gemini 17 / 18); testte 11 / 18 ve 13 / 18. Daraltma referansının test satırı bu yüzden önemli. Kaynak: HANDOFF 2026-11-04 (planlama, P1e 2. adım).
- **Qwen üretici ayarı denenmedi** (temperature 1.0, top_k 20, presence_penalty 2.0). Deterministik ayar (sıcaklık 0) yerel sonuçları alt sınırda tutabilir. Kaynak: DECISIONS 2026-11-01 "tekrar döngüsü", HANDOFF 2026-11-04 (P1d kapanışı).
- **API bütçesi Qwen tokenizer'ıyla sayıldı.** Sağlayıcının saydığı giriş token'ı / Qwen sayımı: Gemini 1,03–1,20, gpt-oss 0,84–0,99. Bütçe sınırı sağlayıcı sayımıyla birebir değil. Kaynak: HANDOFF 2026-11-04 (P1d resmî analiz).
- **9B bilgi satırı dev sonuçları görüldükten sonra eklendi.** Seçimi ve hiçbir kararı değiştirmez (seçilen yerel model 4B). Kaynak: DECISIONS 2026-11-03 "P1e'de qwen3.5-9b bilgi satırı".

## 3. Koşu süreci

- **a1'de gpt-oss özet turu iki kez koşuldu:** 2026-11-01'de durdu (`json_validate_failed`, Groq kotası); resmî kayıt 2026-11-03 `20261103T080725Z-llm`. a1'in ilk 10 turunda `src` ağacı `c9bb8c5b…`, sonra `461d037b…` (kayıtlı istisna `eafc491`). Kaynak: DECISIONS 2026-11-01 "Groq `json_validate_failed`", HANDOFF 2026-11-04 (P1d kapanışı).
- **b aşaması:** Groq turları `--no-day-guard` ile (Eren kararı, `day_guard: skipped`); yerel turlarda kapak uykusu ~1 saat gecikme yarattı, sonucu etkilemedi; 3. günde sıra Groq kotası için bölündü. Kaynak: HANDOFF 2026-11-03, 2026-11-04 (P1d kapanışı).
- **Test koşusunda 38 sn uyku** (2026-11-04T21:23:16Z–21:23:54Z), 9B özet turunun içinde: GNOME'un boşta uyku zamanlayıcısı systemd uyku kilidine uymadı. Yerel model, sıcaklık 0; bağlantı ve şema hatası 0, cevaplar etkilenmez. 9B özet süresine ~38 sn dahil; yeniden koşulmadı. Kaynak: HANDOFF 2026-11-05.
- **Gemini test günü yavaştı.** Denemede iki çağrı 36,0 ve 28,5 sn (dev a2'de çağrı başına ~1,8 sn); model adı, ayar ve çıktı uzunluğu aynı, sağlayıcı yükü gibi. Test tablosunda Gemini özet en uzun çağrı 7,596 sn. API satırlarında süre sağlayıcı yüküne bağlı: dev–test süre farkı yöntem farkı sayılmaz. Kaynak: HANDOFF 2026-11-04 (planlama, deneme kontrolü).
- **`duration_s` son denemenin süresi:** yeniden denenen satırlarda toplam süre değil; yeniden deneme ve Groq beklemesi dahil değil (denemeler `attempts`'ta). Kaynak: HANDOFF 2026-11-04 (P1d kapanışı).

## 4. Puanlama

- **gRPC adı eşlenmiyor (P1a puanlaması).** Kök ilk 3'te gRPC adıyla (dev'de `CartService`, `oteldemo.RecommendationService`; P1d 2B hamda `oteldemo.AdService`) geçtiği hâlde eşlenmediği için ıskalama sayılan satırlar: dev 2 (4B ham 1, gpt-oss ham 1; P1d'deki 2B ham ile 3), test 7 (4B ham 1, gpt-oss ham 3, Gemini ham 2, 9B ham 1); hepsi hamda, testte 3'ü 1. sırada. İlgili ham hücrelerde top-3 en çok bu kadar artardı; hiçbir satırın okuması değişmez (en uç durum gpt-oss ham: dev 8 / test 7). Puanlama değişmez; sayım `error_analysis summary` (özet bölüm 4). Kaynak: HANDOFF 2026-11-04 (3. adım kontrolü), 2026-11-05 (planlama).

## 5. Okumalar

- **Dev–test farkı aşırı uyumla dağılım farkını ayıramaz;** çoklu karşılaştırma düzeltmesi yok (15 satır; biri tesadüfen "fark" çıkabilirdi). Testte bütün satırlar "ayırt edilemedi" (en küçük p 0,1774). Kaynak: DECISIONS 2026-11-04 "P1e dev–test okuması".
- **"Ayırt edilemedi", "aynı" demek değil.** 18 vakada yalnız büyük düşüşler görülebilir: dev 18 → test ≤ 13, 17 → ≤ 11, 16 → ≤ 9, 15 → ≤ 8. Kaynak: DECISIONS 2026-11-04, HANDOFF 2026-11-05 (planlama).
- **Daraltma referansı ile modeller arasında önceden yazılmış karşılaştırma kuralı yok.** Test hücreleri yalnız betimsel okunur; sonradan anlamlılık testi eklenmez. Kaynak: HANDOFF 2026-11-05 (planlama).
- **Takma ad ölçümü** (P1d, yalnız dev; test takma adla koşulmadı):
  - gpt-oss ham hücresi belirsiz (top-3 a1 / a2 / b: 7 / 5 / 6, gürültü 2); diğer 14 hücrede "görülmedi", "üst sınır" hiçbir hücrede yok.
  - Takma ad yalnız adları gizler: span adlarındaki gRPC yöntemleri (`ListRecommendations`, `GetProduct`, `PlaceOrder`, `GetAds`, `Charge`), `get-quote` HTTP yolu ve ayırt edici log ifadeleri kalır. Takma ad farkı ezber etkisinin alt sınırı okunur; ad tutarsızlığı takma adlı cevaplarda eşlenmemiş adlara da yol açabilir, fark iki yönde bozulabilir.
  - Takma adlı koşuların eşlenmemiş ad sayısı (b): 2B ham 5, 4B ham 2, 9B ham 3, gpt-oss ham 3 (biri gerçek ad `checkout`), Gemini ham 2; özet ve daraltmada 0. gpt-oss ham'daki `checkout` girdiden sızmamış: dev `inc-86d286ea`'nın takma adlı ham girdisi yeniden üretildi (sha256 kayıtla aynı); girdide yalnız kökün (`ad` → `promotions`) 125 satırı var, ne `checkout` ne takma adı `order-processor` geçiyor. `checkout` modelin kendi 3. adayı (kök 1. sırada, satır top-3 isabet); ezber mi genel bir ad tahmini mi, ayırt edilemez.
  - `quote-svc` sızıntısı: takma adlı girdide gerçek adı taşıyan tek tanımlayıcı, yalnız pilot `inc-91bf76d4`'te; dev ve testte yok, ölçümü etkilemez.

  Kaynak: HANDOFF 2026-10-31 (P1c 4. adım planı kontrolü), 2026-11-01 (P1c 5c duman kontrolü), 2026-11-02 (P1d b kontrolü), 2026-11-04 (P1d resmî analiz ve kapanışı).

## 6. Hata analizi

- **Yalnız dev** (test P2'den sonra); kapsam a1, 4B / gpt-oss / Gemini × ham / özet / daraltma, şema içi ve top-1'i ıskalayan 29 satır. Kural, BARO, daraltma referansı ve 9B kapsam dışı. Kaynak: DECISIONS 2026-11-04 "P1e hata analizi kapsamı".
- **Tuzakların yalnız 6'sı.** Sınıflama 12 tuzağın 6'sını (T1–T6) kullanıyor. Tuzaklar ajanlar için yazıldı; öteki 6'sı P1'in tek çağrılık kurulumunda uygulanamaz. 12'nin tamamı P2'de. PROJECT'teki "12'li hata sınıflandırması" kutusu bu yüzden P1'de kısmen karşılanır. Kaynak: DECISIONS 2026-11-04 "P1e hata sınıflaması".
- **Etiketleyen bir LLM.** 29 satırı uygulama oturumu (Claude) etiketledi. Eren 10 satırı (tohum 20261104) doğruladı; kartta öngörülen çapa etkisine (etiketi görerek onaylama) karşı kör yapıldı: önce cevapladı, sonra etiketi gördü; 9 katılıyor, 1 katılmıyor (4B daraltma, T5) → yeniden etiketleme yok. Sorular Eren'e planlamanın sade ifadesiyle soruldu; 1. ve 2. satırda ilk T6 cevabı bu ifadenin belirsizliği yüzünden "evet"ti, 5. satırda T5'in ilk cevabı "anlamadım"; netleştirmeden sonraki cevaplar sayıldı (`eren_check.note`). Kaynak: HANDOFF 2026-11-05 (planlama, Eren doğrulaması).
- **İnsan kontrolünden geçmeyenler:** T2 ve T3 kodla belirlendiği için sorulmadı. T4 ve `root_visibility`'nin indirect / absent yargısı Eren'e sorulmadı. Kaynak: HANDOFF 2026-11-05.
- **T2 yorumu:** kök hem absent hem ilk 3'teyse T2 = hayır (2 satır). Donmuş metin bu durumda iki kuralı birden veriyordu; yorum etiketleme sırasında seçildi. Kaynak: HANDOFF 2026-11-04 (3. adım ve kontrolü).
- **T2'de ad eşleşmesi belirleyici:** iki satırda 3. aday kökün işlem adı (`CartService`, `oteldemo.RecommendationService`) ama eşlenmediği için T2 evet. Kaynak: HANDOFF 2026-11-04.
- **T6 dar ve ölçeğe bağlı.**
  - Yalnız başka bir servis daha çok değiştiğinde "evet". "Model tek bir servise bakıp karar vermiş" gibi daha geniş bir çapraz kontrol eksikliğini yakalamaz; bunun bir kısmını T2 / T3 yakalıyor.
  - "En büyük güç" harfiyen uygulandı: iki satırda fark çok küçük (quote-gateway 1,48 / shipping 1,475), bir satırda en büyük güç bir log sinyali (ölçekler farklı).
  - "Daha büyük değişim" kat olarak ölçülseydi doğrulama örnekleminin 2. satırında cart (139 kat) checkout'u (9 kat) geçerdi ve T6 "evet" olurdu.

  Kaynak: HANDOFF 2026-11-04 (3. adım), 2026-11-05 (planlama, Eren doğrulaması).
- **T1 abartılı sıfatları yakalamıyor** (ör. "massive"): doğrulama örnekleminin 8. satırında frontend CPU ortalaması kuralın eşiğinin kılpayı altında. Kaynak: HANDOFF 2026-11-05.

## 7. Tekrarlanabilirlik

- **CI puanlamayı yeniden yapmaz:** snapshot'lar repoda yok; CI tabloyu ve hata özetini commit'lenmiş `scores.json` ve etiket dosyasından bayt aynı yeniden üretir. Puanlamanın kendisi planlama tarafından scratch klonda yeniden yapılıp doğrulandı (15 test koşusu, `scores.json` bayt aynı). Kaynak: HANDOFF 2026-11-04, 2026-11-05.
- **API modelleri zamanla değişebilir:** gpt-oss-120b (Groq) ve gemini-3.5-flash-lite aynı adla farklı davranabilir; yerel modeller GGUF SHA256'sıyla sabit. Kaynak: P1e kartı (HANDOFF 2026-11-04), HANDOFF 2026-10-31 (P1c 1. adım kontrolü, GGUF SHA256).
