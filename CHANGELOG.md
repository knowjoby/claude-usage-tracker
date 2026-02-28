# Changelog

All notable changes to Claude Usage Tracker are documented here.

---

## [2.1] — 2026-02-28

### Added
- **Stop Claude Code button** — detects running Claude processes via `pgrep`; shows `⏸ Stop Claude Code` (kills all processes via `pkill`) when active, `✓ Claude Code is idle` otherwise
- **Running indicator** — appends `●` to the menubar label when Claude Code processes are detected
- **Daily budget cap** — new `DAILY_BUDGET` env var (USD, `0` = no limit); when set, shows a progress bar in the TODAY section (`[███████░░░] 68%  ·  $5.00 limit`)
- **Over-budget alert** — menubar icon overrides to `⚠️`, hero line appends `⚠️`, and progress bar shows `over $X.XX limit` when daily spend is exceeded
- **2 new unit tests** for budget logic (32 total)

---

## [2.0] — 2026-02-28

### Added
- **Unit tests** — 30 tests covering all core logic: token formatting, cost calculation, session parsing, and edge cases
- **README** — full documentation with install instructions, configuration table, pricing table, and screenshot
- **CHANGELOG** — version history from v1.0
- **GitHub release** — v2.0 tagged and published
- **Repo metadata** — description and topics added (`swiftbar`, `claude`, `claude-code`, `anthropic`, `macos`, `menubar`, `token-usage`, `python`)
- Electric indigo color palette — deep indigo (`#2B35C8`) in light mode, bright periwinkle (`#8B96FF`) in dark mode
- Token count + estimated cost combined onto one hero line (`9.0M  ·  $3.40`)
- Georgia-Bold serif font for section headers
- Cleaner sub-stats line: `in 315 · out 17.8k · cache 11.5M`
- Prettier model names: `Haiku 4.5 · Sonnet 4.6` (strips version suffixes and `claude-` prefix)
- Tighter menubar label: `🔴 11.6M · $4.24` (removed "tok" suffix)
- Symlink-based installer — edits to the repo reflect in SwiftBar instantly without reinstalling

### Fixed
- Font colors now correctly adapt to light and dark mode using `darkColor=` parameter
- Resolved `darkColor` not applying due to SwiftBar running via macOS app translocation — fixed by moving SwiftBar to `/Applications`
- Token parsing corrected for nested `message.usage` structure
- Skips synthetic and error messages to avoid inflated token counts

### Changed
- Section labels use Georgia-Bold serif for cleaner typography
- Removed emojis from section labels (`TODAY`, `THIS MONTH`, `ALL TIME`) for a cleaner look
- Bold section labels for stronger visual hierarchy
- Header shortened from `Claude Usage Tracker` to `Claude`
- Links and refresh row simplified, icons removed

---

## [1.1] — 2026-02-22

### Fixed
- Token usage now read from `message.usage` (nested) instead of top-level `usage`
- Skip entries with `isApiErrorMessage` or `error` fields to avoid counting failed requests
- Skip messages with `model: "<synthetic>"`

---

## [1.0] — 2026-02-22

### Added
- Initial release
- Today / This Month / All Time token counts and estimated costs
- Per-model pricing for Opus, Sonnet, and Haiku
- Color-coded menubar icon based on daily usage (⚪ 🟢 🟡 🔴)
- Input, output, and cache token breakdown
- Links to Claude.ai and Anthropic Console
- Auto-refresh every 5 minutes
- `SHOW_COST` and `PLAN` environment variable configuration
