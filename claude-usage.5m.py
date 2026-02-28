#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# <swiftbar.title>Claude Usage Tracker</swiftbar.title>
# <swiftbar.version>2.0</swiftbar.version>
# <swiftbar.author>knowjoby</swiftbar.author>
# <swiftbar.desc>Shows Claude Code token usage from local session files</swiftbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>
# <swiftbar.environment>[SHOW_COST=true, PLAN=pro, DAILY_BUDGET=0, MONTHLY_BUDGET=0]</swiftbar.environment>
#
# SETUP: Drop this file into your SwiftBar plugins folder.
# SwiftBar: https://swiftbar.app (free, download from Mac App Store or website)
#
# This script reads Claude Code's local session files from ~/.claude/projects/
# No API key needed — all data is read locally from your machine.

import os
import json
import glob
import subprocess
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from collections import defaultdict

# ── Configuration ────────────────────────────────────────────────────────────
SHOW_COST      = os.environ.get("SHOW_COST", "true").lower() == "true"
PLAN           = os.environ.get("PLAN", "pro")  # "pro" or "api"
DAILY_BUDGET   = float(os.environ.get("DAILY_BUDGET", "0"))    # USD — 0 = no limit
MONTHLY_BUDGET = float(os.environ.get("MONTHLY_BUDGET", "0"))  # USD — 0 = no limit

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

def calc_cache_savings(model, cache_read_tokens):
    """How much was saved by reading from cache vs paying full input price."""
    p = PRICES.get(model, PRICES["default"])
    mtok = 1_000_000
    return cache_read_tokens * (p["in"] - p["cache_r"]) / mtok

