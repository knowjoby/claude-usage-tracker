# Changelog

All notable changes to Claude Usage Tracker are documented here.

---

## [2.0] — 2026-02-28

### Added
- Electric indigo color palette — deep indigo (`#2B35C8`) in light mode, bright periwinkle (`#8B96FF`) in dark mode
- Token count + estimated cost combined onto one hero line (`9.0M  ·  $3.40`)
- Georgia-Bold serif font for section headers
- Cleaner sub-stats line: `in 315 · out 17.8k · cache 11.5M`
- Prettier model names: `Haiku 4.5 · Sonnet 4.6` (strips version suffixes and `claude-` prefix)
- Tighter menubar label: `🔴 11.6M · $4.24` (removed "tok" suffix)
- Symlink-based installer — edits to the repo reflect in SwiftBar instantly

### Fixed
- Font colors now correctly adapt to light and dark mode using `darkColor=` parameter
- Token parsing corrected for nested `message.usage` structure
- Skips synthetic and error messages to avoid inflated counts
- SwiftBar must be installed in `/Applications` for `darkColor` to work — installer updated accordingly

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
