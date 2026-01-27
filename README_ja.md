# font-sync

macOS専用のCLIフォント同期ツール。Dropbox、iCloud Drive、Google Driveなどのクラウドストレージを介して、複数のMac間でフォントを簡単に同期できます。

[![CI](https://github.com/URAPRO/font-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/URAPRO/font-sync/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/font-sync.svg)](https://pypi.org/project/font-sync/)
[![Python versions](https://img.shields.io/pypi/pyversions/font-sync.svg)](https://pypi.org/project/font-sync/)
[![macOS](https://img.shields.io/badge/macOS-10.14+-blue.svg)](https://github.com/URAPRO/font-sync)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**[English README](README.md)**

## 特徴

- **スマートな差分同期** – 変更されたフォントのみを同期して高速動作
- **クラウドストレージ対応** – Dropbox、iCloud Drive、Google Drive、OneDriveで動作
- **並列処理** – 1000個以上のフォントも効率的に処理
- **美しいCLI** – リッチな進捗バーとフォーマットされたテーブル
- **安全設計** – ドライランモードで事前確認可能
- **プロ仕様** – .otf/.ttf形式対応、メタデータ保持

## クイックスタート

```bash
# インストール
pip install font-sync

# 初期設定（クラウドフォルダを指定）
font-sync init --folder ~/Dropbox/Fonts/

# フォントを同期
font-sync sync
```

## インストール

### pip経由（推奨）

```bash
pip install font-sync
```

### Homebrew経由（準備中）

```bash
brew tap URAPRO/font-sync
brew install font-sync
```

### ソースから

```bash
git clone https://github.com/URAPRO/font-sync.git
cd font-sync
pip install -e ".[dev]"
```

## 使い方

### 初期設定

```bash
font-sync init
```

対話形式で同期元フォルダ（クラウドストレージのディレクトリ）を設定します。

### フォントの同期

```bash
font-sync sync
```

同期元フォルダから新規・更新されたフォントをシステムに同期します。

### フォント一覧

```bash
font-sync list
```

同期元フォルダ内の全フォントと同期状態を表示します。

### フォントのインポート

```bash
font-sync import ~/Downloads/MyFont.otf
font-sync import ~/Desktop/FontCollection/ --move
```

既存のフォントを同期元フォルダに追加します。

### クリーンアップ

```bash
font-sync clean           # ドライラン（確認のみ）
font-sync clean --execute # 実際に削除
```

同期元から削除されたフォントをシステムからも削除します。

## コマンド一覧

| コマンド | 説明 |
|---------|------|
| `init` | 同期元フォルダを設定 |
| `sync` | フォントを同期 |
| `list` | フォント一覧を表示 |
| `import` | フォントを同期元に追加 |
| `clean` | 不要なフォントを削除 |

## ロードマップ

- [x] v1.0 – コア同期機能
- [x] v1.0 – 並列処理・キャッシュ（1000個以上対応）
- [ ] GUIアプリ（macOSメニューバー） – *開発予定*
- [ ] Homebrew対応

## よくある質問

**Q: WindowsやLinuxでも使えますか？**
A: いいえ、font-syncはmacOS専用です。システム固有のフォント処理のため、他のOSには対応していません。

**Q: どのクラウドサービスに対応していますか？**
A: ローカルフォルダに同期するサービスなら何でも使えます：Dropbox、iCloud Drive、Google Drive、OneDriveなど。

**Q: フォントキャッシュをクリアするには？**
A: 以下のコマンドを実行してください：
```bash
sudo atsutil databases -remove
sudo atsutil server -shutdown
sudo atsutil server -ping
```

## 開発

```bash
# 開発用依存関係をインストール
pip install -e ".[dev]"

# テスト実行
pytest

# リンター実行
ruff check src/ tests/
```

## 貢献方法

1. リポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチをプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## ライセンス

MIT License。詳細は[LICENSE](LICENSE)を参照してください。

## 作者

**URAPRO**
- GitHub: [@URAPRO](https://github.com/URAPRO)
- X (Twitter): [@tk_adio](https://twitter.com/tk_adio)

---

<p align="center">Made with ❤️ for designers and developers on macOS</p>
