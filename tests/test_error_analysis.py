"""Dev hata analizi seçimi (DECISIONS 2026-11-04 "P1e hata analizi kapsamı", "P1e hata sınıflaması"): kapsam, otomatik
türler, T3 kuralı, örneklem tohumu."""
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
