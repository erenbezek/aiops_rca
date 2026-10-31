"""Modele giden girdinin seviyeleri (HANDOFF 2026-10-30 P1c kartı 2. madde; DECISIONS 2026-10-30 "Ham log yeniden
tanımlandı", 2026-10-31 "İstem payı", "Ham kesme kuralı", "Boş ham girdi"). Deterministik: aynı vaka ve tokenizer
aynı metni verir.

- **summary** (özet): bütün servislerin önce/sonra sinyal tablosu, denemelerdeki biçim (`tools/trial_summary.py`'den
  taşındı; betik bu adları buradan içe aktarır). Girintisiz JSON.
- **raw** (ham): pencere [alarm − 10 dk, alarm + 10 dk) içindeki WARN+ log kayıtları (severityNumber ≥ 13) ve status
  ERROR span'leri (bütün türler); hesaplanmış sayı yok. Satır `HH:MM:SS.mmm <servis> log <mesaj>` ya da
  `HH:MM:SS.mmm <servis> error-span <span adı>` (UTC); mesajda boşluk ve satır sonları tek boşluğa iner, kimlik/sayı
  sadeleştirmesi yok; satır 500 karakterde kesilir; sıra zaman, eşitlikte satır metni. Veri bloğu ≤ 5000 token: sığmazsa
  zaman sırasıyla baştan tam satırlar, sonra sabit `TRUNCATION_MARK` satırı (işaret dahil ≤ 5000). Pencerede satır
  yoksa girdi boş (`empty`): modele sorulmaz.
- **narrowed** (daraltma; DECISIONS 2026-10-31 "Daraltma girdisinin biçimi"): girintisiz JSON; `alarm_time_utc`,
  `window_minutes`; `candidates` = `candidate_narrowing`'in ilk 5 adayı, **ada göre**; her adayda özetteki servis
  satırının aynısı, `operations` (gelen span adları), `callers` (adayı çağıran istemci span'leri, çağıran + span adı),
  `logs` (alarm sonrası en sık 3 WARN+ mesajı); `calls` = adaylar arasındaki çağrı kenarları (sayısız). Daraltmanın
  grubu, puanı ve sırası verilmez.

Token sayımı dışarıdan verilir (`count_tokens(metin) -> int`; koşuda `llm_client.LocalServer.tokenize`, testlerde
sahte). Her seviye bir sözlük döndürür: `level`, `incident_id`, `text` (veri bloğu), `data_tokens`, `empty`; ham
seviyede ayrıca `lines_total`, `lines_kept`, `truncated`; daraltmada `candidates` (ada göre).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Callable

from aiops_rca.cases import Case
from aiops_rca.narrowing import candidate_narrowing
from aiops_rca.signals import (CPU_METRIC, MEMORY_METRIC, SEVERITY_WARN, STATUS_ERROR, Window, caller_rows,
                               iter_lines, log_message, operation_rows, resource_attr, summarize)

LEVELS = ("raw", "summary", "narrowed")
DATA_BUDGET = 5000  # veri bloğu; 6K'nın 1000'i istem + şablon (DECISIONS 2026-10-31 "İstem payı")
RAW_LINE_CHARS = 500
TRUNCATION_MARK = "[truncated: later lines omitted]"
TOP_MESSAGES = 10
TOP_CANDIDATE_LOGS = 3

TokenCounter = Callable[[str], int]


# --- özet (tools/trial_summary.py'den taşındı, davranış aynı) ---

def p95_ms(durations_ns: list[int]) -> float | None:
    if not durations_ns:
        return None
    ordered = sorted(durations_ns)
    idx = max(0, math.ceil(0.95 * len(ordered)) - 1)  # en yakın sıra yöntemi
    return round(ordered[idx] / 1e6, 1)


def avg_max(values: list[float], scale: float, digits: int) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    avg, peak = round(sum(values) / len(values) * scale, digits), round(max(values) * scale, digits)
    if digits == 0:  # "217" yerine "217.0" yazılmasın (bellek alanlarında ~130 token)
        avg, peak = int(avg), int(peak)
    return avg, peak


def summary_table(result: dict, window: Window) -> dict:
    """Denemelerdeki özet (`trial_summary.build`): servis satırları ve alarm sonrası en sık WARN+ mesajlar."""
    names = set(result["spans"]) | {c for c, _ in result["resources"]}
    services = []
    for svc in sorted(names):
        row = {"service": svc}
        for side in ("before", "after"):
            if svc in result["spans"]:
                count, errors, durations = result["spans"][svc][side]
                row[f"requests_{side}"] = count
                row[f"error_rate_{side}"] = round(errors / count, 3) if count else None
                row[f"p95_ms_{side}"] = p95_ms(durations)
            if (svc, CPU_METRIC) in result["resources"]:
                avg, peak = avg_max(result["resources"][(svc, CPU_METRIC)][side], 1, 2)
                row[f"cpu_pct_avg_{side}"], row[f"cpu_pct_max_{side}"] = avg, peak
            if (svc, MEMORY_METRIC) in result["resources"]:
                # Bellek en yükseği yok (token; Eren, 2026-10-21): bellek yavaş değişir, ortalama yeter.
                avg, _ = avg_max(result["resources"][(svc, MEMORY_METRIC)][side], 1 / 2**20, 0)
                row[f"mem_mb_avg_{side}"] = avg
        services.append(row)
    ranked = sorted(result["logs"].items(), key=lambda kv: (-kv[1]["after"], kv[0]))
    messages = [
        {"service": svc, "message": msg, "count_before": c["before"], "count_after": c["after"]}
        for (svc, msg), c in ranked
        if c["after"] > 0
    ][:TOP_MESSAGES]
    alarm = datetime.fromtimestamp(window.alarm / 1e9, tz=timezone.utc)
    return {
        "alarm_time_utc": alarm.isoformat(timespec="seconds"),
        "window_minutes": {"before": 10, "after": 10},
        "services": services,
        "top_warning_and_error_logs_after_alarm": messages,
    }


def summary_text(summary: dict) -> str:
    # Girintisiz: aynı içerik girintiliye göre ~%35 daha az token (Qwen3.5 tokenizer'ı, 1.099'a karşı 1.713).
    return json.dumps(summary, ensure_ascii=False, separators=(",", ":"))


def summary_input(case: Case, count_tokens: TokenCounter) -> dict:
    window = Window(case.alarm_ns)
    result, _ = summarize(sorted(case.view.glob("*.jsonl")), window)
    text = summary_text(summary_table(result, window))
    return {"level": "summary", "incident_id": case.incident_id, "text": text, "data_tokens": count_tokens(text),
            "empty": False}


# --- ham ---

def clock_ms(t_ns: int) -> str:
    """UTC `HH:MM:SS.mmm` (milisaniye aşağı yuvarlanır; tamsayı aritmetiği)."""
    sec, ns = divmod(t_ns, 10**9)
    return datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%H:%M:%S") + f".{ns // 10**6:03d}"


def raw_line(t_ns: int, service: str, kind: str, text: str) -> str:
    """`kind`: `log` ya da `error-span`. Boşluklar tek boşluğa iner; satır `RAW_LINE_CHARS`'ta kesilir."""
    return f"{clock_ms(t_ns)} {service} {kind} {' '.join(text.split())}"[:RAW_LINE_CHARS]


