"""`tools/agent_compare.py` (P2c 2. madde (c)): sınıflama ve 4B ayrışma denetimi, sahte okuyucu ve sahte kayıtlarla
(snapshot ve tokenizer yok)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import agent_compare as ac  # noqa: E402

from aiops_rca.agent_tools import ToolResult  # noqa: E402
from aiops_rca.evaluate import append_agent_case  # noqa: E402
from aiops_rca.runs import new_run  # noqa: E402

Z, E = frozenset({"zero_duration"}), frozenset({"error_tag"})
ZE = Z | E


def _fake_run_tool(texts):
    """Okuyucu (anahtar) → metin; `run_tool` yerine."""
    def run_tool(store, case, name, args, count, max_tokens):
        assert max_tokens == ac.TOOL_RESULT_TOKENS
        return ToolResult(texts[store], 1, 1, False, False)
    return run_tool


STORES = {frozenset(): frozenset(), Z: Z, E: E, ZE: ZE}


@pytest.mark.parametrize("texts, live, expected", [
    ({frozenset(): "a", Z: "b", E: "c", ZE: "d"}, "a", ("same", None)),
    ({frozenset(): "a", Z: "b", E: "c", ZE: "d"}, "b", ("zero_duration", "zero_duration")),
    ({frozenset(): "a", Z: "b", E: "c", ZE: "d"}, "c", ("unexplained", "error_tag")),          # şart 1
    ({frozenset(): "a", Z: "b", E: "c", ZE: "d"}, "d", ("unexplained", "error_tag+zero_duration")),
    ({frozenset(): "a", Z: "b", E: "c", ZE: "d"}, "x", ("unexplained", None)),
    ({frozenset(): "a", Z: "b", E: "b", ZE: "b"}, "b", ("zero_duration", "zero_duration")),  # aynı boyda bilinen önce
])
def test_classify_call(monkeypatch, texts, live, expected):
    monkeypatch.setattr(ac.at, "run_tool", _fake_run_tool(texts))
    c = ac.classify_call(None, "search_spans", {}, live, len, STORES)
    assert (c["class"], c["diagnosis"]) == expected


def test_subsets_cover_known_transforms():
    assert ac._subsets() == [Z, E, ZE] and set(ac.JAEGER_TRANSFORMS) == {"error_tag", "zero_duration"}
    assert ac.KNOWN == "zero_duration"


def _run(turns, outputs, cid="inc-x"):
    return {"cases": [cid], "turns": {cid: turns}, "outputs": {cid: outputs}}


def _t(i, raw, kind="action"):
    return {"turn": i, "raw_output": raw, "kind": kind}


def test_divergence_identical():
    f = _run([_t(0, "a"), _t(1, "b"), _t(2, "ans", "answer")], {0: {"text": "o0"}, 1: {"text": "o1"}})
    d = ac.model_divergence(f, f)["inc-x"]
    assert d == {"model_diverged": False, "diverged_turn": None, "output_differs_at": None, "turns_compared": 3,
                 "turns_file": 3, "turns_live": 3}


def test_divergence_model_after_same_outputs():
    f = _run([_t(0, "a"), _t(1, "b")], {0: {"text": "o0"}})
    live = _run([_t(0, "a"), _t(1, "B")], {0: {"text": "o0"}})
    d = ac.model_divergence(f, live)["inc-x"]
    assert d["model_diverged"] is True and d["diverged_turn"] == 1 and d["output_differs_at"] is None


def test_divergence_stops_at_output_difference():
    f = _run([_t(0, "a"), _t(1, "b")], {0: {"text": "o0"}})
    live = _run([_t(0, "a"), _t(1, "DIFFERENT")], {0: {"text": "o0 live"}})
    d = ac.model_divergence(f, live)["inc-x"]
    assert d["model_diverged"] is False and d["output_differs_at"] == 0 and d["turns_compared"] == 1


def test_divergence_extra_turn_counts():
    f = _run([_t(0, "a")], {0: {"text": "o0"}})
    live = _run([_t(0, "a"), _t(1, "b")], {0: {"text": "o0"}})
    d = ac.model_divergence(f, live)["inc-x"]
    assert d["model_diverged"] is True and d["diverged_turn"] == 1


def test_divergence_skips_cases_missing_in_file():
    f = _run([_t(0, "a")], {}, cid="inc-other")
    live = _run([_t(0, "a")], {})
    assert ac.model_divergence(f, live) == {}


def test_read_run_from_records(tmp_path):
    d = new_run("agent", ("pilot",), 1, root=tmp_path, model_id="m", provider="gemini",
                settings={"model": "gemini-3.5-flash-lite", "store": "LiveStore", "prompt_sha256": "p"})
    out = {"row": {"end_reason": "answer"},
           "turns": [{"turn": 1, "kind": "answer", "raw_output": "r1"},
                     {"turn": 0, "kind": "action", "raw_output": "r0", "tool": "list_services", "call": "list_services()",
                      "action": {"args": {}}}],
           "tool_outputs": [{"turn": 0, "call": "list_services()", "text": "t0"}]}
    append_agent_case(d, "inc-x", out)
    r = ac.read_run(d)
    assert r["store"] == "LiveStore" and r["cases"] == ["inc-x"] and r["prompt_sha256"] == "p"
    assert [t["turn"] for t in r["turns"]["inc-x"]] == [0, 1] and r["outputs"]["inc-x"][0]["text"] == "t0"


def test_main_file_must_follow_live(tmp_path):
    with pytest.raises(SystemExit):
        ac.main(["--file", str(tmp_path), "--out", str(tmp_path / "o.json")])
