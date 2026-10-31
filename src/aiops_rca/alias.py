"""Takma ad: üç girdi seviyesinin takma adlı kopyası ve kontrolü (HANDOFF 2026-10-31 P1c 4. adım planı; DECISIONS
2026-10-23 takma ad kuralları). Eşleme ve mesaj kuralları `tools/trial_alias.py`'den taşındı (betik buradan içe
aktarır, davranış aynı).

Takma ad gerçek adla üretilen girdinin üzerine uygulanır; ad dışındaki her şey (alanlar, sıra, sayılar, metnin ad
dışındaki parçaları) aynı kalır. Sıra gerçek adların sırasıdır.

- Ad alanları (`service`, `caller`, `calls` çiftleri): gerçek ad → takma ad. `<unknown>` (servisi bilinmeyen log)
  olduğu gibi kalır.
- Metin alanları (log mesajı, span/işlem adı): tanımlayıcı biçimler, uzun adlar önce: tireli / alt çizgili ad
  (`product-catalog`, `product_catalog`; büyük/küçük harf fark etmez) → takma ad; CamelCase ad (`ProductCatalog`) ve
  `…Service` (`CheckoutService`) → takma adın CamelCase'i; `oteldemo.` ve `demo.` önekleri silinir. Sıradan
  İngilizce kelimeler (payment, cart, `Checkout` cümle başında…) kalır.

Seviyeler (`inputs.py` ile aynı dönüş sözlüğü):
- summary, narrowed: tablo `convert_table` ile çevrilir, `summary_text` ile yazılır, token yeniden sayılır.
- raw: gerçek girdinin **aynı satırları** (aynı sıra, aynı sayı); satır metni kesilmeden önce çevrilir, sonra
  500 karakterde kesilir. Takma adlı metin bütçeyi aşarsa sondan satır eksiltilir (aynı kural: tam satırlar +
  `TRUNCATION_MARK`); eksiltilen satır sayısı `alias_lines_dropped`. Boş girdi boş kalır.

Kontrol (biri tutmazsa girdi üretilmez, `ValueError`): ad alanlarında gerçek ad yok, her ad eşlemedeki karşılığı;
metinlerde tanımlayıcı biçim ve yasak terim (`astronomy`, `valkey`, `otel`, `opentelemetry`) kalmamış; metnin
değişmeyen parçaları aynı sırayla duruyor; ad ve metin dışındaki her değer, alan ve sıra aynı.
"""
from __future__ import annotations

import re

from aiops_rca import inputs
from aiops_rca.cases import Case
from aiops_rca.inputs import DATA_BUDGET, TRUNCATION_MARK, TokenCounter, raw_line, raw_records, summary_text
from aiops_rca.signals import Window, summarize

# GLOSSARY "takma ad eşlemesi"; değişirse ikisi birlikte (tests/test_alias.py karşılaştırır).
ALIASES = {
    # 2026-10-23
    "frontend": "storefront",
    "frontend-proxy": "edge-gateway",
    "ad": "promotions",
    "cart": "basket",
    "checkout": "order-processor",
    "payment": "billing",
    "product-catalog": "inventory",
    "recommendation": "suggestions",
    "shipping": "logistics",
    "quote": "rate-calculator",
    "currency": "fx-rates",
    "email": "notifier",
    "image-provider": "media-server",
    "telemetry-docs": "docs-site",
    "astronomy-db": "main-db",
    "valkey-cart": "session-cache",
    # 2026-10-31
    "quote-gateway": "rate-gateway",
    "frontend-web": "storefront-web",
}
UNKNOWN_SERVICE = "<unknown>"  # inputs.raw_records ve summarize'ın servisi bilinmeyen kaydı
PREFIXES = ("oteldemo.", "demo.")
FORBIDDEN_TERMS = re.compile(r"(?<![a-z])(astronomy|valkey|opentelemetry|otel)", re.I)
NAME_KEYS = ("service", "caller")
TEXT_KEYS = ("message", "operation")
NAME_PAIR_KEYS = ("calls",)


def camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("-"))


