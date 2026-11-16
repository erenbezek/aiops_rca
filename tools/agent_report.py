"""P2b pilot dumanı raporu (HANDOFF 2026-11-13, 5. madde; Eren onaylı ad), P2c-0 pilot tasarım turu raporu ve P2c
dev raporu; P2d test raporu.

    python tools/agent_report.py [--report p2b|p2c0|p2c_dev|p2d] [--check]

`REPORTS` rapor adını çıktıya, koşulara ve 4B kuralının koşusuna bağlar; `--report` verilmezse `p2b`.
- `p2b`: `eval_responses/`'teki üç pilot koşusu (`RUNS`; `responses.jsonl`, `turns.jsonl`, `scores.json`). Çıktı
  `results/p2b_pilot.json` ve `.md` (P2c-0'dan önceki hâliyle bayt aynı).
- `p2c0`: eski (P2b) ve yeni (P2c-0, tek yeniden koşu) pilot yan yana (`PAIRS`), iki kural yeni koşulara; servissiz
  `metric_series` çağrıları. Çıktı `results/p2c0_pilot.json` ve `.md` (DECISIONS 2026-11-13 "tek pilot tasarım turu").
- `p2c_dev`: dev koşuları (`DEV_RUNS`; dört koşu, canlı iki model) ve önceden yazılı iki okuma kuralı (DECISIONS
  2026-11-14 "P2c dosya ↔ canlı okuma kuralı" + düzeltme, "P2c ajan ↔ P1 okuma kuralı"); çağrı düzeyi sınıflar
  `results/p2c_dev_calls.json`'dan (`tools/agent_compare.py`). Çıktı `results/p2c_dev.json` ve `.md`. Yalnız dev
  satırları okunur; P1 tarafı `results/p1_runs.json`'daki dev koşuları (test koşuları okunmaz).
- `p2d`: test koşuları (`TEST_RUNS`, anahtarlar dev'deki gibi; teknik kesintiler `TEST_INTERRUPTED`), aynı iki okuma
  kuralı ve dev–test okuması (DECISIONS 2026-11-16: yalnız iki dosya satırı, top-3, P1e'nin `results.dev_test_reading`
  Fisher testi); çağrı düzeyi sınıflar `results/p2d_test_calls.json`'dan. Sonuç tablosu ajan ve P1 satırları dev ve test
  yan yana (P1 gpt-oss ve 9B bilgi olarak, `p1_info`). Çıktı `results/p2d_test.json` ve `.md`. **Yalnız toplamlar**
  (HANDOFF 2026-11-16 P2d kartı; planlama kontrolü 2026-11-17 şart 3): vaka tablosu yok; vaka kimliği listeleri
  (açıklanamayan çağrılar, "model ayrıştı", "oynatılamadı", işaret testinin `only_*_cases`'i, koşu özetinin vaka
  satırları) testte sayıya iner ya da düşer. `TEST_RUNS` dolmadan rapor üretilmez (çıkış hatası).
`--check`: yeniden üretir ve repodakiyle bayt aynı mı bakar (CI; snapshot gerekmez).

İçerik: koşu başına bitiş nedenleri, araç / istek / token / süre, kırpma, tekrarlanan çağrı, araç hatası, kesilen
sonuç, HTTP durumları; 4B kuralı (DECISIONS 2026-11-13) ve bütçe yeniden açma kuralı (DECISIONS 2026-11-09);
vaka tablosu. Pilot isabeti (`scores.json`) yalnız bilgi: istem ve araçlar pilotta belirlendi, hiçbir karara girmez.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from math import comb
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

from aiops_rca.llm_client import GEMINI_RETRY_WAITS, MODELS, RETRY_WAIT, TRANSPORT_ERRORS  # noqa: E402
EVAL = REPO / "eval_responses"
OUT = REPO / "results" / "p2b_pilot"
# (koşu klasörü, etiket); kopyalar llm_cache/'tekilerle bayt aynı (HANDOFF 2026-11-13).
RUNS = [("20261113T075333Z-agent", "(b) Gemini, dosya, 25 vaka"),
        ("20261113T083032Z-agent", "(c) qwen3.5-4b, dosya, 25 vaka"),
        ("20261113T102704Z-agent", "(d) Gemini, canlı, 3 vaka")]
RULE_4B = {"run": "20261113T083032Z-agent", "min_valid": 20, "max_mean_min": 20}
# P2c-0: (eski koşu, yeni koşu, etiket). Yeni koşular kod `cdfd320`…`85531e7`, `prompt_sha256` 5e259201….
PAIRS = [("20261113T075333Z-agent", "20261113T125627Z-agent", "Gemini, dosya, 25 vaka"),
         ("20261113T083032Z-agent", "20261113T182857Z-agent", "qwen3.5-4b, dosya, 25 vaka"),
         ("20261113T102704Z-agent", "20261113T211812Z-agent", "Gemini, canlı, 3 vaka")]
# P2c dev koşuları (kart 4. madde); klasörler koşulardan sonra yazılır (5. madde). Anahtar → (klasör, etiket).
# Kopyalar llm_cache/'tekilerle bayt aynı (HANDOFF 2026-11-15).
DEV_RUNS = {"gemini_file": ("20261114T194507Z-agent", "Gemini, dosya, 1. koşu (resmî)"),
            "gemini_file_2": ("20261114T200540Z-agent", "Gemini, dosya, 2. koşu (gürültü tabanı)"),
            "qwen_file": ("20261114T202141Z-agent", "qwen3.5-4b, dosya"),
            "gemini_live": ("20261115T153308Z-agent", "Gemini, canlı"),
            "qwen_live": ("20261115T153310Z-agent", "qwen3.5-4b, canlı")}
DEV_MODELS = {"gemini-3.5-flash-lite": ("gemini_file", "gemini_live"), "qwen3.5-4b": ("qwen_file", "qwen_live")}
# Canlı dev koşusunun teknik kesintileri (HANDOFF / DECISIONS 2026-11-15): puanlanmadı, `llm_cache/`'te kalır
# (repoda değil). (Gemini klasörü, 4B klasörü, iki modelde oynatılan vaka, neden).
DEV_INTERRUPTED = [("20261115T132147Z-agent", "20261115T132149Z-agent", 5,
                    "takas koruması (boş takas < 1 GB) kalan 13 vakayı oynatmadı"),
                   ("20261115T141055Z-agent", "20261115T141057Z-agent", 2,
                    "durduruldu (yerel sunucunun istem önbelleği vaka başına büyüyordu)")]
# P2d test koşuları (kart 4. madde); klasörler koşulardan sonra yazılır (5. madde). Anahtarlar ve etiketler dev'deki gibi.
TEST_RUNS = {"gemini_file": (None, "Gemini, dosya, 1. koşu (resmî)"),
             "gemini_file_2": (None, "Gemini, dosya, 2. koşu (gürültü tabanı)"),
             "qwen_file": (None, "qwen3.5-4b, dosya"),
             "gemini_live": (None, "Gemini, canlı"),
             "qwen_live": (None, "qwen3.5-4b, canlı")}
# Test koşularının teknik kesintileri (kart 4. madde; puanlamadan önce yazılır): (Gemini klasörü, 4B klasörü, iki modelde
# oynatılan vaka, neden).
TEST_INTERRUPTED: list[tuple[str, str, int, str]] = []
REPORTS = {"p2b": {"out": REPO / "results" / "p2b_pilot", "rule_4b": RULE_4B},
           "p2c0": {"out": REPO / "results" / "p2c0_pilot",
                    "rule_4b": {**RULE_4B, "run": "20261113T182857Z-agent"}},
           "p2c_dev": {"out": REPO / "results" / "p2c_dev", "calls": REPO / "results" / "p2c_dev_calls.json",
                       "p1_runs": REPO / "results" / "p1_runs.json"},
           "p2d": {"out": REPO / "results" / "p2d_test", "calls": REPO / "results" / "p2d_test_calls.json",
                   "p1_runs": REPO / "results" / "p1_runs.json"}}
ALPHA = 0.05  # DECISIONS 2026-11-14: iki yönlü p < 0,05


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


def all_services_calls(run_dir: Path) -> dict:
    """Servissiz `metric_series` çağrıları (P2c-0 B): sayı, verilen `step_s` (yoksa "default"), kesilen."""
    ts = [t for t in _jsonl(run_dir / "turns.jsonl")
          if t.get("tool") == "metric_series" and "service=" not in (t.get("call") or "")]
    steps = Counter((m.group(1) if (m := re.search(r"step_s=(\d+)", t["call"])) else "default") for t in ts)
    return {"calls": len(ts), "step_s": dict(sorted(steps.items(), key=lambda kv: (kv[0] == "default", int(kv[0]) if kv[0] != "default" else 0))),
            "truncated": sum(1 for t in ts if t.get("tool_truncated")),
            "errors": sum(1 for t in ts if t.get("tool_error"))}


def _rule_4b(runs: list[dict], spec: dict) -> dict:
    r4 = next(r for r in runs if r["run"] == spec["run"])
    mean_min = r4["duration_s_mean"] / 60
    return {"run": spec["run"], "valid": r4["schema_valid"], "min_valid": spec["min_valid"],
            "mean_min": round(mean_min, 2), "max_mean_min": spec["max_mean_min"],
            "passed": r4["schema_valid"] >= spec["min_valid"] and mean_min <= spec["max_mean_min"]}


def build_p2c0() -> dict:
    pairs = []
    for old, new, label in PAIRS:
        o, n = summarize(EVAL / old), summarize(EVAL / new)
        n["all_services_metric_series"] = all_services_calls(EVAL / new)
        pairs.append({"label": label, "old": o, "new": n})
    new_runs = [p["new"] for p in pairs]
    budget = {r["run"]: {"budget_endings": r["budget_endings"], "n_cases": r["n_cases"],
                         "reopen": r["budget_endings"] > r["n_cases"] / 2} for r in new_runs}
    return {"pairs": pairs, "rule_4b": _rule_4b(new_runs, REPORTS["p2c0"]["rule_4b"]), "budget_rule": budget}


_COLS = ("| Koşu | Klasör | Bitişler | Geçerli son cevap | Araç sayısı (vaka) | İstek | Token giriş / çıkış | "
         "Süre ort / en çok (sn) | En uzun mesaj | Kırpmalı vaka | Bütçe bitişi | Tekrar | Araç hatası | Kesilen sonuç | "
         "HTTP | top-1 (iyimser) | top-3 (iyimser) |")


def _run_row(label: str, r: dict) -> str:
    er = ", ".join(f"{k} {v}" for k, v in r["end_reasons"].items())
    tc = ", ".join(f"{k}: {v}" for k, v in r["tool_calls"].items())
    http = ", ".join(f"{k}: {v}" for k, v in r["http"].items())
    return (f"| {label} | `{r['run']}` | {er} | {r['schema_valid']}/{r['n_cases']} | {tc} | {r['requests']} | "
            f"{r['tokens_input']} / {r['tokens_output']} | {r['duration_s_mean']} / {r['duration_s_max']} | "
            f"{r['max_message_tokens']} | {r['cases_with_drop']} | {r['budget_endings']} | {r['repeated_calls']} | "
            f"{r['tool_errors']} | {r['tool_truncated']} | {http} | {r['info_top1']}/{r['n_cases']} | "
            f"{r['info_top3']}/{r['n_cases']} |")


def render_p2c0(rep: dict) -> str:
    L = ["# P2c-0 pilot tasarım turu", "",
         "Komutla üretilir: `python tools/agent_report.py --report p2c0` (kaynak `eval_responses/`'teki altı pilot "
         "koşusu). Tek tur (DECISIONS 2026-11-13): onaylı iki değişiklik (A zaman varsayılanı ve görev cümlesi, "
         "B servissiz `metric_series`), pilot bir kez yeniden koşuldu; bu koşudan sonra istem, araçlar ve sınırlar donar. "
         "**Pilot tasarım setidir: isabet (top-1 / top-3) iki turda da iyimser okunur ve hiçbir karara girmez.**", "",
         "## Eski ve yeni pilot", "", _COLS, "|" + "---|" * 17]
    for p in rep["pairs"]:
        L.append(_run_row(f"{p['label']}: eski (P2b, `{p['old']['prompt_sha256'][:8]}`)", p["old"]))
        L.append(_run_row(f"{p['label']}: yeni (P2c-0, `{p['new']['prompt_sha256'][:8]}`)", p["new"]))
    L += ["", "## Servissiz `metric_series` (yeni koşular)", "",
          "| Koşu | Çağrı | Verilen step_s (çağrı) | Kesilen | Araç hatası |", "|---|---|---|---|---|"]
    for p in rep["pairs"]:
        a = p["new"]["all_services_metric_series"]
        st = ", ".join(f"{k}: {v}" for k, v in a["step_s"].items()) or "-"
        L.append(f"| {p['label']} | {a['calls']} | {st} | {a['truncated']} | {a['errors']} |")
    k = rep["rule_4b"]
    L += ["", "## Kurallar (yeni koşulara, aynen)", "",
          f"- **4B kuralı** (DECISIONS 2026-11-13, koşudan önce; `{k['run']}`): geçerli son cevap {k['valid']} / 25 "
          f"(≥ {k['min_valid']}) ve ortalama vaka süresi {k['mean_min']} dk (≤ {k['max_mean_min']}) → "
          f"**{'geçti: 4B P2’de kalır' if k['passed'] else 'kaldı: 4B P2’ye girmez'}**.",
          "- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09: vakaların yarısından çoğu bütçe yüzünden biterse): " +
          "; ".join(f"`{run}` {v['budget_endings']}/{v['n_cases']}" for run, v in rep["budget_rule"].items()) +
          f" → **{'yeniden açılır' if any(v['reopen'] for v in rep['budget_rule'].values()) else 'tetiklenmedi'}**.",
          "", "## Vakalar (yeni koşular)", ""]
    for p in rep["pairs"]:
        L += _case_table(p["label"], p["new"])
    return "\n".join(L)


def _case_table(label: str, r: dict) -> list[str]:
    L = [f"### {label}", "", "| Vaka | Bitiş | Araç | İstek | Süre (sn) | En uzun mesaj | Kırpmalı tur | Tekrar | "
         "Araç hatası | top-1 / top-3 (bilgi) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for c in r["cases"]:
        hit = f"{'evet' if c['top1'] else 'hayır'} / {'evet' if c['top3'] else 'hayır'}"
        L.append(f"| `{c['incident_id']}` | {c['end_reason']} | {c['n_tool_calls']} | {c['n_requests']} | "
                 f"{c['duration_s']} | {c['max_message_tokens']} | {c['turns_with_drop']} | {c['repeated_calls']} | "
                 f"{c['tool_errors']} | {hit} |")
    L.append("")
    return L


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


# --- P2c dev ---------------------------------------------------------------------------------------------------

def sign_test(b: int, c: int) -> float:
    """Eşleştirilmiş kesin işaret testi, iki yönlü (DECISIONS 2026-11-14): p = 2 · P[Bin(b + c; 0,5) ≤ min(b, c)],
    en çok 1; b + c = 0 ise 1."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def paired(left: dict[str, bool], right: dict[str, bool], left_name: str, right_name: str) -> dict:
    """Aynı vakalarda iki taraf (vaka → bildi mi): yalnız soldakinin ve yalnız sağdakinin bildiği vaka sayıları,
    p ve okuma ("fark" yönüyle ya da "ayırt edilemedi")."""
    if set(left) != set(right):
        raise ValueError(f"case sets differ: {sorted(set(left) ^ set(right))}")
    b = sorted(k for k in left if left[k] and not right[k])
    c = sorted(k for k in left if right[k] and not left[k])
    p = sign_test(len(b), len(c))
    if p < ALPHA:
        reading = f"fark: {left_name} lehine" if len(b) > len(c) else f"fark: {right_name} lehine"
    else:
        reading = "ayırt edilemedi"
    return {"n": len(left), "left": sum(left.values()), "right": sum(right.values()), "only_left": len(b),
            "only_right": len(c), "only_left_cases": b, "only_right_cases": c, "p": round(p, 4), "reading": reading}


