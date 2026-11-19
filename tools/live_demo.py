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
kayda girer. Kayıt `DEMO_RUNS/<UTC>-demo/`: `run.json` (korumalar, taban, enjeksiyon ve geri alma durumu, bellek,
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
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import incident_checks as ic  # noqa: E402
import scenario_runner as sr  # noqa: E402

from aiops_rca.cases import Case  # noqa: E402
from aiops_rca.evaluate import append_agent_case  # noqa: E402
from aiops_rca.leakage import scan_model_view  # noqa: E402
from aiops_rca.llm_client import MODELS, LocalServer  # noqa: E402
from aiops_rca.methods.agent import agent_method  # noqa: E402
from aiops_rca.methods.llm import TOKENIZER  # noqa: E402
from aiops_rca.signals import Window, service_rows, summarize  # noqa: E402
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
INHIBIT_WHY = "storage card live demo"  # `scenario_runner.inhibited()`'in tanıdığı neden metni


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
    rec["baseline"] = baseline(sr.utc_ns())
    if spec["kind"] == "flag":
        before = sr.resolve(sr.BY_ID[spec["scenario"]])
        if not isinstance(before, dict) or before.get("variant") != "off":
            rec["baseline"]["problems"].append(f"flag not off before injection: {before}")
    if rec["baseline"]["problems"]:
        rec["result"] = "baseline: " + "; ".join(rec["baseline"]["problems"])
        save()
        return 2

    code, state, low, stop = 0, None, {}, threading.Event()
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
        write_window(d, alarm - NORMAL_S * 10**9, agent_start)
        case = Case(incident_id=f"demo-{stamp}", view=d, alarm_ns=alarm)
        factory = store_factory or (lambda c: LiveStore(c, ends=MAIN_ENDS))
        with ExitStack() as stack:
            if base is None:
                base = stack.enter_context(LocalServer(MODELS[TOKENIZER].gguf)).base
            ask, settings = stack.enter_context(agent_method(model, factory, base=base))
            rec["agent_settings"] = settings
            out = ask(case)
        append_agent_case(d, case.incident_id, out)
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
    rec["answer"] = spec["answer"]  # gerçek cevap ajandan sonra
    outputs = d / "tool_outputs"
    findings = scan_model_view(outputs) if outputs.is_dir() and any(outputs.iterdir()) else []
    rec["leakage"] = {"findings": len(findings), "first": [str(f) for f in findings[:5]]}
    if findings:
        rec["result"] = f"leakage: {len(findings)} finding(s); demo stopped"
        save()
        return 3
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
