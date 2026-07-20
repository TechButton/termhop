#!/usr/bin/env sh
# termhop Linux agent installer:
#   curl -fsSL .../agent/linux/install.sh | sh
#   termhop-agent pair --relay wss://relay.yourdomain.com
#
# No PyPI package or signed release exists yet — this clones the repo into
# a venv-managed install directory rather than pip-installing a package.
# This installer uses a venv-managed checkout.
set -eu
umask 077

REPO_URL="${TERMHOP_REPO_URL:-https://github.com/TechButton/termhop.git}"
INSTALL_DIR="${TERMHOP_INSTALL_DIR:-$HOME/.local/share/termhop}"
BIN_DIR="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"
WAS_ACTIVE=false

if ! command -v python3 >/dev/null 2>&1; then
  echo "TermHop requires Python 3.11 or newer. Install python3 and rerun this command." >&2
  exit 1
fi
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "TermHop requires Python 3.11 or newer; found $PYTHON_VERSION." >&2
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo "TermHop requires Git. Install git and rerun this command." >&2
  exit 1
fi
if ! python3 -m ensurepip --version >/dev/null 2>&1; then
  echo "TermHop needs the Python venv/pip support package before it can install." >&2
  DISTRO_ID=""
  [ -r /etc/os-release ] && . /etc/os-release && DISTRO_ID="${ID:-}"
  case "$DISTRO_ID" in
    ubuntu|debian) echo "Run: sudo apt update && sudo apt install -y python${PYTHON_VERSION}-venv" >&2 ;;
    fedora|rhel|centos) echo "Run: sudo dnf install -y python3-pip" >&2 ;;
    *) echo "Install your distribution's python3-venv (and pip) package, then rerun." >&2 ;;
  esac
  exit 1
fi

if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet termhop-agent 2>/dev/null; then
  WAS_ACTIVE=true
  echo "Stopping the existing TermHop user service for update..."
  systemctl --user stop termhop-agent
fi

if [ ! -d "$INSTALL_DIR/.git" ]; then
  echo "Cloning termhop into $INSTALL_DIR..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
  echo "Updating existing checkout at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --ff-only
fi

cd "$INSTALL_DIR/agent"
if [ -d .venv ] && ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo "The existing virtual environment is incomplete; recreating it..."
  rm -rf .venv
fi
if [ ! -x .venv/bin/python ]; then
  if ! python3 -m venv .venv; then
    echo "Could not create the Python virtual environment. Install python${PYTHON_VERSION}-venv and rerun." >&2
    exit 1
  fi
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo "The virtual environment has no pip. Install python${PYTHON_VERSION}-venv and rerun." >&2
  exit 1
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements-linux.txt

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
if [ "$WAS_ACTIVE" = true ]; then
  systemctl --user start termhop-agent
fi

echo
echo "Installed. Next steps:"
echo "  1. Make the command available in this shell:"
echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "  2. Pair once:"
echo "       termhop-agent pair --relay wss://relay.yourdomain.com"
echo "  3. Once paired, enable the service to survive reboots:"
echo "       systemctl --user enable --now termhop-agent"
echo "       sudo loginctl enable-linger \$USER   # optional: run while logged out"
