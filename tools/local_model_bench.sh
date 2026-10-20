#!/usr/bin/env bash
# Lokal model hız ölçümü (HANDOFF 2026-10-20). llama-bench sabit Docker imajında koşar;
# ham çıktılar repo dışına, ~/cerebrum2/bench_runs/<tarih-saat>-<komut>/ altına yazılır.
# Özet: tools/bench_summary.py <koşu klasörleri...>
#
# Kullanım:
#   tools/local_model_bench.sh matrix [--rounds N] [--models "2B 4B 9B"] [--threads "4 8 12"] [--resume <klasör>]
#   tools/local_model_bench.sh sustained <model> <threads> [--minutes N]
set -euo pipefail

IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:8f3c2cd0808a394d1e7ce02f025f453caacbf163389fe6b6443ec3a1efff96a0"
IMAGE_TAG="full-b11723"
MODELS_DIR="${HOME}/cerebrum2/models"
RUNS_DIR="${HOME}/cerebrum2/bench_runs"
declare -A MODEL_FILES=(
    [2B]="Qwen3.5-2B-Q4_K_M.gguf"
    [4B]="Qwen3.5-4B-Q4_K_M.gguf"
    [9B]="Qwen3.5-9B-Q4_K_M.gguf"
)

# Sınırlar (DECISIONS 2026-10-20): 95 °C üstünde 60 sn'den fazla kalırsa ölçüm durur.
TEMP_LIMIT_C=95
TEMP_LIMIT_SECS=60
SAMPLE_SECS=10

# Tablo hücresinin testleri: girdi okuma, üretim, bütçe (2048+300), ham log (6144+300).
MATRIX_TESTS=(-p 2048 -n 300 -pg 2048,300 -pg 6144,300)
# Sürekli yük: tek iterasyon = bütçe senaryosu.
SUSTAINED_TESTS=(-p 0 -n 0 -pg 2048,300)

die() {
    echo "error: $*" >&2
    exit 1
}

usage() {
    sed -n '7,8p' "$0" | sed 's/^#   /usage: /' >&2
    exit 2
}

# Uyku/boşta askıya alma ölçüm boyunca engellenir; betik kendini systemd-inhibit altında yeniden başlatır.
if [[ -z "${LMB_INHIBITED:-}" ]]; then
    export LMB_INHIBITED=1
    exec systemd-inhibit --what=sleep:idle --who=local_model_bench \
        --why="llama-bench measurement" --mode=block "$0" "$@"
fi

# --- Makine okumaları (sudo'suz) ---

PKG_TEMP_FILE=""
for z in /sys/class/thermal/thermal_zone*; do
    [[ "$(cat "$z/type")" == "x86_pkg_temp" ]] && PKG_TEMP_FILE="$z/temp"
done
[[ -n "$PKG_TEMP_FILE" ]] || die "x86_pkg_temp thermal zone not found"

pkg_temp_c() { echo $(( $(cat "$PKG_TEMP_FILE") / 1000 )); }
ac_online() { cat /sys/class/power_supply/AC0/online; }

# Bütün çekirdeklerin anlık frekans ortalaması ve en yükseği (MHz).
freq_avg_max() {
    awk '{s += $1; if ($1 > m) m = $1} END {printf "%d,%d", s / NR / 1000, m / 1000}' \
        /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq
}

swap_used_kb() { awk '/^SwapTotal/ {t = $2} /^SwapFree/ {f = $2} END {print t - f}' /proc/meminfo; }
mem_avail_kb() { awk '/^MemAvailable/ {print $2}' /proc/meminfo; }

# llama-bench sürecinin belleği (kB): anlık (VmRSS) ve en yüksek (VmHWM). Eşlenen model dosyası dahil;
# cgroup sayacından farklı olarak sayfa önbelleğini hangi konteynerin doldurduğundan etkilenmez.
bench_rss_hwm() {
    local pid
    pid="$(pgrep -x llama-bench | head -1)" || { echo ","; return 0; }
    awk '/^VmRSS/ {r = $2} /^VmHWM/ {h = $2} END {printf "%s,%s", r, h}' "/proc/${pid}/status" 2>/dev/null \
        || echo ","
}

