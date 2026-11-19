"""Canlı demo (canlı demo kartı, HANDOFF 2026-11-18; öneri ve düzeltmeler HANDOFF 2026-11-19): hata enjekte et →
ajan ana izleme yığınından araştırır → kayıt → hata geri alınır.

    python tools/live_demo.py run --fault <hata> --target <servis> [--model <etiket>]
    python tools/live_demo.py run --scenario <flag senaryosu> [--model <etiket>]
    python tools/live_demo.py list                      # kabul listesi (hatalar ve senaryolar)

Demo yığını açık olmalı (`tools/otel_demo.sh up`, en az `NORMAL_S` normal dönem): komut yığını açmaz, kapatmaz.
Sıra: korumalar (`scenario_runner.guards()`; demo konteynerleri burada beklenir, yalnız hata kalıntısı sorun) → taban
sağlık (23 konteyner, flagd zamanlayıcısı durmuş, senaryonun flag'i kapalı, frontend p95 koşucunun ölçüsüyle; dosya)
→ enjeksiyon (`scenario_runner.apply_fault` / `set_flag`; kopya yok); **alarm anı = enjeksiyon başlangıcı** →
`SYMPTOM_S` belirti (DECISIONS 2026-11-19: 10 dk) → ajan (`methods.agent.agent_method`, `LiveStore(case,
ends=MAIN_ENDS)`; istem ve sınırlar P2'deki gibi donmuş) → geri alma ve doğrulama (her durumda) → ajanın gördüğü araç
çıktılarında sızıntı taraması (`leakage.scan_model_view`; bulgu varsa demo durur).

Ajanın `Case`'i: kimlik `demo-<UTC>`, görünüm klasörü demo klasörü (yalnız `window.json`: [alarm − `NORMAL_S`, ajan
başlangıcı)), alarm anı. Ajan gerçek cevabı görmez; gerçek cevap (`INFRA_ANSWERS` / `SCENARIOS`) yalnız ajandan sonra
kayda girer. Kayıt `DEMO_RUNS/<UTC>-demo/`: `report.md` / `report.json` (sızıntı yoksa), `run.json` (korumalar, taban, enjeksiyon ve geri alma durumu, bellek,
sızıntı, sonuç, gerçek cevap), ajan kaydı (`evaluate.append_agent_case`: `responses.jsonl`, `turns.jsonl`,
`tool_outputs/`). Git dışı; `incidents/`, `snapshots/`, `eval_responses/`'e yazılmaz.

Çıkış: 0 demo bitti (geri alma doğrulandı, sızıntı 0); 1 demo bitti ama geri alma doğrulanmadı ya da ajan hata
verdi; 2 kullanım hatası, korumalar ya da taban (enjeksiyon yapılmadı); 3 sızıntı bulgusu.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import incident_checks as ic  # noqa: E402
import scenario_runner as sr  # noqa: E402

from aiops_rca import query  # noqa: E402
from aiops_rca.cases import Case  # noqa: E402
from aiops_rca.evaluate import append_agent_case  # noqa: E402
from aiops_rca.leakage import scan_model_view  # noqa: E402
from aiops_rca.llm_client import MODELS, LocalServer  # noqa: E402
from aiops_rca.methods.agent import agent_method  # noqa: E402
from aiops_rca.methods.llm import TOKENIZER  # noqa: E402
from aiops_rca.scoring import evidence, match_service  # noqa: E402
from aiops_rca.signals import DB_SERVICES, SEVERITY_WARN, Window, normalize, service_rows, signals, summarize  # noqa: E402,E501
from aiops_rca.store_live import MAIN_ENDS, LiveStore  # noqa: E402

DEMO_RUNS = Path.home() / "cerebrum2" / "demo_runs"
NORMAL_S = sr.NORMAL_S  # ajanın penceresi alarmdan bu kadar önce başlar (P2 vakalarında normal dönem 600–840 sn)
SYMPTOM_S = sr.FLAG_S  # DECISIONS 2026-11-19: belirti süresi 10 dk (P2'nin hata dönemi)
DEMO_MODELS = ("gemini-3.5-flash-lite", "qwen3.5-4b")  # DECISIONS 2026-11-18: seçilebilir, varsayılan Gemini
DEFAULT_MODEL = DEMO_MODELS[0]
# Altyapı hatalarının parametreleri V3 vaka listelerinden (incident_lists/v3_*.json); çiftler INFRA_ANSWERS'tan.
INFRA_PARAMS = {("containerPause", "cart"): "on", ("containerPause", "quote"): "on",
                ("containerStop", "currency"): "on", ("containerStop", "recommendation"): "on",
                ("cpuThrottle", "product-catalog"): "0.09", ("cpuThrottle", "recommendation"): "0.03",
                ("networkDelay", "cart"): "50ms", ("networkDelay", "quote"): "50ms",
                ("packetLoss", "currency"): "10%", ("packetLoss", "shipping"): "10%"}
SAMPLE_S = 30
INHIBIT_WHY = "storage card live demo"
REPO = Path(__file__).resolve().parents[1]
DASHBOARD = REPO / "deploy" / "otel-demo" / "grafana" / "aiops-demo.json"
GRAFANA = "http://127.0.0.1:8080/grafana"  # frontend-proxy üzerinden (Grafana'nın kendi portu kapalı)  # `scenario_runner.inhibited()`'in tanıdığı neden metni


def faults() -> dict[str, dict]:
    """Kabul listesi: anahtar → {kind, ..., answer}. Altyapı `<hata>:<hedef>`, flag `scenario_id`."""
    out = {}
    for a in sr.INFRA_ANSWERS:
        key = (a["fault"], a["target"])
        if key in INFRA_PARAMS:
            out[f"{a['fault']}:{a['target']}"] = {
                "kind": "infra", "fault": a["fault"], "target": a["target"], "param": INFRA_PARAMS[key],
                "answer": {"root_cause_service": a["target"], "fault_type": sr.INFRA_FAULTS[a["fault"]]["fault_type"],
                           "propagation_path": a["propagation_path"], "categories": a["categories"]}}
    for sid, s in sr.BY_ID.items():
        if "fault_type" not in s:  # gürültü katmanı (loadGeneratorFloodHomepage) hata değil
            continue
        out[sid] = {"kind": "flag", "scenario": sid,
                    "answer": {"root_cause_service": s["root"], "fault_type": s["fault_type"],
                               "propagation_path": s["propagation_path"], "categories": s["categories"]}}
    return out


def demo_guards() -> dict:
    """`sr.guards()`; demo konteynerleri burada beklenir. Sorun yalnız hata kalıntısı: duran, dondurulmuş ya da CPU
    sınırlı demo konteyneri ya da `aiops-netem`."""
    g = sr.guards()
    problems = [p for p in g["problems"] if not p.startswith("leftovers from a previous run")]
    left = g.get("leftovers") or []
    bad = [c["name"] for c in left if c["name"] == "aiops-netem" or c["paused"] or c["nano_cpus"]
           or c["state"] != "running"]
    if bad:
        problems.append(f"fault leftovers: {', '.join(bad)}")
    return {**g, "problems": problems}


def baseline(now_ns: int) -> dict:
    """Taban sağlık (koşucunun ölçüsü): son `NORMAL_S`'nin dosya verisinden frontend p95 ≤ eşik; konteyner sayısı;
    flagd zamanlayıcısı."""
    recent = [f for f in sorted((sr.TELEMETRY / "filtered").glob("*.jsonl"))
              if f.stat().st_mtime_ns >= now_ns - (NORMAL_S + 60) * 10**9]
    rows = service_rows(summarize(recent, Window(now_ns))[0]) if recent else {}
    check = ic.baseline_check(rows)
    n, sched = sr.container_count(), sr.scheduler_state()
    problems = []
    if n != sr.CONTAINERS:
        problems.append(f"container count {n}, want {sr.CONTAINERS}")
    if sched != "stopped":
        problems.append(f"flagd-ui scheduler {sched}")
    if not check["pass"]:
        problems.append(f"frontend p95 {check['frontend_p95_ms']} ms > {check['threshold_ms']}")
    return {**check, "containers": n, "scheduler": sched, "measured_at": sr.iso(now_ns), "problems": problems}


def _mem_sample(low: dict, stop: threading.Event) -> None:
    """`MemAvailable` en düşüğü ve takas kullanımının tepesi (MiB; planlama 2026-11-19, 4. düzeltme)."""
    while True:
        info = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) / 1024
        except (OSError, ValueError):
            pass
        if "MemAvailable" in info:
            low["mem_available_min_mib"] = round(min(low.get("mem_available_min_mib", 1e12), info["MemAvailable"]), 1)
        if "SwapTotal" in info and "SwapFree" in info:
            used = info["SwapTotal"] - info["SwapFree"]
            low["swap_used_peak_mib"] = round(max(low.get("swap_used_peak_mib", 0.0), used), 1)
        if stop.wait(SAMPLE_S):
            return


def inject(spec: dict) -> dict:
    if spec["kind"] == "infra":
        return {"kind": "infra", **sr.apply_fault(spec["fault"], spec["target"], spec["param"])}
    s = sr.BY_ID[spec["scenario"]]
    before = sr.resolve(s)
    written, verified, answer = sr.set_flag(s, s["variant"])
    return {"kind": "flag", "scenario": spec["scenario"], "before": before, "applied_ok": verified is not None,
            "written": sr.iso(written), "verified_at": sr.iso(verified), "answer": answer}


def revert(spec: dict, state: dict) -> dict:
    if spec["kind"] == "infra":
        return {"kind": "infra", **sr.revert_fault({k: v for k, v in state.items() if k != "kind"})}
    s = sr.BY_ID[spec["scenario"]]
    written, verified, answer = sr.set_flag(s, "off")
    return {**state, "reverted_written": sr.iso(written), "reverted_verified_at": sr.iso(verified),
            "reverted_answer": answer, "verified": verified is not None}


# --- Sonraki adım ve kanıt (planlama 2026-11-19, 1. düzeltme: girdi ajanın çağırdığı araç değil, verinin kendisi) ---

# (kural, koşul, öneri); ilk eşleşen. Koşul 1. adayın canlı veriden kurulan satırında yanan sinyallere bakar
# (`signals.signals`, güç ≥ 1; P1 tanımı). Metinler HANDOFF 2026-11-19 (1. madde önerisi (d)).
NEXT_STEPS = (
    ("database", "aday veritabanı", "Veritabanı bağlantısını ve kaynaklarını kontrol edin."),
    ("resource", "CPU ya da bellek sinyali", "Konteynerin kaynak sınırlarını ve son değişikliklerini kontrol edin."),
    ("error", "hata oranı ya da yeni WARN+ log sinyali",
     "Servisin hata mesajını ve son ayar / dağıtım değişikliğini inceleyin."),
    ("latency", "gecikme sinyali (p95)", "Servisin bağımlılıklarına giden çağrıların süresine bakın; ağ ve kaynak."),
    ("down", "istek düşüşü ya da alarm sonrası veri yok",
     "Konteyner çalışıyor mu, sağlık durumu ve yeniden başlama sayısı?"),
    ("human", "eşleşme yok", "İnsan incelemesi."),
)
FIRE = 1.0  # signals.signals gücü ≥ 1: sinyal yandı


def _one(store, service: str, metric: str, lo: int, hi: int):
    """[lo, hi) aralığında tek kova değeri."""
    step = max(1, (hi - lo) // 10**9)
    pts = query.metric_series(store, service, metric, lo, lo + step * 10**9, step_s=step)["points"]
    return pts[0][1] if pts else None


def candidate_row(store, service: str, alarm_ns: int, end_ns: int) -> dict:
    """1. adayın satırı (`signals.signals` alan adları): istek, hata oranı, p95, CPU, bellek; önce = [alarm −
    `NORMAL_S`, alarm), sonra = [alarm, `end_ns`); yeni WARN+ log mesajı (önce 0, sonra en çok)."""
    lo = alarm_ns - NORMAL_S * 10**9
    row = {}
    for metric, key in (("requests", "requests"), ("error_rate", "error_rate"), ("p95_ms", "p95_ms"),
                        ("cpu_pct", "cpu_pct"), ("mem_mb", "mem_mb")):
        for side, (a, b) in (("before", (lo, alarm_ns)), ("after", (alarm_ns, end_ns))):
            row[f"{key}_{side}"] = _one(store, service, metric, a, b)
    counts = {}
    for side, (a, b) in (("before", (lo, alarm_ns)), ("after", (alarm_ns, end_ns))):
        for r in query.search_logs(store, a, b, service, min_severity=SEVERITY_WARN, limit=None)["logs"]:
            counts.setdefault(normalize(r["message"]), {"before": 0, "after": 0})[side] += 1
    new = [(c["after"], m) for m, c in counts.items() if c["before"] == 0 and c["after"] > 0]
    row["new_warn_top"] = max(new) if new else (0, None)
    return row


def next_step(service: str | None, row: dict | None) -> dict:
    """`NEXT_STEPS`'ten ilk eşleşen satır ve dayandığı sinyaller."""
    def pick(rule: str, fired: dict) -> dict:
        _, cond, text = next(r for r in NEXT_STEPS if r[0] == rule)
        return {"rule": rule, "condition": cond, "text": text, "signals": fired}
    if service is None or row is None:
        return pick("human", {})
    if service in DB_SERVICES:
        return pick("database", {})
    sig, _ = signals(row, only_resources=False)
    fired = {k: v for k, v in sig.items() if v["strength"] >= FIRE}
    for rule, keys in (("resource", ("cpu_pct", "mem_mb")), ("error", ("error_rate", "new_warn_log")),
                       ("latency", ("p95_ms",))):
        hit = {k: fired[k] for k in keys if k in fired}
        if hit:
            return pick(rule, hit)
    if "request_drop" in fired or not row.get("requests_after"):
        return pick("down", {k: fired[k] for k in ("request_drop",) if k in fired})
    return pick("human", {})


