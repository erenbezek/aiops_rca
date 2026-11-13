"""P2b 4. madde (d): ajanın canlı modda uçtan uca koşusu (HANDOFF 2026-11-13, Eren onaylı plan).

    python tools/agent_live.py --model <etiket> --cases <id>,<id> [--root llm_cache]

Vaka başına: `storage_check.replay_case` (snapshot boş yeniden oynatma yığınına, D3 şartları, yığın açık) → ajan
`LiveStore` ile (`methods/agent.py`, dosya modundakiyle aynı istem ve ayarlar) → yığın konteynerlerinde OOM / yeniden
başlama denetimi → `down -v`. OOM kuralı P2a'daki gibi (HANDOFF 2026-11-11): oynatma şartlarından biri kalırsa ya da
ajan çalışırken yığında OOM / yeniden başlama olursa vaka bir kez baştan; ikinci kez de olursa satır yazılmaz,
`live.json`'da "oynatılamadı". Ajan çalışırken yığın belleği 30 sn'de bir örneklenir, tepe satıra.

Kayıt biçimi dosya moduyla aynı (`evaluate.append_agent_case`): `<root>/<UTC>-agent/` içinde `run.json`
(`settings.store` = `LiveStore`), `responses.jsonl` (+ `replay_dir`, `attempts_live`, `jaeger_peak_mib`),
`turns.jsonl`, `tool_outputs/`; ayrıca `live.json` (vaka başına deneme kayıtları). Yalnız `load_cases()` vakaları
(pilot, dev); test ve heldout reddedilir. Uyku ve kapak kilitleri altında kendini yeniden çalıştırır.
Çıkış kodu: 0 bütün vakalar oynatıldı, 1 en az biri oynatılamadı, 2 kullanım hatası.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scenario_runner as sr  # noqa: E402
import storage_check as sc  # noqa: E402

from aiops_rca.cases import load_cases  # noqa: E402
from aiops_rca.evaluate import append_agent_case  # noqa: E402
from aiops_rca.llm_client import MODELS  # noqa: E402
from aiops_rca.methods.agent import agent_method  # noqa: E402
from aiops_rca.runs import new_run  # noqa: E402
from aiops_rca.store_live import LiveStore  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _sample(peaks: dict, stop: threading.Event) -> None:
    while not stop.wait(30):
        for n, v in sc.mem_mib(sc.REPLAY_CONTAINERS).items():
            if v:
                peaks[n] = max(peaks.get(n, 0.0), v)


def run(model: str, cases: list, root: Path) -> int:
    spec = MODELS[model]
    with agent_method(model, LiveStore) as (ask, settings):
        run_dir = new_run("agent", ("pilot", "dev"), len(cases), root=root, model_id=spec.model_id,
                          provider=spec.provider, temperature=0,
                          settings={"model": model, "store": "LiveStore", "cases": [c.incident_id for c in cases],
                                    **settings})
        live = {}
        for case in cases:
            attempts = []
            for n in (1, 2):
                res: dict = {}
                code = sc.replay_case(case.view, keep_up=True, result=res)
                rec = {"attempt": n, "replay_dir": str(res.get("dir")), "replay_valid": code == 0}
                attempts.append(rec)
                out = None
                try:
                    if code != 0:
                        rec["problem"] = "replay_case failed"
                        continue
                    peaks, stop = {}, threading.Event()
                    th = threading.Thread(target=_sample, args=(peaks, stop), daemon=True)
                    th.start()
                    t0 = time.monotonic()
                    out = ask(case)
                    stop.set()
                    rec["agent_s"] = round(time.monotonic() - t0, 1)
                    rec["mem_peak_mib"] = {k: round(v, 1) for k, v in peaks.items()}
                    states = sc.container_states(sc.REPLAY_CONTAINERS)
                    rec["containers_ok"] = all(v and not v["oom_killed"] and v["restarts"] == 0
                                               for v in states.values())
                    rec["end_reason"] = out["row"]["end_reason"]
                finally:
                    p = sc.replay_compose(["down", "-v"], case.view)
                    rec["down_exit"] = p.returncode
                    rec["replay_volumes_left"] = [v for v in sc.volume_sizes() if v.startswith(sc.REPLAY_PROJECT + "_")]
                if out is not None and rec["containers_ok"] and not rec["replay_volumes_left"]:
                    replay_peak = ((res.get("rec") or {}).get("mem_peak_mib") or {}).get("otel-replay-jaeger-1")
                    append_agent_case(run_dir, case.incident_id, out, replay_dir=rec["replay_dir"],
                                      attempts_live=n,
                                      jaeger_peak_mib={"replay": replay_peak,
                                                       "agent": rec["mem_peak_mib"].get("otel-replay-jaeger-1")})
                    rec["valid"] = True
                    break
                rec["valid"] = False
            live[case.incident_id] = {"replayed": attempts[-1].get("valid", False), "attempts": attempts}
            (run_dir / "live.json").write_text(json.dumps(live, ensure_ascii=False, indent=1) + "\n")
            print(f"{case.incident_id}: {live[case.incident_id]['replayed']} "
                  f"{attempts[-1].get('end_reason')} ({len(attempts)} attempt(s))", flush=True)
    print(run_dir)
    return 0 if all(v["replayed"] for v in live.values()) else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="agent_live.py", description="P2b: agent in live mode (replay stack)")
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--cases", required=True, help="comma-separated incident ids (pilot / dev only)")
    ap.add_argument("--root", type=Path, default=REPO / "llm_cache")
    args = ap.parse_args(argv)
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
    return run(args.model, [known[i] for i in ids], args.root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