def retry_wait_s(provider: str, n_attempts: int) -> int:
    """Bir isteğin yeniden deneme beklemesi (sn), deneme sayısından (planlama kontrolü şart 2: sağlayıcıya göre)."""
    waits = GEMINI_RETRY_WAITS if provider == "gemini" else (RETRY_WAIT[provider],)
    return sum(waits[:max(0, n_attempts - 1)])


def retries(run_dir: Path) -> dict:
    """Yeniden denemeler: istek başına deneme sayısından; toplam bekleme ayrı sütun (`duration_s` değişmez)."""
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    provider = MODELS[run["settings"]["model"]].provider
    turns = _jsonl(run_dir / "turns.jsonl")
    n = [len(t.get("attempts") or []) for t in turns]
    rows = _jsonl(run_dir / "responses.jsonl")
    failed = {t["incident_id"] for t in turns
              if t.get("error") is not None and (t.get("attempts") or [{}])[-1].get("status") in TRANSPORT_ERRORS}
    return {"requests_retried": sum(1 for k in n if k > 1), "retries": sum(max(0, k - 1) for k in n),
            "retry_wait_s": sum(retry_wait_s(provider, k) for k in n),
            "transport_no_answer": sum(1 for r in rows if r["end_reason"] == "no_answer" and r["incident_id"] in failed)}


