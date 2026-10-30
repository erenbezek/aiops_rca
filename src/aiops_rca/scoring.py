"""Puanlama (HANDOFF 2026-10-30 P1a kartı 4. madde; DECISIONS 2026-10-30 "Kalibrasyon ölçüsü", "Kanıt geçerliliği",
"P1a kararları").

- Ad eşleme (tek yer, `match_service`): boşluklar sadeleşir, küçük harf, `_` ve boşluk `-` olur; bilinen adlardan
  (snapshot izlerindeki servisler + etiketin kökü) biriyle aynıysa o ad, değilse eşleşmez (yanlış sayılır).
- top-1: 1. aday kök neden. top-3: kök neden üç adaydan birinde. Şemaya uymayan cevap: ikisi de yanlış.
- Kanıt geçerliliği (1. adayın yolu): yolun her ardışık kenarı (A, B), izlerde iki yönden birinde görülen bir
  servisler arası çağrıysa (B A'yı çağırdı: `reverse`, senkron yayılım; A B'yi çağırdı: `forward`, Kafka) geçerli.
  Yön kayda. Eşleşmeyen ad içeren yol geçersiz. Tek servislik (kenarsız) yol `null`, ayrı sayılır.
- Etiket yoluyla örtüşme: etiketin yayılım kenarlarından (kökten belirtiye, yönlü) 1. adayın yolunda ardışık kenar olarak
  geçenlerin payı. Etiketin yolu boşsa `null`.
- Kalibrasyon: Brier = (1. adayın güveni − top-1)² ortalaması, yalnız güven veren cevaplarda. Seçici doğruluk =
  `unsure` false olan vakalarda top-1; kapsama = bu vakaların payı.
- Özet (`score_table`): set başına ve toplam; süre ve token (varsa) toplamı.
"""
from __future__ import annotations

from collections import Counter

from aiops_rca.answer import Answer


def _norm(name: str) -> str:
    return "-".join(name.strip().lower().replace("_", " ").split())


def match_service(name: str, known: set[str]) -> str | None:
    """Cevaptaki adın bilinen karşılığı (yoksa None)."""
    by_norm = {_norm(k): k for k in known}
    return by_norm.get(_norm(name)) if isinstance(name, str) else None


def evidence(path: tuple[str, ...], edges: Counter, known: set[str]) -> dict:
    """Yolun kanıt geçerliliği: valid True/False/None, kenarlar ve görüldükleri yön."""
    names = [match_service(n, known) for n in path]
    if len(path) < 2:
        return {"valid": None, "edges": [], "unmatched": [p for p, n in zip(path, names) if n is None]}
    out = []
    for (a_raw, a), (b_raw, b) in zip(zip(path, names), list(zip(path, names))[1:]):
        if a is None or b is None:
            seen = None
        else:
            fwd, rev = edges.get((a, b), 0) > 0, edges.get((b, a), 0) > 0
            seen = "both" if fwd and rev else "forward" if fwd else "reverse" if rev else None
        out.append({"from": a or a_raw, "to": b or b_raw, "seen": seen})
    return {"valid": all(e["seen"] for e in out), "edges": out,
            "unmatched": [p for p, n in zip(path, names) if n is None]}


def label_overlap(path: tuple[str, ...], label_path: list[list[str]], known: set[str]) -> float | None:
    if not label_path:
        return None
    names = [match_service(n, known) for n in path]
    steps = {(a, b) for a, b in zip(names, names[1:]) if a and b}
    want = {tuple(e) for e in label_path}
    return round(len(want & steps) / len(want), 3)


def score_case(answer: Answer | None, label: dict, edges: Counter, known: set[str]) -> dict:
    """Bir cevabın puanı. `answer` None = şemaya uymayan cevap."""
    root = label["root_cause_service"]
    known = set(known) | {root}
    if answer is None:
        return {"schema_valid": False, "top1": False, "top3": False, "matched": [], "unmatched": [],
                "evidence_valid": None, "evidence_edges": [], "label_path_overlap": None, "confidence": None,
                "unsure": None}
    matched = [match_service(c.service, known) for c in answer.candidates]
    first = answer.candidates[0]
    ev = evidence(first.evidence_path, edges, known)
    return {"schema_valid": True, "top1": matched[0] == root, "top3": root in matched, "matched": matched,
            "unmatched": [c.service for c, m in zip(answer.candidates, matched) if m is None],
            "evidence_valid": ev["valid"], "evidence_edges": ev["edges"],
            "label_path_overlap": label_overlap(first.evidence_path, label["propagation_path"], known),
            "confidence": first.confidence, "unsure": answer.unsure}


def _rate(k: int, n: int) -> float | None:
    return round(k / n, 3) if n else None


def _metrics(rows: list[dict]) -> dict:
    n = len(rows)
    top1, top3 = sum(r["top1"] for r in rows), sum(r["top3"] for r in rows)
    ev = Counter("null" if r["evidence_valid"] is None else "valid" if r["evidence_valid"] else "invalid"
                 for r in rows)
    ov = [r["label_path_overlap"] for r in rows if r["label_path_overlap"] is not None]
    conf = [(r["confidence"], r["top1"]) for r in rows if r["confidence"] is not None]
    sure = [r for r in rows if r["unsure"] is False]
    durations = [r["duration_s"] for r in rows if r.get("duration_s") is not None]
    tokens = [r["tokens"] for r in rows if r.get("tokens")]
    return {
        "n": n, "schema_invalid": sum(not r["schema_valid"] for r in rows),
        "top1": top1, "top1_rate": _rate(top1, n), "top3": top3, "top3_rate": _rate(top3, n),
        "evidence_valid": ev["valid"], "evidence_invalid": ev["invalid"], "evidence_null": ev["null"],
        "label_path_overlap_mean": round(sum(ov) / len(ov), 3) if ov else None, "label_path_overlap_n": len(ov),
        "brier": round(sum((c - h) ** 2 for c, h in conf) / len(conf), 4) if conf else None, "brier_n": len(conf),
        "selective_accuracy": _rate(sum(r["top1"] for r in sure), len(sure)), "coverage": _rate(len(sure), n),
        "duration_s_total": round(sum(durations), 3) if durations else None,
        "tokens_input": sum(t.get("input") or 0 for t in tokens) if tokens else None,
        "tokens_output": sum(t.get("output") or 0 for t in tokens) if tokens else None,
    }


def score_table(rows: list[dict]) -> dict:
    """Set başına ve toplam ölçüler. Her satırda `set` ve `score_case` alanları, varsa `duration_s`, `tokens`."""
    sets = sorted({r["set"] for r in rows})
    return {**{s: _metrics([r for r in rows if r["set"] == s]) for s in sets}, "all": _metrics(rows)}
