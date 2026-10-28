"""Sızıntı testi (aiops_rca.leakage) testleri.

Bitti ölçütü: docs/HANDOFF.md 2026-10-15 "sızıntı testi" kartı. Sahte dosyalar tests/fixtures/leakage/ altında;
her biri taranmadan önce nötr bir ada (model_view/data.jsonl) kopyalanır, böylece bulgu dosya adından değil içerikten gelir.
"""

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from aiops_rca import leakage
from aiops_rca.leakage import LeakageInputError, main, scan_model_view

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "leakage"
OTEL_DEMO_DOC = REPO / "docs" / "OTEL_DEMO.md"

# OpenTelemetry Demo 3.1.0 src/flagd/demo.flagd.json anahtarları (2026-10-15'te upstream'den kontrol edildi).
ALL_FLAGS = [
    "adFailure", "adHighCpu", "adManualGc", "aiRunawayAgent", "aiSlowResponse", "cartFailure",
    "emailMemoryLeak", "emitRawPii", "failedReadinessProbe", "imageSlowLoad", "intlShippingSlowdown",
    "kafkaQueueProblems", "loadGeneratorFloodHomepage", "paymentFailure", "paymentUnreachable",
    "productCatalogFailure", "productCatalogLockContention", "recommendationCacheFailure",
    # Bizim flag'lerimiz (deploy/otel-demo/flagd-extras.json).
    "quoteGatewayMemoryLeak", "quoteGatewayMisroute", "quoteGatewaySlowdown",
]

# Sahte dosya → (OTEL_DEMO.md "Sızıntı yolları" tablosundaki satır, beklenen bulgular).
# Beklenen bulgu: (kural, satır, eşleşen metinde geçmesi gereken parça, küçük harf).
LEAK_FIXTURES = {
    "leak_flagd_service.jsonl": (
        "flagd, flagd-ui servis telemetrisi",
        [("excluded_service", 2, "flagd"), ("excluded_service", 3, "flagd-ui")],
    ),
    "leak_tracing_hook_event.jsonl": (
        "checkout, product-catalog, recommendation, load-generator, agent span'leri",
        [("flag_name", 2, "paymentunreachable"), ("feature_flag_phrase", 2, "feature_flag")],
    ),
    "leak_metrics_hook.jsonl": (
        "cart metrikleri",
        [("feature_flag_phrase", 2, "feature_flag"), ("flag_name", 2, "cartfailure")],
    ),
    "leak_recommendation_cache_attr.jsonl": (
        "recommendation span özniteliği",
        [("feature_flag_phrase", 2, "feature_flag")],
    ),
    "leak_ad_log.jsonl": (
        "ad logu",
        [("flag_name", 2, "admanualgc"), ("feature_flag_phrase", 2, "feature flag")],
    ),
    "leak_shipping_log.jsonl": (
        "shipping logu",
        [("feature_flag_phrase", 2, "feature_flag"), ("flag_name", 2, "intlshippingslowdown")],
    ),
    "leak_envoy_feature_write.jsonl": (
        "frontend-proxy (Envoy) erişim logu ve span'leri",
        [("feature_path", 2, "/feature"), ("feature_path", 3, "/feature")],
    ),
    "leak_envoy_fault_flag.jsonl": (
        "frontend-proxy (Envoy) erişim logu ve span'leri",
        [("envoy_fault_flag", 2, "di"), ("envoy_fault_flag", 3, "di")],
    ),
    # Envoy biçimine uymayan frontend-proxy logu: yedek kontrol (tek başına DI) devreye girmeli.
    "leak_envoy_fault_flag_unparsed.jsonl": (
        "frontend-proxy (Envoy) erişim logu ve span'leri",
        [("envoy_fault_flag", 2, "di")],
    ),
    "leak_flagservice_route.jsonl": (
        "Tarayıcıdaki frontend'in flag sorguları",
        [("flagd_term", 2, "flagservice"), ("flagd_term", 3, "ofrep")],
    ),
    "leak_container_metrics.jsonl": (
        "flagd, flagd-ui, load-generator konteyner metrikleri",
        [
            ("excluded_service", 2, "load-generator"),  # container.name
            ("excluded_service", 3, "load-generator"),  # container.name, başında "/"
            ("excluded_service", 4, "load-generator"),  # span_metrics, service.name
        ],
    ),
    "leak_product_catalog_status.jsonl": (
        "product-catalog span durumu ve olayı",
        [("feature_flag_phrase", 2, "feature flag")],
    ),
    "leak_lock_contention_log.jsonl": (
        "product-catalog logu",
        [("known_phrase", 2, "lock contention scenario")],
    ),
    "leak_load_generator.jsonl": (
        "load-generator span ve logu",
        [("excluded_service", 2, "load-generator"), ("excluded_service", 3, "load-generator")],
    ),
    "leak_infra_helper.jsonl": (
        "Altyapı hatası yardımcı konteyneri ve komut izleri (V2)",
        [("infra_term", 2, "netem"), ("infra_term", 3, "qdisc"), ("infra_term", 3, "netem")],
    ),
}