def _known(run_dir: Path, key: str, cases: set[str] | None = None, set_: str = "dev") -> dict[str, bool]:
    """`set_` vakaları → `key` (top1 / top3) bildi mi; `scores.json`'dan (geçerli cevabı olmayan bilinmemiş)."""
    sc = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
    out = {c["incident_id"]: bool(c[key]) for c in sc["cases"] if c["set"] == set_}
    return {k: v for k, v in out.items() if cases is None or k in cases}


def _dev_table(run_dir: Path, set_: str = "dev") -> dict:
    t = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))["table"][set_]
    return {k: t.get(k) for k in ("n", "top1", "top3", "schema_invalid", "no_answer", "evidence_valid", "brier",
                                  "duration_s_total", "tokens_input", "tokens_output")}


def p1_dev_rows(p1_runs: Path, model: str, set_: str = "dev") -> dict[str, Path]:
    """P1'in `set_` satırları (kural, BARO, daraltma referansı, modelin ham / özet / daraltma): ad → koşu klasörü."""
    spec = json.loads(p1_runs.read_text(encoding="utf-8"))
    base = p1_runs.resolve().parents[1]  # yollar repo köküne göre (results/p1_runs.json)
    out = {}
    for r in spec["rows"]:
        name = r["method"] if r["method"] != "llm" else r["level"] if r["model"] == model else None
        if name and not r["info"]:
            out[name] = base / r["runs"][set_]
    return out