# --- Koşu klasörü, olay kaydı ve izleme ---

RUN=""
MONITOR_PID=""
ACWATCH_PID=""

log_event() {
    echo "$(date --iso-8601=seconds) $*" | tee -a "$RUN/events.log"
}

new_run() {
    local kind="$1"
    RUN="${RUNS_DIR}/$(date +%Y%m%d-%H%M%S)-${kind}"
    mkdir -p "$RUN/raw"
    : > "$RUN/current"
}

# Ortam kaydı: kart "ölçüm başında AC, profil, sıcaklık" istiyor; model dosyalarının hash'i de doğrulanır.
write_env() {
    local file="$1"
    shift
    {
        echo "date=$(date --iso-8601=seconds)"
        echo "command=$*"
        echo "image=${IMAGE}"
        echo "image_tag=${IMAGE_TAG}"
        echo "kernel=$(uname -r)"
        echo "cpu=$(awk -F': ' '/^model name/ {print $2; exit}' /proc/cpuinfo)"
        echo "ac_online=$(ac_online)"
        echo "platform_profile=$(cat /sys/firmware/acpi/platform_profile 2>/dev/null || echo unknown)"
        echo "battery_capacity=$(cat /sys/class/power_supply/BAT0/capacity)"
        echo "battery_status=$(cat /sys/class/power_supply/BAT0/status)"
        echo "charge_end_threshold=$(cat /sys/class/power_supply/BAT0/charge_control_end_threshold)"
        echo "pkg_temp_c=$(pkg_temp_c)"
        echo "freq_avg_max_mhz=$(freq_avg_max)"
        echo "mem_avail_kb=$(mem_avail_kb)"
        echo "swap_used_kb=$(swap_used_kb)"
        echo "docker_running=$(docker ps -q | wc -l)"
        for m in "${!MODEL_FILES[@]}"; do
            echo "model_${m}=${MODEL_FILES[$m]} sha256=$(sha256sum "${MODELS_DIR}/${MODEL_FILES[$m]}" | cut -d' ' -f1)"
        done
    } > "$file"
}

# 10 sn'de bir makine durumu; sıcaklık sınırı aşılırsa ABORT dosyası yazar ve konteyneri durdurur.
monitor_loop() {
    local hot_since="" now temp name
    [[ -s "$RUN/monitor.csv" ]] || echo \
        "ts,pkg_temp_c,freq_avg_mhz,freq_max_mhz,swap_used_kb,mem_avail_kb,ac_online,container,rss_kb,hwm_kb" \
        > "$RUN/monitor.csv"
    while true; do
        now="$(date +%s)"
        temp="$(pkg_temp_c)"
        name="$(cat "$RUN/current" 2>/dev/null || true)"
        echo "${now},${temp},$(freq_avg_max),$(swap_used_kb),$(mem_avail_kb),$(ac_online),${name},$(bench_rss_hwm)" \
            >> "$RUN/monitor.csv"

        if (( temp > TEMP_LIMIT_C )); then
            hot_since="${hot_since:-$now}"
            if (( now - hot_since > TEMP_LIMIT_SECS )); then
                echo "pkg_temp above ${TEMP_LIMIT_C} C for more than ${TEMP_LIMIT_SECS} s at $(date --iso-8601=seconds)" \
                    > "$RUN/ABORT"
                [[ -n "$name" ]] && docker kill "$name" >/dev/null 2>&1 || true
            fi
        else
            hot_since=""
        fi
        sleep "$SAMPLE_SECS"
    done
}