CLEAN_FIXTURES = ["clean_symptoms.jsonl", "clean_false_alarms.jsonl"]


# --- yardımcılar ---

def make_view(tmp_path, fixture_name):
    """Sahte dosyayı nötr adla model_view/data.jsonl olarak kopyalar."""
    view = tmp_path / "model_view"
    view.mkdir()
    shutil.copyfile(FIXTURES / fixture_name, view / "data.jsonl")
    return view


def log_line(service, body):
    """Tek log kaydı içeren OTLP JSON satırı."""
    return json.dumps({
        "resourceLogs": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
            "scopeLogs": [{"scope": {"name": "test"}, "logRecords": [{"body": {"stringValue": body}}]}],
        }]
    })


def view_with_lines(tmp_path, lines, name="data.jsonl"):
    view = tmp_path / "model_view"
    view.mkdir(exist_ok=True)
    (view / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return view


def leak_table_rows():
    """OTEL_DEMO.md "Sızıntı yolları" tablosunun ilk sütunu."""
    text = OTEL_DEMO_DOC.read_text(encoding="utf-8")
    section = text.split("## Sızıntı yolları", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cell = line.strip("|").split("|")[0].strip()
        if cell in ("Kaynak", "") or set(cell) <= {"-"}:
            continue
        rows.append(cell)
    return rows


# --- ölçüt 1: sızıntı tablosundaki her satır için sahte dosya ve bulgu ---

def test_every_leak_table_row_has_a_fixture():
    rows = leak_table_rows()
    assert len(rows) == 13
    covered = {row for row, _ in LEAK_FIXTURES.values()}
    assert set(rows) == covered


def test_every_leak_fixture_file_is_listed():
    on_disk = {p.name for p in FIXTURES.glob("leak_*.jsonl")}
    assert on_disk == set(LEAK_FIXTURES)


@pytest.mark.parametrize("fixture_name", sorted(LEAK_FIXTURES))
def test_leak_fixture_produces_expected_findings(tmp_path, fixture_name):
    view = make_view(tmp_path, fixture_name)
    findings = scan_model_view(view)

    # Dosya adı nötr: hiçbir bulgu addan gelmemeli.
    assert [f for f in findings if f.signal == "name"] == []

    _, expected = LEAK_FIXTURES[fixture_name]
    for rule, line, match_part in expected:
        hits = [
            f for f in findings
            if f.rule == rule and f.line == line and f.json_path and match_part in f.match.lower()
        ]
        assert hits, f"{fixture_name}: beklenen bulgu yok: {rule} satır {line} '{match_part}'\nbulgular: {findings}"

    # Satır 1 her sahte dosyada temiz trafik.
    assert [f for f in findings if f.line == 1] == []


# --- ölçüt 2 ve 3: temiz dosyada ve yanlış alarm adaylarında sıfır bulgu ---

@pytest.mark.parametrize("fixture_name", CLEAN_FIXTURES)
def test_clean_fixture_has_no_findings(tmp_path, fixture_name):
    view = make_view(tmp_path, fixture_name)
    assert scan_model_view(view) == []
    assert main([str(view)]) == 0


# --- kural biçimleri ---

@pytest.mark.parametrize("flag", ALL_FLAGS)
@pytest.mark.parametrize("form", ["camel", "pascal", "lower", "upper", "snake", "upper_snake", "kebab"])
def test_flag_name_forms(tmp_path, flag, form):
    words = [w.lower() for w in re.findall(r"[a-z]+|[A-Z][a-z]*", flag)]
    text = {
        "camel": flag,
        "pascal": flag[0].upper() + flag[1:],
        "lower": flag.lower(),
        "upper": flag.upper(),
        "snake": "_".join(words),
        "upper_snake": "_".join(words).upper(),
        "kebab": "-".join(words),
    }[form]
    view = view_with_lines(tmp_path, [log_line("frontend", f"value={text} done")])
    assert any(f.rule == "flag_name" for f in scan_model_view(view)), text


@pytest.mark.parametrize("text", [
    "feature_flag", "feature.flag", "feature-flag", "Feature Flag", "FEATURE_FLAG", "featureFlag", "feature flags",
])
def test_feature_flag_phrase_separators(tmp_path, text):
    view = view_with_lines(tmp_path, [log_line("frontend", f"x {text} y")])
    assert any(f.rule == "feature_flag_phrase" for f in scan_model_view(view))


@pytest.mark.parametrize("text", ["flagd", "FlagD", "flagservice", "OFREP"])
def test_flagd_terms(tmp_path, text):
    view = view_with_lines(tmp_path, [log_line("frontend", f"upstream {text} ok")])
    assert any(f.rule == "flagd_term" for f in scan_model_view(view))


@pytest.mark.parametrize("path, leaks", [
    ("/feature", True),
    ("/feature/api/read", True),
    ("/Feature/api/write", True),
    ("/features", False),
    ("/featured", False),
    ("/api/products/featured", False),
])
def test_feature_path(tmp_path, path, leaks):
    view = view_with_lines(tmp_path, [log_line("frontend", f"GET {path} 200")])
    found = any(f.rule == "feature_path" for f in scan_model_view(view))
    assert found == leaks


@pytest.mark.parametrize("key", ["service.name", "container.name"])
@pytest.mark.parametrize("value", ["flagd", "flagd-ui", "load-generator", "/load-generator"])
def test_excluded_service_both_attributes(tmp_path, key, value):
    line = json.dumps({
        "resourceMetrics": [{
            "resource": {"attributes": [{"key": key, "value": {"stringValue": value}}]},
            "scopeMetrics": [],
        }]
    })
    view = view_with_lines(tmp_path, [line])
    assert any(f.rule == "excluded_service" for f in scan_model_view(view))


def test_excluded_service_ignores_other_services(tmp_path):
    line = json.dumps({
        "resourceMetrics": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "checkout"}},
                {"key": "container.name", "value": {"stringValue": "/checkout"}},
            ]},
            "scopeMetrics": [],
        }]
    })
    view = view_with_lines(tmp_path, [line])
    assert scan_model_view(view) == []


