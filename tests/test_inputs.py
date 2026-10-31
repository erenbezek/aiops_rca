"""Girdi seviyeleri (HANDOFF 2026-10-30 P1c kartı 2. madde; DECISIONS 2026-10-31 "Ham kesme kuralı", "Boş ham girdi").
Özet: taşınan kod eski `trial_summary.build`'in çıktısını CI örneklerinde birebir üretir (`summary_expected.json`, eski
kodla üretildi). Ham: satır biçimi, pencere, seçim, sıra, kesme, boş girdi; sahte tokenizer (CI'da docker yok)."""
import json
import sys
from pathlib import Path

import pytest

from aiops_rca import inputs
from aiops_rca.cases import INCIDENTS, Case, alarm_ns
from aiops_rca.inputs import (DATA_BUDGET, RAW_LINE_CHARS, TRUNCATION_MARK, clock_ms, fit_lines, raw_input,
                              raw_line, summary_input)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ALARM = 1_800_000_000 * 10**9
SEC = 10**9


def words(text: str) -> int:
    """Sahte tokenizer: boşlukla ayrılmış parça sayısı."""
    return len(text.split())


# --- özet ---

def fixture_cases():
    for view in sorted((FIXTURES / "snapshots").iterdir()):
        label = json.loads((INCIDENTS / f"{view.name}.json").read_text(encoding="utf-8"))
        yield Case(view.name, view, alarm_ns(label["answer"]["injection_start"]))


def test_summary_matches_old_trial_summary_on_fixtures():
    expected = json.loads((FIXTURES / "summary_expected.json").read_text(encoding="utf-8"))
    got = {c.incident_id: summary_input(c, words) for c in fixture_cases()}
    assert sorted(got) == sorted(expected)
    for cid, inp in got.items():
        assert inp["text"] == expected[cid]
        assert (inp["level"], inp["empty"], inp["data_tokens"]) == ("summary", False, words(expected[cid]))


def test_trial_summary_uses_package_table():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import trial_summary
    assert trial_summary.build is inputs.summary_table
    assert trial_summary.TOP_MESSAGES == inputs.TOP_MESSAGES == 10


# --- ham: sahte görünüm ---

def res(svc):
    return {"attributes": [{"key": "service.name", "value": {"stringValue": svc}}]} if svc else {"attributes": []}


def log_doc(svc, t, sev, body=None, attrs=None, observed=None):
    rec = {"timeUnixNano": str(t), "severityNumber": sev}
    if observed is not None:
        rec["observedTimeUnixNano"] = str(observed)
    if body is not None:
        rec["body"] = {"stringValue": body}
    if attrs:
        rec["attributes"] = [{"key": k, "value": {"stringValue": v}} for k, v in attrs.items()]
    return {"resourceLogs": [{"resource": res(svc), "scopeLogs": [{"logRecords": [rec]}]}]}


def span_doc(svc, t, name, error=True, kind=2):
    sp = {"name": name, "kind": kind, "startTimeUnixNano": str(t), "endTimeUnixNano": str(t + 5 * 10**6),
          "status": {"code": 2} if error else {}}
    return {"resourceSpans": [{"resource": res(svc), "scopeSpans": [{"spans": [sp]}]}]}


def make_case(tmp_path, logs=(), spans=()):
    view = tmp_path / "inc-test"
    view.mkdir()
    (view / "logs.jsonl").write_text("".join(json.dumps(d) + "\n" for d in logs), encoding="utf-8")
    (view / "traces.jsonl").write_text("".join(json.dumps(d) + "\n" for d in spans), encoding="utf-8")
    (view / "metrics.jsonl").write_text("", encoding="utf-8")
    return Case("inc-test", view, ALARM)


def test_clock_ms_floors_to_millisecond():
    assert clock_ms(ALARM) == "08:00:00.000"  # 1.8e9 s = 2027-01-15 08:00:00 UTC
    assert clock_ms(ALARM + 1_999_999) == "08:00:00.001"
    assert clock_ms(ALARM - 1) == "07:59:59.999"


def test_raw_line_format_whitespace_and_length():
    assert raw_line(ALARM, "cart", "log", "  a\n\tb   c ") == "08:00:00.000 cart log a b c"
    assert raw_line(ALARM, "checkout", "error-span", "oteldemo.PaymentService/Charge") == \
        "08:00:00.000 checkout error-span oteldemo.PaymentService/Charge"
    long = raw_line(ALARM, "ad", "log", "x" * 1000)
    assert len(long) == RAW_LINE_CHARS and long.startswith("08:00:00.000 ad log xxx")


