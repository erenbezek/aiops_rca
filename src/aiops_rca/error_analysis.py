"""Dev hata analizi (HANDOFF 2026-11-04 P1e kartı 3. madde; DECISIONS 2026-11-04 "P1e hata analizi kapsamı",
"P1e hata sınıflaması").

    python -m aiops_rca.error_analysis select              # kapsamdaki satırlar ve otomatik türler (stdout)
    python -m aiops_rca.error_analysis dossier --out DIR   # satır başına çalışma dosyası (snapshot + yerel tokenizer)
    python -m aiops_rca.error_analysis sample              # Eren doğrulaması için 10 satır (tohum 20261104)
    python -m aiops_rca.error_analysis summary [--check]   # results/p1_error_summary.md / .json (yalnız sayımlar)

Kapsam: `results/p1_runs.json`'daki dev koşularından (P1d a1, gerçek ad) 4B, gpt-oss ve Gemini × ham / özet / daraltma;
girdi sorulmuş (`input_status` ok), cevap gelmiş, şema içi ve top-1'i ıskalayan satırlar. Kural, BARO, daraltma
referansı ve 9B kapsam dışı. Kapsam dışındaki ıskalamalar otomatik türlerle sayılır, etiketlenmez: boş girdi, bütçe
aşımı, cevapsız, şema dışı (sınıra takılan dahil; tekrar döngüsü ayrıca sayılır).

T3 (belirtiyi neden sanma) kodla: 1. aday (eşlenmiş adıyla) etiketin yayılım yolunda kökten başka bir servisse evet;
yolda değilse hayır; ad eşleşmediyse belirlenemez.

`root_visibility: direct` kodla (planlama + Eren, 2026-11-04): kuralın sinyal tanımı (`signals.signals`, güç ≥ 1) kökün
girdideki kendi değerlerine uygulanır; girdide olmayan alan sayılmaz. Özet ve daraltmada kökün satırı (istek, hata
oranı, p95, CPU ve bellek ortalaması; veritabanlarında yalnız CPU/bellek) ve girdideki logları (`count_before` 0 olan
mesajın `count_after`'ı); ham seviyede yalnız kökün `log` satırları, mesaj `signals.normalize` ile, alarmdan önce / sonra
satırın saatine göre sayılır. En az bir sinyal → `direct`. `indirect` / `absent` etiketlemede.

`dossier`: her satır için modelin o seviyedeki girdisi yeniden üretilir (`inputs.<seviye>_input`, sayım yerel Qwen
tokenizer'ıyla; sunucu açılır, üretim yapılmaz) ve sha256'sı kayıttaki `input_sha256` ile aynı olmalı (değilse
durur). Dosyada etiket, T3, modelin cevabı ve girdi. Test vakası hiç okunmaz.

`summary` (HANDOFF 2026-11-05): etiket dosyasından tuzak × model × seviye sayımları, otomatik türler, kökün
görünürlüğüne göre T3, Eren doğrulamasının durumu (`eren_check.agree`; 10 satırın ≥ 3'ünde katılmıyorum → yeniden
etiketleme) ve ad eşlenmemesi: kök, ilk 3'te eşlenmemiş bir adla (`name_key` aynı) geçtiği hâlde ıskalama sayılan
satırlar, dev ve test, LLM satırları. Test burada yalnız `scores.json` ve etiketin kök adıyla, hücre başına sayım
olarak okunur; vaka kimliği çıktıya girmez. Puanlama değişmez.
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
from aiops_rca.signals import DB_SERVICES, normalize, signals

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


RAW_LINE = re.compile(r"^(\d\d):(\d\d):(\d\d)\.(\d{3}) (\S+) (log|error-span) (.*)$")
DAY_MS = 24 * 3600 * 1000


def _row_from_input(entry: dict, logs: list[dict]) -> dict:
    """Girdideki servis satırını `signals.signals`'ın alan adlarına çevirir (yalnız girdide olan alanlar)."""
    row = {k: entry[k] for k in ("requests_before", "requests_after", "error_rate_before", "error_rate_after",
                                 "p95_ms_before", "p95_ms_after") if k in entry}
    for src, dst in (("cpu_pct_avg", "cpu_pct"), ("mem_mb_avg", "mem_mb")):
        for side in ("before", "after"):
            if f"{src}_{side}" in entry:
                row[f"{dst}_{side}"] = entry[f"{src}_{side}"]
    new = [(m["count_after"], m["message"]) for m in logs if m["count_before"] == 0 and m["count_after"] > 0]
    if new:
        row["new_warn_top"] = max(new)
    return row


