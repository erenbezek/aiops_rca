"""Kural baseline (HANDOFF 2026-10-30 P1a kartı 6. madde; DECISIONS 2026-10-30 "Kural baseline sabit", "P1a kararları").

C2'nin basit kuralı, `signals.rule_check` olduğu gibi: görünümdeki bütün `*.jsonl`, pencere `Window(alarm)`; her servise
aynı sinyaller ve eşikler; puan = gücü ≥ 1 olan sinyal sayısı, eşitlikte en büyük güç, sonra servis adı; ilk 3.
astronomy-db ve valkey-cart yalnız CPU/bellek; izleme araçları ve rutin servisler (flagd, flagd-ui, load-generator)
puanlanmaz. Dev'de ayarlanmaz.

Cevap: tam 3 aday, `confidence` null (kural güven vermez, kalibrasyona girmez), `evidence_path` [servis] (kenarsız,
kanıt geçerliliği null), `unsure` false. Gerekçe: puan, eşiği aşan sinyaller, en büyük güç. Ham çıktı: `rule_check`'in
ilk 3'ü (JSON).
"""
from __future__ import annotations

import json

from aiops_rca.cases import Case
from aiops_rca.signals import Window, rule_check, service_rows, summarize


def rule_baseline(case: Case) -> tuple[dict, str]:
    result, _ = summarize(sorted(case.view.glob("*.jsonl")), Window(case.alarm_ns))
    top = rule_check(service_rows(result), None)["top3"]
    answer = {"candidates": [{"service": t["service"], "confidence": None, "evidence_path": [t["service"]],
                              "rationale": f"score {t['score']}: {', '.join(t['signals']) or 'none'}; "
                                           f"max strength {t['max_strength']}"} for t in top],
              "unsure": False}
    return answer, json.dumps(top, ensure_ascii=False, sort_keys=True)
