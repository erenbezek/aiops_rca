"""P1 sonuç tablosu (HANDOFF 2026-11-04 P1e kartı 2. madde; DECISIONS 2026-11-04 "P1e sonuç tablosu repoda",
"P1e dev–test okuması", 2026-11-03 "P1e'de qwen3.5-9b bilgi satırı").

    python -m aiops_rca.results            # results/p1_table.md ve .json'u yazar
    python -m aiops_rca.results --check    # yeniden üretir, repodaki dosyalarla bayt aynı değilse çıkış 1

Girdi: `results/p1_runs.json` (her satırın dev ve test resmî koşu klasörü; test henüz yoksa null) ve `incidents/`
etiketleri (grup için senaryo). Puanlar koşu klasörlerindeki `scores.json` vaka satırlarından okunur; puanlama burada
yeniden yapılmaz (snapshot repoda yok). Her satır için denetlenir: `run.json` yöntemi / modeli / seviyesi satırla aynı,
takma ad yok, `scores.json` o setin bütün geçerli vakalarını tam bir kez içeriyor. Tutmazsa hata, tablo yazılmaz.

Ölçüler `scoring._metrics` ile (P1d analiziyle aynı tanımlar) + süre ortalaması ve en çoğu (cevap gelen satırlarda).
Gruplar: tümü, demo senaryoları, kendi hatalarımız (networkDelay, packetLoss, cpuThrottle, containerPause, containerStop,
quoteGateway*).

Okumalar (kurallar koşudan önce yazıldı):
  - Dev–test: her satırda top-3, iki yönlü Fisher kesin testi; p < 0,05 → "fark" (düşüş / artış), değilse "ayırt
    edilemedi". Çoklu karşılaştırma düzeltmesi yok.
  - 9B bilgi satırı: testte daraltma top-3; yalnız 9B'nin ve yalnız 4B'nin bildiği vaka sayıları; bir yönde ≥ 6 ve
    öteki 0 → "fark", değilse "ayırt edilemedi".
Çıktıda zaman damgası yok: aynı girdiden bayt aynı dosya.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from math import comb
from pathlib import Path

from aiops_rca.cases import REPO, _check_sets, _labels
from aiops_rca.scoring import _metrics

SETS = ("dev", "test")
GROUPS = ("all", "demo", "own")
GROUP_TEXT = {"all": "tümü", "demo": "demo senaryoları", "own": "kendi hatalarımız"}
OWN_SCENARIOS = {"networkDelay", "packetLoss", "cpuThrottle", "containerPause", "containerStop"}  # + quoteGateway*
LEVEL_TEXT = {"raw": "ham", "summary": "özet", "narrowed": "daraltma"}
METHOD_TEXT = {"rule": "kural", "baro": "BARO", "narrowing": "daraltma referansı"}
READING_TEXT = {"down": "fark (düşüş)", "up": "fark (artış)", "none": "ayırt edilemedi"}
ALPHA = (5, 100)                      # p < 0,05 (kesir olarak; karşılaştırma tam sayılarla)
B9_ROWS = ("qwen3.5-9b narrowed", "qwen3.5-4b narrowed")
B9_MIN = 6


def row_id(row: dict) -> str:
    return row["method"] if row["method"] != "llm" else f"{row['model']} {row['level']}"


def row_text(row: dict) -> str:
    if row["method"] != "llm":
        return METHOD_TEXT[row["method"]]
    return f"{row['model']} {LEVEL_TEXT[row['level']]}" + (" (bilgi)" if row.get("info") else "")


def group_of(label: dict) -> str:
    s = label["answer"]["scenario"]
    return "own" if s in OWN_SCENARIOS or s.startswith("quoteGateway") else "demo"


# --- okumalar ---

def fisher(a: int, n1: int, b: int, n2: int) -> tuple[int, int]:
    """2×2 tabloda (a / n1 başarı, b / n2 başarı) iki yönlü Fisher kesin testi; p = pay / payda (tam sayılar).
    İki yön: olasılığı gözlenenden büyük olmayan bütün tablolar."""
    k, n = a + b, n1 + n2
    lo, hi = max(0, k - n2), min(k, n1)
    w = {x: comb(n1, x) * comb(n2, k - x) for x in range(lo, hi + 1)}
    return sum(v for v in w.values() if v <= w[a]), comb(n, k)


def dev_test_reading(dev: int, n_dev: int, test: int, n_test: int) -> dict:
    num, den = fisher(dev, n_dev, test, n_test)
    diff = num * ALPHA[1] < ALPHA[0] * den
    return {"dev_top3": dev, "test_top3": test, "n_dev": n_dev, "n_test": n_test, "p": round(num / den, 4),
            "reading": ("down" if test * n_dev < dev * n_test else "up") if diff else "none"}


def reading_9b(only_9b: int, only_4b: int) -> str:
    if only_9b >= B9_MIN and only_4b == 0:
        return "9b"
    if only_4b >= B9_MIN and only_9b == 0:
        return "4b"
    return "none"


# --- okuma ve denetim ---

def check_run(row: dict, set_: str, meta: dict, scores: dict, label_ids: set[str]) -> list[str]:
    """Koşu kaydı satıra ve sete uyuyor mu; hata listesi (boş = tamam)."""
    errors = []
    st = meta.get("settings") or {}
    if meta.get("method") != row["method"]:
        errors.append(f"method {meta.get('method')} != {row['method']}")
    if row["method"] == "llm" and (st.get("model"), st.get("level")) != (row["model"], row["level"]):
        errors.append(f"model/level {st.get('model')}/{st.get('level')} != {row['model']}/{row['level']}")
    if st.get("alias"):
        errors.append("alias run")
    if set_ not in meta.get("sets", []):
        errors.append(f"set {set_} not in run sets {meta.get('sets')}")
    ids = [c["incident_id"] for c in scores["cases"] if c["set"] == set_]
    if sorted(ids) != sorted(label_ids) or len(ids) != len(set(ids)):
        errors.append(f"{set_} cases in scores.json ({len(ids)}) != valid {set_} labels ({len(label_ids)})")
    return errors


def metrics(rows: list[dict]) -> dict:
    m = _metrics(rows)
    answered = [r for r in rows if r.get("input_status", "ok") == "ok" and not r.get("no_answer")]
    d = [r["duration_s"] for r in answered if r.get("duration_s") is not None]
    m.update(duration_s_mean=round(sum(d) / len(d), 3) if d else None, duration_s_max=max(d) if d else None)
    return m


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(repo: Path = REPO) -> dict:
    runs_file = repo / "results" / "p1_runs.json"
    spec = json.loads(runs_file.read_text(encoding="utf-8"))
    used = [s for s in SETS if any(r["runs"].get(s) for r in spec["rows"])]
    labels = {}
    for s in used:
        _check_sets((s,), s == "test")  # test etiketleri yalnız test koşusu listedeyse okunur
        labels[s] = {d["incident_id"]: d for d in _labels((s,), repo / "incidents")}
    rows, errors, seen = [], [], set()
    for row in spec["rows"]:
        rid = row_id(row)
        if rid in seen:
            errors.append(f"duplicate row {rid}")
        seen.add(rid)
        out = {"id": rid, "label": row_text(row), "info": bool(row.get("info")), "runs": {}}
        for s in SETS:
            run_dir = row["runs"].get(s)
            if not run_dir:
                out[s] = None
                continue
            meta = json.loads((repo / run_dir / "run.json").read_text(encoding="utf-8"))
            scores = json.loads((repo / run_dir / "scores.json").read_text(encoding="utf-8"))
            errors += [f"{rid} {s} {run_dir}: {e}" for e in check_run(row, s, meta, scores, set(labels[s]))]
            cases = [c for c in scores["cases"] if c["set"] == s]
            out["runs"][s] = {"run_dir": run_dir, "scores_sha256": sha256(repo / run_dir / "scores.json")}
            out[s] = {g: metrics([c for c in cases if g == "all" or group_of(labels[s][c["incident_id"]]) == g])
                      for g in GROUPS}
            out[s + "_top3_ids"] = sorted(c["incident_id"] for c in cases if c["top3"])
        dev, test = out["dev"], out["test"]
        out["dev_test"] = (dev_test_reading(dev["all"]["top3"], dev["all"]["n"], test["all"]["top3"], test["all"]["n"])
                           if dev and test else None)
        rows.append(out)
    if errors:
        raise ValueError("p1_runs.json does not match the run records:\n" + "\n".join(errors))
    by_id = {r["id"]: r for r in rows}
    b9 = None
    if all(i in by_id and by_id[i]["test"] for i in B9_ROWS):
        s9, s4 = set(by_id[B9_ROWS[0]]["test_top3_ids"]), set(by_id[B9_ROWS[1]]["test_top3_ids"])
        b9 = {"set": "test", "only_9b": len(s9 - s4), "only_4b": len(s4 - s9), "both": len(s9 & s4)}
        b9["reading"] = reading_9b(b9["only_9b"], b9["only_4b"])
    for r in rows:  # vaka kimlikleri yalnız 9B okumasında kullanılır, çıktıya girmez
        r.pop("dev_top3_ids", None)
        r.pop("test_top3_ids", None)
    return {"source": {"runs_file": "results/p1_runs.json", "runs_file_sha256": sha256(runs_file)},
            "rows": rows, "reading_9b": b9}


# --- yazma ---

def f(v) -> str:
    return "—" if v is None else str(v)


COLUMNS = ("top-1", "top-3", "Kanıt g/ge/k", "Örtüşme", "Brier", "Seçici doğ.", "Kapsama", "Şema dışı", "Boş",
           "Bütçe aşımı", "Cevapsız", "Süre ort/en çok (sn)", "Token giriş/çıkış")


def cells(m: dict) -> list[str]:
    return [f"{m['top1']}/{m['n']}", f"{m['top3']}/{m['n']}",
            f"{m['evidence_valid']}/{m['evidence_invalid']}/{m['evidence_null']}", f(m["label_path_overlap_mean"]),
            f(m["brier"]), f(m["selective_accuracy"]), f(m["coverage"]), f(m["schema_invalid"]), f(m["input_empty"]),
            f(m["input_over_budget"]), f(m["no_answer"]), f"{f(m['duration_s_mean'])}/{f(m['duration_s_max'])}",
            "—" if m["tokens_input"] is None else f"{m['tokens_input']}/{m['tokens_output']}"]


def markdown(res: dict) -> str:
    rows = res["rows"]
    L = ["# P1 sonuç tablosu", "",
         f"Üreten: `python -m aiops_rca.results`. Koşu listesi `{res['source']['runs_file']}` sha256 "
         f"`{res['source']['runs_file_sha256']}`. Puanlar koşu klasörlerindeki `scores.json`'dan; puanlama burada "
         "yeniden yapılmaz.", "",
         "## 1. Dev–test (top-3)", "",
         "| Satır | top-1 dev | top-1 test | top-3 dev | top-3 test | p (Fisher, iki yönlü) | Okuma |",
         "|---|---|---|---|---|---|---|"]
    for r in rows:
        d, t, dt = r["dev"], r["test"], r["dev_test"]
        top = lambda m, k: "—" if m is None else f"{m['all'][k]}/{m['all']['n']}"
        L.append(f"| {r['label']} | {top(d, 'top1')} | {top(t, 'top1')} | {top(d, 'top3')} | {top(t, 'top3')} | "
                 f"{'—' if dt is None else dt['p']} | {'—' if dt is None else READING_TEXT[dt['reading']]} |")
    L += ["", "Kural (DECISIONS 2026-11-04 \"P1e dev–test okuması\"): p < 0,05 → fark (yönüyle), değilse ayırt "
          "edilemedi. Çoklu karşılaştırma düzeltmesi yok; bu kadar satırda biri tesadüfen \"fark\" çıkabilir. Fark, "
          "aşırı uyumla dağılım farkını ayıramaz.", "",
          "## 2. 9B bilgi satırı (test, daraltma top-3)", ""]
    b9 = res["reading_9b"]
    if b9 is None:
        L.append("Test koşusu yok.")
    else:
        text = {"9b": "fark (9B lehine)", "4b": "fark (4B lehine)", "none": "ayırt edilemedi"}[b9["reading"]]
        L += ["| Yalnız 9B | Yalnız 4B | İkisi de | Okuma |", "|---|---|---|---|",
              f"| {b9['only_9b']} | {b9['only_4b']} | {b9['both']} | {text} |"]
    L += ["", "Kural (DECISIONS 2026-11-03): bir yönde ≥ 6 ve öteki 0 → fark, değilse ayırt edilemedi. 9B seçimi ve "
          "hiçbir kararı değiştirmez."]
    for n, s in ((3, "dev"), (4, "test")):
        for g in GROUPS:
            present = [r for r in rows if r[s]]
            size = present[0][s][g]["n"] if present else None
            L += ["", f"## {n}. {s.capitalize()} ayrıntı: {GROUP_TEXT[g]}" + (f" ({size})" if size is not None else ""),
                  ""]
            if not present:
                L.append(f"{s.capitalize()} koşusu yok.")
                continue
            L += ["| Satır | " + " | ".join(COLUMNS) + " |", "|---" * (len(COLUMNS) + 1) + "|"]
            L += [f"| {r['label']} | " + " | ".join(cells(r[s][g])) + " |" for r in present]
    return "\n".join(L) + "\n"


def render(repo: Path = REPO) -> tuple[str, str]:
    res = build(repo)
    return markdown(res), json.dumps(res, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aiops_rca.results", description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="regenerate and compare with the files in the repo")
    args = p.parse_args(argv)
    try:
        md, js = render()
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    out_md, out_json = REPO / "results" / "p1_table.md", REPO / "results" / "p1_table.json"
    if args.check:
        same = [path.exists() and path.read_text(encoding="utf-8") == text for path, text in ((out_md, md), (out_json, js))]
        print("same" if all(same) else "differs: " + ", ".join(p.name for p, ok in zip((out_md, out_json), same) if not ok))
        return 0 if all(same) else 1
    out_md.write_text(md, encoding="utf-8")
    out_json.write_text(js, encoding="utf-8")
    print(f"{out_md.relative_to(REPO)} {sha256(out_md)}\n{out_json.relative_to(REPO)} {sha256(out_json)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
