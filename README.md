# font-sync 🔤

macOS専用のCLIフォント同期ツール。Dropboxなどの共有フォルダを介して、複数のMac間でフォントを簡単に同期できます。

![Status](https://img.shields.io/badge/status-active-success.svg)
![macOS](https://img.shields.io/badge/macOS-10.14+-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

> **Note**: このプロジェクトは[Cursor](https://cursor.sh/)とのCo-Writingで開発されています 🤝

## こんな方におすすめ 👥

- **デザイナー・クリエイター**: 自宅と会社のMacで同じフォント環境を維持したい
- **開発者**: フォント管理を自動化してセットアップ時間を短縮したい
- **チーム**: プロジェクトで使用するフォントをメンバー間で共有したい

## 特徴 ✨

- 🚀 **簡単セットアップ**: わずか3ステップで同期環境を構築
- 🔄 **スマートな差分同期**: 変更されたフォントのみを高速同期
- 📊 **美しいUI**: 進捗状況が一目でわかるビジュアル表示
- 🎯 **完全自動化**: 新規・更新・削除を自動検出して処理
- 🛡️ **安全設計**: ドライランモードで事前確認が可能
- 🎨 **プロ仕様**: .otf/.ttf形式に対応、メタデータ保持

## クイックスタート 🚀

```bash
# 1. インストール
brew install font-sync  # (準備中)

# 2. 初期設定（Dropboxフォルダを指定）
font-sync init --folder ~/Dropbox/Fonts/

# 3. フォントを同期！
font-sync sync
```

たったこれだけで、チーム全員のフォント環境が統一されます！

## インストール方法 📦

### 方法1: Homebrewを使用（推奨・準備中）

```bash
brew tap URAPRO/font-sync
brew install font-sync
```

### 方法2: pipを使用

```bash
# Python 3.8以上が必要です
python3 --version

# font-syncをインストール
pip3 install font-sync
```

### 方法3: ソースからインストール（開発者向け）

```bash
# リポジトリをクローン
git clone https://github.com/URAPRO/font-sync.git
cd font-sync

# 仮想環境を作成（推奨）
python3 -m venv venv
source venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt

# font-syncをインストール
pip install -e .
```

## 詳しい使い方 📖

### 初期設定

```bash
$ font-sync init

font-syncの初期設定を開始します。

同期元フォルダのパスを入力してください。
例: ~/Dropbox/shared-fonts/
同期元フォルダのパス [~/Dropbox/shared-fonts/]: ~/Dropbox/MyFonts/

✓ 設定を保存しました。
設定ファイル: ~/.fontsync/config.json
同期元フォルダ: ~/Dropbox/MyFonts/

ℹ 23個のフォントファイルが見つかりました。
'font-sync sync' コマンドでフォントを同期できます。
```

### フォントの同期

```bash
$ font-sync sync

同期元フォルダ: ~/Dropbox/MyFonts/

ℹ 23個のフォントファイルが見つかりました。

  差分を確認中... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
           同期対象のフォント            
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ 状態         ┃ フォント名    ┃ サイズ  ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ 新規         │ Noto Sans.otf │ 4.2 MB  │
│ 新規         │ Roboto.ttf    │ 2.1 MB  │
│ 更新         │ Helvetica.otf │ 3.5 MB  │
└──────────────┴───────────────┴──────────┘

3個のフォントを同期します。

  インストール中: Helvetica.otf ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

✓ 3個のフォントを正常に同期しました。

同期完了: 2024-01-20 15:30:45
```

### フォント一覧の確認

```bash
$ font-sync list

フォント一覧 - ~/Dropbox/MyFonts/
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 状態 ┃ フォント名        ┃ サイズ  ┃ 更新日時          ┃ メモ                  ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ ✓    │ Helvetica.otf     │ 3.5 MB  │ 2024-01-20 15:30  │ インストール: 2024-01-20 │
│ ✓    │ Noto Sans.otf     │ 4.2 MB  │ 2024-01-15 10:20  │ インストール: 2024-01-20 │
│ ✓    │ Roboto.ttf        │ 2.1 MB  │ 2024-01-10 09:15  │ インストール: 2024-01-20 │
│ ✗    │ Arial Unicode.ttf │ 23.5 MB │ 2024-01-20 14:00  │ -                     │
└──────┴───────────────────┴─────────┴────────────────────┴────────────────────────┘

合計: 4個のフォント
  ✓ インストール済み: 3個
  ✗ 未インストール: 1個
```

### 既存フォントのインポート

ダウンロードしたフォントや既存のフォントコレクションを同期元に追加：

```bash
# 単一のフォントファイル
$ font-sync import ~/Downloads/MyNewFont.otf

1個のフォントが見つかりました:
  • MyNewFont.otf

同期元フォルダにコピーします: ~/Dropbox/MyFonts/
コピーを実行しますか？ [y/n]: y

  フォントをコピー中... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

✓ 1個のフォントをコピーしました。

ヒント: 'font-sync sync' で新しいフォントを他のMacに同期できます。

# フォルダごとインポート
$ font-sync import ~/Desktop/FontCollection/ --move
```

### 不要なフォントのクリーンアップ

同期元から削除されたフォントをシステムからも削除：

```bash
# まず確認（ドライラン）
$ font-sync clean

             削除対象のフォント（2個）              
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ フォント名        ┃ 理由               ┃ インストール日 ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ OldFont.otf       │ 同期元から削除済み │ 2023-12-01     │
│ Unused.ttf        │ 同期元から削除済み │ 2023-11-15     │
└───────────────────┴────────────────────┴────────────────┘

これはドライランモードです。実際の削除は行われません。
実際に削除するには '--execute' オプションを使用してください。

# 実際に削除
$ font-sync clean --execute
```

## よくある質問（FAQ）❓

### Q: WindowsやLinuxでも使えますか？
A: 申し訳ございません。font-syncは現在macOS専用です。フォントの保存場所やシステムの仕組みが異なるため、他のOSには対応していません。

### Q: iCloud Driveでも使えますか？
A: はい！Dropbox以外にも、iCloud Drive、Google Drive、OneDriveなど、ローカルフォルダとして同期されるクラウドストレージであれば使用できます。

### Q: フォントが多すぎて同期に時間がかかります
A: font-syncは差分同期を行うため、2回目以降の同期は高速です。初回のみ、すべてのフォントをインストールする必要があります。

### Q: 会社のセキュリティポリシーでCLIツールの使用が制限されています
A: 今後リリース予定のGUI版（有料）をご検討ください。より安全で使いやすいインターフェースを提供予定です。

### Q: フォントのライセンスは大丈夫ですか？
A: font-syncはフォントファイルをコピーするツールです。フォントのライセンスについては、各フォントのライセンス条項をご確認ください。

## トラブルシューティング 🔧

### フォントが反映されない場合

macOSのフォントキャッシュをクリア：

```bash
# フォントキャッシュをクリア
sudo atsutil databases -remove
sudo atsutil server -shutdown
sudo atsutil server -ping

# または、セーフモードで起動（Shiftキーを押しながら起動）
```

### 権限エラーが発生する場合

```bash
# フォントディレクトリの権限を確認
ls -la ~/Library/Fonts/

# 必要に応じて権限を修正
chmod 755 ~/Library/Fonts/
```

### 同期元フォルダにアクセスできない場合

1. クラウドストレージアプリが起動し、同期が完了しているか確認
2. フォルダパスが正しいか確認:
   ```bash
   ls -la ~/Dropbox/shared-fonts/
   ```
3. 再設定:
   ```bash
   font-sync init --force
   ```

## 開発者向け情報 🛠️

### アーキテクチャ

```
src/
├── commands/       # 各CLIコマンドの実装
├── config.py       # 設定管理
└── font_manager.py # フォント操作のコアロジック
```

### テストの実行

```bash
# すべてのテストを実行
pytest tests/

# カバレッジレポート付き
pytest --cov=src tests/

# 特定のテストのみ
pytest tests/test_font_manager.py -v
```

### 貢献方法

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチをプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

### コーディング規約

- Python 3.8+ の機能を使用
- 型ヒント（Type Hints）必須
- docstringはGoogle形式
- テストカバレッジ80%以上を維持

## ロードマップ 🗺️

- [x] v1.0 - 基本機能の実装
- [ ] v1.1 - パフォーマンス最適化（1000フォント以上対応）
- [ ] v1.2 - 自動同期機能（フォルダ監視）
- [ ] v1.3 - Homebrew対応
- [ ] v2.0 - GUI版リリース（有料）

## ライセンス 📄

このプロジェクトはMIT Licenseのもとで公開されています。詳細は[LICENSE](LICENSE)ファイルをご覧ください。

## 作者 ✍️

**URAPRO**
- GitHub: [@URAPRO](https://github.com/URAPRO)
- X (Twitter): [@tk_adio](https://twitter.com/tk_adio)

## サポート 💖

もしfont-syncが役に立ったら：
- ⭐ このリポジトリにスターをつける
- 🐛 バグを見つけたら[Issue](https://github.com/URAPRO/font-sync/issues)を作成
- 💡 アイデアがあれば[Discussion](https://github.com/URAPRO/font-sync/discussions)で共有

---

**注意**: このツールはmacOS専用です。WindowsやLinuxでの動作は保証されません。

<p align="center">Made with ❤️ for designers and developers on macOS</p> 