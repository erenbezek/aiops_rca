"""Değerlendirme CLI'ı (HANDOFF 2026-10-30 P1a kartı).

    python -m aiops_rca.evaluate run --method rule|baro|narrowing [--sets pilot,dev] [--cases inc-…,…] [--final-test] [--root eval_responses]
    python -m aiops_rca.evaluate run --method llm --model <etiket> --level raw|summary|narrowed [--alias] [--sets …]
                                     [--cases …] [--root llm_cache]
    python -m aiops_rca.evaluate run --method agent --model <etiket> [--sets …] [--cases …] [--root llm_cache]
    python -m aiops_rca.evaluate score <koşu klasörü> [--final-test]

`run`: seçilen setlerin geçerli vakalarında yöntemi koşar, her cevabı şemayla doğrular ve kaydeder (`runs.py`).
Yöntem yalnız `Case`'i alır. `--cases` seçilen setlerin
içinden vaka süzer (set dışı kimlik hata). `llm` yöntemi (`methods/llm.py`) bir model × seviye × gerçek/takma ad koşar;
`--model` ve `--level` yalnız onda ve zorunlu, `--alias` yalnız onda; satıra girdi durumu, token ve denemeler eklenir,
`run.json`'a model, istem ve sunucu ayarları. `score`: kayıtlardan ve etiketlerden puanlar (çağrı kenarları snapshot'tan), `scores.json`
yazar ve set başına tabloyu basar. Sorulmayan girdi (`input_status`
`empty` / `over_budget`) ve cevapsız satır (`no_answer`) ıskalama ve çekimser sayılır; takma adlı koşuda cevaptaki adlar gerçek ada çevrilip eşlenir. `test` seti iki komutta da yalnız `--final-test` ile; `heldout` hiç.
`agent` yöntemi (`methods/agent.py`, P2b) dosya modunda (`FileStore`) ajanı koşar: satır P1 biçiminde + bitiş nedeni,
adım ve istek sayısı; koşu klasörüne ayrıca `turns.jsonl` (vaka × tur) ve `tool_outputs/<vaka>.jsonl` (modele giden
araç çıktılarının metni).
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
from aiops_rca.inputs import LEVELS
from aiops_rca.llm_client import MODELS
from aiops_rca.methods.baro import baro_baseline
from aiops_rca.methods.llm import llm_method
from aiops_rca.methods.narrowing import narrowing_baseline
from aiops_rca.methods.rule import rule_baseline
from aiops_rca.runs import EVAL_RESPONSES, append_response, new_run, read_run
from aiops_rca.scoring import score_case, score_table

METHODS = {"rule": rule_baseline, "baro": baro_baseline, "narrowing": narrowing_baseline}  # + "llm" (model, seviye ve takma adla kurulur)
TABLE_COLUMNS = (("n", "Vaka"), ("top1", "top-1"), ("top3", "top-3"), ("evidence_valid", "Kanıt geçerli"),
                 ("evidence_invalid", "Kanıt geçersiz"), ("evidence_null", "Kenarsız"),
                 ("label_path_overlap_mean", "Örtüşme"), ("brier", "Brier"), ("selective_accuracy", "Seçici doğruluk"),
                 ("coverage", "Kapsama"), ("schema_invalid", "Şema dışı"), ("input_empty", "Boş girdi"),
                 ("input_over_budget", "Bütçe aşımı"), ("no_answer", "Cevapsız"), ("duration_s_total", "Süre (sn)"))


def cmd_run(method: str, sets: tuple[str, ...], final_test: bool, root: Path, *, incidents: Path = INCIDENTS,
            snapshots: Path = SNAPSHOTS, cases: tuple[str, ...] | None = None, model: str | None = None,
            level: str | None = None, alias: bool = False, llm_options: dict | None = None) -> Path:
    if method == "llm":
        if model is None or level is None:
            raise ValueError("--method llm needs --model and --level")
    elif method == "agent":
        if model is None or level is not None or alias:
            raise ValueError("--method agent needs --model and takes no --level or --alias")
    elif model is not None or level is not None or alias:
        raise ValueError("--model, --level and --alias are only for --method llm and agent")
    selected = load_cases(sets, final_test=final_test, incidents=incidents, snapshots=snapshots)
    if cases is not None:
        missing = sorted(set(cases) - {c.incident_id for c in selected})
        if missing:
            raise ValueError(f"cases not in the selected sets: {missing}")
        selected = [c for c in selected if c.incident_id in set(cases)]
    if method == "llm":
        return _run_llm(selected, sets, root, model, level, alias, llm_options or {})
    if method == "agent":
        return _run_agent(selected, sets, root, model, llm_options or {})
    run_dir = new_run(method, sets, len(selected), root=root)
    fn = METHODS[method]
    for case in selected:
        t0 = time.perf_counter()
        obj, raw = fn(case)
        duration = round(time.perf_counter() - t0, 3)
        errors = validate_answer(obj)
        append_response(run_dir, {"incident_id": case.incident_id, "answer": None if errors else obj,
                                  "schema_valid": not errors, "schema_errors": errors, "raw_output": raw,
                                  "duration_s": duration, "tokens": None})
    return run_dir


def _run_llm(selected: list, sets: tuple[str, ...], root: Path, model: str, level: str, alias: bool,
             options: dict) -> Path:
    spec = MODELS.get(model)
    with llm_method(model, level, alias, **options) as (ask, settings):  # GGUF ve sunucu kontrolü koşu klasöründen önce
        run_dir = new_run("llm", sets, len(selected), root=root, model_id=spec.model_id, provider=spec.provider,
                          temperature=0, settings={"model": model, **settings})
        for case in selected:
            append_response(run_dir, {"incident_id": case.incident_id, **ask(case)})
    return run_dir


def _run_agent(selected: list, sets: tuple[str, ...], root: Path, model: str, options: dict) -> Path:
    from aiops_rca.methods.agent import agent_method
    from aiops_rca.store_file import FileStore
    spec = MODELS.get(model)
    store_factory = options.pop("store_factory", FileStore)
    with agent_method(model, store_factory, **options) as (ask, settings):
        run_dir = new_run("agent", sets, len(selected), root=root, model_id=spec.model_id, provider=spec.provider,
                          temperature=0, settings={"model": model, "store": getattr(store_factory, "__name__", "?"),
                                                   **settings})
        for case in selected:
            append_agent_case(run_dir, case.incident_id, ask(case))
    return run_dir


def append_agent_case(run_dir: Path, incident_id: str, out: dict, **extra) -> None:
    """Ajan vakasının kaydı: satır `responses.jsonl`'a (P1 biçimi + `extra`), turlar `turns.jsonl`'a, modele giden araç
    çıktıları `tool_outputs/<vaka>.jsonl`'a. Dosya ve canlı mod (`tools/agent_live.py`) aynı işlevi kullanır."""
    append_response(run_dir, {"incident_id": incident_id, **out["row"], **extra})
    with (run_dir / "turns.jsonl").open("a", encoding="utf-8") as f:
        for t in out["turns"]:
            f.write(json.dumps({"incident_id": incident_id, **t}, ensure_ascii=False, sort_keys=True) + "\n")
    (run_dir / "tool_outputs").mkdir(exist_ok=True)
    with (run_dir / "tool_outputs" / f"{incident_id}.jsonl").open("w", encoding="utf-8") as f:
        for o in out["tool_outputs"]:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")


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
        status = r.get("input_status", "ok")  # rule ve BARO satırlarında alan yok: sorulmuş
        alias = bool(run.get("settings", {}).get("alias"))
        rows.append({"incident_id": r["incident_id"], "set": label["set"],
                     **score_case(answer, label, edges, known, input_status=status, alias=alias,
                                  no_answer=bool(r.get("no_answer"))),
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
    r.add_argument("--method", required=True, choices=sorted([*METHODS, "llm", "agent"]))
    r.add_argument("--model", choices=list(MODELS))
    r.add_argument("--level", choices=list(LEVELS))
    r.add_argument("--alias", action="store_true")
    r.add_argument("--sets", default=",".join(DEFAULT_SETS))
    r.add_argument("--cases", help="comma-separated incident ids within the selected sets")
    r.add_argument("--final-test", action="store_true")
    r.add_argument("--root", type=Path, default=EVAL_RESPONSES)
    s = sub.add_parser("score")
    s.add_argument("run_dir", type=Path)
    s.add_argument("--final-test", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.cmd == "run":
            cases = tuple(x for x in args.cases.split(",") if x) if args.cases else None
            run_dir = cmd_run(args.method, tuple(x for x in args.sets.split(",") if x), args.final_test, args.root,
                              cases=cases, model=args.model, level=args.level, alias=args.alias)
            print(run_dir)
        else:
            print(markdown_table(cmd_score(args.run_dir, args.final_test)["table"]))
    except (PermissionError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
