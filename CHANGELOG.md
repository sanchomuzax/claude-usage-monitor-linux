# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-15

### Added
- System tray indicator showing 5-hour and 7-day Claude API usage
- Dynamic 32x32 icon with segmented progress bars and percentages
- Anthropic brand colors (#D97757 coral-orange accent)
- Click menu with detailed usage info, countdown timers, refresh, and interval settings
- OAuth token authentication via `~/.claude/.credentials.json`
- Rate-limit header parsing from `/v1/messages` API with `oauth-2025-04-20` beta
- Configurable polling interval (5/15/30/60 minutes)
- Autostart on login support
- Single-instance lock
- `--demo` mode for testing without API calls
- Cross-distro installer (`install.sh`) with apt/dnf/pacman support
- 51 unit tests
