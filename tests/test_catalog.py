"""Koşucudaki doğru cevap alanları (`SCENARIOS`) INCIDENT_CATALOG.md "Flag senaryoları" tablosuyla aynı mı (V1).

Tablo elle yazılan kaynak; koşucu etiketlere bu alanları yazar. Biri değişip diğeri unutulursa kırmızı.
Yayılım yolu "a → b → c" zincir, "a → b, c" dallanma: ardışık iki parçanın her çifti bir kenar.
"""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import scenario_runner  # noqa: E402

CATALOG = REPO / "docs" / "INCIDENT_CATALOG.md"


def catalog_rows() -> dict[str, dict]:
    lines = CATALOG.read_text(encoding="utf-8").splitlines()
    start = lines.index("## Flag senaryoları (11)")
    table = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            table.append([c.strip() for c in line.strip().strip("|").split("|")])
    header, rows = table[0], table[2:]
    col = {name: i for i, name in enumerate(header)}
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
