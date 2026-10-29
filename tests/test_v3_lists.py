"""V3 gece listeleri (`incident_lists/v3_night1.json`, `v3_night2.json`) kart tablosuyla birebir aynı mı (HANDOFF 2026-10-29
V3 kartı: bileşim tablosu ve V3a 5. adım; DECISIONS 2026-10-29 "V3 bileşimi").

Bileşim kayıttan önce sabit, sonuca göre değişmez: bir giriş eklenir, silinir, setler ya da geceler arasında yer
değiştirirse kırmızı. Ayrılan 6 birim (`HELDOUT_UNITS`, tanımı `test_catalog.py`'de) yalnız testte.
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


def test_shared_infra_pairs_in_different_nights():
    where = {(key(e)[1:4], e["set"]): name for name, entries in NIGHTS.items() for e in entries if "fault" in e}
    for p in SHARED:
        assert where[(p, "dev")] != where[(p, "test")], p


def test_heldout_units_only_in_test():
    seen = Counter()
    for entries in NIGHTS.values():
        for e in entries:
            if unit(e) in HELDOUT_UNITS:
                assert e["set"] == "test", e
                seen[unit(e)] += 1
    assert seen == Counter({u: 1 for u in HELDOUT_UNITS})


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
