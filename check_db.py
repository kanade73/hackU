import os
from sqlalchemy import create_engine, text

# 現在のファイルの場所を基準に絶対パスを設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

# エンジン作成
engine = create_engine(DATABASE_URI, echo=True)

with engine.begin() as conn:
    result = conn.execute(text("SELECT * FROM timetable"))
    for row in result:
        print(row)
