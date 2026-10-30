"""Vaka erişimi (HANDOFF 2026-10-30 P1a kartı "Bitti sayılır: Erişim"): `test` bayraksız okunamaz, `heldout` hiç
okunamaz, yöntemin gördüğü `Case` etiket alanı taşımaz. Sahte etiketlerle (gerçek `incidents/` okunmaz)."""
import dataclasses
import json

import pytest

from aiops_rca import cases


def label(iid: str, set_: str, valid: bool = True) -> dict:
    return {"incident_id": iid, "set": set_, "valid": valid,
            "answer": {"injection_start": "2026-10-29T03:07:44Z", "root_cause_service": "payment",
                       "propagation_path": [["payment", "checkout"]]}}


@pytest.fixture
def incidents(tmp_path):
    d = tmp_path / "incidents"
    d.mkdir()
    for lab in (label("inc-p1", "pilot"), label("inc-d1", "dev"), label("inc-d2", "dev", valid=False),
                label("inc-t1", "test"), label("inc-h1", "heldout")):
        (d / f"{lab['incident_id']}.json").write_text(json.dumps(lab))
    return d


def test_default_sets_are_valid_pilot_and_dev(incidents, tmp_path):
    got = cases.load_cases(incidents=incidents, snapshots=tmp_path / "snap")
    assert [c.incident_id for c in got] == ["inc-d1", "inc-p1"]
    assert got[0].view == tmp_path / "snap" / "inc-d1"
    assert got[0].alarm_ns == 1793243264 * 10**9


def test_test_set_needs_final_test_flag(incidents):
    with pytest.raises(PermissionError):
        cases.load_cases(("test",), incidents=incidents)
    with pytest.raises(PermissionError):
        cases.load_labels(("dev", "test"), incidents=incidents)
    assert [c.incident_id for c in cases.load_cases(("test",), final_test=True, incidents=incidents)] == ["inc-t1"]


@pytest.mark.parametrize("final_test", [False, True])
def test_heldout_never_read(incidents, final_test):
    with pytest.raises(PermissionError):
        cases.load_cases(("heldout",), final_test=final_test, incidents=incidents)
    with pytest.raises(PermissionError):
        cases.load_labels(("test", "heldout"), final_test=final_test, incidents=incidents)


def test_unknown_set_is_an_error(incidents):
    with pytest.raises(ValueError):
        cases.load_cases(("Dev",), incidents=incidents)


def test_case_carries_no_label_fields():
    # Yöntem yalnız kimliği, görünümü ve alarm anını alır (kart 1. madde).
    assert [f.name for f in dataclasses.fields(cases.Case)] == ["incident_id", "view", "alarm_ns"]


def test_labels_for_scoring_only(incidents):
    got = cases.load_labels(incidents=incidents)
    assert got == {"inc-d1": {"set": "dev", "root_cause_service": "payment", "propagation_path": [["payment", "checkout"]]},
                   "inc-p1": {"set": "pilot", "root_cause_service": "payment",
                              "propagation_path": [["payment", "checkout"]]}}
