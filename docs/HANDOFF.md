# DEVİR

## 2026-10-13 · Planlama → Uygulama
- Yapılan: Fikir aşaması tamamlandı. `docs/PROJE.md`, `KARARLAR.md`, `SOZLUK.md`, `DEVIR.md` yazıldı.
  API duman testi `C:\Users\erenb\cerebrum2\api_duman_testi\duman_testi.py` içinde (proje klasörü dışında) yapıldı.
- Beklenen (amaç: repoyu çalışır hale getirip ilk commit'i atmak):
  1. `aiops_rca/` içinde git reposu başlat. `.gitignore` ekle: en az `snapshots/`, `__pycache__/`, `.env`, LLM cevap önbellekleri.
  2. Duman testini `aiops_rca/` altına İngilizce isimlerle taşı (klasör, dosya ve koddaki tanımlayıcılar).
     İsimleri önce Eren'e öner, onay alınca `SOZLUK.md`'ye yaz.
  3. `docs/HARITA.md`'yi oluştur: mevcut dosyalar + hedef yapı (taslak Mermaid diyagramı, PROJE.md'deki mimariye göre).
  4. İlk commit.
  - Bitti ölçütü: `git log`'da ilk commit var; taşınan duman testi yeni yerinden çalışıyor ve aynı tablo formatını üretiyor
    (Gemma satırı sunucu hatası verebilir, bu bir regresyon değildir); `HARITA.md` var; hiçbir anahtar repoda yok.
- Dikkat:
  - API anahtarları sadece ortam değişkenlerinde (`GROQ_API_KEY`, `GEMINI_API_KEY`, User seviyesinde). Koda, dosyaya veya sohbete yazılmaz.
    Claude Code'un shell'i yeni User değişkenlerini görmeyebilir: `$env:GEMINI_API_KEY = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')`.
  - Eski `cerebrum2/api_duman_testi/` klasörünü silmek dosya silme işlemidir: Eren'in onayı olmadan silme.
  - Duman testinde değerlendirme kriteri değiştirilmez (~6K kriter, ~12K bilgi amaçlı). Taşıma sadece isim ve konum değişikliği.
  - PowerShell 5.1'de `python -c` içine çift tırnak geçmez; çok satırlı denemeler için dosya kullan.
  - Yeni klasör, isim, paket bağımlılığı: önce öner, onay bekle.

## 2026-10-13 · Planlama → Uygulama (ek karar: repoda ne tutulur)
- Yapılan: Uygulamanın notu üzerine karar verildi ("llm_cache git dışı" ile "tablo tek komutla yeniden üretilir" çelişkisi). Bkz. KARARLAR.md.
- Beklenen (ilk görev kartını bekletmez, ilgili adımlar geldiğinde uygulanır):
  - `llm_cache/` git dışında kalır (geliştirme denemeleri).
  - Resmî değerlendirme koşusunun LLM cevapları ayrı, **repoda tutulan** bir klasöre yazılır (geliştirme + test vakaları). Klasör adını öner, Eren onaylasın.
  - Repoda olacaklar: etiketler (ground truth), snapshot meta verisi, baseline çıktıları, CI için 3-5 incident'lık sabit snapshot alt kümesi.
  - Tam snapshot seti git dışında kalır; proje sonunda GitHub Releases'e yüklenir.
  - Bitti ölçütü (ilgili adım geldiğinde): temiz bir klondan, snapshot'lar olmadan, sonuç tablosu tek komutla üretiliyor.
- Dikkat:
  - İlk karttaki `.gitignore` `snapshots/`'ı tamamen dışlıyor. CI alt kümesi ya ayrı bir klasörde durmalı ya da `.gitignore`'a istisna eklenmeli. Hangisi olacağını öner.
  - Snapshot boyutu henüz bilinmiyor; ilk snapshot üretildiğinde incident başına boyutu ölçüp DEVIR.md'ye yaz (CI alt kümesinin kırpılması gerekip gerekmediği buna bağlı).

