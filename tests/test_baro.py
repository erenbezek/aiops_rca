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


# --- port (P1b 2. adım): RCAEval main.py ön adımları + baro ------------------------------------------------------

from aiops_rca.methods.baro import _fill, _percentile, baro_rank  # noqa: E402

NAN, INF = float("nan"), float("inf")


def tab(cols: dict) -> dict:
    """120 satır: time = 0..1190 (10 sn), alarm 600."""
    names = ["time", *cols]
    return {"columns": names, "rows": [[float(10 * i)] + [cols[c][i] for c in cols] for i in range(120)]}


def test_fill_inf_ffill_then_zero():
    assert _fill([[NAN, 1.0], [INF, NAN], [2.0, -INF], [NAN, 3.0]]) == [[0.0, 1.0], [0.0, 1.0], [2.0, 1.0], [2.0, 3.0]]


def test_percentile_matches_numpy_linear():
    v = [float(i) for i in range(60)]  # numpy: percentile(range(60), [25, 75]) = [14.75, 44.25]
    assert (_percentile(v, 25), _percentile(v, 75)) == (14.75, 44.25)
    assert _percentile([1.0, 2.0, 4.0, 8.0], 25) == 1.75 and _percentile([1.0, 2.0, 4.0, 8.0], 75) == 5.0


def test_rank_scores_and_order():
    up = [float(i % 60) for i in range(60)] + [100.0] + [0.0] * 59      # merkez 29,5, ölçek 29,5
    flat_normal = [5.0] * 60 + [float(i) for i in range(60)]             # normalde sabit: o dönemde atılır → kesişimde yok
    zero_iqr = [1.0] * 59 + [2.0] + [1.0] * 59 + [4.0]                   # çeyrekler arası 0 → ölçek 1
    mem = [1e6 * (i % 60) for i in range(60)] + [100e6] + [0.0] * 59     # /1e6 → up ile aynı puan, sırada up'tan sonra
    r = baro_rank(tab({"b_up": up, "a_flat": flat_normal, "c_iqr": zero_iqr, "d_mem": mem}), 600)
    assert [c for c, _ in r] == ["c_iqr", "b_up", "d_mem"]  # 3,0 > 2,39 = 2,39; eşit puanda girdi sırası (kararlı)
    assert dict(r)["b_up"] == dict(r)["d_mem"] == (100.0 - 29.5) / 29.5 and dict(r)["c_iqr"] == 3.0


def test_rank_missing_values_are_filled_first():
    # NaN'lar ffill ile dolar: anomali dönemi tümüyle NaN olan sütun son normal değerle sabitlenir, o dönemde atılır.
    s = [float(i % 60) for i in range(60)] + [NAN] * 60
    leading = [NAN] * 10 + [1.0] * 50 + [9.0] + [1.0] * 59              # baştaki NaN → 0
    r = dict(baro_rank(tab({"x": s, "y": leading}), 600))
    assert "x" not in r
    assert r["y"] == 8.0  # normal: 10 sıfır + 50 bir → medyan 1, 25. ve 75. yüzdelik 1 → ölçek 0 → 1; z = (9 − 1) / 1


# --- CI örnekleri (P1b kapanış): 4 kırpılmış pilot vakada BARO'nun beklenen çıktısı -----------------------------
# Örnekler P1a'nınkiler (`tests/fixtures/snapshots/`; metrikleri yalnız CPU ve bellek, ağ sütunu yok). Beklenen çıktı
# bilerek değiştirilecekse:
#   .venv/bin/python -c "import json, tests.test_baro as t; print(json.dumps(t.baro_fixture_result(), indent=1, sort_keys=True))"
# (çıktı tests/fixtures/baro_expected.json'a; değişiklik ve nedeni HANDOFF'a).

import shutil  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

from aiops_rca import evaluate  # noqa: E402
from aiops_rca.cases import INCIDENTS  # noqa: E402
from aiops_rca.runs import read_run  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def baro_fixture_result() -> dict:
    snaps = FIXTURES / "snapshots"
    with tempfile.TemporaryDirectory() as tmp:
        inc = Path(tmp) / "incidents"
        inc.mkdir()
        for view in sorted(snaps.iterdir()):
            shutil.copy(INCIDENTS / f"{view.name}.json", inc / f"{view.name}.json")
        run_dir = evaluate.cmd_run("baro", ("pilot",), False, Path(tmp) / "runs", incidents=inc, snapshots=snaps)
        _, responses = read_run(run_dir)
        scores = evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=snaps)
    return {"responses": [{k: v for k, v in r.items() if k != "duration_s"} for r in responses],
            "scores": [{k: v for k, v in r.items() if k != "duration_s"} for r in scores["cases"]],
            "table": {s: {k: v for k, v in m.items() if k != "duration_s_total"} for s, m in scores["table"].items()}}


def test_baro_reproduces_expected_output_on_fixtures():
    want = json.loads((FIXTURES / "baro_expected.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(baro_fixture_result(), sort_keys=True)) == want
