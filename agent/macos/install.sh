#!/usr/bin/env sh
# termhop macOS agent installer — matches DEPLOYMENT.md's documented flow:
#   curl -fsSL .../agent/macos/install.sh | sh
#   termhop-agent pair --relay wss://relay.yourdomain.com
#
# This is the SAME "clone + venv" stopgap tier the Linux installer ships —
# no notarized .app or Homebrew formula exists yet (DEPLOYMENT.md documents
# those as the eventual real packaging path; they need an Apple Developer
# ID / notarization / a `brew tap`, none of which exist here). Not an
# oversight, a deliberate v1 scope limit matching Linux's own.
set -eu

REPO_URL="${TERMHOP_REPO_URL:-https://github.com/TechButton/termhop.git}"
INSTALL_DIR="${TERMHOP_INSTALL_DIR:-$HOME/.local/share/termhop}"
BIN_DIR="$HOME/.local/bin"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/termhop"
LABEL="io.termhop.agent"

if [ ! -d "$INSTALL_DIR/.git" ]; then
  echo "Cloning termhop into $INSTALL_DIR..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
  echo "Updating existing checkout at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --ff-only
fi

cd "$INSTALL_DIR/agent"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements-macos.txt

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/termhop-agent" <<EOF
#!/usr/bin/env sh
cd "$INSTALL_DIR/agent"
exec "$INSTALL_DIR/agent/.venv/bin/python" -m macos.main "\$@"
EOF
chmod +x "$BIN_DIR/termhop-agent"

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"
sed -e "s|__EXEC_PATH__|$BIN_DIR/termhop-agent|" -e "s|__LOG_DIR__|$LOG_DIR|" \
  "$INSTALL_DIR/agent/macos/termhop-agent.plist" > "$LAUNCH_AGENTS_DIR/$LABEL.plist"

# bootout-before-bootstrap makes re-running this installer idempotent —
# bootstrap fails loudly (unlike the deprecated load/unload, which
# silently no-ops) if the label is already loaded.
launchctl bootout "gui/$(id -u)" "$LAUNCH_AGENTS_DIR/$LABEL.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS_DIR/$LABEL.plist"

echo
echo "Installed. Next steps:"
echo "  1. termhop-agent pair --relay wss://relay.yourdomain.com"
echo "  2. The launchd agent is already loaded and will run at login going"
echo "     forward (RunAtLoad + KeepAlive) — logs at $LOG_DIR/"