def message_rules() -> list[tuple[re.Pattern, str]]:
    """(desen, yerine) listesi; uzun adlar önce."""
    rules = []
    for real in sorted(ALIASES, key=len, reverse=True):
        alias = ALIASES[real]
        if "-" in real:  # tireli ve alt çizgili yazım
            sep = re.escape(real).replace(r"\-", "[-_]")
            rules.append((re.compile(rf"(?<![A-Za-z0-9]){sep}(?![A-Za-z0-9])", re.I), alias))
            rules.append((re.compile(rf"(?<![A-Za-z0-9]){camel(real)}"), camel(alias)))  # ProductCatalog(Service)
        else:
            rules.append((re.compile(rf"(?<![A-Za-z0-9]){camel(real)}(?=Service)"), camel(alias)))
    for prefix in PREFIXES:
        rules.append((re.compile(rf"(?<![A-Za-z0-9.]){re.escape(prefix)}"), ""))
    return rules


RULES = message_rules()


def convert_message(message: str) -> str:
    for pattern, repl in RULES:
        message = pattern.sub(repl, message)
    return message


def unchanged_parts_kept(real: str, alias: str) -> bool:
    """Gerçek mesajın eşleşmeyen parçaları takma adlı mesajda aynı sırayla duruyor mu."""
    fragments = [real]
    for p, _ in RULES:  # her desen kendi bayrağıyla (CamelCase büyük/küçük harfe duyarlı)
        fragments = [piece for f in fragments for piece in p.split(f)]
    pattern = "(?:.*?)".join(re.escape(f) for f in fragments)
    return re.fullmatch(pattern, alias, re.S) is not None


def alias_name(name: str) -> str:
    """Eşlemede yoksa olduğu gibi döner; kontrol yakalar."""
    return ALIASES.get(name, name)


def convert_table(node, key: str | None = None):
    """Özet ya da daraltma tablosunun takma adlı kopyası (yalnız ad ve metin alanları değişir)."""
    if isinstance(node, dict):
        return {k: convert_table(v, k) for k, v in node.items()}
    if isinstance(node, list):
        if key in NAME_PAIR_KEYS:
            return [[alias_name(n) for n in pair] for pair in node]
        return [convert_table(v, key) for v in node]
    if isinstance(node, str):
        if key in NAME_KEYS:
            return alias_name(node)
        if key in TEXT_KEYS:
            return convert_message(node)
    return node


# --- kontrol ---

def check_name(real: str, alias: str, where: str) -> list[str]:
    if real == UNKNOWN_SERVICE:
        return [] if alias == UNKNOWN_SERVICE else [f"{where}: {real!r} -> {alias!r}"]
    if real not in ALIASES:
        return [f"{where}: no alias for {real!r}"]
    return [] if alias == ALIASES[real] else [f"{where}: {real!r} -> {alias!r}, expected {ALIASES[real]!r}"]


def leftover(text: str, where: str) -> list[str]:
    """Takma adlı metinde kalan tanımlayıcı biçim ya da yasak terim."""
    problems = [f"{where}: identifier left: {p.pattern!r} in {text!r}" for p, _ in RULES if p.search(text)]
    if FORBIDDEN_TERMS.search(text):
        problems.append(f"{where}: forbidden term in {text!r}")
    return problems


def check_text(real: str, alias: str, where: str) -> list[str]:
    problems = leftover(alias, where)
    if not unchanged_parts_kept(real, alias):
        problems.append(f"{where}: text changed beyond names: {real!r} -> {alias!r}")
    return problems


