"""BARO tablosu (HANDOFF 2026-10-30 P1b kartı 1. madde; DECISIONS 2026-10-30 "BARO girdisi", "BARO girdisi düzeltmesi"):
sentetik metrik ve izlerle ızgara, sütun sırası, kova değerleri ve eksik değerler."""
import json
import math

import pytest

from aiops_rca.cases import Case
from aiops_rca.methods.baro import baro_table

ALARM_S = 1_800_000_000
START_S = ALARM_S - 600
S = 10**9


def attr(k, v):
    return {"key": k, "value": {"stringValue": v}}


def metric_doc(container, name, points, attrs=None):
    dps = [{"timeUnixNano": str(int(t * S)), "asDouble": v, **({"attributes": attrs} if attrs else {})} for t, v in points]
    return {"resourceMetrics": [{"resource": {"attributes": [attr("container.name", container)]},
                                 "scopeMetrics": [{"metrics": [{"name": name, "sum": {"dataPoints": dps}}]}]}]}


def span_doc(svc, spans):
    return {"resourceSpans": [{"resource": {"attributes": [attr("service.name", svc)]}, "scopeSpans": [{"spans": spans}]}]}


def server_span(t_s, dur_ms, error=False, kind=2):
    return {"kind": kind, "startTimeUnixNano": str(int(t_s * S)), "endTimeUnixNano": str(int(t_s * S + dur_ms * 1e6)),
            "status": {"code": 2 if error else 0}}


@pytest.fixture
def table(tmp_path):
    view = tmp_path / "view"
    view.mkdir()
    ticks = [START_S - 5 + 10 * i for i in range(121)]  # 10 sn'de bir; ilki pencereden 5 sn önce
    # 0,5 çekirdek = 10 sn'de 5e9 ns; 70. noktada yeniden başlama: sayaç sıfırdan yeniden artar, yalnız 69→70 çifti atlanır
    cpu = [(t, 5 * S * (i if i < 70 else i - 70)) for i, t in enumerate(ticks)]
    mem = [(t, 100e6 + i) for i, t in enumerate(ticks)]
    rx0 = [(t, 1000.0 * i) for i, t in enumerate(ticks)]  # eth0: 100 B/sn
    rx1 = [(t, 500.0 * i) for i, t in enumerate(ticks)]   # eth1: 50 B/sn
    docs = [metric_doc("cart", "container.cpu.usage.total", cpu), metric_doc("cart", "container.memory.usage.total", mem),
            metric_doc("cart", "container.network.io.usage.rx_bytes", rx0, [attr("interface", "eth0")]),
            metric_doc("cart", "container.network.io.usage.rx_bytes", rx1, [attr("interface", "eth1")]),
            metric_doc("astronomy-db", "container.memory.usage.total", mem),
            metric_doc("jaeger", "container.memory.usage.total", mem), metric_doc("flagd", "container.memory.usage.total", mem)]
    (view / "metrics.jsonl").write_text("".join(json.dumps(d) + "\n" for d in docs))
    spans = [server_span(START_S + 1, 10), server_span(START_S + 2, 20, error=True), server_span(START_S + 3, 30),
             server_span(START_S + 4, 40, kind=3),  # istemci span'i: sayılmaz
             server_span(ALARM_S + 15, 50), server_span(START_S - 1, 99), server_span(ALARM_S + 600, 99)]  # son ikisi dışarıda
    traces = [span_doc("cart", spans), span_doc("jaeger", [server_span(START_S + 1, 5)]),
              span_doc("load-generator", [server_span(START_S + 1, 5)])]
    (view / "traces.jsonl").write_text("".join(json.dumps(d) + "\n" for d in traces))
    t = baro_table(Case("inc-x", view, ALARM_S * S))
    return t, {c: [r[i] for r in t["rows"]] for i, c in enumerate(t["columns"])}


def test_grid_and_split(table):
    t, col = table
    assert len(t["rows"]) == 120
    assert col["time"][0] == START_S and col["time"][-1] == ALARM_S + 590
    assert sum(x < ALARM_S for x in col["time"]) == 60


def test_columns_and_order(table):
    t, _ = table
    assert t["columns"] == ["time", "astronomy-db_mem", "cart_cpu", "cart_mem", "cart_net_rx",
                            "cart_latency", "cart_requests", "cart_errors"]


def test_container_values(table):
    _, col = table
    assert col["cart_cpu"][0] == pytest.approx(50.0)  # ilk kova pencere öncesi noktayla
    assert col["cart_cpu"][68] == pytest.approx(50.0)
    assert math.isnan(col["cart_cpu"][69]) and col["cart_cpu"][70] == pytest.approx(50.0)  # geri düşen çift atlandı
    assert col["cart_net_rx"][5] == pytest.approx(150.0)  # arayüzler toplandı
    assert col["cart_mem"][0] == 100e6 + 1  # kova 0'daki nokta START_S + 5 (indeks 1)


def test_span_values_and_missing(table):
    _, col = table
    assert (col["cart_requests"][0], col["cart_errors"][0], col["cart_latency"][0]) == (3.0, 1.0, 30.0)  # p90 en yakın sıra
    assert (col["cart_requests"][1], col["cart_errors"][1]) == (0.0, 0.0) and math.isnan(col["cart_latency"][1])
    assert (col["cart_requests"][61], col["cart_latency"][61]) == (1.0, 50.0)
    assert sum(col["cart_requests"]) == 4.0  # pencere dışındaki ve istemci span'leri yok
