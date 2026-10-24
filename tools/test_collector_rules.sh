#!/usr/bin/env bash
# Collector kural testi (DECISIONS 2026-10-21, 2026-10-24; HANDOFF C2 kartı madde 5).
#
# Kullanım: tools/test_collector_rules.sh [--config <otelcol-config-extras.yml>]
#
# Geçici bir collector'a (demonun imajı, ~/cerebrum2/otel-demo/.env COLLECTOR_CONTRIB_IMAGE) bizim ayar dosyamız ve
# üstüne testin küçük katmanı verilir: otlp/http girişi (127.0.0.1, boş port), dosya çıkışı, hatlarda yalnız bu
# dosyada tanımlı işlemciler (filter/sim_world, transform/scrub; sıra gerçek hatlardan). Upstream'in işlemcileri
# çalışmaz: girdi süzülmemiş (raw) kayıtlardır, onlardan zaten geçmiştir.
#
# Girdi: tests/fixtures/collector_rules/{traces,metrics,logs}.jsonl (C2'nin raw verisinden tek kayıtlık, elle
# gözden geçirilmiş, makine bilgisi temizlenmiş istekler) ve rules.tsv (section, rule, test, sample, note).
# test: delete (tek sorumlu kural), alone (yedekli kural; Eren, 2026-10-24 seçenek A), none (örneksiz, note'ta
# gerekçe), clean (temiz kontrol, rule "-").
#
# Kontroller (hepsi tutarsa çıkış 0):
#   - Kapsam: ayardaki her (section, rule) rules.tsv'de bir kez; rules.tsv'deki her kural ayarda.
#   - Girdi: fixture klasöründe sızıntı CLI'ı bulgu > 0; her örnek satır sızıntılı (bulgu ya da yeniden yazımın
#     orijinal metni); temiz kontroller temiz.
#   - Bütün kurallar açık: çıktıda bulgu 0 ve orijinal metin 0; her temiz kontrol çıktıda girdiyle aynı.
#   - delete: yalnız o kural silinince kendi örneği çıktıda sızıntılı (kasıtlı kırmızı).
#   - alone: hiç kural yokken örnek sızıntılı (kırmızı); yalnız o kural varken düşer ya da temiz (yeşil).
#   - Collector logunda hata yok.
# Çıkış kodu: 0 geçti, 1 kontrol tutmadı, 2 kullanım/ortam hatası (Docker, imaj, dosya).
# Docker ister, CI'da koşmaz; collector sürümü değişince ve kural eklenince elle koşulur. Süre ~1 dk.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"
CONFIG="$REPO/deploy/otel-demo/otelcol-config-extras.yml"
if [[ "${1:-}" == "--config" && -n "${2:-}" ]]; then
  CONFIG="$2"
