# font-sync クイックスタートガイド 🚀

このガイドでは、5分でfont-syncを使い始める方法を説明します。

## 📋 前提条件

- macOS 10.14以降
- Python 3.8以降（確認方法: `python3 --version`）
- Dropboxなどのクラウドストレージ（フォント共有用）

## 🔧 インストール

### 最も簡単な方法（pip）

```bash
pip3 install font-sync
```

### 開発版を使う場合

```bash
git clone https://github.com/yourusername/font-sync.git
cd font-sync
pip3 install -e .
```

## 🎯 3ステップで始める

### ステップ1: 初期設定

```bash
font-sync init
```

以下のように表示されます：

```
font-syncの初期設定を開始します。

同期元フォルダのパスを入力してください。
例: ~/Dropbox/shared-fonts/
同期元フォルダのパス [~/Dropbox/shared-fonts/]: 
```

Dropbox内のフォント用フォルダを指定してEnterを押します。

### ステップ2: フォントを同期元に配置

Finderで同期元フォルダを開いて、共有したいフォント（.otf/.ttf）をコピーします：

```bash
# Finderで開く
open ~/Dropbox/shared-fonts/
```

### ステップ3: 同期を実行

```bash
font-sync sync
```

これで完了です！ 🎉

## 📱 他のMacでの設定

他のMacでも同じ手順を繰り返すだけです：

1. font-syncをインストール
2. `font-sync init` で同じDropboxフォルダを指定
3. `font-sync sync` で同期

## 💡 便利な使い方

### フォントの状態を確認

```bash
# きれいな表で表示
font-sync list

# インストール済みのみ表示
font-sync list --status installed
```

### 新しいフォントを追加

```bash
# ダウンロードしたフォントを同期元に追加
font-sync import ~/Downloads/NewFont.otf
```

### 不要なフォントを削除

```bash
# まず確認
font-sync clean

# 実際に削除
font-sync clean --execute
```

## ❓ トラブルシューティング

### 「コマンドが見つかりません」と表示される

```bash
# PATHを確認
echo $PATH

# pip3でインストールした場所を確認
pip3 show font-sync

# 必要に応じてPATHに追加
export PATH="$PATH:~/.local/bin"
```

### 権限エラーが出る

```bash
# フォントディレクトリの権限を修正
chmod 755 ~/Library/Fonts/
```

### フォントが反映されない

アプリケーションを再起動するか、以下のコマンドを実行：

```bash
# フォントキャッシュをクリア
sudo atsutil databases -remove
```

## 🎓 次のステップ

- [完全なドキュメント](README.md)を読む
- [自動同期の設定](docs/automation.md)を行う
- [チーム向けのベストプラクティス](docs/team-guide.md)を確認

## 💬 サポート

問題が解決しない場合は：

1. [FAQ](README.md#よくある質問faq)を確認
2. [Issue](https://github.com/yourusername/font-sync/issues)を作成
3. [Discussion](https://github.com/yourusername/font-sync/discussions)で質問

---

<p align="center">
Happy Font Syncing! 🎨<br>
<a href="https://github.com/yourusername/font-sync">⭐ Star on GitHub</a>
</p> 