def test_envoy_fallback_only_for_standalone_di(tmp_path):
    view = view_with_lines(tmp_path, [
        log_line("frontend-proxy", "GET /images/x.jpg 200 DI 5004ms"),        # 1: bulgu
        log_line("frontend-proxy", "flags=UF,DI"),                            # 2: bulgu (virgülle ayrılmış)
        log_line("frontend-proxy", "Applied DISCOUNT code; DIAG ok; MIDI"),   # 3: bulgu yok
        log_line("checkout", "GET /images/x.jpg 200 DI 5004ms"),              # 4: frontend-proxy değil, yedek kontrol yok
    ])
    lines = sorted(f.line for f in scan_model_view(view) if f.rule == "envoy_fault_flag")
    assert lines == [1, 2]


@pytest.mark.parametrize("text,leaks", [
    ("aiops-netem", True), ("qdisc netem 8001: root", True), ("QDISC del dev eth0", True), ("NetEm", True),
    ("network timeout after 200ms", False), ("delay 200ms", False), ("discount applied", False),
])
def test_infra_terms(tmp_path, text, leaks):
    view = view_with_lines(tmp_path, [log_line("shipping", text)])
    found = [f for f in scan_model_view(view) if f.rule == "infra_term"]
    assert bool(found) is leaks, found


def test_known_phrase(tmp_path):
    view = view_with_lines(tmp_path, [log_line("product-catalog", "Lock Contention Scenario active")])
    assert any(f.rule == "known_phrase" for f in scan_model_view(view))


# --- ölçüt 4: girdi hataları → çıkış kodu 2, asla temiz değil ---

def test_empty_folder(tmp_path):
    view = tmp_path / "model_view"
    view.mkdir()
    with pytest.raises(LeakageInputError):
        scan_model_view(view)
    assert main([str(view)]) == 2


def test_folder_with_only_empty_file(tmp_path):
    view = view_with_lines(tmp_path, [""])
    assert main([str(view)]) == 2


def test_missing_folder(tmp_path):
    assert main([str(tmp_path / "missing")]) == 2


def test_path_is_a_file(tmp_path):
    view = make_view(tmp_path, "clean_symptoms.jsonl")
    assert main([str(view / "data.jsonl")]) == 2


def test_invalid_json(tmp_path):
    view = view_with_lines(tmp_path, [log_line("frontend", "ok"), "{not json"])
    assert main([str(view)]) == 2


def test_invalid_json_next_to_leak_is_still_input_error(tmp_path):
    view = make_view(tmp_path, "leak_ad_log.jsonl")
    (view / "broken.jsonl").write_text("{not json\n", encoding="utf-8")
    assert main([str(view)]) == 2


