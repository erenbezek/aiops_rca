"""tools/incident_checks.py testleri (V1): küçük sahte OTLP girdileriyle kuralların sınırları.

C2 verisiyle kabul (2. adımın sayılarını aynen üretmesi) ayrıca yapıldı (HANDOFF V1a raporu); burada veri yok.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import incident_checks as ic  # noqa: E402
from trial_summary import Window  # noqa: E402

ALARM = 1_800_000_000 * 10**9
MS = 10**6
SERVER, CLIENT = 2, 3


def span(name: str, t: int, dur_ms: float, kind: int = SERVER, error: bool = False) -> dict:
    s = {"name": name, "kind": kind, "startTimeUnixNano": str(t), "endTimeUnixNano": str(t + int(dur_ms * MS))}
    if error:
        s["status"] = {"code": 2}
    return s


def write_traces(path: Path, service: str, spans: list[dict]) -> Path:
    doc = {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name",
                                                           "value": {"stringValue": service}}]},
                              "scopeSpans": [{"spans": spans}]}]}
    path.write_text(json.dumps(doc) + "\n")
    return path


def periods(name: str, n_before: int, n_after: int, ms_before: float, ms_after: float, **kw) -> list[dict]:
    before = [span(name, ALARM - 60 * 10**9 + i * MS, ms_before, **kw) for i in range(n_before)]
    after = [span(name, ALARM + 60 * 10**9 + i * MS, ms_after, **kw) for i in range(n_after)]
    return before + after


def ops_for(tmp_path: Path, spans: list[dict], service: str = "cart") -> dict:
    return ic.operation_rows([write_traces(tmp_path / "traces.jsonl", service, spans)], Window(ALARM))


def test_operation_rows_counts_only_incoming_spans(tmp_path):
    spans = periods("GetCart", 3, 4, 5, 5) + periods("redis", 9, 9, 1, 1, kind=CLIENT)
    ops = ops_for(tmp_path, spans)
    assert set(ops) == {("cart", "GetCart")}
    assert ops[("cart", "GetCart")]["before"][0] == 3 and ops[("cart", "GetCart")]["after"][0] == 4


def test_operation_latency_symptom_decides(tmp_path):
    ops = ops_for(tmp_path, periods("EmptyCart", 20, 20, 5, 500))
    s = ic.symptom_check({}, ops, "cart")
    assert s["verdict"] == "symptomatic"
    assert s["deciding"]["level"] == "operation" and s["deciding"]["operation"] == "EmptyCart"


def test_operation_below_min_requests_ignored(tmp_path):
    # Kasıtlı kırmızının karşılığı: aynı sapma, enjeksiyon döneminde M − 1 istek → ölçülmez.
    ops = ops_for(tmp_path, periods("EmptyCart", 20, ic.MIN_OP_REQUESTS - 1, 5, 500))
    s = ic.symptom_check({}, ops, "cart")
    assert s["operation_level"] is None and s["verdict"] == "not_measurable"


def test_small_latency_change_is_no_symptom(tmp_path):
    ops = ops_for(tmp_path, periods("GetCart", 20, 20, 5, 6))
    assert ic.symptom_check({}, ops, "cart")["verdict"] == "no_symptom"


def test_error_rate_threshold(tmp_path):
    spans = periods("Charge", 20, 0, 5, 5) + [span("Charge", ALARM + 60 * 10**9 + i * MS, 5, error=i < 2)
                                             for i in range(20)]
    s = ic.symptom_check({}, ops_for(tmp_path, spans, "payment"), "payment")
    assert s["deciding"]["signal"] == "error_rate" and s["deciding"]["strength"] == 2.0  # 0,10 / 0,05


def test_event_check_operation_basis(tmp_path):
    ops = ops_for(tmp_path, periods("EmptyCart", 20, 12, 5, 500))
    s = ic.symptom_check({}, ops, "cart")
    e = ic.event_check(s, {"cart": {"requests_after": 1000}})
    assert e["applied"] and e["pass"] and e["requests_after"] == 12 and e["basis"].startswith("operation")


def test_event_check_resource_signal_uses_service_total():
    rows = {"email": {"requests_before": 50, "requests_after": 4, "cpu_pct_before": 1.0, "cpu_pct_after": 1.0,
                      "mem_mb_before": 50.0, "mem_mb_after": 90.0}}
    s = ic.symptom_check(rows, {}, "email")
    assert s["deciding"]["signal"] == "mem_mb"
    e = ic.event_check(s, rows)
    assert e["applied"] and not e["pass"] and e["requests_after"] == 4 and "resource" in e["basis"]


def test_event_check_not_applied_without_spans():
    rows = {"astronomy-db": {"cpu_pct_before": 1.0, "cpu_pct_after": 5.0, "mem_mb_before": 50.0,
                             "mem_mb_after": 50.0}}
    s = ic.symptom_check(rows, {}, "astronomy-db")
    e = ic.event_check(s, rows)
    assert e["applied"] is False and e["pass"] is None


def test_thresholds_are_the_v1a_values():
    # V1a 2. adımda C2 verisinden seçildi; değişiklik bilerek yapılmalı (DECISIONS'a yazılır).
    assert (ic.MIN_OP_REQUESTS, ic.BASELINE_P95_MS, ic.BASELINE_FACTOR) == (10, 25.3, 2)


@pytest.mark.parametrize("p95,ok", [(ic.BASELINE_FACTOR * ic.BASELINE_P95_MS, True),
                                    (ic.BASELINE_FACTOR * ic.BASELINE_P95_MS + 0.1, False), (None, False)])
def test_baseline_check(p95, ok):
    rows = {"frontend": {"p95_ms_before": p95}} if p95 is not None else {}
    assert ic.baseline_check(rows)["pass"] is ok


def test_monitoring_health_opensearch_increase(tmp_path):
    def point(t, v):
        return {"timeUnixNano": str(t), "asDouble": v,
                "attributes": [{"key": "exporter", "value": {"stringValue": "opensearch"}}]}
    doc = {"resourceMetrics": [{"resource": {"attributes": []}, "scopeMetrics": [{"metrics": [
        {"name": "otelcol_exporter_sent_log_records", "sum": {"dataPoints": [point(ALARM - 10, 100),
                                                                              point(ALARM + 10, 150)]}},
        {"name": "otelcol_exporter_send_failed_log_records", "sum": {"dataPoints": [point(ALARM - 10, 0),
                                                                                     point(ALARM + 10, 3)]}},
    ]}]}]}
    f = tmp_path / "metrics.jsonl"
    f.write_text(json.dumps(doc) + "\n")
    h = ic.monitoring_health(f, ALARM - 5, ALARM + 20)
    assert h["opensearch"]["sent"] == 50 and h["opensearch"]["send_failed"] == 3
