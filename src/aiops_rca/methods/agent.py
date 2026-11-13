"""P2b ajan döngüsü (HANDOFF 2026-11-12 P2b kartı, 1. madde önerisi ve planlama düzeltmeleri; DECISIONS 2026-11-09
"Ajan yapısı", "P2'de model", "çağrı bütçesi", 2026-11-12 "JSON eylem şeması", "geçmiş kodla kırpılır", "daraltma
yok", "takma ad yok").

Vaka başına:
1. Mesajlar: sistem (P1'in sistem istemi), görev (alarm anı, pencere, araç tanımları `agent_tools.TOOLS`'tan, kurallar,
   eylem biçimi; kök tanımı P1'den birebir).
2. Her tur: katı JSON eylem şeması (`ACTION_FORMAT`) — bir araç + parametreler ya da "answer". Eylem kodla da
   doğrulanır (`validate_action`); şema dışı eylem yeniden sorulmaz (`schema_action`).
3. Araç `agent_tools.run_tool` ile; sonuç `user` mesajı olarak geri döner (sağlayıcıların araç rolü yok). Geçersiz
   parametre araç sonucudur ve adım sayılır. Okuyucunun altyapı hatası (HTTP, Jaeger dilim hatası) modele gösterilmez,
   vaka `store_error` ile biter (gösterilseydi dosya ↔ canlı farkı yaratırdı).
4. En çok `MAX_TOOL_CALLS` araç; sonra (ya da model "answer" deyince) cevap turu: P1'in `ANSWER_SCHEMA`'sı ve cevap
   talimatı birebir; `validate_answer`. Şema dışı cevap yeniden sorulmaz (`schema_answer`).
5. Bütçe: her istekten önce tam mesaj (sohbet şablonu dahil) yerel Qwen tokenizer'ıyla ≤ `TOTAL_BUDGET`. Sığmazsa en
   eski araç sonucunun metni tek satırlık ize iner (`fit_history`), sonra bir sonraki; son araç sonucu hep durur;
   modelin eylem JSON'ları düşmez. Yine sığmazsa vaka `budget` ile biter.

Satır P1 kayıt biçiminde (`evaluate score` değişmeden çalışır) + `end_reason`, `n_tool_calls`, `n_requests`.
Tur kaydı (`turns`) ve modele giden araç çıktılarının metni (`tool_outputs`) ayrı döner; koşu klasörüne çağıran yazar.
"""
from __future__ import annotations

import functools
import hashlib
import json
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator

from aiops_rca import agent_tools as at
from aiops_rca.answer import validate_answer
from aiops_rca.cases import Case
from aiops_rca.llm_client import ENDPOINTS, IMAGE, MODELS, MODELS_DIR, LocalServer, Pacer, chat, count_tokens
from aiops_rca.methods.llm import (SYSTEM_PROMPT, TOKENIZER, TOTAL_BUDGET, USER_TEMPLATE, _checked_gguf,
                                   _template_tokens)

MAX_TOOL_CALLS = 8
TOOL_RESULT_TOKENS = 700  # öneri; pilot (a)'da ölçülür (HANDOFF 2026-11-12)
GEMINI_GAP = 4  # sn; Gemini istekleri arası (ücretsiz katmanın dakikalık sınırı); değer pilot (a)'da ölçülür
END_REASONS = ("answer", "step_limit", "budget", "schema_action", "schema_answer", "no_answer", "store_error")
DROPPED = "[earlier result dropped to fit the budget: {call} returned {lines} lines]"

# P1'in onaylı istem metninden birebir (DECISIONS 2026-11-01 "İstem metni"): kök tanımı ve cevap talimatı.
_P1 = USER_TEMPLATE.format(alarm_time="{alarm_time}", level_text="{level_text}", data="{data}")
ROOT_DEFINITION = _P1.split("\n\n")[1]
ANSWER_INSTRUCTIONS = _P1.split("\n\nGive exactly", 1)[1].split("\n\nData:", 1)[0]
ANSWER_INSTRUCTIONS = "Give exactly" + ANSWER_INSTRUCTIONS

# --- eylem şeması --------------------------------------------------------------------------------------------------

_ARG_TYPES = {}
for _spec in at.TOOLS.values():
    for _k, (_kind, _req, _doc) in _spec["params"].items():
        _ARG_TYPES[_k] = _kind
