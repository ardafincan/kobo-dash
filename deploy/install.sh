#!/usr/bin/env bash
# Install the Kobo Dashboard launchd jobs on THIS machine (the Mac Mini).
#
# Fills the plist templates with absolute paths + the host/port from
# config.toml, installs them to ~/Library/LaunchAgents, and loads them.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # project root
DEPLOY="$DIR/deploy"
AGENTS="$HOME/Library/LaunchAgents"

UV="$(command -v uv || true)"
if [[ -z "$UV" ]]; then
    echo "error: 'uv' not found on PATH. Install uv first." >&2
    exit 1
fi

if [[ ! -f "$DIR/config.toml" ]]; then
    echo "error: $DIR/config.toml not found. Copy config.example.toml first." >&2
    exit 1
fi

# Read host/port from config.toml without leaking secrets.
read -r HOST PORT < <("$UV" run --project "$DIR" python - <<'PY'
from src import config
c = config.load()
print(c.host, c.port)
PY
)

echo "project : $DIR"
echo "uv      : $UV"
echo "serve   : http://$HOST:$PORT"

mkdir -p "$AGENTS" "$DIR/logs"

render_fill() {
    sed -e "s#@UV@#$UV#g" -e "s#@DIR@#$DIR#g" \
        -e "s#@HOST@#$HOST#g" -e "s#@PORT@#$PORT#g" "$1"
}

for name in render serve; do
    src="$DEPLOY/com.kobo-dash.$name.plist.template"
    dst="$AGENTS/com.kobo-dash.$name.plist"
    render_fill "$src" > "$dst"
    echo "wrote   $dst"
done

echo
echo "Loading jobs (bootout first in case they were already loaded):"
for name in render serve; do
    label="com.kobo-dash.$name"
    dst="$AGENTS/$label.plist"
    launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$dst"
    echo "  loaded $label"
done

echo
echo "Done. Useful commands:"
echo "  launchctl kickstart -k gui/$(id -u)/com.kobo-dash.render   # force a render now"
echo "  tail -f $DIR/logs/render.log"
echo "  tail -f $DIR/logs/serve.log"
echo "  curl http://$HOST:$PORT/manifest.json"
