"""Yeniden oynatma collector ayarındaki kopyalar kaynaklarıyla aynı mı (depolama D3, planlama 2026-10-25 "kopya ayar
yok"). PyYAML yok: bloklar metin olarak karşılaştırılır (anahtar satırı ve daha içerideki satırlar; yorum ve boş
satırlar hariç)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
REPLAY = REPO / "deploy" / "replay" / "otelcol-replay.yml"
EXTRAS = REPO / "deploy" / "otel-demo" / "otelcol-config-extras.yml"
UPSTREAM = Path.home() / "cerebrum2" / "otel-demo" / "src" / "otel-collector" / "otelcol-config-observability.yml"
EXPORTERS = ["otlp_grpc/jaeger", "otlp_http/prometheus", "opensearch"]
# Upstream'den bilerek farklı satırlar (otelcol-replay.yml başındaki açıklama). Her biri ayarda bulunmalı; bunlar
# çıkarılınca blok upstream'le aynı olmalı. Listede olmayan bir fark kırmızı verir.
REPLAY_ONLY = {
    "otlp_grpc/jaeger": ["      block_on_overflow: true", "        min_size: 2048", "        max_size: 2048"],
    "otlp_http/prometheus": ["      block_on_overflow: true"],
    "opensearch": ["      block_on_overflow: true"],
}


def significant(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def section(text: str, name: str) -> list[str]:
    """Üst düzey `name:` bölümünün satırları."""
    lines = significant(text)
    start = lines.index(f"{name}:")
    out = []
    for line in lines[start + 1:]:
        if not line.startswith(" "):
            break
        out.append(line)
    return out


def block(text: str, top: str, key: str) -> list[str]:
    """`top` bölümündeki `key:` anahtarı ve altındaki satırlar."""
    lines = section(text, top)
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)(\S.*):$", line)
        if m and m.group(2) == key:
            indent = len(m.group(1))
            out = [line]
            for rest in lines[i + 1:]:
                if len(rest) - len(rest.lstrip()) <= indent:
                    break
                out.append(rest)
            return out
    raise AssertionError(f"{top}.{key} not found")


def test_backend_compat_same_as_live():
    replay, extras = REPLAY.read_text(), EXTRAS.read_text()
    assert block(replay, "processors", "transform/backend_compat") == \
        block(extras, "processors", "transform/backend_compat")


def test_only_file_receivers():
    keys = [line.strip()[:-1] for line in section(REPLAY.read_text(), "receivers")
            if re.match(r"^  \S.*:$", line)]
    assert keys and all(k.startswith("otlpjsonfile/") for k in keys), keys


@pytest.mark.skipif(not UPSTREAM.is_file(), reason="upstream demo clone not present (CI)")
@pytest.mark.parametrize("name", EXPORTERS)
def test_exporters_same_as_upstream(name):
    replay = block(REPLAY.read_text(), "exporters", name)
    for line in REPLAY_ONLY[name]:
        assert replay.count(line) == 1, f"{name}: allowed difference {line.strip()!r} not in replay config"
    assert [x for x in replay if x not in REPLAY_ONLY[name]] == block(UPSTREAM.read_text(), "exporters", name)
