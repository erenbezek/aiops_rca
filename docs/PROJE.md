# PROJE

## Ne
Mikroservis ortamına (OpenTelemetry Demo + kendi Python servisim) bilerek hata enjekte edip,
kök nedeni bulan yöntemleri aynı vakalar üzerinde ölçen bir altyapı ve üzerinde iki proje:

- **Proje 1:** CPU'da çalışan küçük lokal model + istatistiksel daraltma (hibrit),
  kanıt/yol doğrulaması ve "emin değilim" diyebilme (kalibrasyon).
- **Proje 2:** Büyük API modeliyle araçlı ajan (Proje 1 bittikten sonra).

Tüm yöntemler aynı vakalarda baseline'lara (kural, BARO) karşı ölçülür.
Büyük API modeli satırları iki modelle koşulur (Groq gpt-oss-120b, Gemini 3.5 Flash Lite), ayarlar birebir aynı.

## Neden
Logların dışarı çıkamadığı bir ortamda küçük lokal model, doğru desteklenirse
kök neden analizinde ne kadar iş görür?

## Bitti sayılması için
- [ ] Otomatik vaka üretimi: enjekte et → kaydet → temizle (gece boyu çalışabilir)
- [ ] En az 30 vakalık snapshot seti; bir kısmı geliştirmede hiç görülmemiş test seti
- [ ] Sonuç tablosu: baseline'lar, küçük lokal model / büyük API modeli × ham log / daraltma
- [ ] Ölçütler: top-1/top-3, kanıt geçerliliği, kalibrasyon, süre, token
- [ ] Canlı demo: hata enjekte et → kanıtlı olay raporu (+ bir sonraki adım önerisi)
- [ ] CI yeşil: birim testler + sabit snapshot'larda baseline regresyonu + servis imajı (GHCR)
- [ ] Sızıntı kontrolü: snapshot'larda cevabı ele veren veri yok (flagd vb.), testle doğrulandı
- [ ] Vaka çeşitliliği: set en az zincirleme hata, sessiz hata (log yok, sadece metrik) ve yanıltıcı gürültü içeriyor
- [ ] Tekrarlanabilirlik:
  - Seviye 1 (her makinede ve CI'da): Sonuç tablosu, repodaki resmî koşu cevapları + etiketler + baseline çıktılarından tek komutla yeniden üretilir
  - Seviye 2 (deneyi baştan koşmak): Tam snapshot seti proje sonunda GitHub Releases'te sıkıştırılmış olarak yayınlandı
- [ ] Sonuç tablosu geliştirme ve test setini yan yana gösteriyor
- [ ] Hata analizi: başarısız vakalar 12'li hata sınıflandırmasıyla etiketlendi (arXiv 2602.09937)
- [ ] DevOps kontrol listesi dolduruldu (aşağıda)
- [ ] Proje 2 (ajan): Proje 1 bittikten sonra

### DevOps kontrol listesi
Proje sonunda her satır için: gerçekten yaptım mı?

| Beceri | Projede nerede | Yapıldı |
|---|---|---|
| Dockerfile, imaj oluşturma | Kendi Python servisim | [ ] |
| OTel instrumentation | Kendi Python servisim | [ ] |
| Docker Compose, kaynak limitleri | OTel Demo yığını | [ ] |
| Telemetri hattı (collector) | flagd filtresi, dosyaya aktarım | [ ] |
| PromQL, Jaeger ve log sorguları | Snapshot kaydedici, ajan araçları | [ ] |
| Linux ağ/kaynak hataları (tc netem, CPU/bellek, kill) | Hata enjeksiyonu | [ ] |
| Otomasyon betikleri | Gece boyu vaka üretim hattı | [ ] |
| Grafana dashboard | Canlı demo | [ ] |
| CI/CD (GitHub Actions, GHCR) | Testler, regresyon, imaj | [ ] |
| Dağıtık sistemde sorun giderme | Kurulum ve işletme | [ ] |

## Kapsam dışı
- Otomatik düzeltme (ajan sadece bir sonraki adımı önerir, uygulamaz)
- Bulut (staj sonrası ayrı proje)
- HolmesGPT (geri planda, ileride tekrar gündeme gelebilir)

### Şartlı ekler
- **Kubernetes** (kind + OTel Demo Helm): yeni makine gelince karar verilecek.
  Önerilen kural: 3. hafta sonunda ana sonuç tablosu dolu değilse yapılmaz.
- **Web arayüzü** (tek sayfa: hata seç + buton + kanıtlı rapor): ana sonuç tablosu dolduktan sonra.
  Kütüphane seçimi o zaman sorulacak.

## Şu an
Repo GitHub'da (erenbezek/aiops_rca); iş akışı: görev başına `task/<konu>` dalı + PR, merge Eren'de.
Duman testi `tools/api_smoke_test.py` olarak taşındı ve geçti; `HARITA.md` taslak hedef yapıyla yazıldı.
Satır sonları LF'e sabitlendi (`.gitattributes`, `.editorconfig`, `.vscode/settings.json`), `task/line-endings` PR'ı inceleme bekliyor.
Bekleyen: yeni makinede lokal model ölçümü; sonraki uygulama görevi planlamadan gelecek.
