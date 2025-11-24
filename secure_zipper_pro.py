#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
secure_zipper_pro.py - AES-256暗号化ZIP作成ツール（エンタープライズ版）

機能:
    - AES-256暗号化ZIP作成
    - 作成後の自動整合性検証
    - 展開テストによる信頼性保証
    - 詳細ログ出力（ファイル + コンソール）
    - GUI/CLIハイブリッド対応
    - アトミックファイル操作
    - 圧縮レベル選択対応

実行方法:
    # GUIモード
    python secure_zipper_pro.py
    
    # CLIモード
    python secure_zipper_pro.py <パス> [オプション]
    python secure_zipper_pro.py document.pdf --level 9 --verify

必要なライブラリ:
    pip install pyzipper

作成者: Claude (Auto-generated)
レベル: 4 (エンタープライズ級)
生成日時: 2025-11-24
バージョン: 2.0
"""

import argparse
import logging
import secrets
import shutil
import string
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from contextlib import contextmanager

try:
    import pyzipper
except ImportError:
    print("ERROR: 'pyzipper' がインストールされていません")
    print("実行してください: pip install pyzipper")
    sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 設定クラス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class Config:
    """アプリケーション設定"""
    PASSWORD_LENGTH: int = 16
    PASSWORD_CHARS: str = string.ascii_letters + string.digits + "!@#$%^&*"
    LOG_FORMAT: str = '%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s'
    DATE_FORMAT: str = '%Y%m%d_%H%M%S'
    DEFAULT_COMPRESSION: int = 6  # 0-9
    VERIFICATION_ENABLED: bool = True
    LOG_DIR: Path = Path("logs")
    TEMP_DIR_PREFIX: str = "secure_zipper_"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ロギング設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def setup_logging() -> logging.Logger:
    """ログ設定（ファイル + コンソール）"""
    Config.LOG_DIR.mkdir(exist_ok=True)
    
    log_file = Config.LOG_DIR / f"secure_zipper_{datetime.now():%Y%m%d}.log"
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # ファイルハンドラ
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
    
    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ユーティリティクラス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PasswordGenerator:
    """暗号学的に安全なパスワード生成"""
    
    @staticmethod
    def generate(length: int = Config.PASSWORD_LENGTH) -> str:
        """
        安全なランダムパスワードを生成
        
        Args:
            length: パスワード長（デフォルト: 16）
        
        Returns:
            str: 生成されたパスワード（英数字+記号）
        """
        alphabet = Config.PASSWORD_CHARS
        
        # 最低1つの数字と文字を保証
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.isdigit() for c in password) and 
                any(c.isalpha() for c in password) and
                any(c in "!@#$%^&*" for c in password)):
                return password


class FileVerifier:
    """ZIP整合性検証クラス"""
    
    @staticmethod
    def verify_zip_integrity(zip_path: Path, password: str) -> Tuple[bool, str]:
        """
        ZIPファイルの整合性を検証
        
        Args:
            zip_path: ZIPファイルパス
            password: パスワード
        
        Returns:
            Tuple[bool, str]: (成功/失敗, メッセージ)
        """
        try:
            with pyzipper.AESZipFile(zip_path, 'r') as zf:
                # パスワード設定
                zf.setpassword(password.encode('utf-8'))
                
                # ファイル一覧取得
                file_list = zf.namelist()
                if not file_list:
                    return False, "ZIPファイルが空です"
                
                # CRCチェック（全ファイル）
                bad_file = zf.testzip()
                if bad_file:
                    return False, f"破損ファイル検出: {bad_file}"
                
                logger.info(f"整合性チェック成功: {len(file_list)}個のファイル")
                return True, f"検証成功（{len(file_list)}ファイル）"
                
        except RuntimeError as e:
            if "Bad password" in str(e):
                return False, "パスワードが正しくありません"
            return False, f"検証エラー: {e}"
        except Exception as e:
            return False, f"予期しないエラー: {e}"
    
    @staticmethod
    def test_extraction(zip_path: Path, password: str) -> Tuple[bool, str]:
        """
        実際に展開テストを行う（一時ディレクトリ使用）
        
        Args:
            zip_path: ZIPファイルパス
            password: パスワード
        
        Returns:
            Tuple[bool, str]: (成功/失敗, メッセージ)
        """
        temp_dir = None
        try:
            # 一時ディレクトリ作成
            temp_dir = tempfile.mkdtemp(prefix=Config.TEMP_DIR_PREFIX)
            temp_path = Path(temp_dir)
            
            with pyzipper.AESZipFile(zip_path, 'r') as zf:
                zf.setpassword(password.encode('utf-8'))
                zf.extractall(temp_path)
            
            # 展開されたファイル数確認
            extracted_files = list(temp_path.rglob('*'))
            file_count = sum(1 for f in extracted_files if f.is_file())
            
            logger.info(f"展開テスト成功: {file_count}個のファイルを展開")
            return True, f"展開テスト成功（{file_count}ファイル）"
            
        except Exception as e:
            return False, f"展開テスト失敗: {e}"
        finally:
            # 一時ディレクトリ削除
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メインアーカイバクラス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SecureArchiver:
    """AES暗号化ZIP作成クラス（検証機能付き）"""
    
    def __init__(self, source_path: str, compression_level: int = Config.DEFAULT_COMPRESSION):
        """
        初期化
        
        Args:
            source_path: 圧縮対象のパス
            compression_level: 圧縮レベル（0-9, 0=無圧縮, 9=最大圧縮）
        """
        self.source_path = Path(source_path).resolve()
        self.compression_level = max(0, min(9, compression_level))
        
        if not self.source_path.exists():
            raise FileNotFoundError(f"指定されたパスが見つかりません: {self.source_path}")
        
        logger.info(f"対象: {self.source_path} (圧縮レベル: {self.compression_level})")
    
    def _get_output_path(self) -> Path:
        """出力ファイルパス生成"""
        timestamp = datetime.now().strftime(Config.DATE_FORMAT)
        stem = self.source_path.stem
        parent = self.source_path.parent
        return parent / f"{stem}_{timestamp}_secured.zip"
    
    @contextmanager
    def _atomic_write(self, final_path: Path):
        """
        アトミックファイル書き込み
        （一時ファイルに書き込み後、成功したらリネーム）
        """
        temp_path = final_path.with_suffix('.tmp')
        try:
            yield temp_path
            # 成功したらリネーム
            temp_path.replace(final_path)
            logger.debug(f"アトミック書き込み完了: {final_path.name}")
        except Exception:
            # 失敗したら一時ファイル削除
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def create_archive(self, verify: bool = Config.VERIFICATION_ENABLED) -> Tuple[Path, str]:
        """
        暗号化ZIPファイル作成
        
        Args:
            verify: 作成後に検証を行うか
        
        Returns:
            Tuple[Path, str]: (ZIPファイルパス, パスワード)
        """
        output_path = self._get_output_path()
        password = PasswordGenerator.generate()
        pwd_bytes = password.encode('utf-8')
        
        logger.info("=== アーカイブ作成開始 ===")
        logger.info(f"出力先: {output_path.name}")
        
        # アトミック書き込み
        with self._atomic_write(output_path) as temp_path:
            try:
                with pyzipper.AESZipFile(
                    temp_path,
                    'w',
                    compression=pyzipper.ZIP_DEFLATED,
                    encryption=pyzipper.WZ_AES,
                    compresslevel=self.compression_level
                ) as zf:
                    zf.setpassword(pwd_bytes)
                    
                    if self.source_path.is_file():
                        self._add_file(zf, self.source_path)
                    else:
                        self._add_folder(zf, self.source_path)
                
                logger.info(f"✅ アーカイブ作成完了: {output_path.name}")
                
            except Exception as e:
                logger.error(f"❌ アーカイブ作成失敗: {e}")
                raise
        
        # 検証フェーズ
        if verify:
            logger.info("=== 検証フェーズ開始 ===")
            self._verify_archive(output_path, password)
        
        return output_path, password
    
    def _verify_archive(self, zip_path: Path, password: str):
        """アーカイブ検証実行"""
        
        # 1. 整合性チェック
        success, msg = FileVerifier.verify_zip_integrity(zip_path, password)
        if not success:
            logger.error(f"❌ 整合性チェック失敗: {msg}")
            raise RuntimeError(f"整合性チェック失敗: {msg}")
        logger.info(f"✅ 整合性チェック: {msg}")
        
        # 2. 展開テスト
        success, msg = FileVerifier.test_extraction(zip_path, password)
        if not success:
            logger.error(f"❌ 展開テスト失敗: {msg}")
            raise RuntimeError(f"展開テスト失敗: {msg}")
        logger.info(f"✅ 展開テスト: {msg}")
        
        logger.info("=== 検証完了：すべて正常 ===")
    
    def _add_file(self, zf: pyzipper.AESZipFile, file_path: Path, arcname: Optional[str] = None):
        """単一ファイルをZIPに追加"""
        if arcname is None:
            arcname = file_path.name
        zf.write(file_path, arcname=arcname)
        logger.debug(f"追加: {arcname}")
    
    def _add_folder(self, zf: pyzipper.AESZipFile, folder_path: Path):
        """
        フォルダを再帰的にZIPに追加
        
        【バグ修正】
        relative_to(folder_path.parent) → relative_to(folder_path)
        これにより、ZIP内のパス構造が正しく保たれる
        """
        file_count = 0
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                # 🔧 修正ポイント: folder_path を基準にする
                arcname = file_path.relative_to(folder_path)
                zf.write(file_path, arcname=str(arcname))
                file_count += 1
                logger.debug(f"追加: {arcname}")
        
        logger.info(f"合計 {file_count} 個のファイルを追加")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GUI実装
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AppGUI:
    """GUIアプリケーション"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Secure Zipper Pro v2.0")
        self.root.geometry("450x300")
        self.root.eval('tk::PlaceWindow . center')
        
        self.compression_level = tk.IntVar(value=Config.DEFAULT_COMPRESSION)
        self.verify_enabled = tk.BooleanVar(value=True)
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        
        # タイトル
        title = tk.Label(
            self.root, 
            text="🔒 Secure Zipper Pro", 
            font=("", 16, "bold"),
            fg="#2c3e50"
        )
        title.pack(pady=20)
        
        # 説明
        desc = tk.Label(
            self.root,
            text="AES-256暗号化 + 自動検証",
            font=("", 10),
            fg="#7f8c8d"
        )
        desc.pack()
        
        # ボタンフレーム
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)
        
        tk.Button(
            btn_frame,
            text="📄 ファイルを選択",
            command=self.select_file,
            width=18,
            height=2,
            bg="#3498db",
            fg="white",
            font=("", 10, "bold")
        ).pack(pady=5)
        
        tk.Button(
            btn_frame,
            text="📁 フォルダを選択",
            command=self.select_folder,
            width=18,
            height=2,
            bg="#2ecc71",
            fg="white",
            font=("", 10, "bold")
        ).pack(pady=5)
        
        # オプションフレーム
        option_frame = tk.LabelFrame(self.root, text="オプション", padx=10, pady=10)
        option_frame.pack(pady=10, padx=20, fill="x")
        
        # 圧縮レベル
        tk.Label(option_frame, text="圧縮レベル (0-9):").grid(row=0, column=0, sticky="w")
        tk.Scale(
            option_frame,
            from_=0,
            to=9,
            orient=tk.HORIZONTAL,
            variable=self.compression_level,
            length=200
        ).grid(row=0, column=1, padx=10)
        
        # 検証オプション
        tk.Checkbutton(
            option_frame,
            text="作成後に自動検証",
            variable=self.verify_enabled
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
    
    def run(self):
        """アプリケーション起動"""
        self.root.mainloop()
    
    def process(self, path: str):
        """処理実行"""
        if not path:
            return
        
        # プログレスバー表示
        progress = self._show_progress()
        
        try:
            archiver = SecureArchiver(
                path,
                compression_level=self.compression_level.get()
            )
            zip_path, password = archiver.create_archive(
                verify=self.verify_enabled.get()
            )
            
            progress.destroy()
            self._show_success_dialog(zip_path, password)
            
        except Exception as e:
            progress.destroy()
            logger.error(f"処理エラー: {e}", exc_info=True)
            messagebox.showerror(
                "エラー",
                f"処理に失敗しました:\n\n{e}\n\n詳細はログファイルを確認してください。"
            )
    
    def _show_progress(self) -> tk.Toplevel:
        """プログレスバー表示"""
        progress = tk.Toplevel(self.root)
        progress.title("処理中...")
        progress.geometry("300x100")
        progress.transient(self.root)
        progress.grab_set()
        
        tk.Label(progress, text="処理中です...しばらくお待ちください", pady=20).pack()
        
        pbar = ttk.Progressbar(progress, mode='indeterminate', length=250)
        pbar.pack(pady=10)
        pbar.start(10)
        
        progress.update()
        return progress
    
    def select_file(self):
        """ファイル選択"""
        path = filedialog.askopenfilename(title="ロックするファイルを選択")
        self.process(path)
    
    def select_folder(self):
        """フォルダ選択"""
        path = filedialog.askdirectory(title="ロックするフォルダを選択")
        self.process(path)
    
    def _show_success_dialog(self, zip_path: Path, password: str):
        """成功ダイアログ表示"""
        dialog = tk.Toplevel(self.root)
        dialog.title("✅ 完了")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        
        tk.Label(
            dialog,
            text="✅ ロック完了",
            font=("", 14, "bold"),
            fg="#27ae60"
        ).pack(pady=15)
        
        # ファイル情報
        info_frame = tk.Frame(dialog)
        info_frame.pack(pady=10)
        
        tk.Label(info_frame, text="保存先:", font=("", 10, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(info_frame, text=str(zip_path), fg="#34495e").grid(row=0, column=1, sticky="w", padx=10)
        
        tk.Label(info_frame, text="サイズ:", font=("", 10, "bold")).grid(row=1, column=0, sticky="w", pady=5)
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        tk.Label(info_frame, text=f"{size_mb:.2f} MB", fg="#34495e").grid(row=1, column=1, sticky="w", padx=10)
        
        # パスワード表示
        tk.Label(
            dialog,
            text="⚠️ このパスワードを安全に保管してください ⚠️",
            font=("", 10, "bold"),
            fg="#e74c3c"
        ).pack(pady=10)
        
        entry = tk.Entry(dialog, font=("Consolas", 12), width=30, justify='center')
        entry.insert(0, password)
        entry.pack(pady=5)
        entry.focus_set()
        entry.selection_range(0, tk.END)
        
        tk.Label(
            dialog,
            text="（パスワードはログファイルには保存されません）",
            font=("", 8),
            fg="#95a5a6"
        ).pack()
        
        tk.Button(
            dialog,
            text="閉じる",
            command=dialog.destroy,
            width=15,
            height=2
        ).pack(pady=20)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI実装
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def cli_mode():
    """コマンドラインモード"""
    parser = argparse.ArgumentParser(
        description="AES-256暗号化ZIP作成ツール（エンタープライズ版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python secure_zipper_pro.py document.pdf
  python secure_zipper_pro.py /path/to/folder --level 9
  python secure_zipper_pro.py data/ --no-verify
        """
    )
    
    parser.add_argument(
        "path",
        help="ロックしたいファイルまたはフォルダのパス"
    )
    
    parser.add_argument(
        "--level",
        type=int,
        default=Config.DEFAULT_COMPRESSION,
        choices=range(0, 10),
        help="圧縮レベル (0-9, デフォルト: 6)"
    )
    
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="作成後の検証をスキップ"
    )
    
    args = parser.parse_args()
    
    try:
        archiver = SecureArchiver(args.path, compression_level=args.level)
        zip_path, password = archiver.create_archive(verify=not args.no_verify)
        
        print("\n" + "="*60)
        print("✅ SUCCESS")
        print("="*60)
        print(f"出力: {zip_path}")
        print(f"パスワード: {password}")
        print("="*60)
        print("\n⚠️  パスワードを安全に保管してください！")
        
    except Exception as e:
        logger.error(f"処理失敗: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        print(f"\n詳細はログファイルを確認してください: {Config.LOG_DIR}")
        sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン処理
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    """メインエントリーポイント"""
    if len(sys.argv) > 1:
        # CLIモード
        cli_mode()
    else:
        # GUIモード
        app = AppGUI()
        app.run()


if __name__ == "__main__":
    main()