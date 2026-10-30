"""Değerlendirme CLI'ı uçtan uca (HANDOFF 2026-10-30 P1a kartı 5–6. madde): sahte snapshot'ta kural baseline koşar, her
cevap şemaya uyar, iki koşu (süre hariç) birebir aynı, puanlama tabloyu kayıtlardan üretir, `test` bayraksız reddedilir."""
import json

import pytest

from aiops_rca import evaluate
from aiops_rca.runs import read_run

ALARM_S = 1_800_000_000
MIN = 60 * 10**9


def attr(k, v):
    return {"key": k, "value": {"stringValue": v}}


def span(sid, parent, t, kind=2, error=False, dur_ms=10):
    s = {"spanId": sid, "kind": kind, "startTimeUnixNano": str(t), "endTimeUnixNano": str(t + dur_ms * 10**6),
         "status": {"code": 2 if error else 0}}
    if parent:
        s["parentSpanId"] = parent
    return s


def snapshot(view, bad: str):
    """frontend → checkout → payment, frontend → cart. `bad` servisi alarmdan sonra hata verir."""
    alarm = ALARM_S * 10**9
    docs = []
    for i, t in enumerate([alarm - 9 * MIN + k * 10**9 * 9 for k in range(60)] +
                          [alarm + MIN + k * 10**9 * 9 for k in range(60)]):
        after = t >= alarm
        spans = {"frontend": [span(f"f{i}", None, t), span(f"fc{i}", f"f{i}", t, kind=3),
                              span(f"fk{i}", f"f{i}", t, kind=3)],
                 "checkout": [span(f"c{i}", f"fc{i}", t, error=after and bad == "checkout"),
                              span(f"cp{i}", f"c{i}", t, kind=3)],
                 "payment": [span(f"p{i}", f"cp{i}", t, error=after and bad == "payment")],
                 "cart": [span(f"k{i}", f"fk{i}", t, error=after and bad == "cart")]}
        docs.append({"resourceSpans": [{"resource": {"attributes": [attr("service.name", svc)]},
                                        "scopeSpans": [{"spans": sp}]} for svc, sp in spans.items()]})
    view.mkdir(parents=True)
    (view / "traces.jsonl").write_text("".join(json.dumps(d) + "\n" for d in docs))
    (view / "window.json").write_text(json.dumps({"start": "x", "end": "y"}))


def label(iid, set_, root):
    return {"incident_id": iid, "set": set_, "valid": True,
            "answer": {"injection_start": "2027-01-15T08:00:00Z", "root_cause_service": root,
                       "propagation_path": [[root, "checkout"], ["checkout", "frontend"]] if root == "payment"
                       else [[root, "frontend"]]}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    inc, snaps = tmp_path / "incidents", tmp_path / "snapshots"
    inc.mkdir()
    from datetime import datetime, timezone
    start = datetime.fromtimestamp(ALARM_S, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for iid, set_, root in (("inc-a", "dev", "payment"), ("inc-b", "pilot", "cart"), ("inc-t", "test", "payment")):
        lab = label(iid, set_, root)
        lab["answer"]["injection_start"] = start
        (inc / f"{iid}.json").write_text(json.dumps(lab))
        snapshot(snaps / iid, root)
    return inc, snaps, tmp_path / "runs"


def run(world):
    inc, snaps, root = world
    return evaluate.cmd_run("rule", ("pilot", "dev"), False, root, incidents=inc, snapshots=snaps)


def test_rule_run_schema_and_answers(world):
    run_dir = run(world)
    meta, rows = read_run(run_dir)
    assert (meta["method"], meta["sets"], meta["n_cases"], meta["model_id"]) == ("rule", ["pilot", "dev"], 2, None)
    assert [r["incident_id"] for r in rows] == ["inc-a", "inc-b"]
    assert all(r["schema_valid"] and r["schema_errors"] == [] and r["tokens"] is None for r in rows)
    first = {r["incident_id"]: r["answer"]["candidates"][0] for r in rows}
    assert (first["inc-a"]["service"], first["inc-b"]["service"]) == ("payment", "cart")
    assert first["inc-a"]["confidence"] is None and first["inc-a"]["evidence_path"] == ["payment"]
    assert all(r["answer"]["unsure"] is False for r in rows)


def test_two_runs_identical_except_duration(world):
    a, b = (read_run(run(world))[1] for _ in range(2))
    strip = [[{k: v for k, v in r.items() if k != "duration_s"} for r in x] for x in (a, b)]
    assert strip[0] == strip[1]


def test_score_from_records(world):
    inc, snaps, _ = world
    run_dir = run(world)
    out = evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=snaps)
    t = out["table"]
    assert (t["all"]["n"], t["all"]["top1"], t["all"]["evidence_null"], t["all"]["brier"]) == (2, 2, 2, None)
    assert (t["dev"]["n"], t["pilot"]["n"]) == (1, 1)
    assert json.loads((run_dir / "scores.json").read_text())["table"] == t
    assert "| toplam | 2 | 2/2 (1.0)" in evaluate.markdown_table(t)


def test_cli_refuses_test_set_without_flag(world, capsys):
    inc, snaps, root = world
    assert evaluate.main(["run", "--method", "rule", "--sets", "test", "--root", str(root)]) == 2
    assert "final_test" in capsys.readouterr().err
    assert evaluate.main(["run", "--method", "rule", "--sets", "heldout", "--final-test", "--root", str(root)]) == 2