def raw_records(case: Case) -> list[tuple[int, str, str, str]]:
    """Penceredeki (zaman ns, servis, tür, metin) kayıtları; sıra yok. Servis bilinmiyorsa `<unknown>`."""
    window = Window(case.alarm_ns)
    out = []
    for doc in iter_lines(sorted(case.view.glob("*.jsonl"))):
        for rl in doc.get("resourceLogs", []):
            svc = resource_attr(rl.get("resource", {}), "service.name") or "<unknown>"
            for sl in rl.get("scopeLogs", []):
                for rec in sl.get("logRecords", []):
                    t = int(rec.get("timeUnixNano", 0)) or int(rec.get("observedTimeUnixNano", 0))
                    if window.side(t) is not None and rec.get("severityNumber", 0) >= SEVERITY_WARN:
                        out.append((t, svc, "log", log_message(rec)))
        for rs in doc.get("resourceSpans", []):
            svc = resource_attr(rs.get("resource", {}), "service.name") or "<unknown>"
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    t = int(sp.get("startTimeUnixNano", 0))
                    if window.side(t) is not None and sp.get("status", {}).get("code") == STATUS_ERROR:
                        out.append((t, svc, "error-span", sp.get("name", "")))
    return out


def raw_lines(records: list[tuple[int, str, str, str]]) -> list[str]:
    """Satırlar, zaman sonra satır metni sırasıyla."""
    return [line for _, line in sorted((t, raw_line(t, s, k, x)) for t, s, k, x in records)]


