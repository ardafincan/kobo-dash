#!/bin/sh
# Kobo e-ink dashboard loop.
#
# Fetches the rendered PNGs from the Mac Mini over Wi-Fi every FETCH_INTERVAL,
# and draws the rotating sequence (read from manifest.json) every
# DISPLAY_INTERVAL. Wi-Fi is only up briefly during a fetch; it is off the rest
# of the time to save battery.
#
# Rules: never blank the screen, never exit on a network error. If a fetch
# fails, keep the existing images and keep rotating.
#
# Lives at /mnt/onboard/.adds/dash/run.sh . Launched from NickelMenu (Step 7).
# Uses the Wi-Fi scripts bundled with KOReader and NiLuJe's FBInk.

DASH=/mnt/onboard/.adds/dash
KO=/mnt/onboard/.adds/koreader
FB="$DASH/fbink"
SERVER="http://192.168.1.2:8080"
SCREENS=/tmp/screens
LOG="$DASH/dash.log"

DISPLAY_INTERVAL="${DISPLAY_INTERVAL:-300}"   # seconds between screens (5 min)
FETCH_INTERVAL="${FETCH_INTERVAL:-900}"       # seconds between fetches (15 min)
KEEP_WIFI="${KEEP_WIFI:-0}"                   # 1 = leave Wi-Fi up (debug only)

# Environment the KOReader Wi-Fi scripts need on the Clara 2E (goldfinch).
export INTERFACE=mlan0 WIFI_MODULE=moal PLATFORM=mx6sll-ntx PRODUCT=goldfinch

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# Fully stop the Kobo software stack the way KOReader does. A plain
# `killall nickel` is not enough — nickel's supervisors respawn it. We kill the
# whole set and wait for nickel to actually die.
stop_nickel() {
    sync
    killall -q -TERM nickel hindenburg sickel fickel strickel fontickel adobehost \
        foxitpdf iink dhcpcd-dbus dhcpcd bluealsa bluetoothd fmon nanoclock.lua \
        memorylogger QtWebEngineProcess 2>/dev/null
    t=0
    while pkill -0 nickel 2>/dev/null; do
        [ "$t" -ge 20 ] && break
        usleep 250000
        t=$((t + 1))
    done
    rm -f /tmp/nickel-hardware-status
}

mkdir -p "$SCREENS"
# Keep the log from growing without bound across restarts.
[ -f "$LOG" ] && tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
log "=== dashboard starting (display=${DISPLAY_INTERVAL}s fetch=${FETCH_INTERVAL}s keep_wifi=${KEEP_WIFI}) ==="

# Take over from Nickel (if running) and silence the status LED.
stop_nickel
echo 0 > /sys/class/leds/GLED/brightness 2>/dev/null

wifi_up() {
    ( cd "$KO" && ./restore-wifi-async.sh >/dev/null 2>&1 )
    i=0
    while [ $i -lt 30 ]; do
        if wget -q -T 4 -O "$SCREENS/manifest.json" "$SERVER/manifest.json" 2>/dev/null; then
            return 0
        fi
        sleep 1
        i=$((i + 1))
    done
    return 1
}

wifi_down() {
    [ "$KEEP_WIFI" = "1" ] && return 0
    ( cd "$KO" && ./disable-wifi.sh >/dev/null 2>&1 )
}

parse_and_fetch() {
    flat=$(tr -d '\n\r' < "$SCREENS/manifest.json")
    newhash=$(printf '%s' "$flat" | sed 's/.*"hash"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
    seqline=$(printf '%s' "$flat" | sed 's/.*"sequence"[[:space:]]*:[[:space:]]*\[\([^]]*\)\].*/\1/')
    # Entries look like "day.png:900" (screen:seconds). Keep them verbatim.
    printf '%s' "$seqline" | tr ',' '\n' | sed 's/[" ]//g' | grep -E '\.png' > "$SCREENS/seq.list"
    log "sequence: $(tr '\n' ' ' < "$SCREENS/seq.list")"

    oldhash=$(cat "$SCREENS/.hash" 2>/dev/null)
    if [ "$newhash" != "$oldhash" ]; then
        log "hash changed; downloading images"
        for png in $(sed 's/:.*//' "$SCREENS/seq.list" | sort -u); do
            if wget -q -T 8 -O "$SCREENS/$png.tmp" "$SERVER/$png" 2>/dev/null; then
                mv "$SCREENS/$png.tmp" "$SCREENS/$png"
                log "fetched $png"
            else
                rm -f "$SCREENS/$png.tmp"
                log "FAILED to fetch $png (keeping old)"
            fi
        done
        echo "$newhash" > "$SCREENS/.hash"
    else
        log "hash unchanged; keeping images"
    fi
}

fetch_cycle() {
    log "fetch: bringing Wi-Fi up"
    if wifi_up; then
        parse_and_fetch
    else
        log "fetch: Wi-Fi/manifest failed; keeping existing screens"
    fi
    wifi_down
    log "fetch: Wi-Fi down"
}

# Initial fetch, then the display loop.
fetch_cycle
last_fetch=$(date +%s)

idx=0
while true; do
    now=$(date +%s)
    if [ $((now - last_fetch)) -ge "$FETCH_INTERVAL" ]; then
        fetch_cycle
        last_fetch=$(date +%s)
    fi

    nap="$DISPLAY_INTERVAL"
    if [ -s "$SCREENS/seq.list" ]; then
        count=$(wc -l < "$SCREENS/seq.list")
        entry=$(sed -n "$(( idx % count + 1 ))p" "$SCREENS/seq.list")
        item="${entry%%:*}"          # screen name
        secs="${entry##*:}"          # per-slot seconds
        case "$secs" in
            ''|*[!0-9]*) secs="$DISPLAY_INTERVAL" ;;   # no/invalid duration -> default
        esac
        nap="$secs"
        if [ -f "$SCREENS/$item" ]; then
            "$FB" -f -c -g file="$SCREENS/$item" >/dev/null 2>&1
            bat=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null)
            log "drew $item for ${secs}s (battery ${bat}%)"
        else
            log "missing $item; skip"
        fi
        idx=$(( (idx + 1) % count ))
    else
        log "no sequence yet; skip"
    fi

    echo 0 > /sys/class/leds/GLED/brightness 2>/dev/null
    sleep "$nap"
done
