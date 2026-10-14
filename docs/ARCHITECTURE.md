# HARİTA

## Hedef yapı (taslak)

PROJECT.md'deki mimariye göre. Kesik çizgili kutular henüz yok; klasör adları ihtiyaç doğduğunda onayla verilecek.

```mermaid
flowchart LR
    subgraph ortam["Demo ortamı (Docker Compose)"]
        otel["OpenTelemetry Demo"]
        own["Kendi Python servisim"]
        col["OTel collector<br/>(flagd filtresi)"]
    end

    inj["Hata enjeksiyonu<br/>(flagd, tc netem, CPU/bellek, kill)"]
    rec["Snapshot kaydedici<br/>(PromQL, Jaeger, log)"]
    snap[("snapshot'lar<br/>snapshots/ — git dışı")]
    fix[("CI alt kümesi<br/>tests/fixtures/snapshots/")]

    base["baseline<br/>(kural, BARO)"]
    nar["candidate_narrowing"]
    llm["LLM<br/>küçük lokal model /<br/>büyük API modeli"]
    cache[("llm_cache/ — git dışı")]
    evr[("eval_responses/")]
    ev["Değerlendirme<br/>top-1/3, kanıt, kalibrasyon"]
    tab["Sonuç tablosu"]

    inj --> ortam
    col --> rec
    rec --> snap
    snap -.-> fix
    snap --> base
    snap --> nar --> llm
    snap -->|ham log| llm
    llm --> cache
    llm --> evr
    base --> ev
    evr --> ev
    ev --> tab

    smoke["tools/api_smoke_test.py"] -.->|model seçimi| llm

    classDef yok stroke-dasharray: 5 5
    class otel,own,col,inj,rec,snap,fix,base,nar,llm,cache,evr,ev,tab yok
```

## Dosyalar

| Dosya | Görev |
|---|---|
| `README.md` | Repo tanıtımı (şimdilik sadece başlık) |
| `.gitignore` | Önbellek, gizli bilgi ve büyük veriyi git dışında tutar |
| `.gitattributes` | Satır sonlarını sabitler: metin dosyaları LF, `.bat`/`.cmd` CRLF |
| `.editorconfig` | Editörlerin yeni dosyaları LF, UTF-8 ve sonda boş satırla kaydetmesi |
| `.vscode/settings.json` | VS Code'da yeni dosyalar LF (`files.eol`) |
| `docs/PROJECT.md` | Ne, neden, bitti ölçütü, kapsam dışı, şu an |
| `docs/ARCHITECTURE.md` | Bu dosya: yapı diyagramı ve dosya tablosu |
| `docs/GLOSSARY.md` | Onaylı isimler |
| `docs/DECISIONS.md` | Kararlar ve nedenleri |
| `docs/HANDOFF.md` | Oturumlar arası notlar |
| `docs/OTEL_DEMO.md` | OpenTelemetry Demo 3.1.0 keşif notları |
| `docs/INCIDENT_CATALOG.md` | Enjekte edilecek hatalar, doğru cevap kuralı, beklenen belirti ve yayılım yolları |
| `tools/api_smoke_test.py` | Aday API modellerinin teknik uygunluk testi (basit cevap, tool calling, uzun girdi) |