def _raw_row(text: str, root: str, alarm_ns: int) -> dict:
    alarm_ms = (alarm_ns // 10**6) % DAY_MS
    counts: dict[str, list[int]] = {}
    for line in text.splitlines():
        m = RAW_LINE.match(line)
        if not m or m.group(5) != root or m.group(6) != "log":
            continue
        t = ((int(m.group(1)) * 60 + int(m.group(2))) * 60 + int(m.group(3))) * 1000 + int(m.group(4))
        if t - alarm_ms > DAY_MS / 2:      # pencere gece yarısını aşarsa
            t -= DAY_MS
        elif alarm_ms - t > DAY_MS / 2:
            t += DAY_MS
        c = counts.setdefault(normalize(m.group(7)), [0, 0])
        c[t >= alarm_ms] += 1
    new = [(after, msg) for msg, (before, after) in counts.items() if before == 0 and after > 0]
    return {"new_warn_top": max(new)} if new else {}


def direct_signals(level: str, text: str, root: str, alarm_ns: int) -> list[str]:
    """Kökün girdideki kendi değerlerinde gücü ≥ 1 olan sinyaller (boş liste = `direct` değil)."""
    if level == "raw":
        row = _raw_row(text, root, alarm_ns)
        sig = {"new_warn_log": signals(row)[0]["new_warn_log"]} if row else {}
    else:
        data = json.loads(text)
        if level == "summary":
            entry = next((s for s in data["services"] if s["service"] == root), None)
            logs = [m for m in data["top_warning_and_error_logs_after_alarm"] if m["service"] == root]
        else:
            entry = next((c for c in data["candidates"] if c["service"] == root), None)
            logs = entry.get("logs", []) if entry else []
        if entry is None and not logs:
            return []
        row = _row_from_input(entry or {}, logs)
        sig, _ = signals(row, root in DB_SERVICES)
        if "new_warn_top" not in row:
            sig.pop("new_warn_log", None)
    return sorted(k for k, v in sig.items() if v["strength"] >= 1)


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


# --- özet (yalnız sayımlar) ---

TRAPS = ("T1", "T2", "T3", "T4", "T5", "T6")
VALUES = ("yes", "no", "undetermined")
VISIBILITY = ("direct", "indirect", "absent")
DISAGREE_MAX = 2  # HANDOFF 2026-11-04: 10 satırın ≥ 3'ünde katılmıyorum → sorular netleşir, 29 satır yeniden
LABELS_FILE = Path("results") / "p1_error_labels.json"
SUMMARY_MD, SUMMARY_JSON = Path("results") / "p1_error_summary.md", Path("results") / "p1_error_summary.json"


def name_key(name: str) -> str:
    """Ad karşılaştırma anahtarı (planlama 2026-11-05): küçük harf, son nokta parçası, `/` öncesi, sondaki `service`
    atılır, yalnız harfler. `oteldemo.CartService/GetCart` → `cart`, `product-catalog` → `productcatalog`."""
    s = name.lower().split(".")[-1].split("/")[0]
    s = s[: -len("service")] if s.endswith("service") else s
    return re.sub(r"[^a-z]", "", s)


def name_miss_rank(case: dict, root: str) -> int | None:
    """Iskalama sayılan şema içi satırda kök, ilk 3'te eşlenmemiş bir adla geçiyorsa o adın sırası (1–3)."""
    if case.get("schema_valid") is not True or case["top3"]:
        return None
    unmatched = iter(case["unmatched"])
    for i, m in enumerate(case["matched"][:3]):
        if m is None and name_key(next(unmatched)) == name_key(root):
            return i + 1
    return None


def name_misses(repo: Path = REPO) -> dict:
    """(model seviye) → set → {count, first}: ad eşlenmemesiyle ıskalama sayılan satır sayısı, kaçı 1. sırada."""
    spec = json.loads((repo / "results" / "p1_runs.json").read_text(encoding="utf-8"))
    llm = [r for r in spec["rows"] if r["method"] == "llm"]
    out: dict[str, dict] = {f"{r['model']} {r['level']}": {} for r in llm}
    for s in ("dev", "test"):
        if not any(r["runs"].get(s) for r in llm):
            continue
        _check_sets((s,), s == "test")  # test yalnız test koşusu listedeyse okunur
        roots = {d["incident_id"]: d["answer"]["root_cause_service"] for d in _labels((s,), repo / "incidents")}
        for r in llm:
            if not r["runs"].get(s):
                continue
            cases = json.loads((repo / r["runs"][s] / "scores.json").read_text(encoding="utf-8"))["cases"]
            ranks = [k for c in cases if c["set"] == s and (k := name_miss_rank(c, roots[c["incident_id"]]))]
            out[f"{r['model']} {r['level']}"][s] = {"count": len(ranks), "first": sum(k == 1 for k in ranks)}
    return out


def summary(repo: Path = REPO) -> dict:
    labels_path = repo / LABELS_FILE
    doc = json.loads(labels_path.read_text(encoding="utf-8"))
    rows, auto = select(repo)
    if [x["key"] for x in doc["rows"]] != [r["key"] for r in rows]:
        raise ValueError("label rows differ from the selection")
    cells = [f"{m} {lv}" for m in MODELS_IN for lv in LEVELS]
    traps = {c: {"n": 0, **{t: dict.fromkeys(VALUES, 0) for t in TRAPS}} for c in cells + ["all"]}
    vis = {v: {"n": 0, "T3": dict.fromkeys(VALUES, 0)} for v in VISIBILITY}
    for x in doc["rows"]:
        for c in (f"{x['model']} {x['level']}", "all"):
            traps[c]["n"] += 1
            for t in TRAPS:
                traps[c][t][x[t]] += 1
        vis[x["root_visibility"]]["n"] += 1
        vis[x["root_visibility"]]["T3"][x["T3"]] += 1
    checked = [x for x in doc["rows"] if "eren_check" in x]
    if not {x["key"] for x in checked} <= set(sample(rows)):
        raise ValueError("eren_check outside the sample")
    disagree = sum(x["eren_check"]["agree"] is False for x in checked)
    reading = "pending" if len(checked) < SAMPLE_N else "relabel" if disagree > DISAGREE_MAX else "ok"
    return {"labels_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
            "questions_sha256": doc["questions_sha256"], "rows": len(doc["rows"]), "auto": auto, "traps": traps,
            "visibility": vis, "name_misses": name_misses(repo),
            "eren_check": {"n": SAMPLE_N, "checked": len(checked), "disagree": disagree, "reading": reading}}


LEVEL_TEXT = {"raw": "ham", "summary": "özet", "narrowed": "daraltma"}
READING_TEXT = {"pending": "bekliyor", "ok": "tamam (< 3 katılmıyorum)",
                "relabel": "yeniden etiketleme (≥ 3 katılmıyorum)"}


def _cell_text(cell: str) -> str:
    model, level = cell.rsplit(" ", 1)
    return f"{model} {LEVEL_TEXT[level]}"


def summary_markdown(res: dict) -> str:
    auto_cols = (("empty", "boş"), ("over_budget", "bütçe aşımı"), ("no_answer", "cevapsız"),
                 ("schema_invalid", "şema dışı"), ("repetition_loop", "tekrar döngüsü"), ("top1_hit", "top-1 isabet"),
                 ("in_scope", "etiketlenen"))
    out = ["# P1e hata analizi özeti", "",
           f"Üreten: `python -m aiops_rca.error_analysis summary`. Etiketler `{LABELS_FILE.as_posix()}` sha256 "
           f"`{res['labels_sha256']}`, sorular sha256 `{res['questions_sha256']}` (tam metin etiket dosyasında). "
           f"Kapsam: dev, P1d a1 (gerçek ad), 4B / gpt-oss / Gemini × ham / özet / daraltma; girdi sorulmuş, şema "
           f"içi, top-1'i ıskalayan {res['rows']} satır.", "",
           "## 1. Otomatik türler (dev, satır başına 18 vaka)", "",
           "| Satır | " + " | ".join(t for _, t in auto_cols) + " |", "|---" * (len(auto_cols) + 1) + "|"]
    for cell, c in res["auto"].items():
        out.append(f"| {_cell_text(cell)} | " + " | ".join(str(c[k]) for k, _ in auto_cols) + " |")
    out += ["", "## 2. Tuzaklar (evet / hayır / belirlenemez)", "",
            "| Satır | n | " + " | ".join(TRAPS) + " |", "|---" * (len(TRAPS) + 2) + "|"]
    for cell, c in res["traps"].items():
        name = "toplam" if cell == "all" else _cell_text(cell)
        vals = [("—" if not c["n"] else "/".join(str(c[t][v]) for v in VALUES)) for t in TRAPS]
        out.append(f"| {name} | {c['n']} | " + " | ".join(vals) + " |")
    out += ["", "## 3. Kökün görünürlüğüne göre T3", "",
            "| Görünürlük | n | T3 evet | T3 hayır | T3 belirlenemez |", "|---|---|---|---|---|"]
    for v, c in res["visibility"].items():
        out.append(f"| {v} | {c['n']} | " + " | ".join(str(c["T3"][x]) for x in VALUES) + " |")
    out += ["", "## 4. Ad eşlenmemesiyle ıskalama sayılan satırlar (LLM, dev ve test)", "",
            "Kök ilk 3'te eşlenmemiş bir adla geçiyor (`name_key` aynı: küçük harf, son nokta parçası, `/` öncesi, "
            "sondaki `service` atılır, yalnız harfler) ve satır ıskalama sayılmış. Puanlama değişmez; hücre başına "
            "sayım, vaka yok. \"1. sırada\": o ad 1. adaydı.", "",
            "| Satır | dev | dev 1. sırada | test | test 1. sırada |", "|---|---|---|---|---|"]
    tot = {s: [0, 0] for s in ("dev", "test")}
    for cell, by in res["name_misses"].items():
        vals = []
        for s in ("dev", "test"):
            c = by.get(s)
            vals += ["—", "—"] if c is None else [str(c["count"]), str(c["first"])]
            if c:
                tot[s][0] += c["count"]
                tot[s][1] += c["first"]
        out.append(f"| {_cell_text(cell)} | " + " | ".join(vals) + " |")
    out.append("| toplam | " + " | ".join(f"{tot[s][0]} | {tot[s][1]}" for s in ("dev", "test")) + " |")
    e = res["eren_check"]
    out += ["", "## 5. Eren doğrulaması", "",
            f"Örneklem {e['n']} satır (tohum {SEED}); işaretlenen {e['checked']}, katılmıyorum {e['disagree']}. "
            f"Okuma: {READING_TEXT[e['reading']]}.", ""]
    return "\n".join(out)


def summary_render(repo: Path = REPO) -> tuple[str, str]:
    res = summary(repo)
    return summary_markdown(res), json.dumps(res, ensure_ascii=False, indent=1) + "\n"


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
            direct = direct_signals(r["level"], inp["text"], ans["root_cause_service"], cases[r["incident_id"]].alarm_ns)
            name = f"{r['model']}__{r['level']}__{r['incident_id']}.md"
            text = "\n".join([
                f"# {r['key']}", "",
                f"- Koşu: `{r['run_dir']}`; girdi sha256 `{sha}` (kayıtla aynı); veri token {inp['data_tokens']}",
                f"- Etiket: kök `{ans['root_cause_service']}`, senaryo `{ans['scenario']}`, hata türü "
                f"`{ans.get('fault_type')}`, kategoriler {ans.get('categories')}",
                f"- Yayılım yolu: {ans['propagation_path']}",
                f"- 1. aday (eşlenmiş): `{r['first_matched']}`; kök ilk 3'te: {r['top3']}; T3 (kod): {r['t3']}",
                f"- Kökün girdideki kendi sinyalleri (kod, güç ≥ 1): {direct or 'yok'} → "
                f"{'direct' if direct else 'direct değil (indirect / absent etiketlemede)'}", "",
                "## Cevap", "", "```json", json.dumps(resp["answer"], ensure_ascii=False, indent=1), "```", "",
                "## Girdi", "", "```", inp["text"], "```", ""])
            (out / name).write_text(text, encoding="utf-8")
            index.append({"key": r["key"], "file": name, "input_sha256": sha, "direct_signals": direct})
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aiops_rca.error_analysis", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    d = sub.add_parser("dossier")
    d.add_argument("--out", type=Path, required=True)
    sub.add_parser("sample")
    sm = sub.add_parser("summary")
    sm.add_argument("--check", action="store_true", help="regenerate and compare with the files in the repo")
    args = p.parse_args(argv)
    if args.cmd == "summary":
        md, js = summary_render()
        files = ((REPO / SUMMARY_MD, md), (REPO / SUMMARY_JSON, js))
        if args.check:
            same = [path.exists() and path.read_text(encoding="utf-8") == text for path, text in files]
            print("same" if all(same) else "differs: " + ", ".join(f.name for (f, _), ok in zip(files, same) if not ok))
            return 0 if all(same) else 1
        for path, text in files:
            path.write_text(text, encoding="utf-8")
            print(f"{path.relative_to(REPO)} {hashlib.sha256(path.read_bytes()).hexdigest()}")
        return 0
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
