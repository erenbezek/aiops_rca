"""P2a 4. madde: aynı sorgu çağrılarının dosya (`FileStore`) ↔ canlı (`LiveStore`) karşılaştırması, LLM'siz.

Çağrı listesi ve eşitlik tanımı ölçmeden önce yazıldı ve Eren onaylı (HANDOFF 2026-11-11). Bu dosyanın bu bölümü
(çağrı listesi, çağrı koşturma, eşitlik, ham kayıt karşılaştırması) karşılaştırma koşusundan önce commit'lendi.

Aralıklar (vaka başına): A = [alarm − 10 dk, alarm), B = [alarm, alarm + 10 dk), C = bütün pencere (`window.json`).
Servisler dosya tarafının `list_services`'inden. Bütün sonuçlar sınırsız (`limit=None`).
- `list_services`: 1 çağrı.
- `metric_series`: her servis × `query.SERIES` (9) × A/B/C, `step_s` 60.
- `search_spans` (A/B/C): süzgeçsiz; `status="error"`; her servis; ayrıca C'de `min_duration_ms=100`.
- `get_trace`: C'deki hata span'lerinin izleri (`trace_id` sırasıyla en çok 200) + C'de başlayan span'lerin bütün
  izlerinden sha256(`trace_id`) sırasıyla ilk 50 (ikisinde birden olan bir kez).
- `search_logs` (A/B/C): süzgeçsiz; `min_severity` 9, 13, 17; her servis; `text` "error" ve "fail".
- `service_dependencies`: A/B/C.
- Ham kayıt (C): span'ler, loglar ve `query.CONTAINER_SERIES`'in dört metriği (C − 60 sn'den), çoklu küme.

Eşitlik: bir çağrının çıktısı iki tarafta birebir aynı (JSON'a çevrilmiş hâliyle `==`: aynı alanlar, aynı sıra,
sayılar tam eşit); tolerans yok. Çağrı hata verirse çıktı `{"error": "<tür>: <mesaj>"}`; iki tarafta aynı hata eşit
sayılır. Fark türü (uygulama hatası / depolama ya da arama sınırı / kayıp / hassasiyet / ad eşleme / yığının kendi
telemetrisi) elle, raporda; ham kayıt karşılaştırması ipucu verir (yalnız dosyada, yalnız canlıda, aynı kimlikte
farklı alan).
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from dataclasses import astuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiops_rca import query  # noqa: E402
from aiops_rca.cases import Case  # noqa: E402
from aiops_rca.signals import WINDOW_NS  # noqa: E402

STEP_S = 60
MIN_DURATION_MS = 100
SEVERITIES = (9, 13, 17)
TEXTS = ("error", "fail")
ERROR_TRACES_MAX = 200
SAMPLE_TRACES = 50
RANGE_NAMES = ("A", "B", "C")

FUNCS = {"list_services": query.list_services, "metric_series": query.metric_series,
         "search_spans": query.search_spans, "get_trace": query.get_trace, "search_logs": query.search_logs,
         "service_dependencies": query.service_dependencies}


def ranges(case: Case, store) -> dict[str, tuple[int, int]]:
    return {"A": (case.alarm_ns - WINDOW_NS, case.alarm_ns), "B": (case.alarm_ns, case.alarm_ns + WINDOW_NS),
            "C": store.window()}


def call_list(case: Case, fs) -> list[dict]:
    """Vakanın çağrı listesi: `[{"id", "fn", "args"}]`; dosya okuyucusundan belirlenimli türetilir."""
    rs = ranges(case, fs)
    services = [s["service"] for s in query.list_services(fs)["services"]]
    calls = [{"fn": "list_services", "args": {}}]
    for svc in services:
        for metric in query.SERIES:
            for r in RANGE_NAMES:
                calls.append({"fn": "metric_series", "args": {"service": svc, "metric": metric, "start": rs[r][0],
                                                              "end": rs[r][1], "step_s": STEP_S}})
    for r in RANGE_NAMES:
        lo, hi = rs[r]
        base = {"start": lo, "end": hi, "limit": None}
        calls.append({"fn": "search_spans", "args": dict(base)})
        calls.append({"fn": "search_spans", "args": {**base, "status": "error"}})
        for svc in services:
            calls.append({"fn": "search_spans", "args": {**base, "service": svc}})
        if r == "C":
            calls.append({"fn": "search_spans", "args": {**base, "min_duration_ms": MIN_DURATION_MS}})
    lo, hi = rs["C"]
    error_traces = sorted({s["trace_id"] for s in
                           query.search_spans(fs, lo, hi, status="error", limit=None)["spans"]})[:ERROR_TRACES_MAX]
    all_traces = sorted({s.trace_id for s in fs.spans(lo, hi) if lo <= s.start_ns < hi},
                        key=lambda t: hashlib.sha256(t.encode()).hexdigest())[:SAMPLE_TRACES]
    for tid in error_traces + [t for t in all_traces if t not in set(error_traces)]:
        calls.append({"fn": "get_trace", "args": {"trace_id": tid, "limit": None}})
    for r in RANGE_NAMES:
        lo, hi = rs[r]
        base = {"start": lo, "end": hi, "limit": None}
        calls.append({"fn": "search_logs", "args": dict(base)})
        for sev in SEVERITIES:
            calls.append({"fn": "search_logs", "args": {**base, "min_severity": sev}})
        for svc in services:
            calls.append({"fn": "search_logs", "args": {**base, "service": svc}})
        for text in TEXTS:
            calls.append({"fn": "search_logs", "args": {**base, "text": text}})
    for r in RANGE_NAMES:
        calls.append({"fn": "service_dependencies", "args": {"start": rs[r][0], "end": rs[r][1]}})
    for i, c in enumerate(calls):
        c["id"] = i
    return calls


def run_call(store, call: dict):
    """Çağrının çıktısı, JSON'a çevrilmiş hâliyle (demetler liste olur); hata verirse `{"error": ...}`."""
    try:
        out = FUNCS[call["fn"]](store, **call["args"])
    except Exception as e:  # noqa: BLE001 — iki tarafın hatası da çıktıdır
        out = {"error": f"{type(e).__name__}: {e}"}
    return json.loads(json.dumps(out))


