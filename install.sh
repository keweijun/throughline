#!/bin/sh
# Install or update Throughline on macOS or Linux:
#   curl -LsSf https://raw.githubusercontent.com/keweijun/throughline/main/install.sh | sh
# For the Chinese welcome guide, set THROUGHLINE_LANGUAGE=zh-CN or pass --language zh-CN (`| sh -s -- --language zh-CN`).
# --no-open leaves the app closed when setup is done.
#
# The steps, the same as README "For Codex" and the one-click updater (#110); change them together:
#   1. install uv if it is missing (uv brings its own Python)
#   2. stop a running Throughline, which keeps its files open
#   3. remove the pre-0.5.1 package name, codex-guided-learning
#   4. install the latest version from main
#   5. run setup: the skill, the course library, the launcher, then open the app
# Courses are never touched. Codex is checked for, not installed.
set -eu

PACKAGE='throughline[pdf] @ git+https://github.com/keweijun/throughline'

main() {
  language="${THROUGHLINE_LANGUAGE:-en}"
  open=yes
  while [ $# -gt 0 ]; do
    case "$1" in
      --language) language="${2:?--language needs a value}"; shift 2 ;;
      --language=*) language="${1#*=}"; shift ;;
      --no-open) open=no; shift ;;
      *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
  done

  # 1.
  if ! command -v uv >/dev/null 2>&1; then
    echo 'Installing uv, which installs Throughline and the Python it runs on...'
    if command -v curl >/dev/null 2>&1; then
      curl -LsSf https://astral.sh/uv/install.sh | sh
    else
      wget -qO- https://astral.sh/uv/install.sh | sh
    fi
    PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$HOME/.cargo/bin:$PATH"
    export PATH
  fi

  # 2.
  if command -v guided-learning >/dev/null 2>&1; then
    guided-learning stop || true
  fi

  # 3. A pipx install, of either name, would clash with uv's guided-learning command.
  uv tool uninstall codex-guided-learning >/dev/null 2>&1 || true
  if command -v pipx >/dev/null 2>&1; then
    pipx uninstall codex-guided-learning >/dev/null 2>&1 || true
    pipx uninstall throughline >/dev/null 2>&1 || true
  fi

  # 4.
  uv tool install --reinstall "$PACKAGE"
  uv tool update-shell >/dev/null 2>&1 || true  # uv's tool folder on PATH in new terminals
  bin="$(uv tool dir --bin)"

  # 5.
  set -- setup
  if [ "$language" = zh-CN ]; then set -- "$@" --language zh-CN; fi
  if [ "$open" = no ]; then set -- "$@" --no-open; fi
  "$bin/guided-learning" "$@"

  if ! command -v codex >/dev/null 2>&1 && [ ! -d /Applications/Codex.app ] && [ ! -d "$HOME/Applications/Codex.app" ]; then
    echo
    echo 'Throughline needs Codex to teach, and Codex was not found.'
    echo 'Install Codex (the desktop app or the CLI: https://learn.chatgpt.com/docs/codex/cli), sign in, then open Throughline again.'
  fi
  case ":$PATH:" in
    *":$bin:"*) ;;
    *) echo; echo "Open a new terminal to use the throughline command, or run $bin/throughline now." ;;
  esac
}

main "$@"  # run only once the whole script has arrived through the pipe
