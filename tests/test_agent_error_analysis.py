"""`tools/agent_error_analysis.py` (P2c 2. madde): soru metni DECISIONS'la aynı, kodla sayılan tuzaklar, seçim ve
özet denetimleri; sahte kayıtlarla (gerçek dev koşusu henüz yok)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import agent_error_analysis as ea  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
LABEL = {"answer": {"root_cause_service": "payment", "propagation_path": [["payment", "checkout"],
                                                                          ["checkout", "frontend"]]}}


def test_questions_verbatim_from_decisions():
    rows = [line for line in (REPO / "docs" / "DECISIONS.md").read_text(encoding="utf-8").splitlines()
            if "P2 hata analizi: 12 tuzağın ajana uyarlanmış soruları" in line]
    assert len(rows) == 1 and rows[0].split(" | ")[1].strip() == ea.QUESTIONS
    assert ea.questions_sha256() == "b887cbbb9a7a199b1cd1aee6c3efcee68573b09f753152283a677d86f2e07cbd"


@pytest.mark.parametrize("tool, args, kind", [
    ("search_spans", {}, "trace"), ("get_trace", {}, "trace"), ("service_dependencies", {}, "trace"),
    ("metric_series", {"metric": "p95_ms"}, "trace"), ("metric_series", {"metric": "error_rate"}, "trace"),
    ("metric_series", {"metric": "cpu_pct"}, "metric"), ("metric_series", {"metric": None}, None),
    ("search_logs", {}, "log"), ("list_services", {}, None)])
def test_kind_of(tool, args, kind):
    assert ea.kind_of(tool, args) == kind


def turn(i, tool=None, call=None, dropped=(), tool_error=False, **args):
    t = {"turn": i, "kind": "action", "dropped": list(dropped), "action": {"args": args}}
    if tool:
        t.update(tool=tool, call=call or f"{tool}({sorted(args.items())})", tool_error=tool_error)
    return t


ROW = {"end_reason": "answer"}


def test_coded_basic_no():
    ts = [turn(0, "list_services"), turn(1, "search_spans", service="payment"),
          turn(2, "metric_series", service="payment", metric="cpu_pct"), turn(3, "search_logs", service="cart")]
    c = ea.coded(ts, [{"text": "payment: x"}], ROW, "payment", "payment", LABEL)
    assert c == {"T2": "no", "T2_root_in_outputs": True, "T3": "no", "T4": "no", "T5": "no", "T7": "no",
                 "T9": "no", "T11": "no", "T12": "no"}


def test_coded_basic_yes():
    ts = [turn(0, "search_spans", call="a", service="checkout"), turn(1, "search_spans", call="a", service="checkout"),
          turn(2, "search_spans", call="b", dropped=[0], tool_error=True)]
    c = ea.coded(ts, [{"text": "checkout"}], {"end_reason": "step_limit"}, "checkout", "checkout", LABEL)
    assert c["T2"] == "yes" and c["T2_root_in_outputs"] is False and c["T3"] == "yes"
    assert c["T4"] == "yes" and c["T5"] == "yes" and c["T7"] == "yes" and c["T9"] == "yes"
    assert c["T11"] == "yes" and c["T12"] == "yes"


def test_coded_end_reasons_and_no_answer():
    c = ea.coded([], [], {"end_reason": "schema_action"}, None, None, LABEL)
    assert c["T4"] == "yes" and c["T7"] == "undetermined" and c["T3"] == "undetermined" and c["T5"] == "yes"
    assert ea.coded([], [], {"end_reason": "budget"}, None, None, LABEL)["T11"] == "yes"


def test_t7_counts_only_first_candidate_calls():
    ts = [turn(0, "search_spans", service="cart"), turn(1, "metric_series", service="cart", metric="cpu_pct"),
          turn(2, "search_logs", service="payment")]
    assert ea.coded(ts, [], ROW, "cart", "cart", LABEL)["T7"] == "no"
    assert ea.coded(ts, [], ROW, "payment", "payment", LABEL)["T7"] == "yes"


# --- seçim ve özet, sahte koşularla ---

def _run(d: Path, model: str, cases: dict):
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"settings": {"model": model}}))
    (d / "tool_outputs").mkdir()
    rows, turns, scores = [], [], []
    for cid, (top1, valid) in cases.items():
        ans = {"candidates": [{"service": "cart"}] * 3} if valid else None
        rows.append({"incident_id": cid, "end_reason": "answer" if valid else "schema_answer", "schema_valid": valid,
                     "answer": ans})
        turns.append({"incident_id": cid, **turn(0, "search_spans", service="cart")})
        scores.append({"incident_id": cid, "set": "dev", "top1": top1, "top3": top1,
                       "matched": ["cart"] if valid else []})
        (d / "tool_outputs" / f"{cid}.jsonl").write_text(json.dumps({"turn": 0, "text": "x"}) + "\n")
    (d / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "turns.jsonl").write_text("".join(json.dumps(t) + "\n" for t in turns))
    (d / "scores.json").write_text(json.dumps({"cases": scores}))


@pytest.fixture
def world(tmp_path):
    ids = [f"inc-{i:08x}" for i in range(4)]
    _run(tmp_path / "g", "gemini-3.5-flash-lite", {ids[0]: (True, True), ids[1]: (False, True), ids[2]: (False, False),
                                                   ids[3]: (True, True)})
    _run(tmp_path / "q", "qwen3.5-4b", {i: (False, True) for i in ids})
    runs = {"gemini_file": ("g", "G"), "qwen_file": ("q", "Q")}
    return runs, tmp_path, {i: LABEL for i in ids}


def test_select_scope(world):
    runs, ev, labels = world
    rows, info = ea.select(runs, ev, labels)
    assert [r["key"].split()[0] for r in rows] == ["gemini-3.5-flash-lite"] * 2 + ["qwen3.5-4b"] * 4
    assert info["gemini-3.5-flash-lite"]["n"] == 4 and info["qwen3.5-4b"]["T2"]["yes"] == 4
    bad = next(r for r in rows if not r["valid_answer"])
    assert bad["T7"] == "undetermined" and bad["first_candidate"] is None


def _labels_doc(rows, **override):
    out = []
    for r in rows:
        x = {"key": r["key"], "model": r["model"], **{t: r[t] for t in ea.CODED}, "T8": "no",
             "T1": "no" if r["valid_answer"] else "undetermined", "T6": "no" if r["valid_answer"] else "undetermined"}
        out.append({**x, **override.get(r["key"], {})})
    return {"questions": ea.QUESTIONS, "questions_sha256": ea.questions_sha256(), "rows": out}


def _summary(tmp_path, world, doc, monkeypatch):
    runs, ev, labels = world
    (tmp_path / "results").mkdir(exist_ok=True)
    (tmp_path / ea.LABELS_FILE).write_text(json.dumps(doc))
    monkeypatch.setattr(ea, "dev_labels", lambda repo: labels)
    return ea.summary(tmp_path, runs, ev)


def test_summary_counts_and_checks(tmp_path, world, monkeypatch):
    rows, _ = ea.select(*world)
    res = _summary(tmp_path, world, _labels_doc(rows), monkeypatch)
    assert res["rows"] == 6 and res["traps"]["all"]["n"] == 6 and res["traps"]["all"]["T1"]["undetermined"] == 1
    assert res["eren_check"] == {"n": 6, "checked": 0, "disagree": 0, "reading": "pending"}
    assert "T10 uygulanamaz" in ea.summary_markdown(res)


@pytest.mark.parametrize("change, msg", [
    ({"T2": "no"}, "coded traps differ"),
    ({"T1": "yes"}, "undetermined without a valid answer"),
])
def test_summary_rejects_wrong_labels(tmp_path, world, monkeypatch, change, msg):
    rows, _ = ea.select(*world)
    bad = next(r for r in rows if not r["valid_answer"])
    with pytest.raises(ValueError, match=msg):
        _summary(tmp_path, world, _labels_doc(rows, **{bad["key"]: change}), monkeypatch)


def test_summary_rejects_changed_questions(tmp_path, world, monkeypatch):
    rows, _ = ea.select(*world)
    doc = _labels_doc(rows)
    doc["questions"] = doc["questions"] + " "
    with pytest.raises(ValueError, match="questions"):
        _summary(tmp_path, world, doc, monkeypatch)
