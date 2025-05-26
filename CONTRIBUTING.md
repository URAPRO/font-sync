# font-syncへの貢献ガイド 🤝

font-syncへの貢献を検討いただき、ありがとうございます！このガイドでは、プロジェクトへの貢献方法を説明します。

## 📋 目次

- [行動規範](#行動規範)
- [貢献の方法](#貢献の方法)
- [開発環境のセットアップ](#開発環境のセットアップ)
- [コーディング規約](#コーディング規約)
- [プルリクエストのプロセス](#プルリクエストのプロセス)
- [イシューの報告](#イシューの報告)

## 行動規範

このプロジェクトに参加するすべての人は、以下の原則に従ってください：

- 🤝 相互尊重と建設的なコミュニケーション
- 🌍 多様性を歓迎し、包括的な環境を維持
- 💡 建設的な批判を提供し、受け入れる
- 🎯 プロジェクトとコミュニティの最善の利益を優先

## 貢献の方法

### 1. バグ報告 🐛

バグを見つけた場合：

1. [Issues](https://github.com/yourusername/font-sync/issues)で既存の報告を確認
2. 新しいイシューを作成し、以下を含める：
   - 明確なタイトルと説明
   - 再現手順
   - 期待される動作と実際の動作
   - 環境情報（macOSバージョン、Pythonバージョン等）
   - 可能であればスクリーンショットやログ

### 2. 機能提案 💡

新機能のアイデアがある場合：

1. [Discussions](https://github.com/yourusername/font-sync/discussions)で議論を開始
2. 以下を説明：
   - 機能の概要と目的
   - ユースケース
   - 実装案（あれば）

### 3. コードの貢献 💻

コードで貢献する場合：

1. イシューを作成または既存のイシューにコメント
2. フォークしてブランチを作成
3. 変更を実装
4. テストを追加/更新
5. プルリクエストを作成

## 開発環境のセットアップ

### 1. リポジトリのフォークとクローン

```bash
# フォーク後、自分のリポジトリをクローン
git clone https://github.com/yourusername/font-sync.git
cd font-sync

# 上流リポジトリを追加
git remote add upstream https://github.com/originaluser/font-sync.git
```

### 2. 開発環境の準備

```bash
# 仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 開発用依存関係をインストール
pip install -r requirements-dev.txt
pip install -e .

# pre-commitフックの設定
pre-commit install
```

### 3. ブランチの作成

```bash
# 最新のmainブランチを取得
git checkout main
git pull upstream main

# フィーチャーブランチを作成
git checkout -b feature/your-feature-name
```

## コーディング規約

### Python スタイルガイド

- **PEP 8**に準拠
- **Black**でコードフォーマット
- **型ヒント**を必ず使用
- **docstring**はGoogle形式

```python
def calculate_hash(self, file_path: Path) -> str:
    """ファイルのSHA256ハッシュを計算する。
    
    Args:
        file_path: ハッシュを計算するファイルのパス
        
    Returns:
        SHA256ハッシュ値（16進数文字列）
        
    Raises:
        FileNotFoundError: ファイルが存在しない場合
        IOError: ファイルの読み込みに失敗した場合
    """
```

### コミットメッセージ

[Conventional Commits](https://www.conventionalcommits.org/)形式を使用：

```
feat: 新しいwatchコマンドを追加
fix: 大容量フォントの同期時のメモリリークを修正
docs: README.mdのインストール手順を更新
test: FontManagerのテストカバレッジを向上
refactor: config.pyのエラーハンドリングを改善
```

### テスト

- すべての新機能にテストを追加
- 既存のテストが通ることを確認
- カバレッジ80%以上を維持

```bash
# テストの実行
pytest tests/

# カバレッジ付きテスト
pytest --cov=src tests/

# 特定のテストのみ
pytest tests/test_font_manager.py::TestFontManager::test_scan_fonts -v
```

## プルリクエストのプロセス

### 1. プルリクエスト作成前

- [ ] すべてのテストが通る
- [ ] コードフォーマットが適切
- [ ] ドキュメントを更新
- [ ] CHANGELOGに変更を記載

```bash
# コードフォーマット
black src/ tests/

# リンター実行
flake8 src/ tests/

# 型チェック
mypy src/
```

### 2. プルリクエストの作成

タイトルと説明に以下を含める：

```markdown
## 概要
このPRで解決する問題や追加する機能の説明

## 変更内容
- 具体的な変更点のリスト
- 技術的な詳細

## テスト方法
1. 変更をテストする手順
2. 期待される結果

## 関連イシュー
Fixes #123
```

### 3. レビュープロセス

- レビュアーのフィードバックに迅速に対応
- 議論は建設的に
- 必要に応じて変更を追加

## イシューの報告

### バグ報告テンプレート

```markdown
**説明**
バグの明確で簡潔な説明

**再現手順**
1. '...'を実行
2. '...'をクリック
3. エラーが発生

**期待される動作**
期待される動作の説明

**スクリーンショット**
該当する場合は追加

**環境:**
 - OS: [例: macOS 14.0]
 - Python: [例: 3.11.0]
 - font-sync: [例: 1.0.0]
```

### 機能リクエストテンプレート

```markdown
**解決したい問題**
この機能で解決したい問題の説明

**提案する解決策**
どのように解決したいかの説明

**代替案**
検討した他の解決策

**追加情報**
その他の関連情報
```

## 質問とサポート

- 一般的な質問: [Discussions](https://github.com/yourusername/font-sync/discussions)
- バグ報告: [Issues](https://github.com/yourusername/font-sync/issues)
- セキュリティ問題: security@example.com（公開イシューを作成しないでください）

## ライセンス

貢献されたコードは、プロジェクトと同じMIT Licenseの下でライセンスされます。

---

ありがとうございます！ 🙏

あなたの貢献がfont-syncをより良いツールにします。 