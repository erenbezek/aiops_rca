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
  - Repoda sadece betikler ve docs; model dosyaları ve ham çıktılar repo dışı. `pytest` 190 yeşil. PR koşusu: PR açılınca bakılacak.
- Dikkat:
  - Gece koşusu tur 2'nin ilk hücresinde ~30 sn priz kopmasıyla durdu (eski betik bütün koşuyu bitiriyordu). Tur 1 `20261020-015311-matrix`'ten, tur 2–3 `20261020-033005-matrix`'ten (`--rounds 2`) birleştirildi; kopan hücre kullanılmadı. `032435-matrix` (iptal) ve `032945-matrix` (boş) kullanılmadı; `014208`, `014619` duman testi, `063543` priz testi + 9B bellek ölçümü.
  - Betik artık prize dayanıklı: priz giderse 1 sn içinde iş durur, hücre `ac_lost` olarak ayrılır, priz gelince baştan koşulur; başlangıçta priz yoksa bekler; `--resume`. İki durum da elle denendi (06:35 ve 06:37).
  - İlk bellek ölçümü (konteyner cgroup `memory.peak`) yanlıştı: eşlenen model dosyası önbelleği ilk dolduran konteynere yazılıyor (9B 3,3 GB görünüyordu). Tablodaki bellek sütunu kullanılmadı; 2B ve 4B'nin belleği yeni yöntemle ölçülmedi (9B'nin altında kaldığı çıkarım).
  - 8 ve 12 iş parçacığında üretim yavaşlıyor ve sapma büyüyor (verimlilik çekirdekleri); 4 iş parçacığı hem en hızlı hem en kararlı. 6 iş parçacığı (4P + 2E) denenmedi.
  - Isınma turu (`llama-bench` warmup) girdi okuma süresi kadar ek iş yapıyor; ölçüm sürelerine dahil değil, toplam koşu süresini uzatıyor (tablo ~4,5 saat sürdü).
  - Eren uzun koşularda prize takılı bırakıyor; şarj sınırı %80'de batarya beklemede, ek zarar yok. DECISIONS'taki "sadece prizdeyken başlar" kuralı betikte "priz yoksa bekler" olarak uygulanıyor.
  - Sonraki kartlar: asıl koşular için aynı yapının `server-b11723` imajı. Kalite ölçülmedi; nicemleme üçüncü taraf.
