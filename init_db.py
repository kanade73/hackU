from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///database.db")

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

import sqlite3

def init_db():
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    print("✅ データベース初期化が完了しました。")

if __name__ == "__main__":
    init_db()

print("✅ テーブル作成が完了しました。")