def assess(store, answer: dict | None, alarm_ns: int, end_ns: int) -> dict:
    """Ajandan sonra: 1. adayın eşlenmiş adı, satırı, sonraki adım, kanıt geçerliliği (P1'in `scoring.evidence`'ı;
    kenarlar canlı izlerin çağrı grafiğinden, pencere [alarm − `NORMAL_S`, `end_ns`))."""
    names = store.names()
    known = set().union(*names.values())
    if not answer or not answer.get("candidates"):
        return {"candidate": None, "matched": None, "row": None, "next_step": next_step(None, None),
                "evidence": None}
    first = answer["candidates"][0]
    matched = match_service(first["service"], known)
    row = candidate_row(store, matched, alarm_ns, end_ns) if matched and matched not in DB_SERVICES else None
    deps = query.service_dependencies(store, alarm_ns - NORMAL_S * 10**9, end_ns)["edges"]
    edges = Counter({(e["caller"], e["callee"]): e["calls"] for e in deps})
    ev = [evidence(tuple(c["evidence_path"]), edges, known) for c in answer["candidates"]]
    return {"candidate": first["service"], "matched": matched, "row": row,
            "next_step": next_step(matched, row) if matched else next_step(None, None), "evidence": ev}


# --- Rapor (1. madde önerisi (c)) ---

