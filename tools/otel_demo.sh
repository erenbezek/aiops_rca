#!/usr/bin/env bash
# OTel Demo'yu repo dışına getirir, sabit sürümü doğrular ve minimal modda çalıştırır (DECISIONS 2026-10-18).
# Kullanım: tools/otel_demo.sh fetch|up|down|config
set -euo pipefail

# Sürüm burada sabit: etiket taşınırsa commit kontrolü yakalar.
DEMO_REPO_URL="https://github.com/open-telemetry/opentelemetry-demo.git"
DEMO_TAG="3.1.0"
DEMO_COMMIT="dedc0178918e260823323b8d95005a8cb924b007"
DEMO_DIR="${HOME}/cerebrum2/otel-demo"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
EXTRAS_FILE="${REPO_ROOT}/deploy/otel-demo/compose.extras.yaml"

die() {
    echo "error: $*" >&2
    exit 1
}

require_clone() {
    [[ -e "$DEMO_DIR" ]] || die "$DEMO_DIR not found; run '$0 fetch' first"
}

# Klon doğru commit'te ve temiz mi? Değilse hata verir; hiçbir şeyi silmez, düzeltmez.
verify_clone() {
    git -C "$DEMO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || die "$DEMO_DIR exists but is not a git work tree; fix or remove it manually"

    # Klasör kendi reposunun kökü olmalı; yoksa üst klasördeki bir repo yanlış hata mesajı üretir.
    local top
    top="$(git -C "$DEMO_DIR" rev-parse --show-toplevel)"
    [[ "$top" == "$(cd "$DEMO_DIR" && pwd -P)" ]] \
        || die "$DEMO_DIR is not a clone itself, it is inside the repo at $top; fix or remove it manually"

    local head
    head="$(git -C "$DEMO_DIR" rev-parse HEAD)"
    [[ "$head" == "$DEMO_COMMIT" ]] \
        || die "$DEMO_DIR is at $head, expected $DEMO_COMMIT (tag $DEMO_TAG); fix it manually"

    # --porcelain izlenmeyen dosyaları da gösterir; upstream'in .gitignore'u dışındaki her değişiklik hata.
    # --no-optional-locks: status .git/index'i yeniden yazmasın; kontrol klonda hiçbir şeyi değiştirmez.
    local changes
    changes="$(git --no-optional-locks -C "$DEMO_DIR" status --porcelain)"
    [[ -z "$changes" ]] \
        || die "$DEMO_DIR has local changes (upstream files must stay untouched):"$'\n'"$changes"
}

# Minimal mod: demonun compose.yaml + compose.observability.yaml, en son bizim katmanımız
# (demonun boş compose.extras.yaml'ı yüklenmez). Env dosyaları Makefile'daki sırayla.
# DEMO_VERSION açıkça verilir: upstream .env'de "latest"; kabuk değişkeni --env-file'ı ezer.
compose() {
    [[ -f "$EXTRAS_FILE" ]] || die "$EXTRAS_FILE not found"
    (
        cd "$DEMO_DIR"
        DEMO_VERSION="$DEMO_TAG" docker compose \
            --env-file .env --env-file .env.override \
            -f compose.yaml -f compose.observability.yaml -f "$EXTRAS_FILE" \
            "$@"
    )
}

cmd_fetch() {
    if [[ -e "$DEMO_DIR" ]]; then
        verify_clone
        echo "ok: $DEMO_DIR already at $DEMO_TAG ($DEMO_COMMIT), clean; nothing to do"
        return 0
    fi

    echo "cloning $DEMO_REPO_URL (tag $DEMO_TAG) into $DEMO_DIR"
    # autocrlf=false: betikler CRLF'ye dönmesin (OTEL_DEMO.md, Kurulum notları).
    git -c core.autocrlf=false -c advice.detachedHead=false \
        clone --branch "$DEMO_TAG" "$DEMO_REPO_URL" "$DEMO_DIR"
    git -C "$DEMO_DIR" config core.autocrlf false
    verify_clone
    echo "ok: cloned $DEMO_TAG ($DEMO_COMMIT)"
}

cmd_up() {
    require_clone
    verify_clone
    # Bayraklar demonun Makefile'ındaki start-minimal ile aynı.
    compose up --force-recreate --remove-orphans --detach
}

# Durdurur; volume silmez. Klon kirli olsa da çalışır (durdurmak hiçbir zaman engellenmesin).
cmd_down() {
    require_clone
    compose down --remove-orphans
}

# up'ın kullandığı dosya ve env'lerle birleşmiş compose ayarını basar; ek argümanlar
# docker compose config'e geçer (ör. --format json).
cmd_config() {
    require_clone
    verify_clone
    compose config "$@"
}

usage() {
    echo "usage: $0 fetch|up|down|config [docker compose config args]" >&2
    exit 2
}

[[ $# -ge 1 ]] || usage
cmd="$1"
shift
case "$cmd" in
    fetch)  [[ $# -eq 0 ]] || usage; cmd_fetch ;;
    up)     [[ $# -eq 0 ]] || usage; cmd_up ;;
    down)   [[ $# -eq 0 ]] || usage; cmd_down ;;
    config) cmd_config "$@" ;;
    *) usage ;;
esac
