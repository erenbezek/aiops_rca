"""`tools/agent_error_analysis.py` (P2c 2. ve 6. madde): soru metni DECISIONS'la aynı, kodla sayılan tuzaklar, seçim ve
özet denetimleri sahte kayıtlarla; gerçek etiket dosyasındaki Eren doğrulaması ve repodaki özetin kayıtlardan aynen
üretilmesi gerçek dev kayıtlarıyla. P2d 2. madde: `--set test` sahte test kayıtlarıyla; boş `TEST_RUNS`."""
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

def _run(d: Path, model: str, cases: dict, set_: str = "dev"):
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"settings": {"model": model}}))
    (d / "tool_outputs").mkdir()
    rows, turns, scores = [], [], []
    for cid, (top1, valid) in cases.items():
        ans = {"candidates": [{"service": "cart"}] * 3} if valid else None
        rows.append({"incident_id": cid, "end_reason": "answer" if valid else "schema_answer", "schema_valid": valid,
                     "answer": ans})
        turns.append({"incident_id": cid, **turn(0, "search_spans", service="cart")})
        scores.append({"incident_id": cid, "set": set_, "top1": top1, "top3": top1,
                       "matched": ["cart"] if valid else []})
        (d / "tool_outputs" / f"{cid}.jsonl").write_text(json.dumps({"turn": 0, "text": "x"}) + "\n")
    (d / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "turns.jsonl").write_text("".join(json.dumps(t) + "\n" for t in turns))
    (d / "scores.json").write_text(json.dumps({"cases": scores}))


def _world(tmp_path, set_):
    ids = [f"inc-{i:08x}" for i in range(4)]
    _run(tmp_path / "g", "gemini-3.5-flash-lite", {ids[0]: (True, True), ids[1]: (False, True), ids[2]: (False, False),
                                                   ids[3]: (True, True)}, set_)
    _run(tmp_path / "q", "qwen3.5-4b", {i: (False, True) for i in ids}, set_)
    runs = {"gemini_file": ("g", "G"), "qwen_file": ("q", "Q")}
    return runs, tmp_path, {i: LABEL for i in ids}


@pytest.fixture
def world(tmp_path):
    return _world(tmp_path, "dev")


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


def _summary(tmp_path, world, doc, monkeypatch, set_="dev"):
    runs, ev, labels = world
    (tmp_path / "results").mkdir(exist_ok=True)
    (tmp_path / ea.FILES[set_][0]).write_text(json.dumps(doc))
    monkeypatch.setattr(ea, "dev_labels", lambda repo: labels)
    monkeypatch.setattr(ea, "set_labels", lambda s, repo: labels if s == "test" else pytest.fail("dev via set_labels"))
    return ea.summary(tmp_path, runs, ev, set_)


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


# --- P2d: --set test (HANDOFF 2026-11-17) ---

def test_files_by_set():
    assert ea.FILES["dev"] == (ea.LABELS_FILE, ea.SUMMARY_MD, ea.SUMMARY_JSON)
    assert [p.as_posix() for p in ea.FILES["test"]] == ["results/p2d_error_labels.json", "results/p2d_error_summary.md",
                                                         "results/p2d_error_summary.json"]


def test_select_and_summary_on_test_set(tmp_path, monkeypatch):
    w = _world(tmp_path, "test")
    runs, ev, labels = w
    rows, info = ea.select(runs, ev, labels, "test")
    assert [r["key"].split()[0] for r in rows] == ["gemini-3.5-flash-lite"] * 2 + ["qwen3.5-4b"] * 4
    dev_rows, dev_info = ea.select(runs, ev, labels, "dev")  # set süzgeci: test satırı dev'e girmez
    assert dev_rows == [] and all(v["n"] == 0 for v in dev_info.values()) and info["qwen3.5-4b"]["n"] == 4
    assert ea.sample(rows) == ea.sample(rows, seed=20261104)  # tohum aynı
    res = _summary(tmp_path, w, _labels_doc(rows), monkeypatch, "test")
    assert res["rows"] == 6 and res["eren_check"]["reading"] == "pending"
    md = ea.summary_markdown(res, "test")
    assert md.startswith("# P2d test hata analizi özeti") and "summary --set test" in md
    assert "results/p2d_error_labels.json" in md and "Kapsam: test," in md


