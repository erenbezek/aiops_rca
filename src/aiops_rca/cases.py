"""Vaka erişimi (HANDOFF 2026-10-30 P1a kartı 1. madde; DECISIONS 2026-10-30 "P1a kararları").

- Etiketler `incidents/inc-*.json`, görünüm `~/cerebrum2/snapshots/<incident_id>/` (`model_view`).
- Varsayılan setler geçerli `pilot` ve `dev`. `test` yalnız `final_test=True` ile (CLI `--final-test`) okunur;
  `heldout` hiç okunmaz. Bilinmeyen set adı hata.
- Yönteme etiket verilmez: `Case` yalnız vaka kimliği, görünüm klasörü ve alarm anıdır (`answer.injection_start`,
  DECISIONS 2026-10-30 "Alarm zamanı"). Etiketin cevap alanları yalnız puanlama için `load_labels` ile okunur.
- Etiketin `set` alanı seçim için her dosyada okunur; seçilmeyen vakanın snapshot'ı açılmaz.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INCIDENTS = REPO / "incidents"
SNAPSHOTS = Path.home() / "cerebrum2" / "snapshots"
DEFAULT_SETS = ("pilot", "dev")
KNOWN_SETS = frozenset({"pilot", "dev", "test", "heldout"})


@dataclass(frozen=True)
class Case:
    """Yöntemin gördüğü vaka: kimlik, görünüm klasörü, alarm anı (ns). Etiketin başka alanı yok."""
    incident_id: str
    view: Path
    alarm_ns: int


def _check_sets(sets: tuple[str, ...], final_test: bool) -> None:
    unknown = set(sets) - KNOWN_SETS
    if unknown:
        raise ValueError(f"unknown set(s): {sorted(unknown)}")
    if "heldout" in sets:
        raise PermissionError("set 'heldout' is never read")
    if "test" in sets and not final_test:
        raise PermissionError("set 'test' needs final_test=True (--final-test)")


def _labels(sets: tuple[str, ...], incidents: Path) -> list[dict]:
    out = []
    for p in sorted(incidents.glob("inc-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("set") in sets and d.get("valid") is True:
            out.append(d)
    return out


def alarm_ns(injection_start: str) -> int:
    return int(datetime.fromisoformat(injection_start.replace("Z", "+00:00")).timestamp()) * 10**9


def load_cases(sets: tuple[str, ...] = DEFAULT_SETS, *, final_test: bool = False, incidents: Path = INCIDENTS,
               snapshots: Path = SNAPSHOTS) -> list[Case]:
    """Seçilen setlerin geçerli vakaları, kimliğe göre sıralı."""
    sets = tuple(sets)
    _check_sets(sets, final_test)
    return [Case(d["incident_id"], snapshots / d["incident_id"], alarm_ns(d["answer"]["injection_start"]))
            for d in _labels(sets, incidents)]


def load_labels(sets: tuple[str, ...] = DEFAULT_SETS, *, final_test: bool = False,
                incidents: Path = INCIDENTS) -> dict[str, dict]:
    """Puanlama için: kimlik → {set, root_cause_service, propagation_path}. Yönteme verilmez."""
    sets = tuple(sets)
    _check_sets(sets, final_test)
    return {d["incident_id"]: {"set": d["set"], "root_cause_service": d["answer"]["root_cause_service"],
                               "propagation_path": [list(e) for e in d["answer"]["propagation_path"]]}
            for d in _labels(sets, incidents)}
