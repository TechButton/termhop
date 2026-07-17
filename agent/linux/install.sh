#!/usr/bin/env sh
# termhop Linux agent installer — matches DEPLOYMENT.md's documented flow:
#   curl -fsSL .../agent/linux/install.sh | sh
#   termhop-agent pair --relay wss://relay.yourdomain.com
#
# No PyPI package or signed release exists yet — this clones the repo into
# a venv-managed install directory rather than pip-installing a package.
# That's a deliberate v1 scope limit (packaging polish is a later step, not
# this one), not an oversight.
set -eu

REPO_URL="${TERMHOP_REPO_URL:-https://github.com/<you>/termhop.git}"
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
echo "  1. termhop-agent pair --relay wss://relay.yourdomain.com"
echo "  2. Once paired, enable the service to survive reboots:"
echo "       systemctl --user enable --now termhop-agent"
echo "       loginctl enable-linger \$USER   # required for a *user* unit to"
echo "                                       # run without an active login session"
