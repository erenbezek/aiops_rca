"""`tools/agent_report.py --report p2c_dev` (P2c 2. madde): işaret testi, eşleştirme, yeniden deneme beklemesi ve
raporun sahte dev koşularıyla kurulması (gerçek dev koşusu henüz yok)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import agent_report as ar  # noqa: E402

CASES = [f"inc-{i:08x}" for i in range(18)]


@pytest.mark.parametrize("b, c, p", [(0, 0, 1.0), (3, 3, 1.0), (6, 0, 0.03125), (0, 6, 0.03125), (5, 0, 0.0625),
                                     (8, 1, 0.0390625), (7, 1, 0.0703125), (10, 2, 0.0385742), (9, 2, 0.0654297)])
def test_sign_test(b, c, p):
    assert ar.sign_test(b, c) == pytest.approx(p, abs=1e-6)


def test_sign_test_thresholds_match_decision():
    """DECISIONS 2026-11-14: pratikte 6'ya 0, 8'e 1, 10'a 2 gerekir (7'ye 1 yetmez)."""
    assert ar.sign_test(6, 0) < ar.ALPHA and ar.sign_test(8, 1) < ar.ALPHA and ar.sign_test(10, 2) < ar.ALPHA
    assert ar.sign_test(7, 1) >= ar.ALPHA and ar.sign_test(5, 0) >= ar.ALPHA and ar.sign_test(9, 2) >= ar.ALPHA


def test_paired_reading_and_direction():
    left = {k: i < 8 for i, k in enumerate(CASES)}
    right = {k: i == 17 for i, k in enumerate(CASES)}
    p = ar.paired(left, right, "ajan", "ham")
    assert (p["only_left"], p["only_right"], p["reading"]) == (8, 1, "fark: ajan lehine")
    p = ar.paired(right, left, "ajan", "ham")
    assert p["reading"] == "fark: ham lehine"
    p = ar.paired({**left, CASES[7]: False}, right, "a", "b")
    assert p["reading"] == "ayırt edilemedi"
    with pytest.raises(ValueError):
        ar.paired(left, {k: True for k in CASES[:-1]}, "a", "b")


@pytest.mark.parametrize("provider, n, wait", [("gemini", 1, 0), ("gemini", 2, 30), ("gemini", 3, 90),
                                               ("gemini", 4, 210), ("local", 1, 0), ("local", 2, 30), ("groq", 2, 65)])
def test_retry_wait_by_provider(provider, n, wait):
    assert ar.retry_wait_s(provider, n) == wait


# --- sahte dev koşuları ---

def _write_run(d: Path, model: str, store: str, known: dict[str, tuple[bool, bool]], attempts=None, sets=("dev",)):
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"settings": {"model": model, "store": store, "prompt_sha256": "p"},
                                            "repo_commit": "c", "sets": list(sets)}))
    rows, turns, cases = [], [], []
    for cid, (t1, t3) in known.items():
        att = (attempts or {}).get(cid, [{"status": 200}])
        failed = att[-1]["status"] != 200
        rows.append({"incident_id": cid, "end_reason": "no_answer" if failed else "answer", "schema_valid": not failed,
                     "n_tool_calls": 1, "n_requests": 2, "tokens": {"input": 10, "output": 2}, "duration_s": 3.0})
        turns += [{"incident_id": cid, "turn": 0, "kind": "action", "input_tokens_local": 100, "dropped": [],
                   "call": "list_services()", "attempts": [{"status": 200}], "error": None},
                  {"incident_id": cid, "turn": 1, "kind": "answer", "input_tokens_local": 200, "dropped": [],
                   "attempts": att, "error": "busy" if failed else None}]
        cases.append({"incident_id": cid, "set": "dev", "top1": t1, "top3": t3})
    tab = {"n": len(known), "top1": sum(v[0] for v in known.values()), "top3": sum(v[1] for v in known.values()),
           "schema_invalid": 0, "no_answer": 0, "evidence_valid": 0, "brier": None, "duration_s_total": 1.0,
           "tokens_input": 1, "tokens_output": 1}
    (d / "scores.json").write_text(json.dumps({"table": {"dev": tab, "all": tab}, "cases": cases}))
    (d / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "turns.jsonl").write_text("".join(json.dumps(t) + "\n" for t in turns))


@pytest.fixture
def world(tmp_path):
    ev = tmp_path / "eval_responses"
    g, q = "gemini-3.5-flash-lite", "qwen3.5-4b"
    all_ = lambda t1, t3: {k: (t1(i), t3(i)) for i, k in enumerate(CASES)}  # noqa: E731
    _write_run(ev / "gf1", g, "FileStore", all_(lambda i: i < 9, lambda i: i < 14),
               attempts={CASES[0]: [{"status": 503}, {"status": 200}],
                         CASES[17]: [{"status": 503}] * 4})
    _write_run(ev / "gf2", g, "FileStore", all_(lambda i: i < 9, lambda i: i < 12))
    live = {k: v for k, v in all_(lambda i: i < 9, lambda i: i < 6).items() if k != CASES[5]}  # bir vaka oynatılamadı
    _write_run(ev / "gl", g, "LiveStore", live)
    _write_run(ev / "qf", q, "FileStore", all_(lambda i: i < 3, lambda i: i < 7))
    _write_run(ev / "ql", q, "LiveStore", all_(lambda i: i < 3, lambda i: i < 7))
    # P1 dev koşuları (kural / BARO: pilot + dev; burada yalnız dev satırları okunur)
    p1 = {"rule": all_(lambda i: i < 10, lambda i: i < 15), "baro": all_(lambda i: False, lambda i: i < 4),
          "narrowing": all_(lambda i: True, lambda i: True)}
    for m in (g, q):
        p1[f"{m}-raw"] = all_(lambda i: i < 2, lambda i: i < 7)
        p1[f"{m}-summary"] = all_(lambda i: i < 8, lambda i: i < 16)
        p1[f"{m}-narrowed"] = all_(lambda i: i < 9, lambda i: True)
    rows = []
    for name, known in p1.items():
        _write_run(ev / f"p1-{name}", "x", "-", known)
        method, model, level = (name, None, None) if "-" not in name else ("llm", *name.rsplit("-", 1))
        rows.append({"method": method, "model": model, "level": level, "info": False,
                     "runs": {"dev": f"eval_responses/p1-{name}", "test": "eval_responses/DO-NOT-READ"}})
    rows.append({"method": "llm", "model": "qwen3.5-9b", "level": "raw", "info": True,
                 "runs": {"dev": "eval_responses/DO-NOT-READ"}})
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "p1_runs.json").write_text(json.dumps({"note": "", "rows": rows}))
    calls = {"runs": [
        {"model": g, "live": {"dir": "gl"}, "file": None, "totals": {"cases": 17, "calls": 40, "same": 38,
                                                                     "zero_duration": 1, "unexplained": 1},
         "cases": {CASES[3]: {"diffs": [{"turn": 2, "call": "get_trace(...)", "class": "unexplained",
                                         "diagnosis": "error_tag"}]},
                   CASES[4]: {"diffs": [{"turn": 1, "call": "search_spans()", "class": "zero_duration",
                                         "diagnosis": "zero_duration"}]}}},
        {"model": q, "live": {"dir": "ql"}, "file": {"dir": "qf"},
         "totals": {"cases": 18, "calls": 50, "same": 50,
                    "divergence": {"cases_paired": 18, "model_diverged": 1, "output_differs": 2, "identical": 15}},
         "cases": {}, "divergence": {CASES[2]: {"model_diverged": True}, CASES[1]: {"model_diverged": False}}}]}
    cp = tmp_path / "results" / "p2c_dev_calls.json"
    cp.write_text(json.dumps(calls))
    runs = {"gemini_file": ("gf1", "G1"), "gemini_file_2": ("gf2", "G2"), "qwen_file": ("qf", "QF"),
            "gemini_live": ("gl", "GL"), "qwen_live": ("ql", "QL")}
    return {"runs": runs, "eval_dir": ev, "calls_path": cp, "p1_runs": tmp_path / "results" / "p1_runs.json"}


def test_build_p2c_dev(world):
    rep = ar.build_p2c_dev(**world)
    g = rep["models"]["gemini-3.5-flash-lite"]
    f = g["file_vs_live_top3"]
    assert f["n"] == 17 and f["not_replayed"] == [CASES[5]]
    assert (f["only_left"], f["only_right"]) == (8, 0) and f["reading"] == "fark: dosya lehine"  # 6..13
    assert g["call_level"]["unexplained"] == [{"incident_id": CASES[3], "turn": 2, "call": "get_trace(...)",
                                               "class": "unexplained", "diagnosis": "error_tag"}]
    a = g["agent_vs_p1"]
    assert (a["raw_top3"]["only_left"], a["raw_top3"]["only_right"]) == (7, 0)
    assert a["raw_top3"]["reading"] == "fark: ajan lehine"
    assert (a["narrowed_top1"]["left"], a["narrowed_top1"]["right"]) == (9, 9)
    assert a["narrowed_top1"]["reading"] == "ayırt edilemedi"
    assert set(g["p1_rows"]) == {"rule", "baro", "narrowing", "raw", "summary", "narrowed"}
    q = rep["models"]["qwen3.5-4b"]
    assert q["call_level"]["model_diverged"] == [CASES[2]]
    assert q["file_vs_live_top3"]["reading"] == "ayırt edilemedi" and q["file_vs_live_top3"]["p"] == 1.0
    assert rep["noise_floor"] == {"file_vs_file_differ": 2, "file_vs_live_differ": 8, "n_file": 18, "n_live": 17}
    r = rep["runs"]["gemini_file"]["retry"]
    assert r == {"requests_retried": 2, "retries": 4, "retry_wait_s": 30 + 210, "transport_no_answer": 1}
    assert rep["runs"]["qwen_file"]["retry"]["retry_wait_s"] == 0
    md = ar.render_p2c_dev(rep)
    assert "açıklanamayan 1" in md and "fark: ajan lehine" in md and "DO-NOT-READ" not in md
    assert "Oynatılamadı (çiftten düştü)" in md and "(iyimser)" not in md


def test_build_p2c_dev_requires_runs():
    with pytest.raises(SystemExit):
        ar.build_p2c_dev()