# Saniyede bir priz kontrolü: hücre sırasında priz giderse AC_LOST yazılır ve iş hemen durdurulur
# (bataryada ölçülen hız prizdekiyle karşılaştırılamaz; boşuna batarya harcanmasın).
acwatch_loop() {
    local name
    while true; do
        if [[ "$(ac_online)" != "1" ]]; then
            name="$(cat "$RUN/current" 2>/dev/null || true)"
            if [[ -n "$name" && ! -e "$RUN/AC_LOST" ]]; then
                touch "$RUN/AC_LOST"
                docker kill "$name" >/dev/null 2>&1 || true
            fi
        fi
        sleep 1
    done
}

start_watchers() {
    monitor_loop &
    MONITOR_PID=$!
    acwatch_loop &
    ACWATCH_PID=$!
}

cleanup() {
    local name pid
    name="$(cat "$RUN/current" 2>/dev/null || true)"
    [[ -n "$name" ]] && docker kill "$name" >/dev/null 2>&1 || true
    for pid in "$MONITOR_PID" "$ACWATCH_PID"; do
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}

# Priz yoksa iş başlatmadan bekler; makine bu sırada yüklenmez.
wait_for_ac() {
    [[ "$(ac_online)" == "1" ]] && return 0
    log_event "AC offline; waiting for mains power (no load while waiting)"
    while [[ "$(ac_online)" != "1" ]]; do
        sleep "$SAMPLE_SECS"
    done
    log_event "AC back online; continuing"
}

check_abort() {
    [[ ! -e "$RUN/ABORT" ]] || die "aborted: $(cat "$RUN/ABORT")"
}

# Tek llama-bench çağrısı; JSON satırları $1 dosyasına. Konteyner adı izlemeye bildirilir.
run_bench() {
    local out="$1" model="$2" threads="$3"
    shift 3
    local name="lmb-$$-${RANDOM}"
    echo "$name" > "$RUN/current"
    local rc=0
    docker run --rm --name "$name" -v "${MODELS_DIR}:/models:ro" "$IMAGE" --bench \
        -m "/models/${MODEL_FILES[$model]}" -t "$threads" -r 1 -o jsonl "$@" \
        > "$out" 2> "${out%.jsonl}.stderr" || rc=$?
    : > "$RUN/current"
    return "$rc"
}

# Bir ölçümü priz kopmasına dayanıklı koşar: priz koparsa çıktı .aclost<N> olarak saklanır,
# satır "ac_lost" ile yazılır, priz gelince aynı ölçüm baştan koşulur.
# $1: CSV dosyası, $2: CSV satırının ilk alanları, $3: çıktı dosyası, sonrası run_bench argümanları.
run_resilient() {
    local csv="$1" prefix="$2" out="$3"
    shift 3
    local attempt=0 start temp rc status
    while true; do
        check_abort
        wait_for_ac
        rm -f "$RUN/AC_LOST"
        start="$(date +%s)"
        temp="$(pkg_temp_c)"
        rc=0
        run_bench "$out" "$@" || rc=$?
        status="$rc"
        if [[ -e "$RUN/AC_LOST" ]]; then
            status="ac_lost"
            attempt=$(( attempt + 1 ))
            mv "$out" "${out}.aclost${attempt}"
            mv "${out%.jsonl}.stderr" "${out%.jsonl}.stderr.aclost${attempt}"
        fi
        echo "${prefix},${start},$(date +%s),${temp},${status}" >> "$csv"
        LAST_START_TEMP="$temp"
        check_abort
        if [[ "$status" == "ac_lost" ]]; then
            log_event "AC lost during ${out##*/}; result discarded, will redo"
            continue
        fi
        (( rc == 0 )) || die "llama-bench failed (exit $rc), see ${out%.jsonl}.stderr"
        return 0
    done
}

parse_model() {
    [[ -n "${MODEL_FILES[$1]:-}" ]] || die "unknown model '$1' (known: ${!MODEL_FILES[*]})"
    [[ -f "${MODELS_DIR}/${MODEL_FILES[$1]}" ]] || die "${MODELS_DIR}/${MODEL_FILES[$1]} not found"
}

