"""Dev hata analizi seçimi (DECISIONS 2026-11-04 "P1e hata analizi kapsamı", "P1e hata sınıflaması"): kapsam, otomatik
türler, T3 kuralı, örneklem tohumu, `root_visibility: direct` hesabı."""
import json

from aiops_rca import error_analysis as ea


def lab(root, path):
    return {"answer": {"root_cause_service": root, "propagation_path": path}}


def test_t3_rule():
    label = lab("payment", [["payment", "checkout"], ["checkout", "frontend"]])
    assert ea.t3("checkout", label) == "yes" and ea.t3("frontend", label) == "yes"   # yolda, kök değil
    assert ea.t3("cart", label) == "no"                                              # yolda değil
    assert ea.t3("payment", label) == "no"                                           # kökün kendisi
    assert ea.t3(None, label) == "undetermined"                                      # ad eşleşmedi


def score(**k):
    return {"input_status": "ok", "no_answer": False, "schema_valid": True, "top1": False, **k}


def test_kind_partition():
    loop = {"finish_reason": "length", "raw_output": '["a", ' + '"frontend", ' * 25}
    assert ea.kind(score(input_status="empty"), {}) == "empty"
    assert ea.kind(score(input_status="over_budget"), {}) == "over_budget"
    assert ea.kind(score(no_answer=True, schema_valid=None), {}) == "no_answer"
    assert ea.kind(score(schema_valid=False), {}) == "schema_invalid"
    assert ea.kind(score(schema_valid=False), loop) == "repetition_loop"
    assert ea.kind(score(top1=True), {}) == "top1_hit" and ea.kind(score(), {}) == "in_scope"


def test_selection_on_dev_runs():
    rows, auto = ea.select()
    assert len(rows) == 29 and len({r["key"] for r in rows}) == 29
    assert {m: sum(r["model"] == m for r in rows) for m in ea.MODELS_IN} == \
        {"qwen3.5-4b": 16, "gpt-oss-120b": 6, "gemini-3.5-flash-lite": 7}
    assert all(sum(c.values()) == 18 for c in auto.values()) and len(auto) == 9
    assert sum(c["in_scope"] for c in auto.values()) == 29
    assert {k: c["schema_invalid"] for k, c in auto.items() if c["schema_invalid"]} == {
        "qwen3.5-4b raw": 2, "gpt-oss-120b raw": 2, "gpt-oss-120b summary": 3, "gpt-oss-120b narrowed": 1,
        "gemini-3.5-flash-lite raw": 2, "gemini-3.5-flash-lite summary": 1}
    assert all(r["incident_id"].startswith("inc-") and r["run_dir"].startswith("eval_responses/") for r in rows)


def test_sample_is_fixed_by_seed():
    rows, _ = ea.select()
    s = ea.sample(rows)
    assert len(s) == 10 and len(set(s)) == 10 and set(s) <= {r["key"] for r in rows}
    assert s == ea.sample(rows) and s != ea.sample(rows, seed=ea.SEED + 1)


# --- root_visibility: direct (kuralın sinyal tanımı, girdideki değerlere) ---

ALARM = (12 * 3600 + 59 * 60 + 33) * 10**9  # 12:59:33 UTC (gün içi; tarih farkı sonucu değiştirmez)


def svc(name, **k):
    return {"service": name, **k}


def summary_text(services, logs=()):
    return json.dumps({"alarm_time_utc": "x", "services": services, "top_warning_and_error_logs_after_alarm": list(logs)})


def test_direct_summary_uses_rule_thresholds_on_input_values():
    gw = svc("quote-gateway", requests_before=113, requests_after=83, error_rate_before=0.0, error_rate_after=0.0,
             p95_ms_before=7.5, p95_ms_after=37.1, cpu_pct_avg_before=1.33, cpu_pct_avg_after=1.27,
             mem_mb_avg_before=48, mem_mb_avg_after=48)
    assert ea.direct_signals("summary", summary_text([gw]), "quote-gateway", ALARM) == ["p95_ms"]
    small = dict(gw, p95_ms_after=27.0)                       # 1,5 kat ama +20 ms değil: sinyal yok
    assert ea.direct_signals("summary", summary_text([small]), "quote-gateway", ALARM) == []
    assert ea.direct_signals("summary", summary_text([gw]), "cart", ALARM) == []          # kök girdide yok
    err = svc("payment", requests_before=100, requests_after=100, error_rate_before=0.0, error_rate_after=0.05)
    assert ea.direct_signals("summary", summary_text([err]), "payment", ALARM) == ["error_rate"]   # +0,05: güç 1


def test_direct_db_only_resources_and_logs_need_zero_before():
    db = svc("valkey-cart", requests_before=100, requests_after=0, cpu_pct_avg_before=1.0, cpu_pct_avg_after=1.0,
             mem_mb_avg_before=10, mem_mb_avg_after=10)
    assert ea.direct_signals("summary", summary_text([db]), "valkey-cart", ALARM) == []    # istek düşüşü sayılmaz
    logs = [{"service": "ad", "message": "boom", "count_before": 0, "count_after": 5},
            {"service": "ad", "message": "old", "count_before": 3, "count_after": 50}]
    assert ea.direct_signals("summary", summary_text([svc("ad")], logs), "ad", ALARM) == ["new_warn_log"]
    assert ea.direct_signals("summary", summary_text([svc("ad")], logs[1:]), "ad", ALARM) == []


