"""Checks that our collector pipelines keep every upstream component.

Kullanım: python tools/check_collector_pipelines.py <upstream.json> <ours.json>
İki dosya da collector'ın `print-config --format=json` çıktısı (birleşik ayar). Collector katmanları
listeleri değiştirdiği için (eklemediği için) upstream'deki her receiver, processor ve exporter bizim aynı
adlı pipeline'da olmalı; processor'lar upstream'deki sırayı korumalı (aralara ekleme serbest).
Çıkış kodu: 0 eksik yok, 1 eksik var, 2 kullanım/girdi hatası.
"""
import json
import sys


def is_subsequence(needle, haystack):
    it = iter(haystack)
    return all(item in it for item in needle)


def compare(upstream, ours):
    problems = []
    up_pipes = upstream.get("service", {}).get("pipelines", {})
    our_pipes = ours.get("service", {}).get("pipelines", {})
    for name, up in sorted(up_pipes.items()):
        mine = our_pipes.get(name)
        if mine is None:
            problems.append(f"{name}: pipeline missing")
            continue
        for kind in ("receivers", "processors", "exporters"):
            missing = [c for c in up.get(kind) or [] if c not in (mine.get(kind) or [])]
            if missing:
                problems.append(f"{name}: {kind} missing {missing}")
        up_proc, my_proc = up.get("processors") or [], mine.get("processors") or []
        if all(p in my_proc for p in up_proc) and not is_subsequence(up_proc, my_proc):
            problems.append(f"{name}: processor order differs from upstream {up_proc} -> {my_proc}")
    return problems, sorted(up_pipes)


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        upstream = json.loads(open(argv[1], encoding="utf-8").read())
        ours = json.loads(open(argv[2], encoding="utf-8").read())
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    problems, checked = compare(upstream, ours)
    for p in problems:
        print(f"MISSING {p}")
    print(f"checked pipelines: {', '.join(checked)}; problems: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
