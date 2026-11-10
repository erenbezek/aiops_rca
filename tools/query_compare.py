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


def _short(v) -> str:
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 120 else s[:117] + "..."


def digest(v) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _multiset_diff(file_items: list, live_items: list, key, examples: int = 5) -> dict:
    """Çoklu küme farkı; aynı kimlikte (key) farklı kayıtlar ayrıca sayılır."""
    fc, lc = Counter(file_items), Counter(live_items)
    only_file, only_live = fc - lc, lc - fc
    fk = {key(x) for x in only_file}
    lk = {key(x) for x in only_live}
    changed = fk & lk
    return {"file": len(file_items), "live": len(live_items), "equal": not only_file and not only_live,
            "only_file": sum(only_file.values()), "only_live": sum(only_live.values()), "changed_ids": len(changed),
            "examples_only_file": [repr(x) for x in list(only_file)[:examples]],
            "examples_only_live": [repr(x) for x in list(only_live)[:examples]]}


def raw_compare(fs, ls, lo: int, hi: int) -> dict:
    """Ham kayıt düzeyi (C): span'ler (başlangıcı aralıkta), loglar, dört konteyner metriği (lo − 60 sn'den)."""
    out = {}
    fsp = [astuple(s) for s in fs.spans(lo, hi) if lo <= s.start_ns < hi]
    lsp = [astuple(s) for s in ls.spans(lo, hi) if lo <= s.start_ns < hi]
    out["spans"] = _multiset_diff(fsp, lsp, key=lambda t: (t[0], t[1]))
    flg = [astuple(r) for r in fs.logs(lo, hi) if lo <= r.time_ns < hi]
    llg = [astuple(r) for r in ls.logs(lo, hi) if lo <= r.time_ns < hi]
    out["logs"] = _multiset_diff(flg, llg, key=lambda t: (t[0], t[1]))
    for name in sorted({n for n, _, _ in query.CONTAINER_SERIES.values()}):
        a = lo - query.EDGE_NS
        fm = [astuple(p) for p in fs.metric_points(name, a, hi) if a <= p.time_ns < hi and p.name == name]
        lm = [astuple(p) for p in ls.metric_points(name, a, hi) if a <= p.time_ns < hi and p.name == name]
        out[name] = _multiset_diff(fm, lm, key=lambda t: (t[1], t[2], t[3]))
    return out