def fit_lines(lines: list[str], count_tokens: TokenCounter, budget: int = DATA_BUDGET) -> tuple[str, int, int]:
    """(metin, tutulan satır, token). Hepsi sığarsa hepsi; sığmazsa baştan en çok satır + `TRUNCATION_MARK`.
    En çok satır ikili aramayla (önek uzadıkça token azalmaz)."""
    full = "\n".join(lines)
    tokens = count_tokens(full)
    if tokens <= budget:
        return full, len(lines), tokens

    def text_for(k: int) -> str:
        return "\n".join(lines[:k] + [TRUNCATION_MARK])

    lo, hi = 0, len(lines) - 1  # lo: sığdığı bilinen; hi: denenecek en büyük
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_tokens(text_for(mid)) <= budget:
            lo = mid
        else:
            hi = mid - 1
    text = text_for(lo)
    tokens = count_tokens(text)
    if tokens > budget:  # işaret tek başına bile sığmıyor: bütçe hatalı
        raise ValueError(f"budget {budget} too small for the truncation mark")
    return text, lo, tokens


def raw_input(case: Case, count_tokens: TokenCounter, budget: int = DATA_BUDGET) -> dict:
    lines = raw_lines(raw_records(case))
    base = {"level": "raw", "incident_id": case.incident_id, "lines_total": len(lines)}
    if not lines:  # boş ham girdi: modele sorulmaz (DECISIONS 2026-10-31)
        return {**base, "text": "", "data_tokens": 0, "empty": True, "lines_kept": 0, "truncated": False}
    text, kept, tokens = fit_lines(lines, count_tokens, budget)
    return {**base, "text": text, "data_tokens": tokens, "empty": False, "lines_kept": kept,
            "truncated": kept < len(lines)}


# --- daraltma ---

def span_fields(sides: dict) -> dict:
    """Bir işlem satırının istek, hata oranı, p95 alanları (özetteki yazımla), önce/sonra."""
    out = {}
    for side in ("before", "after"):
        count, errors, durations = sides[side]
        out[f"requests_{side}"] = count
        out[f"error_rate_{side}"] = round(errors / count, 3) if count else None
        out[f"p95_ms_{side}"] = p95_ms(durations)
    return out


def narrowed_table(case: Case) -> dict:
    """Daraltma girdisinin tablosu (biçim modül belgesinde)."""
    window = Window(case.alarm_ns)
    result, _ = summarize(sorted(case.view.glob("*.jsonl")), window)
    summary = summary_table(result, window)
    rows = {r["service"]: r for r in summary["services"]}
    narrowing = candidate_narrowing(case)
    traces = [case.view / "traces.jsonl"]
    ops = operation_rows(traces, window)
    blocks = []
    for svc in sorted(narrowing["candidates"]):
        block = dict(rows.get(svc, {"service": svc}))
        block["operations"] = [{"operation": name, **span_fields(v)}
                               for (s, name), v in sorted(ops.items()) if s == svc]
        callers, _ = caller_rows(traces, window, svc)
        block["callers"] = [{"caller": c, "operation": name, **span_fields(v)} for (c, name), v in sorted(callers.items())]
        logs = sorted(((m, c) for (s, m), c in result["logs"].items() if s == svc and c["after"] > 0),
                      key=lambda x: (-x[1]["after"], x[0]))[:TOP_CANDIDATE_LOGS]
        block["logs"] = [{"message": m, "count_before": c["before"], "count_after": c["after"]} for m, c in logs]
        blocks.append(block)
    return {"alarm_time_utc": summary["alarm_time_utc"], "window_minutes": summary["window_minutes"],
            "candidates": blocks, "calls": [[a, b] for a, b, _ in narrowing["edges"]]}


def narrowed_input(case: Case, count_tokens: TokenCounter) -> dict:
    table = narrowed_table(case)
    text = summary_text(table)
    return {"level": "narrowed", "incident_id": case.incident_id, "text": text, "data_tokens": count_tokens(text),
            "empty": False, "candidates": [b["service"] for b in table["candidates"]]}
