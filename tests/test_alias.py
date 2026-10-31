"""Takma ad (HANDOFF 2026-10-31 P1c 4. adım planı). Özet: taşınan kurallar eski `trial_alias`'ın çıktısını CI
örneklerinde birebir üretir (`alias_summary_expected.json`, eski kod + onaylı iki adla üretildi). Üç seviye: yalnız
adlar ve metinlerdeki tanımlayıcılar değişir; ham satırlar aynı satırlar, aynı sıra; kontrol bozuk kopyaları yakalar."""
import json
import re
import sys
from pathlib import Path

import pytest

from aiops_rca import alias, inputs
from aiops_rca.alias import ALIASES, FORBIDDEN_TERMS, check_table, check_text, convert_message, convert_table
from aiops_rca.cases import INCIDENTS, Case, alarm_ns
from aiops_rca.inputs import TRUNCATION_MARK, raw_line

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
ALARM = 1_800_000_000 * 10**9
SEC = 10**9


def words(text: str) -> int:
    return len(text.split())


def chars(text: str) -> int:
    return len(text)


def fixture_cases():
    for view in sorted((FIXTURES / "snapshots").iterdir()):
        label = json.loads((INCIDENTS / f"{view.name}.json").read_text(encoding="utf-8"))
        yield Case(view.name, view, alarm_ns(label["answer"]["injection_start"]))


def res(svc):
    return {"attributes": [{"key": "service.name", "value": {"stringValue": svc}}]} if svc else {"attributes": []}


def log_doc(svc, t, body, sev=13):
    rec = {"timeUnixNano": str(t), "severityNumber": sev, "body": {"stringValue": body}}
    return {"resourceLogs": [{"resource": res(svc), "scopeLogs": [{"logRecords": [rec]}]}]}


def span_doc(svc, t, name):
    sp = {"name": name, "kind": 2, "startTimeUnixNano": str(t), "endTimeUnixNano": str(t + 5 * 10**6),
          "status": {"code": 2}}
    return {"resourceSpans": [{"resource": res(svc), "scopeSpans": [{"spans": [sp]}]}]}


def make_case(tmp_path, logs=(), spans=()):
    view = tmp_path / "inc-test"
    view.mkdir()
    (view / "logs.jsonl").write_text("".join(json.dumps(d) + "\n" for d in logs), encoding="utf-8")
    (view / "traces.jsonl").write_text("".join(json.dumps(d) + "\n" for d in spans), encoding="utf-8")
    (view / "metrics.jsonl").write_text("", encoding="utf-8")
    return Case("inc-test", view, ALARM)


# --- taşıma ve eşleme ---

def test_trial_alias_uses_package_rules():
    sys.path.insert(0, str(REPO / "tools"))
    import trial_alias
    assert trial_alias.ALIASES is alias.ALIASES
    assert trial_alias.RULES is alias.RULES
    assert trial_alias.convert_message is alias.convert_message
    assert trial_alias.unchanged_parts_kept is alias.unchanged_parts_kept


def test_aliases_match_glossary():
    row = next(line for line in (REPO / "docs" / "GLOSSARY.md").read_text(encoding="utf-8").splitlines()
               if line.startswith("| takma ad eşlemesi |"))
    pairs = re.findall(r"([a-z-]+) → ([a-z-]+)", row.split("|")[2])
    assert dict(pairs) == ALIASES and len(pairs) == len(ALIASES) == 18
    assert ALIASES["quote-gateway"] == "rate-gateway" and ALIASES["frontend-web"] == "storefront-web"
    assert len(set(ALIASES.values())) == len(ALIASES)  # iki gerçek ad aynı takma adı almaz
    assert not set(ALIASES.values()) & set(ALIASES)  # takma ad gerçek adlardan biri değil