NOTE = "Ajan önerir, uygulamaz: bu rapor bir araştırma özetidir; hiçbir değişiklik otomatik yapılmadı."
OUTPUT_LINES = 3


def report(rec: dict, out: dict) -> dict:
    """Rapor alanları: adaylar (kanıt yolu, gerekçe, kanıt geçerliliği), araç çağrıları (gerekçe, çağrı, çıktının ilk
    satırları), sonraki adım (dayandığı sinyaller), süre ve token, not; en sonda ayrı ve etiketli gerçek cevap."""
    row, a = out["row"], rec.get("assessment") or {}
    ev = a.get("evidence") or []
    answer = row["answer"] if row["schema_valid"] else None
    cands = [{"rank": i + 1, "service": c["service"], "confidence": c["confidence"],
              "evidence_path": c["evidence_path"], "rationale": c["rationale"],
              "evidence_valid": ev[i]["valid"] if i < len(ev) else None}
             for i, c in enumerate((answer or {}).get("candidates") or [])]
    outputs = {o.get("turn"): o for o in out["tool_outputs"]}
    calls = []
    for i, t in enumerate(x for x in out["turns"] if x.get("kind") == "action"):
        act = t.get("action") or {}
        o = outputs.get(i) or {}
        calls.append({"turn": i, "reason": act.get("reason"), "call": t.get("call"),
                      "output_head": (o.get("text") or "").splitlines()[:OUTPUT_LINES]})
    return {"demo": rec["demo"], "model": rec["model"], "alarm_utc": rec["times_utc"].get("alarm"),
            "agent_start_utc": rec["times_utc"].get("agent_start"), "unsure": (answer or {}).get("unsure"),
            "end_reason": row["end_reason"], "candidates": cands, "tool_calls": calls,
            "next_step": a.get("next_step"), "first_candidate_matched": a.get("matched"),
            "duration_s": row["duration_s"], "tokens": row["tokens"], "note": NOTE,
            "revert_verified": (rec.get("revert") or {}).get("verified"),
            "grafana": rec.get("grafana_url"),
            "true_answer_after_agent": rec["answer"]}


