"""Cevap şeması (HANDOFF 2026-10-30 P1a kartı 3. madde; DECISIONS 2026-10-30 "Kalibrasyon ölçüsü", "P1a kararları").

Bütün yöntemlerde aynı. JSON biçimi:

    {"candidates": [{"service": str, "confidence": float | null, "evidence_path": [str, ...], "rationale": str}, ×3],
     "unsure": bool}

- Tam 3 aday, sıralı (1. aday en olası); servis adları birbirinden farklı. Şüphe `unsure` ile ifade edilir.
- `confidence` 0–1 ya da null. Güven veremeyen yöntem üç adayda da null bırakır (kalibrasyona girmez); karışık olamaz.
- `evidence_path` kökten belirtiye servis listesi, en az 1 eleman, ilk eleman adayın kendisi. Tek servislik yol kenarsızdır
  (kanıt geçerliliği null).
- `rationale` kısa gerekçe (metin; boş olabilir). Başka alan yok.
Doğrulayıcı yeni bağımlılık kullanmaz.
"""
from __future__ import annotations

from dataclasses import dataclass

N_CANDIDATES = 3
CANDIDATE_KEYS = frozenset({"service", "confidence", "evidence_path", "rationale"})
ANSWER_KEYS = frozenset({"candidates", "unsure"})


@dataclass(frozen=True)
class Candidate:
    service: str
    confidence: float | None
    evidence_path: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class Answer:
    candidates: tuple[Candidate, ...]
    unsure: bool

    @classmethod
    def from_dict(cls, obj: dict) -> "Answer":
        errors = validate_answer(obj)
        if errors:
            raise ValueError("; ".join(errors))
        return cls(tuple(Candidate(c["service"], None if c["confidence"] is None else float(c["confidence"]),
                                   tuple(c["evidence_path"]), c["rationale"]) for c in obj["candidates"]),
                   obj["unsure"])

    def to_dict(self) -> dict:
        return {"candidates": [{"service": c.service, "confidence": c.confidence, "evidence_path": list(c.evidence_path),
                                "rationale": c.rationale} for c in self.candidates],
                "unsure": self.unsure}


def _norm(name: str) -> str:
    return name.strip().lower()


def validate_answer(obj) -> list[str]:
    """Şema hataları (boş liste = geçerli)."""
    if not isinstance(obj, dict):
        return ["answer is not an object"]
    errors = []
    if set(obj) != ANSWER_KEYS:
        errors.append(f"answer keys {sorted(obj)}, want {sorted(ANSWER_KEYS)}")
    if not isinstance(obj.get("unsure"), bool):
        errors.append("unsure must be true or false")
    cands = obj.get("candidates")
    if not isinstance(cands, list) or len(cands) != N_CANDIDATES:
        return errors + [f"candidates must be a list of exactly {N_CANDIDATES}"]
    confs = []
    for i, c in enumerate(cands, 1):
        if not isinstance(c, dict) or set(c) != CANDIDATE_KEYS:
            errors.append(f"candidate {i}: keys {sorted(c) if isinstance(c, dict) else type(c).__name__}, "
                          f"want {sorted(CANDIDATE_KEYS)}")
            continue
        if not isinstance(c["service"], str) or not c["service"].strip():
            errors.append(f"candidate {i}: service must be a non-empty string")
        conf = c["confidence"]
        if conf is not None and (isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1):
            errors.append(f"candidate {i}: confidence must be null or a number in [0, 1]")
        confs.append(conf is None)
        path = c["evidence_path"]
        if (not isinstance(path, list) or not path
                or not all(isinstance(s, str) and s.strip() for s in path)):
            errors.append(f"candidate {i}: evidence_path must be a non-empty list of service names")
        elif isinstance(c["service"], str) and _norm(path[0]) != _norm(c["service"]):
            errors.append(f"candidate {i}: evidence_path must start at the candidate service")
        if not isinstance(c["rationale"], str):
            errors.append(f"candidate {i}: rationale must be a string")
    if len(set(confs)) > 1:
        errors.append("confidence must be given for all candidates or for none")
    names = [_norm(c["service"]) for c in cands if isinstance(c, dict) and isinstance(c.get("service"), str)]
    if len(names) == N_CANDIDATES and len(set(names)) != N_CANDIDATES:
        errors.append("candidate services must be distinct")
    return errors