def build_p2c_dev(runs: dict = DEV_RUNS, eval_dir: Path = EVAL, calls_path: Path | None = None,
                  p1_runs: Path | None = None) -> dict:
    cfg = REPORTS["p2c_dev"]
    return _build_agent_set(runs, eval_dir, calls_path or cfg["calls"], p1_runs or cfg["p1_runs"], "dev",
                            DEV_INTERRUPTED, "DEV_RUNS")


def _build_agent_set(runs: dict, eval_dir: Path, calls_path: Path, p1_runs: Path, set_: str, interrupted: list,
                     runs_name: str) -> dict:
    """Dev ve test raporunun ortak hesabı (set adına göre); test için vaka kimliği listeleri `build_p2d`'de düşer."""
    missing = [k for k, (d, _) in runs.items() if d is None]
    if missing:
        raise SystemExit(f"error: {runs_name} not filled yet: {missing}")
    dirs = {k: eval_dir / d for k, (d, _) in runs.items()}
    summ = {k: {"label": runs[k][1], **summarize(dirs[k]), "retry": retries(dirs[k])} for k in runs}
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    by_live = {r["live"]["dir"]: r for r in calls["runs"]}
    rep = {"runs": summ, "budget_rule": {k: {"budget_endings": s["budget_endings"], "n_cases": s["n_cases"],
                                             "reopen": s["budget_endings"] > s["n_cases"] / 2}
                                         for k, s in summ.items()},
           "calls_file": {"sha256": hashlib.sha256(calls_path.read_bytes()).hexdigest()},
           "interrupted": [{"gemini": g, "qwen": q, "cases": n, "reason": why} for g, q, n, why in interrupted],
           "models": {}}
    known = lambda d, key, cases=None: _known(d, key, cases, set_)  # noqa: E731
    for model, (fkey, lkey) in DEV_MODELS.items():
        live_cases = set(known(dirs[lkey], "top3"))
        file_top3 = known(dirs[fkey], "top3")
        c = by_live.get(runs[lkey][0])
        if c is None:
            raise SystemExit(f"error: {calls_path.name} has no entry for {runs[lkey][0]}")
        m = {"call_level": {"totals": c["totals"],
                            "unexplained": [{"incident_id": cid, **d} for cid, v in sorted(c["cases"].items())
                                            for d in v["diffs"] if d["class"] == "unexplained"]},
             "file_vs_live_top3": {**paired(known(dirs[fkey], "top3", live_cases), known(dirs[lkey], "top3"),
                                            "dosya", "canlı"),
                                   "not_replayed": sorted(set(file_top3) - live_cases)}}
        if c.get("divergence") is not None:
            m["call_level"]["model_diverged"] = sorted(k for k, v in c["divergence"].items() if v["model_diverged"])
        p1 = p1_dev_rows(p1_runs, model, set_)
        m["agent_vs_p1"] = {
            "raw_top3": paired(known(dirs[fkey], "top3"), known(p1["raw"], "top3"), "ajan", "ham"),
            "narrowed_top1": paired(known(dirs[fkey], "top1"), known(p1["narrowed"], "top1"), "ajan", "daraltma")}
        m["p1_rows"] = {name: {"run": d.name, **_dev_table(d, set_)} for name, d in p1.items()}
        m["agent_rows"] = {k: {"run": dirs[k].name, **_dev_table(dirs[k], set_)} for k in (fkey, lkey)}
        rep["models"][model] = m
    g1, g2 = known(dirs["gemini_file"], "top3"), known(dirs["gemini_file_2"], "top3")
    gl = known(dirs["gemini_live"], "top3")
    rep["noise_floor"] = {"file_vs_file_differ": sum(g1[k] != g2[k] for k in g1),
                          "file_vs_live_differ": sum(g1[k] != gl[k] for k in gl), "n_file": len(g1), "n_live": len(gl)}
    return rep