def parse_sessions():
    files = find_jsonl_files()
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())  # Monday
    this_month = (today.year, today.month)

    totals = {
        "today":     defaultdict(int),
        "yesterday": defaultdict(int),
        "week":      defaultdict(int),
        "month":     defaultdict(int),
        "all_time":  defaultdict(int),
    }
    today_cost = 0.0
    yesterday_cost = 0.0
    week_cost = 0.0
    month_cost = 0.0
    total_cost = 0.0
    today_cache_savings = 0.0
    sessions_today = set()
    models_used = set()
    month_days_with_data = set()

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

                    # Skip synthetic/error messages (auth failures, etc.)
                    if entry.get("isApiErrorMessage") or entry.get("error"):
                        continue

                    # Usage is nested inside the message object
                    message = entry.get("message", {})
                    if message.get("model") == "<synthetic>":
                        continue

                    usage = message.get("usage") or entry.get("usage")
                    if not usage:
                        continue

                    ts_raw = entry.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        entry_date = ts.date()
                    except (ValueError, AttributeError):
                        continue

                    model   = message.get("model") or entry.get("model", "default")
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
                        month_days_with_data.add(entry_date)

                    # yesterday
                    if entry_date == yesterday:
                        for k, v in u.items():
                            totals["yesterday"][k] += v
                        yesterday_cost += cost

                    # this week (Mon–today)
                    if entry_date >= week_start:
                        for k, v in u.items():
                            totals["week"][k] += v
                        week_cost += cost

                    # today
                    if entry_date == today:
                        for k, v in u.items():
                            totals["today"][k] += v
                        today_cost += cost
                        today_cache_savings += calc_cache_savings(model, u["cache_read_input_tokens"])
                        sessions_today.add(session)

        except (OSError, PermissionError):
            continue

    # Projected monthly cost: daily average * days in month
    days_active = max(len(month_days_with_data), 1)
    avg_daily = month_cost / days_active
    days_in_month = (date(today.year, today.month % 12 + 1, 1) - date(today.year, today.month, 1)).days if today.month < 12 else 31
    projected_month_cost = avg_daily * days_in_month

    blank = {"input_tokens": 0, "output_tokens": 0,
             "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    return {
        "today":                {**blank, **dict(totals["today"])},
        "yesterday":            {**blank, **dict(totals["yesterday"])},
        "week":                 {**blank, **dict(totals["week"])},
        "month":                {**blank, **dict(totals["month"])},
        "all_time":             {**blank, **dict(totals["all_time"])},
        "today_cost":           today_cost,
        "yesterday_cost":       yesterday_cost,
        "week_cost":            week_cost,
        "month_cost":           month_cost,
        "total_cost":           total_cost,
        "today_cache_savings":  today_cache_savings,
        "projected_month_cost": projected_month_cost,
        "sessions_today":       len(sessions_today),
        "models":               sorted(models_used),
        "files_found":          len(files),
        "days_in_month":        days_in_month,
        "week_start":           week_start,
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

# ── Process detection ─────────────────────────────────────────────────────────
def get_claude_sessions():
    """Return list of (pids, display_path) for running Claude sessions, grouped by cwd."""
    try:
        pgrep = subprocess.run(["pgrep", "-f", "claude"], capture_output=True, text=True)
        if pgrep.returncode != 0:
            return []
        pids = [int(p) for p in pgrep.stdout.strip().split('\n') if p.strip()]
        if not pids:
            return []
        lsof = subprocess.run(
            ["lsof", "-p", ",".join(str(p) for p in pids), "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=3
        )
        pid_to_cwd = {}
        current_pid = None
        for line in lsof.stdout.split('\n'):
            if line.startswith('p'):
                try: current_pid = int(line[1:])
                except ValueError: current_pid = None
            elif line.startswith('n') and current_pid is not None:
                pid_to_cwd[current_pid] = line[1:]
        cwd_to_pids = {}
        for pid, cwd in pid_to_cwd.items():
            cwd_to_pids.setdefault(cwd, []).append(pid)
        home = str(Path.home())
        # Only keep directories that look like real project dirs
        # (inside home, but not macOS system/library paths)
        excluded_prefixes = (
            home + "/Library/",
            home + "/.Trash",
            "/System/", "/usr/", "/opt/", "/private/", "/var/",
        )
        candidates = []
        for cwd, pids in cwd_to_pids.items():
            if not cwd.startswith("/"):
                continue
            if cwd in ("/", home):
                continue
            if any(cwd.startswith(p) for p in excluded_prefixes):
                continue
            candidates.append((cwd, pids))

        # Remove paths that are subdirectories of another listed path
        roots = []
        for cwd, pids in candidates:
            if not any(cwd.startswith(other + "/") for other, _ in candidates if other != cwd):
                roots.append((pids, cwd.replace(home, "~")))
        return roots
    except Exception:
        return []


# ── Main output ───────────────────────────────────────────────────────────────
def main():
    data = parse_sessions()

    today_tok  = total_tokens(data["today"])
    month_tok  = total_tokens(data["month"])
    total_tok  = total_tokens(data["all_time"])

    # Detect running Claude Code sessions (grouped by working directory)
    sessions = get_claude_sessions()
    claude_running = bool(sessions)

    # Budget checks
    over_budget         = DAILY_BUDGET   > 0 and data["today_cost"]  >= DAILY_BUDGET
    over_monthly_budget = MONTHLY_BUDGET > 0 and data["month_cost"]  >= MONTHLY_BUDGET

    # Pick menubar icon based on today's usage
    if data["files_found"] == 0:
        icon = "⚙️"
        bar_label = "Claude — no data"
    else:
        if over_budget:
            icon = "⚠️"
        elif today_tok == 0:
            icon = "⚪"
        elif today_tok < 100_000:
            icon = "🟢"
        elif today_tok < 500_000:
            icon = "🟡"
        else:
            icon = "🔴"
        label = fmt_tokens(today_tok)
        bar_label = f"{icon} {label}"
        if SHOW_COST and data["today_cost"] > 0:
            bar_label += f" · {fmt_cost(data['today_cost'])}"
        if claude_running:
            bar_label += " ●"

    # ── Menubar text (first line) ──
    print(bar_label)
    print("---")

    ON   = "color=#000000 darkColor=#FFFFFF"   # force full-brightness text both modes
    DIM  = "color=#555555 darkColor=#999999"   # subdued sub-stats

    def fmt_model(m):
        m = m.replace("claude-", "")
        for suffix in ("-20251001", "-20240620", "-20240229", "-20250219"):
            m = m.replace(suffix, "")
        replacements = {"sonnet-4-6": "Sonnet 4.6", "sonnet-4-5": "Sonnet 4.5",
                        "opus-4-6": "Opus 4.6",     "opus-4-5": "Opus 4.5",
                        "haiku-4-5": "Haiku 4.5"}
        return replacements.get(m, m.title())

    # ── Header ──
    print(f"Claude | size=14 {ON}")
    print("---")

    if data["files_found"] == 0:
        print(f"⚠️  No Claude Code session files found | {ON}")
        print(f"Expected path: ~/.claude/projects/ | {DIM}")
        print("---")
    else:
        # ── TODAY ──
        print(f"TODAY  ·  {date.today().strftime('%b %d')} | {ON}")
        hero = fmt_tokens(today_tok)
        if SHOW_COST and data["today_cost"] > 0:
            hero += f"  ·  {fmt_cost(data['today_cost'])}"
            if over_budget:
                hero += "  ⚠️"
        print(f"  {hero} | size=15 {ON}")
        if DAILY_BUDGET > 0:
            bar = usage_bar(data["today_cost"], DAILY_BUDGET)
            limit_str = f"over ${DAILY_BUDGET:.2f} limit" if over_budget else f"${DAILY_BUDGET:.2f} limit"
            print(f"  {bar}  ·  {limit_str} | size=11 {DIM}")
        if data["sessions_today"] > 0:
            print(f"  {data['sessions_today']} session{'s' if data['sessions_today'] != 1 else ''} | size=11 {DIM}")
        if SHOW_COST and data["yesterday_cost"] > 0:
            delta = data["today_cost"] - data["yesterday_cost"]
            arrow = "▲" if delta >= 0 else "▼"
            print(f"  {arrow} {fmt_cost(abs(delta))} vs yesterday ({fmt_cost(data['yesterday_cost'])}) | size=10 {DIM}")
        if data["today"]["input_tokens"] or data["today"]["output_tokens"]:
            today_total = total_tokens(data["today"])
            cache_pct = int(data["today"]["cache_read_input_tokens"] / today_total * 100) if today_total else 0
            parts = [f"in {fmt_tokens(data['today']['input_tokens'])}",
                     f"out {fmt_tokens(data['today']['output_tokens'])}"]
            if data["today"]["cache_read_input_tokens"]:
                parts.append(f"cache {fmt_tokens(data['today']['cache_read_input_tokens'])} ({cache_pct}%)")
            print(f"  {' · '.join(parts)} | size=10 {DIM}")
        if SHOW_COST and data["today_cache_savings"] >= 0.01:
            print(f"  saved {fmt_cost(data['today_cache_savings'])} via cache | size=10 {DIM}")
        print("---")

        # ── THIS WEEK ──
        week_tok = total_tokens(data["week"])
        if week_tok > 0:
            week_end = data["week_start"] + timedelta(days=6)
            week_label = f"{data['week_start'].strftime('%b %d')} – {week_end.strftime('%b %d')}"
            print(f"THIS WEEK  ·  {week_label} | {ON}")
            hero_w = fmt_tokens(week_tok)
            if SHOW_COST and data["week_cost"] > 0:
                hero_w += f"  ·  {fmt_cost(data['week_cost'])}"
            print(f"  {hero_w} | size=15 {ON}")
            print("---")

        # ── THIS MONTH ──
        print(f"THIS MONTH  ·  {date.today().strftime('%B %Y')} | {ON}")
        hero_m = fmt_tokens(month_tok)
        if SHOW_COST and data["month_cost"] > 0:
            hero_m += f"  ·  {fmt_cost(data['month_cost'])}"
            if over_monthly_budget:
                hero_m += "  ⚠️"
        print(f"  {hero_m} | size=15 {ON}")
        if MONTHLY_BUDGET > 0:
            bar_m = usage_bar(data["month_cost"], MONTHLY_BUDGET)
            limit_str_m = f"over ${MONTHLY_BUDGET:.0f} limit" if over_monthly_budget else f"${MONTHLY_BUDGET:.0f} limit"
            print(f"  {bar_m}  ·  {limit_str_m} | size=11 {DIM}")
        if SHOW_COST and data["projected_month_cost"] > 0 and date.today().day < data["days_in_month"]:
            print(f"  projected {fmt_cost(data['projected_month_cost'])} this month | size=10 {DIM}")
        print("---")

        # ── ALL TIME ──
        print(f"ALL TIME | {ON}")
        hero_t = fmt_tokens(total_tok)
        if SHOW_COST and data["total_cost"] > 0:
            hero_t += f"  ·  {fmt_cost(data['total_cost'])}"
        print(f"  {hero_t} | size=15 {ON}")
        if data["models"]:
            models_str = "  ·  ".join(fmt_model(m) for m in data["models"][:3])
            print(f"  {models_str} | size=10 {DIM}")
        print("---")

    # ── Quick links ──
    print(f"Open Claude.ai | href=https://claude.ai")
    print(f"Anthropic Console | href=https://console.anthropic.com/settings/usage")
    print("---")
    if not sessions:
        print(f"✓  Claude Code is idle |")
    elif len(sessions) == 1:
        pids, display = sessions[0]
        params = " ".join(f"param{i+1}={p}" for i, p in enumerate(pids[:6]))
        print(f"⏸  Stop Claude Code ({display}) | bash=/bin/kill {params} terminal=false refresh=true")
    else:
        for pids, display in sessions:
            params = " ".join(f"param{i+1}={p}" for i, p in enumerate(pids[:6]))
            print(f"⏸  {display} | bash=/bin/kill {params} terminal=false refresh=true")
        print(f"⏸  Stop All | bash=/usr/bin/pkill param1=-f param2=claude terminal=false refresh=true")
    print("---")
    print(f"Refresh | refresh=true")
    print(f"  {datetime.now().strftime('%H:%M:%S')} | size=10")

main()
