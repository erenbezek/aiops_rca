"""P2b 3. madde: ajan döngüsü (`methods/agent.py`), sahte llama sunucusuyla (CI'da anahtar ve ağ yok).

Sahte sunucu (`test_llm_method.FakeLlama`): şablon = mesaj içeriklerinin birleşimi, token = boşlukla ayrılmış parça,
sohbet cevapları sırayla. Senaryolar: araç turu + gönüllü cevap, adım sınırı, kırpma (sınırda, sınır aşılınca, hiç
sığmazsa `budget`), şema dışı eylem ve cevap, geçersiz parametre, altyapı hatası (`store_error`), cevapsız; istek
biçimleri (eylem şeması / P1 cevap şeması), istemin P1 metnini birebir taşıması, kayıt dosyaları ve `evaluate score`.
"""
import json
import shutil

import pytest

from test_llm_method import FakeLlama, completion  # noqa: F401
from test_query import S, T0, log, make_store, span  # noqa: F401

from aiops_rca import evaluate
from aiops_rca.cases import INCIDENTS
from aiops_rca.llm_client import RESPONSE_FORMAT
from aiops_rca.methods import agent as ag
from aiops_rca.methods.llm import SYSTEM_PROMPT, USER_TEMPLATE

GOOD = {"candidates": [{"service": "cart", "confidence": 0.6, "evidence_path": ["cart", "frontend"],
                        "rationale": "errors start in cart"},
                       {"service": "frontend", "confidence": 0.3, "evidence_path": ["frontend"], "rationale": "r"},
                       {"service": "ad", "confidence": 0.1, "evidence_path": ["ad"], "rationale": "r"}],
        "unsure": False}
NULLS = {k: None for k in ag.at.ARG_FIELDS}


def act(tool=None, answer=False, **args):
    return {"reason": "look", "action": "answer" if answer else "call_tool", "tool": tool, "args": {**NULLS, **args}}


@pytest.fixture
def fake():
    made = []

    def make(*replies):
        f = FakeLlama(replies)
        made.append(f)
        return f
    yield make
    for f in made:
        f.close()


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(ag, "_checked_gguf", lambda label, models_dir: "sha-test")
    a = T0 + 15 * 60 * S
    st = make_store(tmp_path, spans={"cart": [span("t1", "c1", "GetCart", a + S, 20, status=2, message="boom")],
                                     "frontend": [span("t1", "f1", "GET /", a + S - 10, 30)]},
                    logs={"cart": [log(a + 2 * S, 17, "error", "cart storage down")]})
    return st


def run(fake_srv, store, case=None):
    with ag.agent_method("gemini-3.5-flash-lite", lambda c: store, base=fake_srv.base,
                         chat_url=fake_srv.base + "/v1/chat/completions", key="k", sleep=lambda s: None) as (ask, cfg):
        return ask(case or store.case), cfg


def test_prompt_carries_p1_text():
    assert ag.ROOT_DEFINITION in USER_TEMPLATE and ag.ROOT_DEFINITION.startswith("Find the root cause service:")
    assert ag.ANSWER_INSTRUCTIONS.replace("{", "{{").replace("}", "}}") in USER_TEMPLATE
    task = ag.task_message("2026-01-01T00:15:00+00:00", -12.5, 10.4)
    assert ag.ROOT_DEFINITION in task and "from -12.5 to 10.4 minutes" in task
    for name in ag.at.TOOLS:
        assert f"- {name}(" in task
    assert ag.answer_message().endswith(ag.ANSWER_INSTRUCTIONS)


