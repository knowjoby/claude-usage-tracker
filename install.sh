#!/bin/bash
# Claude Usage Tracker — one-command installer for Mac
# Run this in Terminal: bash install.sh

set -e

PLUGIN_NAME="claude-usage.5m.py"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_SRC="$SCRIPT_DIR/$PLUGIN_NAME"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Claude Usage Tracker — Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check macOS ───────────────────────────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌  This script is for macOS only."
    exit 1
fi

# ── Check Python 3 ───────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌  Python 3 is required but not found."
    echo "    Install it from https://www.python.org or via Homebrew: brew install python3"
    exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo "✅  Found $PYTHON_VER"

# ── Check SwiftBar ───────────────────────────────────────────────────────────
SWIFTBAR_APP="/Applications/SwiftBar.app"
if [[ ! -d "$SWIFTBAR_APP" ]]; then
    echo ""
    echo "⚠️   SwiftBar is not installed."
    echo "     Opening the SwiftBar download page..."
    open "https://swiftbar.app"
    echo ""
    echo "     1. Download and install SwiftBar"
    echo "     2. Launch it — it will ask you to pick a plugins folder"
    echo "        (recommend: ~/Documents/SwiftBar-Plugins)"
    echo "     3. Re-run this installer:  bash install.sh"
    echo ""
    exit 0
fi
echo "✅  SwiftBar is installed"

# ── Find SwiftBar plugins folder ─────────────────────────────────────────────
PLIST="$HOME/Library/Preferences/com.ameba.SwiftBar.plist"
PLUGINS_DIR=""

if [[ -f "$PLIST" ]]; then
    PLUGINS_DIR=$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)
fi

if [[ -z "$PLUGINS_DIR" || ! -d "$PLUGINS_DIR" ]]; then
    # Try common locations
    for candidate in \
        "$HOME/Documents/SwiftBar-Plugins" \
        "$HOME/SwiftBar-Plugins" \
        "$HOME/Library/Application Scripts/com.ameba.SwiftBar"; do
        if [[ -d "$candidate" ]]; then
            PLUGINS_DIR="$candidate"
            break
        fi
    done
fi

if [[ -z "$PLUGINS_DIR" || ! -d "$PLUGINS_DIR" ]]; then
    echo ""
    echo "⚠️   Could not find your SwiftBar plugins folder."
    echo "    Launch SwiftBar and set up a plugins folder, then re-run this script."
    echo ""
    open -a SwiftBar 2>/dev/null || true
    exit 0
fi

echo "✅  SwiftBar plugins folder: $PLUGINS_DIR"

# ── Install the plugin ────────────────────────────────────────────────────────
DEST="$PLUGINS_DIR/$PLUGIN_NAME"
cp "$PLUGIN_SRC" "$DEST"
chmod +x "$DEST"
echo "✅  Plugin installed to: $DEST"

# ── Verify Claude Code session files ─────────────────────────────────────────
CLAUDE_DIR="$HOME/.claude/projects"
if [[ -d "$CLAUDE_DIR" ]]; then
    FILE_COUNT=$(find "$CLAUDE_DIR" -name "*.jsonl" 2>/dev/null | wc -l | tr -d ' ')
    echo "✅  Found $FILE_COUNT Claude Code session file(s) in ~/.claude/projects/"
else
    echo "⚠️   ~/.claude/projects/ not found — run Claude Code at least once first."
fi

# ── Refresh SwiftBar ──────────────────────────────────────────────────────────
if pgrep -x SwiftBar &>/dev/null; then
    open -g "swiftbar://refreshAllPlugins" 2>/dev/null || true
    echo "✅  SwiftBar refreshed"
else
    echo "ℹ️   Starting SwiftBar..."
    open -a SwiftBar 2>/dev/null || true
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done! Look for the Claude icon in your menu bar."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  The tracker shows:"
echo "    🟢  Today's token count + estimated cost"
echo "    📅  Daily / monthly / all-time breakdown"
echo "    🔗  Quick links to Claude.ai and the Console"
echo ""
echo "  It refreshes every 5 minutes automatically."
echo ""
echo "  To customise, open the plugin and edit the"
echo "  SHOW_COST or PLAN variables at the top."
echo ""
