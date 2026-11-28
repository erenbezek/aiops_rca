"""V3 gece listeleri (`incident_lists/v3_night1.json`, `v3_night2.json`) kart tablosuyla birebir aynı mı (HANDOFF 2026-10-29
V3 kartı: bileşim tablosu ve V3a 5. adım; DECISIONS 2026-10-29 "V3 bileşimi").

Bileşim kayıttan önce sabit, sonuca göre değişmez: bir giriş eklenir, silinir, setler ya da geceler arasında yer
değiştirirse kırmızı. Ayrılan 6 birim (`HELDOUT_UNITS`, tanımı `test_catalog.py`'de) yalnız testte.
İki sette olan 13 birimin dev ve test kopyaları farklı gecelerde; tekil 10 birim gece başına 2 ya da 3 (düzeltme:
HANDOFF 2026-10-29 "V3a 4–5 kontrolü; liste düzeltmesi").
Listeler repo dışındaki üreticiyle yazıldı (`~/cerebrum2/analysis/v3_lists.py`, tohum HANDOFF'ta); bu test üreticiye
değil, karta bakar.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import scenario_runner as sr  # noqa: E402
from test_catalog import HELDOUT_UNITS  # noqa: E402
from test_infra_faults import no_side_effects  # noqa: E402

LISTS = REPO / "incident_lists"
FLOOD = "loadGeneratorFloodHomepage_on"


def flag(scenario: str, set_: str, noise: str | None = None) -> tuple:
    return ("scenario", scenario, None, None, noise, set_)


def infra(fault: str, target: str, param: str, set_: str) -> tuple:
    return ("fault", fault, target, param, None, set_)


SHARED = [("networkDelay", "cart", "50ms"), ("packetLoss", "shipping", "10%"), ("cpuThrottle", "product-catalog", "0.09"),
          ("containerPause", "cart", "on"), ("containerStop", "recommendation", "on")]
# Kart tablosu (V3, 40 vaka).
DEV = [flag(s, "dev") for s in ("adFailure_on", "adHighCpu_on", "adManualGc_on", "cartFailure_50pct",
                                "emailMemoryLeak_1000x", "paymentFailure_50pct", "paymentUnreachable_on",
                                "productCatalogFailure_on", "productCatalogLockContention_on",
                                "recommendationCacheFailure_on", "intlShippingSlowdown_10sec")] \
    + [infra(*p, "dev") for p in SHARED] \
    + [flag("quoteGatewayMisroute_on", "dev"), flag("quoteGatewaySlowdown_30ms", "dev"),
       flag("quoteGatewaySlowdown_30ms", "dev", FLOOD)]
TEST = [flag(s, "test") for s in ("cartFailure_50pct", "intlShippingSlowdown_10sec", "productCatalogFailure_on",
                                  "recommendationCacheFailure_on", "paymentUnreachable_on", "adHighCpu_on")] \
    + [infra(*p, "test") for p in SHARED] \
    + [infra("networkDelay", "quote", "50ms", "test"), infra("packetLoss", "currency", "10%", "test"),
       infra("cpuThrottle", "recommendation", "0.03", "test"), infra("containerPause", "quote", "on", "test"),
       infra("containerStop", "currency", "on", "test")] \
    + [flag("quoteGatewayMisroute_on", "test"), flag("quoteGatewaySlowdown_30ms", "test"),
       flag("quoteGatewayMemoryLeak_384kb", "test"),
       flag("paymentFailure_50pct", "test", FLOOD), flag("productCatalogLockContention_on", "test", FLOOD)]
TAILS = {"v3_night1": [flag("quoteGatewaySlowdown_30ms", "dev", FLOOD), flag("paymentFailure_50pct", "test", FLOOD)],
         "v3_night2": [flag("productCatalogLockContention_on", "test", FLOOD),
                       flag("quoteGatewayMemoryLeak_384kb", "test")]}
COUNTS = {"v3_night1": {"dev": 10, "test": 10}, "v3_night2": {"dev": 9, "test": 11}}


def key(e: dict) -> tuple:
    if "fault" in e:
        return ("fault", e["fault"], e["target"], e["param"], e["noise_layer"], e["set"])
    return ("scenario", e["scenario"], None, None, e["noise_layer"], e["set"])


def unit(e: dict) -> tuple:
    return (e["fault"], e["target"]) if "fault" in e else (sr.BY_ID[e["scenario"]]["flag"], sr.BY_ID[e["scenario"]]["root"])


NIGHTS = {name: json.loads((LISTS / f"{name}.json").read_text(encoding="utf-8")) for name in COUNTS}


def test_card_table_itself():
    assert (len(DEV), len(TEST)) == (19, 21)


def test_lists_match_card_table():
    got = Counter(key(e) for entries in NIGHTS.values() for e in entries)
    assert got == Counter(DEV + TEST)
    assert all(set(e) == ({"fault", "target", "param"} if "fault" in e else {"scenario"}) | {"noise_layer", "set"}
               for entries in NIGHTS.values() for e in entries)


@pytest.mark.parametrize("name", COUNTS)
def test_night_counts_and_tail(name):
    entries = NIGHTS[name]
    assert dict(Counter(e["set"] for e in entries)) == COUNTS[name]
    assert [key(e) for e in entries[-len(TAILS[name]):]] == TAILS[name]
    assert all(key(e) not in TAILS[name] for e in entries[:-len(TAILS[name])])


# İki sette olan birimler (setsiz anahtar; flood'lu girişler ayrı birim): 5 altyapı çifti, 6 demo flag'i,
# quoteGatewayMisroute, quoteGatewaySlowdown 30ms. Düzeltme: HANDOFF 2026-10-29 "V3a 4–5 kontrolü; liste düzeltmesi".
SHARED_UNITS = {k[:5] for k in DEV} & {k[:5] for k in TEST}
# Tekil birimler (gece sonundakiler hariç): dev'e özel 5 demo flag'i, yalnız testteki 5 altyapı çifti.
TAIL_KEYS = {k for t in TAILS.values() for k in t}
SINGLES = {"dev": [k for k in DEV if k[:5] not in SHARED_UNITS and k not in TAIL_KEYS],
           "test": [k for k in TEST if k[:5] not in SHARED_UNITS and k not in TAIL_KEYS]}


def test_shared_units_in_different_nights():
    assert len(SHARED_UNITS) == 13 and {len(v) for v in SINGLES.values()} == {5}
    where = {key(e): name for name, entries in NIGHTS.items() for e in entries}
    for u in SHARED_UNITS:
        assert where[(*u, "dev")] != where[(*u, "test")], u


@pytest.mark.parametrize("name", COUNTS)
def test_single_units_two_or_three_per_night(name):
    keys = [key(e) for e in NIGHTS[name]]
    for set_, singles in SINGLES.items():
        assert sum(k in singles for k in keys) in (2, 3), (name, set_)


def test_heldout_units_only_in_test():
    seen = Counter()
    for entries in NIGHTS.values():
        for e in entries:
            if unit(e) in HELDOUT_UNITS:
                assert e["set"] == "test", e
                seen[unit(e)] += 1
    assert seen == Counter({u: 1 for u in HELDOUT_UNITS})


def test_night2_parts_equal_night2():
    # 2. gece iki parçada koşulur (DECISIONS 2026-10-29 "2. gece iki parçada"): 2a (1–15) + 2b (16–20) art arda,
    # giriş giriş ve sırayla v3_night2. v3_night2 kart tablosunun listesi olarak kalır, kendisi koşulmaz.
    a, b = (json.loads((LISTS / f"v3_night2{p}.json").read_text(encoding="utf-8")) for p in "ab")
    assert (len(a), len(b)) == (15, 5)
    assert a + b == NIGHTS["v3_night2"]


def test_retry_list_is_night2_tail():
    # V3c telafi listesi (DECISIONS 2026-10-30 "v3_retry"): v3_night2'nin 17–20. girişleri, aynı sıra. İlk ikisi 2. gecede
    # geçersizdi (telafi), son ikisi koşulmadı (ilk deneme).
    retry = json.loads((LISTS / "v3_retry.json").read_text(encoding="utf-8"))
    assert retry == NIGHTS["v3_night2"][16:20]


@pytest.mark.parametrize("name", COUNTS)
def test_runner_accepts_list(monkeypatch, tmp_path, name):
    # Koşucunun liste denetimi: geçerli liste korumaya kadar gider (koruma burada durdurur: 1); reddedilen liste 2.
    no_side_effects(monkeypatch)
    monkeypatch.setattr(sr, "INCIDENT_RUNS", tmp_path / "runs")
    monkeypatch.setattr(sr, "versions", lambda: {})
    monkeypatch.setattr(sr, "guards", lambda: {"problems": ["test stop"], "swap_free_gb": 3.0, "monitoring_gb": 15.5})
    monkeypatch.setattr(sr, "run_incident", lambda *a, **k: pytest.fail("must not run"))
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    assert sr.cmd_incidents(LISTS / f"{name}.json") == 1


# --- P2e listeleri (`incident_lists/p2e_night1.json`, `p2e_night2.json`; HANDOFF 2026-11-28 planlamanın düzeltilmiş
# kuralı). Üretici repo dışı (`~/cerebrum2/analysis/p2e_lists.py`, tohum ve sha HANDOFF'ta); bu test kurala bakar. ---

P2E = [json.loads((LISTS / f"p2e_night{n}.json").read_text(encoding="utf-8")) for n in (1, 2)]
P2E_ALL = P2E[0] + P2E[1]


def p2e_unit(e: dict) -> tuple:
    return (e["fault"], e["target"], e["param"]) if "fault" in e else (e["scenario"],)


def test_p2e_lists_rule():
    test_entries = [e for entries in NIGHTS.values() for e in entries if e["set"] == "test"]
    base = Counter(p2e_unit(e) for e in test_entries)
    assert len(base) == 21 and set(base.values()) == {1}                       # test listesinin 21 benzersiz girişi
    assert [len(p) for p in P2E] == [17, 17] and all(e["set"] == "p2e" for e in P2E_ALL)
    assert all(set(e) == ({"fault", "target", "param"} if "fault" in e else {"scenario"}) | {"noise_layer", "set"}
               for e in P2E_ALL)
    got = Counter(p2e_unit(e) for e in P2E_ALL)
    assert set(got) == set(base) and sum(got.values()) == 34 and set(got.values()) <= {1, 2}
    kinds = Counter("fault" in e for e in P2E_ALL)
    assert (kinds[False], kinds[True]) == (18, 16)                               # flag 18, altyapı 16
    repeats = [u for u, n in got.items() if n == 2]
    assert len(repeats) == 13 and sum(len(u) == 1 for u in repeats) == 7         # tekrar: flag 7, altyapı 6
    main, spare = P2E_ALL[:30], P2E_ALL[30:]
    assert {p2e_unit(e) for e in main} == set(base)                              # 21 türün hepsi ana blokta
    assert all(p2e_unit(e) in {p2e_unit(m) for m in main} for e in spare)       # yedek (son 4) yalnız tekrar
    assert all(e["noise_layer"] is None for e in spare)
    flood = [e for e in P2E_ALL if e["noise_layer"]]
    assert {e["noise_layer"] for e in flood} == {FLOOD} and all(e in main for e in flood)
    assert sorted(e["scenario"] for e in flood) == ["paymentFailure_50pct", "productCatalogLockContention_on",
                                                    "quoteGatewaySlowdown_30ms"]  # her bileşim bir kez (temel giriş)


@pytest.mark.parametrize("n", (1, 2))
def test_runner_accepts_p2e_list(monkeypatch, tmp_path, n):
    no_side_effects(monkeypatch)
    monkeypatch.setattr(sr, "INCIDENT_RUNS", tmp_path / "runs")
    monkeypatch.setattr(sr, "versions", lambda: {})
    monkeypatch.setattr(sr, "guards", lambda: {"problems": ["test stop"], "swap_free_gb": 3.0, "monitoring_gb": 15.5})
    monkeypatch.setattr(sr, "run_incident", lambda *a, **k: pytest.fail("must not run"))
    monkeypatch.setattr(sr.subprocess, "run", lambda *a, **k: sr.subprocess.CompletedProcess(a, 0, "", ""))
    assert sr.cmd_incidents(LISTS / f"p2e_night{n}.json") == 1
