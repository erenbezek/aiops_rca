"""`tools/agent_report.py --report p2c_dev` (P2c 2. madde): işaret testi, eşleştirme, yeniden deneme beklemesi ve
raporun sahte dev koşularıyla kurulması; `--report p2d` (P2d 2. madde) sahte test koşularıyla: yalnız toplamlar, dev–test
okuması, boş `TEST_RUNS`."""
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

def _write_run(d: Path, model: str, store: str, known: dict[str, tuple[bool, bool]], attempts=None, sets=("dev",),
               set_="dev"):
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
        cases.append({"incident_id": cid, "set": set_, "top1": t1, "top3": t3})
    tab = {"n": len(known), "top1": sum(v[0] for v in known.values()), "top3": sum(v[1] for v in known.values()),
           "schema_invalid": 0, "no_answer": 0, "evidence_valid": 0, "brier": None, "duration_s_total": 1.0,
           "tokens_input": 1, "tokens_output": 1}
    (d / "scores.json").write_text(json.dumps({"table": {set_: tab, "all": tab}, "cases": cases}))
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
    with pytest.raises(SystemExit, match="DEV_RUNS not filled"):
        ar.build_p2c_dev({**ar.DEV_RUNS, "qwen_live": (None, "qwen3.5-4b, canlı")})


def test_dev_runs_filled_and_interrupted_listed():
    """5. madde: beş koşu dolu ve `eval_responses/`'te; iki teknik kesinti raporda listelenir."""
    assert all(d and (ar.EVAL / d / "scores.json").exists() for d, _ in ar.DEV_RUNS.values())
    rep = ar.build_p2c_dev()
    assert [i["cases"] for i in rep["interrupted"]] == [5, 2]
    md = ar.render_p2c_dev(rep)
    assert "**Teknik kesinti:** 2" in md and all(g in md for g, *_ in ar.DEV_INTERRUPTED)


def test_p1_dev_rows_model_filter(tmp_path):
    """Her model yalnız kendi ham / özet / daraltma satırını alır; ortak satırlar (kural, BARO, daraltma referansı)
    ikisinde de aynı; bilgi satırı (9B) ve test yolu okunmaz."""
    rows = [{"method": m, "model": None, "level": None, "info": False, "runs": {"dev": f"e/{m}", "test": "e/T"}}
            for m in ("rule", "baro", "narrowing")]
    for model in ("gemini-3.5-flash-lite", "qwen3.5-4b"):
        for level in ("raw", "summary", "narrowed"):
            rows.append({"method": "llm", "model": model, "level": level, "info": False,
                         "runs": {"dev": f"e/{model}-{level}", "test": "e/T"}})
    rows.append({"method": "llm", "model": "qwen3.5-9b", "level": "raw", "info": True, "runs": {"dev": "e/9b"}})
    (tmp_path / "results").mkdir()
    p = tmp_path / "results" / "p1_runs.json"
    p.write_text(json.dumps({"note": "", "rows": rows}))
    for model in ("gemini-3.5-flash-lite", "qwen3.5-4b"):
        got = {k: v.name for k, v in ar.p1_dev_rows(p, model).items()}
        assert got == {"rule": "rule", "baro": "baro", "narrowing": "narrowing", "raw": f"{model}-raw",
                       "summary": f"{model}-summary", "narrowed": f"{model}-narrowed"}


# --- P2d: sahte test koşuları (dev koşuları `world`'deki) ---

TCASES = [f"inc-{i + 100:08x}" for i in range(18)]


@pytest.fixture
def test_world(world, tmp_path):
    ev = world["eval_dir"]
    g, q = "gemini-3.5-flash-lite", "qwen3.5-4b"
    all_ = lambda t1, t3: {k: (t1(i), t3(i)) for i, k in enumerate(TCASES)}  # noqa: E731
    w = lambda name, model, store, known: _write_run(ev / name, model, store, known, sets=("test",),  # noqa: E731
                                                     set_="test")
    w("tgf1", g, "FileStore", all_(lambda i: i < 5, lambda i: i < 6))
    w("tgf2", g, "FileStore", all_(lambda i: i < 5, lambda i: i < 7))
    w("tgl", g, "LiveStore", {k: v for k, v in all_(lambda i: i < 5, lambda i: i < 6).items() if k != TCASES[9]})
    w("tqf", q, "FileStore", all_(lambda i: i < 3, lambda i: i < 9))
    w("tql", q, "LiveStore", all_(lambda i: i < 3, lambda i: i < 9))
    spec = json.loads(world["p1_runs"].read_text())
    p1 = {"rule": all_(lambda i: i < 4, lambda i: i < 8), "baro": all_(lambda i: False, lambda i: i < 2),
          "narrowing": all_(lambda i: True, lambda i: True)}
    for m in (g, q, "gpt-oss-120b"):
        for lv, f in (("raw", lambda i: i < 6), ("summary", lambda i: i < 6), ("narrowed", lambda i: i < 12)):
            p1[f"{m}-{lv}"] = all_(f, f)
    for name, known in p1.items():
        w(f"tp1-{name}", "x", "-", known)
    for m in ("gpt-oss-120b",):
        for lv in ("raw", "summary", "narrowed"):
            _write_run(ev / f"p1-{m}-{lv}", "x", "-", {k: (False, False) for k in CASES})
            spec["rows"].append({"method": "llm", "model": m, "level": lv, "info": False,
                                 "runs": {"dev": f"eval_responses/p1-{m}-{lv}"}})
    for r in spec["rows"]:
        name = r["method"] if r["method"] != "llm" else f"{r['model']}-{r['level']}"
        if r["model"] == "qwen3.5-9b":
            _write_run(ev / "p1-9b", "x", "-", {k: (True, True) for k in CASES})
            w("tp1-9b", "x", "-", all_(lambda i: True, lambda i: True))
            r["runs"] = {"dev": "eval_responses/p1-9b", "test": "eval_responses/tp1-9b"}
        else:
            r["runs"]["test"] = f"eval_responses/tp1-{name}"
    world["p1_runs"].write_text(json.dumps(spec))
    calls = {"runs": [
        {"model": g, "live": {"dir": "tgl"}, "file": None, "totals": {"cases": 17, "calls": 40, "same": 39,
                                                                      "unexplained": 1},
         "cases": {TCASES[3]: {"diffs": [{"turn": 2, "call": "get_trace(SECRET)", "class": "unexplained",
                                          "diagnosis": None}]}}},
        {"model": q, "live": {"dir": "tql"}, "file": {"dir": "tqf"},
         "totals": {"cases": 18, "calls": 50, "same": 50,
                    "divergence": {"cases_paired": 18, "model_diverged": 1, "output_differs": 0, "identical": 17}},
         "cases": {}, "divergence": {TCASES[2]: {"model_diverged": True}}}]}
    cp = world["calls_path"].parent / "p2d_test_calls.json"
    cp.write_text(json.dumps(calls))
    runs = {"gemini_file": ("tgf1", "G1"), "gemini_file_2": ("tgf2", "G2"), "qwen_file": ("tqf", "QF"),
            "gemini_live": ("tgl", "GL"), "qwen_live": ("tql", "QL")}
    return {"runs": runs, "eval_dir": ev, "calls_path": cp, "p1_runs": world["p1_runs"], "dev_runs": world["runs"]}