def check_table(real, alias, key: str | None = None, where: str = "$") -> list[str]:
    """Takma adlı tablo gerçek tablonun, yalnız adları ve metinlerdeki tanımlayıcıları değişmiş kopyası mı."""
    if type(real) is not type(alias):
        return [f"{where}: type differs"]
    if isinstance(real, dict):
        if list(real) != list(alias):
            return [f"{where}: fields or field order differ"]
        return [p for k in real for p in check_table(real[k], alias[k], k, f"{where}.{k}")]
    if isinstance(real, list):
        if len(real) != len(alias):
            return [f"{where}: length differs"]
        if key in NAME_PAIR_KEYS:
            problems = []
            for i, (rp, ap) in enumerate(zip(real, alias)):
                if len(rp) != len(ap):
                    problems.append(f"{where}[{i}]: length differs")
                problems += [p for j, (r, a) in enumerate(zip(rp, ap)) for p in check_name(r, a, f"{where}[{i}][{j}]")]
            return problems
        return [p for i, (r, a) in enumerate(zip(real, alias)) for p in check_table(r, a, key, f"{where}[{i}]")]
    if isinstance(real, str) and key in NAME_KEYS:
        return check_name(real, alias, where)
    if isinstance(real, str) and key in TEXT_KEYS:
        return check_text(real, alias, where)
    return [] if real == alias else [f"{where}: value differs: {real!r} -> {alias!r}"]


def aliased_table(real: dict, incident_id: str) -> dict:
    alias = convert_table(real)
    problems = check_table(real, alias)
    if problems:
        raise ValueError(f"{incident_id}: alias check failed: " + "; ".join(problems))
    return alias


# --- seviyeler ---

def summary_input(case: Case, count_tokens: TokenCounter) -> dict:
    window = Window(case.alarm_ns)
    result, _ = summarize(sorted(case.view.glob("*.jsonl")), window)
    text = summary_text(aliased_table(inputs.summary_table(result, window), case.incident_id))
    return {"level": "summary", "incident_id": case.incident_id, "text": text, "data_tokens": count_tokens(text),
            "empty": False}


def narrowed_input(case: Case, count_tokens: TokenCounter) -> dict:
    table = aliased_table(inputs.narrowed_table(case), case.incident_id)
    text = summary_text(table)
    return {"level": "narrowed", "incident_id": case.incident_id, "text": text, "data_tokens": count_tokens(text),
            "empty": False, "candidates": [b["service"] for b in table["candidates"]]}


def raw_input(case: Case, count_tokens: TokenCounter, budget: int = DATA_BUDGET) -> dict:
    real = inputs.raw_input(case, count_tokens, budget)
    if real["empty"]:
        return {**real, "alias_lines_dropped": 0}
    # Gerçek satırların sırası (zaman, gerçek satır metni); eşitlikte kayıt sırası.
    records = sorted(((t, raw_line(t, s, k, x), s, k, x) for t, s, k, x in raw_records(case)),
                     key=lambda r: (r[0], r[1]))
    problems = []
    lines = []
    for i, (t, line, svc, kind, text) in enumerate(records):
        where = f"{case.incident_id} raw[{i}]"
        alias_svc, alias_text = alias_name(svc), convert_message(text)
        problems += check_name(svc, alias_svc, where) + check_text(text, alias_text, where)
        alias_line = raw_line(t, alias_svc, kind, alias_text)
        problems += leftover(alias_line, where)
        lines.append(alias_line)
    if problems:
        raise ValueError(f"{case.incident_id}: alias check failed: " + "; ".join(problems))

    kept, mark = real["lines_kept"], real["truncated"]
    real_lines = [r[1] for r in records]
    if "\n".join(real_lines[:kept] + ([TRUNCATION_MARK] if mark else [])) != real["text"]:
        raise ValueError(f"{case.incident_id}: raw lines differ from the real input")  # aynı satırlar

    def text_for(k: int, with_mark: bool) -> str:
        return "\n".join(lines[:k] + ([TRUNCATION_MARK] if with_mark else []))

    text = text_for(kept, mark)
    tokens = count_tokens(text)
    while tokens > budget:  # takma adlı metin uzadıysa sondan tam satır eksilt
        if kept == 0:
            raise ValueError(f"budget {budget} too small for the truncation mark")
        kept, mark = kept - 1, True
        text = text_for(kept, mark)
        tokens = count_tokens(text)
    return {**real, "text": text, "data_tokens": tokens, "lines_kept": kept, "truncated": kept < len(lines),
            "alias_lines_dropped": real["lines_kept"] - kept}
