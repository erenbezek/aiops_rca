"""Koşu kaydı (HANDOFF 2026-10-30 P1a kartı 5. madde).

Koşu klasörü `<kök>/<UTC>-<yöntem>/`, aynı saniyede ikincisi `-2` (resmî koşular `eval_responses/`, denemeler
`llm_cache/`):
- `run.json`: yöntem, model kimliği, sağlayıcı, temperature, ayarlar, setler, başlangıç (UTC), repo commit'i ve çalışma
  ağacının temiz olup olmadığı (`repo_clean`; `eval_responses/` sayılmaz: koşu çıktısı kod değil), vaka sayısı.
- `responses.jsonl`: vaka başına bir satır: `incident_id`, `answer` (şemaya uyuyorsa sözlük, değilse null),
  `schema_valid`, `schema_errors`, `raw_output`, `duration_s`, `tokens` ({input, output} ya da null).
- `scores.json` (`evaluate score` yazar): vaka başına puan ve set başına özet; kayıtlardan yeniden üretilir.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from aiops_rca.cases import REPO

EVAL_RESPONSES = REPO / "eval_responses"


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def new_run(method: str, sets: tuple[str, ...], n_cases: int, *, root: Path = EVAL_RESPONSES,
            model_id: str | None = None, provider: str | None = None, temperature: float | None = None,
            settings: dict | None = None) -> Path:
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    base = f"{started.replace('-', '').replace(':', '')}-{method}"
    root.mkdir(parents=True, exist_ok=True)
    run_dir, k = root / base, 1
    while True:  # aynı saniyede başlayan koşu üzerine yazmaz: -2, -3, ...
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            k += 1
            run_dir = root / f"{base}-{k}"
    status = _git("status", "--porcelain", "--", ".", ":(exclude)eval_responses")  # koşu çıktıları kod değil
    run = {"method": method, "model_id": model_id, "provider": provider, "temperature": temperature,
           "settings": settings or {}, "sets": list(sets), "started_at": started, "repo_commit": _git("rev-parse", "HEAD"),
           "repo_clean": status == "" if status is not None else None, "n_cases": n_cases}
    (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return run_dir


def append_response(run_dir: Path, row: dict) -> None:
    with (run_dir / "responses.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_run(run_dir: Path) -> tuple[dict, list[dict]]:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run_dir / "responses.jsonl").read_text(encoding="utf-8").splitlines() if line]
    return run, rows
