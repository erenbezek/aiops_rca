"""quote-gateway iş mantığı (Flask'sız; tests/test_quote_gateway.py host'ta koşar).

- `parse_items`: istek gövdesindeki `numberOfItems` sıfır ya da pozitif tam sayı olmalı.
- `QuoteCache`: aynı `numberOfItems` için kısa ömürlü (1 sn), sınırlı (64 kayıt) önbellek. Ömür bilerek kısa:
  shipping dakikada ~10–12 istek atıyor, isabet nadir; quote'a giden trafik pratikte değişmez (quote'un V2 çiftleri).
  `put(..., retain_kb=k)` k > 0 iken her eklemeyle k KB'lık bir kayıt saklanır ve hiç silinmez (bellek sızıntısı
  hatası). Kayıtlar rastgele baytla dolar: sıfır dolu bloklar fiziksel belleğe yazılmadan kalabilir (Eren).
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict

CACHE_TTL_S = 1.0
CACHE_MAX_ENTRIES = 64


def parse_items(body) -> int | None:
    """Gövdedeki `numberOfItems`; tam sayı değilse ya da negatifse None."""
    if not isinstance(body, dict):
        return None
    n = body.get("numberOfItems")
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        return None
    return n


class QuoteCache:
    def __init__(self, ttl_s: float = CACHE_TTL_S, max_entries: int = CACHE_MAX_ENTRIES, clock=time.monotonic):
        self.ttl_s, self.max_entries, self.clock = ttl_s, max_entries, clock
        self._entries: OrderedDict[int, tuple[float, str]] = OrderedDict()
        self._retained: list[bytes] = []
        self._lock = threading.Lock()

    def get(self, n: int) -> str | None:
        with self._lock:
            hit = self._entries.get(n)
            if hit is None:
                return None
            if self.clock() - hit[0] > self.ttl_s:
                del self._entries[n]
                return None
            return hit[1]

    def put(self, n: int, quote: str, retain_kb: int = 0) -> None:
        with self._lock:
            self._entries[n] = (self.clock(), quote)
            self._entries.move_to_end(n)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            if retain_kb > 0:
                self._retained.append(os.urandom(retain_kb * 1024))

    def __len__(self) -> int:
        return len(self._entries)

    def retained_bytes(self) -> int:
        with self._lock:
            return sum(len(b) for b in self._retained)