def test_raw_selection_window_and_order(tmp_path):
    case = make_case(tmp_path, logs=[
        log_doc("payment", ALARM + 30 * SEC, 13, "Payment request failed 4111 id=ab12"),  # WARN: girer, sayılar kalır
        log_doc("payment", ALARM + 20 * SEC, 17, "boom"),           # ERROR: girer
        log_doc("payment", ALARM + 10 * SEC, 9, "info line"),        # INFO: girmez
        log_doc("cart", ALARM - 600 * SEC, 13, "first second"),      # pencere başı dahil
        log_doc("cart", ALARM + 600 * SEC, 13, "after end"),         # pencere sonu hariç
        log_doc(None, ALARM + 5 * SEC, 13, attrs={"exception.message": "from attr"}),  # servis yok, mesaj alandan
        log_doc("ad", 0, 13, "observed time", observed=ALARM + 1 * SEC),  # zaman 0 → observed
    ], spans=[
        span_doc("checkout", ALARM + 20 * SEC, "PlaceOrder"),               # eşit zamanda metne göre
        span_doc("frontend", ALARM + 40 * SEC, "GET", error=False),         # hata değil: girmez
        span_doc("frontend-proxy", ALARM + 50 * SEC, "ingress", kind=3),    # her tür girer (CLIENT)
        span_doc("frontend", ALARM - 601 * SEC, "too early"),                # pencere öncesi
    ])
    inp = raw_input(case, words)
    assert inp["text"].split("\n") == [
        "07:50:00.000 cart log first second",
        "08:00:01.000 ad log observed time",
        "08:00:05.000 <unknown> log from attr",
        "08:00:20.000 checkout error-span PlaceOrder",
        "08:00:20.000 payment log boom",
        "08:00:30.000 payment log Payment request failed 4111 id=ab12",
        "08:00:50.000 frontend-proxy error-span ingress",
    ]
    assert (inp["level"], inp["empty"], inp["truncated"], inp["lines_total"], inp["lines_kept"]) == \
        ("raw", False, False, 7, 7)
    assert inp["data_tokens"] == words(inp["text"])


def test_raw_empty_input(tmp_path):
    case = make_case(tmp_path, logs=[log_doc("ad", ALARM, 9, "info")], spans=[span_doc("ad", ALARM, "ok", error=False)])
    inp = raw_input(case, lambda t: pytest.fail("empty input must not be tokenized"))
    assert inp == {"level": "raw", "incident_id": "inc-test", "lines_total": 0, "text": "", "data_tokens": 0,
                   "empty": True, "lines_kept": 0, "truncated": False}


def test_raw_deterministic(tmp_path):
    case = make_case(tmp_path, logs=[log_doc("a", ALARM + i * SEC, 13, f"m {i % 3}") for i in range(50)],
                     spans=[span_doc("b", ALARM + i * SEC, "s") for i in range(50)])
    assert raw_input(case, words) == raw_input(case, words)


# --- kesme ---

def test_fit_all_when_within_budget():
    lines = ["a b", "c d e"]
    assert fit_lines(lines, words, budget=5) == ("a b\nc d e", 2, 5)


def test_fit_truncates_from_start_with_mark():
    lines = [f"l{i} x y" for i in range(100)]  # satır başına 3 token; işaret 4
    text, kept, tokens = fit_lines(lines, words, budget=50)
    assert kept == 15 and tokens == 49  # 15×3 + 4 = 49 ≤ 50; 16 satır 52
    assert text.split("\n") == lines[:15] + [TRUNCATION_MARK]


def test_fit_is_maximal_prefix():
    lines = [" ".join(["w"] * (i % 4 + 1)) for i in range(60)]
    for budget in (10, 37, 64, 99):
        text, kept, tokens = fit_lines(lines, words, budget=budget)
        assert tokens <= budget and kept < len(lines)
        assert words("\n".join(lines[:kept + 1] + [TRUNCATION_MARK])) > budget


def test_fit_budget_too_small_for_mark():
    with pytest.raises(ValueError):
        fit_lines(["a b c"], words, budget=2)


def test_raw_input_truncated_flags(tmp_path):
    case = make_case(tmp_path, logs=[log_doc("svc", ALARM + i * SEC, 13, "x y") for i in range(30)])
    inp = raw_input(case, words, budget=40)  # satır: saat svc log x y = 5 token
    assert inp["truncated"] is True and inp["lines_total"] == 30 and inp["lines_kept"] == 7  # 7×5 + 4 = 39
    assert inp["text"].endswith("\n" + TRUNCATION_MARK) and inp["data_tokens"] <= 40


def test_constants_from_decisions():
    assert DATA_BUDGET == 5000 and RAW_LINE_CHARS == 500
    assert TRUNCATION_MARK == "[truncated: later lines omitted]"
    assert inputs.LEVELS == ("raw", "summary", "narrowed")