def test_build_p2d(test_world):
    rep = ar.build_p2d(**test_world)
    g, q = rep["models"]["gemini-3.5-flash-lite"], rep["models"]["qwen3.5-4b"]
    assert g["dev_test_reading"] == {"dev_top3": 14, "test_top3": 6, "n_dev": 18, "n_test": 18, "p": 0.0176,
                                     "reading": "down"}
    assert q["dev_test_reading"]["reading"] == "none" and q["dev_test_reading"]["dev_top3"] == 7
    assert g["call_level"]["totals"]["unexplained"] == 1 and "unexplained" not in g["call_level"]
    assert "model_diverged" not in q["call_level"] and q["call_level"]["totals"]["divergence"]["model_diverged"] == 1
    assert g["file_vs_live_top3"]["not_replayed"] == 1 and g["file_vs_live_top3"]["n"] == 17
    assert set(g["agent_rows"]) == {"gemini_file", "gemini_file_2", "gemini_live"}
    assert set(q["agent_rows"]) == {"qwen_file", "qwen_live"}
    assert g["agent_rows"]["gemini_file"]["dev"]["top3"] == 14 and g["agent_rows"]["gemini_file"]["test"]["top3"] == 6
    assert g["p1_rows"]["raw"]["dev"]["run"] == "p1-gemini-3.5-flash-lite-raw"
    assert g["p1_rows"]["raw"]["test"]["run"] == "tp1-gemini-3.5-flash-lite-raw"
    assert sorted(rep["p1_info"]) == ["gpt-oss-120b narrowed", "gpt-oss-120b raw", "gpt-oss-120b summary",
                                      "qwen3.5-9b raw"]
    assert all("cases" not in s for s in rep["runs"].values())
    a = g["agent_vs_p1"]["raw_top3"]
    assert (a["left"], a["right"], a["only_left"], a["only_right"]) == (6, 6, 0, 0)


def test_p2d_has_no_case_ids(test_world):
    """Planlama kontrolü 2026-11-17 şart 3: test raporunda (JSON ve md) vaka kimliği ve çağrı ayrıntısı yok."""
    rep = ar.build_p2d(**test_world)
    text = json.dumps(rep, ensure_ascii=False) + ar.render_p2d(rep)
    assert not [c for c in TCASES + CASES if c in text]
    assert "inc-" not in text and "SECRET" not in text and "get_trace" not in text


def test_render_p2d(test_world):
    md = ar.render_p2d(ar.build_p2d(**test_world))
    assert "## Vakalar" not in md and "Oynatılamadı (çiftten düştü): 1 vaka." in md
    assert "fark (düşüş)" in md and "**açıklanamayan 1**" in md and "(bilgi)" in md
    assert "dev 14 / 18, test 6 / 18; p = 0.0176" in md


def test_p2d_power_matches_card():
    """P2d kartı (önceden yazılı güç): Gemini dev 14 → test ≤ 7; 4B dev 9 → test ≤ 2 ya da ≥ 16."""
    assert ar._reach(14, 18, 18) == "≤ 7" and ar._reach(9, 18, 18) == "≤ 2 ya da ≥ 16"


def test_p2d_requires_test_runs():
    """Planlama kontrolü 2026-11-17 şart 4: koşular girene kadar `TEST_RUNS` boş ve rapor üretilmez (CI bu boş durumu
    sınar; koşular girince yerini bayt aynı denetimi alır)."""
    assert all(d is None for d, _ in ar.TEST_RUNS.values()) and set(ar.TEST_RUNS) == set(ar.DEV_RUNS)
    assert ar.TEST_INTERRUPTED == []
    with pytest.raises(SystemExit, match="TEST_RUNS not filled"):
        ar.main(["--report", "p2d", "--check"])