## 2026-10-14 · Planlama → Uygulama (satır sonları)
- Yapılan: Uygulamanın CRLF notu üzerine karar verildi. Bkz. KARARLAR.md.
- Beklenen (amaç: container'a giden betiklerin CRLF ile bozulmasını önlemek; enjeksiyon betiklerinden önce):
  1. Repo köküne `.gitattributes`: tüm metin dosyaları LF (`* text=auto eol=lf`), `.bat` ve `.cmd` CRLF.
  2. Mevcut dosyaları yeni kurala göre normalize et (`git add --renormalize .`), değişen dosya varsa listele.
  3. Tek commit.
  - Bitti ölçütü: `git ls-files --eol` çıktısında çalışma kopyasındaki (`w/`) metin dosyaları `lf`, istisnalar hariç;
    test amaçlı geçici bir `.sh` dosyası (commit edilmez) checkout sonrası LF geliyor.
- Dikkat:
  - `.editorconfig` (editörün yeni dosyaları LF kaydetmesi) Eren'in onayını bekliyor; onaysız ekleme.
    Bu olmadan kalan boşluk: editörde oluşturulup commit edilmeden Docker'a bağlanan dosya CRLF olabilir.
  - `core.autocrlf` global ayarını değiştirme; `.gitattributes` bu repo için onu zaten geçersiz kılıyor.

## 2026-10-14 · Planlama → Uygulama (.editorconfig onaylandı)
- Yapılan: Eren `.editorconfig`'i onayladı; bir önceki kaydın "Dikkat" maddesindeki bekleme kalktı.
- Beklenen (satır sonları göreviyle aynı commit'te olabilir):
  1. Repo köküne `.editorconfig`: `root = true`; tüm dosyalar `end_of_line = lf`, `charset = utf-8`, `insert_final_newline = true`;
     `.bat`/`.cmd` için `end_of_line = crlf`. Girinti kuralı ekleme (kapsam dışı, ayrı bir stil kararı).
  - Bitti ölçütü: Eren'in kullandığı editörde yeni oluşturulan bir dosya LF ile kaydediliyor.
- Dikkat:
  - VS Code `.editorconfig`'i kendiliğinden okumaz, "EditorConfig for VS Code" eklentisi gerekir. Eren hangi editörü kullanıyor, önce sor.
    Eklenti kurmak yeni bir araç demek: Eren'e sor. Alternatifi `.vscode/settings.json` içinde `"files.eol": "\n"`; o da yeni dosya, onay gerekir.

## 2026-10-14 · Planlama → Uygulama (editör: VS Code, eklentisiz)
- Yapılan: Eren VS Code kullanıyor; eklenti kurulmayacak, `.vscode/settings.json` onaylandı. Bir önceki kaydın sorusu kapandı.
- Beklenen (satır sonları göreviyle aynı commit'te olabilir):
  1. `.vscode/settings.json`: `"files.eol": "\n"`. Başka ayar ekleme.
  2. `.editorconfig` yine eklenir (onaylı; VS Code okumasa da diğer editörler ve GitHub için standart). İçeriği `settings.json` ile çelişmemeli.
  3. `.gitignore` `.vscode/`'u dışlıyorsa sadece `settings.json`'ı repoya alacak şekilde ayarla; nasıl yapacağını Eren'e söyle.
  - Bitti ölçütü: VS Code'da yeni oluşturulan bir dosya sağ alttaki durum çubuğunda `LF` gösteriyor;
    ayrıca uygulama oturumunun kendi araçlarıyla yazdığı bir dosya da commit öncesi LF (çalışma kopyası kontrolü).
- Dikkat:
  - `files.eol` sadece yeni dosyaları etkiler; mevcut dosyalar `.gitattributes` + `--renormalize` ile düzelir.

## 2026-10-14 · Uygulama → Planlama
- Yapılan:
  - İlk kart bitti: git + `.gitignore`, duman testi `tools/api_smoke_test.py` (İngilizce tanımlayıcı, çıktı Türkçe), `HARITA.md`, ilk commit.
    Yeni yerinden koşu: Groq ve Gemini GEÇTİ, Gemma 500 (beklenen). Eski `cerebrum2/api_duman_testi/` Eren'in onayıyla silindi.
  - Repo GitHub'a gönderildi (erenbezek/aiops_rca); GitHub'ın README commit'i korundu (rebase, zorla push yok).
  - PR akışı kuruldu: `task/<konu>` dalı, PR'ı Eren açar ve birleştirir (KARARLAR.md).
  - Satır sonu kartları (3 kayıt) `task/line-endings` dalında: `.gitattributes`, `.editorconfig`, `.vscode/settings.json`, renormalize.
    Ölçütler: tüm dosyalar `i/lf w/lf`; geçici `.sh` checkout sonrası LF, geçici `.bat` CRLF; Write aracıyla yazılan dosya LF.
- Beklenen:
  - Eren: `task/line-endings` PR'ını açıp incelemek; EditorConfig eklentisi kurulunca VS Code'da yeni dosyada durum çubuğu `LF` mi, kontrol edip öyleyse merge.
  - Planlama: sonraki uygulama görev kartı.
- Dikkat:
  - Gemini 3.5 Flash Lite duman koşusunda anlık 503 verdi; resmî değerlendirme koşusunda yeniden deneme mantığı gerekecek.
  - Groq dakikada 8K token: ~12K girdi 413 verdi. "Ham log" satırı tek istekte 8K'yı aşamaz.
  - Token sayıları modeller arası karşılaştırılamaz (aynı log: Groq 5921, Gemini 8135).
  - PowerShell 5.1 `Set-Content`/`Out-File` CRLF yazar; Docker'a bağlanacak dosyalar PowerShell ile yazılmamalı (kalıcı kural gerekirse planlama karar versin).
  - `README.md` sadece başlık; doldurulması ayrı iş.

## 2026-10-14 · Planlama → Uygulama (docs dosya adları İngilizce)
- Yapılan:
  - Planlama `main` üzerinde commit edilmemiş docs değişiklikleri bıraktı: `OTEL_DEMO.md` ve `VAKA_KATALOGU.md` (yeni), `KARARLAR.md`, `PROJE.md`, `SOZLUK.md`, `DEVIR.md`.
    İçerik: OTel Demo 3.1.0 keşfi, veri akışı kararı (dosya + kalıcı izleme sistemi), vaka kataloğu, ilgili kararlar.
  - Eren docs dosya adlarının İngilizce olmasını onayladı (bkz. KARARLAR.md son satır).
- Beklenen (amaç: dosya adlarını değiştirmek, geçmişi ve bağlantıları kırmadan):
  1. `task/docs-english-names` dalı aç. Planlamanın bekleyen değişikliklerini **ayrı bir ilk commit** olarak al (ad değişikliğiyle karışmasın).
  2. `git mv` ile yeniden adlandır:
     `PROJE.md` → `PROJECT.md`, `KARARLAR.md` → `DECISIONS.md`, `SOZLUK.md` → `GLOSSARY.md`, `DEVIR.md` → `HANDOFF.md`,
     `HARITA.md` → `ARCHITECTURE.md`, `VAKA_KATALOGU.md` → `INCIDENT_CATALOG.md`. `OTEL_DEMO.md` aynı kalır.
  3. Dosya içlerindeki eski adları yenileriyle değiştir (`GLOSSARY.md`'deki dosya satırları, `ARCHITECTURE.md` tablosu, çapraz referanslar).
     İstisna: `HANDOFF.md`'deki eski kayıtlar ve `DECISIONS.md`'deki eski satırlar değişmez (sona eklenir kuralı).
  4. `HANDOFF.md` sonuna eski ad → yeni ad eşlemesini içeren bir kayıt ekle.
  5. Dalı gönder; Eren PR açıp birleştirir.
  - Bitti ölçütü: `git log --follow docs/PROJECT.md` eski geçmişi gösteriyor;
    `git grep -nE "PROJE\.md|KARARLAR\.md|SOZLUK\.md|DEVIR\.md|HARITA\.md|VAKA_KATALOGU\.md"` sadece `HANDOFF.md`'nin eski kayıtlarında ve `DECISIONS.md`'nin eski satırlarında sonuç veriyor.
- Dikkat:
  - Bu kart bitene kadar senin oturumun eski adlarla çalışır; yeni dosyaları birleştirmeden sonra açılan oturumlar kullanır.
  - PR birleşince Eren planlamaya haber verir; planlama genel `CLAUDE.md` ve `proje_akisi` skill'ini yeni adlara geçirir. Birleştirmeden önce skill'e dokunulmaz.
  - Dosya yazarken PowerShell yazma komutlarını kullanma (KARARLAR: CRLF).

## 2026-10-14 · Uygulama → Planlama (docs adları değişti)
- Yapılan (`task/docs-english-names`): docs dosya adları İngilizce. Geçmiş korundu (`git mv`, ad değişikliği içerik değişikliğinden ayrı commit).

  | Eski ad | Yeni ad |
  |---|---|
  | `PROJE.md` | `PROJECT.md` |
  | `KARARLAR.md` | `DECISIONS.md` |
  | `SOZLUK.md` | `GLOSSARY.md` |
  | `DEVIR.md` | `HANDOFF.md` |
  | `HARITA.md` | `ARCHITECTURE.md` |
  | `VAKA_KATALOGU.md` | `INCIDENT_CATALOG.md` |
  | `OTEL_DEMO.md` | (değişmedi) |

  Bu dosyadaki önceki kayıtlar ve `DECISIONS.md`'deki önceki satırlar eski adlarla kaldı (sona eklenir kuralı); yukarıdaki tabloya göre okunur.
  `ARCHITECTURE.md` tablosuna `OTEL_DEMO.md` ve `INCIDENT_CATALOG.md` eklendi.
- Beklenen:
  - Eren: PR'ı açıp birleştirir, sonra planlamaya haber verir.
  - Planlama: genel `CLAUDE.md` ve `proje_akisi` skill'ini yeni adlara geçirir. O yapılana kadar açılan oturumlar `docs/PROJE.md`'yi bulamaz, proje hafızasını kendiliğinden okumaz.
- Dikkat:
  - Dosya içindeki başlıklar Türkçe kaldı (`# PROJE`, `# KARARLAR`, `# SÖZLÜK`, `# HARİTA`, `# DEVİR`); kart sadece dosya adlarını kapsıyordu. Değişip değişmeyeceği planlamanın kararı.