cmd_matrix() {
    local rounds=3 models="2B 4B 9B" threads_list="4 8 12" resume=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --rounds) rounds="$2"; shift 2 ;;
            --models) models="$2"; shift 2 ;;
            --threads) threads_list="$2"; shift 2 ;;
            --resume) resume="$2"; shift 2 ;;
            *) usage ;;
        esac
    done
    local m t
    for m in $models; do parse_model "$m"; done

    local cmdline="matrix --rounds $rounds --models '$models' --threads '$threads_list'"
    if [[ -n "$resume" ]]; then
        [[ -f "$resume/cells.csv" ]] || die "$resume/cells.csv not found"
        RUN="$(cd "$resume" && pwd -P)"
        : > "$RUN/current"
        rm -f "$RUN/AC_LOST"
        wait_for_ac
        write_env "$RUN/env_resume_$(date +%Y%m%d-%H%M%S).txt" "$cmdline --resume $resume"
    else
        new_run matrix
        wait_for_ac
        write_env "$RUN/env.txt" "$cmdline"
        echo "round,model,threads,start_ts,end_ts,start_temp_c,exit_code" > "$RUN/cells.csv"
    fi
    trap cleanup EXIT
    start_watchers
    echo "run dir: $RUN"

    # Tekrarlar arka arkaya değil: tablo baştan sona $rounds tur koşulur.
    # --resume: geçerli (çıkış kodu 0) kaydı olan hücreler atlanır.
    local r
    for (( r = 1; r <= rounds; r++ )); do
        for m in $models; do
            for t in $threads_list; do
                if grep -q "^${r},${m},${t},.*,0$" "$RUN/cells.csv"; then
                    continue
                fi
                echo "$(date +%T) round $r/$rounds model $m threads $t (start $(pkg_temp_c) C)"
                run_resilient "$RUN/cells.csv" "${r},${m},${t}" "$RUN/raw/r${r}_${m}_t${t}.jsonl" \
                    "$m" "$t" "${MATRIX_TESTS[@]}"
            done
        done
    done
    echo "ok: matrix done; summary: tools/bench_summary.py $RUN"
}

cmd_sustained() {
    [[ $# -ge 2 ]] || usage
    local model="$1" threads="$2" minutes=30
    shift 2
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --minutes) minutes="$2"; shift 2 ;;
            *) usage ;;
        esac
    done
    parse_model "$model"

    new_run sustained
    wait_for_ac
    write_env "$RUN/env.txt" "sustained $model $threads --minutes $minutes"
    echo "iter,model,threads,start_ts,end_ts,start_temp_c,exit_code" > "$RUN/iterations.csv"
    trap cleanup EXIT
    start_watchers
    echo "run dir: $RUN"

    # İterasyonlar arka arkaya. Priz kopmasıyla geçen süre 30 dk'ya sayılmaz (bitiş o kadar uzar).
    local end=$(( $(date +%s) + minutes * 60 )) i=0 before t0 valid
    while (( $(date +%s) < end )); do
        i=$(( i + 1 ))
        before="$(wc -l < "$RUN/iterations.csv")"
        t0="$(date +%s)"
        run_resilient "$RUN/iterations.csv" "${i},${model},${threads}" "$RUN/raw/i$(printf '%04d' "$i").jsonl" \
            "$model" "$threads" "${SUSTAINED_TESTS[@]}"
        # Priz koptuysa (birden fazla deneme), geçerli denemenin dışındaki süre (iptal + bekleme) bitişe eklenir.
        if (( $(wc -l < "$RUN/iterations.csv") - before > 1 )); then
            valid="$(tail -1 "$RUN/iterations.csv" | awk -F, '{print $5 - $4}')"
            end=$(( end + $(date +%s) - t0 - valid ))
        fi
        echo "$(date +%T) iter $i done (start ${LAST_START_TEMP} C)"
    done
    echo "ok: sustained done; summary: tools/bench_summary.py <matrix dirs...> $RUN"
}

[[ $# -ge 1 ]] || usage
cmd="$1"
shift
case "$cmd" in
    matrix) cmd_matrix "$@" ;;
    sustained) cmd_sustained "$@" ;;
    *) usage ;;
esac
