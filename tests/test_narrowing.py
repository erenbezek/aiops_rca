"""Aday daraltma (DECISIONS 2026-10-31 "Daraltmanın öne alma kuralı"): puan ve sıra, derin servislerin öne alınması,
gruplar, K, dışlamalar, puanı 0 olanlarda güç sırası (`rule_check`'ten fark), CI örneklerinde beklenen çıktı."""
import json
from collections import Counter
from pathlib import Path

from aiops_rca.cases import INCIDENTS, Case, alarm_ns
from aiops_rca.narrowing import GROUPS, K, candidate_narrowing, narrow, service_scores
from aiops_rca.signals import rule_check

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXPECTED = FIXTURES / "narrowing_expected.json"


def row(err=(0.0, 0.0), p95=(10.0, 10.0), req=(100, 100), cpu=None, mem=None):
    r = {"error_rate_before": err[0], "error_rate_after": err[1], "p95_ms_before": p95[0], "p95_ms_after": p95[1],
         "p99_ms_before": p95[0], "p99_ms_after": p95[1], "requests_before": req[0], "requests_after": req[1]}
    if cpu:
        r["cpu_pct_before"], r["cpu_pct_after"] = cpu
    if mem:
        r["mem_mb_before"], r["mem_mb_after"] = mem
    return r


def names(ranking):
    return [r["service"] for r in ranking]


def test_k_is_five():
    assert K == 5 and GROUPS == ("deep", "anomalous", "normal")


def test_scores_match_rule_signals():
    rows = {"checkout": row(err=(0, 0.5), p95=(10, 200)),       # hata + p95 + p99 → 3
            "cart": row(req=(100, 10)),                         # istek düşüşü → 1
            "ad": row(err=(0, 0.02)),                           # eşik altı → 0, güç 0.4
            "astronomy-db": row(err=(0, 0.9), cpu=(5, 50)),     # veritabanı: yalnız CPU/bellek → 1
            "jaeger": row(err=(0, 1)), "flagd": row(err=(0, 1)), "<unknown>": row(err=(0, 1))}
    sc = service_scores(rows)
    assert sorted(sc) == ["ad", "astronomy-db", "cart", "checkout"]
    assert sc["checkout"]["score"] == 3 and sc["checkout"]["signals"] == ["error_rate", "p95_ms", "p99_ms"]
    assert sc["cart"]["signals"] == ["request_drop"]
    assert sc["ad"]["score"] == 0 and sc["ad"]["max_strength"] == 0.4
    assert sc["astronomy-db"]["signals"] == ["cpu_pct"]
    # puanlar kural koduyla aynı
    rc = {t["service"]: t["score"] for t in rule_check(rows, None)["top3"]}
    assert all(sc[s]["score"] == n for s, n in rc.items())


def test_deep_promoted_over_higher_scored_caller():
    """frontend → checkout → payment: üçü anormal; yalnız payment derin, puanı en düşük olsa da önce gelir."""
    sc = {"frontend": {"score": 3, "max_strength": 50, "signals": []},
          "checkout": {"score": 2, "max_strength": 20, "signals": []},
          "payment": {"score": 1, "max_strength": 2, "signals": []},
          "cart": {"score": 0, "max_strength": 0.5, "signals": []}}
    edges = Counter({("frontend", "checkout"): 10, ("checkout", "payment"): 5, ("frontend", "cart"): 3})
    r = narrow(sc, edges)
    assert names(r) == ["payment", "frontend", "checkout", "cart"]
    assert [x["group"] for x in r] == ["deep", "anomalous", "anomalous", "normal"]


def test_caller_of_normal_service_is_deep_and_db_without_edges_is_deep():
    sc = {"frontend": {"score": 2, "max_strength": 9, "signals": []},
          "ad": {"score": 0, "max_strength": 0.1, "signals": []},
          "astronomy-db": {"score": 1, "max_strength": 3, "signals": []}}
    r = narrow(sc, Counter({("frontend", "ad"): 4}))
    assert names(r) == ["frontend", "astronomy-db", "ad"]  # ikisi derin, kendi içinde puan sırası
    assert [x["group"] for x in r] == ["deep", "deep", "normal"]


def test_order_within_group_score_then_strength_then_name():
    sc = {"b": {"score": 1, "max_strength": 2.0, "signals": []},
          "a": {"score": 1, "max_strength": 2.0, "signals": []},
          "c": {"score": 1, "max_strength": 5.0, "signals": []},
          "d": {"score": 2, "max_strength": 1.0, "signals": []}}
    assert names(narrow(sc, {})) == ["d", "c", "a", "b"]


def test_zero_score_ordered_by_strength_not_name():
    """`rule_check`'ten tek fark (DECISIONS 2026-10-31): puanı 0 olanlar eşik altı dahil en büyük güce göre."""
    rows = {"zeta": row(err=(0, 0.04)),   # güç 0.8
            "alpha": row(err=(0, 0.01)),  # güç 0.2
            "mid": row(err=(0, 0.02))}    # güç 0.4
    assert names(narrow(service_scores(rows), {})) == ["zeta", "mid", "alpha"]
    assert [t["service"] for t in rule_check(rows, None)["top3"]] == ["alpha", "mid", "zeta"]  # kural: ada göre


def test_ranking_keeps_all_services():
    sc = {f"s{i}": {"score": i % 3, "max_strength": float(i), "signals": []} for i in range(9)}
    r = narrow(sc, {})
    assert len(r) == 9 and sorted(names(r)) == sorted(sc)


# --- CI örnekleri ---

def fixture_cases():
    for view in sorted((FIXTURES / "snapshots").iterdir()):
        label = json.loads((INCIDENTS / f"{view.name}.json").read_text(encoding="utf-8"))
        yield Case(view.name, view, alarm_ns(label["answer"]["injection_start"]))


def fixture_result():
    out = {}
    for c in fixture_cases():
        n = candidate_narrowing(c)
        out[c.incident_id] = {"candidates": n["candidates"], "edges": n["edges"],
                              "ranking": [{k: v for k, v in r.items()} for r in n["ranking"]]}
    return out


def test_fixtures_reproduce_expected():
    assert fixture_result() == json.loads(EXPECTED.read_text(encoding="utf-8"))


def test_fixture_candidates_shape():
    for c in fixture_cases():
        n = candidate_narrowing(c)
        assert len(n["candidates"]) == K and n["candidates"] == [r["service"] for r in n["ranking"][:K]]
        assert all(a in n["candidates"] and b in n["candidates"] for a, b, _ in n["edges"])
