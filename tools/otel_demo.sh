#!/usr/bin/env bash
# OTel Demo'yu repo dışına getirir, sabit sürümü doğrular ve minimal modda çalıştırır (DECISIONS 2026-10-18).
# Kullanım: tools/otel_demo.sh fetch | up [--raw] | down | config [--raw] [docker compose config argümanları]
set -euo pipefail

# Sürüm burada sabit: etiket taşınırsa commit kontrolü yakalar.
DEMO_REPO_URL="https://github.com/open-telemetry/opentelemetry-demo.git"
DEMO_TAG="3.1.0"
DEMO_COMMIT="dedc0178918e260823323b8d95005a8cb924b007"
DEMO_DIR="${HOME}/cerebrum2/otel-demo"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEPLOY_DIR="${REPO_ROOT}/deploy/otel-demo"
EXTRAS_FILE="${DEPLOY_DIR}/compose.extras.yaml"
RAW_FILE="${DEPLOY_DIR}/compose.raw.yaml"
COLLECTOR_EXTRAS="${DEPLOY_DIR}/otelcol-config-extras.yml"
COLLECTOR_RAW="${DEPLOY_DIR}/otelcol-config-raw.yml"
JAEGER_EXTRAS="${DEPLOY_DIR}/jaeger-config-extras.yml"
# Bizim flag'lerimiz (quote-gateway): upstream flag dosyasıyla birleştirilir (reset_flag_file).
FLAGD_EXTRAS="${DEPLOY_DIR}/flagd-extras.json"
# flagd ve flagd-ui bu klasörü bağlar (compose.extras.yaml'da aynı yol).
FLAGD_RUNTIME_DIR="${HOME}/cerebrum2/runtime/flagd"
# Collector dosya çıkışı (compose.extras.yaml'da aynı yol): filtered/ her zaman, raw/ sadece --raw ile.
TELEMETRY_DIR="${HOME}/cerebrum2/telemetry"

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

