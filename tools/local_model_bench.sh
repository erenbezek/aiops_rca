#!/usr/bin/env bash
# Lokal model hız ölçümü (HANDOFF 2026-10-20). llama-bench sabit Docker imajında koşar;
# ham çıktılar repo dışına, ~/cerebrum2/bench_runs/<tarih-saat>-<komut>/ altına yazılır.
# Özet: tools/bench_summary.py <koşu klasörü> [<sustained klasörü>]
#
# Kullanım:
#   tools/local_model_bench.sh matrix [--rounds N] [--models "2B 4B 9B"] [--threads "4 8 12"]
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

# Çalışan konteynerin cgroup'undaki en yüksek bellek (bayt); konteyner yoksa boş.
container_mem_peak() {
    local name="$1" id
    id="$(docker inspect --format '{{.Id}}' "$name" 2>/dev/null)" || return 0
    cat "/sys/fs/cgroup/system.slice/docker-${id}.scope/memory.peak" 2>/dev/null || true
}

# --- Koşu klasörü ve izleme ---

RUN=""
MONITOR_PID=""

start_run() {
    local kind="$1"
    RUN="${RUNS_DIR}/$(date +%Y%m%d-%H%M%S)-${kind}"
    mkdir -p "$RUN/raw"
    : > "$RUN/current"
}

# Ortam kaydı: kart "ölçüm başında AC, profil, sıcaklık" istiyor; model dosyalarının hash'i de doğrulanır.
write_env() {
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
    } > "$RUN/env.txt"
}

# 10 sn'de bir makine durumu; sıcaklık sınırı aşılırsa ABORT dosyası yazar ve konteyneri durdurur.
monitor_loop() {
    local hot_since="" now temp name peak
    echo "ts,pkg_temp_c,freq_avg_mhz,freq_max_mhz,swap_used_kb,mem_avail_kb,ac_online,container,mem_peak_bytes" \
        > "$RUN/monitor.csv"
    while true; do
        now="$(date +%s)"
        temp="$(pkg_temp_c)"
        name="$(cat "$RUN/current" 2>/dev/null || true)"
        peak=""
        [[ -n "$name" ]] && peak="$(container_mem_peak "$name")"
        echo "${now},${temp},$(freq_avg_max),$(swap_used_kb),$(mem_avail_kb),$(ac_online),${name},${peak}" \
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

start_monitor() {
    monitor_loop &
    MONITOR_PID=$!
}

stop_monitor() {
    [[ -n "$MONITOR_PID" ]] && kill "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" 2>/dev/null || true
}

cleanup() {
    local name
    name="$(cat "$RUN/current" 2>/dev/null || true)"
    [[ -n "$name" ]] && docker kill "$name" >/dev/null 2>&1 || true
    stop_monitor
}

# Ölçüm her hücreden önce koşulları kontrol eder; bozulursa koşu durur (sonuçlar yarım ama kayıtlı).
check_conditions() {
    [[ ! -e "$RUN/ABORT" ]] || die "aborted: $(cat "$RUN/ABORT")"
    [[ "$(ac_online)" == "1" ]] || die "AC adapter offline; measurements only on mains power"
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

parse_model() {
    [[ -n "${MODEL_FILES[$1]:-}" ]] || die "unknown model '$1' (known: ${!MODEL_FILES[*]})"
    [[ -f "${MODELS_DIR}/${MODEL_FILES[$1]}" ]] || die "${MODELS_DIR}/${MODEL_FILES[$1]} not found"
}

cmd_matrix() {
    local rounds=3 models="2B 4B 9B" threads_list="4 8 12"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --rounds) rounds="$2"; shift 2 ;;
            --models) models="$2"; shift 2 ;;
            --threads) threads_list="$2"; shift 2 ;;
            *) usage ;;
        esac
    done
    local m t
    for m in $models; do parse_model "$m"; done

    start_run matrix
    [[ "$(ac_online)" == "1" ]] || die "AC adapter offline; measurements only on mains power"
    write_env "matrix --rounds $rounds --models '$models' --threads '$threads_list'"
    trap cleanup EXIT
    start_monitor
    echo "run dir: $RUN"
    echo "round,model,threads,start_ts,end_ts,start_temp_c,exit_code" > "$RUN/cells.csv"

    # Tekrarlar arka arkaya değil: tablo baştan sona $rounds tur koşulur.
    local r start temp rc out
    for (( r = 1; r <= rounds; r++ )); do
        for m in $models; do
            for t in $threads_list; do
                check_conditions
                start="$(date +%s)"
                temp="$(pkg_temp_c)"
                out="$RUN/raw/r${r}_${m}_t${t}.jsonl"
                echo "$(date +%T) round $r/$rounds model $m threads $t (start ${temp} C)"
                rc=0
                run_bench "$out" "$m" "$t" "${MATRIX_TESTS[@]}" || rc=$?
                echo "${r},${m},${t},${start},$(date +%s),${temp},${rc}" >> "$RUN/cells.csv"
                check_conditions
                (( rc == 0 )) || die "llama-bench failed (exit $rc), see ${out%.jsonl}.stderr"
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

    start_run sustained
    [[ "$(ac_online)" == "1" ]] || die "AC adapter offline; measurements only on mains power"
    write_env "sustained $model $threads --minutes $minutes"
    trap cleanup EXIT
    start_monitor
    echo "run dir: $RUN"
    echo "iter,model,threads,start_ts,end_ts,start_temp_c,exit_code" > "$RUN/iterations.csv"

    # İterasyonlar arka arkaya; aralarındaki boşluk (konteyner başlatma + model yükleme) kayıtta görünür.
    local end=$(( $(date +%s) + minutes * 60 )) i=0 start temp rc out
    while (( $(date +%s) < end )); do
        check_conditions
        i=$(( i + 1 ))
        start="$(date +%s)"
        temp="$(pkg_temp_c)"
        out="$RUN/raw/i$(printf '%04d' "$i").jsonl"
        rc=0
        run_bench "$out" "$model" "$threads" "${SUSTAINED_TESTS[@]}" || rc=$?
        echo "${i},${model},${threads},${start},$(date +%s),${temp},${rc}" >> "$RUN/iterations.csv"
        check_conditions
        (( rc == 0 )) || die "llama-bench failed (exit $rc), see ${out%.jsonl}.stderr"
        echo "$(date +%T) iter $i done (start ${temp} C)"
    done
    echo "ok: sustained done; summary: tools/bench_summary.py <matrix dir> $RUN"
}

[[ $# -ge 1 ]] || usage
cmd="$1"
shift
case "$cmd" in
    matrix) cmd_matrix "$@" ;;
    sustained) cmd_sustained "$@" ;;
    *) usage ;;
esac
