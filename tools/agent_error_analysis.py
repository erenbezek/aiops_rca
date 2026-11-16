"""P2 hata analizi (HANDOFF 2026-11-14 P2c kartı 6. madde; DECISIONS 2026-11-14 "P2 hata analizi: 12 tuzağın ajana
uyarlanmış soruları").

    python tools/agent_error_analysis.py select               # kapsamdaki satırlar ve kodla sayılan tuzaklar (stdout)
    python tools/agent_error_analysis.py dossier --out DIR    # satır başına okuma dosyası (kayıtlardan)
    python tools/agent_error_analysis.py sample               # Eren doğrulaması için 10 satır (tohum 20261104)
    python tools/agent_error_analysis.py summary [--check]    # results/p2c_error_summary.md / .json

Kapsam: dev, resmî dosya koşuları (`agent_report.DEV_RUNS`: Gemini 1. koşu, 4B), top-1'i ıskalayan satırlar; kodla
sayılan tuzaklar ayrıca 18 vakanın tümünde bilgi olarak. Çok etiketli. "Girdi" = ajanın o vakada gördüğü bütün araç
çıktıları (`tool_outputs/`, sonradan kırpılanlar dahil).

Kodla (evet / hayır; 7'de geçerli cevap yoksa belirlenemez): T2 eksik inceleme, T3 belirtiyi neden sanma (P1'in
`error_analysis.t3`'ü), T4 geçersiz çağrı, T5 tek kaynak, T7 çapraz kontrol yok, T9 anlamsız tekrar, T11 bütçe taşması,
T12 adım sınırı. Okuyarak (etiket dosyasında; evet / hayır / belirlenemez): T1 yorumda uydurma, T6 zaman hatası,
T8 gerekçe–çağrı uyuşmazlığı; T1 ve T6 geçerli cevap yoksa belirlenemez. T10 uygulanamaz. Soruların tam metni
`QUESTIONS` (DECISIONS satırının karar hücresi, aynen; testte denetlenir); etiket dosyasına sha256'sıyla girer.

Telemetri türü (T5, T7): iz (`search_spans`, `get_trace`, `service_dependencies`, `metric_series` `requests` /
`errors` / `error_rate` / `p95_ms` / `p99_ms`), metrik (`metric_series` öteki metrikler), log (`search_logs`);
`list_services` ve metriği olmayan `metric_series` (araç hatası) tür sayılmaz.

Yalnız dev; test vakası okunmaz. Snapshot gerekmez (kayıtlar ve `incidents/` etiketleri); `summary --check` CI'da.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_report as ar  # noqa: E402

from aiops_rca.error_analysis import SAMPLE_N, SEED, dev_labels, t3  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RUN_KEYS = ("gemini_file", "qwen_file")  # resmî dosya koşuları
CODED = ("T2", "T3", "T4", "T5", "T7", "T9", "T11", "T12")
READ = ("T1", "T6", "T8")
TRAPS = ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T11", "T12")
VALUES = ("yes", "no", "undetermined")
DISAGREE_MAX = 2  # P1 ile aynı: 10 satırın ≥ 3'ünde katılmıyorum → yeniden etiketleme
LABELS_FILE = Path("results") / "p2c_error_labels.json"
SUMMARY_MD, SUMMARY_JSON = Path("results") / "p2c_error_summary.md", Path("results") / "p2c_error_summary.json"
TRACE_METRICS = frozenset({"requests", "errors", "error_rate", "p95_ms", "p99_ms"})
QUESTIONS = (
    '**P2 hata analizi: 12 tuzağın ajana uyarlanmış soruları (dev koşusundan ve etiketlemeden önce; donar'
    ").** Kaynak arXiv 2602.09937 v2, Tablo 2 (planlama 2026-11-14'te yeniden okudu). Kapsam: dev, resmî "
    "dosya koşuları (Gemini ilk koşu, 4B), top-1'i ıskalayan satırlar; kodla sayılanlar ayrıca 18 vakanın"
    ' tümünde bilgi olarak. Çok etiketli. "Girdi" = ajanın o vakada gördüğü bütün araç çıktıları (`tool_o'
    'utputs/`, sonradan kırpılanlar dahil). Telemetri türü: **iz** (`search_spans`, `get_trace`, `service'
    '_dependencies`, `metric_series` `requests` / `errors` / `error_rate` / `p95_ms` / `p99_ms`), **metri'
    'k** (`metric_series` öteki metrikler), **log** (`search_logs`); `list_services` tür sayılmaz. **Kodl'
    'a (evet / hayır):** **2 eksik inceleme:** `service` = kök olan hiç çağrı yok (yan sayı: kök adı herh'
    'angi bir araç çıktısında geçti mi). **3 belirtiyi neden sanma:** P1 ile aynı (`error_analysis.t3`). '
    '**4 geçersiz çağrı (uyarlanmış; makalede kod üretme hatası):** en az bir çağrıda `tool_error` ya da '
    'bitiş `schema_action`. **5 tek kaynak:** çağrıların türleri en çok bir tür. **7 çapraz kontrol yok:*'
    '* `service` = 1. aday olan çağrılar en çok bir türde (geçerli cevap yoksa belirlenemez). **9 anlamsı'
    'z tekrar:** aynı çağrı metni (`call`) en az iki kez. **11 bütçe taşması (uyarlanmış; makalede bellek'
    ' taşması):** en az bir turda `dropped` dolu ya da bitiş `budget`. **12 adım sınırı:** bitiş `step_li'
    "mit`. **Okuyarak (evet / hayır / belirlenemez):** **1 yorumda uydurma:** 1. adayın `rationale`'ı ya "
    "da `evidence_path`'i girdide olmayan ya da girdiyle çelişen bir veri iddiası içeriyor mu (girdide hi"
    'ç geçmeyen servis adı; değerin yönünü / büyüklüğünü ters söyleme; değeri başka servise, metriğe ya d'
    "a zamana bağlama)? Yoldaki kenarların izlerde görülmesi 1'e girmez (kanıt geçerliliği). **6 zaman ha"
    'tası:** 1. adayın gerekçesi alarm öncesine ait bir değeri alarm sonrası belirti gibi kullanıyor ya d'
    'a önce / sonra değerlerini karıştırıyor mu? **8 gerekçe–çağrı uyuşmazlığı (uyarlanmış; makalede tali'
    'mat–kod):** herhangi bir adımda `reason` belirli bir servis, metrik ya da zaman aralığı söylüyor ve '
    'çağrının argümanları başkasını mı soruyor? Gerekçe belirsizse hayır. 1 ve 6 geçerli cevap yoksa beli'
    'rlenemez. **Uygulanamaz:** **10 yanlış atfedilen kanıt** (tek ajanda yönetici–yürütücü aktarımı yok;'
    " aynı hata 1'e girer). Etiketleyen uygulama oturumu (Claude Code); Eren rastgele 10 satırı doğrular "
    "(P1'deki tohumlu seçim). Soru metni etiket dosyasına sha256 ile girer; etiketleme başladıktan sonra "
    "değişmez. P2d'de aynı sorular test başarısızlarına uygulanır (DECISIONS 2026-11-04); planlama testte"
    ' yalnız toplamları görür'
)


def questions_sha256() -> str:
    return hashlib.sha256(QUESTIONS.encode("utf-8")).hexdigest()


def kind_of(tool: str | None, args: dict) -> str | None:
    """Bir çağrının telemetri türü: "trace" / "metric" / "log" ya da None."""
    if tool in ("search_spans", "get_trace", "service_dependencies"):
        return "trace"
    if tool == "search_logs":
        return "log"
    if tool == "metric_series" and args.get("metric"):
        return "trace" if args["metric"] in TRACE_METRICS else "metric"
    return None


def coded(turns: list[dict], outputs: list[dict], row: dict, first_candidate: str | None,
          first_matched: str | None, label: dict) -> dict:
    """Kodla sayılan tuzaklar (+ T2'nin yan sayısı). `turns` vakanın tur kayıtları (tur sırasıyla), `outputs` araç
    çıktıları, `first_candidate` cevabın 1. adayının yazdığı servis adı (geçerli cevap yoksa None)."""
    root = label["answer"]["root_cause_service"]
    calls = [t for t in turns if t.get("tool")]
    args = [(t["tool"], (t.get("action") or {}).get("args") or {}) for t in calls]
    kinds = {k for tool, a in args if (k := kind_of(tool, a))}
    out = {
        "T2": "yes" if not any(a.get("service") == root for _, a in args) else "no",
        "T2_root_in_outputs": any(root in o["text"] for o in outputs),
        "T3": t3(first_matched, label),
        "T4": "yes" if any(t.get("tool_error") for t in calls) or row["end_reason"] == "schema_action" else "no",
        "T5": "yes" if len(kinds) <= 1 else "no",
        "T9": "yes" if len({t["call"] for t in calls}) < len(calls) else "no",
        "T11": "yes" if any(t.get("dropped") for t in turns) or row["end_reason"] == "budget" else "no",
        "T12": "yes" if row["end_reason"] == "step_limit" else "no",
    }
    if first_candidate is None:
        out["T7"] = "undetermined"
    else:
        k7 = {k for tool, a in args if a.get("service") == first_candidate and (k := kind_of(tool, a))}
        out["T7"] = "yes" if len(k7) <= 1 else "no"
    return out


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_run(run_dir: Path) -> dict:
    """Koşunun dev vakaları: satır, puan, turlar, araç çıktıları."""
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    scores = {c["incident_id"]: c for c in json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))["cases"]
              if c["set"] == "dev"}
    rows = {r["incident_id"]: r for r in _jsonl(run_dir / "responses.jsonl") if r["incident_id"] in scores}
    turns: dict[str, list[dict]] = {}
    for t in _jsonl(run_dir / "turns.jsonl"):
        if t["incident_id"] in rows:
            turns.setdefault(t["incident_id"], []).append(t)
    return {"dir": run_dir.name, "model": meta["settings"]["model"], "rows": rows, "scores": scores,
            "turns": {k: sorted(v, key=lambda t: t["turn"]) for k, v in turns.items()},
            "outputs": {k: _jsonl(run_dir / "tool_outputs" / f"{k}.jsonl") for k in rows}}


def select(runs: dict | None = None, eval_dir: Path | None = None, labels: dict | None = None) -> tuple[list, dict]:
    """(kapsamdaki satırlar, model → 18 vakanın kodla tuzak sayımları). Satırlar model, vaka sırasıyla."""
    runs = runs or ar.DEV_RUNS
    eval_dir = eval_dir or ar.EVAL
    labels = labels or dev_labels(REPO)
    missing = [k for k in RUN_KEYS if runs[k][0] is None]
    if missing:
        raise SystemExit(f"error: DEV_RUNS not filled yet: {missing}")
    rows, info = [], {}
    for key in RUN_KEYS:
        run = load_run(eval_dir / runs[key][0])
        counts = {t: dict.fromkeys(VALUES, 0) for t in CODED}
        for cid in sorted(run["rows"]):
            r, sc = run["rows"][cid], run["scores"][cid]
            ans = r.get("answer") if r.get("schema_valid") else None
            first_cand = ans["candidates"][0]["service"] if ans else None
            first_matched = sc["matched"][0] if sc.get("matched") else None
            c = coded(run["turns"].get(cid, []), run["outputs"][cid], r, first_cand, first_matched, labels[cid])
            for t in CODED:
                counts[t][c[t]] += 1
            if not sc["top1"]:
                rows.append({"key": f"{run['model']} {cid}", "model": run["model"], "incident_id": cid,
                             "run_dir": run["dir"], "end_reason": r["end_reason"], "valid_answer": ans is not None,
                             "top3": sc["top3"], "first_candidate": first_cand, "first_matched": first_matched,
                             **c})
        info[run["model"]] = {"n": len(run["rows"]), **counts}
    return rows, info


def sample(rows: list[dict], n: int = SAMPLE_N, seed: int = SEED) -> list[str]:
    """Eren doğrulaması için rastgele n satırın anahtarı (P1'deki tohumlu seçim)."""
    return sorted(random.Random(seed).sample([r["key"] for r in rows], min(n, len(rows))))


def dossier(out: Path, runs: dict | None = None, eval_dir: Path | None = None) -> list[dict]:
    """Satır başına okuma dosyası: etiket, kodla tuzaklar, her adımda gerekçe ve çağrı, araç çıktıları, son cevap."""
    runs = runs or ar.DEV_RUNS
    eval_dir = eval_dir or ar.EVAL
    labels = dev_labels(REPO)
    rows, _ = select(runs, eval_dir, labels)
    loaded = {k: load_run(eval_dir / runs[k][0]) for k in RUN_KEYS}
    by_model = {v["model"]: v for v in loaded.values()}
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for r in rows:
        run = by_model[r["model"]]
        cid = r["incident_id"]
        ans = labels[cid]["answer"]
        outputs = {o["turn"]: o for o in run["outputs"][cid]}
        L = [f"# {r['key']}", "", f"- Koşu: `{r['run_dir']}`; bitiş `{r['end_reason']}`; geçerli cevap "
             f"{r['valid_answer']}; kök ilk 3'te: {r['top3']}",
             f"- Etiket: kök `{ans['root_cause_service']}`, senaryo `{ans['scenario']}`, hata türü "
             f"`{ans.get('fault_type')}`, kategoriler {ans.get('categories')}",
             f"- Yayılım yolu: {ans['propagation_path']}",
             f"- 1. aday (yazılan / eşlenmiş): `{r['first_candidate']}` / `{r['first_matched']}`",
             "- Kodla: " + ", ".join(f"{t} {r[t]}" for t in CODED) +
             f"; kök adı araç çıktılarında: {r['T2_root_in_outputs']}", "", "## Adımlar", ""]
        for t in run["turns"].get(cid, []):
            act = t.get("action") or {}
            L += [f"### Tur {t['turn']} ({t['kind']})", "",
                  f"- reason: {act.get('reason')!r}" if t["kind"] == "action" else "- cevap turu",
                  f"- çağrı: `{t.get('call')}`" + (" (araç hatası)" if t.get("tool_error") else "")
                  + (f"; kırpılan adımlar {t['dropped']}" if t.get("dropped") else ""), ""]
            if t["turn"] in outputs:
                L += ["```", outputs[t["turn"]]["text"], "```", ""]
        row = run["rows"][cid]
        L += ["## Son cevap", "", "```json", json.dumps(row.get("answer"), ensure_ascii=False, indent=1), "```", ""]
        if not row.get("schema_valid"):
            L += ["Ham çıktı:", "", "```", str(row.get("raw_output")), "```", ""]
        name = f"{r['model']}__{cid}.md"
        (out / name).write_text("\n".join(L), encoding="utf-8")
        index.append({"key": r["key"], "file": name})
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "questions.md").write_text(QUESTIONS + "\n", encoding="utf-8")
    return index


def summary(repo: Path = REPO, runs: dict | None = None, eval_dir: Path | None = None) -> dict:
    labels_path = repo / LABELS_FILE
    doc = json.loads(labels_path.read_text(encoding="utf-8"))
    if doc["questions_sha256"] != questions_sha256() or doc["questions"] != QUESTIONS:
        raise ValueError("questions in the label file differ from QUESTIONS")
    rows, info = select(runs, eval_dir)
    if [x["key"] for x in doc["rows"]] != [r["key"] for r in rows]:
        raise ValueError("label rows differ from the selection")
    for x, r in zip(doc["rows"], rows):
        if any(x[t] != r[t] for t in CODED):
            raise ValueError(f"{x['key']}: coded traps differ from the records")
        if not r["valid_answer"] and (x["T1"], x["T6"]) != ("undetermined", "undetermined"):
            raise ValueError(f"{x['key']}: T1 / T6 must be undetermined without a valid answer")
    models = sorted({r["model"] for r in rows} | set(info))
    traps = {m: {"n": 0, **{t: dict.fromkeys(VALUES, 0) for t in TRAPS}} for m in models + ["all"]}
    for x in doc["rows"]:
        for c in (x["model"], "all"):
            traps[c]["n"] += 1
            for t in TRAPS:
                traps[c][t][x[t]] += 1
    checked = [x for x in doc["rows"] if "eren_check" in x]
    if not {x["key"] for x in checked} <= set(sample(rows)):
        raise ValueError("eren_check outside the sample")
    disagree = sum(x["eren_check"]["agree"] is False for x in checked)
    n_sample = min(SAMPLE_N, len(rows))
    reading = "pending" if len(checked) < n_sample else "relabel" if disagree > DISAGREE_MAX else "ok"
    return {"labels_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
            "questions_sha256": questions_sha256(), "rows": len(doc["rows"]), "traps": traps, "info_all_cases": info,
            "eren_check": {"n": n_sample, "checked": len(checked), "disagree": disagree, "reading": reading}}


READING_TEXT = {"pending": "bekliyor", "ok": "tamam (< 3 katılmıyorum)",
                "relabel": "yeniden etiketleme (≥ 3 katılmıyorum)"}


def summary_markdown(res: dict) -> str:
    out = ["# P2c hata analizi özeti", "",
           f"Üreten: `python tools/agent_error_analysis.py summary`. Etiketler `{LABELS_FILE.as_posix()}` sha256 "
           f"`{res['labels_sha256']}`, sorular sha256 `{res['questions_sha256']}` (tam metin etiket dosyasında; "
           f"DECISIONS 2026-11-14). Kapsam: dev, resmî dosya koşuları (Gemini 1. koşu, 4B), top-1'i ıskalayan "
           f"{res['rows']} satır. T10 uygulanamaz.", "",
           "## 1. Tuzaklar, ıskalanan satırlar (evet / hayır / belirlenemez)", "",
           "| Model | n | " + " | ".join(TRAPS) + " |", "|---" * (len(TRAPS) + 2) + "|"]
    for m, c in res["traps"].items():
        vals = [("—" if not c["n"] else "/".join(str(c[t][v]) for v in VALUES)) for t in TRAPS]
        out.append(f"| {'toplam' if m == 'all' else m} | {c['n']} | " + " | ".join(vals) + " |")
    out += ["", "## 2. Kodla sayılan tuzaklar, 18 vakanın tümü (bilgi)", "",
            "| Model | n | " + " | ".join(CODED) + " |", "|---" * (len(CODED) + 2) + "|"]
    for m, c in res["info_all_cases"].items():
        out.append(f"| {m} | {c['n']} | " + " | ".join("/".join(str(c[t][v]) for v in VALUES) for t in CODED) + " |")
    e = res["eren_check"]
    out += ["", "## 3. Eren doğrulaması", "",
            f"Örneklem {e['n']} satır (tohum {SEED}); işaretlenen {e['checked']}, katılmıyorum {e['disagree']}. "
            f"Okuma: {READING_TEXT[e['reading']]}.", ""]
    return "\n".join(out)


def summary_render(repo: Path = REPO) -> tuple[str, str]:
    res = summary(repo)
    return summary_markdown(res), json.dumps(res, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agent_error_analysis.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    d = sub.add_parser("dossier")
    d.add_argument("--out", type=Path, required=True)
    sub.add_parser("sample")
    sm = sub.add_parser("summary")
    sm.add_argument("--check", action="store_true", help="regenerate and compare with the files in the repo")
    args = p.parse_args(argv)
    if args.cmd == "select":
        rows, info = select()
        print(json.dumps({"rows": rows, "info_all_cases": info}, ensure_ascii=False, indent=1))
    elif args.cmd == "dossier":
        print(f"{len(dossier(args.out))} files -> {args.out}")
    elif args.cmd == "sample":
        rows, _ = select()
        print("\n".join(sample(rows)))
    else:
        md, js = summary_render()
        if args.check:
            same = (REPO / SUMMARY_MD).read_text(encoding="utf-8") == md and \
                (REPO / SUMMARY_JSON).read_text(encoding="utf-8") == js
            print("same" if same else "different")
            return 0 if same else 1
        (REPO / SUMMARY_MD).write_text(md, encoding="utf-8")
        (REPO / SUMMARY_JSON).write_text(js, encoding="utf-8")
        print(f"-> {SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
