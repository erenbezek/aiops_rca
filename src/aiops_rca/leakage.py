"""Sızıntı testi: modele verilecek görünümde (model_view) cevabı ele veren izleri arar.

Collector'daki süzmenin arkasındaki ikinci güvenlik ağı. Verilen klasörün altındaki her dosya JSON olarak okunur
(satır başına bir JSON ya da tek JSON belgesi; collector `file` exporter biçimi satır başına bir OTLP isteği).
Belirli alanlara bakılmaz: bütün metin değerleri ve anahtarlar taranır. Klasörün kendi adı ve altındaki klasör ve
dosya adları da taranır.

Kurallar docs/OTEL_DEMO.md "Sızıntı yolları" tablosundan gelir; her kuralın yorumunda karşılık geldiği satırlar var.
Yeni bir sızıntı biçimi önce o tabloya, sonra teste, sonra buraya eklenir.

Kullanım: python -m aiops_rca.leakage <klasör>
Çıkış kodu: 0 temiz, 1 sızıntı var, 2 girdi hatası (boş klasör, okunamayan dosya, geçersiz JSON; asla temiz sayılmaz).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# OpenTelemetry Demo 3.1.0 src/flagd/demo.flagd.json içindeki 18 anahtarın tamamı (minimal modda olmayanlar dahil).
FLAGS = (
    "adFailure", "adHighCpu", "adManualGc", "aiRunawayAgent", "aiSlowResponse", "cartFailure",
    "emailMemoryLeak", "emitRawPii", "failedReadinessProbe", "imageSlowLoad", "intlShippingSlowdown",
    "kafkaQueueProblems", "loadGeneratorFloodHomepage", "paymentFailure", "paymentUnreachable",
    "productCatalogFailure", "productCatalogLockContention", "recommendationCacheFailure",
)

# Satırlar: "flagd, flagd-ui servis telemetrisi", "flagd, flagd-ui, load-generator konteyner metrikleri",
# "load-generator span ve logu". DECISIONS 2026-10-15: simüle edilen dünyada flagd yok.
EXCLUDED_SERVICES = frozenset({"flagd", "flagd-ui", "load-generator"})
SERVICE_KEYS = ("service.name", "container.name")

SIGNALS = {"resourceSpans": "spans", "resourceMetrics": "metrics", "resourceLogs": "logs"}

ENVOY_SERVICE = "frontend-proxy"


def _flag_pattern(flags: tuple[str, ...]) -> re.Pattern[str]:
    # camelCase, snake_case, kebab-case; büyük/küçük harften bağımsız. Boşluklu yazım bilerek yok
    # ("payment failure" gerçek bir belirti mesajı olabilir).
    alternatives = []
    for flag in sorted(flags, key=len, reverse=True):
        words = re.findall(r"[a-z]+|[A-Z][a-z]*", flag)
        alternatives.append("[_-]?".join(re.escape(w) for w in words))
    # Lookahead: çakışan eşleşmeler de denenir, sol sınırı tutmayan bir eşleşme sonrakini yutmasın.
    return re.compile("(?=(" + "|".join(alternatives) + "))", re.IGNORECASE)


# Satırlar: span olayları (TracingHook), cart metrikleri (MetricsHook), ad logu, shipping logu,
# Envoy loglarındaki URL'ler; ayrıca klasör ve dosya adları.
FLAG_NAME = _flag_pattern(FLAGS)

# (kural, kalıp). Hepsi büyük/küçük harften bağımsız.
TEXT_RULES = (
    # Satırlar: span olayları ve cart metrikleri (`feature_flag.*`), recommendation span özniteliği
    # (`demo.feature_flag.recommendation_cache`), ad logu (`Feature Flag ...`), shipping logu
    # (`shipping.feature_flag.evaluated`), product-catalog span durumu (`... Fail Feature Flag Enabled`).
    ("feature_flag_phrase", re.compile(r"feature[\W_]*flag", re.IGNORECASE)),
    # Satırlar: "Tarayıcıdaki frontend'in flag sorguları" (`/flagservice/`, upstream cluster `flagservice`,
    # load-generator OFREP), flagd ve flagd-ui servis telemetrisi.
    ("flagd_term", re.compile(r"flagd|flagservice|ofrep", re.IGNORECASE)),
    # Satır: "frontend-proxy (Envoy) erişim logu ve span'leri" (`POST /feature/api/write`).
    ("feature_path", re.compile(r"/feature(?![sd])", re.IGNORECASE)),
    # Satır: "product-catalog logu". Kalıba girmeyen bilinen ifadeler.
    ("known_phrase", re.compile(r"lock\s+contention\s+scenario", re.IGNORECASE)),
)

# Satır: "frontend-proxy (Envoy) erişim logu ve span'leri" (`%RESPONSE_FLAGS%` alanında `DI`).
# Gövde biçimi (envoy.tmpl.yaml): [%START_TIME%] "%METHOD% %PATH% %PROTOCOL%" %RESPONSE_CODE% %RESPONSE_FLAGS% ...
# Sadece bayrak alanına bakılır; alan virgülle birden fazla bayrak taşıyabilir (`DI,UT`).
ENVOY_ACCESS_LOG = re.compile(r'^\[[^\]]*\] "[^"]*" (\S+) (\S+)')
# Yedek kontrol: frontend-proxy logu Envoy biçimine uymazsa boşluk/virgülle ayrılmış tek başına `DI` aranır.
STANDALONE_DI = re.compile(r"(?<![^\s,])DI(?![^\s,])")


@dataclass(frozen=True)
class Finding:
    file: str  # klasör adıyla başlayan göreli yol, ör. model_view/data.jsonl
    line: int | None  # dosyadaki satır; ad bulgusunda ve tek JSON belgesinde None
    signal: str  # spans, metrics, logs, name (klasör/dosya adı) veya unknown
    service: str | None  # kaydın service.name'i, yoksa container.name'i
    json_path: str | None  # ör. resourceLogs[0].scopeLogs[0].logRecords[0].body.stringValue
    rule: str
    match: str  # eşleşen metin


class LeakageInputError(Exception):
    """Klasör taranamadı; sonuç temiz sayılmaz."""


@dataclass(frozen=True)
class _Context:
    file: str
    line: int | None
    signal: str
    service: str | None


class _Collector:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self._seen: set[tuple] = set()

    def add(self, ctx: _Context, json_path: str | None, rule: str, match: str) -> None:
        key = (ctx.file, ctx.line, json_path, rule, match.lower())
        if key in self._seen:
            return
        self._seen.add(key)
        self.findings.append(Finding(ctx.file, ctx.line, ctx.signal, ctx.service, json_path, rule, match))


def _flag_left_boundary_ok(text: str, start: int) -> bool:
    # Önünde harf olmamalı (`loadFailure` içindeki `adFailure` sayılmaz); camelCase geçişi hariç (`xAdFailure`).
    if start == 0:
        return True
    prev = text[start - 1]
    if not prev.isalpha():
        return True
    return prev.islower() and text[start].isupper()


def _scan_text(text: str, json_path: str | None, ctx: _Context, out: _Collector) -> None:
    for m in FLAG_NAME.finditer(text):
        if _flag_left_boundary_ok(text, m.start()):
            out.add(ctx, json_path, "flag_name", m.group(1))

    for rule, pattern in TEXT_RULES:
        for m in pattern.finditer(text):
            out.add(ctx, json_path, rule, m.group(0))

    envoy = ENVOY_ACCESS_LOG.match(text)
    if envoy:
        if "DI" in envoy.group(2).split(","):
            out.add(ctx, json_path, "envoy_fault_flag", "DI")
    elif ctx.signal == "logs" and ctx.service == ENVOY_SERVICE and STANDALONE_DI.search(text):
        out.add(ctx, json_path, "envoy_fault_flag", "DI")


def _string_value(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("stringValue"), str):
        return value["stringValue"]
    return None


def _check_service(name: str, json_path: str, ctx: _Context, out: _Collector) -> None:
    # Docker konteyner adları "/" ile başlayabilir.
    if name.lstrip("/").lower() in EXCLUDED_SERVICES:
        out.add(ctx, json_path, "excluded_service", name)


def _join(path: str, key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return f"{path}.{key}" if path else key
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def _walk(node: object, path: str, ctx: _Context, out: _Collector) -> None:
    if isinstance(node, dict):
        # OTLP özniteliği: {"key": "service.name", "value": {"stringValue": "flagd"}}
        if node.get("key") in SERVICE_KEYS:
            name = _string_value(node.get("value"))
            if name is not None:
                _check_service(name, _join(_join(path, "value"), "stringValue"), ctx, out)
        for key, value in node.items():
            child = _join(path, str(key))
            # Düz JSON: {"service.name": "flagd"}
            if key in SERVICE_KEYS and isinstance(value, str):
                _check_service(value, child, ctx, out)
            _scan_text(str(key), child, ctx, out)
            _walk(value, child, ctx, out)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, f"{path}[{i}]", ctx, out)
    elif isinstance(node, str):
        _scan_text(node, path, ctx, out)


def _resource_service(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    resource = entry.get("resource")
    attributes = resource.get("attributes") if isinstance(resource, dict) else None
    if not isinstance(attributes, list):
        return None
    found = {}
    for attr in attributes:
        if isinstance(attr, dict) and attr.get("key") in SERVICE_KEYS:
            name = _string_value(attr.get("value"))
            if name is not None:
                found[attr["key"]] = name
    if "service.name" in found:
        return found["service.name"]
    if "container.name" in found:
        return found["container.name"].lstrip("/")
    return None


def _scan_record(record: object, file: str, line: int | None, out: _Collector) -> None:
    if not isinstance(record, dict):
        _walk(record, "", _Context(file, line, "unknown", None), out)
        return
    for key, value in record.items():
        signal = SIGNALS.get(key)
        _scan_text(str(key), _join("", str(key)), _Context(file, line, signal or "unknown", None), out)
        if signal and isinstance(value, list):
            for i, entry in enumerate(value):
                ctx = _Context(file, line, signal, _resource_service(entry))
                _walk(entry, f"{_join('', key)}[{i}]", ctx, out)
        else:
            _walk(value, _join("", str(key)), _Context(file, line, "unknown", None), out)


def _load_records(path: Path) -> list[tuple[int | None, object]]:
    """Satır başına bir JSON; olmazsa tek JSON belgesi. İkisi de olmazsa girdi hatası."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise LeakageInputError(f"cannot read: {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LeakageInputError(f"not UTF-8: {path}: {exc}") from exc

    records: list[tuple[int | None, object]] = []
    line_error = None
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append((number, json.loads(line)))
        except json.JSONDecodeError as exc:
            line_error = (number, exc.msg)
            break
    if line_error is None:
        return records

    try:
        return [(None, json.loads(text))]
    except json.JSONDecodeError:
        number, msg = line_error
        raise LeakageInputError(f"invalid JSON: {path}: line {number}: {msg}") from None


def scan_model_view(path: str | Path) -> list[Finding]:
    """Klasörü tarar, bulguları döner. Taranamazsa LeakageInputError."""
    root = Path(path)
    if not root.exists():
        raise LeakageInputError(f"folder not found: {root}")
    if not root.is_dir():
        raise LeakageInputError(f"not a folder: {root}")
    root = root.resolve()

    entries = [root, *sorted(root.rglob("*"))]
    files = [e for e in entries if e.is_file()]
    if not files:
        raise LeakageInputError(f"no files in folder: {root}")

    out = _Collector()

    def display(entry: Path) -> str:
        return (Path(root.name) / entry.relative_to(root)).as_posix()

    # Klasör ve dosya adları (kökün kendi adı dahil, üst klasörler hariç).
    for entry in entries:
        _scan_text(entry.name, None, _Context(display(entry), None, "name", None), out)

    record_count = 0
    for file in files:
        records = _load_records(file)
        record_count += len(records)
        for line, record in records:
            _scan_record(record, display(file), line, out)
    if record_count == 0:
        raise LeakageInputError(f"no records to scan (files are empty): {root}")

    return out.findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m aiops_rca.leakage",
        description="Scans a model_view folder for traces that reveal the answer (which fault was injected).",
    )
    parser.add_argument("model_view", help="folder to scan")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")

    try:
        findings = scan_model_view(args.model_view)
    except LeakageInputError as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    # Satır başına bir bulgu, sekmeyle ayrılmış: konum, sinyal, servis, JSON yolu, kural, eşleşen metin.
    for f in findings:
        location = f.file if f.line is None else f"{f.file}:{f.line}"
        print("\t".join([location, f.signal, f.service or "-", f.json_path or "-", f.rule, f.match]))

    if findings:
        print(f"leak: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("clean", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
