# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 初期リリースの準備
- `init`, `sync`, `list`, `import`, `clean` コマンドの実装
- SHA256ハッシュによる差分同期機能
- Richライブラリによる美しいコンソール出力
- JSON出力形式のサポート
- 包括的なテストスイート（カバレッジ70%）
- 詳細なドキュメントとクイックスタートガイド

### Changed
- N/A

### Fixed
- N/A

## [1.0.0] - 2024-XX-XX

### 🎉 初回リリース

#### 主な機能
- **簡単セットアップ**: `font-sync init` で即座に開始
- **スマート同期**: 新規・更新・削除されたフォントを自動検出
- **美しいUI**: 進捗表示とテーブル形式の出力
- **安全な操作**: ドライランモードでの事前確認
- **柔軟な管理**: import/cleanコマンドでフォント管理を効率化

#### 技術仕様
- macOS 10.14以降に対応
- Python 3.8以降が必要
- .otf/.ttf形式をサポート
- ~/.fontsync/config.json に設定を保存

[Unreleased]: https://github.com/yourusername/font-sync/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/font-sync/releases/tag/v1.0.0 