def test_direct_narrowed_only_if_root_is_candidate():
    block = svc("cart", requests_before=851, requests_after=902, error_rate_before=0.0, error_rate_after=0.0,
                p95_ms_before=1.1, p95_ms_after=150.0, logs=[])
    text = json.dumps({"candidates": [block, svc("checkout", logs=[])], "calls": []})
    assert ea.direct_signals("narrowed", text, "cart", ALARM) == ["p95_ms"]
    assert ea.direct_signals("narrowed", text, "recommendation", ALARM) == []


def test_direct_raw_counts_root_log_lines_by_time():
    after = [f"13:0{i}:00.000 ad log failed to fetch ad 4711" for i in range(5)]
    before = ["12:50:00.000 ad log failed to fetch ad 99"]
    spans = [f"13:0{i}:00.000 ad error-span GET /ad" for i in range(9)]
    assert ea.direct_signals("raw", "\n".join(after), "ad", ALARM) == ["new_warn_log"]   # sayı sadeleşir: aynı mesaj
    assert ea.direct_signals("raw", "\n".join(after[:4]), "ad", ALARM) == []             # 4 < 5
    assert ea.direct_signals("raw", "\n".join(before + after), "ad", ALARM) == []        # önce de var: yeni değil
    assert ea.direct_signals("raw", "\n".join(spans), "ad", ALARM) == []                 # hata span'i log değil
    assert ea.direct_signals("raw", "\n".join(after), "frontend", ALARM) == []
    late = 23 * 3600 * 10**9 + 58 * 60 * 10**9                                           # alarm 23:58, satırlar 00:0x
    lines = [f"00:0{i}:00.000 ad log boom" for i in range(5)] + ["23:50:00.000 ad log other"]
    assert ea.direct_signals("raw", "\n".join(lines), "ad", late) == ["new_warn_log"]
    early = 2 * 60 * 10**9                                                               # alarm 00:02, önce 23:55
    lines = [f"00:0{i}:00.000 ad log boom" for i in range(3, 8)] + ["23:55:00.000 ad log boom"]
    assert ea.direct_signals("raw", "\n".join(lines), "ad", early) == []                # 23:55 alarm öncesi


def test_labels_file_matches_code():
    # Etiket dosyası: sorular sha'sıyla donmuş; satırlar seçimle aynı; kodla dolan alanlar kodla tutarlı.
    import hashlib
    doc = json.loads((ea.REPO / "results" / "p1_error_labels.json").read_text(encoding="utf-8"))
    assert hashlib.sha256("\n".join(doc["questions"]).encode()).hexdigest() == doc["questions_sha256"]
    assert doc["questions_sha256"] == "dc58d84a1ea8e092b507c905be0573d2efc2bb176c72d53688de03bf77b687f7"
    rows, _ = ea.select()
    by = {r["key"]: r for r in rows}
    assert [x["key"] for x in doc["rows"]] == [r["key"] for r in rows]
    for x in doc["rows"]:
        r = by[x["key"]]
        assert all(x[t] in ("yes", "no", "undetermined") for t in ("T1", "T2", "T3", "T4", "T5", "T6"))
        assert x["root_visibility"] in ("direct", "indirect", "absent")
        assert (x["root_visibility"] == "direct") == bool(x["direct_signals"])
        assert x["top3"] == r["top3"] and x["T3"] == r["t3"]
        assert x["T2"] == ("no" if r["top3"] else "undetermined" if x["root_visibility"] == "absent" else "yes")
        if x["root_visibility"] != "direct":
            assert x["T4"] == "undetermined"
        assert x["reason"]


# --- özet (HANDOFF 2026-11-05): ad anahtarı, ad eşlenmemesi sayımı, toplamlar, Eren doğrulaması okuması ---

def test_name_key():
    assert ea.name_key("oteldemo.CartService/GetCart") == "cart" == ea.name_key("cart")
    assert ea.name_key("hipstershop.ProductCatalogService/GetProduct") == ea.name_key("product-catalog")
    assert ea.name_key("checkout-service") == "checkout" and ea.name_key("valkey-cart") == "valkeycart"
    assert ea.name_key("oteldemo.PaymentService") == "payment" != ea.name_key("checkout")


def test_name_miss_rank():
    case = lambda matched, unmatched, top3=False, valid=True: {"schema_valid": valid, "top3": top3,
                                                                "matched": matched, "unmatched": unmatched}
    assert ea.name_miss_rank(case([None, "ad", None], ["x.FooService/A", "oteldemo.CartService/GetCart"]), "cart") == 3
    assert ea.name_miss_rank(case([None, "ad"], ["oteldemo.CartService/GetCart"]), "cart") == 1
    assert ea.name_miss_rank(case([None], ["oteldemo.CartService/GetCart"], top3=True), "cart") is None   # isabet
    assert ea.name_miss_rank(case([], [], valid=False), "cart") is None                                    # şema dışı
    assert ea.name_miss_rank(case(["ad", "cart2", "x", None], ["CartService"]), "cart") is None            # 4. sıra