elif [[ $# -gt 0 ]]; then
  sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//' >&2
  exit 2
fi
ENV_FILE="$HOME/cerebrum2/otel-demo/.env"
IMAGE="$(sed -n 's/^COLLECTOR_CONTRIB_IMAGE=//p' "$ENV_FILE" 2>/dev/null || true)"
if [[ -z "$IMAGE" ]]; then
  echo "error: COLLECTOR_CONTRIB_IMAGE not found in $ENV_FILE" >&2
  exit 2
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "error: docker or image $IMAGE not available" >&2
  exit 2
fi

exec "$PY" - "$REPO" "$CONFIG" "$IMAGE" <<'PYEOF'
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO, CONFIG, IMAGE = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(REPO / "tools"))
from aiops_rca.leakage import LeakageInputError, scan_model_view  # noqa: E402
from c2_measure import REWRITES  # noqa: E402  (yeniden yazımların orijinal metinleri; tek kaynak)

FIXTURES = REPO / "tests" / "fixtures" / "collector_rules"
FILES = {"traces": "traces.jsonl", "metrics": "metrics.jsonl", "logs": "logs.jsonl"}
TOP = {"traces": "resourceSpans", "metrics": "resourceMetrics", "logs": "resourceLogs"}
ITEM = {"traces": "spans", "metrics": "metrics", "logs": "logRecords"}
PATHS = {"traces": "/v1/traces", "metrics": "/v1/metrics", "logs": "/v1/logs"}
ORIGINALS = [old for _, old, _, _ in REWRITES]
RULE_LINE = re.compile(r"^\s*- '(.*)'\s*$")
TESTS = ("delete", "alone", "none", "clean")


# --- ayar ---------------------------------------------------------------------------------------------------

def parse_rules(text):
    """processors bölümündeki tek satırlık kurallar: [(satır indeksi, section, rule)]."""
    out, inside, path = [], False, []
    for n, line in enumerate(text.splitlines()):
        if re.match(r"^\S", line):
            inside, path = line.startswith("processors:"), []
            continue
        if not inside or not line.strip() or line.strip().startswith("#"):
            continue
        m = RULE_LINE.match(line)
        if m:
            out.append((n, "/".join(p for _, p in path), m.group(1)))
            continue
        if line.strip().startswith("- ") and not line.strip().startswith("- context:"):
            raise SystemExit(f"error: {CONFIG}:{n + 1}: rule not on one single-quoted line: {line.strip()}")
        indent = len(line) - len(line.lstrip())
        key = line.strip().rstrip(":")
        if key.startswith("- context:"):
            key = key[2:].replace(" ", "")
        path = [(i, p) for i, p in path if i < indent] + [(indent, key)]
    return out


def our_processors(text):
    """Gerçek hatlardaki işlemcilerden bu dosyada tanımlı olanlar, sırasıyla."""
    defined, inside = set(), False
    for line in text.splitlines():
        if re.match(r"^\S", line):
            inside = line.startswith("processors:")
        elif inside and re.match(r"^  ([a-z_/]+):\s*$", line):
            defined.add(line.strip().rstrip(":"))
    pipes = {}
    for sig in FILES:
        m = re.search(rf"^    {sig}:\n      processors: \[([^\]]*)\]", text, re.M)
        if not m:
            raise SystemExit(f"error: {CONFIG}: pipeline {sig} processors not found")
        pipes[sig] = [p.strip() for p in m.group(1).split(",") if p.strip() in defined]
    return pipes


def test_layer(pipes):
    exp = "".join(f"  file/rule_test_{s}:\n    path: /out/{s}.jsonl\n    format: json\n" for s in pipes)
    pl = "".join(f"    {s}:\n      receivers: [otlp]\n      processors: [{', '.join(p)}]\n"
                 f"      exporters: [file/rule_test_{s}]\n" for s, p in pipes.items())
    return ("receivers:\n  otlp:\n    protocols:\n      http:\n        endpoint: 0.0.0.0:4318\n"
            f"exporters:\n{exp}service:\n  telemetry:\n    metrics:\n      level: none\n  pipelines:\n{pl}")


TEXT = CONFIG.read_text()
RULES = parse_rules(TEXT)
LINES = TEXT.splitlines(keepends=True)


def config_without(drop):
    return "".join(l for i, l in enumerate(LINES) if i not in drop)


# --- collector ----------------------------------------------------------------------------------------------

def post(base, sig, body):
    req = urllib.request.Request(base + PATHS[sig], data=body.encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()


def run_collector(config_text, records):
    """Kayıtları sırayla gönderir, collector'ı kapatır; {sig: [tek kayıtlık istek]} döner."""
    with tempfile.TemporaryDirectory(prefix="collector_rules_") as tmp:
        tmp = Path(tmp)
        (tmp / "cfg").mkdir()
        (tmp / "out").mkdir()
        (tmp / "cfg" / "extras.yml").write_text(config_text)
        (tmp / "cfg" / "test.yml").write_text(test_layer(our_processors(config_text)))
        cid = subprocess.run(
            ["docker", "run", "-d", "--user", f"{os.getuid()}:{os.getgid()}", "-p", "127.0.0.1::4318",
             "-v", f"{tmp / 'cfg'}:/cfg:ro", "-v", f"{tmp / 'out'}:/out", IMAGE,
             "--config=/cfg/extras.yml", "--config=/cfg/test.yml"],
            capture_output=True, text=True, check=True).stdout.strip()
        try:
            port = subprocess.run(["docker", "port", cid, "4318/tcp"], capture_output=True, text=True,
                                  check=True).stdout.split(":")[-1].strip()
            base = f"http://127.0.0.1:{port}"
            for _ in range(150):
                try:
                    post(base, "traces", '{"resourceSpans":[]}')
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("collector not ready")
            for sig, lines in records.items():
                for line in lines:
                    post(base, sig, line)
        finally:
            subprocess.run(["docker", "stop", "-t", "20", cid], capture_output=True)
            logs = subprocess.run(["docker", "logs", cid], capture_output=True, text=True)
            subprocess.run(["docker", "rm", cid], capture_output=True)
        errors = [l for l in (logs.stdout + logs.stderr).splitlines() if "\terror\t" in l or '"level":"error"' in l]
        if errors:
            raise RuntimeError("collector errors:\n  " + "\n  ".join(errors[:5]))
        out = {}
        for sig in records:
            f = tmp / "out" / f"{sig}.jsonl"
            out[sig] = [one for l in (f.read_text().splitlines() if f.exists() else [])
                        for one in explode(sig, json.loads(l))]
        return out


# --- kayıtlar -----------------------------------------------------------------------------------------------

def explode(sig, doc):
    """İsteği tek kayıtlık isteklere böler (metrikte tek veri noktası)."""
    top, item_key = TOP[sig], ITEM[sig]
    scope_key = top.replace("resource", "scope")
    for res in doc.get(top, []):
        for scope in res.get(scope_key, []):
            for item in scope.get(item_key, []):
                items = [item]
                if sig == "metrics":
                    items = [dict(item, **{t: dict(item[t], dataPoints=[dp])})
                             for t in ("sum", "gauge", "histogram", "exponentialHistogram", "summary")
                             if t in item for dp in item[t].get("dataPoints", [])]
                for it in items:
                    yield {top: [{**{k: v for k, v in res.items() if k != scope_key},
                                  scope_key: [{**{k: v for k, v in scope.items() if k != item_key},
                                               item_key: [it]}]}]}


def attrs(lst):
    return sorted((a["key"], json.dumps(a.get("value"), sort_keys=True)) for a in lst or [])


def key(sig, doc):
    """Kaydı çıktıda bulmak için: kuralların değiştirmediği alanlar."""
    res = doc[TOP[sig]][0]
    scope = res[TOP[sig].replace("resource", "scope")][0]
    item = scope[ITEM[sig]][0]
    if sig == "traces":
        return (sig, item["traceId"], item["spanId"])
    ra = attrs(res.get("resource", {}).get("attributes"))
    if sig == "logs":
        return (sig, json.dumps(ra), item.get("timeUnixNano"), item.get("observedTimeUnixNano"),
                item.get("traceId"), item.get("spanId"), item.get("severityNumber"))
    dp = next(item[t]["dataPoints"][0] for t in ("sum", "gauge", "histogram", "exponentialHistogram", "summary")
              if t in item)
    return (sig, json.dumps(ra), item["name"], dp.get("timeUnixNano"), dp.get("startTimeUnixNano"),
            json.dumps(attrs(dp.get("attributes"))))


def leaks(docs):
    """Her kayıt için sızıntı nedenleri (sızıntı CLI'ının bulguları + yeniden yazımın orijinal metni)."""
    with tempfile.TemporaryDirectory(prefix="collector_rules_scan_") as tmp:
        folder = Path(tmp) / "records"
        folder.mkdir()
        (folder / "records.jsonl").write_text("".join(json.dumps(d) + "\n" for d in docs))
        found = scan_model_view(folder)
    out = [[] for _ in docs]
    for f in found:
        if f.line is not None:
            out[f.line - 1].append(f"{f.rule}:{f.match}")
    for i, d in enumerate(docs):
        s = json.dumps(d, ensure_ascii=False)
        out[i] += [f"original:{o[:30]}" for o in ORIGINALS if o in s]
    return out


# --- test ---------------------------------------------------------------------------------------------------

def main():
    problems = []
    rows = [l.rstrip("\n").split("\t") for l in (FIXTURES / "rules.tsv").read_text().splitlines()]
    if rows[0] != ["section", "rule", "test", "sample", "note"]:
        raise SystemExit("error: rules.tsv header")
    rows = rows[1:]
    lines = {s: (FIXTURES / f).read_text().splitlines() for s, f in FILES.items()}
    docs = {f"{FILES[s]}:{i}": (s, json.loads(l)) for s in FILES for i, l in enumerate(lines[s], 1)}

    # kapsam
    in_config = {(sec, rule): n for n, sec, rule in RULES}
    if len(in_config) != len(RULES):
        problems.append("config has duplicate (section, rule)")
    listed = [(r[0], r[1]) for r in rows if r[2] != "clean"]
    for k in in_config:
        if listed.count(k) != 1:
            problems.append(f"coverage: config rule listed {listed.count(k)} times in rules.tsv: {k[0]}: {k[1]}")
    for k in listed:
        if k not in in_config:
            problems.append(f"coverage: rules.tsv rule not in config: {k[0]}: {k[1]}")
    malformed = []
    for sec, rule, test, sample, note in rows:
        if test not in TESTS or (test == "none") != (sample == "-") or (sample != "-" and sample not in docs):
            malformed.append(f"rules.tsv row malformed: {test} {sample} {rule[:60]}")
        if test == "none" and note in ("", "-"):
            malformed.append(f"rules.tsv none without reason: {rule[:60]}")
    if malformed:
        return problems + malformed
    used = {r[3] for r in rows if r[3] != "-"}
    for ref in docs:
        if ref not in used:
            problems.append(f"fixture line not referenced in rules.tsv: {ref}")

    # girdi (yalnız kayıt dosyaları; rules.tsv kural metinlerini taşır)
    with tempfile.TemporaryDirectory(prefix="collector_rules_input_") as tmp:
        folder = Path(tmp) / "input"
        folder.mkdir()
        for f in FILES.values():
            (folder / f).write_text((FIXTURES / f).read_text())
        try:
            n_input = len(scan_model_view(folder))
        except LeakageInputError as e:
            return [f"leakage CLI input error: {e}"]
    print(f"input: leakage findings {n_input} in {FIXTURES.relative_to(REPO)}/*.jsonl")
    if n_input == 0:
        problems.append("input: no leakage findings")
    refs = list(docs)
    input_leaks = dict(zip(refs, leaks([docs[r][1] for r in refs])))
    kind = {r[3]: r[2] for r in rows}
    for ref in refs:
        if kind[ref] == "clean" and input_leaks[ref]:
            problems.append(f"input: clean control leaky: {ref} {input_leaks[ref][:3]}")
        if kind[ref] != "clean" and not input_leaks[ref]:
            problems.append(f"input: sample not leaky: {ref}")

    def output_of(config_text):
        out = run_collector(config_text, lines)
        flat = [d for s in FILES for d in out[s]]
        return {key(s, d): d for s in FILES for d in out[s]}, flat

    def leaky_out(by_key, ref):
        s, d = docs[ref]
        o = by_key.get(key(s, d))
        return None if o is None else leaks([o])[0]

    # bütün kurallar açık
    full, flat = output_of(TEXT)
    full_leaks = [x for x in leaks(flat) if x] if flat else []
    print(f"full config: {len(flat)} records out, leaky {len(full_leaks)}")
    if full_leaks:
        problems.append(f"full config: {len(full_leaks)} leaky records in output, e.g. {full_leaks[0][:3]}")
    for ref in refs:
        if kind[ref] == "clean":
            s, d = docs[ref]
            if full.get(key(s, d)) != d:
                problems.append(f"full config: clean control dropped or changed: {ref}")

    # kural başına
    none_cfg = None
    for sec, rule, test, sample, note in rows:
        if (sec, rule) not in in_config:
            continue  # kapsam sorunu olarak yazıldı
        if test == "delete":
            by_key, _ = output_of(config_without({in_config[(sec, rule)]}))
            got = leaky_out(by_key, sample)
            ok = bool(got)
            print(f"  delete {'RED  ' if ok else 'green'} {sample:16s} {sec.split('/', 2)[-1]}: {rule[:70]}")
            if not ok:
                problems.append(f"delete: sample not leaky with rule removed: {sec}: {rule}")
        elif test == "alone":
            if none_cfg is None:
                none_cfg, _ = output_of(config_without({n for n, _, _ in RULES}))
            red = leaky_out(none_cfg, sample)
            alone, _ = output_of(config_without({n for n, _, _ in RULES if n != in_config[(sec, rule)]}))
            green = leaky_out(alone, sample)
            ok = bool(red) and not green
            print(f"  alone  {'ok   ' if ok else 'FAIL '} {sample:16s} {sec.split('/', 2)[-1]}: {rule[:70]}")
            if not red:
                problems.append(f"alone: sample not leaky without rules: {sec}: {rule}")
            if green:
                problems.append(f"alone: sample still leaky with only this rule: {sec}: {rule} {green[:3]}")
    counts = {t: sum(1 for r in rows if r[2] == t) for t in TESTS}
    print(f"rules: {len(RULES)} (delete {counts['delete']}, alone {counts['alone']}, none {counts['none']}); "
          f"clean controls {counts['clean']}")
    return problems


try:
    problems = main()
except (RuntimeError, subprocess.CalledProcessError) as e:
    print(f"error: {e}", file=sys.stderr)
    sys.exit(2)
if problems:
    print("FAIL")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)
print("PASS")
PYEOF