def test_test_runs_empty_until_runs(monkeypatch):
    """Boş `TEST_RUNS` kapısı: koşular girdikten sonra da (P2d 5. madde) boş durumda hata verir."""
    monkeypatch.setattr(ea.ar, "TEST_RUNS", {k: (None, n) for k, (_, n) in ea.ar.TEST_RUNS.items()})
    with pytest.raises(SystemExit, match="TEST_RUNS not filled"):
        ea.select(set_="test")
    with pytest.raises(SystemExit, match="TEST_RUNS not filled"):
        ea.main(["summary", "--set", "test", "--check"])


def _world14(tmp_path):
    """14 ıskalanan satır (7 + 7): tohumlu örneklem 10, örneklem dışı 4."""
    ids = [f"inc-{i:08x}" for i in range(7)]
    _run(tmp_path / "g", "gemini-3.5-flash-lite", {i: (False, True) for i in ids}, "test")
    _run(tmp_path / "q", "qwen3.5-4b", {i: (False, True) for i in ids}, "test")
    return {"gemini_file": ("g", "G"), "qwen_file": ("q", "Q")}, tmp_path, {i: LABEL for i in ids}


def _marks(rows, first_disagree, second_disagree=None):
    """1. tur örneklemin tümü işaretli (ilk `first_disagree` katılmıyorum); 2. tur verilirse örneklem dışı da."""
    first = ea.sample(rows)
    rest = [r["key"] for r in rows if r["key"] not in first]
    marks = {k: {"agree": i >= first_disagree} for i, k in enumerate(first)}
    if second_disagree is not None:
        marks.update({k: {"agree": i >= second_disagree} for i, k in enumerate(rest)})
    return {k: {"eren_check": {**v, "T1": "no", "T6": "no", "T8": "no"}} for k, v in marks.items()}


def test_second_round_only_after_relabel(tmp_path, monkeypatch):
    w = _world14(tmp_path)
    rows, _ = ea.select(*w, "test")
    assert len(rows) == 14 and len(ea.sample(rows)) == 10
    res = _summary(tmp_path, w, _labels_doc(rows, **_marks(rows, 2)), monkeypatch, "test")
    assert res["eren_check"]["reading"] == "ok" and "eren_check_2" not in res
    assert "2. tur" not in ea.summary_markdown(res, "test")
    with pytest.raises(ValueError, match="outside the sample"):  # 1. tur tamam okurken örneklem dışı işaret
        _summary(tmp_path, w, _labels_doc(rows, **_marks(rows, 2, 0)), monkeypatch, "test")


@pytest.mark.parametrize("second, want", [
    (None, {"n": 4, "checked": 0, "disagree": 0, "reading": "pending"}),
    (2, {"n": 4, "checked": 4, "disagree": 2, "reading": "ok"}),
    (3, {"n": 4, "checked": 4, "disagree": 3, "reading": "relabel"}),
])
def test_second_round_reading(tmp_path, monkeypatch, second, want):
    w = _world14(tmp_path)
    rows, _ = ea.select(*w, "test")
    res = _summary(tmp_path, w, _labels_doc(rows, **_marks(rows, 3, second)), monkeypatch, "test")
    assert res["eren_check"] == {"n": 10, "checked": 10, "disagree": 3, "reading": "relabel"}
    assert res["eren_check_2"] == want
    assert f"satırın tümü): işaretlenen {want['checked']}, katılmıyorum {want['disagree']}" in \
        ea.summary_markdown(res, "test")


def test_sample_lists_second_round_on_test(capsys):
    # Gerçek test etiketleri: 1. tur 10 satırda 4 katılmıyorum (Eren 2026-11-17) → 2. tur örneklem dışı 12 satır.
    rows, _ = ea.select(set_="test")
    assert ea.main(["sample", "--set", "test"]) == 0
    out = capsys.readouterr().out.splitlines()
    first = ea.sample(rows)
    assert out[:10] == first and out[10] == "# 2. tur"
    assert sorted(out[11:]) == sorted(r["key"] for r in rows if r["key"] not in first) and len(out[11:]) == 12


# --- gerçek test kayıtları (P2d 6. madde B) ---

