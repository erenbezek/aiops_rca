"""P1 sonuç tablosu (DECISIONS 2026-11-04 "P1e sonuç tablosu repoda", "P1e dev–test okuması", 2026-11-03 9B bilgi
satırı): Fisher bilinen değerlerle ve karardaki eşiklerle, 9B okuması, satır denetimi, gruplar, repodaki tablo dosyalarının
kayıtlardan bayt aynı yeniden üretilmesi."""
import json

import pytest

from aiops_rca import results
from aiops_rca.cases import INCIDENTS, REPO, _labels


def p(*args):
    num, den = results.fisher(*args)
    return num / den


def test_fisher_known_values():
    # Fisher'ın çay deneyi: 4 fincanın 3'ü / 4'ün 1'i → iki yönlü p = 34/70.
    assert results.fisher(3, 4, 1, 4) == (34, 70)
    # Ders kitabı örneği (diyet: 10 erkekte 1, 14 kadında 11): iki yönlü p ≈ 0,002759.
    assert p(1, 10, 11, 14) == pytest.approx(0.002759, abs=5e-7)
    assert results.fisher(9, 18, 9, 18) == (results.comb(36, 18), results.comb(36, 18))  # aynı oran: p = 1


@pytest.mark.parametrize("dev,test_max", [(18, 13), (17, 11), (16, 9), (15, 8)])
def test_dev_test_thresholds_from_decision(dev, test_max):
    # DECISIONS 2026-11-04: dev 18 → test ≤ 13; 17 → ≤ 11; 16 → ≤ 9; 15 → ≤ 8 "fark".
    assert results.dev_test_reading(dev, 18, test_max, 18)["reading"] == "down"
    assert results.dev_test_reading(dev, 18, test_max + 1, 18)["reading"] == "none"
    assert results.dev_test_reading(test_max, 18, dev, 18)["reading"] == "up"


def test_reading_9b_rule():
    assert results.reading_9b(6, 0) == "9b" and results.reading_9b(0, 6) == "4b"
    assert results.reading_9b(5, 0) == "none" and results.reading_9b(6, 1) == "none" and results.reading_9b(0, 0) == "none"


def run_meta(method="llm", model="qwen3.5-4b", level="narrowed", alias=False, sets=("dev",)):
    return {"method": method, "sets": list(sets), "settings": {"model": model, "level": level, "alias": alias}}


def test_check_run_catches_mismatches():
    row = {"method": "llm", "model": "qwen3.5-4b", "level": "narrowed"}
    scores = {"cases": [{"incident_id": "a", "set": "dev"}, {"incident_id": "b", "set": "dev"}]}
    assert results.check_run(row, "dev", run_meta(), scores, {"a", "b"}) == []
    assert results.check_run(row, "dev", run_meta(level="raw"), scores, {"a", "b"})
    assert results.check_run(row, "dev", run_meta(model="qwen3.5-9b"), scores, {"a", "b"})
    assert results.check_run(row, "dev", run_meta(alias=True), scores, {"a", "b"})
    assert results.check_run(row, "dev", run_meta(method="rule"), scores, {"a", "b"})
    assert results.check_run(row, "test", run_meta(), scores, {"a", "b"})                 # set koşuda yok
    assert results.check_run(row, "dev", run_meta(), scores, {"a", "b", "c"})             # eksik vaka
    dup = {"cases": scores["cases"] + [{"incident_id": "a", "set": "dev"}]}
    assert results.check_run(row, "dev", run_meta(), dup, {"a", "b"})                     # aynı vaka iki kez


def test_dev_groups_are_11_demo_7_own():
    groups = [results.group_of(d) for d in _labels(("dev",), INCIDENTS)]
    assert (groups.count("demo"), groups.count("own")) == (11, 7)


def test_runs_file_rows():
    spec = json.loads((REPO / "results" / "p1_runs.json").read_text(encoding="utf-8"))
    ids = [results.row_id(r) for r in spec["rows"]]
    llm = [f"{m} {lv}" for m in ("qwen3.5-4b", "gpt-oss-120b", "gemini-3.5-flash-lite", "qwen3.5-9b")
           for lv in ("raw", "summary", "narrowed")]
    assert ids == ["rule", "baro", "narrowing"] + llm
    assert [r["id"] for r in results.build()["rows"] if r["info"]] == llm[-3:]


def test_table_files_match_records():
    # CI: tablo repodaki kayıtlardan yeniden üretilir, repodaki dosyalarla bayt aynı olmalı.
    md, js = results.render()
    assert (REPO / "results" / "p1_table.md").read_text(encoding="utf-8") == md
    assert (REPO / "results" / "p1_table.json").read_text(encoding="utf-8") == js
    assert results.main(["--check"]) == 0


# --- test yolu (planlama 2026-11-04): sahte, test biçimli küçük repo ---

def score_row(iid, set_, top1, top3):
    return {"incident_id": iid, "set": set_, "input_status": "ok", "no_answer": False, "schema_valid": True,
            "top1": top1, "top3": top3, "matched": [], "unmatched": [], "evidence_valid": None, "evidence_edges": [],
            "label_path_overlap": None, "confidence": 0.5, "unsure": False, "duration_s": 1.0, "tokens": None}


