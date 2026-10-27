"""Koşucudaki doğru cevap alanları (`SCENARIOS`) INCIDENT_CATALOG.md "Flag senaryoları" tablosuyla aynı mı (V1);
altyapı hataları (`INFRA_ANSWERS`, `INFRA_FAULTS`, `PARAM_RE`) "Kendi altyapı hatalarımız" tablosuyla aynı mı ve her
satır geçerli, belirtili bir etiketle destekleniyor mu (V2).

Tablo elle yazılan kaynak; koşucu etiketlere bu alanları yazar. Biri değişip diğeri unutulursa kırmızı.
Yayılım yolu "a → b → c" zincir, "a → b, c" dallanma: ardışık iki parçanın her çifti bir kenar.
"""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import scenario_runner  # noqa: E402

CATALOG = REPO / "docs" / "INCIDENT_CATALOG.md"


def table(heading: str) -> tuple[dict, list]:
    """Başlığın altındaki ilk tablo (bir sonraki başlığa kadar): (sütun → sıra, satırlar)."""
    lines = CATALOG.read_text(encoding="utf-8").splitlines()
    start = lines.index(heading)
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("#"):
            break
        if line.startswith("|"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif rows:
            break
    return {name: i for i, name in enumerate(rows[0])}, rows[2:]


def catalog_rows() -> dict[str, dict]:
    col, rows = table("## Flag senaryoları (11)")
    out = {}
    for r in rows:
        flag = r[col["Senaryo"]].strip("`")
        out[flag] = {"root": r[col["Kök neden"]], "fault_type": r[col["Hata tipi"]],
                     "propagation_path": edges(r[col["Beklenen yayılım yolu"]]),
                     "categories": [] if r[col["Kategori"]] == "—" else
                     [c.strip() for c in r[col["Kategori"]].split(",")]}
    return out


def edges(path: str) -> list[list[str]]:
    parts = [[n.strip() for n in p.split(",")] for p in path.split("→")]
    return [[a, b] for left, right in zip(parts, parts[1:]) for a in left for b in right]


ROWS = catalog_rows()
CASES = [s for s in scenario_runner.SCENARIOS if s["root"] is not None]


def test_catalog_has_eleven_scenarios():
    assert len(ROWS) == 11, sorted(ROWS)


def test_every_catalog_scenario_in_runner():
    assert set(ROWS) == {s["flag"] for s in CASES}


@pytest.mark.parametrize("s", CASES, ids=scenario_runner.scenario_id)
def test_answer_fields_match_catalog(s):
    row = ROWS[s["flag"]]
    assert {k: s[k] for k in row} == row


def test_edges_chain_and_branch():
    assert edges("a → b → c") == [["a", "b"], ["b", "c"]]
    assert edges("a → b, c") == [["a", "b"], ["a", "c"]]


def test_flag_cells_are_plain_names():
    assert all(re.fullmatch(r"[A-Za-z]+", f) for f in ROWS)


# --- altyapı hataları (V2) ---

INFRA_HEADING = "## Kendi altyapı hatalarımız (10)"
CATEGORIES = {"cascading", "silent", "noisy", "partial"}
VERDICT_MARKS = {"no_symptom", "borderline", "not_measurable"}


def infra_rows() -> list[dict]:
    col, rows = table(INFRA_HEADING)
    return [{"fault": r[col["Senaryo"]].strip("`"), "target": r[col["Kök neden"]], "param": r[col["Parametre"]].strip("`"),
             "fault_type": r[col["Hata tipi"]], "method": r[col["Yöntem"]].strip("`"),
             "propagation_path": edges(r[col["İzlerde yayılım yolu"]]),
             "categories": [c.strip() for c in r[col["Kategori"]].split(",")],
             "support": r[col["Destek vakası"]].strip("`")} for r in rows]


INFRA = infra_rows()


def test_infra_catalog_has_ten_pairs():
    assert len(INFRA) == 10 and len({(r["fault"], r["target"]) for r in INFRA}) == 10


def test_infra_answers_match_catalog():
    # INFRA_ANSWERS = katalog tablosu (yol ve kategoriler), sıra dahil.
    assert scenario_runner.INFRA_ANSWERS == [{k: r[k] for k in ("fault", "target", "propagation_path", "categories")}
                                             for r in INFRA]


@pytest.mark.parametrize("r", INFRA, ids=lambda r: f"{r['fault']}-{r['target']}")
def test_infra_row_matches_runner(r):
    spec = scenario_runner.INFRA_FAULTS[r["fault"]]
    assert spec["fault_type"] == r["fault_type"] and r["method"] in spec["method"]
    assert re.fullmatch(scenario_runner.PARAM_RE[r["fault"]], r["param"])
    assert set(r["categories"]) <= CATEGORIES and r["target"] != "frontend"


@pytest.mark.parametrize("r", INFRA, ids=lambda r: f"{r['fault']}-{r['target']}")
def test_infra_row_supported_by_symptomatic_label(r):
    label = json.loads((REPO / "incidents" / f"{r['support']}.json").read_text(encoding="utf-8"))
    entry = label["run"]["list_entry"]
    assert (entry["fault"], entry["target"], entry["param"]) == (r["fault"], r["target"], r["param"])
    assert label["valid"] and label["checks"]["symptom"]["verdict"] == "symptomatic"
    assert not VERDICT_MARKS & set(label["marks"])
    a = label["answer"]
    assert a["propagation_path"] == r["propagation_path"] and a["categories"] == r["categories"]


def test_memory_limit_not_in_selection():
    # DECISIONS 2026-10-28: memoryLimit V2'den çıkar (kod kalır).
    assert "memoryLimit" in scenario_runner.INFRA_FAULTS
    assert all(r["fault"] != "memoryLimit" for r in INFRA)
    assert all(x["fault"] != "memoryLimit" for x in scenario_runner.INFRA_ANSWERS)
