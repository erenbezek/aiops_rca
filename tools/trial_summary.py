"""Kaba kalite denemeleri için vaka özeti (HANDOFF 2026-10-21, DECISIONS 2026-10-21).

Kullanım: python tools/trial_summary.py --alarm 2026-10-21T14:00:00+03:00 --out <klasör>/summary.json
          [--input ~/cerebrum2/telemetry/filtered]

Sadece süzülmüş collector dosyalarını (`*.jsonl`, döndürülmüş dosyalar dahil) okur. Pencere: alarmdan önceki
10 dk ("before") ve sonraki 10 dk ("after"). Kaydın zamanı: span'de `startTimeUnixNano`; logda `timeUnixNano`,
0 ya da yoksa `observedTimeUnixNano`; metrikte veri noktasının `timeUnixNano`'su.

İçerik bilerek basit (daraltma değil):
- Servis başına gelen istek sayısı (SERVER ve CONSUMER span'leri), hata oranı (span durumu ERROR), p95 süre (ms),
  önce / sonra.
- Konteyner başına CPU (`container.cpu.utilization`, `docker stats` gibi bir çekirdeğin yüzdesi; ortalama ve en
  yüksek) ve bellek (`container.memory.usage.total`, MB; sadece ortalama), önce / sonra. Konteyner adı servis adıdır. İzleme
  araçlarının konteynerleri (mağazanın değil ölçüm aracının parçası) yok; mağazanın veritabanları var.
  Servis satırında olmayan alan (ör. veritabanında istek, tarayıcı tarafında CPU) satırda yok.
- En sık WARN ve üstü log mesajları (sonraki pencerede), servis ve önce / sonra sayısıyla. WARN dahil: payment
  ödeme hatasını WARN seviyesinde logluyor. Mesajlar gruplanmak için sadeleşir: kimlikler ve sayılar yer tutucu olur.

Özete flag adı, senaryo adı ya da kök neden ipucu yazılmaz; çıktı sızıntı CLI'ı ile ayrıca taranır.
Pencerenin iki ucunda span, log ya da metrik kaydı yoksa (dosya döndürmesi silmiş ya da koşu kısa) hata verir,
eksik özet yazmaz.
Çıkış kodu: 0 yazıldı, 1 pencere eksik, 2 kullanım/girdi hatası.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

WINDOW_NS = 10 * 60 * 10**9
EDGE_NS = 60 * 10**9  # pencere uçlarında kayıt aranan aralık
INCOMING_KINDS = {2, 5}  # SPAN_KIND_SERVER, SPAN_KIND_CONSUMER
STATUS_ERROR = 2
SEVERITY_WARN = 13
TOP_MESSAGES = 10
MESSAGE_CHARS = 200
MESSAGE_KEYS = ("exception.message", "err.message", "error.message", "error", "err", "message")

CPU_METRIC = "container.cpu.utilization"
MEMORY_METRIC = "container.memory.usage.total"
# İzleme araçları (Eren, 2026-10-21): özete girmez. flagd, flagd-ui, load-generator collector'da zaten düşüyor.
TOOLING_CONTAINERS = frozenset({"jaeger", "grafana", "prometheus", "opensearch", "otel-collector", "opamp-server"})

ID_PATTERNS = (
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<id>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "<id>"),
    (re.compile(r"\d+"), "<n>"),
)


def resource_attr(resource: dict, key: str) -> str | None:
    for a in resource.get("attributes", []):
        if a.get("key") == key:
            return a.get("value", {}).get("stringValue")
    return None


def value_text(value: dict) -> str:
    if "stringValue" in value:
        return value["stringValue"]
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def log_message(record: dict) -> str:
    text = value_text(record.get("body", {})).strip()
    if text:
        return text
    attrs = {a.get("key"): a.get("value", {}) for a in record.get("attributes", [])}
    for key in MESSAGE_KEYS:
        if key in attrs and value_text(attrs[key]).strip():
            return value_text(attrs[key]).strip()
    return "<no message>"


def normalize(message: str) -> str:
    message = " ".join(message.split())
    for pattern, repl in ID_PATTERNS:
        message = pattern.sub(repl, message)
    return message[:MESSAGE_CHARS]


def p95_ms(durations_ns: list[int]) -> float | None:
    if not durations_ns:
        return None
    ordered = sorted(durations_ns)
    idx = max(0, math.ceil(0.95 * len(ordered)) - 1)  # en yakın sıra yöntemi
    return round(ordered[idx] / 1e6, 1)


def point_value(dp: dict) -> float | None:
    if "asDouble" in dp:
        return float(dp["asDouble"])
    if "asInt" in dp:
        return float(dp["asInt"])
    return None


class Window:
    def __init__(self, alarm_ns: int):
        self.start = alarm_ns - WINDOW_NS
        self.alarm = alarm_ns
        self.end = alarm_ns + WINDOW_NS

    def side(self, t: int) -> str | None:
        if self.start <= t < self.alarm:
            return "before"
        if self.alarm <= t < self.end:
            return "after"
        return None


def iter_lines(paths: list[Path]):
    for path in paths:
        with path.open(encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except ValueError as e:
                        raise ValueError(f"{path}:{n}: {e}") from e


def summarize(paths: list[Path], window: Window) -> tuple[dict, dict]:
    spans = defaultdict(lambda: {"before": [0, 0, []], "after": [0, 0, []]})  # [istek, hata, süreler]
    logs = defaultdict(Counter)  # (servis, mesaj) -> {before, after}
    resources = defaultdict(lambda: {"before": [], "after": []})  # (konteyner, metrik) -> değerler
    edges = {"spans": [False, False], "logs": [False, False], "metrics": [False, False]}

    def mark(signal: str, t: int) -> None:
        if window.start <= t < window.start + EDGE_NS:
            edges[signal][0] = True
        if window.end - EDGE_NS <= t < window.end:
            edges[signal][1] = True

    for doc in iter_lines(paths):
        for rs in doc.get("resourceSpans", []):
            svc = resource_attr(rs.get("resource", {}), "service.name")
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    t = int(sp.get("startTimeUnixNano", 0))
                    mark("spans", t)
                    side = window.side(t)
                    if side is None or svc is None or sp.get("kind") not in INCOMING_KINDS:
                        continue
                    row = spans[svc][side]
                    row[0] += 1
                    if sp.get("status", {}).get("code") == STATUS_ERROR:
                        row[1] += 1
                    row[2].append(int(sp.get("endTimeUnixNano", t)) - t)
        for rl in doc.get("resourceLogs", []):
            svc = resource_attr(rl.get("resource", {}), "service.name")
            for sl in rl.get("scopeLogs", []):
                for rec in sl.get("logRecords", []):
                    t = int(rec.get("timeUnixNano", 0)) or int(rec.get("observedTimeUnixNano", 0))
                    mark("logs", t)
                    side = window.side(t)
                    if side is None or rec.get("severityNumber", 0) < SEVERITY_WARN:
                        continue
                    logs[(svc or "<unknown>", normalize(log_message(rec)))][side] += 1
        for rm in doc.get("resourceMetrics", []):
            container = resource_attr(rm.get("resource", {}), "container.name")
            for sm in rm.get("scopeMetrics", []):
                for m in sm.get("metrics", []):
                    if m.get("name") not in (CPU_METRIC, MEMORY_METRIC):
                        continue
                    for dp in (m.get("gauge") or m.get("sum") or {}).get("dataPoints", []):
                        t = int(dp.get("timeUnixNano", 0))
                        mark("metrics", t)
                        side = window.side(t)
                        value = point_value(dp)
                        if side is None or not container or container in TOOLING_CONTAINERS or value is None:
                            continue
                        resources[(container, m["name"])][side].append(value)
    return {"spans": spans, "logs": logs, "resources": resources}, edges


def avg_max(values: list[float], scale: float, digits: int) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    avg, peak = round(sum(values) / len(values) * scale, digits), round(max(values) * scale, digits)
    if digits == 0:  # "217" yerine "217.0" yazılmasın (bellek alanlarında ~130 token)
        avg, peak = int(avg), int(peak)
    return avg, peak


def build(result: dict, window: Window) -> dict:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--alarm", required=True, help="ISO 8601 with timezone, e.g. 2026-10-21T14:00:00+03:00")
    parser.add_argument("--out", required=True, help="output JSON file")
    parser.add_argument("--input", default=str(Path.home() / "cerebrum2/telemetry/filtered"))
    args = parser.parse_args(argv)

    try:
        alarm = datetime.fromisoformat(args.alarm)
    except ValueError as e:
        print(f"error: --alarm: {e}", file=sys.stderr)
        return 2
    if alarm.tzinfo is None:
        print("error: --alarm needs a timezone (e.g. +03:00)", file=sys.stderr)
        return 2
    paths = sorted(Path(args.input).expanduser().glob("*.jsonl"))
    if not paths:
        print(f"error: no *.jsonl in {args.input}", file=sys.stderr)
        return 2

    window = Window(int(alarm.timestamp()) * 10**9)
    try:
        result, edges = summarize(paths, window)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    missing = [f"{sig} {end}" for sig, (first, last) in edges.items()
               for end, ok in (("start", first), ("end", last)) if not ok]
    if missing:
        print(f"error: window not covered by data: {', '.join(missing)}", file=sys.stderr)
        return 1

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    # Girintisiz: aynı içerik girintiliye göre ~%35 daha az token (Qwen3.5 tokenizer'ı, 1.099'a karşı 1.713).
    text = json.dumps(build(result, window), ensure_ascii=False, separators=(",", ":"))
    out.write_text(text + "\n", encoding="utf-8")
    print(f"ok: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