def report_md(r: dict) -> str:
    out = [f"# Canlı demo raporu: {r['demo']}", "",
           f"Model `{r['model']}`; alarm (enjeksiyon) {r['alarm_utc']}; ajan başlangıcı {r['agent_start_utc']}; "
           f"bitiş `{r['end_reason']}`; süre {r['duration_s']} sn; token {r['tokens']}.", "",
           f"Grafana panosu (ajanın penceresi): {r.get('grafana')}", "", f"> {r['note']}", "",
           "## Adaylar", ""]
    if not r["candidates"]:
        out.append("Geçerli cevap yok.")
    else:
        out += ["| # | Servis | Güven | Kanıt yolu | Kanıt geçerli | Gerekçe |", "|---|---|---|---|---|---|"]
        for c in r["candidates"]:
            out.append(f"| {c['rank']} | {c['service']} | {c['confidence']} | {' → '.join(c['evidence_path'])} | "
                       f"{c['evidence_valid']} | {c['rationale']} |")
        out += ["", f"Emin değil: {r['unsure']}."]
    ns = r.get("next_step") or {}
    out += ["", "## Sonraki adım", "", f"**{ns.get('text', '-')}** (kural `{ns.get('rule', '-')}`: "
            f"{ns.get('condition', '-')}; 1. aday `{r['first_candidate_matched']}`)."]
    for k, v in (ns.get("signals") or {}).items():
        out.append(f"- {k}: önce {v.get('before')}, sonra {v.get('after')}, güç {v.get('strength')}")
    out += ["", "## Araç çağrıları", ""]
    for c in r["tool_calls"]:
        out += [f"{c['turn'] + 1}. **{c['call']}**: {c['reason']}"]
        out += [f"   `{line}`" for line in c["output_head"]]
    t = r["true_answer_after_agent"]
    out += ["", "## Gerçek cevap (ajandan sonra eklendi; ajan görmedi)", "",
            f"Kök `{t['root_cause_service']}`, hata türü `{t['fault_type']}`, kategoriler {t['categories']}, yol "
            + ", ".join(" → ".join(e) for e in t["propagation_path"]) + ".",
            f"Hata geri alındı ve doğrulandı: {r['revert_verified']}.", ""]
    return "\n".join(out)


