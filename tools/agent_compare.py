"""P2c 2. madde (c): ajanın canlı koşusunda çağrı düzeyi dosya ↔ canlı karşılaştırması ve 4B'nin "çıktı aynı, model
ayrıştı" denetimi (DECISIONS 2026-11-14 "P2c dosya ↔ canlı okuma kuralı" (1); HANDOFF 2026-11-14 öneri (c) ve planlama
kontrolü şart 1).

    python tools/agent_compare.py --live <canlı koşu> [--file <aynı modelin dosya koşusu>] ... --out <json>
                                  [--tokenizer http://127.0.0.1:PORT]

Koşudan sonra, yalnız kayıtlardan (`agent_live.py`'ye dokunmaz). Her `--live` bir canlı ajan koşusu klasörü
(`settings.store` = `LiveStore`); ardından gelen `--file` (isteğe bağlı) aynı modelin dosya koşusu (`FileStore`).

**Çağrı düzeyi:** canlı koşudaki her araç çağrısı (`turns.jsonl`'daki araç ve argümanlar) dosya okuyucusuyla
(`FileStore`) `agent_tools.run_tool(..., TOOL_RESULT_TOKENS)` üzerinden yeniden yapılır; çıkan metin `tool_outputs/`'taki
canlı metinle bayt bayt karşılaştırılır. Kırpma sayımı yerel Qwen tokenizer'ıyla (`methods.llm.TOKENIZER`; sunucu
açılır, üretim yapılmaz; `--tokenizer` verilirse o kullanılır). Sınıf kodla:
- `same`: metin aynı;
- `zero_duration` (bilinen tür): metin farklı, dosya okuyucusuna Jaeger'in sıfır süreli span dönüşümü
  (`query_compare.jaeger_like_store`) uygulanınca aynı;
- `unexplained`: öteki her durum. `error_tag` dönüşümünü içeren bir küme metni eşitliyorsa bu yalnız tanı olarak
  yanına yazılır (`diagnosis`), sınıf yine `unexplained` (planlama kontrolü şart 1).
Dönüşüm kümeleri küçükten büyüğe denenir (aynı boyda `zero_duration` önce); eşitleyen ilk küme tanıdır.

**4B denetimi (`--file` verilen çiftlerde):** vaka başına dosya ve canlı tur kayıtları yan yana; i. turdan önceki bütün
araç çıktıları iki modda aynıysa i. turun ham çıktısı (`raw_output`) da aynı olmalı (cevap turu dahil). İlk ayrışan
turda ham çıktı farklıysa vaka "çıktı aynı, model ayrıştı" (`model_diverged`); ilk farklılık bir araç çıktısındaysa
denetim orada biter (sonraki turların girdisi farklı).

Çıktı: `--out` JSON (dev'de `results/p2c_dev_calls.json`). Snapshot ve tokenizer ister; CI'da koşmaz, çıktısı
commit'lenir. Yalnız pilot / dev vakaları.
"""
from __future__ import annotations

import argparse
import functools
import itertools
import json
import sys
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from query_compare import JAEGER_TRANSFORMS, jaeger_like_store  # noqa: E402

from aiops_rca import agent_tools as at  # noqa: E402
from aiops_rca.cases import load_cases  # noqa: E402
from aiops_rca.llm_client import MODELS, LocalServer, count_tokens  # noqa: E402
from aiops_rca.methods.agent import TOOL_RESULT_TOKENS  # noqa: E402
from aiops_rca.methods.llm import TOKENIZER  # noqa: E402
from aiops_rca.store_file import FileStore  # noqa: E402

KNOWN = "zero_duration"  # DECISIONS 2026-11-14: bilinen tek tür