def test_summary_matches_old_trial_alias_on_fixtures():
    expected = json.loads((FIXTURES / "alias_summary_expected.json").read_text(encoding="utf-8"))
    got = {c.incident_id: alias.summary_input(c, words) for c in fixture_cases()}
    assert sorted(got) == sorted(expected)
    for cid, inp in got.items():
        assert inp["text"] == expected[cid]
        assert (inp["level"], inp["empty"], inp["data_tokens"]) == ("summary", False, words(expected[cid]))


# --- CI örneklerinde üç seviye ---

def real_name_left(text: str) -> list[str]:
    """Takma adlı metinde gerçek adın tanımlayıcı biçimi ya da yasak terim (bağımsız arama, kurallardan değil)."""
    found = []
    for real in ALIASES:
        if "-" in real and re.search(rf"(?<![A-Za-z0-9]){real.replace('-', '[-_]')}(?![A-Za-z0-9])", text, re.I):
            found.append(real)
        if re.search(rf"(?<![A-Za-z0-9]){alias.camel(real)}(?:Service)", text):
            found.append(real)
    if "oteldemo." in text or FORBIDDEN_TERMS.search(text):
        found.append("prefix/forbidden")
    return found


@pytest.mark.parametrize("case", list(fixture_cases()), ids=lambda c: c.incident_id)
def test_fixture_levels_only_names_change(case):
    names = set(ALIASES.values()) | {alias.UNKNOWN_SERVICE}
    for level in ("summary", "narrowed"):
        real = getattr(inputs, f"{level}_input")(case, words)
        got = getattr(alias, f"{level}_input")(case, words)
        r, a = json.loads(real["text"]), json.loads(got["text"])
        assert check_table(r, a) == []
        assert not real_name_left(got["text"].replace('"', " "))
        rows = a["services"] if level == "summary" else a["candidates"]
        assert {x["service"] for x in rows} <= names
        if level == "narrowed":
            assert got["candidates"] == [ALIASES[c] for c in real["candidates"]]
            assert {n for pair in a["calls"] for n in pair} | {c["caller"] for b in a["candidates"]
                                                                 for c in b["callers"]} <= names
    real, got = inputs.raw_input(case, words), alias.raw_input(case, words)
    assert (got["lines_total"], got["lines_kept"], got["truncated"], got["alias_lines_dropped"]) == \
        (real["lines_total"], real["lines_kept"], real["truncated"], 0)
    assert got["empty"] == real["empty"]
    if real["empty"]:
        assert got["text"] == real["text"] == ""
        return
    for rl, al in zip(real["text"].split("\n"), got["text"].split("\n"), strict=True):
        rp, ap = rl.split(" ", 3), al.split(" ", 3)
        assert (ap[0], ap[2]) == (rp[0], rp[2]) and ap[1] == ALIASES.get(rp[1], rp[1])
        assert not real_name_left(al)


# --- ham ---

def test_raw_same_lines_real_order_converted_before_cut(tmp_path):
    long_text = "x" * 460 + " product-catalog down"  # gerçek satırda ad 500. karakterde kesilir
    case = make_case(tmp_path,
                     logs=[log_doc("cart", ALARM + SEC, "boom"), log_doc("ad", ALARM + SEC, "boom"),
                           log_doc(None, ALARM + 3 * SEC, "product_catalog unavailable"),
                           log_doc("payment", ALARM + 4 * SEC, long_text)],
                     spans=[span_doc("cart", ALARM + 2 * SEC, "oteldemo.CartService/GetCart")])
    got = alias.raw_input(case, words)
    lines = got["text"].split("\n")
    # gerçek sıra: aynı zamanda "ad" < "cart"; takma adla sıralansa basket önce gelirdi
    assert [ln.split(" ")[1] for ln in lines] == ["promotions", "basket", "basket", "<unknown>", "billing"]
    assert lines[2].endswith("basket error-span BasketService/GetCart")
    assert lines[3].endswith("<unknown> log inventory unavailable")
    assert lines[4] == raw_line(ALARM + 4 * SEC, "billing", "log", "x" * 460 + " inventory down")
    assert len(lines[4]) == inputs.RAW_LINE_CHARS and lines[4].endswith(" inventory down")
    real4 = inputs.raw_input(case, words)["text"].split("\n")[4]
    assert real4.endswith(" product-catalo")  # gerçekte kesik; takma adda tam
    assert (got["empty"], got["lines_kept"], got["truncated"], got["alias_lines_dropped"]) == (False, 5, False, 0)


