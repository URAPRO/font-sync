"""統合テスト - コマンドのエンドツーエンド動作確認"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.font_manager import FontManager
from src.main import app


@pytest.mark.integration
class TestIntegration:
    """統合テストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナーを作成"""
        return CliRunner()

    @pytest.fixture
    def setup_environment(self, mock_home_dir: Path, mock_sync_folder: Path,
                         mock_font_install_dir: Path, monkeypatch):
        """テスト環境をセットアップ"""
        # ホームディレクトリとフォントインストールディレクトリをモック
        monkeypatch.setattr(Path, "home", lambda: mock_home_dir)

        # os.path.expanduserをモック
        def mock_expanduser(path):
            if path.startswith("~/"):
                return str(mock_home_dir / path[2:])
            return path
        monkeypatch.setattr("os.path.expanduser", mock_expanduser)

        # FontManagerクラスの__init__メソッドをモックして、font_install_dirを設定
        original_init = FontManager.__init__

        def mock_init(self):
            original_init(self)
            self.font_install_dir = mock_font_install_dir

        monkeypatch.setattr(FontManager, "__init__", mock_init)

        return {
            "home_dir": mock_home_dir,
            "sync_folder": mock_sync_folder,
            "font_install_dir": mock_font_install_dir
        }

    def test_init_sync_list_workflow(self, runner, setup_environment):
        """init → sync → list の基本的なワークフローテスト"""
        env = setup_environment
        sync_folder = env["sync_folder"]

        # テスト用フォントファイルを作成（有効なヘッダーを含む）
        font1 = sync_folder / "TestFont1.otf"
        font2 = sync_folder / "TestFont2.ttf"
        font1.write_bytes(b"OTTO" + b"\x00" * 100)  # OTFヘッダー
        font2.write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 100)  # TTFヘッダー

        # 1. initコマンドの実行
        result = runner.invoke(app, ["init", "--folder", str(sync_folder), "--force"])
        assert result.exit_code == 0
        assert "設定を保存しました" in result.stdout
        assert "2個のフォントファイルが見つかりました" in result.stdout

        # 設定ファイルが作成されたことを確認
        config_file = env["home_dir"] / ".fontsync" / "config.json"
        assert config_file.exists()

        # 2. syncコマンドの実行
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
        assert "同期元フォルダ:" in result.stdout
        assert "正常に同期しました" in result.stdout  # "2個のフォントを正常に同期しました。"の一部をチェック

        # フォントがインストールされたことを確認
        assert (env["font_install_dir"] / "TestFont1.otf").exists()
        assert (env["font_install_dir"] / "TestFont2.ttf").exists()

        # 3. listコマンドの実行
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "TestFont1.otf" in result.stdout
        assert "TestFont2.ttf" in result.stdout
        assert "✓" in result.stdout  # インストール済みマーク

    def test_import_command(self, runner, setup_environment):
        """importコマンドのテスト"""
        env = setup_environment

        # 初期設定
        result = runner.invoke(app, ["init", "--folder", str(env["sync_folder"]), "--force"])
        assert result.exit_code == 0

        # インポート元のフォントを作成（有効なヘッダーを含む）
        import_dir = env["home_dir"] / "import_fonts"
        import_dir.mkdir()
        import_font = import_dir / "ImportFont.otf"
        import_font.write_bytes(b"OTTO" + b"\x00" * 100)  # OTFヘッダー

        # importコマンドの実行（確認プロンプトに"y"を入力）
        result = runner.invoke(app, ["import", str(import_font)], input="y\n")
        if result.exit_code != 0:
            print(f"Import command failed with output:\n{result.stdout}")
        assert result.exit_code == 0
        assert "インポートしました" in result.stdout or "コピーしました" in result.stdout

        # フォントが同期元フォルダにコピーされたことを確認
        assert (env["sync_folder"] / "ImportFont.otf").exists()

    def test_clean_command(self, runner, setup_environment):
        """cleanコマンドのテスト"""
        env = setup_environment

        # 初期設定とフォントの同期
        sync_folder = env["sync_folder"]
        font1 = sync_folder / "Font1.otf"
        font1.write_bytes(b"OTTO" + b"\x00" * 100)  # OTFヘッダー

        result = runner.invoke(app, ["init", "--folder", str(sync_folder), "--force"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0

        # 同期元からフォントを削除
        font1.unlink()

        # cleanコマンドの実行（ドライラン）
        result = runner.invoke(app, ["clean", "--dry-run"])
        if result.exit_code != 0:
            print(f"Clean command (dry-run) failed with output:\n{result.stdout}")
        assert result.exit_code == 0
        assert "削除対象" in result.stdout  # "削除対象のフォント"の一部をチェック
        assert "Font1.otf" in result.stdout

        # フォントはまだ存在することを確認
        assert (env["font_install_dir"] / "Font1.otf").exists()

        # cleanコマンドの実行（実際に削除）（確認プロンプトに"y"を入力）
        result = runner.invoke(app, ["clean", "--execute"], input="y\n")
        if result.exit_code != 0:
            print(f"Clean command (execute) failed with output:\n{result.stdout}")
        assert result.exit_code == 0
        assert "削除しました" in result.stdout  # "1個のフォントを削除しました"の一部をチェック

        # フォントが削除されたことを確認
        assert not (env["font_install_dir"] / "Font1.otf").exists()

    def test_error_handling(self, runner, setup_environment):
        """エラーハンドリングのテスト"""

        # 設定なしでsyncを実行
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 1
        assert "設定ファイルが見つかりません" in result.stdout

        # 存在しないフォルダでinit
        result = runner.invoke(app, ["init", "--folder", "/non/existent/folder"])
        assert result.exit_code == 1

    def test_json_output(self, runner, setup_environment):
        """JSON出力形式のテスト"""
        env = setup_environment
        sync_folder = env["sync_folder"]

        # フォントを準備（有効なヘッダーを含む）
        font1 = sync_folder / "Font1.otf"
        font1.write_bytes(b"OTTO" + b"\x00" * 100)  # OTFヘッダー

        # 初期設定と同期
        runner.invoke(app, ["init", "--folder", str(sync_folder), "--force"])
        runner.invoke(app, ["sync"])

        # JSON形式でlist実行
        result = runner.invoke(app, ["list", "--format", "json"])
        if result.exit_code != 0:
            print(f"List command (json) failed with output:\n{result.stdout}")
        assert result.exit_code == 0

        # デバッグ用に出力を表示
        print(f"JSON list output:\n{result.stdout}")

        # JSON出力を検証（JSONは最後の方に出力される）
        output = result.stdout
        # 最後の有効なJSON行を探す（オブジェクトで始まる）
        json_lines = [line for line in output.strip().split('\n') if line.startswith('{')]

        if json_lines:
            # 複数行のJSONの場合、全体を結合する必要がある
            # JSON出力の開始位置を見つける
            json_start = output.find('{\n')
            if json_start != -1:
                json_str = output[json_start:]
                try:
                    json_data = json.loads(json_str)
                    assert json_data["total_fonts"] == 1
                    assert json_data["fonts"][0]["name"] == "Font1.otf"
                    assert json_data["fonts"][0]["is_installed"] is True
                except json.JSONDecodeError:
                    pytest.fail(f"JSONのパースに失敗しました: {json_str[:100]}...")
            else:
                pytest.fail("JSON出力が見つかりませんでした")
        else:
            # JSON出力が見つからない場合はテストを失敗させる
            pytest.fail("JSON出力が見つかりませんでした")
