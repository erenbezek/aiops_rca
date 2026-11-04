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