def fake_repo(tmp_path, top3_9b_test, top3_4b_test=range(13)):
    """dev 18 (7 kendi, 11 demo), test 18 (5 kendi, 13 demo). 4B daraltma: dev top-3 18, top-1 9; test top-3
    `top3_4b_test` (varsayılan `inc-test-00`..`12`), top-1 9. 9B daraltma: dev aynı; test top-3 `top3_9b_test`.
    Kural yalnız dev."""
    inc = tmp_path / "incidents"
    inc.mkdir()
    ids = {"dev": [f"inc-dev-{i:02}" for i in range(18)], "test": [f"inc-test-{i:02}" for i in range(18)]}
    own = {"dev": 7, "test": 5}
    for s, lst in ids.items():
        for i, iid in enumerate(lst):
            scen = ("quoteGatewayDelay" if i % 2 else "networkDelay") if i < own[s] else "adFailure"
            (inc / f"{iid}.json").write_text(json.dumps({"incident_id": iid, "set": s, "valid": True,
                                                         "answer": {"scenario": scen}}))

    def run(name, method, model, level, rows):
        d = tmp_path / "eval_responses" / name
        d.mkdir(parents=True)
        sets = sorted({r["set"] for r in rows})
        (d / "run.json").write_text(json.dumps({"method": method, "sets": sets,
                                                "settings": {"model": model, "level": level} if model else {}}))
        (d / "scores.json").write_text(json.dumps({"cases": rows}))
        return f"eval_responses/{name}"

    def rows(s, top1_n, top3_ids):
        return [score_row(iid, s, i < top1_n, iid in top3_ids) for i, iid in enumerate(ids[s])]

    t4 = {ids["test"][i] for i in top3_4b_test}
    spec = {"rows": [
        {"method": "rule", "model": None, "level": None, "runs": {"dev": run("r", "rule", None, None, rows("dev", 9, set(ids["dev"][:15]))), "test": None}},
        {"method": "llm", "model": "qwen3.5-4b", "level": "narrowed", "runs": {
            "dev": run("a", "llm", "qwen3.5-4b", "narrowed", rows("dev", 9, set(ids["dev"]))),
            "test": run("b", "llm", "qwen3.5-4b", "narrowed", rows("test", 9, t4))}},
        {"method": "llm", "model": "qwen3.5-9b", "level": "narrowed", "info": True, "runs": {
            "dev": run("c", "llm", "qwen3.5-9b", "narrowed", rows("dev", 9, set(ids["dev"]))),
            "test": run("d", "llm", "qwen3.5-9b", "narrowed", rows("test", 9, {ids["test"][i] for i in top3_9b_test}))}}]}
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "p1_runs.json").write_text(json.dumps(spec))
    return tmp_path


@pytest.mark.parametrize("top3_9b,counts,reading", [
    ([*range(10), 13, 14, 15, 16], (4, 3, 10), "none"),     # yalnız 9B 13–16, yalnız 4B 10–12 (yön ayrı sayılar)
    (range(18), (5, 0, 13), "none"),                       # 9B hepsi: yalnız 9B 5 (< 6)
    (range(7), (0, 6, 7), "4b"),                           # 9B 4B'nin 13'ünün 7'si: yalnız 4B 6, yalnız 9B 0
])
def test_test_path_end_to_end(tmp_path, top3_9b, counts, reading):
    res = results.build(fake_repo(tmp_path, list(top3_9b)))
    by = {r["id"]: r for r in res["rows"]}
    dt = by["qwen3.5-4b narrowed"]["dev_test"]
    num, den = results.fisher(18, 18, 13, 18)
    assert (dt["dev_top3"], dt["test_top3"]) == (18, 13)                  # top-1 (9 / 9) değil top-3
    assert dt["p"] == round(num / den, 4) and dt["reading"] == "down"     # karardaki eşik: 18 → ≤ 13 fark
    assert by["rule"]["dev_test"] is None and by["rule"]["test"] is None
    b9 = res["reading_9b"]
    assert (b9["only_9b"], b9["only_4b"], b9["both"]) == counts and b9["reading"] == reading
    t = by["qwen3.5-4b narrowed"]["test"]
    assert (t["all"]["n"], t["own"]["n"], t["demo"]["n"]) == (18, 5, 13)  # test grupları test etiketlerinden
    assert (t["all"]["top3"], t["own"]["top3"], t["demo"]["top3"]) == (13, 5, 8)
    assert by["qwen3.5-4b narrowed"]["dev"]["own"]["n"] == 7
    md, js = results.markdown(res), json.dumps(res, ensure_ascii=False)
    assert "## 4. Test ayrıntı: kendi hatalarımız (5)" in md and "fark (düşüş)" in md
    assert "inc-test" not in md and "inc-test" not in js                 # test vaka kimlikleri çıktıya girmez


def test_test_path_9b_difference_for_9b(tmp_path):
    # 4B testte 12 vaka, 9B hepsi: yalnız 9B 6, yalnız 4B 0 → "fark (9B lehine)"; dev–test 18 → 12 düşüş.
    res = results.build(fake_repo(tmp_path, range(18), top3_4b_test=range(12)))
    b9 = res["reading_9b"]
    assert (b9["only_9b"], b9["only_4b"], b9["both"], b9["reading"]) == (6, 0, 12, "9b")
    assert "fark (9B lehine)" in results.markdown(res)
