"""P2b 4. madde (d): ajanın canlı modda uçtan uca koşusu (HANDOFF 2026-11-13, Eren onaylı plan); P2c 2. madde: bir
oynatmada birden çok model (HANDOFF 2026-11-14 "P2c kartı 1. madde: öneri", (d)).

    python tools/agent_live.py --model <etiket>[,<etiket>] --cases <id>,<id> [--root llm_cache]

Vaka başına: `storage_check.replay_case` (snapshot boş yeniden oynatma yığınına, D3 şartları, yığın açık) → her model
sırayla (verilen sırada; dev'de önce Gemini, sonra 4B) ajanı `LiveStore` ile çalıştırır (`methods/agent.py`, dosya
modundakiyle aynı istem ve ayarlar); her modelden sonra yığın konteynerlerinde ve yerel model sunucusunda
(`aiops-llm`) OOM / yeniden başlama denetimi → `down -v`. OOM kuralı P2a'daki gibi (HANDOFF 2026-11-11): oynatma
şartlarından biri kalırsa ya da bir model çalışırken OOM / yeniden başlama olursa o modelin kısmı bozuktur. Kısmı temiz
geçen modelin satırı yazılır; kısmı bozulan model(ler) ve yığın bozulduktan sonra sırası gelen model(ler) ikinci bir
oynatmada yeniden koşar; ikinci kez de olursa o model için satır yazılmaz, `live.json`'da "oynatılamadı". Ajan
çalışırken yığın belleği ve makinenin boş belleği (`MemAvailable`) 30 sn'de bir örneklenir.

Tek sunucu: Qwen tokenizer'ı (API modelinde sayım) ve 4B'nin kendisi aynı yerel sunucu (`methods.llm.TOKENIZER`);
bir kez açılır, bütün modellere `agent_method(..., base=...)` ile verilir. Başka yerel model reddedilir.

Kayıt biçimi dosya moduyla aynı (`evaluate.append_agent_case`): model başına `<root>/<UTC>-agent/` içinde `run.json`
(`settings.store` = `LiveStore`), `responses.jsonl` (+ `replay_dir`, `attempts_live`, `jaeger_peak_mib`),
`turns.jsonl`, `tool_outputs/`; ayrıca `live.json` (vaka başına o modelin deneme kayıtları). Yalnız `load_cases()`
vakaları (pilot, dev); test ve heldout reddedilir. Uyku ve kapak kilitleri altında kendini yeniden çalıştırır.
Çıkış kodu: 0 bütün vakalar her modelde oynatıldı, 1 en az biri oynatılamadı, 2 kullanım hatası.
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

import scenario_runner as sr  # noqa: E402
import storage_check as sc  # noqa: E402

from aiops_rca.cases import load_cases  # noqa: E402
from aiops_rca.evaluate import append_agent_case  # noqa: E402
from aiops_rca.llm_client import LOCAL_NAME, MODELS, LocalServer  # noqa: E402
from aiops_rca.methods.agent import agent_method  # noqa: E402
from aiops_rca.methods.llm import TOKENIZER  # noqa: E402
from aiops_rca.runs import new_run  # noqa: E402
from aiops_rca.store_live import LiveStore  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _mem_available_mib() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


def _sample(peaks: dict, low: dict, stop: threading.Event) -> None:
    while not stop.wait(30):
        for n, v in sc.mem_mib(sc.REPLAY_CONTAINERS).items():
            if v:
                peaks[n] = max(peaks.get(n, 0.0), v)
        free = _mem_available_mib()
        if free is not None:
            low["min"] = min(low.get("min", free), free)


def _open_server(stack: ExitStack) -> str:
    return stack.enter_context(LocalServer(MODELS[TOKENIZER].gguf)).base


def run(models: list[str], cases: list, root: Path) -> int:
    with ExitStack() as stack:
        base = _open_server(stack)
        asks, run_dirs, lives = {}, {}, {}
        for model in models:
            spec = MODELS[model]
            ask, settings = stack.enter_context(agent_method(model, LiveStore, base=base))
            asks[model] = ask
            run_dirs[model] = new_run("agent", ("pilot", "dev"), len(cases), root=root, model_id=spec.model_id,
                                      provider=spec.provider, temperature=0,
                                      settings={"model": model, "store": "LiveStore",
                                                "cases": [c.incident_id for c in cases], **settings})
            lives[model] = {}
        watched = [*sc.REPLAY_CONTAINERS, LOCAL_NAME]
        for case in cases:
            attempts = {m: [] for m in models}
            pending = list(models)
            for n in (1, 2):
                if not pending:
                    break
                res: dict = {}
                code = sc.replay_case(case.view, keep_up=True, result=res)
                base_rec = {"attempt": n, "replay_dir": str(res.get("dir")), "replay_valid": code == 0}
                recs = {m: dict(base_rec) for m in pending}
                for m in pending:
                    attempts[m].append(recs[m])
                outs: dict = {}
                try:
                    if code != 0:
                        for m in pending:
                            recs[m]["problem"] = "replay_case failed"
                        continue
                    broken = False
                    for m in pending:
                        rec = recs[m]
                        if broken:
                            rec["problem"] = "stack broken before this model"
                            continue
                        peaks, low, stop = {}, {}, threading.Event()
                        th = threading.Thread(target=_sample, args=(peaks, low, stop), daemon=True)
                        th.start()
                        t0 = time.monotonic()
                        try:
                            out = asks[m](case)
                        finally:
                            stop.set()
                        rec["agent_s"] = round(time.monotonic() - t0, 1)
                        rec["mem_peak_mib"] = {k: round(v, 1) for k, v in peaks.items()}
                        rec["mem_available_min_mib"] = low.get("min")
                        states = sc.container_states(watched)
                        rec["containers"] = states
                        rec["containers_ok"] = all(v and not v["oom_killed"] and v["restarts"] == 0
                                                   for v in states.values())
                        rec["end_reason"] = out["row"]["end_reason"]
                        if rec["containers_ok"]:
                            outs[m] = out
                        else:
                            broken = True
                finally:
                    p = sc.replay_compose(["down", "-v"], case.view)
                    left = [v for v in sc.volume_sizes() if v.startswith(sc.REPLAY_PROJECT + "_")]
                    for m in recs:
                        recs[m]["down_exit"] = p.returncode
                        recs[m]["replay_volumes_left"] = left
                replay_peak = ((res.get("rec") or {}).get("mem_peak_mib") or {}).get("otel-replay-jaeger-1")
                for m in list(pending):
                    rec = recs[m]
                    if m in outs and not rec["replay_volumes_left"]:
                        append_agent_case(run_dirs[m], case.incident_id, outs[m], replay_dir=rec["replay_dir"],
                                          attempts_live=n,
                                          jaeger_peak_mib={"replay": replay_peak,
                                                           "agent": rec["mem_peak_mib"].get("otel-replay-jaeger-1")})
                        rec["valid"] = True
                        pending.remove(m)
                    else:
                        rec["valid"] = False
            for m in models:
                lives[m][case.incident_id] = {"replayed": attempts[m][-1].get("valid", False),
                                              "attempts": attempts[m]}
                (run_dirs[m] / "live.json").write_text(json.dumps(lives[m], ensure_ascii=False, indent=1) + "\n")
                print(f"{m} {case.incident_id}: {lives[m][case.incident_id]['replayed']} "
                      f"{attempts[m][-1].get('end_reason')} ({len(attempts[m])} attempt(s))", flush=True)
    for m in models:
        print(run_dirs[m])
    return 0 if all(v["replayed"] for live in lives.values() for v in live.values()) else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="agent_live.py", description="P2b / P2c: agent in live mode (replay stack)")
    ap.add_argument("--model", required=True,
                    help="comma-separated model labels, run in this order on each replay (e.g. "
                         "gemini-3.5-flash-lite,qwen3.5-4b)")
    ap.add_argument("--cases", required=True, help="comma-separated incident ids (pilot / dev only)")
    ap.add_argument("--root", type=Path, default=REPO / "llm_cache")
    args = ap.parse_args(argv)
    models = [x for x in args.model.split(",") if x]
    bad_models = [m for m in models if m not in MODELS
                  or (MODELS[m].provider == "local" and m != TOKENIZER)]
    if bad_models or not models or len(set(models)) != len(models):
        print(f"error: models must be distinct labels from MODELS; the only local model is {TOKENIZER}: "
              f"{bad_models or models}", file=sys.stderr)
        return 2
    known = {c.incident_id: c for c in load_cases()}
    ids = [x for x in args.cases.split(",") if x]
    bad = [i for i in ids if i not in known]
    if bad or not ids:
        print(f"error: not valid pilot/dev cases: {bad or ids}", file=sys.stderr)
        return 2
    if os.environ.get("SCENARIO_RUNNER_INHIBITED") != "1":
        env = dict(os.environ, SCENARIO_RUNNER_INHIBITED="1")
        cmd = [*sr.GNOME_INHIBIT, "systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
               "--who=aiops_rca agent_live", "--why=storage card P2b agent live", sys.executable, *sys.argv]
        return subprocess.run(cmd, env=env).returncode  # neden metni scenario_runner.inhibited()'in tanıdığı ifadeyle
    return run(models, [known[i] for i in ids], args.root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
