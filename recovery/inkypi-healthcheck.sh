#!/bin/bash
# Reboot the Pi if InkyPi's refresh loop has gone quiet.
#
# InkyPi logs "Running interval refresh check" every playlist cycle, whether
# or not the display changed and whether or not the network is up. If that
# heartbeat is missing from the journal for STALE_MINUTES, the app (or the
# whole Pi) is wedged, so reboot.
#
# Reboot-loop protection: nothing happens until the Pi has been up for
# STALE_MINUTES, so there is at most one reboot per STALE_MINUTES.

STALE_MINUTES="${STALE_MINUTES:-90}"   # keep well above your plugin cycle interval
SERVICE="${SERVICE:-inkypi}"

uptime_minutes=$(( $(cut -d. -f1 /proc/uptime) / 60 ))
if [ "$uptime_minutes" -lt "$STALE_MINUTES" ]; then
    exit 0
fi

if journalctl -u "$SERVICE" --since "${STALE_MINUTES} min ago" --no-pager -q \
        | grep -q "Running interval refresh check"; then
    exit 0
fi

echo "No InkyPi refresh heartbeat for ${STALE_MINUTES} min (uptime ${uptime_minutes} min) - rebooting"
/usr/bin/systemctl reboot
