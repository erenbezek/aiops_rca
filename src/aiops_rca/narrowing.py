"""Aday daraltma, `candidate_narrowing` (HANDOFF 2026-10-30 P1c kartı 3. madde; DECISIONS 2026-10-30 "Daraltma",
2026-10-31 "Daraltmanın öne alma kuralı"). Yalnız pilotta ayarlandı; dev'de ayar yok.

1. Aday kümesi ve puan kuralınki (`signals.signals`, aynı eşikler): izleme araçları, rutin servisler (flagd, flagd-ui,
   load-generator) ve `<unknown>` dışarıda; astronomy-db ve valkey-cart yalnız CPU/bellek. Puan = gücü ≥ 1 olan sinyal
   sayısı. Sıra: puan azalan, eşitlikte bütün sinyallerin en büyük gücü azalan (eşik altı dahil; `rule_check`'ten tek
   fark: orada puanı 0 olanlar ada göre), sonra servis adı.
2. Anormal = puan ≥ 1.
3. Çağrı kenarları snapshot'ın bütün izlerinden (`call_graph.service_edges`): A → B = A, B'yi çağırdı. İzlerde olmayan
   servisin (veritabanları) çağırdığı yok.
4. Derin = anormal ve çağırdığı servislerin hiçbiri anormal değil.
5. Sıra: derinler → diğer anormaller → anormal olmayanlar (her grup kendi içinde 1'deki sırayla); ilk K = 5.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from aiops_rca.call_graph import service_edges
from aiops_rca.cases import Case
from aiops_rca.signals import (DB_SERVICES, ROUTINE_SERVICES, TOOLING_CONTAINERS, Window, service_rows, signals,
                               summarize)

K = 5
GROUPS = ("deep", "anomalous", "normal")


def service_scores(rows: dict[str, dict]) -> dict[str, dict]:
    """Servis → {score, max_strength, signals (eşiği aşanlar, adlarıyla sıralı)}; dışlananlar yok."""
    out = {}
    for svc, row in rows.items():
        if svc in TOOLING_CONTAINERS or svc in ROUTINE_SERVICES or svc == "<unknown>":
            continue
        sig, _ = signals(row, svc in DB_SERVICES)
        over = sorted(k for k, s in sig.items() if s["strength"] >= 1)
        out[svc] = {"score": len(over), "max_strength": max((s["strength"] for s in sig.values()), default=0),
                    "signals": over}
    return out


def narrow(scores: dict[str, dict], edges: Counter | dict, k: int = K) -> list[dict]:
    """Bütün servislerin daraltma sırası: [{service, group, score, max_strength, signals}, ...]; ilk `k` aday."""
    order = sorted(scores, key=lambda s: (-scores[s]["score"], -scores[s]["max_strength"], s))
    anomalous = {s for s in order if scores[s]["score"] >= 1}
    callees = defaultdict(set)
    for a, b in edges:
        callees[a].add(b)

    def group(s: str) -> str:
        if s not in anomalous:
            return "normal"
        return "anomalous" if callees[s] & anomalous else "deep"

    ranked = sorted(order, key=lambda s: GROUPS.index(group(s)))  # sorted kararlı: grup içinde `order` korunur
    return [{"service": s, "group": group(s), **scores[s]} for s in ranked]


def candidate_narrowing(case: Case, k: int = K) -> dict:
    """Vakanın daraltması: `candidates` (ilk k servis adı), `ranking` (bütün sıra), `edges` (adaylar arasındaki
    kenarlar, [çağıran, çağrılan, span sayısı], sıralı)."""
    result, _ = summarize(sorted(case.view.glob("*.jsonl")), Window(case.alarm_ns))
    edges, _ = service_edges([case.view / "traces.jsonl"])
    ranking = narrow(service_scores(service_rows(result)), edges, k)
    cands = [r["service"] for r in ranking[:k]]
    among = sorted([a, b, n] for (a, b), n in edges.items() if a in cands and b in cands)
    return {"incident_id": case.incident_id, "candidates": cands, "ranking": ranking, "edges": among}
