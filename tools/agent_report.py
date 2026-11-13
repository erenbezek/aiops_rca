"""P2b pilot dumanı raporu (HANDOFF 2026-11-13, 5. madde; Eren onaylı ad).

    python tools/agent_report.py [--check]

Kaynak: `eval_responses/`'teki üç pilot koşusu (`RUNS`; `responses.jsonl`, `turns.jsonl`, `scores.json`). Çıktı
`results/p2b_pilot.json` ve `.md`. `--check`: yeniden üretir ve repodakiyle bayt aynı mı bakar (CI; snapshot gerekmez).

İçerik: koşu başına bitiş nedenleri, araç / istek / token / süre, kırpma, tekrarlanan çağrı, araç hatası, kesilen
sonuç, HTTP durumları; 4B kuralı (DECISIONS 2026-11-13) ve bütçe yeniden açma kuralı (DECISIONS 2026-11-09);
vaka tablosu. Pilot isabeti (`scores.json`) yalnız bilgi: istem ve araçlar pilotta belirlendi, hiçbir karara girmez.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "eval_responses"
OUT = REPO / "results" / "p2b_pilot"
# (koşu klasörü, etiket); kopyalar llm_cache/'tekilerle bayt aynı (HANDOFF 2026-11-13).
RUNS = [("20261113T075333Z-agent", "(b) Gemini, dosya, 25 vaka"),
        ("20261113T083032Z-agent", "(c) qwen3.5-4b, dosya, 25 vaka"),
        ("20261113T102704Z-agent", "(d) Gemini, canlı, 3 vaka")]
RULE_4B = {"run": "20261113T083032Z-agent", "min_valid": 20, "max_mean_min": 20}


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x]


def summarize(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows = _jsonl(run_dir / "responses.jsonl")
    turns = _jsonl(run_dir / "turns.jsonl")
    scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
    by_case = {r["incident_id"]: r for r in rows}
    sc = {c["incident_id"]: c for c in scores["cases"]}
    cases = []
    for cid in sorted(by_case):
        r = by_case[cid]
        ts = [t for t in turns if t["incident_id"] == cid]
        calls = [t["call"] for t in ts if t.get("call")]
        cases.append({"incident_id": cid, "end_reason": r["end_reason"], "schema_valid": r["schema_valid"],
                      "n_tool_calls": r["n_tool_calls"], "n_requests": r["n_requests"],
                      "tokens_input": r["tokens"]["input"], "tokens_output": r["tokens"]["output"],
                      "duration_s": r["duration_s"], "max_message_tokens": max(t["input_tokens_local"] for t in ts),
                      "turns_with_drop": sum(1 for t in ts if t["dropped"]),
                      "repeated_calls": len(calls) - len(set(calls)),
                      "tool_errors": sum(1 for t in ts if t.get("tool_error")),
                      "tool_truncated": sum(1 for t in ts if t.get("tool_truncated")),
                      "top1": sc[cid]["top1"], "top3": sc[cid]["top3"]})
    http = Counter(str(a.get("status")) for t in turns for a in (t.get("attempts") or []))
    d = [c["duration_s"] for c in cases]
    table = scores["table"]["all"]
    return {"run": run_dir.name, "model": run["settings"]["model"], "store": run["settings"].get("store"),
            "repo_commit": run["repo_commit"], "prompt_sha256": run["settings"]["prompt_sha256"],
            "n_cases": len(cases), "end_reasons": dict(sorted(Counter(c["end_reason"] for c in cases).items())),
            "schema_valid": sum(1 for c in cases if c["schema_valid"]),
            "tool_calls": dict(sorted(Counter(c["n_tool_calls"] for c in cases).items())),
            "requests": sum(c["n_requests"] for c in cases),
            "tokens_input": sum(c["tokens_input"] for c in cases), "tokens_output": sum(c["tokens_output"] for c in cases),
            "duration_s_mean": round(statistics.mean(d), 1), "duration_s_max": round(max(d), 1),
            "max_message_tokens": max(c["max_message_tokens"] for c in cases),
            "cases_with_drop": sum(1 for c in cases if c["turns_with_drop"]),
            "budget_endings": sum(1 for c in cases if c["end_reason"] == "budget"),
            "repeated_calls": sum(c["repeated_calls"] for c in cases),
            "tool_errors": sum(c["tool_errors"] for c in cases),
            "tool_truncated": sum(c["tool_truncated"] for c in cases), "http": dict(sorted(http.items())),
            "info_top1": table["top1"], "info_top3": table["top3"], "cases": cases}


def build() -> dict:
    runs = [{"label": label, **summarize(EVAL / name)} for name, label in RUNS]
    r4 = next(r for r in runs if r["run"] == RULE_4B["run"])
    mean_min = r4["duration_s_mean"] / 60
    rule_4b = {"valid": r4["schema_valid"], "min_valid": RULE_4B["min_valid"], "mean_min": round(mean_min, 2),
               "max_mean_min": RULE_4B["max_mean_min"],
               "passed": r4["schema_valid"] >= RULE_4B["min_valid"] and mean_min <= RULE_4B["max_mean_min"]}
    budget = {r["run"]: {"budget_endings": r["budget_endings"], "n_cases": r["n_cases"],
                         "reopen": r["budget_endings"] > r["n_cases"] / 2} for r in runs}
    return {"runs": runs, "rule_4b": rule_4b, "budget_rule": budget}


def render(rep: dict) -> str:
    L = ["# P2b pilot dumanı", "",
         "Komutla üretilir: `python tools/agent_report.py` (kaynak `eval_responses/`'teki üç pilot koşusu). Pilot "
         "tasarım aşamasıdır: istem, araçlar ve sınırlar pilotta belirlendi; **isabet (top-1 / top-3) yalnız bilgi, "
         "iyimser okunur ve hiçbir karara girmez** (P2b kartı).", "",
         "## Koşular", "",
         "| Koşu | Klasör | Bitişler | Geçerli son cevap | Araç sayısı (vaka) | İstek | Token giriş / çıkış | "
         "Süre ort / en çok (sn) | En uzun mesaj | Kırpmalı vaka | Bütçe bitişi | Tekrar | Araç hatası | Kesilen sonuç | "
         "HTTP | top-1 (bilgi) | top-3 (bilgi) |", "|" + "---|" * 17]
    for r in rep["runs"]:
        er = ", ".join(f"{k} {v}" for k, v in r["end_reasons"].items())
        tc = ", ".join(f"{k}: {v}" for k, v in r["tool_calls"].items())
        http = ", ".join(f"{k}: {v}" for k, v in r["http"].items())
        L.append(f"| {r['label']} | `{r['run']}` | {er} | {r['schema_valid']}/{r['n_cases']} | {tc} | {r['requests']} | "
                 f"{r['tokens_input']} / {r['tokens_output']} | {r['duration_s_mean']} / {r['duration_s_max']} | "
                 f"{r['max_message_tokens']} | {r['cases_with_drop']} | {r['budget_endings']} | {r['repeated_calls']} | "
                 f"{r['tool_errors']} | {r['tool_truncated']} | {http} | {r['info_top1']}/{r['n_cases']} | "
                 f"{r['info_top3']}/{r['n_cases']} |")
    k = rep["rule_4b"]
    L += ["", "## Kurallar", "",
          f"- **4B kuralı** (DECISIONS 2026-11-13, koşudan önce): geçerli son cevap {k['valid']} / 25 (≥ {k['min_valid']}) "
          f"ve ortalama vaka süresi {k['mean_min']} dk (≤ {k['max_mean_min']}) → "
          f"**{'geçti: 4B P2’ye girer' if k['passed'] else 'kaldı: 4B P2’ye girmez'}**.",
          "- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09: vakaların yarısından çoğu bütçe yüzünden biterse): " +
          "; ".join(f"`{run}` {v['budget_endings']}/{v['n_cases']}" for run, v in rep["budget_rule"].items()) +
          f" → **{'yeniden açılır' if any(v['reopen'] for v in rep['budget_rule'].values()) else 'tetiklenmedi'}**.",
          "", "## Vakalar", ""]
    for r in rep["runs"]:
        L += [f"### {r['label']}", "", "| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | "
              "Araç hatası | top-1 / top-3 (bilgi) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for c in r["cases"]:
            hit = f"{'evet' if c['top1'] else 'hayır'} / {'evet' if c['top3'] else 'hayır'}"
            L.append(f"| `{c['incident_id']}` | {c['end_reason']} | {c['n_tool_calls']} | {c['n_requests']} | "
                     f"{c['duration_s']} | {c['max_message_tokens']} | {c['turns_with_drop']} | {c['repeated_calls']} | "
                     f"{c['tool_errors']} | {hit} |")
        L.append("")
    return "\n".join(L)


def main(argv: list[str]) -> int:
    rep = build()
    text_json = json.dumps(rep, ensure_ascii=False, indent=1) + "\n"
    text_md = render(rep)
    if "--check" in argv:
        same = (OUT.with_suffix(".json").read_text(encoding="utf-8") == text_json
                and OUT.with_suffix(".md").read_text(encoding="utf-8") == text_md)
        print("same" if same else "different")
        return 0 if same else 1
    OUT.with_suffix(".json").write_text(text_json, encoding="utf-8")
    OUT.with_suffix(".md").write_text(text_md, encoding="utf-8")
    print(f"-> {OUT.with_suffix('.md')}; 4B {rep['rule_4b']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
