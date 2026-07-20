#!/usr/bin/env sh
# termhop Linux agent installer:
#   curl -fsSL .../agent/linux/install.sh | sh
#   termhop-agent pair --relay wss://relay.yourdomain.com
#
# No PyPI package or signed release exists yet — this clones the repo into
# a venv-managed install directory rather than pip-installing a package.
# This installer uses a venv-managed checkout.
set -eu

REPO_URL="${TERMHOP_REPO_URL:-https://github.com/TechButton/termhop.git}"
INSTALL_DIR="${TERMHOP_INSTALL_DIR:-$HOME/.local/share/termhop}"
BIN_DIR="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"

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
.venv/bin/pip install --quiet -r requirements-linux.txt

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/termhop-agent" <<EOF
#!/usr/bin/env sh
cd "$INSTALL_DIR/agent"
exec "$INSTALL_DIR/agent/.venv/bin/python" -m linux.main "\$@"
EOF
chmod +x "$BIN_DIR/termhop-agent"

mkdir -p "$UNIT_DIR"
sed "s|__EXEC_PATH__|$BIN_DIR/termhop-agent|" "$INSTALL_DIR/agent/linux/termhop-agent.service" \
  > "$UNIT_DIR/termhop-agent.service"
systemctl --user daemon-reload

echo
echo "Installed. Next steps:"
echo "  1. Make the command available in this shell:"
echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "  2. Pair once:"
echo "       termhop-agent pair --relay wss://relay.yourdomain.com"
echo "  3. Once paired, enable the service to survive reboots:"
echo "       systemctl --user enable --now termhop-agent"
echo "       sudo loginctl enable-linger \$USER   # optional: run while logged out"