def test_name_misses_match_planning():
    # Planlama 2026-11-05 (sınırlama 2): dev 2, test 7; testte 1. sırada gpt-oss ham 1, Gemini ham 2.
    m = ea.name_misses()
    nonzero = {k: v for k, v in m.items() if any(c["count"] for c in v.values())}
    assert nonzero == {
        "qwen3.5-4b raw": {"dev": {"count": 1, "first": 0}, "test": {"count": 1, "first": 0}},
        "gpt-oss-120b raw": {"dev": {"count": 1, "first": 0}, "test": {"count": 3, "first": 1}},
        "gemini-3.5-flash-lite raw": {"dev": {"count": 0, "first": 0}, "test": {"count": 2, "first": 2}},
        "qwen3.5-9b raw": {"dev": {"count": 0, "first": 0}, "test": {"count": 1, "first": 0}}}
    assert len(m) == 12


def test_summary_totals_match_labels():
    res = ea.summary()
    a = res["traps"]["all"]
    assert a["n"] == res["rows"] == 29 and sum(res["traps"][c]["n"] for c in res["traps"] if c != "all") == 29
    assert (a["T1"]["yes"], a["T2"]["yes"], a["T2"]["undetermined"], a["T3"]["yes"], a["T5"]["yes"], a["T6"]["yes"]) \
        == (7, 8, 2, 25, 1, 12)
    assert (a["T4"]["no"], a["T4"]["undetermined"]) == (22, 7)
    assert {v: c["n"] for v, c in res["visibility"].items()} == {"direct": 22, "indirect": 3, "absent": 4}
    md, js = ea.summary_render()
    assert "inc-" not in md and "inc-" not in js                     # vaka kimliği çıktıya girmez


def checked_repo(tmp_path, marks):
    """Gerçek kayıtlara bağlı küçük repo; etiket dosyasına `marks` (anahtar → agree) `eren_check` olarak yazılır."""
    tmp_path.mkdir()
    for name in ("incidents", "eval_responses"):
        (tmp_path / name).symlink_to(ea.REPO / name)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "p1_runs.json").symlink_to(ea.REPO / "results" / "p1_runs.json")
    doc = json.loads((ea.REPO / ea.LABELS_FILE).read_text(encoding="utf-8"))
    for x in doc["rows"]:
        x.pop("eren_check", None)                                    # gerçek işaretler bu testte yok sayılır
        if x["key"] in marks:
            x["eren_check"] = {"agree": marks[x["key"]]}
    (tmp_path / ea.LABELS_FILE).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_eren_check_reading(tmp_path):
    import pytest
    keys = ea.sample(ea.select()[0])
    reading = lambda d, marks: ea.summary(checked_repo(tmp_path / d, marks))["eren_check"]
    assert reading("a", {k: False for k in keys[:3]}) == {"n": 10, "checked": 3, "disagree": 3, "reading": "pending"}
    assert reading("b", {k: i >= 3 for i, k in enumerate(keys)})["reading"] == "relabel"     # 3 katılmıyorum
    assert reading("c", {k: i >= 2 for i, k in enumerate(keys)})["reading"] == "ok"          # 2 katılmıyorum
    other = next(r["key"] for r in ea.select()[0] if r["key"] not in keys)
    with pytest.raises(ValueError):
        reading("d", {other: True})                                                          # örneklem dışı


def test_eren_check_in_labels_file():
    # Planlama 2026-11-05 (b2d0e6c): 10 satır, 9 katılıyor, 1 katılmıyor (4B daraltma, T5) → yeniden etiketleme yok.
    doc = json.loads((ea.REPO / ea.LABELS_FILE).read_text(encoding="utf-8"))
    checked = {x["key"]: x for x in doc["rows"] if "eren_check" in x}
    assert sorted(checked) == ea.sample(ea.select()[0])
    for x in checked.values():
        e = x["eren_check"]
        assert set(e) <= {"agree", "T1", "T5", "T6", "note"} and all(e[t] in ("yes", "no") for t in ("T1", "T5", "T6"))
        assert e["agree"] == all(e[t] == x[t] for t in ("T1", "T5", "T6"))
    off = [(k, t) for k, x in checked.items() for t in ("T1", "T5", "T6") if x["eren_check"][t] != x[t]]
    assert off == [("qwen3.5-4b narrowed inc-320c56f9", "T5")]
    assert ea.summary()["eren_check"] == {"n": 10, "checked": 10, "disagree": 1, "reading": "ok"}


def test_summary_files_match_records():
    # CI: özet repodaki kayıtlardan yeniden üretilir, repodaki dosyalarla bayt aynı olmalı.
    md, js = ea.summary_render()
    assert (ea.REPO / ea.SUMMARY_MD).read_text(encoding="utf-8") == md
    assert (ea.REPO / ea.SUMMARY_JSON).read_text(encoding="utf-8") == js
    assert ea.main(["summary", "--check"]) == 0
