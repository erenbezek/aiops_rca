# HANDOFF

## 2026-10-13 · Planlama → Uygulama
- Yapılan: Fikir aşaması tamamlandı. `docs/PROJECT.md`, `DECISIONS.md`, `GLOSSARY.md`, `HANDOFF.md` yazıldı.
  API duman testi `C:\Users\erenb\cerebrum2\api_duman_testi\duman_testi.py` içinde (proje klasörü dışında) yapıldı.
- Beklenen (amaç: repoyu çalışır hale getirip ilk commit'i atmak):
  1. `aiops_rca/` içinde git reposu başlat. `.gitignore` ekle: en az `snapshots/`, `__pycache__/`, `.env`, LLM cevap önbellekleri.
  2. Duman testini `aiops_rca/` altına İngilizce isimlerle taşı (klasör, dosya ve koddaki tanımlayıcılar).
     İsimleri önce Eren'e öner, onay alınca `GLOSSARY.md`'ye yaz.
  3. `docs/ARCHITECTURE.md`'yi oluştur: mevcut dosyalar + hedef yapı (taslak Mermaid diyagramı, PROJECT.md'deki mimariye göre).
  4. İlk commit.
  - Bitti ölçütü: `git log`'da ilk commit var; taşınan duman testi yeni yerinden çalışıyor ve aynı tablo formatını üretiyor
    (Gemma satırı sunucu hatası verebilir, bu bir regresyon değildir); `ARCHITECTURE.md` var; hiçbir anahtar repoda yok.
- Dikkat:
  - API anahtarları sadece ortam değişkenlerinde (`GROQ_API_KEY`, `GEMINI_API_KEY`, User seviyesinde). Koda, dosyaya veya sohbete yazılmaz.
    Claude Code'un shell'i yeni User değişkenlerini görmeyebilir: `$env:GEMINI_API_KEY = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')`.
  - Eski `cerebrum2/api_duman_testi/` klasörünü silmek dosya silme işlemidir: Eren'in onayı olmadan silme.
  - Duman testinde değerlendirme kriteri değiştirilmez (~6K kriter, ~12K bilgi amaçlı). Taşıma sadece isim ve konum değişikliği.
  - PowerShell 5.1'de `python -c` içine çift tırnak geçmez; çok satırlı denemeler için dosya kullan.
  - Yeni klasör, isim, paket bağımlılığı: önce öner, onay bekle.

## 2026-10-13 · Planlama → Uygulama (ek karar: repoda ne tutulur)
- Yapılan: Uygulamanın notu üzerine karar verildi ("llm_cache git dışı" ile "tablo tek komutla yeniden üretilir" çelişkisi). Bkz. DECISIONS.md.
- Beklenen (ilk görev kartını bekletmez, ilgili adımlar geldiğinde uygulanır):
  - `llm_cache/` git dışında kalır (geliştirme denemeleri).
  - Resmî değerlendirme koşusunun LLM cevapları ayrı, **repoda tutulan** bir klasöre yazılır (geliştirme + test vakaları). Klasör adını öner, Eren onaylasın.
  - Repoda olacaklar: etiketler (ground truth), snapshot meta verisi, baseline çıktıları, CI için 3-5 incident'lık sabit snapshot alt kümesi.
  - Tam snapshot seti git dışında kalır; proje sonunda GitHub Releases'e yüklenir.
  - Bitti ölçütü (ilgili adım geldiğinde): temiz bir klondan, snapshot'lar olmadan, sonuç tablosu tek komutla üretiliyor.
- Dikkat:
  - İlk karttaki `.gitignore` `snapshots/`'ı tamamen dışlıyor. CI alt kümesi ya ayrı bir klasörde durmalı ya da `.gitignore`'a istisna eklenmeli. Hangisi olacağını öner.
  - Snapshot boyutu henüz bilinmiyor; ilk snapshot üretildiğinde incident başına boyutu ölçüp HANDOFF.md'ye yaz (CI alt kümesinin kırpılması gerekip gerekmediği buna bağlı).

## 2026-10-14 · Planlama → Uygulama (satır sonları)
- Yapılan: Uygulamanın CRLF notu üzerine karar verildi. Bkz. DECISIONS.md.
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
  - İlk kart bitti: git + `.gitignore`, duman testi `tools/api_smoke_test.py` (İngilizce tanımlayıcı, çıktı Türkçe), `ARCHITECTURE.md`, ilk commit.
    Yeni yerinden koşu: Groq ve Gemini GEÇTİ, Gemma 500 (beklenen). Eski `cerebrum2/api_duman_testi/` Eren'in onayıyla silindi.
  - Repo GitHub'a gönderildi (erenbezek/aiops_rca); GitHub'ın README commit'i korundu (rebase, zorla push yok).
  - PR akışı kuruldu: `task/<konu>` dalı, PR'ı Eren açar ve birleştirir (DECISIONS.md).
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
  - Planlama `main` üzerinde commit edilmemiş docs değişiklikleri bıraktı: `OTEL_DEMO.md` ve `INCIDENT_CATALOG.md` (yeni), `DECISIONS.md`, `PROJECT.md`, `GLOSSARY.md`, `HANDOFF.md`.
    İçerik: OTel Demo 3.1.0 keşfi, veri akışı kararı (dosya + kalıcı izleme sistemi), vaka kataloğu, ilgili kararlar.
  - Eren docs dosya adlarının İngilizce olmasını onayladı (bkz. DECISIONS.md son satır).
