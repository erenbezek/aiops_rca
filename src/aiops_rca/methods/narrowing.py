"""Daraltma referansı (HANDOFF 2026-11-04 P1e kartı 2. madde; DECISIONS 2026-11-04 "P1e sonuç tablosu repoda").

Modelsiz referans satırı: `narrowing.candidate_narrowing`'in kendi sırası, olduğu gibi. Cevap kural baseline'ının
biçiminde: sıranın ilk 3 servisi aday, `confidence` null (güven yok, kalibrasyona girmez), `evidence_path` [servis]
(kenarsız, kanıt geçerliliği null), `unsure` false. Gerekçe: grup, puan, eşiği aşan sinyaller, en büyük güç.
Ham çıktı: sıranın ilk K'si (JSON). Ayar yok.
"""
from __future__ import annotations

import json

from aiops_rca.cases import Case
from aiops_rca.narrowing import candidate_narrowing


def narrowing_baseline(case: Case) -> tuple[dict, str]:
    ranking = candidate_narrowing(case)["ranking"]
    top = ranking[:3]
    answer = {"candidates": [{"service": t["service"], "confidence": None, "evidence_path": [t["service"]],
                              "rationale": f"{t['group']}, score {t['score']}: {', '.join(t['signals']) or 'none'}; "
                                           f"max strength {t['max_strength']}"} for t in top],
              "unsure": False}
    return answer, json.dumps(ranking[:5], ensure_ascii=False, sort_keys=True)