ACTION_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["reason", "action", "tool", "args"],
    "properties": {
        "reason": {"type": "string"},
        "action": {"type": "string", "enum": ["call_tool", "answer"]},
        "tool": {"type": ["string", "null"]},
        "args": {"type": "object", "additionalProperties": False, "required": list(at.ARG_FIELDS),
                 "properties": {k: {"type": [_ARG_TYPES[k], "null"]} for k in at.ARG_FIELDS}},
    },
}
ACTION_FORMAT = {"type": "json_schema", "json_schema": {"name": "agent_action", "strict": True, "schema": ACTION_SCHEMA}}


def validate_action(obj) -> list[str]:
    if not isinstance(obj, dict):
        return ["action is not a JSON object"]
    errors = []
    if set(obj) != {"reason", "action", "tool", "args"}:
        errors.append(f"action keys {sorted(obj)} != ['action', 'args', 'reason', 'tool']")
    if obj.get("action") not in ("call_tool", "answer"):
        errors.append(f"action {obj.get('action')!r} is not call_tool or answer")
    if not isinstance(obj.get("reason"), str):
        errors.append("reason is not a string")
    if obj.get("action") == "call_tool" and not isinstance(obj.get("tool"), str):
        errors.append("call_tool without a tool name")
    if not isinstance(obj.get("args"), dict):
        errors.append("args is not an object")
    return errors


# --- istem ---------------------------------------------------------------------------------------------------------

def tool_definitions() -> str:
    out = []
    for name, spec in at.TOOLS.items():
        params = spec["params"]
        sig = ", ".join(k + ("" if req else "?") for k, (_, req, _) in params.items())
        out.append(f"- {name}({sig}): {spec['description']}")
        for k, (kind, req, doc) in params.items():
            out.append(f"    {k} ({kind}{'' if req else ', optional'}): {doc}")
    return "\n".join(out)


TASK_TEMPLATE = """An alert fired at {alarm_time} (UTC). Investigate the telemetry of the shop with the tools below. \
Telemetry is available from {win_from} to {win_to} minutes relative to the alert (negative values are before the \
alert). Before the alert the shop was working normally; the problem shows after the alert. Times in tool results are relative to the alert: T-02:30.000 is 2 minutes 30 seconds before it.

{root_definition}

Tools:
{tools}

Each turn, answer with one JSON object only:
{{"reason": "<one short sentence>", "action": "call_tool" or "answer", "tool": "<tool name, or null when \
answering>", "args": {{{arg_list}}}}}
Put every argument name in "args"; use null for the ones the tool does not take. Call one tool per turn. You can \
call at most {max_calls} tools. When you know the root cause, or after {max_calls} tool calls, choose "answer"; you \
will then be asked for the final answer."""

RESULT_TEMPLATE = "Result of {call}:\n{text}\n({left} tool calls left)"
ANSWER_TURN = "Give your final answer.\n\n{instructions}"


def task_message(alarm_time: str, win_from: float, win_to: float) -> str:
    return TASK_TEMPLATE.format(alarm_time=alarm_time, win_from=f"{win_from:g}", win_to=f"{win_to:g}",
                                root_definition=ROOT_DEFINITION, tools=tool_definitions(),
                                arg_list=", ".join(f'"{k}": ...' for k in at.ARG_FIELDS), max_calls=MAX_TOOL_CALLS)


def answer_message() -> str:
    return ANSWER_TURN.format(instructions=ANSWER_INSTRUCTIONS)


def prompt_sha256() -> str:
    return hashlib.sha256(json.dumps([SYSTEM_PROMPT, TASK_TEMPLATE, RESULT_TEMPLATE, ANSWER_TURN, DROPPED,
                                      ROOT_DEFINITION, ANSWER_INSTRUCTIONS, tool_definitions()]).encode()).hexdigest()


def call_text(tool: str, args: dict) -> str:
    used = {k: v for k, v in (args or {}).items() if v is not None and k in at.TOOLS.get(tool, {}).get("params", {})}
    return f"{tool}(" + ", ".join(f"{k}={json.dumps(v)}" for k, v in used.items()) + ")"


def _alarm_time(case: Case) -> str:
    return datetime.fromtimestamp(case.alarm_ns / 1e9, tz=timezone.utc).isoformat(timespec="seconds")