- Beklenen (amaç: dosya adlarını değiştirmek, geçmişi ve bağlantıları kırmadan):
  1. `task/docs-english-names` dalı aç. Planlamanın bekleyen değişikliklerini **ayrı bir ilk commit** olarak al (ad değişikliğiyle karışmasın).
  2. `git mv` ile yeniden adlandır: `PROJECT.md`, `DECISIONS.md`, `GLOSSARY.md`, `HANDOFF.md`,
     `ARCHITECTURE.md`, `INCIDENT_CATALOG.md`. `OTEL_DEMO.md` aynı kalır.
  3. Dosya içlerindeki eski adları yenileriyle değiştir (`GLOSSARY.md`'deki dosya satırları, `ARCHITECTURE.md` tablosu, çapraz referanslar).
     İstisna: `HANDOFF.md`'deki eski kayıtlar ve `DECISIONS.md`'deki eski satırlar değişmez (sona eklenir kuralı).
  4. `HANDOFF.md` sonuna eski ad → yeni ad eşlemesini içeren bir kayıt ekle.
  5. Dalı gönder; Eren PR açıp birleştirir.
  - Bitti ölçütü: `git log --follow docs/PROJECT.md` eski geçmişi gösteriyor;
    `git grep` eski Türkçe dosya adlarını hiçbir yerde bulmuyor.
- Dikkat:
  - Bu kart bitene kadar senin oturumun eski adlarla çalışır; yeni dosyaları birleştirmeden sonra açılan oturumlar kullanır.
  - PR birleşince Eren planlamaya haber verir; planlama genel `CLAUDE.md` ve `proje_akisi` skill'ini yeni adlara geçirir. Birleştirmeden önce skill'e dokunulmaz.
  - Dosya yazarken PowerShell yazma komutlarını kullanma (DECISIONS: CRLF).

## 2026-10-14 · Uygulama → Planlama (docs adları değişti)
- Yapılan (`task/docs-english-names`): docs dosya adları, başlıkları ve tüm referansları İngilizce: `PROJECT.md`, `DECISIONS.md`,
  `GLOSSARY.md`, `HANDOFF.md`, `ARCHITECTURE.md`, `INCIDENT_CATALOG.md` (`OTEL_DEMO.md` aynı). Geçmiş korundu (`git mv`, ad değişikliği ayrı commit).
  Eren'in isteğiyle önceki kayıtlardaki dosya referansları da güncellendi (bkz. DECISIONS.md); kayıtların başka içeriği değişmedi.
  `ARCHITECTURE.md` tablosuna `OTEL_DEMO.md` ve `INCIDENT_CATALOG.md` eklendi.
- Beklenen:
  - Eren: PR'ı açıp birleştirir, sonra planlamaya haber verir.
  - Planlama: genel `CLAUDE.md` ve `proje_akisi` skill'ini yeni adlara geçirir (`docs/PROJECT.md` vb.).

## 2026-10-15 · Planlama → Uygulama (sızıntı testi)
- Yapılan: Sızıntı testi tasarlandı, Eren ölçütü ve kararları onayladı (bkz. DECISIONS.md 2026-10-15 satırları). Sızıntı yolları `OTEL_DEMO.md` "Sızıntı yolları" tablosunda (12 satır).
  Planlamanın commit edilmemiş değişiklikleri `main`'de: `DECISIONS.md`, `GLOSSARY.md`, `OTEL_DEMO.md`, `HANDOFF.md` — dalın ilk commit'i olarak al.
- Beklenen (amaç: snapshot'ta cevabı ele veren izi bulan, Docker'sız çalışan bir dedektör; collector süzmesinin arkasındaki ikinci güvenlik ağı):
  1. Dal: `task/leakage-check`. Kökte `pyproject.toml` (paket `aiops_rca`, `src/` düzeni, Python >= 3.11, çalışma zamanı bağımlılığı yok, `pytest` geliştirme bağımlılığı). `.venv` içinde `pip install -e ".[dev]"`; kurulum adımını Eren'e anlat.
  2. `src/aiops_rca/leakage.py`: verilen klasörü (`model_view`) tarar. Bütün JSON metin değerleri ve anahtarlar taranır, belirli alanlara bakılmaz. Klasör ve dosya adları da taranır. CLI: `python -m aiops_rca.leakage <klasör>`.
     Çıkış kodu: 0 temiz, 1 sızıntı var, 2 girdi hatası. Fonksiyon/sınıf adlarını öner, Eren onaylasın.
  3. Kurallar kodda, her biri `OTEL_DEMO.md`'deki satıra yorumla bağlı:
     - Flag adları (`src/flagd/demo.flagd.json`'daki 18 anahtarın tamamı): büyük/küçük harften bağımsız; camelCase, `snake_case`, `kebab-case` biçimleri.
     - `feature flag` ifadesi her ayraçla (`feature_flag`, `feature.flag`, `feature-flag`, `Feature Flag`).
     - `flagd`, `flagservice`, `ofrep` (büyük/küçük harften bağımsız).
     - `/feature` yolu (`/features`, `/featured` hariç).
     - Envoy erişim logunda yanıt bayrağı alanında `DI` (sadece o alan; kelime içi `DI` değil).
     - `service.name` (veya `container.name`) ∈ {`flagd`, `flagd-ui`, `load-generator`}.
     - Kalıba girmeyen bilinen ifadeler: `lock contention scenario`.
  4. Sahte dosyalar `tests/fixtures/leakage/`: collector `file` exporter biçimi (her satır bir OTLP JSON isteği: `resourceSpans` / `resourceMetrics` / `resourceLogs`).
  - Bitti ölçütü (testler önce yazılır, sonuca göre değiştirilmez):
    1. `OTEL_DEMO.md` sızıntı tablosundaki her satır için en az bir sahte dosya var ve test her birinde bulgu üretiyor.
    2. Normal trafik + gerçekçi belirtiler (payment `Invalid token`, gecikme, `cache miss`, hata durumları) içeren temiz dosyada sıfır bulgu.
    3. Yanlış alarm yok: Envoy'un başka bayrakları (`UF`, `-`), kelime içinde `DI` (`DISCOUNT`), `features`/`featured`, "payment failed" gibi gerçek belirti mesajları.
    4. Boş klasör, okunamayan dosya, geçersiz JSON → çıkış kodu 2; asla "temiz" sayılmaz.
    5. Adında flag adı geçen klasör veya dosya yakalanıyor.
    6. Her bulgu: dosya, satır, sinyal türü, servis adı, JSON yolu, kural.
    7. `pytest` yeşil; çalışma zamanında sadece standart kütüphane.
  - Sonra yapılacak (bu kartın dışında, yeni makinede): `positive_control` — süzme kapalı gerçek snapshot'ta her senaryoda en az bir bulgu, süzme açıkken sıfır. Yeni bir sızıntı biçimi çıkarsa önce `OTEL_DEMO.md`'ye, sonra teste eklenir.
  5. `ARCHITECTURE.md`: diyagramı yeni veri akışına göre güncelle (collector → dosya + kalıcı izleme sistemi, sızıntı süzmesi, snapshot dosyadan kesilir; "flagd filtresi" ve "PromQL ile snapshot kaydedici" eskidi). Dosya tablosuna yeni dosyaları ekle.
- Dikkat:
  - Sahte dosyalar koddan okunmuş tahmine dayanıyor; gerçek telemetride biçim farklı çıkabilir. Bu kart döngüseldir, `positive_control` yapılana kadar "doğrulandı" sayılmaz.
  - Test sadece sızıntıyı arar; aşırı süzmenin belirtiyi silmesini yakalamaz (collector kartında ayrı kontrol).
  - Snapshot klasör yapısı henüz kararlaştırılmadı; dedektör sadece "bir klasör" alır, yapı varsayımı yapma.
  - Dosya yazarken PowerShell yazma komutlarını kullanma (CRLF).

## 2026-10-15 · Uygulama → Planlama (sızıntı testi)
- Yapılan (`task/leakage-check`, 5 commit):
  - Planlamanın commit edilmemiş docs değişiklikleri ilk commit olarak alındı. Kartta 4 dosya yazıyordu, değişen 7'ydi: ad değişikliği `PROJECT`, `ARCHITECTURE` ve `INCIDENT_CATALOG`'a da dokunmuştu.
  - `pyproject.toml` + `src/aiops_rca/` iskeleti; `.venv` kuruldu. `.gitignore`'a `.pytest_cache/` ve `*.egg-info/` eklendi.
  - Önce testler yazıldı (kırmızı), sonra `src/aiops_rca/leakage.py`. Sonuç: 190 test yeşil, test dosyası sonradan değiştirilmedi. Kart ölçütlerinin 7'si de testte.
    Eren'in ekleri: sahte dosya nötr adla (`model_view/data.jsonl`) taranıyor ve bulgunun içerikten geldiği, satırı ve `json_path`'i doğrulanıyor;
    `excluded_service` hem `service.name` hem `container.name`'e bakıyor (baştaki `/` atılıyor); Envoy biçimine uymayan frontend-proxy logunda yedek `DI` kontrolü var.
  - Testlerin gerçekten bir şey sınadığı kontrol edildi: kod 8 yerden bilerek bozuldu (yedek DI kontrolü, sol sınır, container.name, bayrak alanı, ad taraması, boş girdi, `/` atma, features/featured istisnası). Her birinde en az bir test kırmızıya döndü.
  - 18 flag adı upstream 3.1.0 `demo.flagd.json` ile karşılaştırıldı, `OTEL_DEMO.md` ile aynı.
  - Program çıktıları İngilizce (Eren'in kararı, DECISIONS.md). Küçük teknik kararlar DECISIONS.md'ye, isimler GLOSSARY.md'ye, dosyalar ve yeni veri akışı ARCHITECTURE.md'ye yazıldı.
- Beklenen:
  - Eren: `task/leakage-check` PR'ını açıp birleştirir.
  - Planlama: sıradaki kart (PROJECT.md'ye göre CI iskeleti). Snapshot klasör adlarının sızıntı kuralı (üst klasörler taranmıyor) ayrıca karara bağlanacak.
- Dikkat:
  - Envoy erişim logu ayrı öznitelikler halinde gelmiyor: `%RESPONSE_FLAGS%` log gövdesindeki tek bir metnin içinde, konumla ayrıştırılıyor (`envoy.tmpl.yaml`, 3.1.0). Gerçek logda biçim farklı çıkarsa yedek kontrol devreye girer, ama bu yalnızca `service.name = frontend-proxy` olan loglarda çalışır.
  - Sahte dosyaların bazı ayrıntıları tahmin: load-generator'ın OFREP'i `flagd:8016` üzerinden doğrudan çağırdığı, MetricsHook metrik adları, docker_stats `container.name` biçimi. `positive_control` bu tahminleri gerçek veriyle sınayacak.
  - "Okunamayan dosya" testi Windows'ta dosya izniyle değil, `Path.read_bytes`'ın `PermissionError` fırlatacak şekilde değiştirilmesiyle (`monkeypatch`) yapılıyor; ayrıca geçersiz UTF-8 testi var.
  - Sahte dosyaları üreten betik repoya girmedi, sadece `.jsonl` çıktıları var. Gerekirse `tools/` altına alınabilir.
  - `pytest>=8` sadece alt sınır, kurulan sürüm 9.1.1. CI kartında sürüm sabitleme kararı gerekebilir.
  - `tools/api_smoke_test.py` çıktısı hâlâ Türkçe (yeni karar sadece bundan sonrası için).
  - Repo kökünde commit edilmemiş artık dosyalar duruyor: `eol_test.txt`, `lf_test.txt` (satır sonu testlerinden kalma). Silinmedi; silmek Eren'in onayıyla.

## 2026-10-16 · Planlama → Uygulama (CI iskeleti)
- Yapılan: CI kararları verildi (DECISIONS.md, 2026-10-16). Repo açık (public).
- Beklenen:
  - Amaç: her PR'da ve main'e her push'ta testler GitHub'ın temiz Linux makinesinde otomatik çalışsın; "bende çalışıyor" yanılgısı yakalansın.
  1. Dal `task/ci-skeleton`.
  2. `pyproject.toml`: `[dev]` içinde `pytest>=8` → `pytest==9.1.1`.
  3. `.github/workflows/` altında tek workflow:
     - Tetik: `pull_request` ve `push` (sadece `main`).
     - `permissions: contents: read`; gizli anahtar kullanılmaz; `timeout-minutes` konur (takılan iş dakika harcamasın).
     - `actions/checkout` ve `actions/setup-python` commit SHA'sıyla, yanına sürüm yorumu. SHA resmî sürüm etiketinden alınır ve `git ls-remote` ile doğrulanır.
     - Python 3.11, `ubuntu-latest`.
     - Test işi: `pip install -e ".[dev]"`, sonra `pytest`.
     - Çalışma zamanı kontrolü: ayrı, boş bir sanal ortama ekstrasız `pip install .`; sonra `clean_symptoms.jsonl` geçici bir klasöre kopyalanıp `python -m aiops_rca.leakage <klasör>` çalıştırılır, çıkış kodu 0 beklenir. Bu, "çalışma zamanında sadece standart kütüphane" kuralını makineyle denetler.
     - Workflow dosyası, workflow adı ve job adları Eren'e önerilir. Job adı önemli: dal koruma kuralı zorunlu kontrolü bu adla seçer.
  4. `ARCHITECTURE.md` dosya tablosu, `GLOSSARY.md` (onaylanan adlar), `PROJECT.md` DevOps tablosunda CI satırı ve Şu an.
- Bitti ölçütü (önce yazıldı, sonuca göre değişmez):
  1. PR'da ve main'e push'ta CI çalışıyor; şu anki testlerle yeşil.
  2. Kasıtlı kırmızı: ayrı bir dalda bir test bilerek bozulur, PR açılır, CI kırmızı olur. PR birleştirilmeden kapatılır; dalın silinmesi Eren'in onayıyla. Kırmızı koşunun bağlantısı HANDOFF'a yazılır.
  3. Hiç test toplanmazsa CI kırmızı (pytest çıkış kodu 5). Workflow'da bu kodu yutan bir şey olmamalı (`|| true`, `continue-on-error` yok).
  4. Ekstrasız kurulumla sızıntı CLI'ı temiz dosyada 0 dönüyor.
  5. Workflow'da gizli anahtar yok, izin sadece okuma.
  6. Koşu süresi HANDOFF'a yazılır.
- Sonra (Eren, GitHub ayarları): ilk yeşil koşudan sonra main için dal koruma kuralı, zorunlu kontrol = test job'u.
- Dikkat:
  - Repo açık: CI günlüğü herkese açık. Ortam değişkenlerini ya da makine bilgisini yazdıran adım ekleme.
  - Dependabot, kilit dosyası, imaj derleme, Windows koşucusu bu kartın dışında; gerekirse not et.
  - `tools/api_smoke_test.py`'ye dokunma, CI'a ekleme.
  - Dosya yazarken PowerShell yazma komutlarını kullanma (CRLF).

## 2026-10-16 · Planlama → Eren (makine değişimi)
- Yapılan: Taşıma listesi hazırlandı. CI kartı bittikten sonra, yeni karta geçmeden makine değişecek.
- Beklenen:
  - Eski makinede, geçmeden önce:
    1. CI kartı tamamen bitmiş: PR birleşti, kasıtlı kırmızı PR kapatıldı, dal koruma açıldı.
    2. `git status` temiz; `git log --branches --not --remotes` boş.
    3. Kişisel yedek (USB veya kişisel depolama, paylaşılan klasör değil): kişisel notlar (CC_mem), `~/.claude/CLAUDE.md`, `~/.claude/skills/proje_akisi/`, `~/.claude/settings.json`, isteğe bağlı `~/.claude/projects/` (sohbet geçmişi ve hafıza).
    4. Kopyalanmaz: `~/.claude/.credentials.json`, `~/.claude.json` (giriş bilgisi), API anahtarları, `.venv`, `__pycache__`, `*.egg-info`.
  - Yeni makinede:
    5. Git, Python 3.11, Claude Code kurulur, giriş yapılır. Repo aynı yola klonlanır: `C:\Users\erenb\cerebrum2\aiops_rca`. Kullanıcı adı aynıysa Claude'un hafıza klasörü de eşleşir.
    6. Yedekler aynı yerlerine konur; API anahtarları ayrı bir PowerShell penceresinden User düzeyinde girilir.
    7. Doğrulama: `.venv` + `pip install -e ".[dev]"`, `pytest` yeşil (190 test). Planlama oturumu `cerebrum2`'de açılır, "nerede kaldık" sorusuna `PROJECT.md`'den doğru cevap vermeli.
  - Eski makinede, doğrulamadan sonra:
    8. API anahtarı ortam değişkenleri silinir, Claude'dan çıkılır (`/logout`), GitHub girişi Windows Kimlik Bilgisi Yöneticisi'nden kaldırılır, sonra makine silinir.
    9. Makine tamamen silinmeden elden çıkacaksa API anahtarları yenilenir.
- Dikkat:
  - Asıl risk eski makinede: 8. adım atlanırsa anahtarlar ve giriş bilgileri makineyle birlikte gider.
  - Yeni makine şirketinse kişisel dosyaları koymadan önce şirket kuralına bakılır.
  - Yeni makinede planlamanın ilk konusu: Docker kurulumu (WSL içinde Docker Engine mi, Docker Desktop mı), `OTEL_DEMO.md` "Açık kararlar".

## 2026-10-16 · Uygulama → Planlama (CI iskeleti)
- Yapılan (`task/ci-skeleton`, PR #4):
  - `pytest==9.1.1`; `.github/workflows/ci.yml` (workflow `CI`, tek job `test`); `.gitignore`'a `build/` (yerelde `pip install .` bırakıyor).
  - Eklentiler: `actions/checkout` v7.0.1 `3d3c42e5aac5ba805825da76410c181273ba90b1`, `actions/setup-python` v7.0.0 `5fda3b95a4ea91299a34e894583c3862153e4b97`. İkisi de en güncel resmî sürüm (2026-07-20); SHA'lar `git ls-remote` ile alındı, hafif etiket olduğu için doğrudan commit'i gösteriyor.
  - Eren'in ekleri: kurulumdan önce ve sonra alınan `pip freeze --all` çıktıları karşılaştırılıyor; yeni ya da değişen tek satır `aiops_rca` olmalı. Düz `freeze` pip/setuptools/wheel'i göstermediği için `--all` kullanıldı. Yerelde sınandı: sahte bağımlılık (`iniconfig`) eklenince adım kırmızı oluyor. CLI geçici klasörün içinden çalışıyor ve kurulu kopyadan yükleniyor (yerelde `site-packages` yolu görüldü).
  - `persist-credentials: false` (onaylı).
- Bitti ölçütleri:
  1. PR koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/38914078552. Eren günlükte gördü: `190 passed`, yeni paket olarak sadece `aiops_rca @ file://...`, CLI `clean`. **main'e push koşusu birleştirmeden sonra doğrulanacak.**
  2. Kasıtlı kırmızı (PR #5, taban yanlışlıkla `main`, birleştirilmeden kapatıldı; `task/ci-red-check` Eren'in onayıyla silindi, commit'ler `refs/pull/5/head`'de duruyor):
     (a) `test_finding_fields` bozuldu → https://github.com/erenbezek/aiops_rca/actions/runs/38915091150, günlükte `Process completed with exit code 1.`
     (b) `pytest -k no_such_test` → https://github.com/erenbezek/aiops_rca/actions/runs/38915191850, günlükte `Process completed with exit code 5.`
     İkisinde de kırmızı adım "Run tests", sonraki adımlar atlandı.
  3. Hiç test seçilmeyince kırmızı: (b) ile gösterildi; workflow'da `|| true` ve `continue-on-error` yok.
  4. Ekstrasız kurulumla CLI temiz dosyada 0: yeşil koşuda adım başarılı, günlükte `clean`.
  5. Gizli anahtar yok, izin `contents: read`.
  6. Süre: toplam 26 sn (dev kurulum 11 sn, pytest 1 sn, ekstrasız kurulum kontrolü 8 sn). Kırmızı koşular 13 ve 11 sn.
- Beklenen:
  - Eren: PR #4'ü birleştirir; main push koşusu yeşilse dal koruma kuralını açar (main, zorunlu kontrol `test`).
  - Uygulama ya da planlama: main push koşusunun bağlantısını bir sonraki kayda yazar.
- Dikkat:
  - **`ubuntu-latest` 2026-10-19'dan itibaren Ubuntu 26'ya geçiyor** (koşulardaki GitHub notu). Kod değişmeden CI'ın ortamı değişecek; "kod değişmeden kırmızıya dönmesin" kararıyla çelişebilir. İmajı sürüme sabitlemek (ör. `ubuntu-24.04`) planlamanın kararı.
  - Açık repoda bile adım günlükleri API'den giriş yapmadan okunamıyor (403). Durum, süre ve hata notları (annotations) okunabiliyor; test sayısı gibi ayrıntılar için günlüğe tarayıcıdan bakılmalı.
  - Kurulum kontrolünün kalan boşluğu: venv'de hazır gelen paketlerden (`pip`, `setuptools`) biri çalışma zamanı bağımlılığı yapılırsa satır değişmez ve kontrol bunu görmez. Bu durumu `test_leakage_imports_only_stdlib` yakalıyor.
  - Kasıtlı kırmızı için PR'ın tabanı `task/ci-skeleton` olmalıydı, `main` seçildi. PR kapatıldığı için zararı yok.
  - Düzeltme: 2026-10-15 kaydındaki `eol_test.txt` ve `lf_test.txt` artık dosyaları Eren'in onayıyla silindi.
  - Kart dışı, yapılmadı: Dependabot, kilit dosyası, Windows koşucusu.

## 2026-10-16 · Planlama → Uygulama (CI Ubuntu sabitleme)
- Yapılan: CI iskeleti kapandı. main push koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/38916248086 (`91a9ba9`). main'de dal koruması açık (GitHub API `protected: true`; zorunlu kontrolün `test` olduğunu Eren ayarlardan teyit eder). Kararlar DECISIONS.md'de (2026-10-16): `ubuntu-24.04`, HANDOFF git'te kalır, proje Ubuntu'da.
- Beklenen:
  1. Dal `task/ci-ubuntu-pin`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, OTEL_DEMO, PROJECT).
  2. `.github/workflows/ci.yml`: `runs-on: ubuntu-latest` → `ubuntu-24.04`. Başka değişiklik yok.
  3. Hafızandaki "HANDOFF git dışına" notunu sil ya da güncelle: karar tersine döndü (DECISIONS 2026-10-16).
- Bitti ölçütü: PR koşusu yeşil ve günlükte koşucu imajı Ubuntu 24.04 görünüyor; main push koşusu yeşil; bağlantılar HANDOFF'a yazılır.
- Dikkat: 2026-10-19'dan önce birleşmeli.

## 2026-10-16 · Planlama → Eren (taşıma listesine düzeltme)
Önceki taşıma kaydı Windows'a göre yazılmıştı; proje Ubuntu'da çalışacak. Değişenler:
- Yedeğe eklenecek: uygulama oturumunun hafızası (`~/.claude/projects/C--Users-erenb-cerebrum2-aiops-rca/memory/`). Ev klasörü hafızası (`C--Users-erenb/memory/`, başka projeler) Eren'in kararı. Yedek zip'i `Downloads`'tan USB'ye ya da kişisel depolamaya taşınır.
- Yol: repo `~/cerebrum2/aiops_rca` olarak klonlanır (5. madde yerine). Planlama oturumu `~/cerebrum2`, uygulama `~/cerebrum2/aiops_rca` içinde açılır.
- Claude hafıza klasörünün adı yoldan türüyor, Linux'ta otomatik eşleşmez: her oturum bir kez açıldıktan sonra `~/.claude/projects/` altında oluşan yeni klasörün `memory/` alt klasörüne eski hafıza dosyaları kopyalanır.
- `~/.claude/CLAUDE.md`, `skills/proje_akisi/`, `settings.json` aynı göreli yerlerine konur. `settings.json`'daki durum satırı `jq` ister.
- `~/.claude/CLAUDE.md`'deki Core.md yolu Windows yolu; CC_mem'in nereye konacağına göre güncellenir.
- API anahtarları (6. madde): Ubuntu'da Windows'taki "User düzeyi ortam değişkeni" yok. Saklama yöntemi yeni makinede karara bağlanır; anahtar sohbete ve repoya yine girmez.
- Python: Ubuntu 24.04'ün Python'u 3.12, proje ve CI 3.11. Yeni makinenin ilk planlama konularından biri.
- 7. maddedeki doğrulama aynı: `pytest` yeşil (190 test), planlama "nerede kaldık"a `PROJECT.md`'den doğru cevap veriyor.
- Kurulum öncesi (dual boot): BitLocker kurtarma anahtarı alınır, Hızlı Başlatma kapatılır.

## 2026-10-16 · Planlama → Planlama (CI Ubuntu sabitleme, sonuç)
- Yapılan (`task/ci-ubuntu-pin`, PR #6): Eren'in isteğiyle kartı planlama uyguladı (makine değişimi öncesi son iş; rol istisnası, yeni makinede roller yine ayrı).
  - `ci.yml`: `runs-on: ubuntu-latest` → `ubuntu-24.04`, başka değişiklik yok.
  - Uygulama oturumunun hafızasından "HANDOFF git dışına" notu silindi (karar tersine döndü).
- Bitti ölçütü:
  - PR koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/38921084079 (`e72e5eb`, job 14 sn). API'de job etiketi `ubuntu-24.04`; Eren günlükte "Set up job" adımında Ubuntu 24.04 gördü. Bütün adımlar başarılı (testler, ekstrasız kurulum, sızıntı CLI'ı).
  - main push koşusu birleştirmeden sonra; bağlantısı yeni makinedeki ilk planlama kaydına yazılır.
- Dikkat:
  - Uygulamanın kalan hafıza notu (`explicit-git-add`) hâlâ silinmiş `lf_test`/`eol_test` dosyalarını gerekçe gösteriyor; kural geçerli, gerekçe eski. Yeni makinede güncellenir.
  - `ubuntu-24.04` imajının da bir destek sonu var; GitHub kaldırmadan önce duyurur, o zaman yeni bir sabitleme kararı gerekir.

## 2026-10-17 · Planlama → Planlama (sahte dosya üreticisi repoya)
- Yapılan (`task/fixture-generator`; Eren'in isteğiyle planlama uyguladı, makine değişimi öncesi):
  - Sızıntı testinin sahte dosyalarını üreten betik uygulama oturumunun Windows geçici klasöründeydi, makine değişince kaybolacaktı. `tools/gen_leakage_fixtures.py` olarak repoya alındı; sadece başına kullanım satırı eklendi.
  - `OTEL_DEMO.md`: 3.1.0 etiketinin commit'i yazıldı (`dedc0178…`; etiket taşınırsa fark edilsin).
  - `ARCHITECTURE.md` dosya tablosu, `GLOSSARY.md` (`gen_leakage_fixtures`, Eren onaylı).
  - main'deki CI koşusu (PR #6 sonrası) yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/38968357919 (`a5a35d6`).
- Bitti ölçütü: betik boş klasöre çalıştırılınca `tests/fixtures/leakage/` altındaki 16 dosyanın bayt bayt aynısı çıkıyor (yerelde `diff -r` ile gösterildi); `pytest` 190 yeşil; PR koşusu yeşil.
- Dikkat:
  - Sahte dosyalar artık elle değil betikle değiştirilir. Bunu zorlayan bir test yok (betik çıktısı ile repodaki dosyaları karşılaştıran test eklenebilir; ayrı karar).
  - `positive_control` gerçek telemetride biçim farkı gösterirse düzeltme bu betikte yapılır.

## 2026-10-17 · Planlama → Planlama (yeni makine, Python 3.12)
- Taşıma doğrulaması (Ubuntu 24.04, yeni makine): repo `~/cerebrum2/aiops_rca`a klonlandı, `.venv` (sistem Python 3.12.3) + `pip install -e ".[dev]"`, `pytest` 190 yeşil. Hafıza klasörleri Linux yollarına kopyalandı.
- Yapılan (`task/ci-python-312`; Eren'in kararı): CI ve paket Python 3.12.
  - `ci.yml`: `python-version: "3.11"` → `"3.12"`, başka değişiklik yok.
  - `pyproject.toml`: `requires-python = ">=3.12"` (3.11 artık test edilmiyor). `ARCHITECTURE.md` dosya tablosu, `DECISIONS.md` satırı, `PROJECT.md` "Şu an".
- Bitti ölçütü: PR koşusu yeşil ve "Set up Python" adımında 3.12.x; yerelde `pytest` 190 yeşil.
- Dikkat:
  - Kendi Python servisimin Docker imajı yazılırken taban imaj da 3.12 seçilmeli (yerel, CI ve imaj aynı sürüm).

## 2026-10-18 · Planlama → Uygulama (Docker Engine kurulumu)
- Yapılan (planlama, 2026-10-17/18):
  - PR #8 (Python 3.12) birleşti. PR koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/38973917301; main push koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/38974082044 (`fb0cb6c`).
  - Geçiş dönemi bitti: PR #6, #7, #8'i planlama uyguladı (makine değişimi istisnası). Bundan sonra roller ayrı; kartı uygulama uygular.
  - API anahtarları yeni makinede: `~/.config/aiops_rca/keys.env` (izin 600), `~/.bashrc` yüklüyor (DECISIONS 2026-10-18). `tools/api_smoke_test.py`: Groq gpt-oss-120b ve Gemini 3.5 Flash Lite GEÇTİ; Gemma 4 31B KALDI (Google 500/503, projede kullanılmıyor). Eski anahtarları Eren konsoldan iptal ediyor.
  - Docker Engine kararı (DECISIONS 2026-10-18), OTEL_DEMO "Açık kararlar"da kapatıldı.
- Beklenen:
  1. Dal `task/docker-engine`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, OTEL_DEMO, PROJECT).
  2. Docker Engine'i Docker'ın resmî Ubuntu kurulum belgesindeki apt deposu yöntemiyle kur: `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`. Önce çakışan paket (`docker.io`, `podman-docker` vb.) var mı bak; varsa silmeden Eren'e sor.
  3. Kullanıcıyı `docker` grubuna ekle.
  4. sudo isteyen komutları Eren `!` ile kendisi çalıştırır; parola sohbete girmez.
- Bitti ölçütü:
  - Oturum kapatılıp açıldıktan (ya da yeniden başlatmadan) sonra `docker run --rm hello-world` sudo'suz çalışıyor.
  - `systemctl is-enabled docker` → `enabled` (açılışta başlıyor).
  - `docker version` (istemci + sunucu) ve `docker compose version` çıktıları bu dosyaya yazıldı.
  - Repoda sadece docs değişti; kod ve CI değişmedi. PR koşusu yeşil.
- Dikkat:
  - `docker` grubu root eşdeğeri; bilerek kabul edildi.
  - Yayınlanan portlar `ufw`'yu atlar. Bu kartta port açılmıyor; `127.0.0.1:` bağlaması OTel Demo kartında.
  - Docker'ın varsayılan log sürücüsü (`json-file`) sınır koymaz; gece boyu vaka üretiminde disk dolabilir. Bu kartta değiştirme; OTel Demo kartında karar verilecek, gözlemin varsa yaz.
  - Kart dışı: rootless Docker, Docker Desktop, Kubernetes.

## 2026-10-18 · Planlama → Planlama (sıradaki: lokal model hız ölçümü)
- Makine: Intel Core 5 210H (4 performans + 4 verimlilik çekirdeği, 12 iş parçacığı; AVX2, AVX-VNNI, AVX-512 yok), 16 GB RAM, sadece Intel entegre grafik, 311 GB boş disk. RAM'in tek/çift kanal olduğu bilinmiyor (`sudo dmidecode -t memory`).
- Tahmin (ölçülmedi, 4 bit): ~3B üretim 12–20 token/sn, ~7–8B 6–9 token/sn; 6K token girdiyi okuma 3B'de ~1 dk, 7B'de ~2–4 dk. Darboğaz girdi uzunluğu; ham log koşulu süre/bağlam sınırına takılabilir.
- Docker'dan sonra kart: 2–3 model boyutunda girdi işleme ve üretim hızı ölçümü (çekirdek ayarı dahil). Önce: araç kararı (llama.cpp / Ollama; yeni bağımlılık, Eren onayı) ve geçme kriteri (vaka başına süre bütçesi) ölçümden önce yazılır. Model seçimi ölçümden sonra.

## 2026-10-18 · Uygulama → Planlama (Docker Engine kurulumu, sonuç)
- Yapılan (`task/docker-engine`):
  - İlk commit planlamanın docs değişiklikleri (`8e92760`).
  - Çakışan paket yoktu (`docker.io`, `docker-compose`, `podman-docker`, `containerd`, `runc`, snap Docker); silinen bir şey yok.
  - Kurulum Docker'ın resmî belgesine göre (docs.docker.com/engine/install/ubuntu, 2026-10-18'de kontrol edildi): anahtar `/etc/apt/keyrings/docker.asc`, depo `/etc/apt/sources.list.d/docker.sources` (deb822 biçimi, `noble`, `amd64`). sudo komutlarını Eren ayrı terminalde çalıştırdı.
  - Paketler: `docker-ce` / `docker-ce-cli` 5:29.9.1, `containerd.io` 2.4.2, `docker-buildx-plugin` 0.38.0, `docker-compose-plugin` 5.6.0. `eren` `docker` grubunda.
- Bitti ölçütü (yeniden başlatmadan sonra ölçüldü):
  - `docker run --rm hello-world` sudo'suz: "Hello from Docker!", çıkış kodu 0. GEÇTİ.
  - `systemctl is-enabled docker` → `enabled`; `is-active` → `active`. GEÇTİ.
  - `docker version`: istemci ve sunucu Docker Engine - Community 29.9.1, API 1.56; containerd v2.4.2, runc 1.5.2, docker-init 0.19.0; linux/amd64. GEÇTİ.
  - `docker compose version` → `Docker Compose version v5.6.0`. GEÇTİ.
  - Repoda sadece `docs/` değişti. PR #9 koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39078550856 (2. commit).
- Dikkat:
  - Log sürücüsü `json-file`, `/etc/docker/daemon.json` yok (Docker varsayılanı, sınır yok). Kök `/var/lib/docker` sistem diskinde (`/`, 310 GB boş). Depolama `overlayfs`, cgroup `systemd` v2. Sınır kararı OTel Demo kartında.
  - `hello-world` imajı yerelde kaldı (birkaç KB); istenirse `docker image rm hello-world`.
  - Grup değişikliği açık oturumlara yansımaz; Claude Code dahil süreçler yeniden girişten sonra açılmalı.

## 2026-10-18 · Planlama → Uygulama (OTel Demo kurulumu)
- Yapılan (planlama):
  - Docker kartı doğrulandı (planlama makinede tekrar ölçtü, hepsi GEÇTİ). PR #9 main push koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39079803231 (`742e33f`). Not: `docker-ce-rootless-extras` 5:29.9.1 de kurulu (`docker-ce`'nin önerdiği paket, otomatik geldi); rootless kullanılmıyor.
  - Kararlar (DECISIONS 2026-10-18): demo repo dışında betikle; demo imajları `3.1.0`'a sabit; log sınırı iki katman; host portları sadece `127.0.0.1`'de üç port; kalıcı veri için üst sınır kuralı ve 30 GB disk eşiği. Bulgular OTEL_DEMO.md "Log, port ve imaj sürümü".
  - Onaylı yeni isimler (GLOSSARY'ye uygulama yazar): `tools/otel_demo.sh` (demoyu getirir, başlatır, durdurur), `deploy/otel-demo/compose.extras.yaml` (bizim compose katmanımız; `deploy/` yeni klasör).
- Beklenen:
  1. Dal `task/otel-demo-setup`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, OTEL_DEMO, PROJECT).
  2. Makine: `/etc/docker/daemon.json` (şu an yok, 2026-10-18 kontrol edildi):
     `{"log-driver": "json-file", "log-opts": {"max-size": "5m", "max-file": "2"}, "ip": "127.0.0.1"}`
     ardından `sudo systemctl restart docker`. sudo komutlarını Eren `!` ile çalıştırır. İçerik bu kayda ve OTEL_DEMO.md'ye yazılır (makinede duruyor, repoda değil).
  3. `tools/otel_demo.sh` (bash, `set -euo pipefail`; ekran çıktısı İngilizce, yorumlar Türkçe):
     - `fetch`: `~/cerebrum2/otel-demo` yoksa etiket 3.1.0'ı `-c core.autocrlf=false` ile klonlar; `HEAD` = `dedc0178918e260823323b8d95005a8cb924b007` değilse çıkış ≠ 0. Klasör varsa: doğru commit ve temiz çalışma kopyasıysa hiçbir şey yapmadan 0; değilse hata verir, **silmez, düzeltmez**.
     - `up`: önce `fetch`'in doğrulamasını yapar; minimal mod: demonun `compose.yaml` + `compose.observability.yaml` + bizim `deploy/otel-demo/compose.extras.yaml` (demonun boş `compose.extras.yaml`'ının yerine), `--env-file .env --env-file .env.override`; `DEMO_VERSION=3.1.0` açıkça verilir (yöntem uygulamada).
     - `down`: durdurur; volume silmez.
  4. `deploy/otel-demo/compose.extras.yaml`: `frontend-proxy` ve `flagd-ui`'ye 5 MB × 2 log; bütün servislerde `ports: !reset []`; sadece `127.0.0.1:8080:8080` (`frontend-proxy`), `127.0.0.1:9090:9090` (Prometheus), `127.0.0.1:9200:9200` (OpenSearch). Envoy admin 10000 kapalı.
  5. ARCHITECTURE.md dosya tablosu ve diyagram; GLOSSARY.md'ye iki isim; OTEL_DEMO.md'ye çalıştırma komutu ve ölçümler.
- Bitti ölçütü:
  - `fetch`: boş durumda klonlar; ikinci çalıştırma 0 ve değişiklik yok; kasıtlı kırmızı: klonda `git checkout HEAD~1` → çıkış ≠ 0, klasör yerinde (sonra geri alınır).
  - `docker compose config` (betiğin dosya ve env'leriyle): demo imajlarının hepsi `3.1.0-<servis>`, hiçbiri `latest`; yayınlanan port sadece üç tane ve `host_ip: 127.0.0.1`; `frontend-proxy` ve `flagd-ui`'de log 5m/2.
  - `up` sonrası 10 dk içinde bütün konteynerler `running` (healthcheck'i olanlar `healthy`). `ss -tln`: Docker'a ait hiçbir port `0.0.0.0` ya da `[::]` üzerinde değil. `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/` → 200; `/jaeger/ui`'de trace listesi boş değil; `/grafana` açılıyor.
  - `daemon.json`: compose dışı bir test konteynerinde (`docker run --rm -d -p 5000 busybox sleep 60` gibi) `docker inspect` → LogConfig `max-size 5m, max-file 2`, port `127.0.0.1`'e bağlı.
  - Ölçümler kayda: `docker stats --no-stream` (toplam bellek, en büyük 5 konteyner), demo açıkken `free -h`, `docker system df` (imaj boyutu), ilk `up` süresi.
  - `pytest` 190 yeşil; PR koşusu yeşil.
- Dikkat:
  - Kart dışı: collector sızıntı süzmesi ve dosya çıkışı, Jaeger kalıcılığı ve saklama süreleri, `positive_control`, kendi Python servisi, hata enjeksiyonu, `compose.full.yaml` (Kafka). Bu kartta snapshot alınmaz.
  - Upstream klonda hiçbir dosya değiştirilmez; `fetch`'in temizlik kontrolü bunu doğrular.
  - Minimal mod konteyner limit toplamı ~6,8 GB (16 GB RAM). Bellek yetmezse limitleri değiştirme; ölç, yaz, planlamaya bırak.
  - İlk `up` birkaç GB imaj indirir.
  - `!reset` Compose ≥ 2.24.4 ister (kurulu v5.6.0). `!reset` sonrası `ports` boş görünmüyorsa (ör. `docker compose config`'te eski port duruyorsa) dur ve yaz.
  - Betik CI'da çalışmaz (CI'da Docker yok); `shellcheck` kart dışı.

## 2026-10-18 · Planlama → Planlama (not: demo klonu flag değişikliğiyle kirlenir)
- Bulgu (commit `dedc0178`, `compose.yaml`): `flagd-ui` klondaki `./src/flagd` klasörünü `/app/data` olarak **yazılabilir** bağlıyor; `flagd` aynı klasörü `/etc/flagd` olarak okuyor. flagd-ui'den flag değiştirmek klondaki `src/flagd/demo.flagd.json`'u değiştirir.
- Sonuç: hata enjeksiyonu kartında klon kesin kirlenir; `tools/otel_demo.sh`'ın "klon temiz değilse hata" kuralı her enjeksiyondan sonra `up`'ı durdurur. OTel Demo kurulum kartında flag değiştirilmediği için beklenmiyor; uygulama `up` sonrası klonda `git status`'a bakar, kirlenme varsa durur ve yazar.
- Karar enjeksiyon kartından önce planlamada verilecek. Önerilen: flag dosyasının kopyası `deploy/otel-demo/` altında, `compose.extras.yaml`'dan `flagd` ve `flagd-ui`'ye bağlanır; upstream klon hiç yazılmaz, flag'lerin başlangıç hali repoda sabit kalır. Diğer seçenekler: temizlik kontrolünde bu dosyayı hariç tutmak; `down`'da dosyayı geri yüklemek.

## 2026-10-18 · Uygulama → Uygulama (OTel Demo kartı: ölçüm yöntemleri, ölçmeden önce)
- Kart ölçütleri değişmedi; aşağıdakiler nasıl ölçüleceğinin netleştirmesi (Eren onayı, 2026-10-18).
- Jaeger "trace listesi boş değil": arayüz sayfası trace olsa da olmasa da aynı HTML'i döndürür, bu yüzden API ile ölçülür:
  `curl -s 'http://127.0.0.1:8080/jaeger/ui/api/traces?service=frontend&limit=1' | jq '.data | length'` → ≥ 1. GEÇER; 0 ya da hata KALIR. `up`'tan sonraki 10 dk içinde ölçülür.
- Grafana "açılıyor": `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/grafana/api/health` → `200`.
- Mağaza: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/` → `200` (kartta yazılı olduğu gibi).
- Port kapatma: üç port tutulan serviste `ports: !override [...]` (`!reset` liste boşaltır, aynı yerde yeni port eklenemez); diğer servislerde `ports: !reset []`. `!reset` sadece minimal modda tanımlı servislere yazılır (`compose.yaml` + `compose.observability.yaml`); listede olmayan servis ek dosyada tanımsız yarım servis yaratır.
- Klon temizliği: `up` sonrası `git -C ~/cerebrum2/otel-demo status --porcelain` boş olmalı; değilse dur ve yaz, bu kartta çözülmez. Bilinen: `flagd-ui` `./src/flagd`'yi yazılabilir bağlıyor; enjeksiyon kartında klon kirlenecek, çözümü planlamada.
- `tools/otel_demo.sh config` (onaylı yeni komut): betiğin dosya ve env'leriyle `docker compose config` çıktısı; `docker compose config` ölçütleri bu komutla ölçülür.

## 2026-10-18 · Uygulama → Planlama (OTel Demo kurulumu, sonuç)
- Yapılan (`task/otel-demo-setup`):
  - `/etc/docker/daemon.json` (makinede): `{"log-driver": "json-file", "log-opts": {"max-size": "5m", "max-file": "2"}, "ip": "127.0.0.1"}`; `dockerd --validate` sonrası `systemctl restart docker` (Eren çalıştırdı).
  - `tools/otel_demo.sh` `fetch` / `up` / `down` / `config`; `deploy/otel-demo/compose.extras.yaml` (3 portta `!override`, 21 serviste `!reset []`; konteyner portu `.env` değişkeninden, host portu sabit).
  - Kart dışı küçük kararlar (Eren onayı): `verify_clone` `git --no-optional-locks status` kullanır (kontrol `.git/index`'i yazmasın); repo kökü kontrolü (`--show-toplevel` = `$DEMO_DIR`); `down` kirli klonda da çalışır; `up` bayrakları Makefile `start-minimal` ile aynı (`--force-recreate --remove-orphans --detach`).
  - ARCHITECTURE (diyagram: `otel` artık var; iki yeni düğüm, tablo), GLOSSARY (3 satır), OTEL_DEMO ("Çalıştırma" bölümü), PROJECT "Şu an".
- Bitti ölçütü (ölçüm yöntemleri bu dosyada ölçmeden önce yazıldı):
  - `fetch`: boş durumda klonladı (53 sn, 71 MB, HEAD `dedc0178`, `core.autocrlf=false`); ikinci çalıştırma 0, `.git` dahil hiçbir dosyanın mtime/boyutu değişmedi; `HEAD~1` → çıkış 1, klasör yerinde, geri alındı. Ek: fazladan dosya → 1; üst klasörde başka repo → 1 (doğru mesaj). GEÇTİ.
  - `config`: 18 demo imajının hepsi `3.1.0-<servis>`, `latest` yok (karşı kontrol: `DEMO_VERSION` verilmezse 18'i `latest-`); yayınlanan port sadece 8080, 9090, 9200, hepsi `host_ip: 127.0.0.1`; `frontend-proxy` ve `flagd-ui` log 5m/2, sınırsız servis kalmadı; ports/logging dışında upstream birleşik ayarla fark yok. GEÇTİ.
  - `up`: 25 konteyner `running`, healthcheck'i olan 19'u `healthy` (ikinci `up` sonrası da). `ss -tln`: Docker portları sadece `127.0.0.1` (8080, 9090, 9200). `/` → 200; Jaeger API `frontend` trace sayısı 1; `/grafana/api/health` → 200. GEÇTİ.
  - `up` sonrası klon `git status` boş (iki `up` sonrası). GEÇTİ.
  - `daemon.json`: `docker run --rm -d -p 5000 busybox sleep 60` → LogConfig `max-size 5m, max-file 2`, port `127.0.0.1:32768`. GEÇTİ.
  - `pytest` 190 yeşil. PR #10 koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39160253360 (`e82e6ef`).
- Ölçümler:
  - İlk `up` 15 dk 17 sn (917 sn): ~14,7 dk 12,2 GB imaj indirme, ~42 sn açılış; komut bittiğinde hepsi running/healthy. İmajlar inmişken `up` 83 sn.
  - `docker stats` (açılıştan ~2 dk sonra): toplam 2,87 GiB. En büyük 5: opensearch 860 MiB / 1 GiB, load-generator 583 MiB / 1,47 GiB, ad 223 MiB / 300 MiB, otel-collector 195 MiB / 400 MiB, flagd-ui 175 MiB / 200 MiB.
  - `free -h`: kullanılan 4,7 → 7,4 GiB, kullanılabilir 7,9 GiB, takas 150 MiB.
  - `docker system df`: imajlar 12,2 GB, isimsiz volume'ler 3 adet 66 MB; boş disk 310 → 299 GB.
- Dikkat:
  - 10 dk ölçütü `up` komutunun bitişinden sayıldı (açılış ~42 sn). Başlangıçtan sayılırsa ilk kurulum (imaj indirme dahil 15 dk 17 sn) kalır; kriter değiştirilmedi, okuma planlamanın kararı.
  - Yarım klon: `git clone` INT/TERM ve ağ hatasında klasörü kendisi siliyor; sadece KILL ya da elektrik kesintisinde yarım klasör kalır, o durumda `fetch` hata verir (silmez). Değişiklik gerekmedi (Eren).
  - Depolama kartı: kalıcılık isimli volume ile olmalı. Şu an OpenSearch her `up`'ta sıfırlanıyor (yeniden kurulumdan önceki belge sayısı 0). Prometheus verisi imajın isimsiz volume'ü (`/prometheus`) sayesinde `--force-recreate`'e dayanıyor (konteyner 21:33:08'de yeniden kuruldu, en eski örnek 21:31:03, volume kimliği aynı) ama bu tesadüfi; `down`/`up` sonrası ölçülmedi.
  - Collector kartı için: OpenSearch'te zaman damgası 0 (1970) olan loglar var (ilk ~4 dk'da 53 belge); zaman aralığına göre kesimde kaybolabilir.
  - Bellek sınırına yakın: flagd-ui %87, opensearch %84, ad %74 (açılıştan ~2 dk sonra, tek ölçüm). Limitler değiştirilmedi.
  - Demo kartın sonunda `down` ile kapatıldı; yerelde imajlar (12,2 GB), isimsiz volume'ler, `busybox` ve `hello-world` imajları duruyor.

## 2026-10-18 · Planlama → Planlama (OTel Demo kartı doğrulaması ve sonraki kartlara notlar)
- Doğrulama (planlama makinede tekrar ölçtü, PR #10 sonrası main `e3aa7b4`; main push koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39160713432):
  - `fetch` tekrar: çıkış 0, "nothing to do"; klon temiz.
  - `config --format json`: 25 servis; 18 demo imajının hepsi `3.1.0-*`; diğer 7 imaj sabit sürüm; yayınlanan port sadece 8080, 9090, 9200, hepsi `host_ip: 127.0.0.1`; 25 serviste log `max-size 5m`.
  - `up`: 34 sn; 60 sn sonra 25 `running`, 19 `healthy`, `unhealthy` yok; yeniden başlama 0, OOM yok. `ss -tln`: Docker'a ait sadece `127.0.0.1` 8080/9090/9200 (631 CUPS, 53 DNS sistemin). LAN IP'si (192.168.1.48) üzerinden 8080 erişilemiyor (ek kontrol). `/` 200, `/grafana/api/health` 200, Jaeger API `frontend` trace 1, Prometheus `/-/ready` 200, OpenSearch 200. `up` sonrası klon temiz. `down` çıkış 0.
  - Bellek (açılıştan ~1 dk sonra, tek ölçüm): grafana %86, opensearch %82, flagd-ui %81, ad %74.
- 10 dk ölçütünün okunması (Eren onayı): "imajlar indikten sonra açılış" (42 sn uygulamada, 34 sn planlamada) → GEÇTİ. İlk kurulum indirme dahil 15 dk 17 sn (12,2 GB), ayrıca kayıtlı. Ölçüt yazılırken belirsizdi; okuma ölçümden önce önerildi, onay ölçümden sonra geldi.
- Sonraki kartlar için:
  - **Depolama kartı (isimsiz volume birikmesi):** her `up`/`down` döngüsü yeni isimsiz volume bırakıyor, eskiler silinmiyor: uygulamanın kaydında 3 volume / 66 MB, planlamanın bir döngüsünden sonra 6 / 139,6 MB (~70 MB/döngü). Gece koşusu vaka başına yeniden başlatırsa GB'larca birikir (DECISIONS 2026-10-18 üst sınır kuralı). Çözüm isimli volume'ler; mevcut isimsiz volume'ler şimdilik silinmedi (Eren'in kararı).
  - **Vaka üretim kartı (vaka geçerliliği):** bazı servisler bellek limitine yakın (yukarıda). Vaka sırasında hedef dışı bir servis kendiliğinden yeniden başlar ya da OOM olursa doğru cevap etiketi yanlış olur. Ölçüt önerisi: kaydedici her vakada konteynerlerin `RestartCount` ve `State.OOMKilled` değerini vaka öncesi/sonrası kaydeder; hedef dışı beklenmeyen yeniden başlama varsa vaka geçersiz sayılır ve sete girmez.

## 2026-10-20 · Planlama → Uygulama (lokal model hız ölçümü)
- Yapılan (planlama): DECISIONS 2026-10-20: llama.cpp (sabit Docker imajı), uzun koşu makine sınırları, süre bütçesi. Makine durumu (2026-10-20 okundu): `x86_pkg_temp` ve `coretemp` okunuyor, NVMe sıcaklığı okunuyor; `BAT0/charge_control_end_threshold` var, değer 100; güç profili `balanced` (`quiet`/`balanced`/`performance`); `turbostat` kurulu (sudo ister); okuma anında makine bataryadaydı.
- Amaç: model seçiminden önce bu makinede hangi model boyutunun süre bütçesine sığdığını ölçmek. Kalite ölçülmez; model seçimi bu ölçümden sonra ayrı kararla.
- Beklenen:
  1. Dal `task/local-model-bench`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, PROJECT; ayrıca main'de bekleyen 2026-10-18 doğrulama kaydı).
  2. **Şarj sınırı %80, kalıcı:** yeni paket kurmadan (ör. açılışta ve uykudan dönüşte `charge_control_end_threshold`'a 80 yazan bir systemd birimi). Yöntemi ve dosya/birim adını önce Eren'e öner; sudo komutlarını Eren `!` ile çalıştırır. `asusctl` gibi yeni paket kart dışı.
  3. **llama.cpp imajı:** resmî `ghcr.io/ggml-org/llama.cpp` imajından `llama-bench` içeren sürüm; etiket ve digest kayda. İmaj işlemci komut setlerini (AVX2, AVX-VNNI) kullanıyor mu kontrol et (`llama-bench`/sistem bilgisi çıktısı); kullanmıyorsa dur ve yaz.
  4. **Modeller:** aynı aileden 3 boyut (~2B, ~4B, ~8B), 4 bit (`Q4_K_M`), GGUF. Aile, kaynak ve indirme klasörü (repo dışı; öneri `~/cerebrum2/models`) **indirmeden önce** Eren'e önerilir (yeni isim). Her dosyanın kaynağı ve SHA256'sı kayda.
  5. **Ölçüm araçları** (betik adları önce önerilir): `llama-bench` ile girdi okuma ve üretim hızı; sürekli yük sırasında 10 sn'de bir sıcaklık, işlemci frekansı ve hız kaydı. Ölçümler `systemd-inhibit` altında, prizde, demo kapalıyken.
- Bitti ölçütü:
  - Şarj sınırı: yeniden başlatmadan sonra ve uyku/uyanma sonrası değer 80; prizde %80'de şarj duruyor (durum `Not charging` ya da eşdeğeri).
  - Hız tablosu: 3 model × iş parçacığı 4/8/12 × girdi 2048 ve 6144 token, üretim 300 token; her hücre en az 3 tekrar (ortalama ± sapma). Ölçüm başında `AC online=1`, profil `balanced` ve sıcaklık kayda.
  - Sürekli yük: en iyi iş parçacığı ayarıyla ~8B modelde 30 dk kesintisiz iş (2048 girdi + 300 üretim döngüsü). Dakika başına hız, en yüksek sıcaklık ve ortalama frekans kayda; ilk 2 dk ile son 10 dk arasındaki hız farkı (%) yazılır.
  - Bütçe hesabı: her model için **ısınmış hızla** "2048 token girdi + 300 token üretim" süresi; ≤ 2 dk olanlar GEÇER. 6144 token (ham log yaklaşığı) süresi kriter dışı, yazılır.
  - Sınırlar: ölçüm boyunca `x86_pkg_temp` 95 °C üstünde 1 dk'dan fazla kalmadı (kaldıysa ölçüm durur ve yazılır); model + bağlam en yüksek bellek ≤ 10 GB; takas kullanımı artmadı.
  - Repoda kod/betik ve docs; model dosyaları ve ölçüm ham çıktıları repoya girmez (özet tablo HANDOFF'a ve `docs/` altına). `pytest` 190 yeşil; PR koşusu yeşil.
- Dikkat:
  - 2048 token "daraltılmış girdi" bir varsayım; daraltma yazılınca gerçek uzunluk ölçülür ve bütçe yeniden hesaplanır.
  - Demo bu kartta kapalı. Vaka kaydı sırasında model çalışmaz kuralı (model CPU'yu doldurursa servisler yavaşlar, sahte belirti kayda geçer) vaka üretim kartında karara bağlanacak; bu kartta ölçüm demo kapalıyken yapılır.
  - Güç profilini `performance`'a alma, iş parçacığı dışında llama.cpp ayarlarıyla (batch, flash attention vb.) optimizasyon yapma: kart dışı; fark edersen yaz.
  - İndirme: 3 model ~8–9 GB, imaj ~1–2 GB. Boş disk 299 GB.

## 2026-10-20 · Uygulama → Uygulama (lokal model hız ölçümü: ölçüm yöntemleri, ölçmeden önce)
- Kart ölçütlerinin nasıl ölçüleceği netleştirildi (Eren onayı, 2026-10-20). Ölçüt eşikleri değişmedi; sürekli yük testinin modeli Eren'in kararıyla değişti (aşağıda).
- Bütçe: `llama-bench -pg 2048,300` (girdi okuma + üretim tek iş; üretim 2048 token bağlamın üstüne). Süre = 2348 / ölçülen hız (token/sn). Karar süre üzerinden: ısınmış süre ≤ 120 sn GEÇER. Ham log için aynı yöntem: `-pg 6144,300`, süre = 6444 / hız; kriter dışı, yazılır. Ayrı okuma (`-p`) ve üretim (`-n`) hızları tabloda gösterilir, karar için kullanılmaz.
- Tekrarlar: `-r 1`; tablo baştan sona 3 tur koşulur (aynı hücrenin tekrarları arka arkaya değil). Hücre değeri 3 turun ortalaması ± sapması. Her hücrenin başlangıcında `x86_pkg_temp` kayda.
- Isınmış hız: sürekli yük testi (30 dk, 2048 girdi + 300 üretim döngüsü, en iyi iş parçacığı ayarı) tablodan sonra, soğuk (tablo) bütçe süresi 120 sn'ye en yakın modelde koşulur (kartta ~8B yazıyordu). Yavaşlama oranı = ilk 2 dk ile son 10 dk hız farkı. Diğer modellerin ısınmış süresi bu oranla hesaplanır; bu bir varsayım ve sonuçta öyle yazılır.
- Ortam: ölçüm sırasında makine boşta (tarayıcı kapalı, oturum beklemede), prizde, demo kapalı, `systemd-inhibit` altında. Ölçüm başında `AC0/online`, güç profili ve sıcaklık kayda.

## 2026-10-20 · Uygulama → Planlama (lokal model hız ölçümü, sonuç)
- Yapılan (`task/local-model-bench`): sonuç tablosu ve yöntem `docs/LOCAL_MODEL_BENCH.md`'de.
  - Şarj sınırı: `/etc/systemd/system/battery-charge-limit.service` (oneshot; `multi-user`, `suspend`, `hibernate`, `hybrid-sleep`, `suspend-then-hibernate` hedeflerine bağlı; `BAT0/charge_control_end_threshold`'a 80 yazar). `systemd-analyze verify` sonrası `enable --now` (Eren çalıştırdı).
  - llama.cpp `full-b11723` (digest `sha256:8f3c2cd0…96a0`, 4,2 GB; kartta 1–2 GB tahmin edilmişti). Modeller Qwen3.5 2B/4B/9B `Q4_K_M` (`unsloth`, sabit commit, SHA256 tuttu), `~/cerebrum2/models/`.
  - `tools/local_model_bench.sh` (`matrix`, `sustained`, `--resume`), `tools/bench_summary.py`.
- Bitti ölçütü:
  - Şarj sınırı: birimden hemen sonra 80; uyku/uyanma (öncesinde elle 100) sonrası 80, birim uyanmada çalıştı; yeniden başlatma (öncesinde elle 100) sonrası 80; prizde %79–80'de `Not charging` (2026-10-20 06:28 ve 06:56). GEÇTİ.
  - İmaj komut setleri: `system_info` `AVX2 = 1`, `AVX_VNNI = 1`, CPU sürümü `alderlake`. GEÇTİ.
  - Hız tablosu: 3 model × 4/8/12 iş parçacığı × 3 tur, her hücre `-p 2048 -n 300 -pg 2048,300 -pg 6144,300`; ölçüm başında AC 1, `balanced`, sıcaklık kayda. GEÇTİ. Kartta "girdi 2048 ve 6144" ayrı okuma testi olarak değil, `-pg 6144,300` içinde ölçüldü (Eren onayı).
  - Sürekli yük: 9B, 4 iş parçacığı, 30,4 dk, 9 iterasyon; hız 18,23–18,46 t/s; en yüksek 93 °C (ilk dk), sonra ~77 °C; ortalama frekans ~2250 MHz. Hız farkı ilk iterasyon → son 10 dk **+1,1 %** (ilk 2 dk penceresi boş kaldı, ilk iterasyon kullanıldı; Eren onayı). GEÇTİ (ölçüldü ve yazıldı).
  - Bütçe (ısınmış, 2048+300 ≤ 120 sn): 2B 29,6 sn GEÇER, 4B 72,3 sn GEÇER (ikisi de 9B oranıyla varsayım), 9B 127,4 sn KALIR (ölçüldü). 6144+300 (kriter dışı, soğuk): 68,8 / 177,0 / 295,9 sn.
  - Sınırlar: 95 °C üstü hiç örnek yok (en yüksek 94 °C). Bellek (llama-bench `VmHWM`): 9B 6144 bağlamda 8,93 GB, 2048 bağlamda 8,79 GB → ≤ 10 GB GEÇTİ. **Takas arttı** (koşu başına en çok +0,3 MB / +16 MB / +69 MB; en düşük `MemAvailable` ~10,4 GB) → ölçüt harfiyen KALDI; yorum planlamada.
  - Repoda sadece betikler ve docs; model dosyaları ve ham çıktılar repo dışı. `pytest` 190 yeşil. PR #11 koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39370628905 (`9217bb3`).
- Dikkat:
  - Gece koşusu tur 2'nin ilk hücresinde ~30 sn priz kopmasıyla durdu (eski betik bütün koşuyu bitiriyordu). Tur 1 `20261020-015311-matrix`'ten, tur 2–3 `20261020-033005-matrix`'ten (`--rounds 2`) birleştirildi; kopan hücre kullanılmadı. `032435-matrix` (iptal) ve `032945-matrix` (boş) kullanılmadı; `014208`, `014619` duman testi, `063543` priz testi + 9B bellek ölçümü.
  - Betik artık prize dayanıklı: priz giderse 1 sn içinde iş durur, hücre `ac_lost` olarak ayrılır, priz gelince baştan koşulur; başlangıçta priz yoksa bekler; `--resume`. İki durum da elle denendi (06:35 ve 06:37).
  - İlk bellek ölçümü (konteyner cgroup `memory.peak`) yanlıştı: eşlenen model dosyası önbelleği ilk dolduran konteynere yazılıyor (9B 3,3 GB görünüyordu). Tablodaki bellek sütunu kullanılmadı; 2B ve 4B'nin belleği yeni yöntemle ölçülmedi (9B'nin altında kaldığı çıkarım).
  - 8 ve 12 iş parçacığında üretim yavaşlıyor ve sapma büyüyor (verimlilik çekirdekleri); 4 iş parçacığı hem en hızlı hem en kararlı. 6 iş parçacığı (4P + 2E) denenmedi.
  - Isınma turu (`llama-bench` warmup) girdi okuma süresi kadar ek iş yapıyor; ölçüm sürelerine dahil değil, toplam koşu süresini uzatıyor (tablo ~4,5 saat sürdü).
  - Eren uzun koşularda prize takılı bırakıyor; şarj sınırı %80'de batarya beklemede, ek zarar yok. DECISIONS'taki "sadece prizdeyken başlar" kuralı betikte "priz yoksa bekler" olarak uygulanıyor.
  - Sonraki kartlar: asıl koşular için aynı yapının `server-b11723` imajı. Kalite ölçülmedi; nicemleme üçüncü taraf.

## 2026-10-20 · Planlama → Planlama (hız ölçümü doğrulaması ve sonraki kartlara notlar)
- Doğrulama (planlama, main `01f88ed`; main push koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39371046997):
  - Şarj sınırı 80, durum `Not charging` (%80), `battery-charge-limit.service` `enabled`.
  - llama.cpp imajı makinede etiketsiz (betik digest ile çekiyor); digest `sha256:8f3c2cd0…96a0` kayıttakiyle aynı.
  - Üç GGUF dosyasının SHA256'sı `docs/LOCAL_MODEL_BENCH.md` ile aynı.
  - `tools/bench_summary.py` üç ham klasörden aynı bütçe sonucunu üretti (2B 29,6 / 4B 72,3 / 9B 127,4 sn).
- Takas ölçütü: KALDI olarak kalır; ölçüt kartta yanlış seçilmişti (planlamanın hatası). Bir sonraki ölçümden itibaren `pswpin` ve `/proc/pressure/memory` (DECISIONS 2026-10-20).
- Priz kopması (tur 2'nin ilk hücresi): kabloyu Eren çıkarmış; donanım/kablo sorunu değil.
- Sonraki kartlar için:
  - **Değerlendirme kartı (ham log bütçesi):** 2026-10-20 bütçe satırındaki "240 koşu × 2 dk ≈ 7 saat" ham log koşularını da 2 dk sayıyordu (planlamanın hesap hatası). 4B ile 120 × 72 sn + 120 × 177 sn ≈ 8,3 saat > 7 saat. Gerçek ham log 6144 token'dan çok uzun olabilir (25 servis, dakikalarca log; bağlam penceresini aşabilir). Ham log koşulunun kendi planı gerekiyor (tekrar sayısı, vaka alt kümesi, ayrı gece ya da bağlamı aşan girdide ne yapılacağı); kartta karara bağlanır.
  - **Asıl koşular (model sunucusu):** hız ölçümünde iterasyon başına ~75 sn ölçülmeyen ek iş var (konteyner, model yükleme, ısınma turu). Koşu başına yeniden başlatılırsa bütçe çöker; sunucu (`server-b11723`) bir kez açılır, koşular ona bağlanır.
  - **Canlı demo (bellek):** 9B ~8,9 GB (`VmHWM`, 6144 bağlam); demo açıkken boş bellek ~7,2 GB (2026-10-18) → 9B demoyla birlikte sığmaz; 4B sığması beklenir (ölçülmedi).
  - **Model seçimi:** hızda 2B ve 4B bütçeye sığıyor, 9B 7 sn farkla kalıyor. Kalite ölçülmedi; seçim kalite ölçümünden sonra.

## 2026-10-20 · Planlama → Uygulama (collector C1: süzme, dosya çıkışı, flag dosyası)
- Yapılan (planlama): DECISIONS 2026-10-20: şarj sınırı günlük kapalı / koşu öncesi açılır; collector iki kart (C1, C2); süzülmemiş paralel çıkış (varsayılan kapalı); dosya çıkışı `~/cerebrum2/telemetry/` ve 2 GB geçici sınır; flag dosyası `~/cerebrum2/runtime/flagd/`; mesaj yeniden yazma ilkesi. Onaylı yeni isimler: `~/cerebrum2/telemetry/`, `~/cerebrum2/runtime/flagd/`.
- Amaç: modelin ve izleme sisteminin göreceği telemetri flag/senaryo bilgisi taşımasın, ama belirtiler kalsın; telemetri dosyaya sınırlı boyutta yazılsın; flag değiştirmek klonu kirletmesin. Gerçek senaryolarla doğrulama C2'de.
- Beklenen:
  1. Dal `task/collector-filter`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, PROJECT; main'de bekleyen 2026-10-20 doğrulama kaydı dahil).
  2. **Flag dosyası:** `up` klondaki `src/flagd/demo.flagd.json`'u `~/cerebrum2/runtime/flagd/`'a kopyalar (her seferinde üzerine); `compose.extras.yaml` `flagd` (`/etc/flagd`) ve `flagd-ui` (`/app/data`) bağlamalarını bu klasöre çevirir. flagd-ui'nin yazabildiği izinler.
  3. **Collector ayarı:** bizim `deploy/otel-demo/otelcol-config-extras.yml` (upstream'deki dosyanın adı; DECISIONS 2026-10-14), betik `OTEL_COLLECTOR_CONFIG_EXTRAS` ile bağlar. Süzme iki çıkıştan (dosya ve izleme sistemi) önce, ortak:
     - `flagd`, `flagd-ui`, `load-generator` servislerinin bütün telemetrisi; bu konteynerlerin `docker_stats` ve `span_metrics` metrikleri.
     - "Simüle edilen dünyada flagd yok" (DECISIONS 2026-10-15): servislerin flagd'ye giden rutin çağrıları (client span'leri), `/feature` ve `/flagservice` yolları, `flagd`/`ofrep` geçen alanlar.
     - Span olayı `feature_flag.evaluation`, `feature_flag.*` öznitelik ve metrikleri, `demo.feature_flag.recommendation_cache`.
     - Envoy erişim logunda `DI` bayrağı (DECISIONS 2026-10-15'teki arama kuralıyla).
     - OTEL_DEMO.md sızıntı tablosundaki her satır ya bir kurala bağlanır ya da neden gerekmediği yazılır; yeniden yazılacak mesajların metinleri Eren'e önerilir.
     - Upstream'in pipeline listeleri **değiştirilir, eklenmez** (OTEL_DEMO.md): upstream'deki her processor ve exporter bizim listede de olmalı.
  4. **Dosya çıkışı:** collector `file` exporter, OTLP JSON, satır başına bir kayıt (sızıntı testinin okuyabildiği biçim); sinyal başına ayrı dosya; `~/cerebrum2/telemetry/filtered/`. Dosya döndürme ayarları toplamı (süzülmüş + süzülmemiş) ≤ 2 GB.
  5. **Süzülmemiş paralel çıkış:** süzme processor'larından geçmeyen ayrı pipeline'lar → `~/cerebrum2/telemetry/raw/`. Açma yöntemini (ayrı ek dosya, ortam değişkeni vb.) öner; varsayılan kapalı.
- Bitti ölçütü:
  - Flag: `up` sonrası klon temiz; çalışma kopyası klondaki dosyayla aynı (SHA256). flagd-ui API ile bir flag açılıp `/feature/api/read`'den geri okununca açık; çalışma kopyası değişti, klon temiz; flag kapatıldı. İkinci `up` dosyayı başlangıç haline döndürdü.
  - Collector ayarı: collector imajıyla (`0.159.0`) `validate` geçti; bizim pipeline'larımız upstream'deki bütün processor ve exporter'ları içeriyor (elle değil, upstream config'le karşılaştırarak; yöntem kayda).
  - 30 dk normal koşu (flag'ler kapalı, süzülmemiş çıkış kapalı): `filtered/`'da üç sinyalin dosyası var; `raw/` boş; `aiops_rca` sızıntı CLI'ı `filtered/` üzerinde 0 bulgu; Jaeger servis listesinde (`/jaeger/ui/api/services`) `flagd`, `flagd-ui`, `load-generator` yok ve `frontend` trace'i var; Prometheus'ta `feature_flag` ile başlayan metrik yok; OpenSearch'te `load-generator` logu yok (sorgular kayda).
  - Kısa koşu (5 dk, süzülmemiş çıkış açık): sızıntı CLI'ı `raw/` üzerinde bulgu verir (en az flagd ve load-generator), aynı anda `filtered/` 0. Bu rutin trafik için mini `positive_control`; senaryo bazlı tam kontrol C2'de. Koşu sonunda `raw/` silinir.
  - Hacim: 30 dk koşudan sinyal başına MB/saat; 2 GB sınırının gece koşusunda kaç saate yettiği hesaplanır ve kayda; gerekirse sınır önerisi.
  - Zaman damgası 0 (1970) olan kayıtlar dosya çıkışında sayılır ve kayda (bu kartta düzeltilmez).
  - `pytest` yeşil; PR koşusu yeşil.
- Dikkat:
  - Şarj sınırı şu an kapalı (100). 30 dk'lık koşu uzun koşu sayılmaz; C2 ve gece koşularından önce açılır.
  - Senaryoya özgü kurallar (yeniden yazılan mesajlar, `DI`, `feature_flag.evaluation` olayları) flag açılmadan gerçek veride görülemez; C1'de kurallar yazılır ve `validate` edilir, gerçek doğrulama C2'de. İstersen bir senaryoyla (ör. `paymentFailure`) kısa bir deneme yapılabilir, kart ölçütü değil.
  - Bir span'i silmek trace'te boşluk bırakır (ör. flagd client span'leri); kabul edildi, rapor sınırlaması.
  - Collector'ın Docker soketi ve host dosya sistemi erişimi upstream tasarımı (`docker_stats`, `host_metrics`); değiştirilmez, risk olarak kayıtlı.
  - Collector bellek limiti 400M; süzme ve iki dosya çıkışı sonrası `docker stats` kayda.
  - Kart dışı: C2 koşusu, snapshot kesme aracı, kalıcı depolama (isimli volume), kendi Python servisi, hata enjeksiyonu betiği.

## 2026-10-20 · Uygulama → Uygulama (collector C1: sıra, kararlar ve ölçüm yöntemleri, ölçmeden önce)
- Eren onayı (2026-10-20). Kart ölçütleri değişmedi.
- Sıra: flag dosyası → dosya çıkışı (süzmesiz) + `--raw` → keşif koşusu (~10 dk, `raw/` açık) → süzme kuralları → 30 dk normal + 5 dk `raw/` koşuları. Kurallar keşifteki envantere dayanır (OTTL'de "her alanda ara" yok; alanlar tek tek adlandırılır).
- Collector kullanıcısı `1000:984` (eren, `docker` grubu); upstream `0:0`. Doğrulama: aynı süre (5 dk) upstream kullanıcıyla ve bizimkiyle çalışırken Prometheus'taki metrik adları listesi (`/api/v1/label/__name__/values`) karşılaştırılır; bizimkinde eksik ad olmamalı (yeni ad olabilir). Eksik çıkarsa root'a dönülür, kayda yazılır.
- Süzülmemiş çıkış: `deploy/otel-demo/otelcol-config-raw.yml` + `deploy/otel-demo/compose.raw.yaml`, sadece `tools/otel_demo.sh up --raw` ile yüklenir; varsayılan yüklenmez.
- Upstream karşılaştırması: collector `0.159.0` imajıyla `print-config --format=json --feature-gates=otelcol.printInitialConfig`; upstream birleşik ayarı (4 katman, demonun boş extras'ıyla) ve bizim birleşik ayarımız; `tools/check_collector_pipelines.py <upstream.json> <ours.json>` her sinyalde upstream processor/exporter/receiver'ın bizim süzülmüş pipeline'da olduğunu kontrol eder, eksikte çıkış ≠ 0. Kasıtlı kırmızı: bir upstream processor'ı listeden çıkarınca çıkış ≠ 0.
- Ölçüm sorguları (30 dk koşu):
  - Jaeger: `curl -s http://127.0.0.1:8080/jaeger/ui/api/services | jq -r '.data[]'` → `flagd`, `flagd-ui`, `load-generator` yok; `frontend` trace sayısı (`/jaeger/ui/api/traces?service=frontend&limit=1`) ≥ 1.
  - Prometheus: `curl -s http://127.0.0.1:9090/api/v1/label/__name__/values | jq -r '.data[]' | grep -c '^feature_flag'` → 0.
  - OpenSearch: `curl -s 'http://127.0.0.1:9200/otel-logs-*/_count' -H 'Content-Type: application/json' -d '{"query":{"term":{"resource.service.name":"load-generator"}}}'` → `count` 0 (alan adı keşifte doğrulanır; yanlış alan 0 vereceği için aynı sorgu `frontend` ile > 0 vermeli).
  - Sızıntı: `python -m aiops_rca.leakage ~/cerebrum2/telemetry/filtered` → çıkış 0, 0 bulgu; 5 dk koşuda `raw/` üzerinde çıkış 1 ve bulgularda flagd ile load-generator.
  - Hacim: sinyal başına dosya boyutu / koşu süresi → MB/saat.

## 2026-10-20 · Uygulama → Planlama (collector C1, sonuç)
- Yapılan (`task/collector-filter`):
  - Flag dosyası: `up` her seferinde `demo.flagd.json`'u `~/cerebrum2/runtime/flagd/`'a sıfırlar (sil + kopyala; flagd-ui dosyayı root olarak yeni dosya halinde yazıyor); `flagd` ve `flagd-ui` oraya bağlı.
  - Collector: `deploy/otel-demo/otelcol-config-extras.yml` (`filter/sim_world`, `transform/scrub`, `file/{traces,metrics,logs}` → `~/cerebrum2/telemetry/filtered/`); `--raw` ile `otelcol-config-raw.yml` + `compose.raw.yaml` (ayrı pipeline'lar ve `span_metrics/raw` → `raw/`). Collector `eren:docker`. Kural eşlemesi ve hacim: OTEL_DEMO.md "Süzme kuralları" ve "Çalıştırma".
  - `tools/check_collector_pipelines.py`: upstream ve bizim `print-config --format=json` çıktısını karşılaştırır.
  - Keşif koşusu (10 dk, `--raw`) envanteri kuralların temeli; tabloda olmayan üç kanal bulundu: servislerin flagd'ye rutin çağrıları (beklenen), **host süreç metrikleri** (bütün süreç komut satırları; Eren: tümden düşür), **collector'ın kendi logları** (kural metinlerini logluyordu; Eren: düşür + yollar ön ekli).
- Bitti ölçütü:
  - Flag: `up` sonrası klon temiz, iki dosyanın SHA256'sı aynı (`20a4c5d5…`); flagd-ui API ile `adFailure` açık, `/feature/api/read` → `on`, çalışma kopyası değişti, klon temiz; kapatıldı; ikinci `up` dosyayı sıfırladı (SHA256 klonla aynı, sahibi eren). Ek: flagd'nin kendisi 4 aç/kapada da yeni değeri ≤ 1 sn'de gördü. GEÇTİ.
  - Collector ayarı: `validate` (0.159.0) bizim ayar ve bizim + raw, çıkış 0. `check_collector_pipelines.py`: 4 pipeline, eksik 0; kasıtlı kırmızı: processor silinince 1, sıra bozulunca 1. Raw pipeline'ların alıcı/processor listeleri upstream'le birebir. GEÇTİ.
  - 30 dk normal koşu (15:36–16:06; ilk denemede 32 bulgu çıktı, collector logu düzeltmesinden sonra tekrarlandı): `filtered/`'da üç sinyal; `raw/` boş; sızıntı CLI'ı `filtered/` → `clean`, çıkış 0; Jaeger servislerinde flagd/flagd-ui/load-generator yok, `frontend` trace 1; Prometheus `feature_flag*` 0; OpenSearch load-generator 0, flagd 0 (alan kontrolü frontend 28.416). GEÇTİ.
  - 5 dk koşu (`--raw`, 16:09–16:15): sızıntı CLI'ı `raw/` → 28.543 bulgu, çıkış 1 (flagd 10.821, load-generator 551, flagd-ui 99, product-catalog, recommendation, frontend-proxy, cart, checkout, frontend-web, ad, payment, süreç metrikleri); aynı koşuda `filtered/` → `clean`. `raw/` silindi. GEÇTİ.
  - Hacim: 30 dk'da traces 194,7 MB (bir kez döndü), logs 65,6, metrics 54,1 → ~630 MB/saat (traces ~389, logs ~131, metrics ~108). 2 GB sınırı (filtered 900 MB + raw 900 MB) şimdiki döndürmeyle traces'te ~46 dk, logs'ta ~2,3 saat, metrics'te ~2,8 saat geriye gidiyor; 7 saatlik gece ~4,4 GB üretir. Öneri aşağıda. Ölçüldü ve yazıldı.
  - Zaman damgası 0: dosya çıkışında logların 2.716 / 55.965'i (currency 1.973, shipping 743); span ve metrikte 0. Düzeltilmedi.
  - `pytest` 190 yeşil. PR #12 koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39429246500 (`a176143`).
- Dikkat:
  - **2 GB sınırı önerisi (karar planlamada):** toplam sınır yetmez değil ama döndürme eski veriyi siliyor; snapshot vaka bitiminden sonra en geç ~45 dk içinde (traces'in ömrü) kesilmeli. İki seçenek: (a) toplamı 2 GB tutup hacme göre dağıtmak (raw normalde kapalı olduğu için filtered'a daha çok: ör. traces 1 GB, logs/metrics 300'er MB → traces ~2,5 saat) ve raw'ı sadece positive_control gecesinde açmak; (b) snapshot kesicinin vaka sonunda hemen kesmesini zorunlu kılıp sınırı olduğu gibi bırakmak.
  - Collector belleği: süzme açık ~107 MiB, raw da açıkken ~239 MiB (limit 400M, `GOMEMLIMIT=160MiB`). C2'de raw açık ve senaryo yükü altında izlenmeli.
  - Collector açılış yarışı (`docker_stats` bir konteyneri kaçırabiliyor; süzme açıkken beklenen sayı 22), flagd doğrulaması (flagd-ui değil flagd'ye sor, ~1 sn bekle), flagd-ui zamanlayıcısı (varsayılan kapalı, vaka öncesi kontrol): OTEL_DEMO "Sonraki kartlar için notlar"da (enjeksiyon ve vaka üretim kartları).
  - Upstream'in birleşik ayarında `prometheus/ad` alıcısı kullanılmıyor (tam mod metrik alıcı listesini değiştiriyor); değiştirmedik.
  - Bizim ölçüm sorgularımız (`/jaeger`, `/grafana`, `/feature` dışındakiler) 8080 üzerinden frontend-proxy'den geçtiği için frontend-proxy telemetrisine istek olarak düşüyor. Flag bilgisi taşımıyor ama operatör trafiği; vaka sırasında sorgu yapılacaksa ayrı porttan (Prometheus 9090 gibi) ya da vaka penceresinin dışında.
  - Sentetik kural testi (geçici collector'a hazırlanmış OTLP kayıtları; girdide 43 bulgu, çıktıda 0) repoya alınmadı. Öneri: `tools/test_collector_rules.sh` + `tests/fixtures/collector_rules/` (Docker ister, CI'da koşmaz); collector sürümü değişince ve kural eklenince elle koşulur.
  - `tests/test_leakage.py` OTEL_DEMO.md'de `## Sızıntı yolları` bölümünü bir sonraki `## ` başlığına kadar okuyor; o bölüme alt başlıklı tablo eklenirse satırlar sızıntı satırı sayılır (bu kartta eşleme tablosu ayrı `##` bölümüne konarak çözüldü).
  - Upstream değişirse elle güncellenecekler: `compose.raw.yaml`'daki collector komut listesi, `otelcol-config-extras.yml` başındaki upstream liste notu, `otelcol-config-raw.yml`'daki alıcı listeleri (`check_collector_pipelines.py` süzülmüş pipeline'ları kontrol eder, raw'ı etmez).

## 2026-10-21 · Planlama → Planlama (collector C1 doğrulaması)
- Doğrulama (planlama, main `b232f03`; PR #12 koşusu https://github.com/erenbezek/aiops_rca/actions/runs/39429246500 ve main push koşusu yeşil). Makine bataryadaydı (%86): 30 + 5 dk yerine 10 + 5 dk tekrar ölçüm; önceki dosyalar silinmedi, sadece bu koşunun eklediği kısım ölçüldü.
  - Flag dosyası: `up` sonrası klon temiz, iki dosyanın SHA256'sı aynı (`20a4c5d5…`), sahibi eren. flagd-ui API ile `adFailure` açıldı: flagd'den `on` (ResolveBoolean), çalışma kopyası değişti (sahibi root), klon temiz; 60 sn sonra kapatıldı, flagd `off`. İkinci `up` (`--raw`) dosyayı klonla aynı SHA'ya ve eren'e döndürdü. GEÇTİ.
  - Collector ayarı: `validate` (0.159.0) bizim ayar ve bizim + raw, çıkış 0. `check_collector_pipelines.py` upstream'e karşı 4 pipeline, eksik 0 (raw açıkken de 0); kasıtlı kırmızı: `redaction` silinince 1, logs'ta sıra bozulunca 1. Raw pipeline'larda alıcı ve processor listeleri upstream'le aynı, tek fark `span_metrics` → `span_metrics/raw`. GEÇTİ.
  - Normal koşu (12:52–13:02, `adFailure` 1 dk açık dahil): sızıntı CLI'ı bu koşunun `filtered/` kısmında `clean`, çıkış 0; Jaeger servislerinde flagd/flagd-ui/load-generator yok, `frontend` trace 1; Prometheus `feature_flag*` 0, flagd/flagd-ui/load-generator serisi 0; OpenSearch load-generator 0, flagd 0, flagd-ui 0 (frontend 9.562). `RestartCount`/`OOMKilled` temiz. GEÇTİ.
  - `--raw` 5 dk (13:05–13:10): raw → 26.401 bulgu, çıkış 1 (product-catalog 10.854, flagd 10.041, recommendation, frontend-proxy, load-generator 582, cart, checkout, frontend-web, flagd-ui 99, ad, payment); aynı dakikalarda `filtered/` → `clean`. `raw/` ve planlamanın kopyası silindi. GEÇTİ.
  - Hacim (10 dk): traces ~382, logs ~131, metrics ~108 MB/saat (~621; uygulama ~630). Dosya döndürme çalıştı (`traces-<zaman>-size.jsonl`).
  - Zaman damgası 0: logların 824 / 17.912'si (%4,6; currency 584, shipping 240); uygulamada %4,9.
  - `pytest` 190 yeşil.
- Farklar ve notlar:
  - Açılış yarışı tekrarlandı: Prometheus'ta `count(container_uptime_seconds)` 22 yerine 21, eksik `image-provider` (uygulamada `ad`). Vaka öncesi sayı kontrolü gerekli (OTEL_DEMO "Sonraki kartlar için notlar"a eklendi).
  - flagd-ui flag'i kapatınca dosya ilk haline dönmüyor (yeniden biçimlendiriyor, SHA farklı); başlangıç hali yalnız `up` ile (OTEL_DEMO "Flag'i açıp kapatma" düzeltildi, eski satır klondaki dosyayı gösteriyordu).
  - Collector belleği raw açıkken ~110 MiB ölçüldü (uygulama ~239 MiB). C2'de raw açık ve senaryo yükü altında izlenir.
  - HANDOFF 2026-10-20 yöntem kaydındaki `--feature-gates=otelcol.printInitialConfig` 0.159.0'da yok (hata verir). Çalışan komut: `print-config --format=json --feature-gates=service.profilesSupport`, dört katman `--config` ile; `host_metrics` için `/hostfs` bağlanmalı (boş klasör yeter) ve demonun `.env`'i `--env-file` ile verilmeli.
  - `adFailure` açıkken ad'de hata span'i görüldü (41 span'de 1), kapalıyken 0; örnek çok küçük, sadece işaret. Belirti kontrolü C2'de.
  - İsimsiz volume'ler 24 → 27 (iki `up`). Depolama kartına.
- Kararlar (Eren, 2026-10-21): 2 GB sınırında seçenek (b): snapshot vaka biter bitmez kesilir, sınırların dağılımı depolama kartında. Kural testi betiği C2'de. Kaba kalite denemesi C2'den önce (DECISIONS 2026-10-21).

## 2026-10-21 · Planlama → Uygulama (kaba kalite denemesi)
- Yapılan (planlama): DECISIONS 2026-10-21 (kaba kalite denemesi, snapshot vaka biter bitmez kesilir, kural testi betiği C2'de); PROJECT ve OTEL_DEMO güncellendi; C1 doğrulaması yukarıda.
- Amaç: asıl değerlendirmeden önce, aynı basit özetle küçük modellerin ve `large_api_model`'in kök neden servisini bulup bulamadığına kaba bakmak. Model boyutu seçimine ve hibritin gereğine işaret verir. Oran değildir, rapora girmez.
- Beklenen:
  1. Dal `task/quality-trial`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, PROJECT, OTEL_DEMO).
  2. **Vakalar** (elle, sırayla, ikisi de "deneme" işaretli; geliştirme/test setine girmez):
     - Her vaka ayrı `tools/otel_demo.sh up` (flag dosyası sıfırlanır; `--raw` yok). Açılıştan sonra: Prometheus'ta `count(container_uptime_seconds)` = 22 (değilse collector yeniden başlatılır), flagd-ui zamanlayıcısı kapalı.
     - 10 dk normal → flag açılır ve flagd'den doğrulanır → 10 dk → flag kapatılır → özet hemen kesilir → `down`.
     - Vaka 1: `paymentFailure` = `50%` (sayısal flag; flagd'de `ResolveFloat`). Vaka 2: `paymentUnreachable` = `on`. Doğru servis INCIDENT_CATALOG'dan: payment / checkout.
  3. **Özet betiği** (adı ve çıktı klasörü önce Eren'e önerilir; klasör repo dışı): sadece `~/cerebrum2/telemetry/filtered/`'dan, vaka penceresini (alarm zamanından önceki 10 dk + sonraki 10 dk) okur. Pencere kaydın zamanına göre kesilir; `timeUnixNano` 0 ise `observedTimeUnixNano` kullanılır (C1: currency ve shipping loglarının ~%5'i; 2026-10-21'de 1.918 kaydın hepsinde `observedTimeUnixNano` dolu). Özet **JSON** (sızıntı CLI'ı sadece JSON okuyor, düz metinde çıkış 2) ve vaka başına kendi klasöründe; dosya ve klasör adlarında flag ya da senaryo adı geçmez (CLI adları da tarıyor). Doğru cevap kaydı (flag, varyant, doğru servis) özet klasörünün dışında tutulur. İçerik: servis başına istek sayısı, hata oranı, p95 gecikme (önce / sonra) ve en sık hata log mesajları (servis ve sayıyla). Alarm zamanı flag açılış zamanıdır; özete flag adı, senaryo adı ya da kök neden ipucu girmez. Bilerek basit: daraltma değil.
  4. **Modeller** (demo kapalıyken; vaka kaydı sırasında model çalışmaz, 9B demoyla sığmaz):
     - Yerel: llama.cpp `full-b11723` (hız ölçümündeki imaj, kayıtlı digest `sha256:8f3c2cd0…96a0`; içinde `llama-server` var, yeni imaj indirilmez), sunucu bir kez açılır; Qwen3.5 2B/4B/9B Q4_K_M sırayla; 4 iş parçacığı; düşünme modu kapalı (hız bütçesi 300 çıktı token'ıyla ölçüldü); çıktı ≤ 300 token.
     - API: Groq gpt-oss-120b ve Gemini 3.5 Flash Lite. İkisi de akıl yürütme modeli; düşünme tamamen kapatılamıyor (gpt-oss), düşünme token'ları çıktı sınırından düşebiliyor. Düşünme en düşük seviyeye çekilir (parametre adları ve en düşük değerler sağlayıcı dokümanından doğrulanıp kayda); çıktı sınırı düşünmeye yetecek kadar yüksek, son cevap hedefi ≤ 300 token; düşünme ve son cevap token'ları ayrı kayda. Groq'ta girdi + düşünme + cevap dakikada 8K token altında kalmalı. Anahtarlar `keys.env`'den, ekrana basılmaz.
     - Beş modelde aynı olanlar: istem, girdi, temperature 0. Düşünme ve çıktı sınırı aynı değil (yukarıda).
  5. **İstem:** önce Eren'e önerilir, onaylanınca beş modelde aynı ve değişmez. Çıktı biçimi: en olası 3 servis sırayla + her biri için kısa gerekçe (JSON).
- Bitti ölçütü (ölçmeden önce yazıldı, sonuca göre değişmez):
  - İki vaka kaydı: flag açılış/kapanış zamanları, flagd doğrulaması, konteyner sayısı, `RestartCount`/`OOMKilled`. Hedef dışı beklenmeyen yeniden başlama varsa vaka geçersiz, yazılır.
  - İki özet: token sayısı ≤ 2048 (llama.cpp sunucusunun `/tokenize`'ı ile); sızıntı CLI'ı özet dosyasında 0 bulgu (bulgu varsa o özet modele verilmez, yazılır); dosya yolu ve SHA256'sı kayda.
  - Sonuç tablosu: 2 vaka × 5 model; doğru servis top-1'de mi, top-3'te mi; süre; girdi, düşünme ve son cevap token'ları; biçimi bozuk çıktı (bozuk çıktı "çözemedi" sayılır). İstisna: token sınırına takıldığı için boş ya da yarım gelen cevap "çözemedi" sayılmaz; sınır bir kez iki katına çıkarılıp tekrar istenir, ikisi de kayda (yoksa kural yanlışlıkla "girdi kötü" der).
  - "Çözer" = doğru servis ilk 3'te. Yorum DECISIONS 2026-10-21 kuralıyla, her küçük model için ayrı; iki API modeli ayrışırsa ikisi de ayrı yazılır ve sinyal "belirsiz" sayılır. Asimetri: küçükler düşünmeden, büyükler düşünerek cevaplar; "büyük çözer + küçük çözemez" çıkarsa "düşünmesiz küçük model yetmiyor" diye yazılır, yalnız boyut farkı diye değil.
  - Repoda kod ve docs; özetler, model cevapları ve ham çıktılar repoya girmez. `pytest` yeşil; PR koşusu yeşil.
- Dikkat:
  - 2 vaka, tek tekrar: genelleme yazılmaz ("küçük model ödeme hatalarını çözüyor" gibi). Sonuç model seçimi için tek başına yetmez.
  - Prizde yapılır; toplam ~1 saat, uzun koşu sayılmaz (şarj sınırı gerekmez).
  - Vaka penceresinde 8080 üzerinden Jaeger/Grafana açılmaz (C1: operatör trafiği frontend-proxy telemetrisine düşüyor). Flag yazma ve flagd doğrulaması `/feature` ve `/flagservice` yollarından gider, süzmede düşer.
  - Groq dakikada 8K token: ~2K girdiyle sorun beklenmez; Gemini anlık 503 verebilir, tek yeniden deneme yazılır.
  - Kart dışı: daraltma, kalibrasyon, C2, vaka üretim otomasyonu, model ailesi ya da nicemleme değişikliği.

## 2026-10-21 · Uygulama → Planlama (kaba kalite denemesi, sonuç)
- Yapılan (`task/quality-trial`): `tools/trial_summary.py` (vaka özeti), `tools/trial_ask_models.py` (beş model, `--score`); isimler ve özet alanları GLOSSARY'de. Çıktılar repo dışı, `~/cerebrum2/quality_trial/case1|case2/` (`view/summary.json`, `case.json`, `answers/`) ve `run.log`.
  - Özet: girintisiz JSON (girintili 1.713, girintisiz 1.099 token; aynı içerik). Hata logu = WARN ve üstü (payment ödeme hatasını WARN logluyor; Eren onayı). Pencere uçlarında kayıt yoksa özet yazılmaz (çıkış 1; 13:00 alarmıyla denendi).
  - Düşünme ayarları denenerek doğrulandı: Groq `reasoning_effort: low` (en düşük; `low`/`medium`/`high`), düşünme token'ları `max_tokens`'tan düşüyor (20 sınırla boş cevap, `finish_reason: length`), kayıtta `usage.completion_tokens_details.reasoning_tokens`. Gemini `reasoning_effort: minimal` (dokümanda 3.x için en düşük; 3.5 Flash Lite tabloda yok), düşünme token'ı raporlanmadı (`total = prompt + completion`). Qwen3.5 `chat_template_kwargs.enable_thinking: false` çalışıyor (açıkken 300 token'ın tamamı düşünmeye gitti). API çıktı sınırı 2000, yerel 300.
  - İstem (Eren onayı): kök neden tanımı istemde ("kendi kodu ya da ayarı bozuk servis, başka yerdeki sorunun belirtisini gösteren değil"; DECISIONS 2026-10-14); JSON modu zorlanmadı, cevaptaki ilk JSON nesnesi okunur. Metin `trial_ask_models.py`'de.
- Bitti ölçütü:
  - Vaka kayıtları (`case.json`): vaka 1 `paymentFailure` `50%` açık 11:19:47–11:30:00 UTC, vaka 2 `paymentUnreachable` `on` açık 11:43:33–11:53:47 UTC; flagd'den doğrulandı (ResolveFloat 0,5 / ResolveBoolean true, ≤ 1 sn; kapanışta off). Konteyner sayısı normal başında, açılışta ve kapanışta 22; zamanlayıcı üç kontrolde kapalı; `RestartCount` 0, `OOMKilled` yok. GEÇTİ.
  - Özetler: `/tokenize` ile 869 ve 850 token (istemle 1.100 / 1.081; sohbet şablonuyla girdi 1.116 / 1.097); sızıntı CLI'ı ikisinde `clean`; SHA256 `db393952…dba12`, `ebd14cd2…e4c0`. GEÇTİ.
  - Sonuç tablosu (doğru servis: vaka 1 payment, vaka 2 checkout; süre sn; token girdi/düşünme/cevap):

    | Model | Vaka 1 top-1 / top-3 | süre | token | Vaka 2 top-1 / top-3 | süre | token |
    |---|---|---|---|---|---|---|
    | `qwen3.5-2b` | ✓ / ✓ | 16,9 | 1116/0/194 | ✓ / ✓ | 14,3 | 1097/0/151 |
    | `qwen3.5-4b` | ✓ / ✓ | 33,4 | 1116/0/116 | ✓ / ✓ | 35,8 | 1097/0/134 |
    | `qwen3.5-9b` | biçim bozuk → ✗ | 64,2 | 1116/0/143 | biçim bozuk → ✗ | 62,3 | 1097/0/121 |
    | `gpt-oss-120b` | ✓ / ✓ | 1,7 | 1060/285/138 | ✓ / ✓ | 0,9 | 1041/104/129 |
    | `gemini-3.5-flash-lite` | ✓ / ✓ | 1,4 | 1256/0/146 | ✓ / ✓ | 50,8 | 1234/0/102 |

    Token sınırına takılan cevap yok (tekrar deneme olmadı). GEÇTİ (ölçüldü ve yazıldı).
  - Yorum (DECISIONS 2026-10-21 kuralı, her küçük model ayrı): iki API modeli aynı (sinyal belirsiz değil). 2B ve 4B: büyük çözer + küçük çözer → **umut var**. 9B: büyük çözer + küçük çözemez → kural "düşünmesiz küçük model yetmiyor" der; ama sebep servis seçimi değil biçim: iki cevapta da son `}` eksik, `finish_reason: stop` (sınıra takılmadı, kart tekrar denemeye izin vermiyor). Okunabilseydi ikisinde de doğru servis top-1'deydi; bu sadece not, ölçüt değişmedi.
  - Repoda kod ve docs; özetler ve cevaplar repo dışı. `pytest` 190 yeşil. PR #13 koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39597212650 (`d945062`).
- Dikkat:
  - 2 vaka, tek tekrar, ikisi de ödeme yolu: genelleme yok. "Zor" vaka beklenenden kolaydı: özette checkout %100 hata ve p95 39 → 201 ms, payment ve email'e 0 istek; tek log frontend "Checkout failed to place order" (30). İstemdeki kök neden tanımı da işi kolaylaştırmış olabilir. Sessiz senaryolarda (ör. `adHighCpu`) aynı sonuç beklenmemeli.
  - 9B biçim hatası: Qwen3.5 9B iki kez aynı şekilde nesneyi kapatmadı. Asıl koşularda JSON modu ya da daha toleranslı okuyucu düşünülürse bu karar planlamanın; burada değiştirilmedi.
  - Gemini vaka 2'de 50,8 sn: kayıtta tek deneme. Koşu sırasında betik 503 sonrası tekrar denemeyi ayrı yazmıyordu (kart "yazılır" diyordu); 50,8 sn ikinci çağrının süresi olsaydı ilk çağrı 503 alıp 30 sn beklemiş olurdu, büyük ihtimalle tek yavaş çağrı ama kesin değil. Koşudan sonra düzeltildi: ilk hata `retried_after` alanına yazılıyor (sahte cevapla denendi); bu koşunun verisi değişmedi.
  - Vaka sırasında 8080'den sadece flag yazma (`/feature`) ve flagd doğrulaması (`/flagservice`) yapıldı. Kontroller betiği (flag yaz/doğrula, konteyner sayısı, zamanlayıcı) repoya alınmadı; zamanlayıcı durumu `GET /feature/scheduler` sayfasındaki "Scheduler stopped" yazısından okundu (flagd-ui'de bunun için API yok). Vaka üretim kartında işe yarar.
  - flagd-ui zamanlayıcı ve `/feature/api/write` yolu upstream testindeki gibi: `read` → `defaultVariant` değiştir → `write`.

## 2026-10-21 · Planlama → Planlama (kaba kalite denemesi doğrulaması)
- Doğrulama (planlama, main `821cf5d`; PR #13 koşusu ve main push koşusu yeşil):
  - `trial_ask_models.py --score` kayıtlı cevaplardan tabloyu birebir üretti.
  - Özetlerin SHA256'sı kayıtla aynı (`db393952…`, `ebd14cd2…`); sızıntı CLI'ı iki `view/`'da `clean`. `case.json` `view/` dışında.
  - Vaka 2 özeti `trial_summary.py` ile `filtered/`'dan yeniden üretildi: SHA256 aynı. Vaka 1'in penceresi döndürmeyle silinmişti (traces 14:09–14:16 yerel); betik "window not covered by data" deyip çıkış 1 verdi (koruma çalışıyor; DECISIONS 2026-10-21 "vaka biter bitmez kesilir" kararının örneği).
  - 9B'nin iki cevabı: yalnız son `}` eksik, sıralama vaka 1 payment/checkout/frontend-proxy, vaka 2 checkout/frontend/payment. Kural gereği "çözemedi" doğru.
  - `trial-llama` konteyneri kapalı.
- Yorum: iki vaka da kolaydı; özet cevaba çok yakındı (vaka 1 payment logunda `Invalid token`, vaka 2'de hata veren tek servis checkout, %100). Gösterdiği: özet biçimi işe yarıyor, 2B/4B böyle bir JSON özeti okuyup servis seçebiliyor. Göstermediği: zor vakada boyut farkı ve hibritin gereği (denemenin asıl sorusu cevapsız kaldı; Eren).
- Kararlar (Eren, 2026-10-21): asıl koşularda JSON şeması zorlanır; 9B elenmez (DECISIONS 2026-10-21). `c68d8b3`'teki ikinci karar: bu denemenin `filtered/` verisi kalır (süzülmüş, cevap içermiyor; döndürme zamanla siler).
- Süreç notu: uygulama PR #13 birleştikten sonra dala bir commit daha attı (`c68d8b3`, GitHub'da `task/quality-trial`'da, main'de yok). İçeriği bu kayıtla ve DECISIONS'la main'e taşındı; ek PR açılmadı. **Kural (uygulama için): PR birleştikten sonra dala commit atılmaz; sonradan çıkan karar planlamaya iletilir, planlama main'e yazar.** Dalın silinmesi Eren'de.

## 2026-10-21 · Planlama → Uygulama (zor deneme)
- Yapılan (planlama): DECISIONS 2026-10-21 (JSON şeması zorlanır, 9B elenmez, zor deneme); kaba kalite denemesi doğrulaması yukarıda; PROJECT güncellendi.
- Amaç: zor vakalarda küçük modellerin (2B/4B/9B) kök neden servisini bulup bulamadığına ve boyutun fark edip etmediğine kaba bakmak; hibritin gereğine işaret. Oran değil, rapora girmez.
- Beklenen:
  1. Dal `task/quality-trial-2`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, PROJECT). **PR birleştikten sonra dala commit atılmaz** (sonradan çıkan karar planlamaya iletilir).
  2. **Vakalar** (ilk denemedeki akış: her vaka ayrı `up`, 22 konteyner kontrolü, zamanlayıcı kapalı, 10 dk normal → flag aç + flagd'den doğrula → 10 dk → kapat → özet hemen kesilir → `down`; `RestartCount`/`OOMKilled` kaydı):
     - `adHighCpu` = `on` → ad
     - `productCatalogFailure` = `on` → product-catalog (`defaultVariant` değil, targeting kuralının dalı: OTEL_DEMO "Flag'i açıp kapatma")
     - `productCatalogLockContention` = `on` → product-catalog
     - `intlShippingSlowdown` = `10sec` → shipping
     - Klasörler mevcut yapıda `~/cerebrum2/quality_trial/case3` … `case6` (adlarda flag/senaryo yok; `case.json` `view/` dışında).
  3. **Özet** (`tools/trial_summary.py` genişler): mevcut alanlara ek olarak servis başına `docker_stats`'tan CPU kullanımı ve bellek kullanımı (önce/sonra; ortalama ve en yüksek). Konteyner adı servis adına eşlenir. Yeni alan adları önerilir, GLOSSARY'ye yazılır. Özet ≤ 2048 token; sızıntı CLI'ı `clean`.
  4. **Belirti kontrolü (modellerden önce):** her özette kök neden servisinin önce/sonra değerleri tabloya; hiçbir sinyalde (hata oranı, p95, CPU, bellek, WARN+ log) görünür sapma yoksa vaka "belirtisiz" yazılır, modeller yine koşar ama sonucu yoruma girmez. Sapma eşiği ölçmeden önce önerilir, Eren onaylar (INCIDENT_CATALOG kalibrasyon ölçütü: "normal döneme göre görünür sapma").
  5. **Modeller** (`tools/trial_ask_models.py` genişler): aynı beş model ve ayarlar (yerel düşünme kapalı ≤ 300 token; API düşünme en düşük, sınır 2000; temperature 0). **JSON şeması zorlanır**: llama.cpp sunucusunda `response_format` şema/gramer, Groq ve Gemini'de kendi `response_format` desteği; her sağlayıcının mekanizması dokümandan ve bir denemeyle doğrulanıp kayda (desteklenmiyorsa dur ve yaz). İstemin alan açıklamasına CPU ve bellek eklenir; yeni metin Eren'e önerilir, onaylanınca beş modelde aynı.
- Bitti ölçütü (ölçmeden önce yazıldı, sonuca göre değişmez):
  - Dört vaka kaydı (ilk denemedeki alanlar). Hedef dışı beklenmeyen yeniden başlama → vaka geçersiz, yazılır.
  - Dört özet: token ≤ 2048 (`/tokenize`), sızıntı CLI'ı `clean`, SHA256 kayda; belirti tablosu ve "belirtili/belirtisiz" kararı modellerden önce yazılı.
  - Sonuç tablosu: 4 vaka × 5 model; top-1, top-3, süre, girdi/düşünme/cevap token, biçim. Token sınırına takılan cevapta sınır bir kez iki katı (ilk denemedeki kural).
  - Yorum DECISIONS 2026-10-21 zor deneme kuralıyla, vaka başına; "çözer" = doğru servis ilk 3'te. Ezber sınırlaması yorumda yazılır.
  - `trial_ask_models.py --score` ilk denemenin cevaplarından aynı tabloyu üretmeye devam eder (geriye uyum). `pytest` yeşil; PR koşusu yeşil.
- Dikkat:
  - Toplam ~2 saat: uzun koşu. Prizde; şarj sınırı önceden açılır (DECISIONS 2026-10-20; sudo komutunu Eren `!` ile çalıştırır), `systemd-inhibit` altında.
  - Kalibrasyon yapılmadı: sessiz vakalarda (özellikle `adHighCpu`) 10 dk'da belirti zayıf olabilir; bu yüzden belirti kontrolü var. Varyant değiştirilmez (kalibrasyon C2'de).
  - `productCatalogFailure` mesajı süzmede yeniden yazılıyor (`failed to load product from catalog`): yeniden yazımın gerçek veride ilk görüldüğü yer; sızıntı CLI'ı `clean` vermezse o vaka modele verilmez, yazılır (C2 için bulgu).
  - `productCatalogLockContention` kilit logu da yeniden yazılıyor; aynı kural.
  - Vaka penceresinde 8080'den sadece flag yazma ve flagd doğrulaması.
  - Kart dışı: daraltma, C2, kalibrasyon, varyant seçimi, yeni senaryo, model ailesi değişikliği.

## 2026-10-23 · Uygulama → Planlama (zor deneme, sonuç)
- Yapılan (dal `task/quality-trial-2`):
  - `trial_summary.py`: konteyner başına CPU (`cpu_pct_avg/max_before/after`, bir çekirdeğin yüzdesi) ve bellek (`mem_mb_avg_before/after`, MB). Bellek en yükseği yok, sadece ortalama (token; Eren seçeneği B). İzleme araçlarının konteynerleri yok; veritabanı satırlarında sadece CPU/bellek. Metrikler için de pencere ucu kontrolü.
  - **CPU düzeltmesi (koşu sırasında):** ilk sürüm `container.cpu.utilization` okuyordu. Bu collector sürümünde metrik anlık değil (birim `1`, açılıştan beri birikmiş ortalama gibi). Vaka 3'te `ad` `docker stats`'ta ~%404 iken özet 0,03 → 3,44 doğrusal artış gösterdi. Kaynak formüle bakıp "yüzde" demiştim, gerçek veriyle karşılaştırmamıştım; yanlıştı. Düzeltme (Eren onayı, ölçüt önceden): birikimli CPU süresi sayacından (`container.cpu.usage.total`, ns) hız = artış / süre × 100. Ölçütler: vaka 3 `ad` sonra 397,15 (364–445 aralığında), önce 1,42 (< 5), CPU dışı bütün alanlar eski özetle birebir aynı, özetler ≤ 2048, `pytest` 190 yeşil. GEÇTİ (`ebde62e`). Vaka 3 özeti alınan telemetri yedeğinden yeniden üretildi (`case.json` `summary_note`); vaka 4–6 betikle zaten düzeltilmiş kodla çıktı. Yedekler silindi.
  - `trial_symptoms.py` (yeni): kök neden servisinde özetteki değerler normal döneme göre sapıyor mu; eşikler ölçmeden önce Eren onaylı (hata oranı +0,05; p95 ×1,5 ve +20 ms; CPU ×1,5 ve +5 puan; bellek ×1,2; önceki pencerede olmayan ≥ 5 WARN+ log; istek ≥ 20 iken ≤ ×0,5). Sonuç `symptoms.json` (`view/` dışında).
  - `trial_ask_models.py`: JSON şeması `root_cause_candidates` (`response_format` `json_schema`, `strict`; tam 3 `{service, reason}`, enum yok). Yerel llama.cpp, Groq ve Gemini'de denendi: 5 servis istendiğinde bile üçü de geçerli JSON ve tam 3 aday döndürdü. Adlar harf dışı karakterler atılarak karşılaştırılıyor; özette olmayan adlar `unmatched` sütununda. İlk denemenin `--score` tablosu birebir aynı (yeni sütun en sonda). İstem metni Eren onaylı (sadece veri tanımına CPU/bellek cümlesi eklendi).
- Ölçüt sonuçları:
  - Vaka kayıtları (`case.json`, UTC; flag açık aralığı): vaka 3 `adHighCpu` `on` 22:56:58–23:07:04; vaka 4 `productCatalogFailure` targeting `if[1]`=`on` 23:19:28–23:29:34 (ResolveBoolean context `product_id=OLJCESPC7Z`, `TARGETING_MATCH`); vaka 5 `productCatalogLockContention` `on` 23:41:03–23:51:09; vaka 6 `intlShippingSlowdown` `10sec` 00:02:34–00:12:39 (ResolveInt 10; shipping int okuyor). Hepsi flagd'den ≤ 1 sn'de doğrulandı, kapanışta off. Konteyner sayısı üç kontrolde 22, zamanlayıcı kapalı; 25 konteyner çalışıyor, `RestartCount` 0, `OOMKilled` yok. GEÇTİ.
  - Özetler: token 1.764 / 1.789 / 1.744 / 1.733 (istemle 2.035 / 2.060 / 2.015 / 2.004); sızıntı CLI'ı dördünde `clean`; SHA256 `f59d4509…`, `d68f5cc9…`, `019a4e11…`, `784d5baa…` (tamı `case.json`'da). GEÇTİ.
  - Belirti kontrolü (modellerden önce): vaka 3 belirtili (ad CPU 1,42 → 397,15); vaka 4 belirtili (product-catalog hata oranı 0 → 0,082); vaka 5 belirtili (p95 23,6 → 25.692,7 ms, istek 3.243 → 1.405); vaka 6 **belirtisiz** (shipping p95 3,4 → 3,5). Bilgi için (karar özete göre): vaka 6'da 131 shipping isteğinden sadece 1'i > 9 sn; yük üreteci neredeyse hiç yurt dışı adres göndermiyor.
  - Sonuç tablosu (doğru servisin sırası; ✗ = ilk 3'te yok; süre sn):

    | Model | Vaka 3 ad | Vaka 4 product-catalog | Vaka 5 product-catalog | Vaka 6 shipping (belirtisiz) | süre |
    |---|---|---|---|---|---|
    | `qwen3.5-2b` | ✗ | ✗ | 1 | ✗ | 25–29 |
    | `qwen3.5-4b` | 1 | 3 | 1 | ✗ | 54–64 |
    | `qwen3.5-9b` | 1 | 3 | 2 | ✗ | 102–107 |
    | `gpt-oss-120b` | 1 | 2 | 1 | ✗ | 1,3–1,6 |
    | `gemini-3.5-flash-lite` | 1 | 1 | 1 | ✗ | 1,2–1,6 |

    20 cevabın hepsi geçerli JSON, tekrar deneme yok, `unmatched` boş. Girdi token: yerel 2.020–2.076, Groq 1.966–2.009 (+ düşünme 135–186), Gemini 2.447–2.506. Satır satır tablo: `python tools/trial_ask_models.py ~/cerebrum2/quality_trial/case{3,4,5,6} --score`. GEÇTİ (ölçüldü ve yazıldı).
  - Yorum (DECISIONS 2026-10-21 zor deneme kuralı, "çözer" = ilk 3): vaka 3, 4, 5'te iki büyük model çözer ve küçüklerden en az biri çözer → üçü de **umut var**. Boyuta göre: 2B üç belirtili vakanın birinde; 4B ve 9B üçünde (vaka 4'te ikisi de 3. sırada). Vaka 6 belirtisiz, yoruma girmez (beşi de çözemedi, beklenen).
  - `pytest` 190 yeşil. PR #14 koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/39879013368 (`b8394a1`).
- Dikkat:
  - Örnek küçük: yorumlanabilen 3 vaka, ikisinin kök nedeni aynı servis (product-catalog). product-catalog normal dönemde de yüksek CPU'da (vaka 3: ort. %53, en yüksek %84) ve modeller onu sık listeye koyuyor (vaka 3 ve 6'da 5 cevabın 4'ünde). "Hep product-catalog" diyen bir model vaka 4 ve 5'i çözmüş görünürdü; sonuç küçük modellerin işe yaradığını tek başına göstermez.
  - İlk 3 cömert: ~16 servisten rastgele 3 seçmek bile ~%19. Vaka 4'te top-1'i sadece Gemini buldu.
  - Ezber sınırlaması: büyük modeller OTel Demo'yu eğitimde görmüş olabilir (flag senaryoları upstream'de açık).
  - Süzmede yeniden yazılan product-catalog mesajları (`failed to load product from catalog`, kilit logu) vaka 4 ve 5 özetlerinde hiç görünmedi: WARN+ loglarda product-catalog satırı yok (vaka 4'te sadece frontend `API request failed` 279 ve `Checkout failed to place order` 3). Yeniden yazımın gerçek veride çalıştığı bu denemede gösterilmedi (C2 için).
  - Normal dönem tabanı vakalar arasında oynuyor: product-catalog CPU ort. %53 / %21 / %14 (vaka 3/4/5), p95 172,8 / 49,2 / 23,6 ms.
  - Vaka 3'te kayıt betiği (repo dışı) alarm zamanını yanlış alandan okudu; özet 15 sn sonra elle aynı alarmla alındı, veri kaybı yok. Kontroller ve kayıt betikleri repoya alınmadı (vaka üretim kartında işe yarar: flag yaz/doğrula, targeting dalı, konteyner sayısı, zamanlayıcı, `docker stats` örneği, telemetri yedeği).
  - Kart 3. madde bellek için "ortalama ve en yüksek" diyordu; en yüksek Eren kararıyla çıkarıldı (token).

## 2026-10-23 · Planlama → Planlama (zor deneme doğrulaması)
- Doğrulama (planlama, main `88c13a6`; PR #14 koşusu yeşil, birleşmeden sonra dala commit yok):
  - `trial_ask_models.py --score` vaka 3–6 tablosunu kayıtlı cevaplardan birebir üretti; vaka 1–2 tablosu yeni ad karşılaştırmasıyla değişmedi.
  - Dört özetin SHA256'sı `case.json`'la aynı; sızıntı CLI'ı dördünde `clean`.
  - Vaka 6 özeti `filtered/`'dan yeniden üretildi, SHA256 aynı (`784d5baa…`). Vaka 3–5'in penceresi döndürmeyle silinmiş; vaka 5'te betik "window not covered by data" verdi (koruma çalışıyor).
  - `trial_symptoms.py` dört vakada aynı `symptoms.json`'u üretti.
  - Kod: şema `strict`, tam 3 aday, enum yok; ad karşılaştırması `[^a-z]` atılarak (rakam da atılıyor; şimdiki servis adlarında rakam yok). Özette izleme araçları yok, astronomy-db ve valkey-cart var.
  - CPU düzeltmesi model sonuçlarından önce, önceden yazılmış ölçütle ve Eren onayıyla yapılmış; ölçüt sonuca göre değişmemiş.
- Düzeltme (vaka 6 neden belirtisiz): sonuç kaydındaki "yük üreteci yurt dışı adres neredeyse göndermiyor" açıklaması eksik. `people.json`'da 9 kişinin 1'i Kanada (siparişlerin ~%11'i, katalogdaki gibi). Vaka 6'da alarm sonrası 26 sipariş → ~3 yurt dışı beklenir, 1 geldi (tesadüf sınırında). Asıl sebep yapısal: gecikme sadece `ship-order`'da; shipping'in 131 isteğinin ~105'i fiyat sorgusu (`quote`). 3 sipariş de gecikse istek payı ~%2 < %5 → p95 değişmez; checkout'ta da 26 siparişin 1–3'ü. Bu özet ve 10 dk pencereyle senaryo görünmez; C2 kalibrasyonunda karar (INCIDENT_CATALOG notu).
- Yorum notları:
  - Belirtili vakaların sapmaları çok büyüktü (ad CPU 1,4 → 397; product-catalog p95 23,6 → 25.693 ms): "zor" vakalar yüksek sesliydi.
  - Vaka 4 en öğretici: Gemini dışında bütün modeller hatayı gösteren çağıranları (frontend, checkout) kök nedenin önüne koydu. Daraltmanın asıl işi: hatanın çıktığı en derin servisi öne almak. Daraltma kartında bu vaka akılda tutulur.
  - Boyut: 2B 1/3, 4B ve 9B 3/3; 9B 4B'den ~2 kat yavaş ve fazladan bir şey göstermedi. Model seçimi geliştirme setinde; şimdi eleme yok.
  - Eren: kaba denemelerin başarısı zayıf; büyük modellerin OTel Demo'yu eğitimde görmüş olması muhtemel (kesin değil). Eşit şartlar sorusu açık (aşağıdaki planlama önerisi Eren'e soruldu).

## 2026-10-23 · Planlama → Uygulama (takma ad ön denemesi)
- Yapılan (planlama): DECISIONS 2026-10-23 (takma ad ayarı, ön deneme); GLOSSARY'de takma ad ve eşleme; zor deneme doğrulaması yukarıda; INCIDENT_CATALOG `intlShippingSlowdown` notu; PROJECT güncellendi.
- Amaç: büyük (ve küçük) modellerin deneme vakalarındaki başarısının ne kadarının OTel Demo'yu tanımaktan geldiğine kaba bakmak. Oran değil, rapora girmez.
- Beklenen:
  1. Dal `task/alias-trial`; ilk commit planlamanın docs değişiklikleri (DECISIONS, GLOSSARY, HANDOFF, INCIDENT_CATALOG, PROJECT). **PR birleştikten sonra dala commit atılmaz.**
  2. **Dönüştürme betiği** (adı, kod adı ve çıktı klasörleri önce Eren'e önerilir; repo dışı, `view/` mantığı korunur): `~/cerebrum2/quality_trial/case1`…`case6`'daki `view/summary.json`'dan takma adlı kopya. Eşleme GLOSSARY'deki tablo (16 ad), bütün vakalarda aynı. Değişen: servis adı alanları; mesajlardaki tanımlayıcı biçimler (`product-catalog`, `frontend-proxy`, `ProductCatalog`, `CheckoutService`, `oteldemo.` gibi); `astronomy`, `valkey`, `otel`, `opentelemetry`. Kalan: mesajlardaki sıradan İngilizce kelimeler (payment, cart, email, shipping, checkout…; e-ticaret anlamı korunur, demoyu ele vermez). Değiştirmede uzun adlar önce (`frontend-proxy` `frontend`'den önce). Rakamlar, alanlar, sıra ve mesajların geri kalanı aynı.
  3. **Koşular** (`trial_ask_models.py` aynı istem ve ayarlar, JSON şeması): (a1) ve (a2) gerçek adlı özetlerle beş model, aynı gün iki kez; (b) takma adlı özetlerle beş model. Her koşul ayrı cevap klasörüne (seçenek ve klasör adı önerilir). Cevaplar eşlemeyle gerçek ada çevrilip puanlanır; özette olmayan adlar `unmatched`. Eski cevaplar yerinde kalır, üzerine yazılmaz; tabloda bilgi olarak, gürültü hesabına girmez.
  4. **Bilgi yoklaması** (ölçüte girmez): beş modele aynı istem: OpenTelemetry Demo'daki (Astronomy Shop) hata senaryolarını (feature flag) ve etkiledikleri servisleri listelemesi. İstem metni Eren'e önerilir. Cevaplar deneme klasörlerinin dışında, ayrı klasörde (cevap içerir; adı önerilir). Doğru bilinen flag/servis eşleşmeleri sayılır (OTEL_DEMO "Hata senaryoları" tablosuna göre).
- Bitti ölçütü (ölçmeden önce yazıldı, sonuca göre değişmez):
  - Dönüştürme kontrolü (modellerden önce): takma adlı 6 özette sızıntı CLI'ı `clean`; servis adı alanlarında 16 gerçek addan hiçbiri yok; mesajlarda gerçek adların tanımlayıcı biçimleri (tireli, CamelCase, `…Service`, `oteldemo.`) ve `astronomy`, `valkey`, `otel`, `opentelemetry` geçmiyor (sıradan kelimeler aranmaz); ad dışındaki bütün değerler gerçek adlı özetle aynı (betikle karşılaştırma); token sayıları kayda (≤ 2048).
  - Sonuç tablosu: 6 vaka × 5 model × {eski (bilgi), (a1), (a2), (b)}: top-1, top-3, `unmatched`. Gürültü (a1–a2) ve yorum DECISIONS 2026-10-23 kuralıyla, model başına; vaka 6 tabloda, yorumda değil.
  - Bilgi yoklaması: model başına doğru flag→servis eşleşmesi sayısı (13 minimal mod flag'inden).
  - `--score` ilk iki denemenin tablolarını aynı üretmeye devam eder. `pytest` yeşil; PR koşusu yeşil.
- Dikkat:
  - Takma ad log mesajlarındaki ayırt edici ifadeleri (ör. `Invalid token`) silmez; bunlar belirti, kalır. Model bu ifadelerden demoyu tanıyabilir: sınırlama olarak yazılır.
  - Gemini anlık 503: tek yeniden deneme, `retried_after` kayda.
  - Demo kapalı; ~65 dk (üç koşul), uzun koşu değil; prizde.
  - Planlama düzeltmesi (2026-10-23, ölçmeden önce, uygulamanın itirazı): gürültü eski cevaplardan değil (a1–a2)'den; dönüşüm sıradan kelimeleri değiştirmez.
  - Kart dışı: C2, yeni vaka, daraltma, ham log/ajan yolunda takma ad (değerlendirme kartı).

## 2026-10-23 · Uygulama → Uygulama (takma ad ön denemesi: kararlar, ölçmeden önce)
- Dönüştürme: `demo.` öneki de tanımlayıcı biçimlerden sayılır (`oteldemo.` gibi); önek silinir, gerisi kalır. Örnek (vaka 1 payment logu): `demo.user_context.loyalty_level=gold` → `user_context.loyalty_level=gold`. Ölçütteki "mesajlarda geçmiyor" kontrolüne `demo.` de girer (Eren, 2026-10-23; uygulamanın notu üzerine, model koşmadan önce).
- Altı özetteki bütün WARN+ mesajları (dönüştürmeden önce bakıldı): 3 farklı mesaj, 4 kayıt (`Payment request failed. Invalid token. demo.user_context.loyalty_level=gold`, `Checkout failed to place order`, `API request failed`); takma adın etkisi asıl olarak servis adı alanlarında.
- Bilgi yoklaması sayımı: serviste sondaki `service` eki atılır (`adservice` = `ad`, `productcatalogservice` = `product-catalog`); eski demo sürümlerinin adlarını bilen model düşük görünmesin (Eren seçeneği A, 2026-10-23, ölçmeden önce). Flag adında değişiklik yok.
- Puanlama düzeltmesi (sahte cevapla bulundu, ölçmeden önce): takma adlı koşuda cevaptaki gerçek ad (özette yok) `unmatched`'e düşer ve doğru sayılmaz; ilk sürüm onu gerçek ada eşleyip doğru sayıyordu. İlk iki denemenin tabloları değişmedi.

## 2026-10-23 · Uygulama → Planlama (takma ad ön denemesi, sonuç)
- Yapılan (dal `task/alias-trial`):
  - `tools/trial_alias.py`: `view/summary.json` → `view_alias/summary.json` (servis adı alanları; mesajlarda tireli/alt çizgili, CamelCase, `…Service` biçimleri; `oteldemo.` ve `demo.` önekleri silinir; uzun adlar önce). Aynı betik kontrolü yapar: alanlarda gerçek ad yok, mesajlarda tanımlayıcı biçim ve `astronomy`/`valkey`/`otel`/`opentelemetry` yok, ad dışındaki değerler/alanlar/sıra aynı, mesajların değişmeyen parçaları aynı sırada; tutmazsa yazmaz (çıkış 1). Bozuk girdilerle denendi (gerçek ad, sayı, sıra, mesaj metni, `valkey`): hepsinde yazmadı.
  - `trial_ask_models.py`: `--view`, `--answers`, `--alias` (puanlamada takma ad → gerçek ad), `--probe` (bilgi yoklaması, `--score` ile sayım). Varsayılanlarla ilk iki denemenin tabloları birebir aynı.
  - Yerel sunucu düzeltmesi (Eren onayı, kart dışı küçük iş): `start_local`/`stop_local` eski konteynerin silinmesini bekliyor (a2'de 9B açılışı `docker run` 125 ile düştü; `--rm` silmesi bitmeden aynı ad). Arka arkaya üç açılışla denendi.
- Ölçüt sonuçları:
  - Dönüştürme kontrolü (modellerden önce): 6 özette geçti; değişen tek mesaj vaka 1 (`demo.` silindi). Sızıntı CLI'ı 6 `view_alias/`'ta `clean`. Token (özet / istemle): vaka 1–6 875/1146, 858/1129, 1769/2040, 1796/2067, 1749/2020, 1738/2009 (gerçek adla 869–1789). GEÇTİ.
  - Koşular (aynı gün, 2026-10-23 17:39–19:10 UTC): (a1), (a2), (b), bilgi yoklaması. a2'de 9B sunucu açılamadı; 9B a2 aynı akşam ayrıca koşuldu (aynı ayarlar). 120 cevabın hepsi geçerli JSON, tekrar deneme yok, `unmatched` hepsinde boş (takma adlı koşuda gerçek ad kullanan model yok).
  - Sonuç (belirtili vaka 1–5'te ilk 3'te çözülen sayı; eski = önceki denemelerin cevapları, bilgi):

    | Model | eski | a1 | a2 | b (takma ad) | gürültü | karar |
    |---|---|---|---|---|---|---|
    | `qwen3.5-2b` | 3 | 3 | 3 | 3 | 0 | bu vakalarda görülmedi |
    | `qwen3.5-4b` | 5 | 5 | 5 | 5 | 0 | bu vakalarda görülmedi |
    | `qwen3.5-9b` | 3 | 5 | 5 | 4 | 0 | bu vakalarda görülmedi |
    | `gpt-oss-120b` | 5 | 5 | 5 | 5 | 0 | bu vakalarda görülmedi |
    | `gemini-3.5-flash-lite` | 5 | 5 | 5 | 5 | 0 | bu vakalarda görülmedi |

    Kural (DECISIONS 2026-10-23): gürültü ≥ 2 → belirsiz; b ≤ min(a1, a2) − 2 → ezber işareti. Hiçbir modelde ikisi de yok. 9B'nin tek kaybı vaka 4 (takma adla ilk 3'te yok). Vaka 6 belirtisiz: dört koşulda beş model de çözemedi. Satır satır: `python tools/trial_ask_models.py ~/cerebrum2/quality_trial/case{1..6} --answers answers_a1 --score` (a2 aynı; b: `--view view_alias --answers answers_alias --alias`). GEÇTİ (ölçüldü ve yazıldı).
  - Bilgi yoklaması (13 flag; doğru flag adı / doğru flag→servis çifti): 2B 0/0 (tek anlamsız satır), 4B 0/0 (boş liste), 9B 0/0 (`OTEL_FEATURE_FLAGS`), gpt-oss-120b 1/1 (`payment-failure` → payment; diğerleri `checkout-failure`, `inventory-failure`, `recommendation-failure` genel kalıplar, bu da büyük ihtimalle tahmin), Gemini 0/0 (10 uydurma `…ServiceFailure`, eski `…service` adlarıyla). Cevaplar `~/cerebrum2/quality_trial_probe/`. GEÇTİ (ölçüldü).
  - `pytest` 190 yeşil. PR #15 koşusu yeşil: https://github.com/erenbezek/aiops_rca/actions/runs/40009549741 (`7433d11`).
- Dikkat:
  - Takma adla top-1 biraz düştü (ölçüt değil): gpt-oss-120b 4 → 3, Gemini 5 → 4, ikisi de vaka 5'te (product-catalog → inventory 2. sıraya, önüne order-processor / suggestions). 4B ve 9B top-1 a1'de de 3.
  - Gürültü 0 (çözülen sayı farkı): yerel modeller temperature 0'da a1 ve a2'de birebir aynı cevap verdi. API'de temperature 0'a rağmen adaylar değişti: gpt-oss vaka 1, 3, 4'te 2.–3. aday (sıra ya da başka servis), vaka 6'da (belirtisiz) üç adayın üçü de farklı (top-1 checkout → frontend-proxy); Gemini vaka 3'te 3. aday (quote → email). Belirtili vakalarda top-1 ve ilk-3 sonucu hiç değişmedi.
  - "Eski" ile a1 farkı (9B 3 → 5) koşul farkı: vaka 1–2 eski cevapları şemasız ve CPU/belleksiz istemle alındı (9B'nin "çözemedi"si biçimdi). Gürültüye girmedi.
  - Sınırlamalar: 5 belirtili vaka, sinyaller güçlü (özetteki hata/CPU/gecikme cevabı taşıyor); `Invalid token` gibi ayırt edici log ifadeleri kaldı; bilgi yoklaması sadece flag adlarını ölçüyor, mimariyi (hangi servis kimi çağırır) değil. Sonuç: bu vakalarda başarı ad tanımaya dayanmıyor gibi; "ezber yok" demek değil.
  - Süre: yerel modeller bu akşam dünden ~%30 yavaş (9B vaka 3–5'te 134–144 sn, zor denemede 102–107; yük ortalaması ~3). Ölçüt değil; neden araştırılmadı.

## 2026-10-23 · Planlama → Planlama (takma ad ön denemesi doğrulaması)
- Doğrulama (planlama, main `6875f76`; PR #15 koşusu yeşil, birleşmeden sonra dala commit yok):
  - (a1), (a2) ve takma adlı (b) tablolar kayıtlı cevaplardan aynı üretildi; belirtili 5 vakada çözülen: 2B 3/3/3, 4B 5/5/5, 9B 5/5/4, gpt-oss 5/5/5, Gemini 5/5/5.
  - Takma adlı 6 özet: planlamanın ayrı betiğiyle eşleme gerçek adlı özete uygulanınca birebir aynı (ad dışında fark yok; tek mesaj değişikliği vaka 1 `demo.` öneki). Servis alanlarında gerçek ad yok; `astronomy`/`valkey`/`otel`/`demo.`/tireli ve CamelCase adlar yok. Sızıntı CLI'ı altısında `clean`.
  - Bilgi yoklaması cevapları okundu, sayım doğru: hiçbir model OTel Demo flag'lerini hatırlamıyor (Gemini eski `…service` adlarıyla uydurma; gpt-oss'un tek eşleşmesi `payment-failure` genel kalıp).
- Sonucun gücü (planlamanın hatası): test ezberin **avantajını** ölçemezdi. Bu 5 vakada büyük modeller gerçek adla zaten 5/5 çözüyordu (tavan etkisi) ve özetteki sayılar cevabı taşıyordu (zor deneme doğrulamasında yazılmıştı). Ölçülebilen tek şey "takma ad modeli bozuyor mu" idi. Bu, öneri anında Eren'e açıkça söylenmeliydi; sadece "6 vaka, sinyal zayıf" denmişti. Değerli kalanlar: bilgi yoklaması (flag ezberi yok), takma ad aracı (asıl değerlendirmede hazır), API gürültüsü ölçüldü (temperature 0'da 2.–3. adaylar değişiyor). Ezberin güçlü testi asıl değerlendirmede, geliştirme setinin zor vakalarında gerçek ad/takma ad (DECISIONS 2026-10-23); yeni ön deneme yok. Süreç kuralı: güç kontrolü (DECISIONS 2026-10-23).
- Notlar (değerlendirme kartına):
  - Yerel modeller bu koşuda zor denemeden ~%30 yavaştı (9B 134–144 sn); nedeni araştırılmadı. Asıl koşulardan önce o gün hız yeniden ölçülür, bütçe ona göre.
  - Boyut: 4B her koşulda 5/5; karar geliştirme setinde.
  - `tools/trial_alias.py --help` yardım göstermiyor (argümanı yol sanıyor); küçük, sadece not.
- Eren (2026-10-23): C2 kartı önce ertelendi, aynı gün yazıldı (aşağıda).

## 2026-10-23 · Planlama → Uygulama (collector C2: positive_control, belirti korunması, kalibrasyon)
- Yapılan (planlama): DECISIONS 2026-10-23 (C2 tasarımı, güç kontrolü kuralı); takma ad ön denemesi doğrulaması yukarıda.
- Amaç: gerçek senaryolarla, süzülmemiş (`raw/`) ve süzülmüş (`filtered/`) çıkış yan yana açıkken her senaryoda: (1) sızıntı testi gerçek veride senaryoya özgü sızıntıyı buluyor, süzülmüş veride hiçbir şey bulmuyor; (2) süzme belirtiyi silmiyor; (3) senaryo 10 dk'da telemetride belirti üretiyor, varyant seçilebiliyor; (4) collector yük altında dayanıyor.
- Güç kontrolü (DECISIONS 2026-10-23): raw'da senaryoya özgü bulgu yok → sızıntı CLI'ı düzeltilir; filtered'da bulgu → collector kuralı düzeltilir; belirti raw'da var filtered'da yok → aşırı süzme, kural düzeltilir; belirti raw'da da yok → varyant değişir ya da senaryo katalogdan çıkar (Eren); iki seviye → vaka üretimindeki varyant (Eren); collector bellek sınıra yakın → limit değişir. Tavan/taban yok (senaryolar bağımsız). Zayıf yan: her senaryo bir kez; sınırda sonuçlar vaka üretiminde tekrarlanır. Ek (Eren, 2026-10-23): belirti gücü ve basit kural kontrolü → vaka üretiminde kendi altyapı hatalarımızın oranı ve zorluk seviyeleri (kural senaryoyu kolayca çözüyorsa o senaryo modelleri ayırt edemez; tavan etkisi model çalıştırmadan görülür).
- Beklenen:
  1. Dal `task/collector-c2`; ilk commit planlamanın docs değişiklikleri (DECISIONS, HANDOFF, PROJECT; main'de bekleyen takma ad doğrulaması dahil). **PR birleştikten sonra dala commit atılmaz.**
  2. **Koşucu betiği** (adı, çıktı klasörü ve kayıt alanları önce Eren'e önerilir; kayıtlar cevap içerir, repo dışı). Koşu başına: `tools/otel_demo.sh up --raw` → 22 konteyner (`count(container_uptime_seconds)`; değilse collector yeniden başlatılır, tekrar sayılır) → flagd-ui zamanlayıcısı kapalı → 10 dk normal → flag yaz, flagd'den doğrula (`productCatalogFailure` `product_id` bağlamıyla; sayısal flag'ler doğru tiple) → 10 dk → flag kapat, doğrula → ölçümler **hemen** (DECISIONS 2026-10-21: döndürme) → `RestartCount`/`OOMKilled` (hedef dışı beklenmeyen yeniden başlama → koşu geçersiz; `emailMemoryLeak`'te email'in yeniden başlaması beklenen, kayda) → `down`. Collector belleği dakikada bir. Vaka penceresinde 8080'den sadece flag yazma ve doğrulama.
  3. **Gece korumaları** (DECISIONS 2026-10-20 makine sınırları): priz (`AC online=1`), şarj sınırı 80, `x86_pkg_temp` kuralı, boş disk ≥ 30 GB, `systemd-inhibit`; biri tutmazsa başlamaz ya da sıradaki koşudan önce durur ve yazar. Güç profili `balanced`.
  4. **Ölçümler (koşu başına, raw ve filtered ayrı):**
     - Sızıntı: sızıntı CLI'ı raw'da çıkış 1 ve **senaryoya özgü** bulgu (flag adı ya da OTEL_DEMO sızıntı tablosundaki ifade; flagd/load-generator'ın rutin bulguları sayılmaz); filtered'da `clean`.
     - Belirti (kök neden servisi, telemetriden; normal 10 dk ile flag 10 dk): hata oranı, p95, p99, CPU, bellek, istek sayısı, yeni WARN+ log. Eşikler zor denemedekiler (HANDOFF 2026-10-23 sonuç kaydı) + p99 (×1,5 ve +20 ms). Karar: belirtili / belirtisiz / sınırda (karar veren sinyal eşiğe %20'den yakın).
     - Yeniden yazımlar: senaryoya özgü orijinal metin raw'da ≥ 1 ve filtered'da 0; yeni metin filtered'da ≥ 1 (product-catalog hata mesajı, kilit logları, `adManualGc`, shipping gecikme logu; WARN+ ile sınırlı değil, bütün sinyaller).
     - Collector: en yüksek bellek, yeniden başlama.
     - **Belirti gücü:** karar veren sinyalin (en güçlü sapma) gözlenen değişimi ve eşiğe oranı (kaç kat aştı), raw ve filtered için.
     - **Basit kural kontrolü** (model yok, filtered telemetriden; kural ölçmeden önce burada yazılı): kök neden servisi için kullanılan sinyaller ve eşikler **bütün servislere** uygulanır. Servis puanı = eşiği aşan sinyal sayısı; eşitlikte eşiği aşan sinyaller arasında en büyük oran (sonra/önce) öne geçer. En yüksek puanlı 3 servis kuralın cevabı; top-1 ve top-3 kayda. `astronomy-db` ve `valkey-cart` sadece CPU/bellekle puanlanır; izleme araçları puanlanmaz.
  5. **Kural testi betiği** (DECISIONS 2026-10-21; önerilen adlar `tools/test_collector_rules.sh`, `tests/fixtures/collector_rules/`, Eren onaylar): geçici collector'a C2'nin raw verisinden çıkarılmış küçük örnekler (her kurala en az bir); girdide bulgu > 0, çıktıda 0; kasıtlı kırmızı: bir kural silinince bulgu çıkar. Docker ister, CI'da koşmaz.
  6. Sıra: koşucu + 2 senaryo gözetimli (yeniden yazım içerenlerden: `adManualGc`, `productCatalogFailure`) → Eren onayı → gece (15 koşu, ~6–6,5 saat; sığmazsa iki gece) → kural testi betiği.
- Bitti ölçütü (ölçmeden önce yazıldı, sonuca göre değişmez):
  - 15 koşu kaydı: geçerli/geçersiz ve sebep; korumalar ve makine durumu (priz, şarj, sıcaklık, disk, güç profili).
  - `positive_control`: her geçerli koşuda raw'da senaryoya özgü bulgu ≥ 1, filtered `clean`. Tutmayan senaryo için sebep (CLI mı collector mı) yazılır, düzeltilir, o senaryo yeniden koşar.
  - Belirti tablosu: senaryo × {raw, filtered} × sinyal ve karar. Raw belirtili + filtered belirtisiz → aşırı süzme: kural düzeltilir, yeniden koşar.
  - Yeniden yazım tablosu: dört metin için raw/filtered sayıları.
  - Kalibrasyon önerisi INCIDENT_CATALOG'a (karar Eren'de): iki seviyeli senaryolarda varyant; belirtisiz senaryolar için seçenek (varyant, pencere ya da çıkarma); `intlShippingSlowdown` için p99 sonucu.
  - Collector: 15 koşuda yeniden başlama 0, en yüksek bellek < 400 MiB (kayda).
  - Zorluk tablosu: senaryo başına belirti gücü (eşiğin kaç katı) ve basit kuralın top-1/top-3 sonucu; kuralın kaç senaryoyu top-1'de çözdüğü. Yorum ve kendi hatalarımızın oranı önerisi vaka üretim kartında (karar Eren'de).
  - Kural testi betiği geçer, kasıtlı kırmızı kırmızı.
  - Gece sonunda `raw/` boş (örnekler çıkarıldıktan sonra silinir); `pytest` yeşil; PR koşusu yeşil.
- Dikkat:
  - C2 verisi vaka seti değildir: geliştirme/test setine girmez, snapshot kesilmez (snapshot biçimi vaka üretim kartında).
  - `DI` kuralı gerçek veride sınanamaz (tek kaynağı `imageSlowLoad`, katalog dışı); yazılır.
  - Modeller bu kartta çalışmaz.
  - Kart dışı: snapshot biçimi, depolama kartı, kendi altyapı hatalarımız, özet/daraltma tasarımı, model koşuları.

## 2026-10-24 · Planlama → Planlama (değerlendirme kartı: 30 vakanın ayırma gücü)
- Hesap (planlama, kaba): aynı 30 vakada iki model, McNemar p<0,05; iki modelin vakalardaki başarısı bağımsız varsayıldı.
  - Farkın görünmesi için gereken net vaka farkı: ters yönde 0 vaka varken 6 (%20); 1'de 7; 2'de 8; 3–4'te 9 (%30).
  - Farkı görme olasılığı (simülasyon): %70'e %80 → ~%8; %60'a %80 → ~%29; %50'ye %80 → ~%58; %50'ye %90 → ~%90.
- Anlamı: 30 vakalık set büyük farkları gösterebilir (küçük/büyük model, daraltmalı/daraltmasız), yakın farkları göstermez (4B/9B).
- Değerlendirme kartına (ölçmeden önce yazılır): bu, API gürültüsü ölçümüyle birlikte çalışmanın bilinen sınırı olarak yer alır. Model boyutu seçimi için ya vaka sayısı artırılır ya da yakın fark "ayırt edilemedi" diye yazılır. 1–2 vakalık fark "daha iyi" diye okunmaz.
- Şart değil, sınır notu; DECISIONS'a yazılmadı (Eren, 2026-10-24).

## 2026-10-24 · Uygulama → Uygulama (C2, ölçmeden önce)
- Planlama kararları (Eren onaylı, 2026-10-24); kart değişmez, bu bölüm ölçmeden önce yazıldı ve sonuca göre değişmez:
  - **Collector:** "en yüksek bellek < 400 MiB" ölçütü kalkar (konteyner sınırı zaten 400M; aşınca OOM, yeniden başlama ölçütüne takılır); en yüksek bellek sadece kayda. Yeni ölçüt: `otelcol_receiver_refused_*`, `otelcol_exporter_send_failed_*`, `otelcol_exporter_enqueue_failed_*` her koşuda seri olarak var ve pencerede (normal + flag) artış 0; seri yoksa ölçüt geçmez. `otelcol_processor_refused_*` bu sürümde yoksa kayda yazılır. Mevcut adlar ilk gözetimli koşuda listelenir. Not: `docker stats` süreç belleğini, `memory_limiter` Go heap'ini ölçer; aynı şey değil (yumuşak sınır ~220 MiB = %80 − %25 × 400 MiB).
  - **Güç formülü:** her sinyalde T = iki koşulun gerektirdiği değerlerin büyüğü (ör. p95 için max(önce × 1,5, önce + 20 ms)); güç = (sonra − önce) / (T − önce); istek düşüşünde ters yönde (önce − sonra) / (önce − T). Güç ≥ 1 belirtili; 0,8 ≤ güç < 1,2 sınırda. Senaryonun gücü = belirtili sinyaller arasında en büyük güç, karar o sinyale göre. Basit kuralda eşitliği oran değil güç bozar.
  - **Isınma:** koşu sırasında `x86_pkg_temp` kuralı tutmazsa koşu geçersiz, soğuyunca baştan koşulur. İkinci kez de ısınırsa üçüncü kez koşulmaz, kayda yazılır, karar Eren'de (`adHighCpu`'da olası).
- Kural testi örnekleri: DECISIONS 2026-10-24 (elle gözden geçirilmiş küçük raw örnekleri, satırlar Eren'e gösterilir).
- Planlama kararları (2) (Eren onaylı, 2026-10-24; ölçmeden önce yazıldı, sonuca göre değişmez). Yukarıdaki "Collector" maddesinin ölçüt kısmının ve "Güç formülü" maddesinin karar eşiklerinin yerine geçer:
  1. **Collector ölçütü:**
     - Kapsam: 6 dosya çıkışımız (`file/traces`, `file/metrics`, `file/logs`, `file/raw_traces`, `file/raw_metrics`, `file/raw_logs`). Her biri için `otelcol_exporter_sent_*` serisi var ve pencerede artış > 0; `send_failed` ve `enqueue_failed` artışı 0 (seri yoksa 0). `otelcol_receiver_refused_*` serisi var, artışı 0.
     - Artış = pencere sonundaki değer − pencere başından önceki son değer; pencere başından önce noktası olmayan seri 0'dan başlamış sayılır (pencerede 120 ile doğan seri → 120). Pencere: normal başı – flag kapanışı.
     - opensearch, otlp_grpc/jaeger, otlp_http/prometheus, span_metrics, debug (ve bulunan diğerleri): sadece kayda, sent ve failed artışı birlikte. `processor_refused` yoksa kayda.
     - Neden: bu sürümde `enqueue_failed` ve dosya çıkışlarının `send_failed` serisi hiç yok (sayaç ilk hatada doğuyor). Eski veride (zor deneme vaka 6) `send_failed_log_records` artışı yalnız opensearch'te (demonun log deposu), `file/logs` eksiksiz.
  2. **Senaryoya özgü bulgu:** CLI bulgusu (`flag_name` kuralıyla senaryonun flag adı ya da metinde senaryonun `PHRASES` ifadesi), flag penceresinde, senaryonun beklenen yolundaki serviste ≥ 1:
     - adManualGc → ad; cartFailure → cart; paymentUnreachable → checkout; productCatalogFailure ve productCatalogLockContention → product-catalog; recommendationCacheFailure → recommendation; intlShippingSlowdown → shipping. Bunlarda flagd bulgusu sayılmaz.
     - adFailure, adHighCpu, emailMemoryLeak, paymentFailure → flagd (OTEL_DEMO sızıntı tablosuna göre ad, email ve payment flag değerlendirme olayı yaymıyor).
     - loadGeneratorFloodHomepage → load-generator kaydı ve aynı satırda flood ifadesi.
     - Normal pencere sayısı ve servis kırılımı kayda; senaryonun flag adı beklenmeyen bir serviste çıkarsa kayda.
     - Gözetimli iki koşudan sonra, geceden önce: raw'daki `flag_name` bulgularının servis kırılımı bu tabloyla karşılaştırılır. Tutmazsa tablo geceden önce düzeltilir (Eren).
  3. **Belirti kararı:** sınırda önce gelir: güç < 0,8 belirtisiz; 0,8 ≤ güç < 1,2 sınırda; ≥ 1,2 belirtili. raw ve filtered kararı farklıysa (herhangi iki kategori) sinyal bazında incelenir; sinyal başına güç iki taraf için kayda. Kök neden servisinde CPU ya da bellek iki pencerede de değersizse karar "ölçülemedi" (belirtisiz değil); değersiz sinyaller kayda.
  4. Yeni WARN log gücü = en sık yeni mesajın sayısı / 5.
  5. Soğuma: 2 dk boyunca 90 °C altı.
  6. **Pencere kapsaması:** bütün dosya çıkışlarında `max_megabytes` 100 → 300 (raw ve filtered; `max_backups` 2; en fazla 5,4 GB; DECISIONS 2026-10-24). Kopyalamada her {raw, filtered} × {traces, metrics, logs} için kaynak dosyalardaki en eski kaydın kendi zamanı (izlerde `startTimeUnixNano`, metriklerde `timeUnixNano`, loglarda `timeUnixNano`, 0 ise `observedTimeUnixNano`) ≤ pencere başı; değilse koşu geçersiz ("pencere döndürmeyle kısaldı (<base>/<signal>)"), bir kez yeniden koşulur, ikincisinde kayda, karar Eren'de. `run.json`'a sinyal başına en eski kayıt zamanı ve hız (MB/dk).
  7. **Süzülmemiş kopyalar:** `c2_runs/*/window/raw/` ve `samples/` kart bitince silinmez; planlama doğrulamasından sonra Eren onayıyla silinir ve kayda yazılır (DECISIONS 2026-10-24). Kural testi örnekleri bundan önce, kartın içinde seçilir. "Gece sonunda `telemetry/raw/` boş" ölçütü aynı.
  8. Adlar onaylı: `window/raw/`, `window/filtered/`, `collector_mem.tsv`, `containers_start.txt`, `containers_end.txt`.
  9. Gözetimli iki koşunun raporuna: sinyal başına raw ve filtered hız (MB/dk) ve 300 MB'la en kötü tutma süresi (600 MB / hız); otelcol metrik adları; madde 2 karşılaştırması.
- Uygulamanın tanımları (ölçmeden önce):
  - Kapsamadaki "pencere başı" = kopyanın başı (normal başlangıcı − 2 dk). Normal başından biraz sıkı: CPU'nun ilk hızı ve collector sayaçlarının "pencere başından önceki son değeri" bu 2 dk'dan geliyor.
  - Kopya: zamanlarından biri [normal − 2 dk, flag kapanışı + 1 dk] içinde olan satırlar (satır = bir OTLP isteği).
  - Senaryoya özgü bulgunun penceresi: satırdaki en büyük zaman flag yazılışı ile flag kapanışı arasında.
- Demo açmadan gösterildi (eski süzülmüş veri, zor deneme vaka 6 penceresi; sahte raw satırları sızıntı fixture'larından):
  - Artış: pencerede 120 ile doğan sabit seri → 120; önceden 100 sabit → 0; önceden 50, sonda 80 → 30; pencereden sonra artan → 0. `file/raw_traces` `send_failed` pencerede doğunca ölçüt FAIL; sadece opensearch hatası → PASS (kayıtta); `file/logs` sent serisi yoksa FAIL.
  - Kapsama: pencere başı en eski kayıttan (filtered/metrics 2026-10-20T13:09:31Z) 1 dk önceye alınınca üç sinyal de "kısaldı"; 1 dk sonraya alınınca metrics kapsandı, traces/logs kısaldı (onların en eski kaydı daha yeni).
  - Uçtan uca: `positive_control` PASS (sahte shipping logu, beklenen yol shipping), filtered `clean`; eski veride `file/raw_*` sent serisi yok → collector FAIL (beklenen: o koşuda raw yoktu); opensearch `send_failed` +3742 kayıtta; ölçüm koşu başına ~3 dk.
  - Bulunan ve düzeltilen hata: pencere kopyası her kaynak dosyada hedefi yeniden açıp sıfırlıyordu (NUL dolu delikler).

## 2026-10-24 · Uygulama → Planlama (C2, gözetimli iki koşu)
- Koşular (UTC; `~/cerebrum2/c2_runs/`, `tools/scenario_runner.py run adManualGc_on productCatalogFailure_on`): korumalar tuttu (priz 1, şarj sınırı 80, `balanced`, inhibit, disk ~300 GB), en yüksek `x86_pkg_temp` 71 °C.
  - `adManualGc_on_1` (22:41–23:03): **geçersiz, uygulamanın hatası.** Kapsama kontrolü "pencere başı"nı kopyanın başı (normal − 2 dk = 22:40:18) aldı; raw klasörü koşudan önce boştu, ilk raw kaydı collector açılışı (22:41:54). Planlamanın tanımıyla (normal başı 22:42:18) kapsanıyordu. Koşucu kuralla bir kez yeniden koştu. Öneri aşağıda.
  - `adManualGc_on_2` (23:03–23:24): geçerli. Collector en yüksek bellek 127 MiB (ilk denemede 311 MiB).
  - `productCatalogFailure_on_1` (23:24–23:51): geçerli. 6 dk'da 21 konteyner → collector yeniden başlatıldı (normal öncesi, kurala göre), sonra 22. Flag `TARGETING_MATCH` ile doğrulandı. En yüksek bellek 125 MiB.
  - Pencerede yeniden başlama/OOM yok. Ölçüm koşu başına ~2,3 dk.
- Ölçümler (`measure.json`):

  | | adManualGc | productCatalogFailure |
  |---|---|---|
  | `positive_control` | PASS: raw flag penceresinde ad'de 233 (normal 16); filtered `clean` | PASS: raw flag penceresinde product-catalog'da 3274 (normal 3079, TracingHook her istekte); filtered `clean` |
  | Belirti (raw = filtered, aynı) | belirtili, p99 gücü 75,5 (p95 52, yeni WARN 23, CPU 3,8, bellek 1,04) | belirtili, hata oranı gücü 1,67 (gecikme/CPU/bellek < 0,1) |
  | Yeniden yazım | orijinal raw 123 / filtered 0; yeni filtered 123 | orijinal raw 1996 / filtered 0; yeni filtered 1996 |
  | Basit kural top-3 | ad (5 sinyal), frontend-proxy, frontend → top-1 ✓ | frontend (2), checkout, product-catalog → top-1 ✗, top-3 ✓ |
  | Collector | PASS | PASS |

  - Aşırı süzme görülmedi: iki koşuda raw ve filtered kök neden sinyalleri birebir aynı.
  - Collector: 6 dosya çıkışında sent artışı > 0, `send_failed`/`enqueue_failed` serisi yok (0); `receiver_refused` 27–28 seri, artış 0; `processor_refused` yok. Kayıt: opensearch 20 dk'da sent ~25 bin, `send_failed` ~10,5 bin (demonun log deposu ~%30 kayıp; bizim dosyalar etkilenmiyor); `jaeger_storage_exporter` da listede.
- Madde 9 — hız ve 300 MB'la en kötü tutma (600 MB / hız; iki koşunun büyüğü):

  | | traces | metrics | logs |
  |---|---|---|---|
  | raw MB/dk | 7,37 → 81 dk | 3,03 → 198 dk | 2,67 → 225 dk |
  | filtered MB/dk | 6,53 → 92 dk | 1,74 → 345 dk | 2,17 → 276 dk |

  Pencere başından kopyaya ~22 dk; en kötü 81 dk ile ~3,7 kat pay (trafik seli için).
- Madde 9 — otelcol metrik adları (39): `otelcol_exporter_{sent,send_failed}_*` (send_failed yalnız `log_records`, yalnız opensearch), `otelcol_exporter_{in_flight_requests,queue_capacity,queue_size}`, `otelcol_receiver_{accepted,failed,refused}_*`, `otelcol_processor_{incoming,outgoing}_items`, `otelcol_processor_memory_limiter_accepted_*` (refused yok), `otelcol_processor_filter_*.filtered`, `otelcol_processor_batch_*`, `otelcol_process_*`, `otelcol_scraper_*`, `otelcol.resourcedetection.*`. `enqueue_failed` ve `processor_refused` adı hiç yok.
- Madde 2 — raw `flag_name` bulgularının servis kırılımı (iki koşu toplamı) ve tablo:
  - Tabloyla uyan: cartFailure → cart 240; paymentUnreachable → checkout 102; productCatalogFailure → product-catalog 11026; recommendationCacheFailure → recommendation 2250; intlShippingSlowdown → shipping 9; adManualGc → ad 127 (log); loadGeneratorFloodHomepage → load-generator 260 (flood ifadesi ayrıca aranır).
  - flagd yolundakiler: emailMemoryLeak flagd 102 (flag kapalıyken de, flag penceresinde ~20: email flagd üzerinden değerlendiriyor; ölçüt kolay geçer, ayırt edici değil); paymentFailure flagd pencere başına 1; adFailure ve adHighCpu flagd 1 (sadece normal penceresinde, açılışta). Değişen flag'in adı flagd'de yazma anında görünüyor (adManualGc: flag penceresinde flagd 2), adFailure/adHighCpu'nun flag penceresindeki flagd bulgusu buna dayanacak; gece görülür.
  - Tabloda olup görülmeyen: productCatalogLockContention product-catalog'da `flag_name` yok (sadece flagd 1). Ölçüt PHRASES (`lock contention scenario` logu, sadece açıkken) ile geçmeli; gece görülür.
  - Beklenmeyen servis: adFailure ve adHighCpu ad'de 1'er (normal); emitRawPii → checkout 107; failedReadinessProbe → cart 138 (senaryo değiller).
  - Servissiz kayıt (`-`): adManualGc ve productCatalogFailure 88–92 / koşu: raw'da `host_metrics` süreç metrikleri (`processscraper`), koşucunun komut satırı (`scenario_runner.py run adManualGc_on productCatalogFailure_on`) sızıyor. filtered'da yok (C1 kuralı: processscraper tümden düşer). Gece koşusu `run all` ile bütün senaryo adlarını komut satırına koyar: raw'da her senaryo adı her koşuda görünür; `-` beklenen yolda olmadığı için senaryoya özgü sayılmaz.
  - Sonuç: tablo değişikliği gerekmiyor görünüyor; karar planlamada.
- Kural testi adayları için not: `samples/` kayıtları makineye ait bilgi taşıyabiliyor (`processscraper`: komut satırı, ev klasörü yolları). Repoya girecek örnek seçilirken temizlenmeli/kısaltılmalı; satırlar Eren'e gösterilecek.
- Öneri (onay bekliyor): kapsama kontrolünde pencere başı = normal başlangıcı (planlamanın tanımı); kopya yine normal − 2 dk'dan başlar. Geceden önce.
- Kapsama düzeltmesi yapıldı (Eren onayı, 2026-10-24; gece koşusundan önce): pencere başı = normal başlangıcı; kopya yine normal − 2 dk'dan başlar, pay kontrolde aranmaz. `adManualGc_on_1` kayıtlı değerleriyle yeni kural: raw en eski kayıtlar 22:41:54–56 ≤ normal başı 22:42:18 → kapsanırdı. O koşu yine geçersiz kalır (kayıt değişmez), `adManualGc_on_2` geçerli olan.
- Planlama (Eren onaylı, 2026-10-24), gece koşusundan önce; ölçmeden önce yazıldı:
  - Beklenen yol tablosu değişmez; gece koşusuna geçilebilir.
  - `positive_control` 0 çıkan koşuda karar sırası: (1) CLI'ın flag penceresindeki bulgularında senaryonun flag adı/ifadesi başka bir serviste var mı (servissiz `-` hariç)? Varsa tablo eksik → kayda, tablo düzeltilir, yeniden koşulmaz. (2) Yoksa raw flag penceresinde düz metin araması: bulursa CLI hatası → düzeltilir, senaryo yeniden koşar; bulmazsa bu senaryoda sızıntı yolu yok → kayda, CLI hatası sayılmaz, yeniden koşulmaz.

## 2026-10-24 · Uygulama → Planlama (C2, gece koşusu sonucu)
- Koşu: `scenario_runner.py run all`, 2026-10-24 00:19–09:03 UTC (03:19–12:03 yerel). Prizde, şarj sınırı 80, `balanced`; en yüksek `x86_pkg_temp` 77 °C (adHighCpu), ısınma yok. Ölçüm: 13 geçerli koşu `c2_measure.py` (4 paralel, ~25 dk).
- 15 koşudan 13 geçerli (gözetimli `adManualGc_on_2` ve `productCatalogFailure_on_1` da geçerli):
  - `productCatalogFailure_on_2` **geçersiz (elle):** makine 04:56–07:06 UTC uykuda kaldı (systemd-inhibit `block` kilidine rağmen; GNOME'un 2 saat hareketsizlik uykusu açık: `sleep-inactive-ac-timeout` 7200, `-type` suspend; logind kaydında isteği gönderen yok, en olası GNOME). Uyku normal penceresinin ortasına düştü; koşucu bekleme süresini monotonik saatle saydığı için fark etmedi ve "VALID" yazdı (uygulamanın eksiği). Ölçülmedi; `productCatalogFailure_on_1` (gözetimli) geçerli sonuç. Kalan koşular `gnome-session-inhibit --inhibit suspend:idle` (elle, kod değişmeden) altında bitti.
  - `recommendationCacheFailure_on_1` **geçersiz (koşucu):** recommendation flag penceresinde 3 kez yeniden başladı (OOM bayrağı sonda yok). Kart "hedef **dışı** beklenmeyen yeniden başlama → geçersiz" diyor; koşucu yalnız email'i beklenen saydı (uygulamanın kartı dar okuması). Pencere elle kopyalandı (demo kapanırken; son saniyeler eksik olabilir, `window_manual_copy.json`), kayıt için ölçüldü: `positive_control` PASS, belirtili (p99 gücü 112, bellek 5,1, CPU 1,4), filtered `clean`, collector PASS, kural top-1 recommendation.
  - 16 koşunun 12'sinde normal öncesi konteyner sayısı 6 dk'da 21'de kaldı, collector yeniden başlatıldı (koşu başına +6 dk). Hangi konteynerin metriği eksik, bakılmadı.
- **Bitti ölçütleri:**
  - `positive_control`: 15/15 PASS (geçersiz recommendation dahil); filtered 15/15 `clean`. flagd yolundakiler flag penceresinde 2–39 bulgu (adFailure/adHighCpu 2: flag yazma anı). Beklenmeyen servis: adFailure/adHighCpu'da `ad` (flag adı, normal penceresinde 1); diğerlerinde `flagd` (yazma anı) ve `-` (`processscraper`, sadece raw).
  - Aşırı süzme: yok. 14 koşunun hepsinde kök neden servisinin bütün sinyalleri raw ve filtered'da aynı (`verdicts_differ` hep False).
  - Yeniden yazımlar (raw orijinal / filtered orijinal / filtered yeni): `adManualGc` 109/0/109; product-catalog hata mesajı 1996/0/1996; kilit logu (`lock_holding`) 15/0/15; shipping gecikme logu 8/0/8. `lock_failed` ("failed to acquire lock…") hiç görülmedi.
  - Collector: 15/15 PASS (6 dosya çıkışı sent > 0, failed 0; `receiver_refused` 0); pencerede collector yeniden başlaması yok; en yüksek bellek 118–128 MiB (sadece gözetimli ilk denemede 311). opensearch her koşuda ~%30 kayıp (sent ~25 bin, failed ~10 bin; kayıt).
  - Hız ve en kötü tutma (300 MB, 600 MB / hız): raw traces 8,89 MB/dk (flood) → 67 dk; filtered traces 7,94 (flood) → 76 dk; metrics/logs ≥ 198 dk. Pencereden kopyaya ~22 dk.
- **Belirti ve zorluk tablosu** (filtered; raw aynı). Güç = karar veren sinyalin eşiğe oranı. Kural = basit kural top-3:

  | Senaryo | Karar | Güç (sinyal) | Kural top-1 / top-3 |
  |---|---|---|---|
  | adFailure | belirtili | 6,0 (yeni WARN; hata oranı 2,8) | ad ✓ / ✓ |
  | adHighCpu | belirtili | 78,6 (CPU 1,3 → 394) | ad ✓ / ✓ |
  | adManualGc (gece) | belirtili | 118,6 (p99 4,5 → 2377 ms) | ad ✓ / ✓ |
  | cartFailure %10 | belirtisiz | 0,14 (bellek; hata oranı +0,001) | checkout ✗ / ✗ |
  | cartFailure %50 | sınırda | 0,8 (4 yeni WARN "Wasn't able to connect to redis"; hata oranı +0,005) | checkout ✗ / ✗ |
  | emailMemoryLeak 100x | belirtisiz | 0,70 (bellek 68 → 77 MB) | ad ✗ / ✗ |
  | emailMemoryLeak 1000x | belirtili | 2,95 (bellek 50 → 80 MB; yeniden başlama yok) | email ✓ / ✓ |
  | paymentFailure %10 | belirtisiz | 0,77 (hata oranı +0,038) | checkout ✗ / ✗ |
  | paymentFailure %50 | belirtili | 7,8 (hata oranı +0,39) | payment ✓ / ✓ |
  | paymentUnreachable | belirtili | 20 (checkout hata oranı 0 → 1,0) | checkout ✓ / ✓ |
  | productCatalogFailure | belirtili | 1,67 (hata oranı +0,084) | frontend ✗ / ✓ |
  | productCatalogLockContention | belirtili | 1418 (p99 19 ms → 28 sn) | recommendation ✗ / ✓ |
  | recommendationCacheFailure (geçersiz) | belirtili | 112 (p99) | recommendation ✓ / ✓ |
  | intlShippingSlowdown 10sec | belirtili | 500 (p95 3,9 ms → 10,0 sn) | shipping ✓ / ✓ |

  - Geçerli 12 senaryo koşusunda basit kural top-1 7, top-3 9; belirtili 9 koşuda top-1 7, top-3 9/9. Belirtisiz/sınırda 4 koşunun (cart ×2, email 100x, payment %10) hiçbirinde kök neden ilk 3'te değil.
  - **Zor denemeyle çelişki:** intlShippingSlowdown zor denemede (aynı `10sec`) p95'te belirtisizdi; burada p95 10 sn (gecikme shipping isteklerinin %5'inden fazlasında). Neden (istek karışımı, tek koşu) bakılmadı.
- **Kalibrasyon önerisi** (karar Eren'de; INCIDENT_CATALOG'a onaydan sonra yazılır):
  - İki seviyeliler: paymentFailure %50 (%10 sınırın altında: 0,77); emailMemoryLeak 1000x (100x belirtisiz); cartFailure ikisi de belirtisiz/sınırda (cart'ta hata oranı ≤ %0,5; belirti cart'ın kendi telemetrisinde zayıf) → seçenek: %100 varyantı, daha uzun pencere ya da katalogdan çıkarma.
  - intlShippingSlowdown: 10sec bu koşuda p95'te de belirtili; p99 de 500 kat. Zor denemeyle çelişki tek koşu, vaka üretiminde tekrar görülür.
  - Zorluk: belirtili senaryoların çoğunda basit kural top-1'de çözüyor (tavan etkisine yakın); modelleri ayırt edecek olanlar zincirleme senaryolar (productCatalogFailure, LockContention: kural top-1'i kaçırıyor) ve belirtisi zayıf olanlar.
- Kalan işler (kart): kural testi betiği ve örnekleri (Eren'e satırlar gösterilir; `samples/` makine bilgisi taşıyabilir), sonra `telemetry/raw/` silinir (c2_runs kopyaları planlama doğrulamasından sonra), PR.
- Onay bekleyen kod düzeltmeleri (koşucu): (a) uyku algılama: duvar saati ile monotonik saat arasında pencerede > 1 dk fark → koşu geçersiz; (b) GNOME uyku engeli (`gnome-session-inhibit`, makinede kurulu) koşucunun kendi engeline eklenir; (c) kök neden servisinin yeniden başlaması beklenen sayılır (kartın "hedef dışı" ifadesi), kayda yazılır; bu düzeltmeyle `recommendationCacheFailure_on_1` geçerli sayılır mı (Eren).

## 2026-10-24 · Uygulama → Planlama (C2, koşucu düzeltmesi ve recommendation yeniden koşusu)
- Koşucu düzeltmeleri (Eren onayı, 2026-10-24; `5449029`):
  - (a) Uyku tespiti: normal başlangıcı ile flag kapanışı arasında `CLOCK_BOOTTIME − CLOCK_MONOTONIC` artışı (uykuda geçen süre) `run.json` `suspended_s`'e yazılır; > 60 sn → geçersiz. Duvar saati yerine BOOTTIME: NTP düzeltmelerinden etkilenmez.
  - (b) `run` kendini `gnome-session-inhibit --inhibit suspend:idle` + `systemd-inhibit` altında yeniden çalıştırır; korumalara `gnome_inhibited` eklendi (`gnome-session-inhibit --list`'te koşucunun suspend engeli var mı). Not: `--inhibit` listesi iki nokta üst üsteyle ayrılır; yardım metni virgül diyor ama virgüllü liste yok sayılıyor (denendi).
  - (c) Senaryonun kök neden servisinin yeniden başlaması / durması beklenen (`expected_restarts`); başka konteyner → geçersiz. `EXPECTED_RESTART` kaldırıldı (email zaten emailMemoryLeak'in kök nedeni).
  - Kontrol: sahte durumlarla recommendation yeniden başlaması → geçerli; cart yeniden başlaması ya da durması → geçersiz; kök nedensiz flood'da email yeniden başlaması → geçersiz. Korumalar engelsiz iki sorun, iki engel altında sorunsuz. pytest 190/190.
- `recommendationCacheFailure_on_2`, 13:07–13:29 UTC (16:07–16:29 yerel): **geçerli.** recommendation yine flag penceresinde 3 kez yeniden başladı (OOM bayrağı yok), beklenen sayıldı; başka yeniden başlama yok. `suspended_s` 0, 22 konteyner (collector yeniden başlatılmadı), en yüksek 68 °C, kapsama tuttu. Koşudan sonra engel kalmadı.
  - `positive_control` PASS (raw flag penceresinde 920 bulgu), filtered `clean`.
  - Belirti: raw ve filtered aynı, belirtili, güç 4,18 (p95 78 → 241 ms; p99 3,9; bellek 62 → 96 MB, 2,8). Kural top-1 recommendation.
  - Collector PASS (6 dosya çıkışı sent > 0, failed 0; `receiver_refused` 0). opensearch sent 23.936 / failed 9.913 (kayıt).
  - **Gece koşusundan fark:** (1) güç 4,18, gecenin geçersiz koşusunda 112 (p99). Aynı yön, büyüklük çok farklı; tek koşu, sebebine bakılmadı. (2) Collector belleği koşu boyunca 280–307 MiB, düz (gece 96–128). Bu koşuda collector yeniden başlatılmadı; gece başlatılan koşularda ~110. Gözetimli ilk denemedeki 311 de büyük ihtimalle aynı durum. Büyüme yok; bellek sınırına göre önemi planlamanın kararı.
- Tablo güncellemesi: `recommendationCacheFailure` geçerli koşu = `_2` (belirtili, 4,18, kural ✓ / ✓). Böylece tablodaki geçerli 14 senaryo koşusu (gece 12 + gözetimli productCatalogFailure_on_1 + bu koşu): belirtili 10, kural top-1 8, top-3 10/10. Düzeltme: gece raporundaki "Geçerli 12 senaryo koşusunda" tablodaki 13 satırı sayıyor, 13 olmalıydı (top-1 7 ve top-3 9 sayıları doğru).

## 2026-10-24 · Uygulama → Planlama (C2, kural testi betiği)
- `tools/test_collector_rules.sh` ve `tests/fixtures/collector_rules/` (adlar Eren onaylı; plan ve ölçütler ölçmeden önce, 2026-10-24). Sonuç: **PASS**, ~25 sn.
- Yöntem: geçici collector (demonun imajı, `.env` `COLLECTOR_CONTRIB_IMAGE`, şu an 0.159.0) gerçek `otelcol-config-extras.yml` + testin katmanı (otlp/http 127.0.0.1 boş port, dosya çıkışı, hatlarda yalnız `filter/sim_world` ve `transform/scrub`; girdi raw olduğu için upstream işlemcileri yok). Kayıtlar tek tek gönderilir; sızıntı = sızıntı CLI'ının bulgusu ya da yeniden yazımın orijinal metni (`c2_measure.REWRITES`).
- Örnek seçimi (scratch, repoya girmedi): 19 koşunun `samples/` + `window/raw`'dan kelime süzgeçli tek kayıtlar (423 aday) + normal pencereden temiz adaylar; her kural için silme / tek başına koşuları (collector'la, gerçek ayar).
  - 53 kural: **tek sorumlu 18** (silinince kendi örneği sızıyor), **yedekli 23** (gerçek kaydı başka kural da düşürüyor; ör. flagd istemci span'ini ad, `server.address` ve `rpc.service` kuralının üçü de yakalıyor). Plandaki "örnekli her kural silinince kırmızı" ölçütü yedeklilerde tutamazdı; Eren kararı (seçenek A): yedekliler `alone` testi (hiç kural yokken örnek sızıntılı, yalnız o kural varken düşer ya da temiz). Bu kontrolle 18 yedekli kural sınandı.
  - **Örneksiz 17** (`rules.tsv` `none`, gerekçeli): gerçek kaydı yok 12 (DI ×6, `lock_failed`, product-catalog mesajının log gövdesi hali, `url.path`/`http.route` ×4; `window/raw`'da doğrudan da arandı, 0); eşleşen kayıt bulgu taşımıyor 2 (collector'ın kendi logu, OpenFeature logu); eşleşen kayıtta başka sızıntı da var, kural tek başına temizlemiyor 3 (`feature_flag` anahtar silme kuralları: span, span olayı, log).
  - Fixture: 23 örnek + 9 temiz kontrol (32 satır; Eren satırları gördü ve onayladı). Temiz kontroller kurallara yakın ve düşmemeli: Envoy span ve erişim logu (normal yol), flagd dışı gRPC span ve RPC metriği, tarayıcı resourceFetch, flag dışı konteynerin docker metriği, normal span metriği, shipping ve ad logu. Temizlenen alanlar: `host.name`, `os.description`, `host.cpu.model.name`, `container.id`, `container.hostname`.
- Sonuç (ölçütler):
  - Kapsam: 53 kuralın hepsi `rules.tsv`'de bir kez (delete 18, alone 18, none 17).
  - Girdi: CLI 77 bulgu; her örnek sızıntılı, temiz kontroller temiz.
  - Tam ayar: 17 kayıt çıktı (9 temiz kontrol + 8 yeniden yazılan örnek), sızıntılı 0; 9 temiz kontrol girdiyle aynı.
  - `delete` 18/18 kırmızı; `alone` 18/18 (kuralsız kırmızı, tek başına yeşil). Collector logunda hata yok.
  - Kasıtlı kırmızı, betik düzeyinde: adManualGc yeniden yazımı silinmiş ayar → FAIL (kapsam + çıktıda 1 sızıntılı kayıt); logs `service.name` kuralı `".*"` yapılmış ayar (aşırı süzme) → FAIL (kapsam + 3 temiz log kontrolü düştü + 4 yeniden yazım testi kırmızı vermedi). Kullanım hatası → çıkış 2.
  - pytest 190/190.
- Bulunan ve düzeltilen hatalar (uygulamanın): aynı kural metni birden fazla bölümde geçiyor (`service.name`, OpenFeature kapsamı, `rpc.service`, `server.address`, `url.path`); kuralı yalnız metinle tanımlayan ilk kontrol yanlış satırı sildi → kural kimliği (section, rule), `rules.tsv`'de `section` sütunu. Sızıntı CLI'ı klasördeki bütün dosyaları okuyor → girdi taraması yalnız `.jsonl` kopyasında.
- Not (karar planlamanın): yedekli kurallar savunma katmanı; 23'ünden biri bozulursa gerçek hatta sızıntı olmaz ama bu test yakalar. `none` olan 3 anahtar silme kuralı için gevşek bir kontrol ("kuralın hedeflediği bulgu kaybolur") eklenebilir; bu kartta yapılmadı.

## 2026-10-24 · Uygulama → Planlama (C2 oturum sonu)
- Yapılan: C2 kartı bitti, PR #16 merge edildi (main `9cf8e6e`). Koşucu düzeltmeleri (uyku tespiti, GNOME engeli, kök neden servisinin yeniden başlaması beklenen), `recommendationCacheFailure_on_2` geçerli, kural testi betiği ve fixture'lar (Eren satırları onayladı), `telemetry/raw/` boşaltıldı (~2,4 GB, Eren onayı). Ayrıntılar bu dosyada 2026-10-24 tarihli dört Uygulama → Planlama kaydında.
- Beklenen (planlama): C2 sonuçlarının doğrulanması (`~/cerebrum2/c2_runs/*/run.json`, `measure.json`); kalibrasyon kararı → INCIDENT_CATALOG (payment %50, email 1000x, cartFailure için %100 / uzun pencere / çıkarma, intlShippingSlowdown çelişkisi); doğrulamadan sonra `c2_runs/*/window/raw/` ve `samples/` silme onayı (Eren).
- Dikkat:
  - recommendation belirti gücü iki koşuda çok farklı (112 → 4,18, aynı yön); intlShipping zor denemede belirtisiz, C2'de belirtili. Tek koşuluk sonuçlar.
  - Collector belleği normal öncesi yeniden başlatılmayan koşuda ~300 MiB, başlatılanlarda ~110 MiB (sınır ölçütü < 400 tuttu). 16 gece koşusunun 12'sinde normal öncesi 21 konteyner (collector yeniden başlatıldı; hangi konteynerin metriği eksik, bakılmadı).
  - Kural testi: yedekli 23 kural savunma katmanı; örneksiz 17 kuralın 12'sinin gerçek kaydı yok (DI, `lock_failed`, `url.path`/`http.route`, PC log gövdesi). Collector sürümü değişince `tools/test_collector_rules.sh` elle koşulur.
  - `gnome-session-inhibit --inhibit` listesi iki nokta üst üsteyle (`suspend:idle`); yardım metnindeki virgüllü biçim yok sayılıyor.

## 2026-10-24 · Planlama → Uygulama (C2 doğrulama ve kalibrasyon)
- Gözetimli iki koşu (planlamanın bağımsız kontrolü):
  - Yeniden yazım sayıları tuttu: adManualGc 123/0/123, product-catalog 1996/0/1996.
  - Sızıntı CLI'ı filtered'da 0, raw'da 1 döndü.
  - Beklenen yol tablosu değişmedi.
  - Planlamanın o sırada sözlü verdiği "açılış etkisi yok, ısınma gerekmez" sonucu (yalnız ad'e bakılarak çıkarılmıştı) aşağıda düzeltildi.
- Gece sonucu doğrulandı (run.json, measure.json, pencere dosyaları):
  - Geçerlilik bu dosyadaki kayıtlarla aynı.
  - journalctl'da gece tek uyku var: 04:56–07:06 UTC, yalnız productCatalogFailure_on_2'ye denk. 11:15–12:57 UTC uykusu koşuların arasında.
  - productCatalogFailure_on_2'nin run.json'u valid: true kalmıştı; bu kartta düzeltildi.
  - Belirti ve kural tablosu 17 measure.json'dan yeniden çıkarıldı; uygulamanın tablosuyla aynı.
  - Sızıntı, CLI'dan bağımsız olarak düz metinle arandı: 19 filtered pencerede 18 flag adı, yazım biçimleri (_, -, boşluk), flagd, feature_flag, openfeature ve flood ifadeleri. Sonuç 0. Tek eşleşme dotnet.monitor.lock_contentions (cart'ın .NET çalışma zamanı metriği, her koşuda var); sızıntı değil.
  - Koşu başında başka flag açık değildi (raw'daki flag değerlendirmeleri, 3 koşu).
- Uygulamanın raporuna düzeltmeler:
  - cartFailure belirtisiz değil, zincirleme:
    - EmptyCart (cart isteklerinin ~%3'ü) p99: %10'da 5 ms → 75 sn (1 hata), %50'de 4 ms → 380 sn (4 hata).
    - checkout PlaceOrder p95: 54 ms → 31 sn ve 37 ms → 450 sn; %50'de 31 siparişin 8'i hata.
    - frontend-proxy POST'ta 15 sn zaman aşımı.
    - Servis düzeyi ölçüm EmptyCart'ı GetCart ve AddItem içinde kaybediyor.
  - intlShippingSlowdown çelişkisi rastlantı: C2'de 26 ship-order'ın 8'i gecikmeli (beklenen ~3). Servis p95'i, gecikmeli istekler %5'i (~7) geçince oynuyor. Zor denemede ~3 vardı.
  - paymentFailure %10: Charge'da 26 istekte 1 hata (10 dk'da 16–43 sipariş).
  - emailMemoryLeak 100x: bellek flag açıkken ~1,8 MB/dk, normal dönemde ~0,8 MB/dk artıyor (adFailure koşusunda ~0,65); ayrılmıyor. 1000x: 2 dk'da 53 → 89 MB, sonra dalgalanıyor.
  - Collector'ın ~300 MiB belleği "yeniden başlatılmayan koşu" ile açıklanmıyor: yeniden başlatılmayan 4 gece koşusu 119–127 MiB.
    - ~300 MiB olan iki koşu (adManualGc_on_1, recommendationCacheFailure_on_2) "yavaş taban" koşuları: bütün servisler 20 dk boyunca 3–10 kat yavaş (frontend p95 85–230 ms, gece ~24 ms); product-catalog normal dönemde %26–57 CPU harcıyor (gece %9–10); istek sayısı aynı (~25 bin span).
    - Neden bulunmadı. Başka flag açık değildi. rec_2 uykudan uyandıktan 10 dk sonra başladı, ama adManualGc_on_1 son uyanmadan 5,5 saat sonra başladı. Uygulama o sırada dosya yazmıyordu. İkisi de gündüz ya da gözetimli koşu.
    - recommendation gücünün 112'den 4,18'e düşmesi bu yavaş tabandan; karar (belirtili) değişmiyor.
    - Gözetimli adManualGc_on_2'de hafif yükselme var (frontend 35–48 ms).
  - Isınma: normal dönemi açılıştan ~10–30 sn sonra başlayan koşularda ilk 3–5 dk daha yavaş (ad ilk dakikada 85–135 ms, sonra ~4 ms; frontend ve product-catalog ~%30). Collector'ın yeniden başlatıldığı 12 koşuda 6 dk bekleme yüzünden bu etki yok. C2 kararlarını değiştirmiyor: sınırdaki koşular hata oranı, bellek ve WARN ile karar veriyor.
- Kararlar (Eren, 2026-10-24): kalibrasyon ve işlem düzeyi belirti (DECISIONS'ta); productCatalogFailure_on_2 geçersiz işaretlenir; c2_runs raw kopyaları ve samples/ silinir.
- Vaka üretimi kartı için notlar (karar o kartta verilecek):
  - Koşular gece yapılır; normal dönemden önce sabit ısınma (~5 dk) olur. Taban sağlık kontrolü eklenir: normal dönemde frontend p95 referansın X katını geçerse koşu geçersiz; eşik veriyle konur.
  - Basit kural belirtili 10 koşunun 8'inde kök nedeni ilk sırada buluyor (tavan). Kolay vakalar modelleri ayırmaz; ağırlık zincirleme vakalarda olmalı (productCatalogFailure, LockContention, cartFailure).
  - ad ve astronomy-db ilgisiz senaryolarda da kuralın ilk 3'üne giriyor (gürültü).
  - Sipariş yolu senaryolarında olay az (10 dk'da 25–30 PlaceOrder). Düşük seviyeli varyantlarda pencere olaysız kalabilir; vaka başına "olay var mı" kontrolü gerekir.
  - 16 koşunun 12'sinde bir konteynerin metriği (count(container_uptime_seconds) = 21) collector yeniden başlatılana kadar gelmedi; koşu başına +6 dk. Hangi konteyner olduğuna bakılmadı.
  - Collector belleği en çok 311 MiB oldu, sınır 400 MiB; yavaş taban koşularında pay az. Kayda alınır.

## 2026-10-25 · Uygulama → Planlama (C2 doğrulama ve kalibrasyon, sonuç)
- Yapılan (dal `task/c2-dogrulama`): planlamanın kaydı (yapıştırmada iki kez giren "paymentFailure %10" satırı bir kez, Eren onayı), DECISIONS iki satır, INCIDENT_CATALOG dört satır. intlShippingSlowdown belirtisinde "Siparişlerin ~%11'inde gecikme" kaldı, parantezin içi yeni metin; yeni metindeki iç parantezler kaldırıldı (Eren onayı).
- `productCatalogFailure_on_2/run.json`: `valid` true → false, `invalid_reasons` [] → kartın metni. Önce/sonra JSON farkı yalnız bu iki alan, anahtar sırası aynı; dosya koşucunun biçimiyle (`indent=1`) yazıldı.
- Silme (Eren onayı): `c2_runs/*/window/raw/` 19 klasör 5,50 GB ve `*/samples/` 17 klasör 5,8 MB (önce ölçüldü, planlamanın ölçümüyle aynı). Sonra: ikisi de 0; 19 `window/filtered/` 4,39 GB, 57 dosyanın sha256'sı silmeden öncekiyle aynı; 17 `measure.json`, 19 `run.json`, `window_manual_copy.json` duruyor. Boş disk 287,96 → 293,47 GB (+5,51 GB, `df -B1`). `c2_runs/` toplam 4,39 GB.
- Dikkat: `measure.json`'daki `samples/` yolları artık yok (kart: düzeltme gerekmiyor). `c2_measure.py` değişmedi.

## 2026-10-25 · Planlama → Uygulama (depolama kartı)
- Önce 3-5 maddelik plan, Eren onaylar. Her bölümden (D1, D2, D3) sonra rapor ver ve dur. Yeni ad (volume adı, betik adı) koymadan önce öner. Yeni paket yok: badger Jaeger imajında var; collector-contrib alıcıları kendi imajında var. Upstream dosyalarına dokunma; değişiklik bizim katmanda (`compose.extras.yaml`, `otelcol-config-extras.yml`, `tools/`). `~/cerebrum2/c2_runs/*/window/filtered/` D3 bitene kadar silinmez.
- Kayıt (ilk commit): DECISIONS 2026-10-25 iki satır (canlı taraf yeniden oynatmayla; collector dosya döndürmesi kalıcı), GLOSSARY `yeniden oynatma`, bu kart.
- Amaç: canlı izleme sistemi kalıcı ve sınırlı olsun, OpenSearch log kaybetmesin, canlı taraf dosyayla aynı veriyi tutsun. Yeniden oynatmanın çalıştığı vaka üretiminden önce gösterilsin.
- Kapsam dışı: yeniden oynatma aracının kendisi (Proje 2), snapshot biçimi ve sınırı (vaka üretimi kartı).
- **D1 · Ölçüm (değişiklik yok).** 1 saatlik normal koşu (up, raw kapalı). Koşudan önce şarj sınırı 80 mi, kontrol et.
  - OpenSearch kaybı:
    - opensearch çıkışının sent, send_failed ve enqueue_failed sayaçları.
    - Collector logundaki opensearch hata mesajları (farklı mesajlar ve sayıları).
    - OpenSearch tarafında reddedilen bulk istekleri (thread pool ve node stats).
    - Neden yazılır; düzeltme önerisi seçeneklerle sunulur (ör. bellek/heap, kuyruk/batch, eşleme). Seçimi Eren yapar.
  - Büyüme: Prometheus ve OpenSearch veri klasörlerinin saatlik artışı (ondalık GB). Jaeger şu an bellekte; onun disk büyümesi D2'de ölçülür.
  - Jaeger, Prometheus, OpenSearch ve collector için tepe bellek, yeniden başlama ve OOM.
  - Rapor ver ve dur.
- **D2 · Kalıcı ayarlar.**
  - İsimli volume'ler: Prometheus, Jaeger (badger, diske), OpenSearch.
  - Saklama: süre 7 gün; boyut sınırı D1–D2 ölçümünden önerilir (ör. saatlik büyüme × gece başına 8 saat × 7 × 1,5). Yöntemi (Prometheus retention.size, badger TTL, OpenSearch eski indeks silme) uygulama önerir, Eren onaylar.
  - OpenSearch düzeltmesi: D1'de seçilen.
  - Koşucu koruması: izleme volume'lerinin toplamı sınırı aşarsa koşu başlamaz.
  - Ölçütler (ölçmeden önce yazılı, sonuca göre değişmez):
    - 1 saatlik koşuda opensearch send_failed ve enqueue_failed artışı 0.
    - Canlı = dosya, kapalı bir aralıkta (pencere kenarlarından 2 dk içeride, sorgudan önce 2 dk bekleme):
      - Jaeger'deki span sayısı = file/traces'teki span sayısı (servis başına; arama sınırına takılmamak için dilimlerle).
      - OpenSearch'teki log sayısı = file/logs'taki log kaydı sayısı.
      - Prometheus'ta seçili 3 metrik (gauge, sum, histogram _count) için örnek sayısı ve değerler dosyayla aynı.
    - down + up sonrası önceki aralığın sayıları üç sistemde de aynı.
    - Bellek: OOM yok, beklenmeyen yeniden başlama yok; tepe değerler kayda.
    - Volume boyutları kayda.
    - Kasıtlı kırmızı: düşük bir sahte sınırla koşucu koşuyu başlatmıyor.
    - pytest yeşil.
  - Rapor ver ve dur.
- **D3 · Yeniden oynatma denemesi.**
  - Girdi: iki C2 süzülmüş penceresi, ~8,7 saat arayla. Aralık, Prometheus'ta blok sıkıştırmasını tetiklesin diye seçildi.
    - `~/cerebrum2/c2_runs/productCatalogFailure_on_1/window/filtered/` (2026-10-23 23:31–23:51 UTC, 0,24 GB)
    - `~/cerebrum2/c2_runs/intlShippingSlowdown_10sec_1/window/filtered/` (2026-10-24 08:14–08:35 UTC, 0,23 GB)
  - Hedef: boş ve ayrı volume'lü bir Jaeger, Prometheus ve OpenSearch. Canlı demonun volume'lerine yazılmaz. Prometheus'un saklama süresi en eski verinin yaşından uzun olmalı.
  - Yöntem uygulamanın önerisi (ör. collector-contrib'in dosya okuyan OTLP alıcısı ya da standart kütüphaneyle OTLP/HTTP gönderimi).
  - Ölçütler:
    - Her pencere için Jaeger span sayısı ve OpenSearch log sayısı dosyayla aynı.
    - Prometheus'ta seçili 3 metrikte örnek sayısı ve değerler dosyayla aynı.
    - Prometheus'ta blok oluştuktan (sıkıştırma) sonra iki pencerenin verisi de sorgulanabilir.
    - Canlı demonun volume boyutları değişmedi.
  - Güç kontrolü:
    - Hepsi tutarsa B kesinleşir.
    - Prometheus eski örnekleri reddederse önce sıra dışı yazma ayarı (out_of_order_time_window) denenir; yine reddederse dur, planlamaya dön (karar değişebilir).
    - Jaeger ya da OpenSearch sayısı tutmazsa fark ve nedeni yazılır.
  - Rapor ver ve dur.
- **Bitince:**
  - ARCHITECTURE: mon artık kalıcı (kesik çizgi kalkar); Proje 2 notu: mon snapshot'lardan yeniden oynatmayla dolar.
  - OTEL_DEMO: kalıcılık bölümü güncellenir.
  - Disk bütçesi tablosu HANDOFF'a: döndürme 5,4 / 2,7 GB; izleme sınırı; snapshot tahmini ~0,23 GB/vaka (sıkıştırmasız; sınırı vaka üretimi kartında).
  - PROJECT "Şu an"; DevOps listesindeki "Kalıcı depolama, saklama süresi" satırının işaretlenmesini öner.
  - PR açıklaması sade; push'tan önce PR durumuna bak.

## 2026-10-25 · Uygulama → Planlama (depolama D1, ölçüm)
- Betik: `tools/storage_check.py watch` (adlar Eren onaylı). Korumalar (koşucunun `guards`, GNOME + systemd engeli) → `otel_demo.sh up` (raw kapalı) → 22 konteyner → 5 dk ısınma → pencere → 90 sn bekleme → sayaçlar → `down`. Çıktı `~/cerebrum2/storage_runs/<UTC>-watch/`.
- Ölçmeden önce tanımlar: dakikada bir bellek (`docker stats`, dört servis); 5 dk'da bir veri klasörü (`du -sk` konteyner içinde), OpenSearch heap, collector logunun son 5 dk'sı (Docker logu 5 MB × 2 döndüğü için parça parça); başta ve sonda OpenSearch node stats ve indeksler, konteyner yeniden başlama/OOM; exporter sayaçları süzülmüş metrik dosyalarından, C2'nin artış tanımıyla. Saatlik büyüme = (son − ilk) / pencere saati, ondalık GB. Sınırlama: Prometheus ilk 2 saatte WAL'a yazar, 1 saatlik büyüme kalıcı büyümeyi göstermez.
- Kontrol (demo açmadan): sayaçlar eski verinin son 20 dk'sında `recommendationCacheFailure_on_2` kaydıyla aynı (opensearch sent 23.936 / failed 9.913).
- Koşu 1 (`20261024T2343Z-watch`, 23:49–00:49 UTC, 60 dk): geçerli; 22 konteyner, collector yeniden başlatılmadı, uyku 0, en yüksek 60 °C, yeniden başlama/OOM yok.
  - opensearch: sent 100.920, send_failed 5.623 (%5,3), enqueue_failed 0 (seri yok). `file/logs` sent 106.541 (≈ sent + failed).
  - OpenSearch tarafı: write pool rejected 0, indexing pressure rejections 0, breaker 0, index_failed 0; heap (400 MiB) en çok %77, old GC 0. Kapasite sorunu yok.
  - Collector logu: tek tür, 314 satır: `Permanent error … mapper_parsing_exception` (yeniden denenmez, satır başına ~18 kayıt düşer). Betik mesajı 400 karakterde kesti, `down` logu sildi; alan adı görülemedi.
  - Büyüme: Prometheus 0,48 → 4,26 MB (0,004 GB/saat), OpenSearch 16 → 192 MB (0,176 GB/saat; `du`, translog dahil).
  - Tepe bellek / sınır: Jaeger 394 / 1200 MiB, Prometheus 94 / 200 MiB, OpenSearch 1022 / 1024 MiB (bütün koşu 1018–1022; dosya önbelleği dahil, OOM yok), collector 137 / 400 MiB.
  - `_cat/indices` bugünkü indekste 1.038 kayıt gösterdi (indekslenen 104 bin): sorgulanmayan indeks yenilenmiyor (search idle). Betik düzeltildi: sonda `_refresh`.
- Betik düzeltmesi (Eren onayı): `reason` metinleri olduğu gibi ve mesaj grubunun ilk tam satırı `collector_errors.json`'a; sonda `_refresh` ve `otel-logs-*` eşlemesi `opensearch_mapping.json`'a.
- Koşu 2 (`20261025T0053Z-watch`, 00:59–01:14 UTC, 15 dk): geçerli. opensearch sent 20.060, send_failed 7.256 (**%26,6**). Kapasite yine sorunsuz (rejected 0, heap en çok %57, bellek 894 MiB).
  - Neden: `Could not dynamically add mapping for field [http.request.method]. Existing mapping for [attributes.http] must be of type object but found [text].` (3.265 kez). İndekste `attributes.http` = `text`.
  - Dosyada: düz `http` özniteliği yalnız cart'ta (3 kayıt, açılışta, değer `"8080"`); `http.*` frontend'de (51.498 kayıt). OpenSearch boş günlük indekste türü ilk kayda göre sabitliyor; cart'ın açılış logu önce gelirse frontend'in HTTP loglarının hepsi reddediliyor.
  - Koşudan koşuya fark: her `up` OpenSearch'ü boş açıyor (C2 ~%30). Koşu 1'de çakışma yalnız 2026-10-24 indeksinde (23:49–00:00); gece yarısı açılan indekse frontend önce yazdı: %26,6 × 11/60 ≈ %4,9 (ölçülen %5,3). Kalıcı volume'le de her yeni gün şansa kalır.
- Karar (Eren, 2026-10-25; DECISIONS): seçenek E, collector'da iki çıkıştan önce cart'ın `http` özniteliğini çakışmayan ada çevirmek. Elenenler: indeks şablonu (cart kayıtları düşer, canlı ≠ dosya), `flat_object` (öznitelik sorguları değişir), exporter eşleme kipleri (noktalı alan açılımını OpenSearch yapıyor; çözmüyor), heap artırma (kapasite sorunu yok).

## 2026-10-25 · Uygulama → Planlama (depolama D2, kalıcı ayarlar)
- Değişiklikler (upstream dosyalarına dokunulmadı; adlar Eren onaylı, GLOSSARY'de):
  - `compose.extras.yaml`: isimli volume'ler (`prometheus-data`, `jaeger-data`, `opensearch-data`); Jaeger ikinci ayar dosyasıyla diske (`jaeger-config-extras.yml`, badger, TTL 168 saat; volume `/tmp`'de, imajda 10001'in yazabildiği tek klasör); Prometheus komutu upstream listesi + `--storage.tsdb.retention.size=2GB`; Jaeger bellek sınırı 2000M.
  - `otelcol-config-extras.yml`: `transform/backend_compat` (logs, iki çıkıştan önce): `http` → `http_ports` (seçenek E), kayıt zamanı 0 ise alınma zamanı (seçenek A; currency ve shipping logları OpenSearch'te 1970'e yazılıyordu).
  - `otel_demo.sh up`: OpenSearch ISM kuralı `otel-logs-retention` (7 gün → sil), yoksa yüklenir ve mevcut indekslere bağlanır.
  - `scenario_runner.py guards()`: `monitoring_gb` (`docker system df -v`; geçici konteynerde `du` ile aynı) ≤ `MAX_MONITORING_GB` (40). `storage_check.py watch` aynı korumayı kullanır.
  - `storage_check.py compare`: canlı = dosya (Jaeger v3 API 1 dk dilimlerle, OpenSearch `_refresh` + sayım, Prometheus 3 metrik örnek sayısı ve değerleri).
  - Kural testi: `NOT_LEAK` (backend_compat testin hatlarına girmez), 3 `none` satırı; PASS 56 kural. Plandan sapma: cart logu kural testine örnek olarak eklenemedi, doğrulama `compare` ile.
- 1 saatlik koşu (`~/cerebrum2/storage_runs/20261025T0154Z-watch`, 02:00–03:00 UTC): geçerli; 22 konteyner, uyku 0, en yüksek 60 °C.
  - opensearch: sent 109.453, send_failed 0, enqueue_failed 0; diğer exporter'larda da 0. `collector_errors.json` boş.
  - Canlı = dosya (02:02–02:58 UTC): span 338.578 = 338.578 (servis başına fark yok, 855 Jaeger sorgusu), log 102.114 = 102.114, `container.memory.percent` 7.392, `container.network.io.usage.rx_bytes` 7.392, `traces.span.metrics.duration` count 4.704; değerler aynı. EŞİT.
  - `down` + `up` + 2 dk sonra aynı aralık: aynı sayılar, EŞİT (`compare_after_restart.json`).
  - Büyüme: Jaeger 0,587, OpenSearch 0,255 (D1'de 0,176; artık reddedilen log yok), Prometheus 0,004 GB/saat. Pencere sonu boyutlar: Jaeger 0,91, OpenSearch 0,30, Prometheus 0,006 GB.
  - Tepe bellek / sınır: Jaeger 1200,1 / 1200 MiB, OpenSearch 915 / 1024, collector 127 / 400, Prometheus 79 / 200. OOM ve yeniden başlama yok.
- Jaeger belleği (ek ölçüm, 10 dk, 5 sn'de bir `memory.stat`; ölçüt önceden: anon tepe < sınırın %80'i, oom_kill 0):
  - 1200M (03:10–03:20 UTC): anon çoğunlukla 120–470 MiB; açılıştan ~4,5 dk sonra 15 sn'de 316 → 967 MiB, ~2 dk 960–1064 MiB. Toplam 1200 MiB (anon 1064 + dosya 108); `memory.events max` 5.076, oom 0. KALDI (< 960 değil).
  - 2000M (03:26–03:36 UTC): aynı sıçrama, anon tepe 1248 MiB (< 1600), `memory.events max` 0, oom 0. GEÇTİ.
  - Neden doğrulanmadı (tahmin: badger'ın 5 dk'lık bakımı/sıkıştırması). Yer açılınca sıçrama büyüdü; veri arttıkça büyüyebilir, D3'te Jaeger belleği yine kayda.
- Prometheus canlıda: `retention.size` 2GiB, `retention.time` 1w ("1w or 2GiB"). Jaeger `HostConfig.Memory` 2.097.152.000.
- Koruma: `monitoring_gb` 1,3. Kasıtlı kırmızı: `AIOPS_MAX_MONITORING_GB=0.5 scenario_runner.py run adFailure_on` → "STOP before adFailure_on: guards: monitoring volumes 1.3 GB > 0.5", çıkış 1, demo açılmadı; diğer korumalar geçti. Docker okunamazsa da kırmızı.
- pytest 190/190.
- Eski anonim volume'ler silindi (Eren onayı; `docker volume prune`, yalnız anonim ve bağlı olmayanlar): 117 adet, 2,85 GB; boş disk 292,24 → 295,09 GB. İsimli üç volume yerinde.
- Dikkat:
  - Kart örneğindeki formül (saatlik büyüme × 8 saat × 7 × 1,5) ~71 GB verir; onaylanan 40 GB her gece 8 saat koşuda (~48 GB/hafta) 6. günde koşucuyu durdurur. Gece koşu planı netleşince sınır yeniden bakılmalı.
  - `astronomy-db` imajı `/var/lib/postgresql`'i anonim volume olarak tanımlıyor; her `down` + `up` bir anonim volume bırakır (kapsam dışı, not). `down -v` isimli volume'leri de siler, kullanılmamalı.
  - OpenSearch belleği 915 / 1024 MiB (dosya önbelleği dahil), heap en çok %70.

## 2026-10-25 · Uygulama → Planlama (depolama D3, yeniden oynatma)
- Yapılan (adlar planlama ve Eren onaylı, GLOSSARY'de; planlamanın dört eki uygulandı):
  - `deploy/replay/compose.yaml` (`otel-replay`): Jaeger, Prometheus, OpenSearch upstream tanımından `extends` (imaj upstream .env'den, ayar dosyaları aynı; Jaeger bizim katmanla, 2000M); portlar 127.0.0.1 (16686, 19090, 19200), ayrı volume'ler. Collector: tek alıcı `otlpjsonfile` (`REPLAY_WINDOW` → `/replay`), sayaçlar yalnız çekme ucunda (127.0.0.1:18888), yeniden başlamaz. Prometheus komutu upstream'inki (7 gün, boyut sınırı yok).
  - `deploy/replay/otelcol-replay.yml`: `transform/backend_compat` kopyası, upstream'in üç exporter kopyası; `span_metrics` yok (metrik dosyasında zaten var).
  - `tests/test_replay_config.py`: kopyalar kaynaklarıyla aynı (`REPLAY_ONLY` dışında), alıcılar yalnız dosya. Upstream klonu yoksa (CI) exporter testi atlanır. Kasıtlı kırmızılar: liste dışı fark, eksik izinli satır.
  - `storage_check.py replay`: korumalar, canlı demo kapalı ve `otel-replay_*` yoksa başlar; Prometheus boş mu (numSeries 0, Jaeger'in ittiği metrik ulaşmıyor); pencereler zaman sırasıyla; bitiş sent = dosya, send_failed = 0 (zaman aşımı 20 dk, dolarsa rapor); her pencereden sonra head maxTime ≤ pencere sonu + 1 dk, reddetme sayaçları; `compare` sayımı (2. pencereden önce kasıtlı kırmızı); ilk pencere diskteki bloğa girince yeniden sayım; collector logu durdurulmadan önce `collector_<koşu>.log`.
- Pencereler: `productCatalogFailure_on_1` (2026-10-23 23:29–23:52 UTC; span 133.793, metrik noktası 106.869, log 40.326), `intlShippingSlowdown_10sec_1` (2026-10-24 08:12–08:36 UTC; 126.418 / 104.748 / 38.014).
- Koşu 1 (`20261025T0402Z-replay`): FAIL. Metrikler tam ve eşit; izler ve loglar çoğu kayıp (pencere 1: span sent 4.811, send_failed 57.449, enqueue_failed 71.533; log sent 5.461, enqueue_failed 34.865).
- Teşhis (18:36 yerel, elle, pencere 1): collector logunda "sending queue is full" (141) ve Jaeger'den "received message after decompression larger than max 4194304" (~8.200 span'lık paketler). Alınan 68.195 span'ın 65.870'i boyuttan, 65.598'i kuyruk dolu diye düştü.
- Düzeltme (Eren, seçenek 1; DECISIONS): `block_on_overflow: true` (üç exporter), Jaeger paketi `min_size`/`max_size` 2048. Canlı collector değişmedi.
- Koşu 2 (`20261025T1540Z-replay`): veri tam ve eşit, ama `block_covers_first` False. Betik hatası: kontrol bloğun başını pencere başıyla (kenar paylı, 23:29:06) karşılaştırıyordu; promtool blok başı olarak ilk örneğin zamanını (23:29:07,989) gösteriyor. Koşu 1'de tesadüfen geçmişti: sıra dışı örneklerle oluşan blok 2 saatlik sınıra hizalı (22:00). Ölçüt sonuca bakılarak geçti sayılmadı; kontrol düzeltildi (blok dosyadaki en eski ve en yeni metrik zamanını kapsamalı; kayıtlı iki blokta doğru, 1 ms kaydırılmış iki kasıtlı kırmızıda False), koşu tekrarlandı (Eren).
- Koşu 3 (`~/cerebrum2/storage_runs/20261025T1601Z-replay`, 16:01–16:05 UTC): **PASS**, 11 ölçütün hepsi.
  - Gönderilen = dosya, send_failed 0, enqueue_failed 0, collector hata satırı 0, zaman aşımı yok (pencere başına < 1 dk).
  - Karşılaştırma eşit: pencere 1 span 133.652, log 40.326, metrikler 2.944 / 2.944 / 1.958; pencere 2 span 126.392, log 38.009, metrikler 2.910 / 2.910 / 1.758. Bloktan sonra da eşit (head 07:35'ten başlıyor, pencere 1 yalnız blokta).
  - Prometheus: önce boş; reddedilen örnek 0 (out_of_order, out_of_bound); sıra dışı kabul 654 (koşu 2'de 0, koşu 1'de 13.290: paket sırası koşudan koşuya değişiyor); exemplar sıra dışı 21 (yalnız exemplar). Blok 2026-10-23 22:00–00:00, 179.043 örnek.
  - Canlı volume'ler değişmedi. OOM ve yeniden başlama yok.
  - Tepe bellek: Jaeger 1972,2 / 2000 MiB, OpenSearch 865, Prometheus 122, collector 186 MiB.
  - Hedef volume'ler: Jaeger 439,3 MB, OpenSearch 42,6 MB, Prometheus 5,3 MB; Eren onayıyla silindi (üç koşunun ve teşhisin hepsi).
- Sonuç: Prometheus eski zaman damgasını kabul ediyor, diske yazdıktan sonra da sorgulanabiliyor; DECISIONS 2026-10-25 "yeniden oynatma" kararının D3 riski çıkmadı.
- Proje 2 notları (karar değil):
  - Yeniden oynatma zaman sırasıyla ve boş hedefe: Prometheus'un sıra dışı penceresi 30 dk (upstream `out_of_order_time_window`); daha eski bir pencere sonradan gelirse reddedilir (denenmedi).
  - Prometheus süre saklaması en yeni bloğun zamanından sayılıyor, duvar saatinden değil (v3.13.1 kaynağında doğrulandı); en yeni blok süre yüzünden silinmez.
  - OpenSearch exporter indeks adını oynatma tarihinden alıyor (`otel-logs-2026-10-25`), logun zamanından değil; ISM 7 günü oynatma gününden sayar. Sayım `@timestamp` ile, sonucu etkilemedi.
  - Jaeger belleği yeniden oynatmada sınırın %99'u (260 bin span ~2 dk'da); toplam bellek, dosya önbelleği dahil olabilir, `memory.stat` ile ayrıştırılmadı. Daha uzun ya da çok pencereli oynatmada sınır aşılabilir.
  - Hedef volume'ler kalıcı olursa onlara da boyut sınırı gerekir (iki pencere ~0,49 GB).
- Dikkat:
  - Collector `otlpjsonfile` adının eskidiğini yazıyor (yeni ad `otlp_json_file`); hâlâ çalışıyor. Ad değişikliği onay ister.
  - `replay.log` (koşu günlüğü) GLOSSARY'de yok; `watch.log`'un karşılığı, onay bekliyor.
  - `storage_check.py`'deki replay sabitleri ve fonksiyonları (`REPLAY_COMPOSE`, `wait_replayed` vb.) iç adlar, GLOSSARY'de değil.
  - pytest 195/195.

## 2026-10-25 · Uygulama → Planlama (depolama kartı bitti, disk bütçesi)
- Yapılan ("Bitince" işleri): ARCHITECTURE (`mon` kalıcı, kesik çizgi kalktı; Proje 2'de ajanın canlı araçları yeniden oynatma hedefine bakar, `snap` → `replay`), OTEL_DEMO kalıcılık bölümü, PROJECT "Şu an", bu tablo. `replay.log` GLOSSARY'ye eklendi (Eren onayı).
- Disk bütçesi (ondalık GB; 2026-10-25 ölçümü, boş disk 292,20 GB):

| Kalem | Boyut | Not |
|---|---|---|
| Collector dosya döndürmesi, süzülmüş | en çok 2,83 GB | 3 sinyal × 3 dosya × 300 MiB (`max_megabytes` MiB; kartta 2,7) |
| Collector dosya döndürmesi, süzülmüş + süzülmemiş (`--raw`) | en çok 5,66 GB | kartta 5,4 |
| İzleme sistemi volume'leri (canlı) | ≤ 40 GB | koruma (`MAX_MONITORING_GB`); büyüme ~0,85 GB/saat demo (D2); Prometheus ayrıca ≤ 2GiB |
| Snapshot (vaka penceresi, süzülmüş, sıkıştırmasız) | ~0,23 GB/vaka | 19 C2 penceresi: ortalama 0,231, en çok 0,278 GB (~25 dk); 30 vaka ≈ 6,9 GB. Sınır vaka üretimi kartında |
| Yeniden oynatma hedefi (Proje 2) | ~0,25 GB/vaka | D3: 2 pencere 0,49 GB (Jaeger 0,44); hedef kalıcı olursa sınır gerekir |
| Docker imajları | 19,29 GB | şu an |
| `~/cerebrum2/c2_runs/` | 4,39 GB | süzülmemiş kopyalar silinmiş; `window/filtered/` duruyor |
| `~/cerebrum2/telemetry/` | 2,28 GB | döndürmenin şu anki doluluğu |

- Öneri: PROJECT DevOps listesinde "Kalıcı depolama, saklama süresi" satırı işaretlenebilir (Jaeger diske, Prometheus/OpenSearch saklama, boyut koruması, yeniden başlatma sonrası doğrulama). Karar planlamanın / Eren'in; işaretlemedim.
- Dikkat: 40 GB her gece 8 saat koşuda 6. günde dolar (D2 notu); gece planı netleşince yeniden bakılmalı.

## 2026-10-25 · Planlama → Uygulama (vaka üretimi V1)
- Yeni usul (DECISIONS 2026-10-25): planlama kartları ve kararları docs'a kendi dalında yazar; uygulama kartı buradan okur. Bu kartın kayıtları (DECISIONS dört satır, PROJECT DevOps satırı) planlamanın commit'inde. İşe `task/vaka-hatti` dalında devam et.
- Vaka üretimi planı: V1 vaka hattı ve pilot gece (bu kart) → V2 altyapı hataları (kill, CPU, bellek, ağ; enjeksiyon yönteminin izi sızıntı mı, ağ aracı kararı) → kendi Python servisi kartı (DECISIONS 2026-10-25, seçenek A) → V3 resmî set (~40 vaka; bileşim ve dev/test bölümü kayıttan önce yazılır, test vakalarına yalnız otomatik kontroller bakar).
- Not: bu sırayla tablo ~4 Kasım'a dolmaz; PROJECT'teki kurala göre Kubernetes yapılmaz.
- Önce 3-5 maddelik planını yaz, Eren onaylasın. Yeni ad (klasör, dosya, alan, komut) koymadan önce öner. Yeni paket yok. Upstream'e dokunma. V1a ve V1b sonunda rapor ver ve dur.

### Amaç
Koşucu bir vakayı gözetimsiz, uçtan uca üretsin: enjekte et → kaydet → temizle → snapshot + etiket → otomatik geçerlilik kontrolleri. Pilot gece hattı sınar. Pilot vakalar resmî sete girmez (geliştirmede bakılacaklar; resmî set V3'te, kendi servisle).
Kapsam dışı: altyapı hataları (V2), kendi servis, resmî set bileşimi ve dev/test bölümü (V3), değerlendirme (modele ne verileceği, alarm zamanı dahil).

### V1a · Biçim ve kontroller (gece koşusu yok; mevcut C2 verisiyle)
1. Snapshot biçimi (öner, Eren onaylar):
   - Vaka kimliği opak: senaryo, servis, varyant, tarih geçmez (sızıntı testi klasör ve dosya adlarını da tarar).
   - `model_view`: pencerenin süzülmüş izleri, metrikleri, logları; meta olarak yalnız pencere sınırları.
   - Etiket: INCIDENT_CATALOG "Doğru cevap kaydı" alanları + koşu kaydı (korumalar, sürümler, kontrol sonuçları). Snapshot klasörünün dışında, ayrı kökte. Pilot vakaların set alanı ayrı bir değer (ad öner).
   - Konum repo dışı; sıkıştırma yok (Releases'te proje sonunda).
   - Sınır (DECISIONS 2026-10-18): snapshot toplamı ≤ 20 GB (~85 vaka); aşılırsa koşucu başlamaz.
2. Koşu akışı: korumalar → up → 5 dk ısınma → taban sağlık kontrolü → 10 dk normal → 10 dk enjeksiyon → temizleme (flag API'den geri okunur) → kesim → kontroller → down.
   - Senaryo listesi dosyadan okunur (komut satırında senaryo adı yok).
   - `down` sonrası bu koşunun anonim volume'leri silinir (astronomy-db her `up`'ta ~24 MB bırakıyor); yöntemi öner.
   - C2'de 16 koşunun 12'sinde bir konteynerin metriği gelmedi, collector yeniden başlatıldı (+6 dk). Hangi konteyner ve neden: bak, ucuz düzeltme varsa öner.
3. Kontroller (ölçütler ölçmeden önce yazılı; sonuca göre değişmez):
   - Kapsama: C2'deki gibi; eksikse vaka geçersiz.
   - Sızıntı: `model_view` üzerinde `leakage.py` 0 bulgu. Bulgu çıkarsa vaka geçersiz ve gece durur (sistematik olabilir).
   - Taban sağlık: normal dönemde frontend p95 ≤ 2 × referans. Referans: C2'nin geçerli koşularının normal dönemlerinde frontend p95 medyanı, iki yavaş taban koşusu (`adManualGc_on_1`, `recommendationCacheFailure_on_2`) hariç. Geçme şartı: bu kural iki yavaş koşuyu geçersiz sayar, diğer C2 koşularından en fazla birini geçersiz sayar. Tutmazsa dur, planlamaya dön. Koşuda geçmezse vaka geçersiz, bir kez tekrar.
   - Belirti (DECISIONS 2026-10-24): C2'nin servis düzeyi kuralı (`c2_measure.py` eşikleri) + işlem düzeyi: kök neden servisinin her span adı için aynı eşikler (hata oranı +0,05; p95 ve p99 ×1,5 ve +20 ms), iki dönemde de en az M istek. Karar en güçlü sinyalle.
     - M seçimi (yöntem veriye bakmadan önce): adaylar 10, 20, 30. C2'nin geçerli koşularında (flood hariç), kök neden ve katalogdaki yayılım yolu dışındaki her servis için normal ↔ enjeksiyon dönemi işlem düzeyi kuralla karşılaştırılır; "belirtili" çıkan servis-koşu çifti yanlış alarmdır. Yanlış alarm oranı ≤ %5 olan en küçük M seçilir. Hiçbiri tutmazsa dur, planlamaya dön. Aynı çiftlerde servis düzeyi kuralın yanlış alarm oranı da rapora.
     - Seçilen M ile C2'nin belirtili koşuları yeniden değerlendirilir; cartFailure %50 belirtili çıkmalı. Çıkmazsa rapora, kural değişmez.
   - Olay var mı: enjeksiyon döneminde, belirti kararını veren işlemde en az M istek; yoksa "olaysız", vaka geçersiz.
   - Belirtisiz ya da sınırda vaka geçersiz sayılmaz, işaretlenir; set kararı V3'te.
   - İzleme sağlığı (kayda; dosya asıl kaynak olduğu için vakayı geçersiz kılmaz): opensearch send_failed ve enqueue_failed artışı, Jaeger bellek tepesi ve `memory.events` max, collector bellek tepesi, OOM ve yeniden başlamalar. Collector'ın OOM'u ya da yeniden başlaması vakayı geçersiz kılar.
   - ISM (bir kez): `up` sonrası `GET _plugins/_ism/explain/otel-logs-*` her otel-logs indeksinde policy_id = `otel-logs-retention`; çıktı rapora.
- Rapor ver ve dur (biçim önerisi, referans, M ve yanlış alarm oranları).

### V1b · Pilot gece
- Şarj sınırı 80 mi, kontrol et. Gece, gözetimsiz.
- Liste: 11 katalog senaryosu, kalibre varyantlarla + `noise_layer`'lı 2 vaka (`loadGeneratorFloodHomepage` + paymentFailure %50; `loadGeneratorFloodHomepage` + productCatalogLockContention). ~13 vaka.
- Ölçütler:
  - Gece yarıda kalmadı; her vaka geçerli/geçersiz ve nedeniyle kayıtlı.
  - Geçerli vaka oranı ≥ %80.
  - Sızıntı 0.
  - C2'de belirtili çıkan senaryoların hepsi (kalibre varyantla; liste C2 kaydından, rapora) belirtili ya da sınırda.
  - Vaka başına süre ve snapshot boyutu kayda.
  - Kasıtlı kırmızı: düşük sahte snapshot sınırıyla koşucu başlamıyor.
  - pytest yeşil.
- Güç kontrolü:
  - Geçerli oran < %80 → V3'ten önce düzeltilir.
  - C2'de belirtili bir senaryo burada belirtisiz → rapora; kural değişmez, planlama karar verir.
  - Sızıntı > 0 → dur.
  - Vaka başına süre → V3'ün kaç gece süreceği bundan hesaplanır.
- Rapor ver ve dur.

### Bitince
- ARCHITECTURE: snapshot kesici, snapshot'lar ve `model_view` kesik çizgiden çıkar; etiket kökü eklenir.
- GLOSSARY, DECISIONS (snapshot biçimi, sınır, M, taban eşiği).
- PR açıklaması sade; push'tan önce PR durumuna bak.

## 2026-10-25 · Planlama → Uygulama (V1 netleştirmeler)
Uygulamanın V1 kartına dört sorusunun cevabı (Eren onayı). Kartın ölçütlerine eklenir; ölçmeden önce yazıldı.
1. Taban sağlık kontrolü normal dönemin verisiyle, normal dönem bitince ve enjeksiyondan hemen önce yapılır. Geçmezse enjeksiyon yapılmaz, vaka geçersiz, bir kez tekrarlanır. Koşudaki kontrol C2 analiziyle aynı veri kaynağını ve aynı p95 hesabını kullanır. (Kart akışındaki "ısınma → taban sağlık kontrolü → 10 dk normal" sırası bununla düzelir.)
2. "Olay var mı": belirti kararı kaynak sinyalinden (CPU, bellek) geldiyse, enjeksiyon döneminde kök neden servisinin toplam isteği en az M olmalı (emailMemoryLeak gibi kaynak hataları da istekle tetikleniyor). Hiç izi olmayan servislerde (ör. astronomy-db) olay kontrolü uygulanmaz; kayda "uygulanmadı" yazılır.
3. M seçiminde yalnız "belirtili" çıkan servis-koşu çifti yanlış alarm sayılır; "sınırda" sayılmaz (vaka kontrolünde de sınırda vaka belirtili sayılmıyor, yalnız işaretleniyor). Her M için sınırda oranı da rapora.
4. Taban kuralının sınanması: referans, geçerli 16 koşudan `recommendationCacheFailure_on_2` çıkarılarak 15 koşunun normal dönemlerinden (frontend p95 medyanı). Kural bu 16 koşuya ve `adManualGc_on_1`'e (geçersiz ama süzülmüş verisi sağlam) uygulanır. Geçme şartı: iki yavaş koşu geçersiz çıkar, diğer 15'ten en fazla biri geçersiz çıkar. `productCatalogFailure_on_2` (uyku) ve `recommendationCacheFailure_on_1` (yeniden başlama) hesaba girmez.
- Küçük düzeltmeler: kartta "Snapshot toplamı ≤ 20 GB (DECISIONS 2026-10-18)" — 2026-10-18 satırı yalnız "her bileşene sınır" kuralını koyuyor, 20 GB bu kartın kararı ("Bitince"de DECISIONS'a). Collector yeniden başlatma sayısı kayıtta geçerli 16 koşunun 11'i, 19 koşunun 13'ü (kartta "16'nın 12'si" yanlış); V1a'da incelenir.
- Uygulamanın V1a planı (5 adım, her adım sonunda rapor) uygun; 1. adımla (biçim önerisi) başlanabilir.

## 2026-10-25 · Uygulama → Planlama (vaka üretimi V1a)
- Yapılan (adlar Eren onaylı, GLOSSARY'de; DECISIONS üç satır):
  - Snapshot biçimi: `~/cerebrum2/snapshots/inc-<8 hex>/` = `model_view` (süzülmüş `traces/metrics/logs.jsonl` + `window.json`); etiket repoda `incidents/<incident_id>.json` (`answer`, `window`, `checks`, `valid`, `invalid_reasons`, `marks`, `run`); pilot etiketleri commit edilir (`set: pilot`).
  - `SCENARIOS`'a doğru cevap alanları (`fault_type`, `propagation_path` kenar listesi, `categories`); `tests/test_catalog.py` INCIDENT_CATALOG tablosuyla aynı olduğunu kontrol eder (kasıtlı kırmızı: hata tipi ve yol değişince).
  - `tools/incident_checks.py`: işlem düzeyi belirti, olay, taban sağlık, izleme sağlığı; ölçü C2'ninki. Kabul: C2 verisinde 2. adımın sayılarını aynen üretti (taban geçersizleri, M = 10'da 7 yanlış alarm / 5 sınırda, 15 kök neden kararının 15'i). `tests/test_incident_checks.py` 13 test; üç kasıtlı bozmanın üçünü yakaladı.
  - `scenario_runner.py incidents <liste>` (C2'nin `run`'ı değişmedi): korumalar (+ snapshot ≤ 20 GB) → `up` (raw kapalı) → ISM (gecede bir) → collector yeniden başlatma → 22 konteyner → ısınma (up'tan 5 dk) → flag'ler kapalı, zamanlayıcı durmuş → 10 dk normal → taban sağlık (geçmezse enjeksiyon yok, bir kez tekrar) → flag (+ noise_layer) 10 dk → kapat, doğrula → anonim volume'ler kaydedilir → `down` → silinir → kesim → kontroller → etiket. Sızıntıda gece durur; geçersiz vakanın snapshot'ı gece klasörüne taşınır.
  - `incident_lists/pilot.json`: 13 vaka.
- C2 analizi (netleştirmelerle; betik ve sonuç repo dışında, sonuç DECISIONS'ta):
  - Taban: referans 25,3 ms, eşik 50,6 ms; geçersiz `adManualGc_on_1` (223,5) ve `recommendationCacheFailure_on_2` (82,7), diğer 15'ten hiçbiri. GEÇTİ.
  - M: 201 servis-koşu çifti; işlem düzeyi yanlış alarm M = 10/20/30'da aynı: 7 (%3,48), sınırda 5 (%2,49); payda ölçülebilir çiftler olursa %4,19 / %4,29 / %4,96. Servis düzeyi kural: 8 (%3,98), sınırda 12. M = 10.
  - Seçilen M ile 15 koşu: cartFailure %50 belirtili (EmptyCart p99, istek 30 / 23); kalibre varyantların hepsi belirtili; paymentFailure %10 ve emailMemoryLeak 100x belirtisiz; cartFailure %10 belirtili (C2'de belirtisizdi); olay 15/15.
- İncelemeler:
  - Collector açılış yarışı: 4 açılışın 1'inde (`currency`, collector'dan 0,49 sn sonra başlamış) konteyner metriği 6 dk boyunca gelmedi; diğer 3'ünde 60. sn'de 22. Süzülmemiş kopyaya bağlı değil. Neden tahmini: alıcı açılışta listeyi alıp sonra olayları dinliyor (kaynakta doğrulanmadı). Düzeltme: her vakada yeniden başlatma (Eren).
  - Anonim volume: yalnız `postgres:18.4` (astronomy-db), açılış başına 66,08 MB (kartta 24 MB).
- Uçtan uca tek vaka (`inc-8ceb7ae5`, paymentFailure %50, 18:28–18:56 UTC, gece klasörü `~/cerebrum2/incident_runs/20261025T1828Z-one/`): GEÇERLİ.
  - ISM: `otel-logs-2026-10-25` → `otel-logs-retention`, geçti. Collector yeniden başlatıldıktan sonra 22.
  - Taban: frontend p95 24,7 ms. Kapsama tam, sızıntı 0 (CLI da "clean"), belirti belirtili (payment hata oranı, güç 9,6), olay 25 istek ≥ 10, opensearch send_failed 0, beklenmeyen yeniden başlama 0, uyku 0, en çok 71 °C.
  - Süre 1.640 sn (~27,5 dk; 13 vaka ~6 saat), snapshot 0,239 GB (13 vaka ~3,1 GB). Anonim volume silindi.
  - Kasıtlı kırmızı: `AIOPS_MAX_SNAPSHOT_GB=0.1` → "STOP … guards: snapshots 0.24 GB > 0.1", demo açılmadı.
- pytest 226/226.
- Dikkat:
  - Jaeger: bellek tepesi 2000 / 2000 MiB (dosya önbelleği dahil), `memory.events max` 10.695, OOM 0 (D2'de 10 dk'da max 0). Kayıt, vakayı geçersiz kılmaz. Koşucu artık dakikada bir Jaeger'in anon belleğini de ölçüyor (`run.memory.jaeger_anon_peak_mib`; tek vakada henüz ölçülmedi). Pilot gecede ilk izlenecek risk.
  - `window.json` + sabit normal dönem enjeksiyon anını verir (DECISIONS satırında not).
  - Katalog yollarında frontend-proxy yok; yanlış alarmların hepsi orada.
  - Pilot gece (V1b) Eren'in başlatmasıyla; liste `incident_lists/pilot.json`.

## 2026-10-26 · Uygulama → Planlama (vaka üretimi V1b, pilot gece; V1 bitti)
- Koşu: `scenario_runner.py incidents incident_lists/pilot.json`, 2026-10-25 19:07 – 2026-10-26 01:09 UTC (6 sa 2 dk), gece klasörü `~/cerebrum2/incident_runs/20261025T1913Z-pilot/`. Önce: şarj sınırı 80, priz, 48 °C, boş disk 291 GB, izleme 1,81 GB, snapshot 0,24 GB.
- Ölçütler (kart V1b):
  - Gece yarıda kalmadı: 13 deneme, 13 kayıt, tekrar yok. ✓
  - Geçerli oran: 13/13 (%100). ✓
  - Sızıntı: 13 vakada 0. ✓
  - C2'de belirtili çıkan senaryolar (kalibre varyant; C2 `measure.json` servis düzeyi kararı: adFailure, adHighCpu, adManualGc, emailMemoryLeak 1000x, paymentFailure %50, paymentUnreachable, productCatalogFailure, productCatalogLockContention, recommendationCacheFailure, intlShippingSlowdown 10sec): 10/10 belirtili. cartFailure %50 (C2'de sınırda) de belirtili (EmptyCart p95). ✓
  - Süre 1.632–1.658 sn (~27,4 dk/vaka); snapshot 0,191–0,287 GB (pilot toplamı 3,09 GB; kök 3,33 GB, tek vaka dahil). ✓
  - Kasıtlı kırmızı (snapshot sınırı) V1a'da. ✓ pytest 226/226. ✓
- Vaka başına: taban frontend p95 23,3–27,7 ms; ISM geçti (`ism.json`); OpenSearch send_failed / enqueue_failed 0; beklenmeyen yeniden başlama 0 (recommendation yeniden başlaması beklenen); en çok 79 °C; anonim volume her vakada silindi; `marks` hepsinde boş.
- Kararı veren sinyaller: adFailure yeni uyarı logu; adHighCpu CPU; adManualGc p99; cartFailure EmptyCart p95 (işlem); emailMemoryLeak p95; paymentFailure ve paymentUnreachable hata oranı; productCatalogFailure GetProduct hata oranı (işlem); productCatalogLockContention ListProducts p99 (işlem); recommendationCacheFailure p99; intlShippingSlowdown ship-order p99 (işlem); flood'lu iki vaka aynı sinyallerle.
- Güç kontrolü: V3 ~40 vaka ≈ 18,3 saat (6 saatlik 3 gece ya da 9 saatlik 2 gece).
- Planlamaya (karar değil):
  - Jaeger: anon tepe 1.677–1.826 MiB (2000M sınırın %84–91'i; en yüksek flood'lu vakada), `memory.events max` vaka başına 12–38 bin, OOM 0. D2'nin "anon < %80" ölçütünü her vakada aşıyor. OOM olursa vaka "beklenmeyen yeniden başlama" ile geçersiz olur (V2'de ve uzun pencerede risk).
  - cartFailure olay payı ince: EmptyCart enjeksiyon döneminde 13 istek (M = 10).
  - Hiçbir vaka belirtisiz ya da sınırda değil: pilot set kolay; V3 bileşimi için bilgi.
  - Collector cgroup tepesi flood'lu paymentFailure'da 400 / 400 MiB, ama anon ~90 MiB (dosya önbelleği), `max` 18; bellek sorunu değil.
- "Bitince": ARCHITECTURE diyagramı (kesici, snapshot'lar ve `model_view` kesik çizgiden çıktı; `incidents/` ve `incident_checks.py` eklendi), PROJECT "Şu an". GLOSSARY ve DECISIONS (snapshot biçimi, sınır, M, taban eşiği) V1a commit'inde.
- Repoda 13 pilot etiketi (`incidents/`); tek vaka denemesinin etiketi (`inc-8ceb7ae5`) V1a'da.

## 2026-10-26 · Planlama → Uygulama (vaka üretimi V2, altyapı hataları)
- V1 planlama kontrolü: rapor doğrulandı. 14 etiket (13 pilot + tek vaka) geçerli ve belirtili; 14 snapshot sızıntı tarayıcısından bağımsız geçirildi, bulgu 0; snapshot pencereleri etiketlerle aynı; pytest 226/226.
- Kararlar DECISIONS 2026-10-26 (yedi satır: Jaeger 2500M, ağ aracı, hata yöntemleri, iz kuralı, zaman kalıbı, systemd-run, V3 notu) ve INCIDENT_CATALOG "Kendi altyapı hatalarımız" tablosu. Bu kartın kayıtları planlamanın commit'inde. İşe `task/vaka-v2` dalında devam et.
- Önce 3-5 maddelik planını yaz, Eren onaylasın. Yeni ad (senaryo, imaj, konteyner, dosya, alan) koymadan önce öner. Yardımcı imajın tabanı (sabit sürümlü alpine) ve içindeki iproute2 kararla onaylı; başka imaj ya da paket sorulur. Upstream'e dokunma. V2a ve V2b sonunda rapor ver ve dur.

### Amaç
Altı altyapı hatasını (durdurma, dondurma, CPU kısıtlama, bellek sınırı, ağ gecikmesi, paket kaybı) koşucuya eklemek, kalibre etmek ve bir gece koşusunda sınamak. Vakalar `set: pilot`, resmî sete girmez.
Kapsam dışı: kendi Python servisi (sonraki kart), V3 bileşimi ve dev/test bölümü, repoda systemd birimi ve zamanlayıcı (V3'ten önce ayrı kart), değerlendirme.

### V2a · Mekanizma (gözetimli, gece koşusu yok)
1. Öner (Eren onaylar): senaryo adları, yardımcı imajın adı ve Dockerfile'ın yeri (`deploy/` altında), yardımcı konteyner ad deseni, liste dosyasında altyapı hatasının biçimi (tip, hedef, parametre).
2. Enjeksiyon ve temizleme:
   - Enjeksiyondan önce hedefin mevcut değeri okunur (CPU ve bellek sınırı), temizlemede geri yazılır ve geri okunarak doğrulanır (flag'lerdeki gibi). netem: kural silinir, `tc qdisc show` ile doğrulanır. Dondurma: `unpause`, durum running. Durdurma: `start`, durum running.
   - Temizleme doğrulanamazsa vaka geçersiz ve gece durur (sonraki vakayı kirletebilir).
   - Bellek: yeni sınır ölçülen kullanımın altında; oranı öner.
3. Kontrollerin uyarlanması:
   - Durdurma ve dondurmada hedefin kendi span'ları kesilir ya da azalır: belirti ve olay kontrolü hedefi çağıran servisin hedefe giden istemci span'larında yapılır (paymentUnreachable'daki checkout gibi). Yöntemi öner.
   - Bellek, durdurma ve dondurmada hedef `expected_restarts`'a girer. `split_restarts`'ın `paused` durumunu nasıl gördüğüne bak.
   - Koşucunun konteyner sayısı (22) ve izleme sağlığı kontrolleriyle çakışan yerleri listele.
   - İz kuralı (DECISIONS): yardımcı konteyner `otelcol-config-extras.yml`'deki süzgece eklenir (flagd satırının yanına). Sızıntı tarayıcısına desenler eklenir: yardımcı konteynerin adı ve imajı, `netem`, `qdisc`. Test: desenli sahte satır yakalanıyor (kasıtlı kırmızı).
4. Zaman kalıbı: normal dönem rastgele 8–12 dk, kuyruk rastgele 1–3 dk; tohum ve süreler etikette. Testler: süreler aralıkta, aynı tohum aynı süreleri verir.
5. Jaeger sınırı 2500M (`compose.extras.yaml`, yorum satırıyla). Etiketteki boş `run.snapshot_gb` alanı düzeltilir.
6. Kuru deneme (gözetimli): her hata tipi bir hedefte, kısa enjeksiyonla (yöntemi öner). Bakılanlar:
   - Mekanizma çalışıyor ve hedefte etki gözleniyor.
   - Temizlik doğrulanıyor.
   - Yardımcı konteyner `model_view`'da yok, sızıntı 0.
   - Bu denemelerin çıktısı sete girmez.
- Rapor ver ve dur.

### V2b · Kalibrasyon gecesi
- Aday listesi ölçmeden önce yazılır, Eren onaylar:
  - Hedefler: her hata tipi için 2 servis. Ölçütler:
    - Katalogdaki bir yayılım yolunda olsun, yayılım görünsün.
    - Pilot verisinde 10 dakikada en az M istek alsın.
    - Mümkünse farklı diller.
    - En az biri hiçbir flag'in hedefi olmayan bir servis (ör. currency, quote, shipping).
  - Parametre: CPU, gecikme ve kayıpta hafiften güçlüye 2 aday; durdurma, dondurma ve bellekte tek değer.
  - Toplam süre ≤ 9 saat.
- Başlatma: Eren `systemd-run --user` ile başlatır (DECISIONS); komutu raporda ver. Önce şarj sınırının 80 olduğu kontrol edilir.
- Ölçütler:
  - Gece yarıda kalmadı.
  - Geçerli vaka oranı ≥ %80.
  - Sızıntı 0.
  - Temizlik her vakada doğrulandı.
  - Her (tip, hedef) çifti için belirtili çıkan en hafif aday seçilir ve INCIDENT_CATALOG'a yazılır. Hiçbir aday belirtili değilse o çift rapora girer; kural değişmez, karar planlamanın.
  - Jaeger: anon tepe < 2.000 MiB, OOM 0.
  - Collector'ın OOM'u ya da yeniden başlaması 0 (mevcut kural: vakayı geçersiz kılar).
  - Belirtinin hedefi çağıranlarda görünüp görünmediği kayda geçer (geçme şartı değil; katalogdaki yayılım yollarını bu doldurur).
  - pytest yeşil.
- Güç kontrolü:
  - Bir hata tipinde iki hedefte de belirti yoksa o tip V3'e girmez ya da parametresi yeniden seçilir; karar planlamanın.
  - Jaeger ölçütü tutmazsa V3'ten önce Jaeger kararı yeniden açılır.
  - Temizliği doğrulanamayan bir vaka çıkarsa mekanizma düzeltilir ve gece tekrarlanır.
  - Vaka başına süre V3'ün kaç gece süreceğini belirler.
- Rapor ver ve dur.

### Bitince
- INCIDENT_CATALOG: senaryo adları, hedefler, parametreler, beklenen yayılım; `test_catalog.py` kapsamı.
- GLOSSARY (onaylı adlar), ARCHITECTURE (yardımcı imaj, enjeksiyon), OTEL_DEMO (Jaeger 2500M), PROJECT "Şu an". DevOps tablosundaki "Linux ağ/kaynak hataları" satırını planlama kontrolden sonra işaretler.
- PR açıklaması sade; push'tan önce PR durumuna bak.

## 2026-10-26 · Uygulama → Planlama (vaka üretimi V2a, mekanizma)
- Yapılan:
  - Altı altyapı hatası koşucuda (`INFRA_FAULTS`, `apply_fault`, `revert_fault`). Hedefin durumu önce okunur, hata uygulanıp geri okunur, temizlikte önceki değer geri yazılıp doğrulanır. Doğrulanamazsa vaka geçersiz sayılır ve gece durur (`cleanup_failed`). `frontend` hedef seçilemez.
  - Ağ hataları için yardımcı imaj `deploy/netem/Dockerfile` (`aiops-netem:1`; sabit alpine 3.24.3 ve iproute2 7.0.0-r0). Konteyner `--network container:<hedef>` ile koşar ve yalnız NET_ADMIN yetkisi alır. Gece öncesinde imaj yoksa koşucu hata verir ve derleme komutunu yazar.
  - CPU sınırının geri alınması: `docker update --cpus 0` çıkış 0 verdiği hâlde sınırı kaldırmıyor. Bu yüzden önceki değer 0 ise çekirdek sayısı yazılıyor.
  - Durdurma ve dondurmada belirti ve olay, çağıranların hedefe giden istemci span'lerinde ölçülür (`caller_rows`, `caller_symptom_check`). Hedefe giden span şu yollarla eşleşir: hedefin adı, o vakadaki IP'leri (enjeksiyondan önce ve geri almadan sonra kaydedilen) ya da hedefin kendi gelen span'lerinde görülen gRPC servis adı.
  - `split_restarts` artık `paused` değişimini de görüyor. Stop, pause ve memory hatalarında hedef `expected_restarts`'a giriyor; dondurmanın kanıtı ayrıca `fault_state`'te.
  - Zaman kalıbı tohumla belirleniyor (`schedule`): normal dönem 10–14 dk, kuyruk 1–3 dk. Pencere `fault_off + kuyruk`'ta biter.
  - İz kuralı: collector süzgecinde `aiops-netem` için kural var, sızıntı tarayıcısında `infra_term` (netem, qdisc) deseni var. OTEL_DEMO tablosuna satır eklendi; 14 snapshot yeniden tarandı, hepsi temiz. Jaeger sınırı 2500M.
  - DECISIONS 46ed6b6 eklendi:
    - Bellek sınırı toplam kullanıma (`memory.current`, `usage_mib`) göre hesaplanıyor.
    - Temizlik doğrulaması: hedef çalışıyor, dondurulmamış ve IP'si var olmalı; `STABLE_S` (30 sn) boyunca yeniden başlama sayısı sabit kalmalı (`fault_state.stable`).
    - Jaeger için kayda swap tepesi (dakikalık `memory.swap.current` ve `memory.swap.peak`) ile Go yığını tepesi (`prom_max`, Prometheus `job="jaeger"`) giriyor.
- Kuru deneme `incident_runs/20261026T0327Z-v2_dry/` (`incident_lists/v2_dry.json`, 6 hata, her biri 3 dk). Dört ölçüt geçti:
  - 6/6 uygulandı, 6/6 temizlik doğrulandı.
  - Sızıntı 0; netem/qdisc düz metin araması da 0.
  - Snapshot kökü ve `incidents/` değişmedi.
  
  Beş vaka belirtili. `memoryLimit` cart "no event" ile geçersiz: sınır 16,9 MB kaldı, cart 12 kez yeniden başladı. Bu sonuç kararın (46ed6b6) kaynağı. Eski temizlik kuralı bu vakada IP boşken "doğrulandı" demişti; yeni kural bu durumu düşürür (testte kasıtlı kırmızısı var).
- Karar eklerinin canlı kontrolü (19:35–19:43 yerel saat, demo açık ~5 dk):
  - `cgroup_memory("jaeger")` değerleri: current 1.290, anon 802, file 481 MiB; swap 0 ve swap tepesi 0 (okunabiliyor).
  - Prometheus'tan Jaeger yığın tepesi 795,6 MiB.
  - quote pause → geri alma: `verified` true, IP var, 30 sn'de yeniden başlama 0→0.
  - Demo kapandı, anonim volume silindi.
- Testler: pytest 266/266. Kasıtlı kırmızılar paused, hata tipi, tohum, aralık, gRPC eşleşmesi, IP eşleşmesi, `infra_term`, IP'siz temizlik, 30 sn içinde yeniden başlama ve anon tabanlı bellek sınırı için koşuldu; hepsinde ilgili test kırmızı verdi.
- Beklenen (planlama): V2b aday listesi. Bellekte iki aday olacak, ikisi de sürecin açılış ihtiyacının üstünde. Listeyi Eren onaylayınca kalibrasyon gecesi koşulacak.
- Dikkat:
  - Kuru denemede taban sağlık 27,6–30,7 ms çıktı; ölçüm penceresi ısınmaya taşıyordu. Gerçek gecede normal dönem 10–14 dk olduğu için taşma olmaz.
  - Monitor'deki dakikalık swap örneklemesi canlıda yalnız `cgroup_memory` okuması üzerinden sınandı (Monitor bu kontrolde çalışmadı); ilk gerçek kaydı V2b gecesi verecek.
  - Altyapı vakalarında `propagation_path` boş; V2b'den sonra katalogdan gelecek.

## 2026-10-26 · Planlama → Uygulama (V2b aday listesi)
- V2a kontrolü: rapor ve commit (`844d1d5`) uygun; pytest 266/266.
- Liste aşağıda, ölçmeden önce yazıldı (Eren onayı). Veri: pilot `inc-07533a0a`'nın normal dönemi (10 dk); istek sayısı = servisin gelen span'leri, bellek = `container.memory.usage.total` medyanı, CPU = `container.cpu.usage.total` artış hızının ortalaması.
- Kartın hedef ölçütlerinde iki düzeltme:
  - "Katalogdaki bir yayılım yolunda" ölçütü yayılımın görünmesi anlamında uygulandı. Katalogdaki yollar flag'lerden çıkıyor; flag dışı servisler (currency, quote) o yollarda yok. Bu iki servisin izlerde çağıranları var: currency ← frontend, checkout; quote ← shipping ← frontend, checkout.
  - Kartta flag dışı örneklerden biri olarak geçen shipping yanlış: shipping, intlShippingSlowdown'ın hedefi.
- checkout, email ve payment aday değil: normal dönemde 10 dk'da 24 istek alıyorlar, M = 10'a göre pay ince.

### Liste (20 vaka)
| Hata | Hedef 1 | Hedef 2 | Adaylar (hafif → güçlü) |
|---|---|---|---|
| networkDelay | cart (.NET; çağıranlar frontend, checkout) | quote (PHP; çağıran shipping) | 50 ms, 200 ms |
| packetLoss | shipping (Rust) | currency (C++) | %10, %30 |
| cpuThrottle | product-catalog (Go) | recommendation (Python) | Ortalama kullanımın 1×'i ve 0,5×'i: product-catalog 0,09 / 0,045; recommendation 0,03 / 0,015 çekirdek |
| containerPause | cart | quote | tek değer |
| containerStop | recommendation | currency | tek değer |
| memoryLimit | ad (Java) | quote (PHP) | Toplam kullanımın 0,9×'i ve 0,75×'i (enjeksiyon anında ölçülen) |

- **CPU'da flag dışı hedef yok (istisna):** currency ve quote ortalama 0,01 çekirdek kullanıyor; bu, Docker'ın en düşük sınırı.
- **Bellek tabanı:** gece öncesinde kısa bir açılışla her bellek hedefinin açılış ihtiyacı ölçülür (açılıştan sonraki ilk 60 sn'de `memory.current` tepesi). Bu tabanın altında kalan aday düşer ve kayda yazılır; o çift tek adayla kalır.
- **Kuru deneme bilgisi:**
  - product-catalog 0,05 çekirdekte p99 23 → 4.099 ms.
  - shipping 200 ms gecikmede p95 3,7 → 405 ms.
  - payment %20 kayıpta belirti zayıftı (servis düzeyi p95, güç 21).
- **Sıra:** networkDelay → packetLoss → cpuThrottle → containerPause → containerStop → memoryLimit. Temizliği en riskli olanlar sonda: temizlik doğrulanamazsa gece durur, önceki vakalar kayıtta kalır. Her çiftte hafif aday önce.
- **Süre:** vaka başına ~30 dk, toplam ~10 saat. Eren onayıyla kartın 9 saatlik bütçesinin yerine tek gece (ör. 21:00 → ~07:00).

### Gece
- Liste dosyasının adını öner (ör. `incident_lists/v2b.json`). Gece öncesinde yapılacaklar:
  - Bellek tabanı ölçümü.
  - `aiops-netem:1` imajının var olduğu kontrol edilir.
  - Şarj sınırının 80 olduğu kontrol edilir.
  - pytest yeşil.
  - Eren'e `systemd-run --user` komutu verilir.
- **Ölçütler:** kart V2b, DECISIONS 2026-10-26 düzeltmeleriyle:
  - Jaeger: OOM 0 ve yeniden başlama 0; anon, swap ve Go yığını tepesi kayda.
  - Bellek hatasında olay kuralı hedefin kendi isteği (≥ M).
- **Seçim:** her (hata, hedef) çifti için belirtili çıkan en hafif aday INCIDENT_CATALOG'a girer. Hiçbir aday belirtili değilse o çift rapora girer; kural değişmez, karar planlamanın.
- Rapor ver ve dur.

## 2026-10-26 · Uygulama → Planlama (V2b gece hazırlığı)
- Liste `incident_lists/v2b.json` (Eren onayı): kartın sırasıyla 16 vaka. Bellek çifti yok (Eren seçenek A).
- Bellek tabanı (19:55–20:03 yerel saat, kısa açılış; açılıştan sonraki ilk 60 sn'de `memory.peak`, 60. sn'de okundu; ısınmış kullanım `memory.current`, up'tan 300 sn sonra) ve **düşen adaylar** (kart kuralı):

  | Hedef | Taban | Isınmış kullanım (6. dk) | 0,9× | 0,75× |
  |---|---|---|---|---|
  | ad | 220,7 MiB | 210,2 MiB (210,7) | 189,2 MiB, düştü | 157,6 MiB, düştü |
  | quote | 24,0 MiB | 18,6 MiB (18,6) | 16,7 MiB, düştü | 14,0 MiB, düştü |

  İki serviste de açılış tepesi ısınmış kullanımdan yüksek. Bu yüzden kullanımın 1'den küçük her katı tabanın altında kalıyor. Bellek adayları yeniden seçilecek; karar planlamanın.
- Hazırlık kontrolleri:
  - `aiops-netem:1` mevcut, şarj sınırı 80, pytest 266/266.
  - Disk 281 GB boş; izleme volume'leri 6,15 GB, snapshot kökü 3,33 GB.
  - Kullanıcı biriminden `gnome-session-inhibit`, `systemd-inhibit`, Docker ve venv çalışıyor (1 sn'lik test birimi).
- Başlatma (Eren): `systemd-run --user --unit=aiops-incidents -p WorkingDirectory=/home/eren/cerebrum2/aiops_rca /home/eren/cerebrum2/aiops_rca/.venv/bin/python tools/scenario_runner.py incidents incident_lists/v2b.json`. Makine prize bağlı olmalı; koruma prize bağlı değilken başlatmaz.

## 2026-10-27 · Uygulama → Planlama (vaka üretimi V2b, kalibrasyon gecesi)
- Gece `incident_runs/20261026T1719Z-v2b/` (`incident_lists/v2b.json`, 16 vaka), 20:19–04:39 yerel saat (8 sa 20 dk). Birim `aiops-incidents` başarıyla bitti. Etiketler `incidents/` altında (16), snapshot'lar kökte (toplam 30 vaka, 7,54 GB).
- Ölçütler:
  - Gece yarıda kalmadı.
  - Geçerli 16/16, sızıntı 16/16 vakada 0.
  - Temizlik 16/16 doğrulandı: IP aynı kaldı, 30 sn'de yeniden başlama 0→0.
  - Beklenmeyen yeniden başlama 0.
  - Collector'da OOM 0 ve yeniden başlama 0 (tepe 114–123 MiB).
  - Jaeger'de OOM 0 ve yeniden başlama 0.
  - pytest 266/266.
  
  Kayıt için:
  - Taban sağlık 23,5–27,5 ms.
  - Uyku 0 sn, sıcaklık en çok 82 °C.
  - OpenSearch'e gönderim hatası 0, collector alıcısında reddedilen 0.
- Seçim (her çiftte belirtili çıkan en hafif aday):
  - networkDelay: cart 50 ms (AddItem p99 1,2 → 154 ms).
  - packetLoss: shipping %10 (servis p99, güç 63).
  - cpuThrottle: product-catalog 0.09 (GetProduct p99 22 → 1.200 ms), recommendation 0.03 (servis p99, güç 840).
  - containerPause cart ve quote, containerStop recommendation ve currency: tek değer, belirtili; ölçüm çağırandan.
  - **Aday çıkmayan çiftler:** networkDelay quote ve packetLoss currency. İki adayda da hedefte belirti yok.
- Çağıranlarda belirti (kayıt; ölçüm `caller_rows` ve `caller_symptom_check` ile, snapshot'tan): 16/16 belirtili. Aday çıkmayan çiftlerde:
  - quote 50 ms: shipping p99 4 → 148 ms (güç 7,2).
  - quote 200 ms: shipping p99 6 → 447 ms (güç 22).
  - currency %10: checkout→Convert p99 3 → 419 ms (güç 21).
  - currency %30: frontend→GetSupportedCurrencies p99 7 → 1.315 ms (güç 65).
  
  Neden: bu iki servis kimseyi çağırmıyor, netem yalnız cevaplarını geciktiriyor ve gecikme hedefin kendi span'lerine girmiyor. cart (valkey'i çağırıyor) ve shipping (quote'u çağırıyor) hedefte belirti verdi.
- Jaeger kaydı:
  - Go yığını tepesi 2.544–4.295 MiB; gece boyunca artış eğilimi yok.
  - `memory.peak` her vakada 2.500 MiB (sınırda).
  - Swap tepesi: `memory.swap.peak` 922–2.008 MiB, dakikalık örnekleme 918–1.940 MiB.
  - Anon tepe 1.995–2.240 MiB.
- Vaka başına süre 1.751–2.005 sn (ortalama 31,2 dk).
- İnce paylar (seçilmeyen adaylarda): recommendation 0.015'te enjeksiyon döneminde 12 istek, cart 200 ms'de EmptyCart 15 istek (M = 10).
- Beklenen (planlama):
  1. Ağ hatalarında, çağrı yapmayan hedeflerde belirtinin nereden ölçüleceği; quote ve currency çiftlerinin akıbeti.
  2. Yeni bellek adayları (önceki adaylar taban altında kaldı, önceki kayıt).
  3. Jaeger: yığın kararda varsayılan ~3 GiB'i aştı; swap tepesi 4 GB'lık swap'ın yarısına yaklaştı. Ölçüt geçti, ama daha uzun gecelerde risk var.
  
  Kararlardan sonra uygulama INCIDENT_CATALOG'u (adlar, hedefler, parametreler, yayılım), `test_catalog.py` kapsamını ve kalan kayıtları yazar.

## 2026-10-27 · Planlama → Uygulama (V2c: ağ belirtisi, bellek kalibrasyonu, Jaeger denemesi)
- **V2b kontrolü (planlama):**
  - Uygun: 16/16 etiket geçerli; 16 snapshot bağımsız tarandı, sızıntı 0; `window.json` etiketlerle aynı; temizlik 16/16 doğrulandı.
  - Zaman kalıbı kurala uygun: normal dönem 10,2–13,5 dk, kuyruk 1,0–3,0 dk. pytest 266/266.
  - quote ve currency için çağıran ölçümü planlamada yeniden yapıldı, uygulamanın sayılarıyla aynı.
  - V2b seçimleri kesin. Ek olarak networkDelay quote 50 ms ve packetLoss currency %10 seçildi (DECISIONS 2026-10-27, ağ belirtisi).
- **Kararlar:** DECISIONS 2026-10-27'deki üç satır (ağ belirtisi, bellek hedefleri, Jaeger). Ölçütler oradadır; bu kart sırayı verir.
- Onaylı adlar: `V2c`, `incident_lists/v2c.json` (GLOSSARY'ye uygulama yazar).

### a. Kod
- **Ağ hatalarında belirti:** networkDelay ve packetLoss'ta hedefin kendi belirtisinin yanında çağıran ölçümü de yapılır (`caller_rows`, `caller_symptom_check`); güçlü olan `symptom` olur. Etikette iki ölçümün ikisi de kayıtlı kalır. Olay kuralı değişmez.
- **Boş swap koruması:** her vakadan önce `/proc/meminfo` SwapFree < 1 GB ise koşucu vakaya başlamaz, geceyi durdurur, nedeni log'a ve kayda yazar. Vaka boyunca en düşük boş swap `run` kaydına girer.
- **Jaeger:** `compose.extras.yaml`'da Jaeger'e `GOMEMLIMIT=2000MiB`. Vaka kaydına Jaeger CPU ortalaması eklenir (yığın tepesi zaten var).
- Testler; pytest yeşil.

### b. Bellek tabanı
- Hedef adayları: cart, payment, frontend, email, recommendation.
- Taban: açılıştan sonraki ilk 60 sn'de `memory.peak`.
- Isınmış kullanım: yük altında en az 20 dk çalıştıktan sonra `memory.current`.
- Uygunluk: 0,9× ısınmış kullanım > taban. Pay = 0,9× ısınmış kullanım / taban. Payı en geniş iki servis seçilir. Her biri için iki aday: 0,9× ve 0,75× ısınmış kullanım; tabanın altındaki aday düşer.
- Hiçbir servis uymazsa memoryLimit V2'den çıkar; koşu yapılmaz, rapor ver ve dur.
- Ölçüm tablosu (beş servis: taban, ısınmış kullanım, pay, adaylar) HANDOFF'a; liste `incident_lists/v2c.json` (en fazla 4 vaka, her çiftte hafif aday önce). Eren onayından sonra koşu.

### c. Kısa koşu
- `systemd-run --user` ile, Eren başlatır (~2 saat). Öncesinde: şarj sınırı 80 mi, makine prize bağlı mı, `aiops-netem:1` mevcut mu, pytest yeşil mi.
- `GOMEMLIMIT` denemesi bu koşuda. Her vakada geçme şartı: Jaeger swap tepesi < 500 MiB, OOM 0, yeniden başlama 0, `otlp_grpc/jaeger` ve `jaeger_storage_exporter` gönderim hatası 0, collector'da reddedilen 0. Kayda: Go yığını tepesi, Jaeger CPU ortalaması, en düşük boş swap.
- Bellek seçimi: her çiftte belirtili çıkan en hafif aday. Olay kuralı: hedefin kendi isteği enjeksiyon döneminde ≥ M.
- Jaeger şartı geçmezse: ayar kaldırılır, karar planlamaya döner. Ayar yüzünden geçersiz olan vaka sonra yeniden koşulur.

### d. Rapor ver ve dur
- Raporda: bellek seçimi (ya da memoryLimit'in çıkışı), Jaeger ölçümleri vaka vaka, koruma devreye girdi mi, pytest.
- INCIDENT_CATALOG altyapı satırları planlama kontrolünden sonra yazılır.

## 2026-10-27 · Uygulama → Planlama (V2c a ve b: kod, bellek tabanı)
- **a (`7f15dca`):**
  - Ağ hatalarında belirti hem hedefte hem çağıranlarda ölçülür, güçlü olan karar verir. İki ölçüm `checks.symptom_target` ve `checks.symptom_callers` olarak kayıtlı; olay hedefin kendi isteğiyle kontrol edilir.
  - Boş swap koruması korumalara eklendi (`swap_free_gb`, 1 GB); vaka boyunca en düşük boş swap `run.min_swap_free_gb`'ye yazılır.
  - Jaeger'e `GOMEMLIMIT=2000MiB`; Jaeger CPU ortalaması kayda giriyor.
  - `run.export_failures`: Prometheus'tan, normal başından vaka sonuna. Snapshot'taki `monitoring_health` normal başı → hata kapanışını ve yalnız geçerli vakayı kapsıyor; bu okuma kuyruğu ve geçersiz vakayı da kapsar.
- **Canlı kontrolde bulunan:**
  - `send_failed` sayaçları hata olmadıkça Prometheus'ta hiç oluşmuyor; seri yoksa 0 sayılıyor (`monitoring_health` gibi).
  - Sayaçlar `__name__` deseniyle tek sorguda okunamadı; tahminen adı düşen seriler çakışıyordu. Her metrik adı ayrı sorgulanıyor.
  
  İkinci kontrolde dokuz sorgu da 0 döndü; aynı etiketlerle `sent` sayaçları doluydu (Jaeger'e 18.437, depoya 18.818 span).
- **V2b'nin altı ağ vakası yeni kuralla çevrimdışı hesaplandı:** quote ve currency'nin dört vakası belirtili oldu (karar çağırandan); olay kontrolü 108–595 istekle geçti. cart ve shipping'de de çağıran daha güçlü çıktı, karar değişmedi.
- pytest 287/287. Kasıtlı kırmızılar: güçlü olanın seçimi, swap koruması, meminfo, `cpu.stat`, boş sonucun 0 sayılması, frontend ret kuralı (iki yönde).
- **b · bellek tabanı** (23:00–23:24 yerel saat, tek açılış; değerler MiB). Taban: ilk 60 sn'de `memory.peak`. Isınmış kullanım: 25. dakikada `memory.current`. Ölçüm boyunca yeniden başlama 0. İstek sayıları pilot `inc-07533a0a`'nın normal döneminden.

  | Servis | Taban | Isınmış (20. / 25. dk) | Pay | 0,9× | 0,75× | İstek (10 dk) |
  |---|---|---|---|---|---|---|
  | frontend | 103,8 | 121,1 / 120,6 | 1,046 | 108,5 ✓ | 90,4 düştü | 9.159 |
  | cart | 47,6 | 51,6 / 52,4 | 0,991 | 47,2 düştü | 39,3 düştü | 871 |
  | email | 63,9 | 57,9 / 58,5 | 0,824 | 52,6 düştü | 43,9 düştü | 24 |
  | recommendation | 53,5 | 47,9 / 47,8 | 0,804 | 43,0 düştü | 35,8 düştü | 505 |
  | payment | 91,4 | 59,7 / 60,4 | 0,595 | 54,4 düştü | 45,3 düştü | 24 |

  Kurala uyan tek servis frontend; payı ince (sınır tabanın %4,5 üstünde). cart 0,4 MiB eksikle uymadı.
- Koşucu frontend'i reddediyordu. Eren seçenek A: ret yalnız `memoryLimit` için kalktı (DECISIONS 2026-10-27).
- Liste `incident_lists/v2c.json`: tek vaka, memoryLimit frontend 0.9 (~31 dk).
- **Dikkat (planlama):** Jaeger `GOMEMLIMIT` denemesi tek bir ~31 dk'lık vakada sınanacak. V2b'de yığın ilk 3 saatte büyümüştü; kısa koşu bunu göstermez. Ek vaka gerekip gerekmediği planlamanın kararı.
