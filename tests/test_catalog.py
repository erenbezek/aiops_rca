"""Koşucudaki doğru cevap alanları (`SCENARIOS`) INCIDENT_CATALOG.md "Flag senaryoları" tablosuyla aynı mı (V1);
altyapı hataları (`INFRA_ANSWERS`, `INFRA_FAULTS`, `PARAM_RE`) "Kendi altyapı hatalarımız" tablosuyla aynı mı ve her
satır geçerli, belirtili bir etiketle destekleniyor mu (V2).

Tablo elle yazılan kaynak; koşucu etiketlere bu alanları yazar. Biri değişip diğeri unutulursa kırmızı.
Kategori hücresi varyant başına da yazılabilir (DECISIONS 2026-10-29, quote-gateway sızıntısı):
"`384kb`: silent (`inc-…`); `1024kb`: — (`inc-…`)"; o zaman her varyant kendi kategorisi ve destek etiketiyle sınanır.
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


VARIANT_CELL = re.compile(r"`([^`]+)`: (.+) \(`(inc-[0-9a-f]{8})`\)")


def category_list(cell: str) -> list[str]:
    return [] if cell.strip() == "—" else [c.strip() for c in cell.split(",")]


def variant_cells(cell: str) -> dict[str, dict]:
    """Varyant başına kategori hücresi → {varyant: {"categories", "support"}}; düz hücrede boş."""
    if "`" not in cell:
        return {}
    out = {}
    for part in cell.split(";"):
        m = VARIANT_CELL.fullmatch(part.strip())
        assert m, f"bad variant cell: {part!r}"
        out[m.group(1)] = {"categories": category_list(m.group(2)), "support": m.group(3)}
    return out


def catalog_rows() -> dict[str, dict]:
    col, rows = table("## Flag senaryoları (14)")
    out = {}
    for r in rows:
        flag = r[col["Senaryo"]].strip("`")
        variants = variant_cells(r[col["Kategori"]])
        out[flag] = {"root": r[col["Kök neden"]], "fault_type": r[col["Hata tipi"]],
                     "propagation_path": edges(r[col["Beklenen yayılım yolu"]]),
                     "categories": None if variants else category_list(r[col["Kategori"]]),
                     "variants": variants}
    return out


def edges(path: str) -> list[list[str]]:
    parts = [[n.strip() for n in p.split(",")] for p in path.split("→")]
    return [[a, b] for left, right in zip(parts, parts[1:]) for a in left for b in right]


ROWS = catalog_rows()
VERDICT_MARKS = {"no_symptom", "borderline", "not_measurable"}
CASES = [s for s in scenario_runner.SCENARIOS if s["root"] is not None]


def test_catalog_has_fourteen_scenarios():
    # 11 demo flag'i + kendi servisimizin 3 flag'i (quote-gateway, DECISIONS 2026-10-28).
    assert len(ROWS) == 14, sorted(ROWS)


def test_every_catalog_scenario_in_runner():
    assert set(ROWS) == {s["flag"] for s in CASES}


@pytest.mark.parametrize("s", CASES, ids=scenario_runner.scenario_id)
def test_answer_fields_match_catalog(s):
    row = ROWS[s["flag"]]
    if row["variants"]:
        assert s["variant"] in row["variants"], "variant missing from per-variant catalog cell"
        categories = row["variants"][s["variant"]]["categories"]
    else:
        categories = row["categories"]
    want = {"root": row["root"], "fault_type": row["fault_type"], "propagation_path": row["propagation_path"],
            "categories": categories}
    assert {k: s[k] for k in want} == want


VARIANT_ROWS = [(flag, v, d) for flag, row in ROWS.items() for v, d in row["variants"].items()]


def test_leak_categories_per_variant():
    # DECISIONS 2026-10-29: 384 KB silent, 1024 KB boş (OOM yeniden başlaması çağıranlarda hata span'i üretir).
    assert ROWS["quoteGatewayMemoryLeak"]["variants"] == {
        "384kb": {"categories": ["silent"], "support": "inc-ff3a6614"},
        "1024kb": {"categories": [], "support": "inc-660f7c44"}}


@pytest.mark.parametrize("flag,variant,d", VARIANT_ROWS, ids=[f"{f}_{v}" for f, v, _ in VARIANT_ROWS])
def test_variant_supported_by_own_label(flag, variant, d):
    label = json.loads((REPO / "incidents" / f"{d['support']}.json").read_text(encoding="utf-8"))
    a = label["answer"]
    assert (a["scenario"], a["variant"]) == (flag, variant)
    assert label["valid"] and label["checks"]["symptom"]["verdict"] == "symptomatic"
    assert not VERDICT_MARKS & set(label["marks"])
    assert a["categories"] == d["categories"] and a["propagation_path"] == ROWS[flag]["propagation_path"]


def test_edges_chain_and_branch():
    assert edges("a → b → c") == [["a", "b"], ["b", "c"]]
    assert edges("a → b, c") == [["a", "b"], ["a", "c"]]


def test_flag_cells_are_plain_names():
    assert all(re.fullmatch(r"[A-Za-z]+", f) for f in ROWS)


# --- altyapı hataları (V2) ---

INFRA_HEADING = "## Kendi altyapı hatalarımız (10)"
CATEGORIES = {"cascading", "silent", "noisy", "partial"}


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


# DECISIONS 2026-10-29 (`heldout`): yalnız V3 testinde olan 6 birim (hata ya da senaryo, kök neden servisi; varyant
# fark etmez). Bu birimlerin etiketleri geliştirmede okunmaz: set `heldout` (pilot etiketleri) ya da `test` (V3).
HELDOUT_UNITS = {("networkDelay", "quote"), ("packetLoss", "currency"), ("cpuThrottle", "recommendation"),
                 ("containerPause", "quote"), ("containerStop", "currency"),
                 ("quoteGatewayMemoryLeak", "quote-gateway")}


def test_heldout_only_in_held_units():
    labels = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((REPO / "incidents").glob("inc-*.json"))]
    unit = {d["incident_id"]: (d["answer"]["scenario"], d["answer"]["root_cause_service"]) for d in labels}
    leaked = [(d["incident_id"], d["set"]) for d in labels
              if unit[d["incident_id"]] in HELDOUT_UNITS and d["set"] not in {"heldout", "test"}]
    stray = [d["incident_id"] for d in labels if d["set"] == "heldout" and unit[d["incident_id"]] not in HELDOUT_UNITS]
    assert not leaked, f"held-out unit labels open to development: {leaked}"
    assert not stray, f"heldout outside the held-out units: {stray}"
    # Ad yazım hatası kuralı boşa düşürmesin: her birimin repoda en az bir etiketi var.
    assert HELDOUT_UNITS <= set(unit.values())


def test_flag_labels_follow_catalog_categories():
    # DECISIONS 2026-10-29 "Flag kategorileri": etiketteki kategoriler koşucudaki senaryonunkiler, noise_layer'lı vakada
    # + noisy (pilot etiketleri geriye dönük güncellendi; V3 etiketlerini koşucu yazar).
    for p in sorted((REPO / "incidents").glob("inc-*.json")):
        label = json.loads(p.read_text(encoding="utf-8"))
        entry, a = label["run"]["list_entry"], label["answer"]
        if "fault" in entry:
            continue
        cats = scenario_runner.BY_ID[entry["scenario"]]["categories"]
        want = cats + (["noisy"] if a["noise_layer"] and "noisy" not in cats else [])
        assert a["categories"] == want, (label["incident_id"], a["categories"], want)