def test_tool_turn_then_answer(world, fake):
    srv = fake(completion(act("list_services")), completion(act(answer=True)), completion(GOOD))
    out, cfg = run(srv, world)
    row = out["row"]
    assert (row["end_reason"], row["n_tool_calls"], row["n_requests"]) == ("answer", 1, 3)
    assert row["schema_valid"] and row["answer"] == GOOD and not row["no_answer"]
    assert row["tokens"] == {"input": 4500, "output": 360}
    assert 0 <= row["duration_s"] and 0 <= row["wait_s"] and row["model_s"] >= 0
    chats = srv.chats()
    assert [c["response_format"] for c in chats] == [ag.ACTION_FORMAT, ag.ACTION_FORMAT, RESPONSE_FORMAT]
    assert chats[0]["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    m = chats[1]["messages"]
    assert [x["role"] for x in m] == ["system", "user", "assistant", "user"]
    assert m[3]["content"].startswith("Result of list_services():\n2 services\n") and "(7 tool calls left)" in m[3]["content"]
    assert chats[2]["messages"][-1]["content"] == ag.answer_message()
    assert len(out["tool_outputs"]) == 1 and out["tool_outputs"][0]["call"] == "list_services()"
    assert [t["kind"] for t in out["turns"]] == ["action", "action", "answer"]
    assert out["turns"][0]["tool"] == "list_services" and out["turns"][0]["tool_output_sha256"]
    assert cfg["prompt_sha256"] == ag.prompt_sha256() and cfg["max_tool_calls"] == 8 and cfg["request_gap_s"] == 4


def test_step_limit(world, fake):
    calls = [completion(act("search_logs", from_min=-1, to_min=1))] * ag.MAX_TOOL_CALLS
    srv = fake(*calls, completion(GOOD))
    row = run(srv, world)[0]["row"]
    assert (row["end_reason"], row["n_tool_calls"], row["n_requests"]) == ("step_limit", 8, 9)
    assert srv.chats()[-1]["response_format"] == RESPONSE_FORMAT
    assert "(0 tool calls left)" in srv.chats()[-1]["messages"][-2]["content"]


def test_invalid_param_is_a_step(world, fake):
    srv = fake(completion(act("metric_series", service="nope", metric="cpu_pct", from_min=-1, to_min=0)),
               completion(act(answer=True)), completion(GOOD))
    out = run(srv, world)[0]
    assert out["row"]["n_tool_calls"] == 1 and out["turns"][0]["tool_error"]
    assert 'error: unknown service "nope"' in srv.chats()[1]["messages"][-1]["content"]


def test_schema_action_and_answer(world, fake):
    srv = fake(completion("not json"))
    row = run(srv, world)[0]["row"]
    assert (row["end_reason"], row["schema_valid"], row["n_requests"]) == ("schema_action", False, 1)
    srv = fake(completion({"reason": "r", "action": "call_tool", "tool": None, "args": NULLS}))
    assert run(srv, world)[0]["row"]["end_reason"] == "schema_action"
    srv = fake(completion(act(answer=True)), completion({"candidates": []}))
    row = run(srv, world)[0]["row"]
    assert (row["end_reason"], row["schema_valid"], row["answer"]) == ("schema_answer", False, None)


def test_no_answer(world, fake):
    srv = fake((400, {"error": {"message": "bad request"}}))
    row = run(srv, world)[0]["row"]
    assert (row["end_reason"], row["no_answer"]) == ("no_answer", True)


def test_store_error(world, fake):
    class Broken:
        def __init__(self, inner):
            self.inner, self.case = inner, inner.case

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def spans(self, *a, **k):
            raise OSError("jaeger: HTTP 503")

    srv = fake(completion(act("search_spans", from_min=-1, to_min=1)))
    out = run(srv, Broken(world), world.case)[0]
    assert (out["row"]["end_reason"], out["row"]["no_answer"]) == ("store_error", True)
    assert "jaeger: HTTP 503" in out["turns"][0]["store_error"] and len(srv.chats()) == 1  # modele gösterilmedi


def test_fit_history_drops_oldest_keeps_last():
    steps = [{"action_text": "a", "result_message": "r " * 50, "stub": "s"} for _ in range(3)]
    words = lambda msgs: sum(len(m["content"].split()) for m in msgs)  # noqa: E731
    size = lambda d, tail=None: words(ag.build_messages("t", steps, d, tail))  # noqa: E731
    msgs, dropped, n = ag.fit_history("t", steps, None, words, budget=size(set()))
    assert dropped == set() and n == size(set())
    msgs, dropped, n = ag.fit_history("t", steps, None, words, budget=size({0}))
    assert dropped == {0} and msgs[3]["content"] == "s" and msgs[-1]["content"] == steps[2]["result_message"]
    msgs, dropped, n = ag.fit_history("t", steps, "tail", words, budget=size({0, 1}, "tail"))
    assert dropped == {0, 1} and msgs[-1]["content"] == "tail" and msgs[-2]["content"] == steps[2]["result_message"]
    msgs, dropped, n = ag.fit_history("t", steps, None, words, budget=size({0, 1}) - 1)
    assert msgs is None and dropped == {0, 1}  # son sonuç düşmez: sığmıyor


def test_budget_end(world, fake, monkeypatch):
    real = ag.fit_history
    monkeypatch.setattr(ag, "fit_history",
                        lambda task, steps, tail, count, budget=None: real(task, steps, tail, count, budget=10))
    srv = fake()  # görev mesajı bile sığmaz: hiç istek gitmez
    row = run(srv, world)[0]["row"]
    assert (row["end_reason"], row["input_status"], row["n_requests"]) == ("budget", "over_budget", 0)
    assert srv.chats() == []


def test_trimming_in_a_run(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(ag, "_checked_gguf", lambda label, models_dir: "sha-test")
    a = T0 + 15 * 60 * S
    st = make_store(tmp_path, logs={"cart": [log(a + i * S, 17, "error", f"storage error number {i} in cart")
                                             for i in range(30)]})
    real = ag.fit_history

    def tight(task, steps, tail, count, budget=None):  # yalnız son sonuç tam kalırsa sığar
        need = count(ag.build_messages(task, steps, set(range(len(steps) - 1)), tail)) if steps else 0
        return real(task, steps, tail, count, budget=max(need + 5, ag.TOTAL_BUDGET if not steps else 0))
    monkeypatch.setattr(ag, "fit_history", tight)
    srv = fake(*[completion(act("search_logs", from_min=-1, to_min=1))] * 3, completion(act(answer=True)),
               completion(GOOD))
    out = run(srv, st)[0]
    assert out["row"]["end_reason"] == "answer" and out["row"]["n_tool_calls"] == 3
    m = srv.chats()[3]["messages"]
    stubs = [x for x in m if x["content"].startswith("[earlier result dropped to fit the budget: search_logs(")]
    assert len(stubs) == 2 and m[-1]["content"].startswith("Result of search_logs(")  # son sonuç duruyor
    assert out["turns"][3]["dropped"] == [0, 1] and out["turns"][2]["dropped"] == [0] and out["turns"][1]["dropped"] == []


def test_evaluate_run_and_score(tmp_path, fake, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(ag, "_checked_gguf", lambda label, models_dir: "sha-test")
    fixtures = Path(__file__).resolve().parent / "fixtures" / "snapshots"
    cid = "inc-0f31ed0e"
    inc = tmp_path / "incidents"
    inc.mkdir()
    shutil.copy(INCIDENTS / f"{cid}.json", inc / f"{cid}.json")
    srv = fake(completion(act("list_services")), completion(act(answer=True)), completion(GOOD))
    run_dir = evaluate.cmd_run("agent", ("pilot",), False, tmp_path / "runs", incidents=inc, snapshots=fixtures,
                               model="gemini-3.5-flash-lite",
                               llm_options={"base": srv.base, "chat_url": srv.base + "/v1/chat/completions",
                                            "key": "k", "sleep": lambda s: None})
    run = json.loads((run_dir / "run.json").read_text())
    assert run["method"] == "agent" and run["settings"]["store"] == "FileStore"
    rows = [json.loads(x) for x in (run_dir / "responses.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["end_reason"] == "answer"
    turns = [json.loads(x) for x in (run_dir / "turns.jsonl").read_text().splitlines()]
    assert len(turns) == 3 and all(t["incident_id"] == cid for t in turns)
    outs = [json.loads(x) for x in (run_dir / "tool_outputs" / f"{cid}.jsonl").read_text().splitlines()]
    assert len(outs) == 1 and outs[0]["text"].split("\n")[0].endswith("services")
    scores = evaluate.cmd_score(run_dir, False, incidents=inc, snapshots=fixtures)
    assert scores["cases"][0]["incident_id"] == cid and scores["table"]["all"]["n"] == 1
    with pytest.raises(ValueError):
        evaluate.cmd_run("agent", ("pilot",), False, tmp_path / "runs", incidents=inc, snapshots=fixtures)


# İstem metni Eren onaylı (HANDOFF 2026-11-13, P2b 3. madde; P1 "Onay 3" gibi). Değişirse yeniden onay ve kayıt.
# P2c-0 (pilot tasarım turu): A ve B metinleri Eren onaylı (HANDOFF 2026-11-13, P2c-0 2. madde); P2b'deki
# a2fa4331c47c2be2ad96176c1cb70cc641715a4aca4d014f15755ef37a6cf102.
PROMPT_SHA256 = "5e259201605b4f4742373adf4e8adc346a8d2aaad2ce652825469e173efb3f17"


def test_prompt_sha256_frozen():
    assert ag.prompt_sha256() == PROMPT_SHA256


def test_agent_live_rejects_unknown_and_test_cases(capsys):
    """Canlı mod gerçek yığın ister (CI'da yok); burada yalnız vaka reddi: pilot / dev dışı kimlik 2 ile döner."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import agent_live  # noqa: E402
    assert agent_live.main(["--model", "gemini-3.5-flash-lite", "--cases", "inc-nope"]) == 2
    test_ids = [p.stem for p in sorted(INCIDENTS.glob("inc-*.json"))
                if json.loads(p.read_text()).get("set") == "test"][:1]
    if test_ids:
        assert agent_live.main(["--model", "gemini-3.5-flash-lite", "--cases", test_ids[0]]) == 2
    assert "not valid pilot/dev cases" in capsys.readouterr().err


def test_pilot_report_reproduces():
    """`results/p2b_pilot.*` repodaki pilot koşularından bayt aynı yeniden üretilir (snapshot gerekmez)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import agent_report  # noqa: E402
    assert agent_report.main(["--check"]) == 0
    assert agent_report.main(["--report", "p2c0", "--check"]) == 0  # P2c-0 pilot tasarım turu
    assert agent_report.main(["--report", "p2c_dev", "--check"]) == 0  # P2c dev koşuları


# --- P2e B kolu: `narrowed_start` (HANDOFF 2026-11-28; planlamanın 2. madde ölçütleri (a)–(d)) ---

# B'nin istemi: A'nın parçaları + `NARROWED_START` (P1 metni birebir). Değişirse yeniden onay ve kayıt.
PROMPT_SHA256_NARROWED_START = "d237c17e93f82acf1bca8ee6b9e4efcca0e8500c73f41c7c12ea8365ef7bfd03"


def _fixture_cases():
    from pathlib import Path
    from aiops_rca.cases import Case, alarm_ns
    fixtures = Path(__file__).resolve().parent / "fixtures"
    for view in sorted((fixtures / "snapshots").iterdir()):
        label = json.loads((INCIDENTS / f"{view.name}.json").read_text(encoding="utf-8"))
        yield Case(view.name, view, alarm_ns(label["answer"]["injection_start"]))


def test_narrowed_start_is_p1_narrowed_input_byte_for_byte():
    """(a) Blok = P1'in daraltma açıklaması + "Data:" + P1'in daraltma girdisinin metni (CI örneklerinde donmuş
    `narrowed_expected.json` ve P1'in kullanıcı mesajı)."""
    from pathlib import Path
    from aiops_rca.methods import llm
    expected = json.loads((Path(__file__).resolve().parent / "fixtures" / "narrowed_expected.json").read_text())
    for case in _fixture_cases():
        block = ag.narrowed_start_text(case)
        assert block == llm.LEVEL_TEXT["narrowed"] + "\n\nData:\n" + expected[case.incident_id]
        p1_user = llm.build_messages("narrowed", "T", expected[case.incident_id])[1]["content"]
        assert p1_user.endswith("\n\nData:\n" + expected[case.incident_id]) and llm.LEVEL_TEXT["narrowed"] in p1_user


def test_fit_history_never_shortens_the_task():
    """(b) Bütçe dolunca yalnız araç sonuçları ize iner; görev (tablo dahil) her durumda birebir; görev bile sığmazsa
    kısaltılmaz, `None` (vaka `budget`)."""
    task = "task " + "table " * 400
    steps = [{"action_text": "a", "result_message": "r " * 300, "stub": "s"} for _ in range(6)]
    words = lambda msgs: sum(len(m["content"].split()) for m in msgs)  # noqa: E731
    full = words(ag.build_messages(task, steps, set()))
    for budget in range(full, 0, -97):
        msgs, dropped, n = ag.fit_history(task, steps, None, words, budget=budget)
        if msgs is None:
            assert budget < words(ag.build_messages(task, steps, set(range(len(steps) - 1))))
            continue
        assert msgs[1]["content"] == task and n <= budget


def test_narrowed_start_run_and_settings(tmp_path, fake, monkeypatch):
    """(a)–(c) uçtan uca, dosya modu: B'de her isteğin görev mesajı = A'nın görevi + blok (kırpma sırasında da);
    ayarlarda `narrowed_start` ve B'nin sha'sı. A'nın ayarlarında alan yok, sha donmuş değer."""
    from pathlib import Path
    monkeypatch.setattr(ag, "_checked_gguf", lambda label, models_dir: "sha-test")
    fixtures = Path(__file__).resolve().parent / "fixtures" / "snapshots"
    cid = "inc-0f31ed0e"
    inc = tmp_path / "incidents"
    inc.mkdir()
    shutil.copy(INCIDENTS / f"{cid}.json", inc / f"{cid}.json")
    real = ag.fit_history

    def tight(task, steps, tail, count, budget=None):  # 2. adımdan sonra en eski sonuç ize iner
        need = count(ag.build_messages(task, steps, set(range(len(steps) - 1)), tail)) if steps else 0
        return real(task, steps, tail, count, budget=max(need + 5, ag.TOTAL_BUDGET * 100 if not steps else 0))
    monkeypatch.setattr(ag, "fit_history", tight)
    opts = lambda srv: {"base": srv.base, "chat_url": srv.base + "/v1/chat/completions", "key": "k",  # noqa: E731
                        "sleep": lambda s: None}
    tasks = {}
    for b in (False, True):
        srv = fake(*[completion(act("list_services"))] * 3, completion(act(answer=True)), completion(GOOD))
        run_dir = evaluate.cmd_run("agent", ("pilot",), False, tmp_path / f"runs{b}", incidents=inc,
                                   snapshots=fixtures, model="gemini-3.5-flash-lite", llm_options=opts(srv),
                                   narrowed_start=b)
        settings = json.loads((run_dir / "run.json").read_text())["settings"]
        chats = srv.chats()
        tasks[b] = {c["messages"][1]["content"] for c in chats}
        assert len(tasks[b]) == 1 and len(chats) == 5
        if b:
            assert settings["narrowed_start"] is True and settings["prompt_sha256"] == PROMPT_SHA256_NARROWED_START
            assert any(m["content"].startswith("[earlier result dropped") for m in chats[3]["messages"])
        else:
            assert "narrowed_start" not in settings and settings["prompt_sha256"] == PROMPT_SHA256
    case = next(c for c in _fixture_cases() if c.incident_id == cid)
    (a_task,), (b_task,) = tasks[False], tasks[True]
    assert b_task == a_task + "\n\n" + ag.narrowed_start_text(case)
    assert ag.prompt_sha256(True) == PROMPT_SHA256_NARROWED_START != PROMPT_SHA256
    with pytest.raises(ValueError):
        evaluate.cmd_run("llm", ("pilot",), False, tmp_path / "x", incidents=inc, snapshots=fixtures,
                         model="gemini-3.5-flash-lite", level="narrowed", narrowed_start=True)


def test_narrowed_start_reads_only_the_snapshot(tmp_path, monkeypatch):
    """(d) Blok yalnız vakanın snapshot klasöründen okur: etiket dosyaları (`incidents/`) açılmaz."""
    import builtins
    import io
    from aiops_rca.cases import Case
    case = next(_fixture_cases())
    view = tmp_path / "view"
    shutil.copytree(case.view, view)
    copy = Case(case.incident_id, view, case.alarm_ns)
    want = ag.narrowed_start_text(case)
    opened = []
    real_open = builtins.open

    def spy(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)
    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    assert ag.narrowed_start_text(copy) == want
    assert opened and all(p.startswith(str(view)) for p in opened if p.endswith((".json", ".jsonl")))
    assert not any("incidents" in p for p in opened)
