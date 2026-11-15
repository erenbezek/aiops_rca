"""`tools/agent_live.py` (P2c 2. madde (d); canlı kararı DECISIONS 2026-11-15): bir oynatmada birden çok model, her
oynatma denemesinden önce yerel sunucu yeniden açılır, başta takas denetimi; sahte yığınla (Docker, Gemini ve yerel
sunucu yok). Gerçek oynatma CI'da koşmaz; burada yalnız koşucunun kararları ve kaydı."""
from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import agent_live  # noqa: E402

from aiops_rca.cases import load_cases  # noqa: E402

GEM, QW = "gemini-3.5-flash-lite", "qwen3.5-4b"
OK = {"restarts": 0, "oom_killed": False, "status": "running", "exit_code": 0}
OOM = {"restarts": 0, "oom_killed": True, "status": "exited", "exit_code": 137}
BASE = agent_live.LocalServer(agent_live.MODELS[agent_live.TOKENIZER].gguf).base


class FakeWorld:
    """Oynatma sonuçları (`replays`: 0 geçti, 1 kaldı), her model koşusundan sonra OOM olup olmadığı (`oom`:
    (oynatma no, model) kümesi) ve boş takas (`swap`, GB)."""

    def __init__(self, monkeypatch, tmp_path, replays=(0, 0), oom=(), swap=4.0):
        self.replays, self.oom, self.calls, self.n = list(replays), set(oom), [], 0
        self.current_model = None
        self.server_up = False
        sc = agent_live.sc
        monkeypatch.setattr(sc, "replay_case", self.replay_case)
        monkeypatch.setattr(sc, "replay_compose", self.replay_compose)
        monkeypatch.setattr(sc, "volume_sizes", lambda: {"otel_live_x": "1GB"})
        monkeypatch.setattr(sc, "container_states", self.container_states)
        monkeypatch.setattr(sc, "mem_mib", lambda names: {n: 100.0 for n in names})
        monkeypatch.setattr(agent_live.sr, "swap_free_gb", lambda: swap)
        monkeypatch.setattr(agent_live, "_open_server", self.open_server)
        monkeypatch.setattr(agent_live, "agent_method", self.agent_method)
        self.root = tmp_path

    def open_server(self, stack):
        assert not self.server_up, "server opened twice without closing"
        self.server_up = True
        self.calls.append(("server_open",))

        def close():
            self.server_up = False
            self.calls.append(("server_close",))

        stack.callback(close)
        return BASE

    def replay_case(self, view, keep_up, result=None):
        assert self.server_up, "replay without a fresh server"
        self.n += 1
        d = self.root / f"replay-{self.n}"
        d.mkdir()
        result.update(dir=d, rec={"mem_peak_mib": {"otel-replay-jaeger-1": 1000.0 + self.n}})
        self.calls.append(("replay", view.name))
        return self.replays.pop(0)

    def replay_compose(self, args, view):
        self.calls.append(("down", view.name))
        return type("P", (), {"returncode": 0})()

    def container_states(self, names):
        assert agent_live.LOCAL_NAME in names
        bad = (self.n, self.current_model) in self.oom
        return {n: (OOM if bad and n == "otel-replay-jaeger-1" else OK) for n in names}

    @contextlib.contextmanager
    def agent_method(self, label, store_factory, base=None):
        assert base == BASE

        def ask(case):
            assert self.server_up
            self.current_model = label
            self.calls.append(("ask", label, case.incident_id))
            row = {"end_reason": "answer", "answer": None, "duration_s": 1.0}
            return {"row": row, "turns": [{"turn": 0, "kind": "action"}],
                    "tool_outputs": [{"turn": 0, "call": "list_services()", "text": f"{label} x"}]}

        yield ask, {"prompt_sha256": "p"}


def _cases(n=1):
    return load_cases(("pilot",))[:n]


def _read(root, model):
    d = next(p for p in sorted(root.glob("*-agent*"))
             if json.loads((p / "run.json").read_text())["settings"]["model"] == model)
    rows = [json.loads(x) for x in (d / "responses.jsonl").open()] if (d / "responses.jsonl").exists() else []
    return d, rows, json.loads((d / "live.json").read_text())


def test_single_model_record(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path)
    case = _cases()[0]
    assert agent_live.run([GEM], [case], tmp_path / "out") == 0
    d, rows, live = _read(tmp_path / "out", GEM)
    assert [c[0] for c in w.calls] == ["server_open", "replay", "ask", "down", "server_close"]
    assert len(rows) == 1 and rows[0]["attempts_live"] == 1 and rows[0]["replay_dir"].endswith("replay-1")
    assert rows[0]["jaeger_peak_mib"] == {"replay": 1001.0, "agent": None}
    a = live[case.incident_id]
    assert a["replayed"] is True and len(a["attempts"]) == 1
    assert {"attempt", "replay_dir", "replay_valid", "agent_s", "mem_peak_mib", "containers_ok", "end_reason",
            "down_exit", "replay_volumes_left", "valid", "server_started_utc", "llm_mem_mib"} <= set(a["attempts"][0])
    assert a["attempts"][0]["llm_mem_mib"] == {"start": 100.0, "end": 100.0}
    assert a["attempts"][0]["server_started_utc"].endswith("Z")
    assert (d / "turns.jsonl").exists() and (d / "tool_outputs" / f"{case.incident_id}.jsonl").exists()
    assert json.loads((d / "run.json").read_text())["settings"]["store"] == "LiveStore"