def test_raw_drops_from_end_when_alias_text_longer(tmp_path):
    case = make_case(tmp_path, logs=[log_doc("ad", ALARM + i * SEC, f"m{i}") for i in range(3)])
    real = inputs.raw_input(case, chars, budget=10**6)
    budget = real["data_tokens"]  # gerçek metin tam sığar; "promotions" "ad"dan uzun
    real = inputs.raw_input(case, chars, budget=budget)
    got = alias.raw_input(case, chars, budget=budget)
    assert (real["lines_kept"], real["truncated"]) == (3, False)
    assert got["data_tokens"] == chars(got["text"]) <= budget
    assert got["truncated"] and got["text"].split("\n")[-1] == TRUNCATION_MARK
    assert 0 < got["alias_lines_dropped"] == 3 - got["lines_kept"] and got["lines_total"] == 3
    assert got["text"].split("\n")[:-1] == [raw_line(ALARM + i * SEC, "promotions", "log", f"m{i}")
                                            for i in range(got["lines_kept"])]


def test_raw_empty_stays_empty(tmp_path):
    got = alias.raw_input(make_case(tmp_path), words)
    assert (got["empty"], got["text"], got["data_tokens"], got["alias_lines_dropped"]) == (True, "", 0, 0)


def test_unknown_service_is_not_written(tmp_path):
    case = make_case(tmp_path, logs=[log_doc("mystery", ALARM + SEC, "boom")],
                     spans=[span_doc("mystery", ALARM + SEC, "op")])
    for fn in (alias.raw_input, alias.summary_input):
        with pytest.raises(ValueError, match="no alias for 'mystery'"):
            fn(case, words)


# --- kontrol (kasıtlı bozuk kopyalar) ---

def table():
    return {"alarm_time_utc": "2027-01-15T08:00:00+00:00",
            "services": [{"service": "cart", "requests_before": 3}, {"service": "ad", "requests_before": 4}],
            "top_warning_and_error_logs_after_alarm": [
                {"service": "cart", "message": "oteldemo.CartService failed for product-catalog", "count_after": 2}],
            "calls": [["cart", "ad"]]}


def test_check_accepts_converted_table():
    a = convert_table(table())
    assert check_table(table(), a) == []
    assert a["top_warning_and_error_logs_after_alarm"][0]["message"] == "BasketService failed for inventory"
    assert a["calls"] == [["basket", "promotions"]]


@pytest.mark.parametrize("break_it, expect", [
    (lambda a: a["services"][0].update(service="cart"), "expected 'basket'"),
    (lambda a: a["services"].reverse(), "expected 'basket'"),
    (lambda a: a["services"][1].update(requests_before=5), "value differs"),
    (lambda a: a["services"][0].update(extra=1), "fields or field order differ"),
    (lambda a: a["top_warning_and_error_logs_after_alarm"][0].update(message="CartService failed for inventory"),
     "identifier left"),
    (lambda a: a["top_warning_and_error_logs_after_alarm"][0].update(message="BasketService failed: inventory"),
     "text changed beyond names"),
    (lambda a: a["calls"][0].reverse(), "expected 'basket'"),
    (lambda a: a.update(alarm_time_utc="x"), "value differs"),
])
def test_check_catches_broken_copies(break_it, expect):
    a = convert_table(table())
    break_it(a)
    problems = check_table(table(), a)
    assert problems and any(expect in p for p in problems)


def test_check_catches_forbidden_term_left():
    # `.` sonrası önek silinmez (veride bu biçim yok); `otel` kalır, kontrol yakalar
    real = "grpc.oteldemo.CartService/GetCart"
    assert any("forbidden" in p for p in check_text(real, convert_message(real), "x"))
