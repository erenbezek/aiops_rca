"""Değerlendirme CLI'ı (HANDOFF 2026-10-30 P1a kartı).

    python -m aiops_rca.evaluate run --method rule [--sets pilot,dev] [--final-test] [--root eval_responses]
    python -m aiops_rca.evaluate score <koşu klasörü> [--final-test]

`run`: seçilen setlerin geçerli vakalarında yöntemi koşar, her cevabı şemayla doğrular ve kaydeder (`runs.py`).
Yöntem yalnız `Case`'i alır. `score`: kayıtlardan ve etiketlerden puanlar (çağrı kenarları snapshot'tan), `scores.json`
yazar ve set başına tabloyu basar. `test` seti iki komutta da yalnız `--final-test` ile; `heldout` hiç.
Çıkış: 0 tamam, 2 kullanım hatası.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from aiops_rca.answer import Answer, validate_answer
from aiops_rca.call_graph import metric_containers, service_edges
from aiops_rca.cases import DEFAULT_SETS, INCIDENTS, SNAPSHOTS, load_cases, load_labels
from aiops_rca.methods.rule import rule_baseline
from aiops_rca.runs import EVAL_RESPONSES, append_response, new_run, read_run
from aiops_rca.scoring import score_case, score_table

METHODS = {"rule": rule_baseline}
TABLE_COLUMNS = (("n", "Vaka"), ("top1", "top-1"), ("top3", "top-3"), ("evidence_valid", "Kanıt geçerli"),
                 ("evidence_invalid", "Kanıt geçersiz"), ("evidence_null", "Kenarsız"),
                 ("label_path_overlap_mean", "Örtüşme"), ("brier", "Brier"), ("selective_accuracy", "Seçici doğruluk"),
                 ("coverage", "Kapsama"), ("schema_invalid", "Şema dışı"), ("duration_s_total", "Süre (sn)"))


def cmd_run(method: str, sets: tuple[str, ...], final_test: bool, root: Path, *, incidents: Path = INCIDENTS,
            snapshots: Path = SNAPSHOTS) -> Path:
    cases = load_cases(sets, final_test=final_test, incidents=incidents, snapshots=snapshots)
    run_dir = new_run(method, sets, len(cases), root=root)
    fn = METHODS[method]
    for case in cases:
        t0 = time.perf_counter()
        obj, raw = fn(case)
        duration = round(time.perf_counter() - t0, 3)
        errors = validate_answer(obj)
        append_response(run_dir, {"incident_id": case.incident_id, "answer": None if errors else obj,
                                  "schema_valid": not errors, "schema_errors": errors, "raw_output": raw,
                                  "duration_s": duration, "tokens": None})
    return run_dir


def cmd_score(run_dir: Path, final_test: bool, *, incidents: Path = INCIDENTS, snapshots: Path = SNAPSHOTS) -> dict:
    run, responses = read_run(run_dir)
    labels = load_labels(tuple(run["sets"]), final_test=final_test, incidents=incidents)
    rows = []
    for r in responses:
        label = labels[r["incident_id"]]
        view = snapshots / r["incident_id"]
        edges, traced = service_edges([view / "traces.jsonl"])
        known = traced | metric_containers(sorted(view.glob("metrics*.jsonl")))
        answer = Answer.from_dict(r["answer"]) if r["schema_valid"] else None
        rows.append({"incident_id": r["incident_id"], "set": label["set"], **score_case(answer, label, edges, known),
                     "duration_s": r["duration_s"], "tokens": r["tokens"]})
    out = {"run": run, "table": score_table(rows), "cases": rows}
    (run_dir / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def markdown_table(table: dict) -> str:
    keys = [k for k in table if k != "all"] + ["all"]
    lines = ["| Set | " + " | ".join(h for _, h in TABLE_COLUMNS) + " |", "|---" * (len(TABLE_COLUMNS) + 1) + "|"]
    for k in keys:
        t = table[k]
        cells = []
        for col, _ in TABLE_COLUMNS:
            v = t[col]
            if col in ("top1", "top3"):
                v = f"{v}/{t['n']} ({t[col + '_rate']})"
            cells.append("—" if v is None else str(v))
        lines.append(f"| {'toplam' if k == 'all' else k} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aiops_rca.evaluate", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--method", required=True, choices=sorted(METHODS))
    r.add_argument("--sets", default=",".join(DEFAULT_SETS))
    r.add_argument("--final-test", action="store_true")
    r.add_argument("--root", type=Path, default=EVAL_RESPONSES)
    s = sub.add_parser("score")
    s.add_argument("run_dir", type=Path)
    s.add_argument("--final-test", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.cmd == "run":
            run_dir = cmd_run(args.method, tuple(x for x in args.sets.split(",") if x), args.final_test, args.root)
            print(run_dir)
        else:
            print(markdown_table(cmd_score(args.run_dir, args.final_test)["table"]))
    except (PermissionError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
