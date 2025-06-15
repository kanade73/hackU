import os
from sqlalchemy import create_engine, text

# 現在のファイルの場所を基準に絶対パスを設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URI, echo=True)

with engine.begin() as conn:
    delete_query = text("""
        DELETE FROM timetable
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM timetable
            GROUP BY weekday, period, subject
        )
    """)
    conn.execute(delete_query)

    # 削除後の確認用に、テーブルの全データを再度表示
    result = conn.execute(text("SELECT * FROM timetable"))
    for row in result:
        print(row)
