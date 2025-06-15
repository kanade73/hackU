import os
from sqlalchemy import create_engine, text

# 絶対パスを利用して database.db を指定する
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URI, echo=True)

def create_tables():
    with engine.begin() as conn:
        # user_settings テーブルの作成
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday INTEGER NOT NULL,
                available_minutes INTEGER NOT NULL
            )
        """))
        # timetable テーブルの作成
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday INTEGER NOT NULL,
                period INTEGER NOT NULL,
                subject TEXT
            )
        """))
        print("✅ テーブル作成が完了しました。")

def insert_dummy_data():
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO timetable (weekday, period, subject)
            VALUES (5, 1, '数学'), (5, 2, '物理'), (6, 1, '英語')
        """))
        print("✅ ダミーデータ追加完了")

if __name__ == "__main__":
    create_tables()
    insert_dummy_data()