def test_eren_check_in_test_labels_file():
    # Eren 2026-11-17 1. tur: 10 satırda 4 katılmıyorum. Dördü de etiketleyicinin soru dışı ölçüt (2. / 3. aday) önerisi;
    # etiket donmuş metne göre ilk hâlinde kaldı (2026-11-18, notlu). Yeniden etiketlemede tek değişiklik: 4B
    # inc-d3869549 T8 evet (Eren'in 1. tur cevabı 'hayır', notlu). 2. tur: örneklem dışı 12 satır, 12'si katılıyorum.
    rows, _ = ea.select(set_="test")
    doc = json.loads((ea.REPO / ea.FILES["test"][0]).read_text(encoding="utf-8"))
    first = ea.sample(rows)
    checked = {x["key"]: x for x in doc["rows"] if "eren_check" in x}
    assert sorted(checked) == sorted(x["key"] for x in doc["rows"]) and len(checked) == 22
    for x in checked.values():
        e = x["eren_check"]
        assert set(e) <= {"agree", "T1", "T6", "T8", "note"} and all(e[t] in ea.VALUES for t in ea.READ)
    g, q = "gemini-3.5-flash-lite", "qwen3.5-4b"
    off = {f"{g} inc-e763eeaf", f"{q} inc-986ae88a", f"{q} inc-a519be4f", f"{q} inc-e4d29c6d"}
    assert {k for k, x in checked.items() if x["eren_check"]["agree"] is False} == off and off <= set(first)
    for k in off:  # etiket ilk hâlinde: Eren'in cevabından tam bir okumada ayrılıyor
        x = checked[k]
        assert sum(x["eren_check"][t] != x[t] for t in ea.READ) == 1 and "soru dışı" in x["eren_check"]["note"]
    fixed = checked[f"{q} inc-d3869549"]
    assert fixed["T8"] == "yes" and fixed["eren_check"]["T8"] == "no" and fixed["eren_check"]["agree"] is True
    for k, x in checked.items():  # öteki satırlarda Eren'in okuması etiketle aynı
        if k not in off | {fixed["key"]}:
            assert x["eren_check"]["agree"] is True and all(x["eren_check"][t] == x[t] for t in ea.READ)
    res = ea.summary(set_="test")
    assert res["eren_check"] == {"n": 10, "checked": 10, "disagree": 4, "reading": "relabel"}
    assert res["eren_check_2"] == {"n": 12, "checked": 12, "disagree": 0, "reading": "ok"}


def test_test_summary_files_match_records():
    # CI: test özeti repodaki kayıtlardan yeniden üretilir, repodaki dosyalarla bayt aynı olmalı.
    md, js = ea.summary_render(set_="test")
    _, md_path, js_path = ea.FILES["test"]
    assert (ea.REPO / md_path).read_text(encoding="utf-8") == md
    assert (ea.REPO / js_path).read_text(encoding="utf-8") == js
    assert ea.main(["summary", "--set", "test", "--check"]) == 0


# --- gerçek dev kayıtları ---

def test_eren_check_in_labels_file():
    # Eren 2026-11-16 (P2c 6. madde): 10 satırın 10'u katılıyor → yeniden etiketleme yok. 4B inc-320c56f9'da önce
    # T1 evet dedi, geri aldı ("sıçrama" bir miktar artış varsa uydurma değil); işareti katılıyor.
    doc = json.loads((ea.REPO / ea.LABELS_FILE).read_text(encoding="utf-8"))
    checked = {x["key"]: x for x in doc["rows"] if "eren_check" in x}
    assert sorted(checked) == ea.sample(ea.select()[0])
    for x in checked.values():
        e = x["eren_check"]
        assert set(e) <= {"agree", "T1", "T6", "T8", "note"} and all(e[t] in ea.VALUES for t in ("T1", "T6", "T8"))
        assert e["agree"] == all(e[t] == x[t] for t in ("T1", "T6", "T8"))
    assert [k for k, x in checked.items() if "note" in x["eren_check"]] == ["qwen3.5-4b inc-320c56f9"]
    assert ea.summary()["eren_check"] == {"n": 10, "checked": 10, "disagree": 0, "reading": "ok"}


def test_summary_files_match_records():
    # CI: özet repodaki kayıtlardan yeniden üretilir, repodaki dosyalarla bayt aynı olmalı.
    md, js = ea.summary_render()
    assert (ea.REPO / ea.SUMMARY_MD).read_text(encoding="utf-8") == md
    assert (ea.REPO / ea.SUMMARY_JSON).read_text(encoding="utf-8") == js
    assert ea.main(["summary", "--check"]) == 0