def test_invalid_utf8(tmp_path):
    view = tmp_path / "model_view"
    view.mkdir()
    (view / "data.jsonl").write_bytes(b'{"a": "\xff\xfe"}\n')
    assert main([str(view)]) == 2


def test_unreadable_file(tmp_path, monkeypatch):
    view = make_view(tmp_path, "clean_symptoms.jsonl")

    def deny(self):
        raise PermissionError(f"erişim reddedildi: {self}")

    monkeypatch.setattr(Path, "read_bytes", deny)
    assert main([str(view)]) == 2


def test_pretty_printed_json_document_is_accepted(tmp_path):
    view = tmp_path / "model_view"
    view.mkdir()
    doc = json.loads(log_line("ad", "Feature Flag adManualGc enabled"))
    (view / "data.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    findings = scan_model_view(view)
    assert any(f.rule == "flag_name" for f in findings)


# --- ölçüt 5: klasör ve dosya adları ---

def test_folder_name_with_flag(tmp_path):
    sub = tmp_path / "model_view" / "incident_paymentFailure"
    sub.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "clean_symptoms.jsonl", sub / "data.jsonl")
    findings = scan_model_view(tmp_path / "model_view")
    assert any(f.rule == "flag_name" and f.signal == "name" and "incident_paymentFailure" in f.file for f in findings)


def test_file_name_with_flag(tmp_path):
    view = tmp_path / "model_view"
    view.mkdir()
    shutil.copyfile(FIXTURES / "clean_symptoms.jsonl", view / "cart_failure_spans.jsonl")
    findings = scan_model_view(view)
    assert any(f.rule == "flag_name" and f.signal == "name" and f.line is None for f in findings)


def test_root_folder_name_is_scanned(tmp_path):
    view = tmp_path / "adHighCpu"
    view.mkdir()
    shutil.copyfile(FIXTURES / "clean_symptoms.jsonl", view / "data.jsonl")
    findings = scan_model_view(view)
    assert any(f.rule == "flag_name" and f.signal == "name" for f in findings)


def test_parent_folders_are_not_scanned(tmp_path):
    # Karar (2026-10-15): verilen klasör ve altı taranır; üst klasörleri planlama ayrıca ele alacak.
    view = tmp_path / "paymentFailure" / "model_view"
    view.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "clean_symptoms.jsonl", view / "data.jsonl")
    assert scan_model_view(view) == []


# --- ölçüt 6: bulgu alanları ---

def test_finding_fields(tmp_path):
    view = make_view(tmp_path, "leak_ad_log.jsonl")
    hits = [f for f in scan_model_view(view) if f.rule == "flag_name"]
    assert len(hits) == 1
    f = hits[0]
    assert f.file == "model_view/data.jsonl"
    assert f.line == 2
    assert f.signal == "logs"
    assert f.service == "ad"
    assert f.json_path == "resourceLogs[0].scopeLogs[0].logRecords[0].body.stringValue"
    assert f.match == "adManualGc"


def test_finding_service_falls_back_to_container_name(tmp_path):
    view = make_view(tmp_path, "leak_container_metrics.jsonl")
    hits = [f for f in scan_model_view(view) if f.line == 2]
    assert hits and all(f.service == "load-generator" and f.signal == "metrics" for f in hits)


def test_cli_output_lists_findings(tmp_path, capsys):
    view = make_view(tmp_path, "leak_lock_contention_log.jsonl")
    assert main([str(view)]) == 1
    out = capsys.readouterr().out
    assert "model_view/data.jsonl" in out
    assert "known_phrase" in out
    assert "product-catalog" in out


def test_module_entry_point(tmp_path):
    view = make_view(tmp_path, "leak_ad_log.jsonl")
    result = subprocess.run([sys.executable, "-m", "aiops_rca.leakage", str(view)], capture_output=True)
    assert result.returncode == 1


# --- ölçüt 7: çalışma zamanında sadece standart kütüphane ---

def test_leakage_imports_only_stdlib():
    tree = ast.parse(Path(leakage.__file__).read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.add(node.module.split(".")[0])
    assert modules <= set(sys.stdlib_module_names) | {"__future__"}, modules


def test_scanner_knows_our_flags():
    # flagd-extras.json'a eklenen her flag tarayıcının listesinde olmalı (quote-gateway kartı, Eren).
    ours = set(json.loads((REPO / "deploy" / "otel-demo" / "flagd-extras.json").read_text(encoding="utf-8"))["flags"])
    assert ours and ours <= set(leakage.FLAGS) and ours <= set(ALL_FLAGS)
