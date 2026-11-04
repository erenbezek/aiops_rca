"""Dev hata analizi (HANDOFF 2026-11-04 P1e kartı 3. madde; DECISIONS 2026-11-04 "P1e hata analizi kapsamı",
"P1e hata sınıflaması").

    python -m aiops_rca.error_analysis select              # kapsamdaki satırlar ve otomatik türler (stdout)
    python -m aiops_rca.error_analysis dossier --out DIR   # satır başına çalışma dosyası (snapshot + yerel tokenizer)
    python -m aiops_rca.error_analysis sample              # Eren doğrulaması için 10 satır (tohum 20261104)

Kapsam: `results/p1_runs.json`'daki dev koşularından (P1d a1, gerçek ad) 4B, gpt-oss ve Gemini × ham / özet / daraltma;
girdi sorulmuş (`input_status` ok), cevap gelmiş, şema içi ve top-1'i ıskalayan satırlar. Kural, BARO, daraltma
referansı ve 9B kapsam dışı. Kapsam dışındaki ıskalamalar otomatik türlerle sayılır, etiketlenmez: boş girdi, bütçe
aşımı, cevapsız, şema dışı (sınıra takılan dahil; tekrar döngüsü ayrıca sayılır).

T3 (belirtiyi neden sanma) kodla: 1. aday (eşlenmiş adıyla) etiketin yayılım yolunda kökten başka bir servisse evet;
yolda değilse hayır; ad eşleşmediyse belirlenemez.

`dossier`: her satır için modelin o seviyedeki girdisi yeniden üretilir (`inputs.<seviye>_input`, sayım yerel Qwen
tokenizer'ıyla; sunucu açılır, üretim yapılmaz) ve sha256'sı kayıttaki `input_sha256` ile aynı olmalı (değilse
durur). Dosyada etiket, T3, modelin cevabı ve girdi. Test vakası hiç okunmaz.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

from aiops_rca.cases import REPO, _check_sets, _labels

MODELS_IN = ("qwen3.5-4b", "gpt-oss-120b", "gemini-3.5-flash-lite")
LEVELS = ("raw", "summary", "narrowed")
SEED, SAMPLE_N = 20261104, 10
LOOP_RUN = 20  # DECISIONS 2026-11-01 "P1d'de sınıra takılan cevapta durma": aynı dize art arda ≥ 20 kez
LOOP = re.compile(r'("(?:[^"\\]|\\.)*")(?:\s*,\s*\1){%d,}' % (LOOP_RUN - 1))
AUTO = ("empty", "over_budget", "no_answer", "schema_invalid", "repetition_loop", "top1_hit", "in_scope")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def dev_labels(repo: Path = REPO) -> dict[str, dict]:
    _check_sets(("dev",), False)
    return {d["incident_id"]: d for d in _labels(("dev",), repo / "incidents")}


def t3(matched_first: str | None, label: dict) -> str:
    """Belirtiyi neden sanma (kodla): yes / no / undetermined."""
    if matched_first is None:
        return "undetermined"
    root = label["answer"]["root_cause_service"]
    on_path = {s for edge in label["answer"]["propagation_path"] for s in edge}
    return "yes" if matched_first != root and matched_first in on_path else "no"


def kind(score: dict, resp: dict) -> str:
    """Bir dev satırının türü (AUTO'dan biri)."""
    status = score.get("input_status", "ok")
    if status != "ok":
        return status                                           # empty / over_budget
    if score.get("no_answer"):
        return "no_answer"
    if score["schema_valid"] is False:
        loop = resp.get("finish_reason") == "length" and LOOP.search(resp.get("raw_output") or "")
        return "repetition_loop" if loop else "schema_invalid"
    return "top1_hit" if score["top1"] else "in_scope"


def select(repo: Path = REPO) -> tuple[list[dict], dict]:
    """(kapsamdaki satırlar, (model, seviye) → otomatik tür sayıları). Satırlar model, seviye, vaka sırasıyla."""
    spec = json.loads((repo / "results" / "p1_runs.json").read_text(encoding="utf-8"))
    labels = dev_labels(repo)
    rows, auto = [], {}
    for model in MODELS_IN:
        for level in LEVELS:
            run_dir = next(r["runs"]["dev"] for r in spec["rows"]
                           if r["method"] == "llm" and (r["model"], r["level"]) == (model, level))
            scores = json.loads((repo / run_dir / "scores.json").read_text(encoding="utf-8"))
            resp = {r["incident_id"]: r for r in _jsonl(repo / run_dir / "responses.jsonl")}
            counts = dict.fromkeys(AUTO, 0)
            for c in sorted((c for c in scores["cases"] if c["set"] == "dev"), key=lambda c: c["incident_id"]):
                k = kind(c, resp[c["incident_id"]])
                counts[k] += 1
                if k == "in_scope":
                    lab = labels[c["incident_id"]]
                    first = c["matched"][0] if c["matched"] else None
                    rows.append({"key": f"{model} {level} {c['incident_id']}", "model": model, "level": level,
                                 "incident_id": c["incident_id"], "run_dir": run_dir, "top3": c["top3"],
                                 "first_matched": first, "t3": t3(first, lab)})
            auto[f"{model} {level}"] = counts
    return rows, auto


def sample(rows: list[dict], n: int = SAMPLE_N, seed: int = SEED) -> list[str]:
    """Eren doğrulaması için rastgele n satırın anahtarı (liste sırası `select`'inki; tohum sabit)."""
    return sorted(random.Random(seed).sample([r["key"] for r in rows], n))


# --- çalışma dosyası (yerel; snapshot ve tokenizer sunucusu ister) ---

def dossier(out: Path, repo: Path = REPO) -> list[dict]:
    from aiops_rca import inputs
    from aiops_rca.cases import load_cases
    from aiops_rca.llm_client import MODELS, LocalServer, count_tokens
    from aiops_rca.methods.llm import TOKENIZER

    rows, _ = select(repo)
    labels = dev_labels(repo)
    cases = {c.incident_id: c for c in load_cases(("dev",))}
    out.mkdir(parents=True, exist_ok=True)
    index = []
    with LocalServer(MODELS[TOKENIZER].gguf) as server:
        count = lambda text: count_tokens(server.base, text)
        for r in rows:
            resp = {x["incident_id"]: x for x in _jsonl(repo / r["run_dir"] / "responses.jsonl")}[r["incident_id"]]
            inp = getattr(inputs, f"{r['level']}_input")(cases[r["incident_id"]], count)
            sha = hashlib.sha256(inp["text"].encode()).hexdigest()
            if sha != resp["input_sha256"]:
                raise RuntimeError(f"{r['key']}: input sha {sha} != recorded {resp['input_sha256']}")
            ans = labels[r["incident_id"]]["answer"]
            name = f"{r['model']}__{r['level']}__{r['incident_id']}.md"
            text = "\n".join([
                f"# {r['key']}", "",
                f"- Koşu: `{r['run_dir']}`; girdi sha256 `{sha}` (kayıtla aynı); veri token {inp['data_tokens']}",
                f"- Etiket: kök `{ans['root_cause_service']}`, senaryo `{ans['scenario']}`, hata türü "
                f"`{ans.get('fault_type')}`, kategoriler {ans.get('categories')}",
                f"- Yayılım yolu: {ans['propagation_path']}",
                f"- 1. aday (eşlenmiş): `{r['first_matched']}`; kök ilk 3'te: {r['top3']}; T3 (kod): {r['t3']}", "",
                "## Cevap", "", "```json", json.dumps(resp["answer"], ensure_ascii=False, indent=1), "```", "",
                "## Girdi", "", "```", inp["text"], "```", ""])
            (out / name).write_text(text, encoding="utf-8")
            index.append({"key": r["key"], "file": name, "input_sha256": sha})
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aiops_rca.error_analysis", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    d = sub.add_parser("dossier")
    d.add_argument("--out", type=Path, required=True)
    sub.add_parser("sample")
    args = p.parse_args(argv)
    rows, auto = select()
    if args.cmd == "select":
        print(json.dumps({"rows": [r["key"] for r in rows], "auto": auto}, ensure_ascii=False, indent=1))
    elif args.cmd == "sample":
        print("\n".join(sample(rows)))
    else:
        index = dossier(args.out)
        print(f"{len(index)} files, input sha256 equal to the records: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
