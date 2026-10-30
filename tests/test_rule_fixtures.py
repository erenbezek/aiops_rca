"""Kural baseline'ın CI regresyonu (HANDOFF 2026-10-30 P1a kartı 7. madde): kırpılmış 4 pilot vakada
(`tests/fixtures/snapshots/`, üretici `~/cerebrum2/analysis/p1a_fixtures.py`, sha256 HANDOFF'ta) `evaluate run` ve
`score` beklenen çıktıyı (`tests/fixtures/rule_expected.json`) birebir üretir; süreler hariç. Ölçü katmanının
regresyonu için her servisin her sinyalinin gücü de karşılaştırılır (kuralın ilk 3'ü eşik değişikliğini her zaman
göstermez: p95 eşiği 1,5 → 1,4 yapılınca bu 4 vakada ilk 3 aynı kaldı).

Etiketler repodaki `incidents/`'tan kopyalanır (yalnız bu 4 vaka). Beklenen çıktı bilerek değiştirilecekse:
    .venv/bin/python -c "import json, tests.test_rule_fixtures as t; print(json.dumps(t.result(), indent=1, sort_keys=True))"
(çıktı rule_expected.json'a; değişiklik ve nedeni HANDOFF'a).
"""
import json
import shutil
import tempfile
from pathlib import Path

from aiops_rca import evaluate
from aiops_rca.cases import INCIDENTS, load_cases
from aiops_rca.runs import read_run
from aiops_rca.signals import DB_SERVICES, Window, service_rows, signals, summarize

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SNAPSHOTS = FIXTURES / "snapshots"
EXPECTED = FIXTURES / "rule_expected.json"


def result() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        inc = Path(tmp) / "incidents"
        inc.mkdir()
        for view in sorted(SNAPSHOTS.iterdir()):
            shutil.copy(INCIDENTS / f"{view.name}.json", inc / f"{view.name}.json")
        run_dir = evaluate.cmd_run("rule", ("pilot",), False, Path(tmp) / "runs", incidents=inc, snapshots=SNAPSHOTS)
        _, responses = read_run(run_dir)
        scores = evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=SNAPSHOTS)
        strengths = {}
        for case in load_cases(("pilot",), incidents=inc, snapshots=SNAPSHOTS):
            svc_rows = service_rows(summarize(sorted(case.view.glob("*.jsonl")), Window(case.alarm_ns))[0])
            strengths[case.incident_id] = {
                svc: {k: v["strength"] for k, v in signals(row, svc in DB_SERVICES)[0].items()}
                for svc, row in sorted(svc_rows.items())}
    return {"signal_strengths": strengths,
            "responses": [{k: v for k, v in r.items() if k != "duration_s"} for r in responses],
            "scores": [{k: v for k, v in r.items() if k != "duration_s"} for r in scores["cases"]],
            "table": {s: {k: v for k, v in m.items() if k != "duration_s_total"} for s, m in scores["table"].items()}}


def test_fixtures_are_small_pilot_views():
    files = [f for f in SNAPSHOTS.rglob("*") if f.is_file()]
    assert sum(f.stat().st_size for f in files) <= 5_000_000
    for view in SNAPSHOTS.iterdir():
        label = json.loads((INCIDENTS / f"{view.name}.json").read_text(encoding="utf-8"))
        assert label["set"] == "pilot" and label["valid"]
        assert sorted(f.name for f in view.iterdir()) == ["logs.jsonl", "metrics.jsonl", "traces.jsonl", "window.json"]


def test_rule_baseline_reproduces_expected_output():
    assert result() == json.loads(EXPECTED.read_text(encoding="utf-8"))