def test_two_models_one_replay_in_order(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path)
    cases = _cases(2)
    assert agent_live.run([GEM, QW], cases, tmp_path / "out") == 0
    asks = [c for c in w.calls if c[0] in ("replay", "ask")]
    assert asks == [("replay", cases[0].incident_id), ("ask", GEM, cases[0].incident_id),
                    ("ask", QW, cases[0].incident_id), ("replay", cases[1].incident_id),
                    ("ask", GEM, cases[1].incident_id), ("ask", QW, cases[1].incident_id)]
    for m in (GEM, QW):
        d, rows, live = _read(tmp_path / "out", m)
        assert [r["incident_id"] for r in rows] == [c.incident_id for c in cases]
        assert all(r["attempts_live"] == 1 for r in rows)
        out = [json.loads(x) for x in (d / "tool_outputs" / f"{cases[0].incident_id}.jsonl").open()]
        assert out[0]["text"] == f"{m} x"  # her model kendi klasörüne


def test_server_reopened_before_each_case(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path)
    cases = _cases(2)
    assert agent_live.run([GEM, QW], cases, tmp_path / "out") == 0
    one = ["server_open", "replay", "ask", "ask", "down", "server_close"]
    assert [c[0] for c in w.calls] == one * 2 and not w.server_up


def test_oom_during_second_model_reruns_only_it(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path, oom={(1, QW)})
    case = _cases()[0]
    assert agent_live.run([GEM, QW], [case], tmp_path / "out") == 0
    assert [c for c in w.calls if c[0] == "ask"] == [("ask", GEM, case.incident_id), ("ask", QW, case.incident_id),
                                                       ("ask", QW, case.incident_id)]
    assert [c[0] for c in w.calls] == ["server_open", "replay", "ask", "ask", "down", "server_close",
                                       "server_open", "replay", "ask", "down", "server_close"]
    _, g_rows, g_live = _read(tmp_path / "out", GEM)
    _, q_rows, q_live = _read(tmp_path / "out", QW)
    assert g_rows[0]["attempts_live"] == 1 and len(g_live[case.incident_id]["attempts"]) == 1
    assert q_rows[0]["attempts_live"] == 2 and q_rows[0]["replay_dir"].endswith("replay-2")
    first = q_live[case.incident_id]["attempts"][0]
    assert first["containers_ok"] is False and first["valid"] is False
    assert all("server_started_utc" in a for a in q_live[case.incident_id]["attempts"])


def test_oom_during_first_model_skips_second_and_reruns_both(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path, oom={(1, GEM)})
    case = _cases()[0]
    assert agent_live.run([GEM, QW], [case], tmp_path / "out") == 0
    assert [c[1] for c in w.calls if c[0] == "ask"] == [GEM, GEM, QW]
    _, _, q_live = _read(tmp_path / "out", QW)
    first = q_live[case.incident_id]["attempts"][0]
    assert first["problem"] == "stack broken before this model" and first["valid"] is False
    for m in (GEM, QW):
        _, rows, _ = _read(tmp_path / "out", m)
        assert rows[0]["attempts_live"] == 2


def test_twice_broken_is_not_replayed(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path, oom={(1, QW), (2, QW)})
    case = _cases()[0]
    assert agent_live.run([GEM, QW], [case], tmp_path / "out") == 1
    _, q_rows, q_live = _read(tmp_path / "out", QW)
    _, g_rows, g_live = _read(tmp_path / "out", GEM)
    assert q_rows == [] and q_live[case.incident_id]["replayed"] is False
    assert len(g_rows) == 1 and g_live[case.incident_id]["replayed"] is True
    assert w.n == 2


def test_replay_failure_twice(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path, replays=(1, 1))
    case = _cases()[0]
    assert agent_live.run([GEM, QW], [case], tmp_path / "out") == 1
    assert not [c for c in w.calls if c[0] == "ask"] and [c[0] for c in w.calls].count("down") == 2
    assert [c[0] for c in w.calls].count("server_close") == 2 and not w.server_up
    for m in (GEM, QW):
        _, rows, live = _read(tmp_path / "out", m)
        assert rows == [] and live[case.incident_id]["replayed"] is False
        assert [a["problem"] for a in live[case.incident_id]["attempts"]] == ["replay_case failed"] * 2
        assert all("llm_mem_mib" not in a and "server_started_utc" in a for a in live[case.incident_id]["attempts"])


def test_volume_left_blocks_rows(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path)
    monkeypatch.setattr(agent_live.sc, "volume_sizes", lambda: {agent_live.sc.REPLAY_PROJECT + "_jaeger-data": "1"})
    case = _cases()[0]
    assert agent_live.run([GEM], [case], tmp_path / "out") == 1
    _, rows, live = _read(tmp_path / "out", GEM)
    assert rows == [] and w.n == 2 and live[case.incident_id]["attempts"][0]["replay_volumes_left"]


@pytest.mark.parametrize("swap", [1.99, None])
def test_low_swap_starts_nothing(monkeypatch, tmp_path, capsys, swap):
    w = FakeWorld(monkeypatch, tmp_path, swap=swap)
    assert agent_live.run([GEM, QW], _cases(2), tmp_path / "out") == 2
    assert w.calls == [] and not (tmp_path / "out").exists()
    assert "swap free" in capsys.readouterr().err


def test_swap_at_threshold_starts(monkeypatch, tmp_path):
    w = FakeWorld(monkeypatch, tmp_path, swap=float(agent_live.sr.MIN_SWAP_FREE_START_GB))
    assert agent_live.run([GEM], _cases(), tmp_path / "out") == 0 and w.n == 1


@pytest.mark.parametrize("models", ["qwen3.5-2b", f"{GEM},{GEM}", "nope", f"{GEM},qwen3.5-9b"])
def test_main_rejects_bad_models(models, capsys):
    case = _cases()[0].incident_id
    assert agent_live.main(["--model", models, "--cases", case]) == 2
    assert "error: models" in capsys.readouterr().err