# Minimal mod: demonun compose.yaml + compose.observability.yaml, sonra bizim katmanımız (demonun boş
# compose.extras.yaml'ı yüklenmez); RAW=1 ise en son compose.raw.yaml. Env dosyaları Makefile'daki sırayla.
# Kabuk değişkenleri --env-file'ı ezer:
# - DEMO_VERSION: upstream .env'de "latest".
# - OTEL_COLLECTOR_CONFIG_EXTRAS: demonun boş collector extras'ı yerine bizimki.
# - OTEL_COLLECTOR_USER: eren + docker grubu (dosyalar eren'in olsun, Docker soketi okunabilsin).
# - OTEL_COLLECTOR_CONFIG_RAW: sadece compose.raw.yaml kullanır.
# - JAEGER_CONFIG_EXTRAS: Jaeger'in ikinci ayar dosyası (diske yazma; depolama kartı).
RAW=0
compose() {
    local f files=(-f compose.yaml -f compose.observability.yaml -f "$EXTRAS_FILE")
    (( RAW )) && files+=(-f "$RAW_FILE")
    for f in "$EXTRAS_FILE" "$RAW_FILE" "$COLLECTOR_EXTRAS" "$COLLECTOR_RAW" "$JAEGER_EXTRAS"; do
        [[ -f "$f" ]] || die "$f not found"
    done
    local docker_gid
    docker_gid="$(getent group docker | cut -d: -f3)" || die "docker group not found"
    (
        cd "$DEMO_DIR"
        DEMO_VERSION="$DEMO_TAG" \
        OTEL_COLLECTOR_CONFIG_EXTRAS="$COLLECTOR_EXTRAS" \
        OTEL_COLLECTOR_CONFIG_RAW="$COLLECTOR_RAW" \
        JAEGER_CONFIG_EXTRAS="$JAEGER_EXTRAS" \
        OTEL_COLLECTOR_USER="$(id -u):${docker_gid}" \
            docker compose --env-file .env --env-file .env.override "${files[@]}" "$@"
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

# Her up bütün flag'ler kapalı, sabit commit'teki haliyle başlar. flagd-ui dosyayı root olarak
# yeniden yazmış olabilir: üzerine kopyalamak yerine silinir (klasör bizim, sudo gerekmez).
# Dosya = upstream demo.flagd.json + bizim flagd-extras.json (upstream'in sonuna eklenir; aynı ad iki dosyada da
# varsa hata, upstream'e dokunulmaz; Eren onayı 2026-10-28).
reset_flag_file() {
    mkdir -p "$FLAGD_RUNTIME_DIR"
    rm -f "${FLAGD_RUNTIME_DIR}/demo.flagd.json"
    merge_flag_files "${DEMO_DIR}/src/flagd/demo.flagd.json" "$FLAGD_EXTRAS" "${FLAGD_RUNTIME_DIR}/demo.flagd.json"
    chmod 0644 "${FLAGD_RUNTIME_DIR}/demo.flagd.json"
}

merge_flag_files() {
    python3 - "$1" "$2" "$3" <<'PY'
import json, sys
upstream, extras, out = sys.argv[1:4]
doc = json.load(open(upstream, encoding="utf-8"))
ours = json.load(open(extras, encoding="utf-8"))["flags"]
dup = sorted(set(doc["flags"]) & set(ours))
if dup:
    sys.exit(f"error: flags defined in both {upstream} and {extras}: {dup}")
doc["flags"].update(ours)
with open(out, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=2)
    f.write("\n")
PY
}

# Klasörler collector'dan önce eren'in kullanıcısıyla açılır (Docker eksik bağlama klasörünü root'la açar).
prepare_telemetry_dirs() {
    mkdir -p "${TELEMETRY_DIR}/filtered" "${TELEMETRY_DIR}/raw"
}

cmd_up() {
    require_clone
    verify_clone
    reset_flag_file
    prepare_telemetry_dirs
    (( RAW )) && echo "warning: unfiltered output on; ${TELEMETRY_DIR}/raw holds answer-revealing data, delete it after use" >&2
    # Bayraklar demonun Makefile'ındaki start-minimal ile aynı.
    compose up --force-recreate --remove-orphans --detach
    opensearch_retention
}

# OpenSearch saklaması (depolama kartı, DECISIONS 2026-10-25): ISM kuralı 7 günden eski otel-logs-* indeksini
# siler. Kural volume'de kalıcı; yoksa yüklenir, varsa dokunulmaz. ism_template yalnız kuraldan sonra açılan
# indekslere uyar; açılışta kuraldan önce açılmış indeks olabileceği için kurala bağlanmamış otel-logs-* indeksleri
# ayrıca bağlanır (zaten bağlı olanlar için OpenSearch "failed" der; zararsız). ISM 5 dk'da bir kontrol eder;
# günlük indeks açılışından ~7 gün sonra silinir.
OPENSEARCH_URL="http://127.0.0.1:9200"
ISM_POLICY="otel-logs-retention"
opensearch_retention() {
    local i
    for (( i = 0; i < 60; i++ )); do
        curl -fsS "${OPENSEARCH_URL}/_cluster/health" 2>/dev/null | grep -qE '"status":"(green|yellow)"' && break
        sleep 3
    done
    (( i < 60 )) || die "OpenSearch not healthy after 180 s; ISM policy not applied"
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' "${OPENSEARCH_URL}/_plugins/_ism/policies/${ISM_POLICY}")"
    if [[ "$code" == "404" ]]; then
        curl -fsS -X PUT -H 'Content-Type: application/json' "${OPENSEARCH_URL}/_plugins/_ism/policies/${ISM_POLICY}" -d '{
          "policy": {
            "description": "otel-logs-*: delete indices older than 7 days (aiops_rca storage card)",
            "default_state": "hot",
            "states": [
              {"name": "hot", "actions": [], "transitions": [{"state_name": "delete", "conditions": {"min_index_age": "7d"}}]},
              {"name": "delete", "actions": [{"delete": {}}], "transitions": []}
            ],
            "ism_template": [{"index_patterns": ["otel-logs-*"], "priority": 100}]
          }
        }' >/dev/null || die "ISM policy upload failed"
        echo "ok: ISM policy ${ISM_POLICY} created"
    elif [[ "$code" == "200" ]]; then
        echo "ok: ISM policy ${ISM_POLICY} present"
    else
        die "ISM policy check returned HTTP $code"
    fi
    curl -fsS -X POST -H 'Content-Type: application/json' "${OPENSEARCH_URL}/_plugins/_ism/add/otel-logs-*" \
        -d "{\"policy_id\": \"${ISM_POLICY}\"}" >/dev/null || die "ISM add to existing indices failed"
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
    echo "usage: $0 fetch | up [--raw] | down | config [--raw] [docker compose config args]" >&2
    exit 2
}

[[ $# -ge 1 ]] || usage
cmd="$1"
shift
if [[ "$cmd" == "up" || "$cmd" == "config" ]] && [[ "${1:-}" == "--raw" ]]; then
    RAW=1
    shift
fi
case "$cmd" in
    fetch)  [[ $# -eq 0 ]] || usage; cmd_fetch ;;
    up)     [[ $# -eq 0 ]] || usage; cmd_up ;;
    down)   [[ $# -eq 0 ]] || usage; cmd_down ;;
    config) cmd_config "$@" ;;
    *) usage ;;
esac
