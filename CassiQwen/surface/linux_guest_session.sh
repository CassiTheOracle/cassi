#!/usr/bin/env bash
set -Eeuo pipefail

session_id=cassi-surface-01
account=cassi-surface
home=/home/cassi-surface
runtime=/run/user/1000/$session_id
config=$home/.config/cassi-surface

if [[ $# != 2 || $2 != "$session_id" || $(id -un) != "$account" || $(id -u) != 1000 ]]; then
    echo 'Expected the dedicated Cassi account and session identifier' >&2
    exit 2
fi

export HOME=$home USER=$account LOGNAME=$account PATH=/usr/local/bin:/usr/bin:/bin
export DISPLAY=:1 XAUTHORITY=$runtime/Xauthority XDG_RUNTIME_DIR=$runtime
export DBUS_SESSION_BUS_ADDRESS=unix:path=$runtime/bus
export PULSE_SERVER=unix:$runtime/pulse/native PULSE_SINK=cassi.surface.$session_id.output
unset WAYLAND_DISPLAY WSL_DISTRO_NAME WSL_INTEROP WSLENV

ready() {
    [[ -S $runtime/rfb.sock && -S $runtime/bus && -S $runtime/pulse/native ]] &&
        /usr/bin/xset q >/dev/null 2>&1
}

case $1 in
    ready)
        ready
        ;;
    stop)
        [[ -f $runtime/owner.pid ]] || exit 0
        read -r owner_pid < "$runtime/owner.pid"
        [[ $owner_pid =~ ^[0-9]+$ && -r /proc/$owner_pid/cmdline ]] || exit 1
        [[ $(/usr/bin/stat -c %u "/proc/$owner_pid") == $(id -u) ]] || exit 1
        command_line=$(/usr/bin/tr '\0' ' ' < "/proc/$owner_pid/cmdline")
        [[ $command_line == *"linux_guest_session.sh run $session_id"* ]] || exit 1
        /usr/bin/kill -TERM "$owner_pid"
        ;;
    run)
        umask 077
        /usr/bin/mkdir -p -m 0700 "$runtime/pulse"
        /usr/bin/chmod 0700 "$runtime" "$runtime/pulse"
        if [[ -e $runtime/owner.pid ]]; then
            echo 'Session owner marker exists; reconcile it before starting another' >&2
            exit 1
        fi
        printf '%s\n' "$$" > "$runtime/owner.pid"
        children=()
        cleanup() {
            trap - EXIT TERM INT
            if ((${#children[@]})); then
                /usr/bin/kill -TERM "${children[@]}" 2>/dev/null || true
                wait "${children[@]}" 2>/dev/null || true
            fi
            /usr/bin/rm -f "$runtime/owner.pid"
        }
        trap cleanup EXIT TERM INT

        /usr/bin/dbus-daemon --session --nofork --nopidfile --address="unix:path=$runtime/bus" > "$runtime/dbus.log" 2>&1 &
        children+=("$!")
        /usr/bin/pulseaudio -n --daemonize=no --exit-idle-time=-1 --disallow-exit --file="$config/pulse.pa" > "$runtime/audio.log" 2>&1 &
        children+=("$!")
        for ((attempt=0; attempt<80; attempt++)); do
            if [[ -S $runtime/pulse/native ]] &&
                /usr/bin/pactl --server="unix:$runtime/pulse/native" info >/dev/null 2>&1; then break; fi
            /usr/bin/kill -0 "${children[1]}" 2>/dev/null ||
                { echo 'PulseAudio exited before readiness' >&2; exit 1; }
            /usr/bin/sleep 0.1
        done
        [[ -S $runtime/pulse/native ]] || { echo 'PulseAudio socket did not become ready' >&2; exit 1; }
        /usr/bin/chmod 0600 "$runtime/pulse/native"

        cookie=$(/usr/bin/openssl rand -hex 16)
        /usr/bin/xauth -f "$XAUTHORITY" add :1 . "$cookie"
        /usr/bin/Xvnc :1 -auth "$XAUTHORITY" -geometry 1280x800 -depth 24 \
            -nolisten tcp -rfbport -1 -rfbunixpath "$runtime/rfb.sock" \
            -rfbunixmode 0600 -SecurityTypes None -NeverShared \
            -AcceptCutText=0 -SendCutText=0 > "$runtime/xvnc.log" 2>&1 &
        children+=("$!")
        for ((attempt=0; attempt<80; attempt++)); do
            if /usr/bin/xset q >/dev/null 2>&1; then break; fi
            /usr/bin/kill -0 "${children[2]}" 2>/dev/null || { echo 'Xvnc exited before readiness' >&2; exit 1; }
            /usr/bin/sleep 0.1
        done
        /usr/bin/xset q >/dev/null 2>&1 || { echo 'Xvnc display did not become ready' >&2; exit 1; }

        /usr/bin/xfce4-session > "$runtime/xfce.log" 2>&1 &
        children+=("$!")
        /usr/bin/stunnel4 "$config/stunnel.conf" > "$runtime/stunnel.log" 2>&1 &
        children+=("$!")
        wait -n "${children[@]}"
        ;;
    *)
        echo 'Expected run, ready, or stop' >&2
        exit 2
        ;;
esac
