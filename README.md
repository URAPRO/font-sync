# font-sync

A CLI font synchronization tool for macOS. Easily sync fonts across multiple Macs via cloud storage like Dropbox, iCloud Drive, or Google Drive.

[![CI](https://github.com/URAPRO/font-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/URAPRO/font-sync/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/font-sync.svg)](https://pypi.org/project/font-sync/)
[![Python versions](https://img.shields.io/pypi/pyversions/font-sync.svg)](https://pypi.org/project/font-sync/)
[![macOS](https://img.shields.io/badge/macOS-10.14+-blue.svg)](https://github.com/URAPRO/font-sync)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**[日本語版 README はこちら](README_ja.md)**

## Features

- **Smart Differential Sync** – Only syncs changed fonts for fast operation
- **Cloud Storage Support** – Works with Dropbox, iCloud Drive, Google Drive, OneDrive
- **Parallel Processing** – Handles 1000+ fonts efficiently
- **Beautiful CLI** – Rich progress bars and formatted tables
- **Safe by Default** – Dry-run mode for previewing changes
- **Pro Format Support** – .otf and .ttf with metadata preservation

## Quick Start

```bash
# Install
pip install font-sync

# Initialize (specify your cloud folder)
font-sync init --folder ~/Dropbox/Fonts/

# Sync fonts
font-sync sync
```

## Installation

### Via pip (Recommended)

```bash
pip install font-sync
```

### Via Homebrew (Coming Soon)

```bash
brew tap URAPRO/font-sync
brew install font-sync
```

### From Source

```bash
git clone https://github.com/URAPRO/font-sync.git
cd font-sync
pip install -e ".[dev]"
```

## Usage

### Initialize

```bash
font-sync init
```

Interactively set up your sync source folder (cloud storage directory).

### Sync Fonts

```bash
font-sync sync
```

Syncs new and updated fonts from the source folder to your system.

### List Fonts

```bash
font-sync list
```

Shows all fonts in the source folder with their sync status.

### Import Fonts

```bash
font-sync import ~/Downloads/MyFont.otf
font-sync import ~/Desktop/FontCollection/ --move
```

Add existing fonts to your sync source folder.

### Clean Up

```bash
font-sync clean           # Dry-run (preview)
font-sync clean --execute # Actually remove
```

Remove fonts that were deleted from the source folder.

## Commands

| Command | Description |
|---------|-------------|
| `init` | Set up sync source folder |
| `sync` | Sync fonts from source to system |
| `list` | List fonts and their status |
| `import` | Add fonts to source folder |
| `clean` | Remove orphaned fonts |

## Roadmap

- [x] v1.0 – Core sync functionality
- [x] v1.0 – Parallel processing & caching (1000+ fonts)
- [ ] GUI app (macOS menu bar) – *Coming soon*
- [ ] Homebrew formula

## FAQ

**Q: Does it work on Windows/Linux?**
A: No, font-sync is macOS only due to system-specific font handling.

**Q: Which cloud services are supported?**
A: Any service that syncs to a local folder: Dropbox, iCloud Drive, Google Drive, OneDrive, etc.

**Q: How do I refresh the font cache?**
A: Run these commands:
```bash
sudo atsutil databases -remove
sudo atsutil server -shutdown
sudo atsutil server -ping
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License. See [LICENSE](LICENSE) for details.

## Author

**URAPRO**
- GitHub: [@URAPRO](https://github.com/URAPRO)
- X (Twitter): [@tk_adio](https://twitter.com/tk_adio)

---

<p align="center">Made with ❤️ for designers and developers on macOS</p>