def _jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def read_run(run_dir: Path) -> dict:
    """Koşu: ayarlar ve vaka başına turlar (tur sırasıyla) ile araç çıktıları (tur → metin)."""
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows = _jsonl(run_dir / "responses.jsonl")
    turns: dict[str, list[dict]] = {}
    for t in _jsonl(run_dir / "turns.jsonl"):
        turns.setdefault(t["incident_id"], []).append(t)
    outputs = {}
    for r in rows:
        cid = r["incident_id"]
        turns[cid] = sorted(turns.get(cid, []), key=lambda t: t["turn"])
        outputs[cid] = {o["turn"]: o for o in _jsonl(run_dir / "tool_outputs" / f"{cid}.jsonl")}
    return {"dir": run_dir.name, "model": meta["settings"]["model"], "store": meta["settings"].get("store"),
            "repo_commit": meta.get("repo_commit"), "prompt_sha256": meta["settings"].get("prompt_sha256"),
            "cases": [r["incident_id"] for r in rows], "turns": turns, "outputs": outputs}


def _subsets() -> list[frozenset[str]]:
    """Dönüşüm kümeleri küçükten büyüğe; aynı boyda bilinen tür (`zero_duration`) önce: yalnız o eşitliyorsa sınıf
    bilinen türdür, başka bir kümenin de eşitlemesi bunu değiştirmez."""
    names = sorted(JAEGER_TRANSFORMS)
    subsets = [frozenset(c) for n in range(1, len(names) + 1) for c in itertools.combinations(names, n)]
    return sorted(subsets, key=lambda s: (len(s), s != frozenset({KNOWN})))


def classify_call(case, tool: str, args: dict, live_text: str, count, stores: dict) -> dict:
    """Bir canlı çağrının sınıfı (`same` / `zero_duration` / `unexplained`) ve tanısı."""
    file_text = at.run_tool(stores[frozenset()], case, tool, args, count, TOOL_RESULT_TOKENS).text
    if file_text == live_text:
        return {"class": "same", "diagnosis": None}
    for subset in _subsets():
        if at.run_tool(stores[subset], case, tool, args, count, TOOL_RESULT_TOKENS).text == live_text:
            diag = "+".join(sorted(subset))
            return {"class": KNOWN if subset == frozenset({KNOWN}) else "unexplained", "diagnosis": diag}
    return {"class": "unexplained", "diagnosis": None}


def compare_calls(live: dict, cases: dict, count) -> dict:
    """Canlı koşunun bütün araç çağrıları: vaka başına sayımlar ve farklı çağrıların listesi."""
    out = {}
    for cid in live["cases"]:
        case = cases[cid]
        stores = {frozenset(): FileStore(case), **{s: jaeger_like_store(case, s) for s in _subsets()}}
        classes, diffs = Counter(), []
        for t in live["turns"][cid]:
            if not t.get("tool"):
                continue
            args = t["action"]["args"]
            o = live["outputs"][cid][t["turn"]]
            assert o["call"] == t["call"], (cid, t["turn"])  # `turns.jsonl` anahtarları sıralı: metni kayıttan
            c = classify_call(case, t["tool"], args, o["text"], count, stores)
            classes[c["class"]] += 1
            if c["class"] != "same":
                diffs.append({"turn": t["turn"], "call": t["call"], **c})
        out[cid] = {"calls": sum(classes.values()), "classes": dict(sorted(classes.items())), "diffs": diffs}
    return out


def model_divergence(file_run: dict, live_run: dict) -> dict:
    """Vaka başına: önceki araç çıktıları aynıyken ham çıktısı ayrışan ilk tur (`model_diverged`), yoksa ilk farklı
    araç çıktısının turu (`output_differs_at`). Yalnız iki koşuda da olan vakalar."""
    out = {}
    for cid in live_run["cases"]:
        if cid not in file_run["turns"]:
            continue
        ft, lt = file_run["turns"][cid], live_run["turns"][cid]
        fo, lo = file_run["outputs"][cid], live_run["outputs"][cid]
        rec = {"model_diverged": False, "diverged_turn": None, "output_differs_at": None,
               "turns_compared": 0, "turns_file": len(ft), "turns_live": len(lt)}
        for i in range(max(len(ft), len(lt))):
            if i >= len(ft) or i >= len(lt):  # aynı girdide birinde tur var, ötekinde yok
                rec.update(model_diverged=True, diverged_turn=i)
                break
            rec["turns_compared"] += 1
            if ft[i]["raw_output"] != lt[i]["raw_output"] or ft[i]["kind"] != lt[i]["kind"]:
                rec.update(model_diverged=True, diverged_turn=i)
                break
            if (fo.get(i) or {}).get("text") != (lo.get(i) or {}).get("text"):
                rec["output_differs_at"] = i
                break
        out[cid] = rec
    return out


