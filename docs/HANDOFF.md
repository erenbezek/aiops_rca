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
