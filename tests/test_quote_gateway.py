"""quote-gateway iş mantığı (services/quote-gateway/gateway.py): girdi kontrolü, kısa ömürlü sınırlı önbellek, sızıntı kipi.

Flask katmanı ve flag'lerin etkisi canlıda sınanır (HANDOFF); burada host'a yeni paket gerekmez.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "services" / "quote-gateway"))
import gateway as gw  # noqa: E402


@pytest.mark.parametrize("body,want", [({"numberOfItems": 3}, 3), ({"numberOfItems": 0}, 0),
                                       ({"numberOfItems": -1}, None), ({"numberOfItems": "3"}, None),
                                       ({"numberOfItems": 2.5}, None), ({"numberOfItems": True}, None),
                                       ({}, None), (None, None), ([3], None)])
def test_parse_items(body, want):
    assert gw.parse_items(body) == want


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_cache_decision_values():
    # Eren onayı: 1 sn ömür (quote'un trafiği korunur), 64 kayıt.
    assert (gw.CACHE_TTL_S, gw.CACHE_MAX_ENTRIES) == (1.0, 64)


def test_cache_hit_within_ttl_and_expiry():
    clock = Clock()
    c = gw.QuoteCache(clock=clock)
    c.put(3, "26.97")
    clock.t = 0.9
    assert c.get(3) == "26.97"
    clock.t = 1.2
    assert c.get(3) is None and len(c) == 0


def test_cache_is_bounded_without_retention():
    c = gw.QuoteCache(max_entries=4, clock=Clock())
    for n in range(10):
        c.put(n, str(n))
    assert len(c) == 4 and c.get(0) is None and c.get(9) == "9"
    assert c.retained_bytes() == 0


def test_retention_grows_per_request_with_nonzero_data():
    c = gw.QuoteCache(max_entries=4, clock=Clock())
    for n in range(10):
        c.put(n % 2, "1.00", retain_kb=8)
    assert len(c) == 2 and c.retained_bytes() == 10 * 8 * 1024
    # Rastgele bayt: sıfır dolu blok fiziksel belleğe yazılmadan kalabilir (Eren).
    assert all(any(b) for b in c._retained) and len(set(c._retained)) == 10


# --- flag birleştirme (tools/otel_demo.sh merge_flag_files) ve koşucunun yeni flag'leri açıp kapatması ---

import copy  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
import scenario_runner as sr  # noqa: E402

EXTRAS = REPO / "deploy" / "otel-demo" / "flagd-extras.json"
OURS = [s for s in sr.SCENARIOS if s["root"] == "quote-gateway"]
UPSTREAM = {"$schema": "https://flagd.dev/schema/v0/flags.json", "flags": {
    "adFailure": {"description": "x", "state": "ENABLED", "variants": {"on": True, "off": False}, "defaultVariant": "off"},
    "paymentFailure": {"description": "y", "state": "ENABLED", "variants": {"100%": 1, "off": 0}, "defaultVariant": "off"}}}


def merge(tmp_path, upstream: dict) -> subprocess.CompletedProcess:
    """otel_demo.sh'deki birleştirme betiğini (heredoc) aynen çalıştırır."""
    script = re.search(r"<<'PY'\n(.*?)\nPY\n", (REPO / "tools" / "otel_demo.sh").read_text(), re.S).group(1)
    (tmp_path / "up.json").write_text(json.dumps(upstream))
    return subprocess.run([sys.executable, "-c", script, str(tmp_path / "up.json"), str(EXTRAS),
                           str(tmp_path / "out.json")], capture_output=True, text=True)


def test_merge_appends_our_flags(tmp_path):
    assert merge(tmp_path, UPSTREAM).returncode == 0
    out = json.loads((tmp_path / "out.json").read_text())
    ours = json.loads(EXTRAS.read_text())["flags"]
    assert list(out["flags"]) == list(UPSTREAM["flags"]) + list(ours)
    assert out["$schema"] == UPSTREAM["$schema"] and all(out["flags"][k] == v for k, v in ours.items())


def test_merge_rejects_duplicate_name(tmp_path):
    up = copy.deepcopy(UPSTREAM)
    up["flags"]["quoteGatewaySlowdown"] = up["flags"]["adFailure"]
    r = merge(tmp_path, up)
    assert r.returncode != 0 and "quoteGatewaySlowdown" in r.stderr and not (tmp_path / "out.json").exists()


def test_our_flags_off_by_default_and_variants_in_runner():
    ours = json.loads(EXTRAS.read_text())["flags"]
    assert {s["flag"] for s in OURS} == set(ours) and len(OURS) == 5
    for s in OURS:
        f = ours[s["flag"]]
        assert f["defaultVariant"] == "off" and s["variant"] in f["variants"]


@pytest.mark.parametrize("s", OURS, ids=sr.scenario_id)
def test_runner_sets_and_resets_our_flag_in_merged_file(tmp_path, monkeypatch, s):
    assert merge(tmp_path, UPSTREAM).returncode == 0
    state = {"doc": json.loads((tmp_path / "out.json").read_text())}

    def fake_http(method, url, body=None, timeout=20):  # flagd-ui: oku, yaz, çöz
        if url.endswith("/feature/api/read"):
            return copy.deepcopy(state["doc"])
        if url.endswith("/feature/api/write"):
            state["doc"] = copy.deepcopy(body["data"])
            return {}
        if "/Resolve" in url:
            return {"variant": state["doc"]["flags"][body["flagKey"]]["defaultVariant"]}
        raise AssertionError(url)

    monkeypatch.setattr(sr, "http", fake_http)
    monkeypatch.setattr(sr.time, "sleep", lambda _: None)
    before = copy.deepcopy(state["doc"])
    _, verified, answer = sr.set_flag(s, s["variant"])
    assert verified is not None and answer["variant"] == s["variant"]
    assert state["doc"]["flags"][s["flag"]]["defaultVariant"] == s["variant"]
    assert {k: v for k, v in state["doc"]["flags"].items() if k != s["flag"]} == \
        {k: v for k, v in before["flags"].items() if k != s["flag"]}
    _, verified, _ = sr.set_flag(s, "off")
    assert verified is not None and state["doc"] == before


# --- imajlar GHCR'da, digest'le sabit (DECISIONS 2026-10-29 "İmajlar GHCR'da") ---

COMPOSE = REPO / "deploy" / "otel-demo" / "compose.extras.yaml"
PINNED = r"ghcr\.io/erenbezek/{name}@sha256:[0-9a-f]{{64}}"


def test_images_pinned_by_digest():
    assert re.fullmatch(PINNED.format(name="aiops-quote-gateway"), sr.GATEWAY_IMAGE)
    assert re.fullmatch(PINNED.format(name="aiops-netem"), sr.NETEM_IMAGE)


def test_compose_uses_runner_gateway_image():
    block = re.search(r"\n  quote-gateway:\n(.*?)\n  [a-z-]+:\n", COMPOSE.read_text(), re.S).group(1)
    assert re.findall(r"^    image: (\S+)$", block, re.M) == [sr.GATEWAY_IMAGE]