def _window_minutes(store, case: Case) -> tuple[float, float]:
    lo, hi = store.window()
    a = -int(-(lo - case.alarm_ns) * 10 // at.MIN_NS) / 10  # içe doğru 0,1 dk'ya yuvarla
    b = int((hi - case.alarm_ns) * 10 // at.MIN_NS) / 10
    return a, b


# --- geçmiş ve bütçe -----------------------------------------------------------------------------------------------

def build_messages(task: str, steps: list[dict], dropped: set[int], tail: str | None = None) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
    for i, s in enumerate(steps):
        msgs.append({"role": "assistant", "content": s["action_text"]})
        msgs.append({"role": "user", "content": s["stub"] if i in dropped else s["result_message"]})
    if tail is not None:
        msgs.append({"role": "user", "content": tail})
    return msgs


def fit_history(task: str, steps: list[dict], tail: str | None, count: Callable[[list[dict]], int],
                budget: int = TOTAL_BUDGET) -> tuple[list[dict] | None, set[int], int]:
    """En eskiden başlayarak araç sonuçlarını ize indirir, son sonuç hep durur. Döner: (mesajlar ya da sığmazsa None,
    ize inen adımlar, son sayım)."""
    dropped: set[int] = set()
    while True:
        msgs = build_messages(task, steps, dropped, tail)
        n = count(msgs)
        if n <= budget:
            return msgs, dropped, n
        candidates = [i for i in range(len(steps) - 1) if i not in dropped]  # son adım hep durur
        if not candidates:
            return None, dropped, n
        dropped.add(candidates[0])


# --- yöntem --------------------------------------------------------------------------------------------------------

@contextmanager
def agent_method(label: str, store_factory: Callable[[Case], object], *, models_dir=MODELS_DIR,
                 base: str | None = None, chat_url: str | None = None, key: str | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> Iterator[tuple[Callable[[Case], dict], dict]]:
    """(vaka → {"row", "turns", "tool_outputs"}, `run.json` ayarları). `base` verilirse sunucu açılmaz (testler)."""
    if label not in MODELS:
        raise ValueError(f"unknown model {label!r}")
    spec = MODELS[label]
    server_label = label if spec.provider == "local" else TOKENIZER
    settings = {"max_tokens": spec.max_tokens, "extra": spec.extra, "prompt_sha256": prompt_sha256(),
                "total_budget": TOTAL_BUDGET, "max_tool_calls": MAX_TOOL_CALLS,
                "tool_result_tokens": TOOL_RESULT_TOKENS, "image": IMAGE, "gguf": MODELS[server_label].gguf,
                "gguf_sha256": _checked_gguf(server_label, models_dir)}
    if spec.provider != "local":
        settings["tokenizer"] = TOKENIZER
    gap = {"groq": 65, "gemini": GEMINI_GAP}.get(spec.provider)
    if gap:
        settings["request_gap_s"] = gap
    pacer = Pacer(gap, sleep=sleep) if gap else None
    with ExitStack() as stack:
        if base is None:
            base = stack.enter_context(LocalServer(MODELS[server_label].gguf, models_dir=models_dir)).base
        url = f"{base}/v1/chat/completions" if spec.provider == "local" else (chat_url or ENDPOINTS[spec.provider])
        count_text = functools.partial(count_tokens, base)
        count_msgs = functools.partial(_template_tokens, base)

        def request(msgs, **kw):
            t0 = clock()
            if pacer:
                pacer.wait()
            waited = clock() - t0  # gerçekten beklenen süre
            rec = chat(spec, msgs, url=url, key=key, sleep=sleep, **kw)
            if pacer:
                pacer.done()
            return {**rec, "wait_s": round(waited, 3)}

        def ask(case: Case) -> dict:
            return run_case(case, store_factory(case), request, count_text, count_msgs, clock)

        yield ask, settings


def _tokens(rec: dict) -> dict:
    t = rec.get("tokens") or {}
    return {"input": t.get("input") or 0, "output": t.get("output") or 0}


def run_case(case: Case, store, request, count_text, count_msgs, clock=time.monotonic) -> dict:
    t_start = clock()
    lo_min, hi_min = _window_minutes(store, case)
    task = task_message(_alarm_time(case), lo_min, hi_min)
    steps, turns, outputs = [], [], []
    tok = {"input": 0, "output": 0}
    model_s = wait_s = 0.0
    row = {"input_status": "ok", "answer": None, "schema_valid": None, "schema_errors": [], "raw_output": None,
           "finish_reason": None, "attempts": [], "tokens": None, "duration_s": None, "no_answer": False,
           "end_reason": None, "n_tool_calls": 0, "n_requests": 0}

    def finish(reason: str, **kw) -> dict:
        # Süre: vakanın duvar saati, istek aralığı beklemesi hariç (sağlayıcı sınırı, yöntemin işi değil).
        row.update(kw, end_reason=reason, n_tool_calls=len(steps), tokens=tok,
                   duration_s=round(clock() - t_start - wait_s, 3), model_s=round(model_s, 3), wait_s=round(wait_s, 3))
        return {"row": row, "turns": turns, "tool_outputs": outputs}

    def turn(kind: str, msgs, n_local, dropped, rec) -> dict:
        nonlocal model_s, wait_s
        row["n_requests"] += 1
        wait_s += rec.get("wait_s") or 0
        for k, v in _tokens(rec).items():
            tok[k] += v
        model_s += rec.get("duration_s") or 0
        t = {"turn": len(turns), "kind": kind, "input_tokens_local": n_local, "dropped": sorted(dropped),
             "n_messages": len(msgs), "raw_output": rec.get("raw_output"), "schema_valid": rec.get("schema_valid"),
             "schema_errors": rec.get("schema_errors"), "finish_reason": rec.get("finish_reason"),
             "tokens": rec.get("tokens"), "duration_s": rec.get("duration_s"), "attempts": rec.get("attempts"),
             "error": rec.get("error")}
        turns.append(t)
        return t

    forced = False
    while True:
        if len(steps) >= MAX_TOOL_CALLS:
            forced = True
            break
        msgs, dropped, n_local = fit_history(task, steps, None, count_msgs)
        if msgs is None:
            return finish("budget", input_status="over_budget")
        rec = request(msgs, response_format=ACTION_FORMAT, validate=validate_action)
        t = turn("action", msgs, n_local, dropped, rec)
        if rec.get("error") is not None:
            return finish("no_answer", no_answer=True, schema_errors=rec.get("schema_errors"))
        if not rec.get("schema_valid"):
            return finish("schema_action", schema_valid=False, schema_errors=rec.get("schema_errors"),
                          raw_output=rec.get("raw_output"))
        act = rec["answer"]
        t["action"] = act
        if act["action"] == "answer":
            break
        call = call_text(act["tool"], act["args"])
        try:
            res = at.run_tool(store, case, act["tool"], act["args"], count_text, TOOL_RESULT_TOKENS)
        except (OSError, RuntimeError) as e:  # okuyucunun altyapı hatası: modele gösterilmez
            t["store_error"] = f"{type(e).__name__}: {e}"[:500]
            return finish("store_error", no_answer=True, schema_errors=[t["store_error"]])
        left = MAX_TOOL_CALLS - len(steps) - 1
        result_message = RESULT_TEMPLATE.format(call=call, text=res.text, left=left)
        stub = DROPPED.format(call=call, lines=res.lines_shown)
        sha = hashlib.sha256(res.text.encode()).hexdigest()
        t.update(tool=act["tool"], call=call, tool_output_sha256=sha, tool_output_tokens=count_text(res.text),
                 tool_lines_shown=res.lines_shown, tool_lines_total=res.lines_total, tool_truncated=res.truncated,
                 tool_error=res.error)
        outputs.append({"turn": t["turn"], "call": call, "text": res.text})
        steps.append({"action_text": rec["raw_output"], "result_message": result_message, "stub": stub})

    msgs, dropped, n_local = fit_history(task, steps, answer_message(), count_msgs)
    if msgs is None:
        return finish("budget", input_status="over_budget")
    rec = request(msgs)  # P1'in cevap şeması ve doğrulayıcısı
    turn("answer", msgs, n_local, dropped, rec)
    reason = "step_limit" if forced else "answer"
    common = {k: rec.get(k) for k in ("raw_output", "finish_reason", "attempts")}
    if rec.get("error") is not None:
        return finish("no_answer", no_answer=True, schema_errors=rec.get("schema_errors"), **common)
    if not rec.get("schema_valid"):
        return finish("schema_answer", schema_valid=False, schema_errors=rec.get("schema_errors"), **common)
    return finish(reason, answer=rec["answer"], schema_valid=True, schema_errors=[], **common)
