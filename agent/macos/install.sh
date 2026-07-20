#!/usr/bin/env sh
# termhop macOS agent installer:
#   curl -fsSL .../agent/macos/install.sh | sh
#   termhop-agent pair --relay wss://relay.yourdomain.com
#
# This installer uses a venv-managed checkout.
set -eu
umask 077

REPO_URL="${TERMHOP_REPO_URL:-https://github.com/TechButton/termhop.git}"
INSTALL_DIR="${TERMHOP_INSTALL_DIR:-$HOME/.local/share/termhop}"
BIN_DIR="$HOME/.local/bin"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/termhop"
LABEL="io.termhop.agent"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
WAS_ACTIVE=false

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  WAS_ACTIVE=true
  echo "Stopping the existing TermHop LaunchAgent for update..."
  launchctl bootout "gui/$(id -u)" "$PLIST_PATH"
fi

if [ ! -d "$INSTALL_DIR/.git" ]; then
  echo "Cloning termhop into $INSTALL_DIR..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
  echo "Updating existing checkout at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --ff-only
fi

cd "$INSTALL_DIR/agent"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements-macos.txt

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/termhop-agent" <<EOF
#!/usr/bin/env sh
cd "$INSTALL_DIR/agent"
exec "$INSTALL_DIR/agent/.venv/bin/python" -m macos.main "\$@"
EOF
chmod +x "$BIN_DIR/termhop-agent"

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"
sed -e "s|__EXEC_PATH__|$BIN_DIR/termhop-agent|" -e "s|__LOG_DIR__|$LOG_DIR|" \
  "$INSTALL_DIR/agent/macos/termhop-agent.plist" > "$PLIST_PATH"

# Stop an older loaded copy, if present. Do not bootstrap the new agent until
# the user completes first pairing; otherwise launchd would repeatedly start an
# unconfigured agent with no relay URL.
if [ "$WAS_ACTIVE" = true ]; then
  launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
fi

echo
echo "Installed. Next steps:"
echo "  1. Make the command available in this shell:"
echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "  2. Pair once:"
echo "       termhop-agent pair --relay wss://relay.yourdomain.com"
echo "  3. After that terminal session ends, start the persistent agent:"
echo "       launchctl bootstrap gui/\$(id -u) \"$LAUNCH_AGENTS_DIR/$LABEL.plist\""
echo "     It will reconnect automatically and run at login. Logs: $LOG_DIR/"
