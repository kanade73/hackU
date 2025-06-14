# create_tables.py

from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///database.db")

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL,
            available_minutes INTEGER NOT NULL
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL,
            period INTEGER NOT NULL,
            subject TEXT
        )
    """))

    from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///database.db")

with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO timetable (weekday, period, subject)
        VALUES (5, 1, '数学'), (5, 2, '物理'), (6, 1, '英語')
    """))

print("✅ ダミーデータ追加完了")


print("✅ テーブル作成が完了しました。")