def load_dashboard() -> dict:
    """Panoyu Grafana API'sine yükler (üzerine yazar; Eren kararı 2026-11-19, seçenek A: upstream'e ve compose'a
    dokunmadan). Döner: kayıt (uid, durum ya da hata)."""
    dash = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    try:
        r = sr.http("POST", f"{GRAFANA}/api/dashboards/db", {"dashboard": {**dash, "id": None}, "overwrite": True})
    except Exception as e:  # noqa: BLE001  pano yüklenemezse demo sürer; kayda (kabul ölçütü ayrıca bakar)
        return {"uid": dash["uid"], "ok": False, "error": f"{type(e).__name__}: {e}"}
    ok = isinstance(r, dict) and r.get("status") == "success"
    return {"uid": dash["uid"], "ok": ok, "response": r if not ok else {"status": r["status"], "url": r.get("url")}}


def dashboard_url(lo_ns: int, hi_ns: int) -> str:
    uid = json.loads(DASHBOARD.read_text(encoding="utf-8"))["uid"]
    return f"{GRAFANA}/d/{uid}?from={lo_ns // 10**6}&to={hi_ns // 10**6}"


def write_window(view: Path, lo_ns: int, hi_ns: int) -> None:
    fmt = lambda ns: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ns // 10**9))  # noqa: E731
    (view / "window.json").write_text(json.dumps({"start": fmt(lo_ns), "end": fmt(hi_ns)}) + "\n")


