from sqlalchemy import create_engine, text
from datetime import datetime

# DBエンジン作成
engine = create_engine("sqlite:///database.db")

# 複数の初期データ
data = [
    ('math', 'report', 3, '2025-06-30', datetime(2025, 6, 1, 12, 0), 120),
    ('english', 'homework', 2, '2025-06-28', datetime(2025, 6, 2, 10, 0), 60),
    ('science', 'report', 4, '2025-07-01', datetime(2025, 6, 3, 15, 0), 180),
    ('history', 'presentation', 1, '2025-06-25', datetime(2025, 6, 1, 9, 0), 45),
    ('programming', 'assignment', 5, '2025-06-29', datetime(2025, 6, 4, 14, 0), 240),
]

# 挿入処理
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO task (subject, category, difficulty, due_date, created_at, time_spent)
        VALUES (:subject, :category, :difficulty, :due_date, :created_at, :time_spent)
    """), [
        {
            "subject": s,
            "category": c,
            "difficulty": d,
            "due_date": dd,
            "created_at": ca,
            "time_spent": ts
        } for s, c, d, dd, ca, ts in data
    ])

print("✅ 初期データを挿入しました。")
