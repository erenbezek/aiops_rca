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
