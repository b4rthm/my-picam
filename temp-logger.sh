#!/bin/bash
#
# Log the CPU temperature of the Raspberry Pi once a minute.
#
# The log contains one line per measurement:
#
#     temp=45.3 max_temp=48.1
#
# The maximum temperature is kept in a separate state file, so it survives
# a restart of this script.
#
set -u

# Force a consistent number format: without this, a German locale makes
# awk print "45,8" instead of "45.8" and the comparison below breaks.
export LC_ALL=C

DIR="${PICAM_LOG_DIR:-/home/pi/my-picam/logs}"
FILE="$DIR/temp.log"
STATE_FILE="$DIR/temp_max"
INTERVAL="${PICAM_TEMP_INTERVAL:-60}"

mkdir -p "$DIR"

read_temp() {
    if command -v vcgencmd >/dev/null 2>&1; then
        vcgencmd measure_temp 2>/dev/null | sed -n "s/^temp=\([0-9][0-9.]*\)'C$/\1/p"
    else
        # Fall back to the thermal zone (works on any Linux board).
        for zone in /sys/class/thermal/thermal_zone*/temp; do
            [ -r "$zone" ] || continue
            awk '{printf "%.1f\n", $1/1000}' "$zone" 2>/dev/null && break
        done
    fi
}

# Restore the maximum temperature from the state file.
if [ -f "$STATE_FILE" ]; then
    max_temp=$(cut -d' ' -f1 "$STATE_FILE" 2>/dev/null)
else
    max_temp="0.0"
fi
[ -n "${max_temp:-}" ] || max_temp="0.0"

# Truncate the log if it grew too large (keep the last ~2000 lines).
if [ -f "$FILE" ] && [ "$(wc -l < "$FILE")" -gt 2000 ]; then
    tail -n 2000 "$FILE" > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"
fi

while true; do
    curr_temp=$(read_temp)

    if [ -n "$curr_temp" ]; then
        # Compare as floats, the temperature is not an integer.
        if awk "BEGIN{exit !($curr_temp > $max_temp)}" 2>/dev/null; then
            max_temp="$curr_temp"
            echo "$max_temp" > "$STATE_FILE"
        fi
        echo "temp=$curr_temp max_temp=$max_temp" >> "$FILE"
    else
        echo "temp=unknown max_temp=$max_temp" >> "$FILE"
    fi

    sleep "$INTERVAL"
done