# --- daraltma ---

def nspan(sid, parent, t, kind=2, error=False, name="op", attrs=None):
    s = {"spanId": sid, "kind": kind, "name": name, "startTimeUnixNano": str(t),
         "endTimeUnixNano": str(t + 10 * 10**6), "status": {"code": 2} if error else {}}
    if parent:
        s["parentSpanId"] = parent
    if attrs:
        s["attributes"] = [{"key": k, "value": {"stringValue": v}} for k, v in attrs.items()]
    return s


def chain_case(tmp_path):
    """frontend → checkout → payment; payment alarmdan sonra hata ve WARN log verir; ad yalnız frontend'den çağrılır."""
    docs, logs = [], []
    for i in range(120):
        t = ALARM - 590 * SEC + i * 10 * SEC
        after = t >= ALARM
        spans = {
            "frontend": [nspan(f"f{i}", None, t, name="GET /"),
                         nspan(f"fc{i}", f"f{i}", t, kind=3, name="PlaceOrder", attrs={"server.address": "checkout"}),
                         nspan(f"fa{i}", f"f{i}", t, kind=3, name="GetAds", attrs={"server.address": "ad"})],
            "checkout": [nspan(f"c{i}", f"fc{i}", t, name="PlaceOrder", error=after),
                         nspan(f"cp{i}", f"c{i}", t, kind=3, name="Charge", attrs={"server.address": "payment"},
                               error=after)],
            "payment": [nspan(f"p{i}", f"cp{i}", t, name="Charge", error=after)],
            "ad": [nspan(f"a{i}", f"fa{i}", t, name="GetAds")]}
        docs.append({"resourceSpans": [{"resource": res(s), "scopeSpans": [{"spans": sp}]} for s, sp in spans.items()]})
        if after:
            logs.append(log_doc("payment", t, 13, f"charge failed card {i}"))
            if i % 2:
                logs.append(log_doc("payment", t, 17, "token invalid"))
    case = make_case(tmp_path, logs=logs, spans=docs)
    return case


def test_narrowed_format(tmp_path):
    case = chain_case(tmp_path)
    inp = inputs.narrowed_input(case, words)
    data = json.loads(inp["text"])
    assert (inp["level"], inp["empty"]) == ("narrowed", False) and inp["data_tokens"] == words(inp["text"])
    assert list(data) == ["alarm_time_utc", "window_minutes", "candidates", "calls"]
    names = [b["service"] for b in data["candidates"]]
    assert names == sorted(names) == inp["candidates"] == ["ad", "checkout", "frontend", "payment"]  # 4 servis var
    assert data["calls"] == [["checkout", "payment"], ["frontend", "ad"], ["frontend", "checkout"]]
    by = {b["service"]: b for b in data["candidates"]}
    # servis satırı özetteki satırın aynısı
    summary = {r["service"]: r for r in json.loads(summary_input(case, words)["text"])["services"]}
    for svc, b in by.items():
        assert {k: v for k, v in b.items() if k not in ("operations", "callers", "logs")} == summary[svc]
    pay = by["payment"]
    assert [o["operation"] for o in pay["operations"]] == ["Charge"]
    assert pay["operations"][0]["error_rate_before"] == 0.0 and pay["operations"][0]["error_rate_after"] == 1.0
    assert [(c["caller"], c["operation"]) for c in pay["callers"]] == [("checkout", "Charge")]
    assert pay["logs"] == [{"message": "charge failed card <n>", "count_before": 0, "count_after": 60},
                           {"message": "token invalid", "count_before": 0, "count_after": 30}]
    assert by["frontend"]["callers"] == [] and by["frontend"]["logs"] == []
    for b in data["candidates"]:  # daraltmanın grubu, puanı, sırası yok
        assert not {"group", "score", "max_strength", "signals", "rank"} & set(b)


def test_narrowed_logs_capped_at_three(tmp_path):
    case = chain_case(tmp_path)
    extra = [log_doc("payment", ALARM + k * SEC, 13, f"msg{chr(97 + k)}") for k in range(5)]
    with (case.view / "logs.jsonl").open("a", encoding="utf-8") as f:
        f.write("".join(json.dumps(d) + "\n" for d in extra))
    pay = {b["service"]: b for b in json.loads(inputs.narrowed_input(case, words)["text"])["candidates"]}["payment"]
    assert len(pay["logs"]) == inputs.TOP_CANDIDATE_LOGS == 3


def test_narrowed_fixtures_reproduce_expected():
    got = {c.incident_id: inputs.narrowed_input(c, words)["text"] for c in fixture_cases()}
    assert got == json.loads((FIXTURES / "narrowed_expected.json").read_text(encoding="utf-8"))
