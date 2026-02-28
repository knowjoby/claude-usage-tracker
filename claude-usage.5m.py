#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# <swiftbar.title>Claude Usage Tracker</swiftbar.title>
# <swiftbar.version>1.1</swiftbar.version>
# <swiftbar.author>knowjoby</swiftbar.author>
# <swiftbar.desc>Shows Claude Code token usage from local session files</swiftbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>
# <swiftbar.environment>[SHOW_COST=true, PLAN=pro]</swiftbar.environment>
#
# SETUP: Drop this file into your SwiftBar plugins folder.
# SwiftBar: https://swiftbar.app (free, download from Mac App Store or website)
#
# This script reads Claude Code's local session files from ~/.claude/projects/
# No API key needed — all data is read locally from your machine.

import os
import json
import glob
from datetime import datetime, timezone, date
from pathlib import Path
from collections import defaultdict

# ── Configuration ────────────────────────────────────────────────────────────
SHOW_COST = os.environ.get("SHOW_COST", "true").lower() == "true"
PLAN      = os.environ.get("PLAN", "pro")  # "pro" or "api"

# Approximate Anthropic pricing per million tokens (USD)
# Update these if pricing changes: https://www.anthropic.com/pricing
PRICES = {
    "claude-opus-4-6":              {"in": 15.00, "out": 75.00, "cache_w": 18.75, "cache_r": 1.50},
    "claude-opus-4-5":              {"in": 15.00, "out": 75.00, "cache_w": 18.75, "cache_r": 1.50},
    "claude-sonnet-4-6":            {"in":  3.00, "out": 15.00, "cache_w":  3.75, "cache_r": 0.30},
    "claude-sonnet-4-5":            {"in":  3.00, "out": 15.00, "cache_w":  3.75, "cache_r": 0.30},
    "claude-haiku-4-5-20251001":    {"in":  0.80, "out":  4.00, "cache_w":  1.00, "cache_r": 0.08},
    "claude-haiku-4-5":             {"in":  0.80, "out":  4.00, "cache_w":  1.00, "cache_r": 0.08},
    "default":                      {"in":  3.00, "out": 15.00, "cache_w":  3.75, "cache_r": 0.30},
}

# ── Data reading ──────────────────────────────────────────────────────────────
def find_jsonl_files():
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return []
    return list(claude_dir.rglob("*.jsonl"))

def calc_cost(model, usage):
    p = PRICES.get(model, PRICES["default"])
    mtok = 1_000_000
    return (
        usage["input_tokens"]              * p["in"]      / mtok +
        usage["output_tokens"]             * p["out"]     / mtok +
        usage["cache_creation_input_tokens"] * p["cache_w"] / mtok +
        usage["cache_read_input_tokens"]   * p["cache_r"] / mtok
    )

def parse_sessions():
    files = find_jsonl_files()
    today     = date.today()
    this_month = (today.year, today.month)

    totals = {
        "today":    defaultdict(int),
        "month":    defaultdict(int),
        "all_time": defaultdict(int),
    }
    today_cost = 0.0
    month_cost = 0.0
    total_cost = 0.0
    sessions_today = set()
    models_used = set()

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if entry.get("type") != "assistant":
                        continue

                    usage = entry.get("usage")
                    if not usage:
                        continue

                    ts_raw = entry.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        entry_date = ts.date()
                    except (ValueError, AttributeError):
                        continue

                    model   = entry.get("model", "default")
                    session = entry.get("sessionId", str(fpath))
                    u = {
                        "input_tokens":                usage.get("input_tokens", 0),
                        "output_tokens":               usage.get("output_tokens", 0),
                        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                        "cache_read_input_tokens":     usage.get("cache_read_input_tokens", 0),
                    }
                    cost = calc_cost(model, u)

                    # all-time
                    for k, v in u.items():
                        totals["all_time"][k] += v
                    total_cost += cost
                    models_used.add(model)

                    # this month
                    if (entry_date.year, entry_date.month) == this_month:
                        for k, v in u.items():
                            totals["month"][k] += v
                        month_cost += cost

                    # today
                    if entry_date == today:
                        for k, v in u.items():
                            totals["today"][k] += v
                        today_cost += cost
                        sessions_today.add(session)

        except (OSError, PermissionError):
            continue

    blank = {"input_tokens": 0, "output_tokens": 0,
             "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    return {
        "today":          {**blank, **dict(totals["today"])},
        "month":          {**blank, **dict(totals["month"])},
        "all_time":       {**blank, **dict(totals["all_time"])},
        "today_cost":     today_cost,
        "month_cost":     month_cost,
        "total_cost":     total_cost,
        "sessions_today": len(sessions_today),
        "models":         sorted(models_used),
        "files_found":    len(files),
    }