def first_diff(a, b, path: str = "") -> str | None:
    """İki JSON değerinin ilk farkı (yol ve iki değer), yoksa None."""
    if type(a) is not type(b):
        return f"{path or '.'}: {_short(a)} != {_short(b)}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: {'missing' if k not in a else _short(a[k])} != " \
                       f"{'missing' if k not in b else _short(b[k])}"
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return f"{path}: length {len(a)} != {len(b)}" if len(a) != len(b) else None
    return None if a == b else f"{path or '.'}: {_short(a)} != {_short(b)}"


def diff_paths(a, b, path: str = "", out: Counter | None = None) -> Counter:
    """Bütün farkların sayımı; yol liste indeksleri `[]` ile genelleştirilmiş (ör. `.spans[].duration_ms`)."""
    out = Counter() if out is None else out
    if type(a) is not type(b):
        out[path or "."] += 1
    elif isinstance(a, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b:
                out[f"{path}.{k} (missing)"] += 1
            else:
                diff_paths(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list):
        for x, y in zip(a, b):
            diff_paths(x, y, f"{path}[]", out)
        if len(a) != len(b):
            out[f"{path} (length)"] += 1
    elif a != b:
        out[path or "."] += 1
    return out


def _short(v) -> str:
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 120 else s[:117] + "..."


def digest(v) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _multiset_diff(file_items: list, live_items: list, key, fields: tuple[str, ...], examples: int = 5) -> dict:
    """Çoklu küme farkı; aynı kimlikte (key) farklı kayıtlarda hangi alanın farklı olduğu ve sayısal alanlarda
    (canlı − dosya) farkın dağılımı (`changed_fields`)."""
    fc, lc = Counter(file_items), Counter(live_items)
    only_file, only_live = fc - lc, lc - fc
    fk, lk = {}, {}
    for x in only_file:
        fk.setdefault(key(x), x)
    for x in only_live:
        lk.setdefault(key(x), x)
    changed = sorted(set(fk) & set(lk), key=repr)
    fields_c = Counter()
    for k in changed:
        a, b = fk[k], lk[k]
        diff = []
        for name, x, y in zip(fields, a, b):
            if x != y:
                d = (y - x) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else "~"
                diff.append(f"{name} {d:+}" if d != "~" else f"{name} ~")
        fields_c[", ".join(diff)] += 1
    return {"file": len(file_items), "live": len(live_items), "equal": not only_file and not only_live,
            "only_file": sum(only_file.values()), "only_live": sum(only_live.values()), "changed_ids": len(changed),
            "changed_fields": dict(fields_c.most_common()),
            "examples_only_file": [repr(x) for x in list(only_file)[:examples]],
            "examples_only_live": [repr(x) for x in list(only_live)[:examples]]}


def raw_compare(fs, ls, lo: int, hi: int) -> dict:
    """Ham kayıt düzeyi (C): span'ler (başlangıcı aralıkta), loglar, dört konteyner metriği (lo − 60 sn'den)."""
    out = {}
    fsp = [astuple(s) for s in fs.spans(lo, hi) if lo <= s.start_ns < hi]
    lsp = [astuple(s) for s in ls.spans(lo, hi) if lo <= s.start_ns < hi]
    out["spans"] = _multiset_diff(fsp, lsp, key=lambda t: (t[0], t[1]), fields=tuple(query.Span.__slots__))
    flg = [astuple(r) for r in fs.logs(lo, hi) if lo <= r.time_ns < hi]
    llg = [astuple(r) for r in ls.logs(lo, hi) if lo <= r.time_ns < hi]
    out["logs"] = _multiset_diff(flg, llg, key=lambda t: (t[0], t[1], t[4]), fields=tuple(query.LogRecord.__slots__))
    for name in sorted({n for n, _, _ in query.CONTAINER_SERIES.values()}):
        a = lo - query.EDGE_NS
        fm = [astuple(p) for p in fs.metric_points(name, a, hi) if a <= p.time_ns < hi and p.name == name]
        lm = [astuple(p) for p in ls.metric_points(name, a, hi) if a <= p.time_ns < hi and p.name == name]
        out[name] = _multiset_diff(fm, lm, key=lambda t: (t[1], t[2], t[3]), fields=tuple(query.MetricPoint.__slots__))
    return out


# --- Koşu (P2a 4. madde, ikinci commit) -------------------------------------------------------------------------
#
#   python tools/query_compare.py run (--set pilot | --cases <id>,<id>) [--out <klasör>]
# Vaka başına: `storage_check.replay_case` (yığın açık); şartlardan biri kalırsa `down -v` ve bir kez daha; çağrılar
# iki tarafa (`call_list` sırasıyla); ham kayıt (C); karşılaştırma boyunca 30 sn'de bir yığın belleği; sonda yığın
# konteynerlerinde OOM / yeniden başlama denetimi (varsa vaka geçersiz, onaylı kuralla bir kez daha; HANDOFF
# 2026-11-11); canlı çıktılar `outputs.jsonl`'a, `leakage.scan_model_view` ile taranır, sonra silinir (çağrı başına
# sha256 kalır); `down -v`. Kayıt `<out>/<vaka>/case.json` (+ `calls.jsonl`: çağrı başına eşitlik, sha256, süre, ilk
# fark), koşu özeti `<out>/run.json`. Varsayılan `<out>` = `~/cerebrum2/p2a_compare/<UTC>-<set|cases>/`.
# Yalnız `load_cases()` vakaları (pilot, dev); test ve heldout açılmaz.

import argparse  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

OUT_ROOT = Path.home() / "cerebrum2" / "p2a_compare"


def _mem_sampler(sc, peaks: dict, stop: threading.Event) -> None:
    while not stop.wait(30):
        for n, v in sc.mem_mib(sc.REPLAY_CONTAINERS).items():
            if v:
                peaks[n] = max(peaks.get(n, 0.0), v)


def _containers_ok(states: dict) -> bool:
    return all(v and not v["oom_killed"] and v["restarts"] == 0 for v in states.values())


def compare_once(case: Case, d: Path, log) -> dict:
    """Bir deneme: oynatma + karşılaştırma. Döner: deneme kaydı (`valid` ile)."""
    import storage_check as sc
    from aiops_rca.leakage import scan_model_view
    from aiops_rca.store_file import FileStore
    from aiops_rca.store_live import LiveStore

    res: dict = {}
    code = sc.replay_case(case.view, keep_up=True, result=res)
    rec = {"replay_dir": str(res.get("dir")), "replay_valid": code == 0, "valid": False,
           "exemplar_rejects": (res.get("rec") or {}).get("checks", {}).get("exemplar_rejects"),
           "replay_s": (res.get("rec") or {}).get("replay_s")}
    try:
        if code != 0:
            rec["problem"] = "replay_case failed: " + "; ".join(
                [k for k, v in ((res.get("rec") or {}).get("criteria") or {}).items() if not v]
                + (res.get("rec") or {}).get("problems", []))
            return rec
        peaks, stop = {}, threading.Event()
        th = threading.Thread(target=_mem_sampler, args=(sc, peaks, stop), daemon=True)
        th.start()
        t0 = time.monotonic()
        fs, ls = FileStore(case), LiveStore(case)
        calls = call_list(case, fs)
        live_dir = d / "live"
        live_dir.mkdir(parents=True, exist_ok=True)
        by_fn: dict[str, Counter] = {}
        file_s = live_s = 0.0
        with (d / "calls.jsonl").open("w") as rows, (live_dir / "outputs.jsonl").open("w") as outs:
            for i, c in enumerate(calls):
                t1 = time.monotonic()
                a = run_call(fs, c)
                t2 = time.monotonic()
                b = run_call(ls, c)
                t3 = time.monotonic()
                file_s, live_s = file_s + t2 - t1, live_s + t3 - t2
                eq = a == b
                row = {"id": c["id"], "fn": c["fn"], "args": c["args"], "equal": eq, "file_sha": digest(a),
                       "live_sha": digest(b), "file_s": round(t2 - t1, 3), "live_s": round(t3 - t2, 3)}
                if not eq:
                    row["first_diff"] = first_diff(a, b)
                    row["diff_paths"] = dict(diff_paths(a, b).most_common())
                rows.write(json.dumps(row, ensure_ascii=False) + "\n")
                outs.write(json.dumps({"id": c["id"], "fn": c["fn"], "output": b}, ensure_ascii=False) + "\n")
                by_fn.setdefault(c["fn"], Counter())["equal" if eq else "different"] += 1
                if (i + 1) % 100 == 0:
                    log(f"  {case.incident_id}: {i + 1}/{len(calls)} calls; live {live_s:.0f} s, file {file_s:.0f} s")
        lo, hi = ranges(case, fs)["C"]
        rec["raw"] = raw_compare(fs, ls, lo, hi)
        rec["calls"] = {fn: dict(c) for fn, c in by_fn.items()}
        rec["n_calls"] = len(calls)
        rec["compare_s"] = round(time.monotonic() - t0)
        rec["file_s"], rec["live_s"] = round(file_s), round(live_s)
        rec["live_queries"] = dict(ls.queries)
        stop.set()
        rec["mem_peak_mib"] = {n: round(v, 1) for n, v in peaks.items()}
        rec["containers_after"] = sc.container_states(sc.REPLAY_CONTAINERS)
        rec["containers_ok"] = _containers_ok(rec["containers_after"])
        t1 = time.monotonic()
        findings = scan_model_view(live_dir)
        rec["leakage"] = {"findings": len(findings), "examples": [str(f) for f in findings[:5]],
                          "bytes": (live_dir / "outputs.jsonl").stat().st_size,
                          "seconds": round(time.monotonic() - t1)}
        shutil.rmtree(live_dir)
        rec["valid"] = rec["containers_ok"]
        if not rec["containers_ok"]:
            rec["problem"] = "replay stack container restarted or OOM during the comparison"
        return rec
    finally:
        p = sc.replay_compose(["down", "-v"], case.view)
        rec["down_exit"] = p.returncode
        left = [n for n in sc.volume_sizes() if n.startswith(sc.REPLAY_PROJECT + "_")]
        rec["replay_volumes_left"] = left
        if left:
            rec["valid"] = False
            rec["problem"] = (rec.get("problem", "") + "; replay volumes left after down -v").lstrip("; ")


def compare_case(case: Case, out: Path, log) -> dict:
    d = out / case.incident_id
    d.mkdir(parents=True, exist_ok=True)
    attempts = []
    for n in (1, 2):
        log(f"{case.incident_id}: attempt {n}")
        rec = compare_once(case, d, log)
        attempts.append(rec)
        log(f"{case.incident_id}: attempt {n} valid {rec['valid']} {rec.get('problem', '')}")
        if rec["valid"]:
            break
    final = attempts[-1]
    summary = {"case": case.incident_id, "replayed": final["valid"], "attempts": len(attempts),
               "attempt_records": attempts}
    if final["valid"]:
        diff = sum(c.get("different", 0) for c in final["calls"].values())
        summary.update(calls_equal=final["n_calls"] - diff, calls_different=diff,
                       raw_equal=all(v["equal"] for v in final["raw"].values()))
    (d / "case.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    return summary


def run(cases: list[Case], out: Path) -> int:
    import scenario_runner as sr
    out.mkdir(parents=True, exist_ok=True)
    log_file = (out / "run.log").open("a")

    def log(msg: str) -> None:
        line = f"{sr.iso(sr.utc_ns())} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    t0 = time.monotonic()
    repo = Path(__file__).resolve().parents[1]
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()  # noqa: E731
    rec = {"cases": [c.incident_id for c in cases], "results": {}, "started_utc": sr.iso(sr.utc_ns()),
           "git_sha": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain", "--", "src", "tools"))}
    for c in cases:
        s = compare_case(c, out, log)
        rec["results"][c.incident_id] = {k: v for k, v in s.items() if k != "attempt_records"}
        rec["seconds"] = round(time.monotonic() - t0)
        (out / "run.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        log(f"{c.incident_id}: {rec['results'][c.incident_id]}")
    log(f"done -> {out}; {rec['seconds']} s")
    log_file.close()
    return 0 if all(r["replayed"] for r in rec["results"].values()) else 1


# --- Rapor (P2a 4. madde) ---------------------------------------------------------------------------------------
#
#   python tools/query_compare.py report <koşu klasörü>... [--out results/p2a_compare]
# Koşu kayıtlarından `<out>.json` ve `<out>.md`. Farklı her çağrının türü kodla: dosya okuyucusuna Jaeger'in bilinen
# dönüşümleri (`JAEGER_TRANSFORMS`) tek tek ve birlikte uygulanıp çağrı yeniden koşulur; canlı sha256'yla eşitleyen en
# küçük dönüşüm kümesi türdür, hiçbiri eşitlemezse "açıklanamadı". Snapshot'ları okur (yalnız pilot / dev; CI'da koşmaz).

# Jaeger'in okurken yaptığı dönüşümler (DECISIONS 2026-11-11): ad → açıklama.
JAEGER_TRANSFORMS = {
    "zero_duration": "Jaeger süresi 0 olan span'i bitiş + 1 ns ile döndürüyor (depolama; duration_ms 0 ↔ 1e-06)",
    "error_tag": "Jaeger error=\"true\" etiketini hata durumuna çeviriyor (depolama); canlı okuyucu bunu geri alıyor "
                 "(store_live.undo_jaeger_error_tag, DECISIONS 2026-11-12), bu tür artık beklenmiyor (tanı olarak "
                 "sınanır)",
}


def jaeger_like_store(case: Case, transforms: frozenset[str]):
    """Dosya okuyucusu + seçilen Jaeger dönüşümleri (span'lerde)."""
    import dataclasses
    from aiops_rca.query import span_from_otlp
    from aiops_rca.signals import iter_lines, resource_attr
    from aiops_rca.store_file import FileStore

    class _Store(FileStore):
        def _load_spans(self):
            if self._spans is None:
                out = []
                for doc in iter_lines([self.view / "traces.jsonl"]):
                    for rs in doc.get("resourceSpans", []):
                        svc = resource_attr(rs.get("resource", {}), "service.name")
                        if svc is None:
                            continue
                        for ss in rs.get("scopeSpans", []):
                            for sp in ss.get("spans", []):
                                s = span_from_otlp(svc, sp)
                                if "error_tag" in transforms and s.status == 0 and any(
                                        a.get("key") == "error" and a.get("value", {}).get("stringValue") == "true"
                                        for a in sp.get("attributes", [])):
                                    s = dataclasses.replace(s, status=2)
                                if "zero_duration" in transforms and s.end_ns == s.start_ns:
                                    s = dataclasses.replace(s, end_ns=s.end_ns + 1)
                                out.append(s)
                self._spans = out
            return self._spans

    return _Store(case)


def classify_differences(case: Case, rows: list[dict]) -> dict[int, str]:
    """Farklı çağrı kimliği → tür ("zero_duration", "error_tag", "zero_duration+error_tag", "unexplained")."""
    import itertools
    names = sorted(JAEGER_TRANSFORMS)
    subsets = [frozenset(c) for n in range(1, len(names) + 1) for c in itertools.combinations(names, n)]
    stores = {t: jaeger_like_store(case, t) for t in subsets}
    out = {}
    for r in rows:
        if r["equal"]:
            continue
        call = {"fn": r["fn"], "args": r["args"]}
        out[r["id"]] = next(("+".join(sorted(t)) for t in subsets if digest(run_call(stores[t], call)) == r["live_sha"]),
                            "unexplained")
    return out


def build_report(runs: list[Path]) -> dict:
    from aiops_rca.cases import load_cases
    sets = {c.incident_id: s for s in ("pilot", "dev") for c in load_cases((s,))}
    known = {c.incident_id: c for c in load_cases()}
    rep = {"runs": [], "cases": {}, "totals": {}, "types": {}, "transforms": JAEGER_TRANSFORMS}
    for run_dir in runs:
        meta = json.loads((run_dir / "run.json").read_text())
        rep["runs"].append({"dir": run_dir.name, "git_sha": meta.get("git_sha"), "git_dirty": meta.get("git_dirty"),
                            "seconds": meta.get("seconds"), "cases": len(meta["cases"])})
        for cid in meta["cases"]:
            summary = json.loads((run_dir / cid / "case.json").read_text())
            a = summary["attempt_records"][-1]
            row = {"set": sets.get(cid), "run": run_dir.name, "attempts": summary["attempts"],
                   "replayed": summary["replayed"]}
            if summary["replayed"]:
                rows = [json.loads(x) for x in (run_dir / cid / "calls.jsonl").open()]
                kinds = classify_differences(known[cid], rows)
                rp = json.loads((Path(a["replay_dir"]) / "replay_case.json").read_text())
                row.update(calls={fn: dict(c) for fn, c in sorted(a["calls"].items())},
                           types=dict(Counter(kinds.values())),
                           raw={k: {"equal": v["equal"], "changed_ids": v["changed_ids"],
                                    "ids_only_file": v["only_file"] - v["changed_ids"],
                                    "ids_only_live": v["only_live"] - v["changed_ids"],
                                    "changed_fields": v.get("changed_fields", {})} for k, v in a["raw"].items()},
                           exemplar_rejects=a["exemplar_rejects"], leakage_findings=a["leakage"]["findings"],
                           compare_s=a["compare_s"], replay_s=a["replay_s"],
                           jaeger_peak_mib={"replay": rp["mem_peak_mib"].get("otel-replay-jaeger-1"),
                                            "compare": a["mem_peak_mib"].get("otel-replay-jaeger-1")})
            else:
                row["problem"] = a.get("problem")
            rep["cases"][cid] = row
    for s in ("pilot", "dev"):
        rows = [r for r in rep["cases"].values() if r["set"] == s]
        if not rows:
            continue
        ok = [r for r in rows if r["replayed"]]
        fn_tot, types, raw_fields = {}, Counter(), Counter()
        for r in ok:
            for fn, c in r["calls"].items():
                for k, v in c.items():
                    fn_tot.setdefault(fn, Counter())[k] += v
            types.update(r["types"])
            for k, v in r["raw"].items():
                raw_fields.update({f"{k}: aynı kimlikte farklı ({f})": n for f, n in v["changed_fields"].items()})
                raw_fields[f"{k}: yalnız dosyada kimlik"] += v["ids_only_file"]
                raw_fields[f"{k}: yalnız canlıda kimlik"] += v["ids_only_live"]
        rep["totals"][s] = {
            "cases": len(rows), "replayed": len(ok), "retried": sum(r["attempts"] > 1 for r in rows),
            "calls": {fn: dict(c) for fn, c in sorted(fn_tot.items())},
            "equal": sum(c.get("equal", 0) for c in fn_tot.values()),
            "different": sum(c.get("different", 0) for c in fn_tot.values()),
            "leakage_findings": sum(r["leakage_findings"] for r in ok),
            "exemplar_rejects": {"min": min(r["exemplar_rejects"] for r in ok), "max": max(r["exemplar_rejects"] for r in ok),
                                 "sum": sum(r["exemplar_rejects"] for r in ok)} if ok else None,
            "jaeger_peak_mib": max(max(v for v in r["jaeger_peak_mib"].values() if v) for r in ok) if ok else None,
            "compare_s": {"min": min(r["compare_s"] for r in ok), "max": max(r["compare_s"] for r in ok)} if ok else None,
            "raw_changes": {k: v for k, v in sorted(raw_fields.items()) if v},
        }
        rep["types"][s] = dict(sorted(types.items()))
    return rep


def render_report(rep: dict) -> str:
    L = ["# P2a: dosya ↔ canlı karşılaştırması", "",
         "Komutla üretilir: `python tools/query_compare.py report <koşu klasörü>...` (kayıtlar repo dışında, "
         "`~/cerebrum2/p2a_compare/`). Çağrı listesi, eşitlik tanımı ve OOM kuralı ölçmeden önce yazıldı "
         "(HANDOFF 2026-11-11); fark türlerinin kararı sonuç görüldükten sonra (DECISIONS 2026-11-11).", "",
         "Eşitlik: çağrı çıktısı iki tarafta birebir aynı (tolerans yok). Fark türü kodla: dosya okuyucusuna "
         "Jaeger'in bilinen dönüşümleri uygulanıp çağrı yeniden koşulur; canlıyla eşitleyen dönüşüm türdür.", "",
         "## Koşular", "", "| Koşu | Kod | Vaka | Süre (sa) |", "|---|---|---|---|"]
    for r in rep["runs"]:
        L.append(f"| `{r['dir']}` | `{(r['git_sha'] or '')[:7]}`{' (dirty)' if r['git_dirty'] else ''} | "
                 f"{r['cases']} | {r['seconds'] / 3600:.2f} |")
    for s, t in rep["totals"].items():
        L += ["", f"## {s}", "",
              f"- Vaka: {t['cases']}; oynatılan {t['replayed']}; yeniden denenen {t['retried']}.",
              f"- Çağrı: {t['equal'] + t['different']}; eşit {t['equal']}, farklı {t['different']}.",
              f"- Sızıntı bulgusu (canlı çıktılar): {t['leakage_findings']}.",
              f"- Exemplar reddi (vaka başına): {t['exemplar_rejects']['min']:.0f}–{t['exemplar_rejects']['max']:.0f}, "
              f"toplam {t['exemplar_rejects']['sum']:.0f} (şart değil; DECISIONS 2026-11-10).",
              f"- Jaeger bellek tepesi: {t['jaeger_peak_mib']:.1f} MiB (sınır 2000 MiB).",
              f"- Karşılaştırma süresi (vaka başına, oynatma hariç): {t['compare_s']['min']}–{t['compare_s']['max']} sn.",
              "", "| Fonksiyon | Eşit | Farklı |", "|---|---|---|"]
        for fn, c in t["calls"].items():
            L.append(f"| `{fn}` | {c.get('equal', 0)} | {c.get('different', 0)} |")
        L += ["", "| Fark türü | Çağrı |", "|---|---|"]
        for k, n in rep["types"][s].items():
            L.append(f"| `{k}` | {n} |")
        L += ["", f"Açıklanamayan farklı çağrı: {rep['types'][s].get('unexplained', 0)}."]
        L += ["", "Ham kayıt (C aralığı; span, log, dört metrik) farkları; listede olmayan sinyal ve sayaç 0:", ""]
        L += [f"- {k}: {v}" for k, v in t["raw_changes"].items()] or ["- yok"]
    L += ["", "## Fark türlerinin açıklaması", ""]
    L += [f"- `{k}`: {v}." for k, v in rep["transforms"].items()]
    L += ["", "## Sınırlamalar", "",
          "- Jaeger süresi 0 olan span'i bitiş + 1 ns ile döndürüyor; geri çevrilmez (gerçekten 1 ns süren span "
          "canlıda aynı görünür). Bu çağrılar farklı sayılır (DECISIONS 2026-11-11).",
          "- Jaeger error=\"true\" etiketini hata durumuna çeviriyor; canlı okuyucu geri alıyor. Kural Jaeger'in "
          "bugünkü davranışına (belirtilmemiş + etiket → hata, etiket kalır; hata + etiket → etiket silinir) bağlı "
          "(DECISIONS 2026-11-12).",
          "- Hata tanımı (OTLP durumu; P1 ile aynı) Envoy'un yanıtsız isteklerini (http.status_code 0, yalnız "
          "error=\"true\" etiketi) hata saymıyor; dosyada da canlıda da (DECISIONS 2026-11-12).",
          "- Exemplar reddi her vakada var ve koşudan koşuya değişiyor; sorgu katmanı exemplar okumuyor "
          "(DECISIONS 2026-11-10).",
          "- Çağrı listesi dosya tarafından türetiliyor (servisler, izler); canlıda fazladan olan bir şey yalnız "
          "süzgeçsiz çağrılarda ve ham kayıt karşılaştırmasında görünür.",
          "", "## Vakalar", "", "| Vaka | Set | Deneme | Eşit | Farklı | Türler | Exemplar | Jaeger MiB (oynatma / karş.) |",
          "|---|---|---|---|---|---|---|---|"]
    for cid, r in sorted(rep["cases"].items(), key=lambda x: (x[1]["set"] or "", x[0])):
        if not r["replayed"]:
            L.append(f"| `{cid}` | {r['set']} | {r['attempts']} | oynatılamadı: {r.get('problem')} | | | | |")
            continue
        eq = sum(c.get("equal", 0) for c in r["calls"].values())
        df = sum(c.get("different", 0) for c in r["calls"].values())
        ty = ", ".join(f"{k} {v}" for k, v in sorted(r["types"].items())) or "—"
        jp = r["jaeger_peak_mib"]
        L.append(f"| `{cid}` | {r['set']} | {r['attempts']} | {eq} | {df} | {ty} | {r['exemplar_rejects']:.0f} | "
                 f"{jp['replay']:.0f} / {jp['compare']:.0f} |")
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    from aiops_rca.cases import load_cases
    ap = argparse.ArgumentParser(prog="query_compare.py", description="P2a file vs live query comparison")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="replay each case and compare the same calls on file and live stores")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", choices=("pilot", "dev"))
    g.add_argument("--cases", help="comma-separated incident ids (pilot / dev only)")
    r.add_argument("--out", type=Path)
    rp = sub.add_parser("report", help="build results/p2a_compare.json and .md from run folders")
    rp.add_argument("runs", nargs="+", type=Path)
    rp.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "results" / "p2a_compare")
    args = ap.parse_args(argv)
    if args.cmd == "report":
        rep = build_report([r.resolve() for r in args.runs])
        args.out.with_suffix(".json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n")
        args.out.with_suffix(".md").write_text(render_report(rep))
        print(f"-> {args.out.with_suffix('.json')}, {args.out.with_suffix('.md')}; types {rep['types']}")
        return 0
    known = {c.incident_id: c for c in load_cases()}
    if args.set:
        cases = [c for c in load_cases((args.set,))]
        tag = args.set
    else:
        ids = args.cases.split(",")
        bad = [i for i in ids if i not in known]
        if bad:
            print(f"error: not valid pilot/dev cases: {bad}", file=sys.stderr)
            return 2
        cases = [known[i] for i in ids]
        tag = "cases"
    out = args.out or OUT_ROOT / (time.strftime("%Y%m%dT%H%MZ", time.gmtime()) + f"-{tag}")
    if os.environ.get("SCENARIO_RUNNER_INHIBITED") != "1":
        import scenario_runner as sr
        env = dict(os.environ, SCENARIO_RUNNER_INHIBITED="1")
        cmd = [*sr.GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
               "--who=aiops_rca query_compare", "--why=storage card P2a query compare", sys.executable,
               *sys.argv]  # neden metni scenario_runner.inhibited()'in tanıdığı "storage card" ile
        if not args.out:
            cmd += ["--out", str(out)]
        return subprocess.run(cmd, env=env).returncode
    return run(cases, out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
