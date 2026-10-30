"""Cevap şeması (HANDOFF 2026-10-30 P1a kartı 3. madde; DECISIONS 2026-10-30 "P1a kararları": tam 3 aday)."""
import copy

import pytest

from aiops_rca.answer import Answer, validate_answer


def cand(service: str, conf=0.5, path=None, why="") -> dict:
    return {"service": service, "confidence": conf, "evidence_path": path or [service], "rationale": why}


GOOD = {"candidates": [cand("payment", 0.7, ["payment", "checkout", "frontend"], "errors"), cand("checkout", 0.2),
                       cand("frontend", 0.1)], "unsure": False}


def test_good_answer_round_trip():
    assert validate_answer(GOOD) == []
    a = Answer.from_dict(GOOD)
    assert a.candidates[0].evidence_path == ("payment", "checkout", "frontend")
    assert a.to_dict() == GOOD


def test_null_confidence_everywhere_is_valid():
    a = copy.deepcopy(GOOD)
    for c in a["candidates"]:
        c["confidence"] = None
    assert validate_answer(a) == []


def bad(edit) -> dict:
    a = copy.deepcopy(GOOD)
    edit(a)
    return a


@pytest.mark.parametrize("name,obj", [
    ("two candidates", bad(lambda a: a["candidates"].pop())),
    ("four candidates", bad(lambda a: a["candidates"].append(cand("cart")))),
    ("duplicate service", bad(lambda a: a["candidates"][2].update(service="Payment", evidence_path=["Payment"]))),
    ("empty service", bad(lambda a: a["candidates"][1].update(service=" ", evidence_path=[" "]))),
    ("confidence > 1", bad(lambda a: a["candidates"][0].update(confidence=1.2))),
    ("confidence bool", bad(lambda a: a["candidates"][0].update(confidence=True))),
    ("mixed null confidence", bad(lambda a: a["candidates"][1].update(confidence=None))),
    ("empty path", bad(lambda a: a["candidates"][0].update(evidence_path=[]))),
    ("path not starting at candidate", bad(lambda a: a["candidates"][0].update(evidence_path=["checkout", "payment"]))),
    ("rationale not text", bad(lambda a: a["candidates"][0].update(rationale=None))),
    ("extra candidate key", bad(lambda a: a["candidates"][0].update(score=3))),
    ("unsure missing", bad(lambda a: a.pop("unsure"))),
    ("unsure not bool", bad(lambda a: a.update(unsure="no"))),
    ("extra answer key", bad(lambda a: a.update(notes="x"))),
    ("not an object", ["payment"]),
])
def test_invalid_answers(name, obj):
    assert validate_answer(obj), name
    with pytest.raises(ValueError):
        Answer.from_dict(obj)
