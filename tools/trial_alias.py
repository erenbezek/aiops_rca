"""Takma ad ön denemesi: vaka özetinin takma adlı kopyası (HANDOFF 2026-10-23, DECISIONS 2026-10-23).

Kullanım: python tools/trial_alias.py <vaka klasörü>...

Her vakada `view/summary.json` okunur, `view_alias/summary.json` yazılır (aynı biçim: girintisiz JSON). Eşleme
`ALIASES` (GLOSSARY "takma ad eşlemesi (2026-10-23)" ile aynı), bütün vakalarda aynı.

Değişen:
- Servis adı alanları (`services[].service`, log satırlarının `service` alanı): gerçek ad → takma ad.
- Log mesajlarındaki tanımlayıcı biçimler, uzun adlar önce:
  tireli / alt çizgili ad (`product-catalog`, `product_catalog`; büyük/küçük harf fark etmez) → takma ad;
  CamelCase ad (`ProductCatalog`) ve `…Service` (`CheckoutService`) → takma adın CamelCase'i (`Inventory`,
  `OrderProcessorService`); `oteldemo.` ve `demo.` önekleri silinir (Eren, 2026-10-23).
Kalan: mesajlardaki sıradan İngilizce kelimeler (payment, cart, checkout, `Checkout` cümle başında…), rakamlar,
alanlar, sıra.

Kontrol (yazmadan önce; biri tutmazsa o vaka yazılmaz, çıkış 1):
- Servis adı alanlarında gerçek ad yok, hepsi takma ad.
- Mesajlarda tanımlayıcı biçimler ve `astronomy`, `valkey`, `otel`, `opentelemetry` geçmiyor (sıradan kelimeler
  aranmaz). Bunlardan birinin karşılığı tanımlı değilse (ör. tek başına `valkey`) betik uydurmaz, hata verir.
- Ad dışındaki her şey aynı: alanlar, sıra, sayılar; mesajlarda değişen parçalar dışındaki metin.
Çıkış kodu: 0 yazıldı, 1 kontrol tutmadı, 2 kullanım/girdi hatası.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# GLOSSARY "takma ad eşlemesi (2026-10-23)"; değişirse ikisi birlikte.
ALIASES = {
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
}
PREFIXES = ("oteldemo.", "demo.")
FORBIDDEN_TERMS = re.compile(r"(?<![a-z])(astronomy|valkey|opentelemetry|otel)", re.I)


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


def convert(summary: dict) -> dict:
    out = json.loads(json.dumps(summary))
    for row in out["services"]:
        row["service"] = ALIASES.get(row["service"], row["service"])
    for msg in out["top_warning_and_error_logs_after_alarm"]:
        msg["service"] = ALIASES.get(msg["service"], msg["service"])
        msg["message"] = convert_message(msg["message"])
    return out


def unchanged_parts_kept(real: str, alias: str) -> bool:
    """Gerçek mesajın eşleşmeyen parçaları takma adlı mesajda aynı sırayla duruyor mu."""
    fragments = [real]
    for p, _ in RULES:  # her desen kendi bayrağıyla (CamelCase büyük/küçük harfe duyarlı)
        fragments = [piece for f in fragments for piece in p.split(f)]
    pattern = "(?:.*?)".join(re.escape(f) for f in fragments)
    return re.fullmatch(pattern, alias, re.S) is not None


def check(real: dict, alias: dict) -> list[str]:
    problems = []
    names = set(ALIASES.values())
    for row in alias["services"]:
        if row["service"] not in names:
            problems.append(f"service field not aliased: {row['service']}")
    for msg in alias["top_warning_and_error_logs_after_alarm"]:
        if msg["service"] not in names and msg["service"] != "<unknown>":
            problems.append(f"log service field not aliased: {msg['service']}")
        for pattern, _ in RULES:
            if pattern.search(msg["message"]):
                problems.append(f"identifier left in message: {pattern.pattern!r} in {msg['message']!r}")
        if FORBIDDEN_TERMS.search(msg["message"]):
            problems.append(f"forbidden term in message: {msg['message']!r}")
    # Ad dışındaki her şey aynı: takma adlar geri çevrilip mesajlar ayrı kontrol edilir.
    back = {a: r for r, a in ALIASES.items()}
    restored = json.loads(json.dumps(alias))
    for row in restored["services"]:
        row["service"] = back.get(row["service"], row["service"])
    for msg_r, msg_a, msg_o in zip(restored["top_warning_and_error_logs_after_alarm"],
                                   alias["top_warning_and_error_logs_after_alarm"],
                                   real["top_warning_and_error_logs_after_alarm"]):
        msg_r["service"] = back.get(msg_r["service"], msg_r["service"])
        if not unchanged_parts_kept(msg_o["message"], msg_a["message"]):
            problems.append(f"message text changed beyond names: {msg_o['message']!r} -> {msg_a['message']!r}")
        msg_r["message"] = msg_o["message"]
    if restored != real or list(map(list, map(dict.keys, restored["services"]))) != \
            list(map(list, map(dict.keys, real["services"]))):
        problems.append("non-name values, fields or order differ")
    return problems


def dumps(summary: dict) -> str:
    return json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    status = 0
    for case in (Path(a).expanduser() for a in argv):
        src = case / "view" / "summary.json"
        try:
            text = src.read_text(encoding="utf-8")
            real = json.loads(text)
        except (OSError, ValueError) as e:
            print(f"error: {src}: {e}", file=sys.stderr)
            return 2
        if dumps(real) != text:
            print(f"error: {src}: not in trial_summary format (re-serialized text differs)", file=sys.stderr)
            return 2
        unknown = {r["service"] for r in real["services"]} - set(ALIASES)
        if unknown:
            print(f"error: {src}: no alias for {sorted(unknown)}", file=sys.stderr)
            return 2
        alias = convert(real)
        problems = check(real, alias)
        if problems:
            status = 1
            print(f"{case.name}: NOT WRITTEN", file=sys.stderr)
            for p in problems:
                print(f"  {p}", file=sys.stderr)
            continue
        out = case / "view_alias" / "summary.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(dumps(alias), encoding="utf-8")
        changed = [(o["message"], a["message"]) for o, a in zip(real["top_warning_and_error_logs_after_alarm"],
                                                                 alias["top_warning_and_error_logs_after_alarm"])
                   if o["message"] != a["message"]]
        print(f"{case.name}: ok: {out} ({len(alias['services'])} services; messages changed: {changed})")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