def build(pairs: list[tuple[Path, Path | None]], count) -> dict:
    cases = {c.incident_id: c for c in load_cases()}
    rep = {"rule": "DECISIONS 2026-11-14 P2c dosya ↔ canlı okuma kuralı (1)", "known_classes": [KNOWN],
           "transforms": JAEGER_TRANSFORMS, "tool_result_tokens": TOOL_RESULT_TOKENS, "tokenizer": TOKENIZER,
           "runs": []}
    for live_dir, file_dir in pairs:
        live = read_run(live_dir)
        if live["store"] != "LiveStore":
            raise SystemExit(f"error: {live_dir} is not a live run (store {live['store']})")
        unknown = [c for c in live["cases"] if c not in cases]
        if unknown:
            raise SystemExit(f"error: not pilot/dev cases: {unknown}")
        calls = compare_calls(live, cases, count)
        tot = Counter()
        for v in calls.values():
            tot.update(v["classes"])
        entry = {"model": live["model"], "live": {k: live[k] for k in ("dir", "repo_commit", "prompt_sha256")},
                 "file": None, "cases": calls,
                 "totals": {"cases": len(calls), "calls": sum(tot.values()), **dict(sorted(tot.items()))}}
        if file_dir is not None:
            f = read_run(file_dir)
            if f["store"] != "FileStore" or f["model"] != live["model"]:
                raise SystemExit(f"error: {file_dir} is not a file run of {live['model']}")
            div = model_divergence(f, live)
            entry["file"] = {k: f[k] for k in ("dir", "repo_commit", "prompt_sha256")}
            entry["divergence"] = div
            entry["totals"]["divergence"] = {
                "cases_paired": len(div), "model_diverged": sum(v["model_diverged"] for v in div.values()),
                "output_differs": sum(v["output_differs_at"] is not None for v in div.values()),
                "identical": sum(not v["model_diverged"] and v["output_differs_at"] is None for v in div.values())}
        rep["runs"].append(entry)
    return rep


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="agent_compare.py", description="P2c: call-level file vs live comparison")
    ap.add_argument("--live", type=Path, action="append", required=True)
    ap.add_argument("--file", type=Path, action="append", default=[],
                    help="file-mode run of the same model; pairs with the --live given just before it")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tokenizer")
    # --live / --file sırası: her --file kendisinden önceki --live'a bağlanır
    pairs: list[tuple[Path, Path | None]] = []
    it = iter(argv)
    rest = []
    for a in it:
        if a in ("--live", "--file"):
            v = next(it, None)
            if v is None:
                ap.error(f"{a} needs a value")
            if a == "--live":
                pairs.append((Path(v), None))
            elif not pairs or pairs[-1][1] is not None:
                ap.error("--file must follow its --live")
            else:
                pairs[-1] = (pairs[-1][0], Path(v))
            rest += [a, v]
        else:
            rest.append(a)
    args = ap.parse_args(rest)
    with ExitStack() as stack:
        base = args.tokenizer or stack.enter_context(LocalServer(MODELS[TOKENIZER].gguf)).base
        rep = build(pairs, functools.partial(count_tokens, base))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in rep["runs"]:
        print(r["model"], r["live"]["dir"], r["totals"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