def run(spec_key: str, model: str, *, root: Path = DEMO_RUNS, store_factory=None, base: str | None = None,
        sleep=time.sleep) -> int:
    spec = faults()[spec_key]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    d = root / f"{stamp}-demo"
    d.mkdir(parents=True)
    rec: dict = {"demo": spec_key, "model": model, "spec": {k: v for k, v in spec.items() if k != "answer"},
                 "ends": MAIN_ENDS, "normal_s": NORMAL_S, "symptom_s": SYMPTOM_S, "times_utc": {}, "result": None}

    def save() -> None:
        (d / "run.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")

    def mark(key: str) -> int:
        ns = sr.utc_ns()
        rec["times_utc"][key] = sr.iso(ns)
        save()
        return ns

    rec["guards"] = demo_guards()
    if rec["guards"]["problems"]:
        rec["result"] = "guards: " + "; ".join(rec["guards"]["problems"])
        save()
        return 2
    rec["dashboard"] = load_dashboard()
    rec["baseline"] = baseline(sr.utc_ns())
    if spec["kind"] == "flag":
        before = sr.resolve(sr.BY_ID[spec["scenario"]])
        if not isinstance(before, dict) or before.get("variant") != "off":
            rec["baseline"]["problems"].append(f"flag not off before injection: {before}")
    if rec["baseline"]["problems"]:
        rec["result"] = "baseline: " + "; ".join(rec["baseline"]["problems"])
        save()
        return 2

    code, state, low, stop, agent_out = 0, None, {}, threading.Event(), None
    factory = store_factory or (lambda c: LiveStore(c, ends=MAIN_ENDS))
    sampler = threading.Thread(target=_mem_sample, args=(low, stop), daemon=True)
    sampler.start()
    try:
        alarm = mark("alarm")
        state = inject(spec)
        rec["injection"] = state
        save()
        if not state.get("applied_ok"):
            raise RuntimeError("injection not applied")
        sleep(SYMPTOM_S)
        agent_start = mark("agent_start")
        rec["grafana_url"] = dashboard_url(alarm - NORMAL_S * 10**9, agent_start)
        write_window(d, alarm - NORMAL_S * 10**9, agent_start)
        case = Case(incident_id=f"demo-{stamp}", view=d, alarm_ns=alarm)
        with ExitStack() as stack:
            if base is None:
                base = stack.enter_context(LocalServer(MODELS[TOKENIZER].gguf)).base
            ask, settings = stack.enter_context(agent_method(model, factory, base=base))
            rec["agent_settings"] = settings
            out = ask(case)
        append_agent_case(d, case.incident_id, out)
        agent_out = out
        rec["agent"] = {"end_reason": out["row"]["end_reason"], "schema_valid": out["row"]["schema_valid"],
                        "n_tool_calls": out["row"]["n_tool_calls"], "duration_s": out["row"]["duration_s"],
                        "tokens": out["row"]["tokens"]}
        mark("agent_end")
    except Exception as e:  # noqa: BLE001  her durumda geri alınır; hata kayda
        rec["error"] = f"{type(e).__name__}: {e}"
        code = 1
    finally:
        # Altyapıda hedef önceden okunamadıysa (`before` yok) hiçbir şey uygulanmadı; flag her durumda kapatılır.
        if state is not None and (spec["kind"] == "flag" or state.get("before") is not None):
            try:
                rec["revert"] = revert(spec, state)
            except Exception as e:  # noqa: BLE001  geri alma hatası kayda; demo "doğrulanmadı" biter
                rec["revert"] = {"error": f"{type(e).__name__}: {e}", "verified": False}
            mark("reverted")
            if not rec["revert"].get("verified"):
                code = 1
        stop.set()
        sampler.join(timeout=5)
        rec["memory"] = low
        save()
    if agent_out is not None:
        try:
            ans = agent_out["row"]["answer"] if agent_out["row"]["schema_valid"] else None
            rec["assessment"] = assess(factory(case), ans, case.alarm_ns, agent_start)
        except Exception as e:  # noqa: BLE001  değerlendirme hatası kayda; demo sonucu değişmez
            rec["assessment"] = {"error": f"{type(e).__name__}: {e}"}
    rec["answer"] = spec["answer"]  # gerçek cevap ajandan sonra
    outputs = d / "tool_outputs"
    findings = scan_model_view(outputs) if outputs.is_dir() and any(outputs.iterdir()) else []
    rec["leakage"] = {"findings": len(findings), "first": [str(f) for f in findings[:5]]}
    if findings:
        rec["result"] = f"leakage: {len(findings)} finding(s); demo stopped"
        save()
        return 3
    if agent_out is not None:
        r = report(rec, agent_out)
        (d / "report.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n")
        (d / "report.md").write_text(report_md(r), encoding="utf-8")
    rec["result"] = "ok" if code == 0 else "finished with problems"
    save()
    print(d)
    return code


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="live_demo.py", description="live demo: inject a fault, run the agent live")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("--fault")
    r.add_argument("--target")
    r.add_argument("--scenario")
    r.add_argument("--model", default=DEFAULT_MODEL, choices=DEMO_MODELS)
    args = ap.parse_args(argv)
    if args.cmd == "list":
        for k, v in faults().items():
            print(k, v["kind"])
        return 0
    key = args.scenario if args.scenario else f"{args.fault}:{args.target}"
    if (args.scenario is None) == (args.fault is None) or key not in faults():
        print(f"error: give --scenario or --fault/--target from `list`; not accepted: {key}", file=sys.stderr)
        return 2
    if os.environ.get("SCENARIO_RUNNER_INHIBITED") != "1":
        env = dict(os.environ, SCENARIO_RUNNER_INHIBITED="1")
        cmd = [*sr.GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
               "--who=aiops_rca live_demo", f"--why={INHIBIT_WHY}", sys.executable, *sys.argv]
        return subprocess.run(cmd, env=env).returncode
    return run(key, args.model)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