# ── Formatting helpers ────────────────────────────────────────────────────────
def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)

def fmt_cost(c):
    if c < 0.01:
        return f"<$0.01"
    return f"${c:.2f}"

def total_tokens(u):
    return (u.get("input_tokens", 0) +
            u.get("output_tokens", 0) +
            u.get("cache_creation_input_tokens", 0) +
            u.get("cache_read_input_tokens", 0))

def usage_bar(used, limit, width=10):
    if limit == 0:
        return ""
    pct = min(used / limit, 1.0)
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:.0f}%"

# ── Main output ───────────────────────────────────────────────────────────────
def main():
    data = parse_sessions()

    today_tok  = total_tokens(data["today"])
    month_tok  = total_tokens(data["month"])
    total_tok  = total_tokens(data["all_time"])

    # Pick menubar icon based on today's usage
    if data["files_found"] == 0:
        icon = "⚙️"
        bar_label = "Claude — no data"
    else:
        if today_tok == 0:
            icon = "⚪"
        elif today_tok < 100_000:
            icon = "🟢"
        elif today_tok < 500_000:
            icon = "🟡"
        else:
            icon = "🔴"
        label = fmt_tokens(today_tok)
        bar_label = f"{icon} {label} tok"
        if SHOW_COST and data["today_cost"] > 0:
            bar_label += f"  ·  {fmt_cost(data['today_cost'])}"

    # ── Menubar text (first line) ──
    print(bar_label)
    print("---")

    # ── Header ──
    print("Claude Usage Tracker | size=13 color=#7b68ee")
    print("---")

    if data["files_found"] == 0:
        print("⚠️  No Claude Code session files found")
        print("Make sure Claude Code has been run at least once.")
        print("Expected path: ~/.claude/projects/")
        print("---")
    else:
        # ── TODAY ──
        print(f"📅  TODAY  ({date.today().strftime('%b %d')})")
        print(f"  Tokens:   {fmt_tokens(today_tok):>10} | font=Menlo size=11")
        if data["sessions_today"] > 0:
            print(f"  Sessions: {data['sessions_today']:>10} | font=Menlo size=11")
        if SHOW_COST:
            print(f"  Est cost: {fmt_cost(data['today_cost']):>10} | font=Menlo size=11")
        if data["today"]["input_tokens"] or data["today"]["output_tokens"]:
            print(f"  ↳ Input:  {fmt_tokens(data['today']['input_tokens']):>10} | font=Menlo size=11 color=#888")
            print(f"  ↳ Output: {fmt_tokens(data['today']['output_tokens']):>10} | font=Menlo size=11 color=#888")
            if data["today"]["cache_read_input_tokens"]:
                print(f"  ↳ Cache hit: {fmt_tokens(data['today']['cache_read_input_tokens']):>7} | font=Menlo size=11 color=#888")
        print("---")

        # ── THIS MONTH ──
        print(f"📆  THIS MONTH  ({date.today().strftime('%B %Y')})")
        print(f"  Tokens:   {fmt_tokens(month_tok):>10} | font=Menlo size=11")
        if SHOW_COST:
            print(f"  Est cost: {fmt_cost(data['month_cost']):>10} | font=Menlo size=11")
        print("---")

        # ── ALL TIME ──
        print("🕰️  ALL TIME")
        print(f"  Tokens:   {fmt_tokens(total_tok):>10} | font=Menlo size=11")
        if SHOW_COST:
            print(f"  Est cost: {fmt_cost(data['total_cost']):>10} | font=Menlo size=11")
        if data["models"]:
            models_str = ", ".join(m.replace("claude-", "") for m in data["models"][:3])
            print(f"  Models:   {models_str} | font=Menlo size=11 color=#888")
        print("---")

    # ── Quick links ──
    print("🔗  Open Claude.ai | href=https://claude.ai color=#555")
    print("📊  Anthropic Console | href=https://console.anthropic.com/settings/usage color=#555")
    print("---")
    print("↻  Refresh now | refresh=true")
    print(f"Updated: {datetime.now().strftime('%H:%M:%S')} | size=10 color=#aaa")

main()
