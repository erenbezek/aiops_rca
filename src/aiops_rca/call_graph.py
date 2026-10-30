"""Snapshot izlerinden servisler arası çağrı kenarları (DECISIONS 2026-10-30 "Kanıt geçerliliği", "P1a kararları").

Kenar (A, B): üst span A servisinde, alt span B servisinde (A ≠ B), yani A B'yi çağırdı (Kafka'da üretici → tüketici).
Bütün snapshot penceresi okunur (`traces.jsonl`). Üst span'i snapshot'ta olmayan span (pencere kesimi) kenar vermez.
Sayı = o kenarı veren alt span sayısı. Aynı geçişte izlerde görülen servis adları da döner (ad eşleme için).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from aiops_rca.signals import iter_lines, resource_attr


def service_edges(trace_paths: list[Path]) -> tuple[Counter, set[str]]:
    """((üst servis, alt servis) → alt span sayısı, izlerde görülen servisler)."""
    span_svc: dict[str, str] = {}
    children: list[tuple[str, str]] = []  # (üst span kimliği, alt span servisi)
    for doc in iter_lines(trace_paths):
        for rs in doc.get("resourceSpans", []):
            svc = resource_attr(rs.get("resource", {}), "service.name")
            if svc is None:
                continue
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    sid = sp.get("spanId")
                    if sid:
                        span_svc[sid] = svc
                    parent = sp.get("parentSpanId")
                    if parent:
                        children.append((parent, svc))
    edges = Counter()
    for parent, svc in children:
        p = span_svc.get(parent)
        if p is not None and p != svc:
            edges[(p, svc)] += 1
    return edges, set(span_svc.values()) | {svc for _, svc in children}