def _cell(p: dict, left: str, right: str) -> str:
    return (f"{left} {p['left']} / {p['n']}, {right} {p['right']} / {p['n']}; yalnız {left} {p['only_left']}, yalnız "
            f"{right} {p['only_right']}; p = {p['p']} → **{p['reading']}**")


def render_p2c_dev(rep: dict) -> str:
    L = ["# P2c dev koşuları", "",
         "Komutla üretilir: `python tools/agent_report.py --report p2c_dev` (kaynak `eval_responses/`'teki dev "
         "koşuları, `results/p2c_dev_calls.json` sha256 `" + rep["calls_file"]["sha256"] + "`, `results/p1_runs.json`'"
         "daki P1 dev koşuları). Tasarım donmuş (DECISIONS 2026-11-14); okuma kuralları koşudan önce yazıldı. "
         "Resmî sonuç P2d'deki test koşusudur; dev okuması tasarımı değiştirmez.", "",
         "## Koşular", "", _COLS.replace("(iyimser)", "(dev)") + " Yeniden deneme (istek / bekleme sn) | "
         "Taşıma hatasıyla cevapsız |", "|" + "---|" * 19]
    for s in rep["runs"].values():
        r = s["retry"]
        L.append(_run_row(s["label"], s) + f" {r['requests_retried']} / {r['retry_wait_s']} | "
                                           f"{r['transport_no_answer']} |")
    L += ["", "Süre sütunu kayıttaki `duration_s` (yeniden deneme beklemesi içinde; istek aralığı beklemesi hariç); "
              "yeniden deneme beklemesi ayrı sütunda.", "",
          "- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09): " +
          "; ".join(f"{rep['runs'][k]['label']} {v['budget_endings']}/{v['n_cases']}"
                    for k, v in rep["budget_rule"].items()) +
          f" → **{'yeniden açılır' if any(v['reopen'] for v in rep['budget_rule'].values()) else 'tetiklenmedi'}**.",
          "- **Kod:** " + "; ".join(f"{s['label']} `{s['repo_commit'][:7]}`" for s in rep["runs"].values()) +
          ". Dosya koşuları ile canlı koşu arasındaki kod farkı yalnız canlı koşucu (`tools/agent_live.py`: yerel "
          "sunucu her oynatmadan önce yeniden açılır, başta takas denetimi); `src/` ve istem aynı.",
          f"- **Teknik kesinti:** {len(rep.get('interrupted', []))} (puanlanmadı; canlı koşu baştan koşuldu): " +
          "; ".join(f"`{i['gemini']}` / `{i['qwen']}`, {i['cases']} vaka, {i['reason']}"
                    for i in rep.get("interrupted", [])) + ".",
          "- **Okuma notu (sonuçtan önce yazıldı, DECISIONS 2026-11-15):** 4B dosya koşusunda yerel sunucunun istem "
          "önbelleği önceki vakalardan doluydu, canlıda her vaka boş önbellekle başladı; \"çıktı aynı, model "
          "ayrıştı\" çıkarsa sayılır ve bu fark olası neden olarak sınırlamalara yazılır.",
          "", "## Dosya ↔ canlı (DECISIONS 2026-11-14, üç katman)", ""]
    for model, m in rep["models"].items():
        t = m["call_level"]["totals"]
        L += [f"### {model}", "",
              f"- **(1) Çağrı düzeyi:** {t['calls']} canlı çağrı ({t['cases']} vaka): aynı {t.get('same', 0)}, "
              f"bilinen tür (`zero_duration`) {t.get('zero_duration', 0)}, **açıklanamayan "
              f"{t.get('unexplained', 0)}** (beklenen 0)."]
        for u in m["call_level"]["unexplained"]:
            L.append(f"  - `{u['incident_id']}` tur {u['turn']}: `{u['call']}` (tanı: {u['diagnosis'] or 'yok'})")
        if "model_diverged" in m["call_level"]:
            d = t.get("divergence", {})
            L.append(f"- **4B denetimi:** {d.get('cases_paired')} vakada çıktı aynıyken model ayrıştı: "
                     f"{d.get('model_diverged')} ({', '.join(f'`{x}`' for x in m['call_level']['model_diverged']) or '-'}); "
                     f"bir araç çıktısı farklı: {d.get('output_differs')}; baştan sona aynı: {d.get('identical')}.")
        f = m["file_vs_live_top3"]
        L += [f"- **(2) Sonuç düzeyi, top-3 (eşleştirilmiş kesin işaret testi):** {_cell(f, 'dosya', 'canlı')}."
              + (f" Oynatılamadı (çiftten düştü): {', '.join(f'`{x}`' for x in f['not_replayed'])}."
                 if f["not_replayed"] else ""), ""]
    nf = rep["noise_floor"]
    L += [f"- **(3) Gürültü tabanı (Gemini, betimsel):** top-3 sonucu ayrışan vaka: dosya 1 ↔ dosya 2 "
          f"{nf['file_vs_file_differ']} / {nf['n_file']}, dosya 1 ↔ canlı {nf['file_vs_live_differ']} / {nf['n_live']}.",
          "", "## Ajan ↔ P1 (DECISIONS 2026-11-14, model başına iki hücre)", "",
          "Ajan tarafı dosya modunun ilk koşusu; P1 tarafı aynı modelin dev koşuları (P1d a1, gerçek ad). Geçerli "
          "cevabı olmayan vaka bilinmemiş. Dört hücrede çoklu karşılaştırma düzeltmesi yok.", ""]
    for model, m in rep["models"].items():
        a = m["agent_vs_p1"]
        L += [f"- **{model}, (a) ajan ↔ ham, top-3:** {_cell(a['raw_top3'], 'ajan', 'ham')}.",
              f"- **{model}, (b) ajan ↔ daraltma, top-1:** {_cell(a['narrowed_top1'], 'ajan', 'daraltma')}."]
    L += ["", "## Öteki ölçüler (yalnız sayı; dev, 18 vaka)", "",
          "| Model | Satır | Koşu | top-1 | top-3 | Şema dışı | Cevapsız | Kanıt geçerli | Brier | Süre toplam (sn) | "
          "Token giriş / çıkış |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for model, m in rep["models"].items():
        for name, r in [*m["agent_rows"].items(), *m["p1_rows"].items()]:
            label = rep["runs"][name]["label"] if name in rep["runs"] else name
            L.append(f"| {model} | {label} | `{r['run']}` | {r['top1']} | {r['top3']} | {r['schema_invalid']} | "
                     f"{r['no_answer']} | {r['evidence_valid']} | {r['brier']} | {r['duration_s_total']} | "
                     f"{r['tokens_input']} / {r['tokens_output']} |")
    L += ["", "## Vakalar", ""]
    for s in rep["runs"].values():
        L += _case_table(s["label"], s)
    return "\n".join(L)


# --- P2d test ----------------------------------------------------------------------------------------------------

def _table_dev_test(dev_dir: Path, test_dir: Path) -> dict:
    return {"dev": {"run": dev_dir.name, **_dev_table(dev_dir, "dev")},
            "test": {"run": test_dir.name, **_dev_table(test_dir, "test")}}


def build_p2d(runs: dict | None = None, eval_dir: Path = EVAL, calls_path: Path | None = None,
              p1_runs: Path | None = None, dev_runs: dict = DEV_RUNS, dev_eval_dir: Path | None = None) -> dict:
    """Test raporu: dev raporunun hesabı test setinde + dev–test okuması (iki dosya satırı) + dev ve test yan yana
    sonuç tablosu. Vaka kimliği taşıyan bütün alanlar düşer ya da sayıya iner (planlama kontrolü 2026-11-17 şart 3)."""
    from aiops_rca.results import dev_test_reading

    runs = TEST_RUNS if runs is None else runs
    cfg = REPORTS["p2d"]
    calls_path, p1_runs = calls_path or cfg["calls"], p1_runs or cfg["p1_runs"]
    dev_eval_dir = dev_eval_dir or eval_dir
    rep = _build_agent_set(runs, eval_dir, calls_path, p1_runs, "test", TEST_INTERRUPTED, "TEST_RUNS")
    for s in rep["runs"].values():
        s.pop("cases")
    for model, (fkey, _) in DEV_MODELS.items():
        m = rep["models"][model]
        m["call_level"].pop("unexplained")
        m["call_level"].pop("model_diverged", None)
        f = m["file_vs_live_top3"]
        f["not_replayed"] = len(f["not_replayed"])
        for cell in (f, *m["agent_vs_p1"].values()):
            cell.pop("only_left_cases")
            cell.pop("only_right_cases")
        dev3 = _known(dev_eval_dir / dev_runs[fkey][0], "top3", set_="dev")
        test3 = _known(eval_dir / runs[fkey][0], "top3", set_="test")
        m["dev_test_reading"] = dev_test_reading(sum(dev3.values()), len(dev3), sum(test3.values()), len(test3))
        keys = [k for k in runs if rep["runs"][k]["model"] == model]
        m["agent_rows"] = {k: _table_dev_test(dev_eval_dir / dev_runs[k][0], eval_dir / runs[k][0]) for k in keys}
        p1_dev, p1_test = p1_dev_rows(p1_runs, model, "dev"), p1_dev_rows(p1_runs, model, "test")
        m["p1_rows"] = {name: _table_dev_test(p1_dev[name], p1_test[name]) for name in p1_dev}
    spec = json.loads(p1_runs.read_text(encoding="utf-8"))
    base = p1_runs.resolve().parents[1]
    rep["p1_info"] = {f"{r['model']} {r['level']}": _table_dev_test(base / r["runs"]["dev"], base / r["runs"]["test"])
                      for r in spec["rows"] if r["method"] == "llm" and r["model"] not in DEV_MODELS}
    return rep


def _reach(dev: int, n_dev: int, n_test: int) -> str:
    """Dev top-3'üne göre "fark" okuması veren test top-3 değerleri (önceden hesaplanabilir güç)."""
    from aiops_rca.results import dev_test_reading

    ts = [t for t in range(n_test + 1) if dev_test_reading(dev, n_dev, t, n_test)["reading"] != "none"]
    lo = [t for t in ts if t * n_dev < dev * n_test]
    hi = [t for t in ts if t * n_dev > dev * n_test]
    parts = ([f"≤ {max(lo)}"] if lo else []) + ([f"≥ {min(hi)}"] if hi else [])
    return " ya da ".join(parts) or "yok"


def render_p2d(rep: dict) -> str:
    from aiops_rca.results import READING_TEXT as DT_TEXT

    L = ["# P2d test koşuları", "",
         "Komutla üretilir: `python tools/agent_report.py --report p2d` (kaynak `eval_responses/`'teki test ve dev "
         "koşuları, `results/p2d_test_calls.json` sha256 `" + rep["calls_file"]["sha256"] + "`, `results/p1_runs.json`'"
         "daki P1 koşuları). Tasarım donmuş (DECISIONS 2026-11-14); okuma kuralları koşudan önce yazıldı (DECISIONS "
         "2026-11-14, 2026-11-16). **Resmî sonuç budur.** Testte yalnız toplamlar: vaka başına sonuç yok.", "",
         "## Koşular", "", _COLS.replace("(iyimser)", "(test)") + " Yeniden deneme (istek / bekleme sn) | "
         "Taşıma hatasıyla cevapsız |", "|" + "---|" * 19]
    for s in rep["runs"].values():
        r = s["retry"]
        L.append(_run_row(s["label"], s) + f" {r['requests_retried']} / {r['retry_wait_s']} | "
                                           f"{r['transport_no_answer']} |")
    L += ["", "Süre sütunu kayıttaki `duration_s` (yeniden deneme beklemesi içinde; istek aralığı beklemesi hariç); "
              "yeniden deneme beklemesi ayrı sütunda.", "",
          "- **Bütçe yeniden açma kuralı** (DECISIONS 2026-11-09; testte yalnız sayılır, tasarım donmuş): " +
          "; ".join(f"{rep['runs'][k]['label']} {v['budget_endings']}/{v['n_cases']}"
                    for k, v in rep["budget_rule"].items()) +
          f" → {'tetiklenirdi' if any(v['reopen'] for v in rep['budget_rule'].values()) else 'tetiklenmedi'}.",
          "- **Kod:** " + "; ".join(f"{s['label']} `{s['repo_commit'][:7]}`" for s in rep["runs"].values()) +
          "; istem " + ", ".join(sorted({f"`{s['prompt_sha256'][:8]}`" for s in rep["runs"].values()})) + ".",
          f"- **Teknik kesinti:** {len(rep['interrupted'])}" +
          (" (puanlanmadı; koşu baştan koşuldu): " + "; ".join(
              f"`{i['gemini']}` / `{i['qwen']}`, {i['cases']} vaka, {i['reason']}" for i in rep["interrupted"])
           if rep["interrupted"] else "") + ".",
          "- **Okuma notu (sonuçtan önce yazıldı, DECISIONS 2026-11-15):** 4B dosya koşusunda yerel sunucunun istem "
          "önbelleği önceki vakalardan doluydu, canlıda her vaka boş önbellekle başladı; \"çıktı aynı, model "
          "ayrıştı\" çıkarsa sayılır ve bu fark olası neden olarak sınırlamalara yazılır.",
          "", "## Dosya ↔ canlı (DECISIONS 2026-11-14, üç katman)", ""]
    for model, m in rep["models"].items():
        t = m["call_level"]["totals"]
        L += [f"### {model}", "",
              f"- **(1) Çağrı düzeyi:** {t['calls']} canlı çağrı ({t['cases']} vaka): aynı {t.get('same', 0)}, "
              f"bilinen tür (`zero_duration`) {t.get('zero_duration', 0)}, **açıklanamayan "
              f"{t.get('unexplained', 0)}** (beklenen 0; ayrıntı yalnız hata analizi maddesinde)."]
        if "divergence" in t:
            d = t["divergence"]
            L.append(f"- **4B denetimi:** {d['cases_paired']} vakada çıktı aynıyken model ayrıştı: "
                     f"{d['model_diverged']}; bir araç çıktısı farklı: {d['output_differs']}; baştan sona aynı: "
                     f"{d['identical']}.")
        f = m["file_vs_live_top3"]
        L += [f"- **(2) Sonuç düzeyi, top-3 (eşleştirilmiş kesin işaret testi):** {_cell(f, 'dosya', 'canlı')}."
              + (f" Oynatılamadı (çiftten düştü): {f['not_replayed']} vaka." if f["not_replayed"] else ""), ""]
    nf = rep["noise_floor"]
    L += [f"- **(3) Gürültü tabanı (Gemini, betimsel):** top-3 sonucu ayrışan vaka: dosya 1 ↔ dosya 2 "
          f"{nf['file_vs_file_differ']} / {nf['n_file']}, dosya 1 ↔ canlı {nf['file_vs_live_differ']} / {nf['n_live']}.",
          "", "## Ajan ↔ P1 (DECISIONS 2026-11-14, model başına iki hücre)", "",
          "Ajan tarafı dosya modunun ilk koşusu; P1 tarafı aynı modelin test koşuları (P1e). Geçerli cevabı olmayan "
          "vaka bilinmemiş. Dört hücrede çoklu karşılaştırma düzeltmesi yok.", ""]
    for model, m in rep["models"].items():
        a = m["agent_vs_p1"]
        L += [f"- **{model}, (a) ajan ↔ ham, top-3:** {_cell(a['raw_top3'], 'ajan', 'ham')}.",
              f"- **{model}, (b) ajan ↔ daraltma, top-1:** {_cell(a['narrowed_top1'], 'ajan', 'daraltma')}."]
    L += ["", "## Dev–test (DECISIONS 2026-11-16: yalnız iki dosya satırı, top-3, iki yönlü Fisher)", ""]
    for model, m in rep["models"].items():
        d = m["dev_test_reading"]
        L.append(f"- **{model}, ajan dosya (1. koşu):** dev {d['dev_top3']} / {d['n_dev']}, test {d['test_top3']} / "
                 f"{d['n_test']}; p = {d['p']} → **{DT_TEXT[d['reading']]}** (\"fark\" için test "
                 f"{_reach(d['dev_top3'], d['n_dev'], d['n_test'])}).")
    L += ["", "Öteki satırlarda dev ve test yalnız sayı (aşağıdaki tablo).", "",
          "## Sonuç tablosu (dev ve test yan yana; öteki ölçüler testte, yalnız sayı)", "",
          "| Model | Satır | Koşu (test) | dev top-1 | dev top-3 | test top-1 | test top-3 | Şema dışı | Cevapsız | "
          "Kanıt geçerli | Brier | Süre toplam (sn) | Token giriş / çıkış |", "|" + "---|" * 13]

    def row(model, label, r):
        d, t = r["dev"], r["test"]
        return (f"| {model} | {label} | `{t['run']}` | {d['top1']} / {d['n']} | {d['top3']} / {d['n']} | "
                f"{t['top1']} / {t['n']} | {t['top3']} / {t['n']} | {t['schema_invalid']} | {t['no_answer']} | "
                f"{t['evidence_valid']} | {t['brier']} | {t['duration_s_total']} | {t['tokens_input']} / "
                f"{t['tokens_output']} |")

    for model, m in rep["models"].items():
        for name, r in m["agent_rows"].items():
            L.append(row(model, "ajan, " + rep["runs"][name]["label"], r))
        for name, r in m["p1_rows"].items():
            L.append(row(model, f"P1 {name}", r))
    for cell, r in rep["p1_info"].items():
        model, level = cell.rsplit(" ", 1)
        L.append(row(model, f"P1 {level} (bilgi)", r))
    L.append("")
    return "\n".join(L)


def main(argv: list[str]) -> int:
    name = argv[argv.index("--report") + 1] if "--report" in argv else "p2b"
    if name not in REPORTS:
        print(f"unknown report {name!r}; one of {sorted(REPORTS)}")
        return 2
    OUT = REPORTS[name]["out"]
    builders = {"p2b": (build, render), "p2c0": (build_p2c0, render_p2c0), "p2c_dev": (build_p2c_dev, render_p2c_dev),
                "p2d": (build_p2d, render_p2d)}
    rep = builders[name][0]()
    text_json = json.dumps(rep, ensure_ascii=False, indent=1) + "\n"
    text_md = builders[name][1](rep)
    if "--check" in argv:
        same = (OUT.with_suffix(".json").read_text(encoding="utf-8") == text_json
                and OUT.with_suffix(".md").read_text(encoding="utf-8") == text_md)
        print("same" if same else "different")
        return 0 if same else 1
    OUT.with_suffix(".json").write_text(text_json, encoding="utf-8")
    OUT.with_suffix(".md").write_text(text_md, encoding="utf-8")
    print(f"-> {OUT.with_suffix('.md')}" + (f"; 4B {rep['rule_4b']}" if "rule_4b" in rep else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
