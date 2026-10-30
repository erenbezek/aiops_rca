"""Puanlama ve çağrı kenarları (HANDOFF 2026-10-30 P1a kartı "Bitti sayılır: Puanlama"): sahte cevaplarla top-1/top-3,
ad eşleme, geçerli/geçersiz/kenarsız yol, örtüşme, Brier, seçici doğruluk, "emin değilim"."""
import json
from collections import Counter

import pytest

from aiops_rca.answer import Answer
from aiops_rca.call_graph import service_edges
from aiops_rca.scoring import match_service, score_case, score_table

KNOWN = {"frontend", "checkout", "payment", "cart", "valkey-cart", "frontend-proxy"}
# checkout payment'ı çağırır, frontend checkout'u çağırır, checkout Kafka'ya yazar (accounting tüketir).
EDGES = Counter({("checkout", "payment"): 5, ("frontend", "checkout"): 7, ("checkout", "accounting"): 2})
LABEL = {"set": "dev", "root_cause_service": "payment", "propagation_path": [["payment", "checkout"], ["checkout", "frontend"]]}


def answer(services, paths=None, conf=None, unsure=False) -> Answer:
    paths = paths or [[s] for s in services]
    confs = conf or [None] * 3
    return Answer.from_dict({"candidates": [{"service": s, "confidence": c, "evidence_path": p, "rationale": ""}
                                            for s, p, c in zip(services, paths, confs)], "unsure": unsure})


@pytest.mark.parametrize("name,want", [("payment", "payment"), (" Payment ", "payment"), ("valkey_cart", "valkey-cart"),
                                       ("Valkey Cart", "valkey-cart"), ("paymentservice", None), ("pay", None)])
def test_match_service(name, want):
    assert match_service(name, KNOWN) == want


def test_top1_top3():
    assert score_case(answer(["payment", "checkout", "cart"]), LABEL, EDGES, KNOWN)[("top1")] is True
    s = score_case(answer(["checkout", "cart", "PAYMENT"]), LABEL, EDGES, KNOWN)
    assert (s["top1"], s["top3"]) == (False, True)
    s = score_case(answer(["checkout", "cart", "frontend"]), LABEL, EDGES, KNOWN)
    assert (s["top1"], s["top3"]) == (False, False)
    s = score_case(answer(["paymentsvc", "cart", "frontend"]), LABEL, EDGES, KNOWN)
    assert (s["top1"], s["unmatched"]) == (False, ["paymentsvc"])


def test_evidence_valid_both_directions_recorded():
    a = answer(["payment", "cart", "frontend"], [["payment", "checkout", "frontend"], ["cart"], ["frontend"]])
    s = score_case(a, LABEL, EDGES, KNOWN | {"accounting"})
    assert s["evidence_valid"] is True
    assert [e["seen"] for e in s["evidence_edges"]] == ["reverse", "reverse"]
    # Kafka: yayılım çağrı yönünde.
    a = answer(["checkout", "cart", "frontend"], [["checkout", "accounting"], ["cart"], ["frontend"]])
    s = score_case(a, LABEL, EDGES, KNOWN | {"accounting"})
    assert (s["evidence_valid"], s["evidence_edges"][0]["seen"]) == (True, "forward")


def test_evidence_invalid_and_null():
    a = answer(["payment", "cart", "frontend"], [["payment", "frontend"], ["cart"], ["frontend"]])
    assert score_case(a, LABEL, EDGES, KNOWN)["evidence_valid"] is False  # payment ↔ frontend çağrısı yok
    a = answer(["payment", "cart", "frontend"], [["payment", "nowhere"], ["cart"], ["frontend"]])
    assert score_case(a, LABEL, EDGES, KNOWN)["evidence_valid"] is False  # eşleşmeyen ad
    s = score_case(answer(["payment", "cart", "frontend"]), LABEL, EDGES, KNOWN)
    assert (s["evidence_valid"], s["label_path_overlap"]) == (None, 0.0)  # tek servislik yol


def test_label_path_overlap():
    a = answer(["payment", "cart", "frontend"], [["payment", "checkout", "frontend"], ["cart"], ["frontend"]])
    assert score_case(a, LABEL, EDGES, KNOWN)["label_path_overlap"] == 1.0
    a = answer(["payment", "cart", "frontend"], [["payment", "checkout"], ["cart"], ["frontend"]])
    assert score_case(a, LABEL, EDGES, KNOWN)["label_path_overlap"] == 0.5
    a = answer(["frontend", "cart", "payment"], [["frontend", "checkout", "payment"], ["cart"], ["payment"]])
    assert score_case(a, LABEL, EDGES, KNOWN)["label_path_overlap"] == 0.0  # ters yön sayılmaz
    assert score_case(a, {**LABEL, "propagation_path": []}, EDGES, KNOWN)["label_path_overlap"] is None


def row(a, set_="dev", label=LABEL, **extra):
    return {"set": set_, **score_case(a, label, EDGES, KNOWN), **extra}


def test_brier_selective_accuracy_coverage():
    rows = [row(answer(["payment", "cart", "frontend"], conf=[0.8, 0.1, 0.1])),               # doğru, 0,8
            row(answer(["cart", "payment", "frontend"], conf=[0.6, 0.3, 0.1])),               # yanlış, 0,6
            row(answer(["checkout", "cart", "frontend"], conf=[0.3, 0.3, 0.3], unsure=True))]  # yanlış, emin değil
    t = score_table(rows)["dev"]
    assert t["brier"] == round((0.2 ** 2 + 0.6 ** 2 + 0.3 ** 2) / 3, 4) and t["brier_n"] == 3
    assert (t["selective_accuracy"], t["coverage"]) == (0.5, 0.667)
    assert (t["top1"], t["top1_rate"], t["top3"]) == (1, 0.333, 2)


def test_no_confidence_skips_calibration_and_schema_invalid_counts_wrong():
    rows = [row(answer(["payment", "cart", "frontend"]), duration_s=0.5),
            {"set": "pilot", **score_case(None, LABEL, EDGES, KNOWN), "duration_s": 1.0}]
    t = score_table(rows)
    assert (t["dev"]["brier"], t["dev"]["brier_n"], t["dev"]["coverage"]) == (None, 0, 1.0)
    assert (t["pilot"]["schema_invalid"], t["pilot"]["top1"], t["pilot"]["coverage"]) == (1, 0, 0.0)
    assert (t["all"]["n"], t["all"]["top1"], t["all"]["evidence_null"], t["all"]["duration_s_total"]) == (2, 1, 2, 1.5)
    assert t["all"]["tokens_input"] is None


def test_service_edges_from_spans(tmp_path):
    def rs(svc, spans):
        return {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": svc}}]},
                "scopeSpans": [{"spans": spans}]}
    docs = [{"resourceSpans": [rs("frontend", [{"spanId": "a1"}, {"spanId": "a2", "parentSpanId": "a1"}]),
                               rs("checkout", [{"spanId": "b1", "parentSpanId": "a2"}])]},
            {"resourceSpans": [rs("payment", [{"spanId": "c1", "parentSpanId": "b1"},
                                              {"spanId": "c2", "parentSpanId": "zz"}])]}]  # zz: pencere dışında
    p = tmp_path / "traces.jsonl"
    p.write_text("".join(json.dumps(d) + "\n" for d in docs))
    edges, names = service_edges([p])
    assert edges == Counter({("frontend", "checkout"): 1, ("checkout", "payment"): 1})
    assert names == {"frontend", "checkout", "payment"}
