# migrate_add_is_completed.py

import os
from sqlalchemy import create_engine, text

# 現在のスクリプトのディレクトリからDBファイルの絶対パスを生成
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

# エンジンを作成
engine = create_engine(DATABASE_URI)

def add_column_if_not_exists():
    with engine.begin() as conn:
        # 既存のカラム名一覧を取得
        result = conn.execute(text("PRAGMA table_info(task)"))
        columns = [row[1] for row in result.fetchall()]
        
        # すでにカラムが存在していれば何もしない
        if "is_completed" in columns:
            print("✅ 'is_completed' カラムはすでに存在します。")
        else:
            # カラムを追加
            conn.execute(text("ALTER TABLE task ADD COLUMN is_completed BOOLEAN DEFAULT 0"))
            print("✅ 'is_completed' カラムを追加しました。")

if __name__ == "__main__":
    add_column_if_not_exists()
