from sqlalchemy import create_engine, text
from datetime import datetime

# SQLite データベースに接続（database.db）
engine = create_engine("sqlite:///database.db", echo=True)

def init_db():
    with engine.begin() as conn:
        # === テーブル作成 ===
        # 課題テーブル
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS task (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty INTEGER NOT NULL,
                due_date DATE NOT NULL,
                created_at DATETIME NOT NULL,
                predicted_time REAL,
                time_spent REAL,
                assigned_for_today INTEGER DEFAULT 0,
                assigned_date DATE
            );
        """))
        # 曜日ごとの使える時間テーブル
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS available_time (
                weekday INTEGER PRIMARY KEY,
                available_hours REAL
            );
        """))
        # 時間割テーブル
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday INTEGER NOT NULL,
                period INTEGER NOT NULL,
                subject TEXT NOT NULL
            );
        """))
        
        # === 初期データ挿入 ===
        # available_timeテーブル：大学生向けの曜日ごとの使える時間（available_hours を「時間」で設定）
        conn.execute(text("DELETE FROM available_time"))
        conn.execute(text("""
            INSERT INTO available_time (weekday, available_hours) VALUES
            (0, 6),   -- 月曜日
            (1, 8),   -- 火曜日
            (2, 5),   -- 水曜日
            (3, 7),   -- 木曜日
            (4, 4),   -- 金曜日
            (5, 3),   -- 土曜日
            (6, 3)    -- 日曜日
        """))
        
        # timetableテーブル：大学の授業や講義・実験・ゼミなどを想定
        conn.execute(text("DELETE FROM timetable"))
        conn.execute(text("""
            INSERT INTO timetable (weekday, period, subject) VALUES
            (0, 1, '線形代数'),
            (0, 2, '物理学基礎'),
            (0, 3, 'プログラミング基礎'),
            (1, 1, '統計学'),
            (1, 2, '英語コミュニケーション'),
            (1, 3, '化学実験'),
            (2, 1, '経済学概論'),
            (2, 2, '体育'),
            (2, 3, 'データ構造'),
            (3, 1, '微分積分'),
            (3, 2, '歴史学概論'),
            (3, 3, '情報理論'),
            (4, 1, '哲学入門'),
            (4, 2, 'プログラミング応用'),
            (4, 3, 'リーダーシップ論'),
            (5, 1, 'ゼミ活動'),
            (5, 2, '自由研究'),
            (5, 3, 'ボランティア活動'),
            (6, 1, '読書会'),
            (6, 2, '映画研究'),
            (6, 3, '週末活動')
        """))
        
        # taskテーブル：大学生向けの課題データ例
        # created_at は現在日時（ここでは固定値も可）
        conn.execute(text("DELETE FROM task"))
        conn.execute(text("""
            INSERT INTO task (subject, category, difficulty, due_date, created_at, predicted_time)
            VALUES 
            ('線形代数の課題', '宿題', 3, '2025-06-17', '2025-06-15 10:00:00', 120),
            ('物理学実験レポート', 'レポート', 4, '2025-06-18', '2025-06-15 11:00:00', 180),
            ('プログラミングプロジェクト', 'プロジェクト', 5, '2025-06-20', '2025-06-15 12:00:00', 240),
            ('統計学テスト準備', 'テスト準備', 2, '2025-06-19', '2025-06-15 13:00:00', 90),
            ('英語プレゼン資料作成', 'プレゼン', 3, '2025-06-21', '2025-06-15 14:00:00', 150)
        """))
    print("✅ 大学生向け初期データの挿入が完了しました。")

if __name__ == "__main__":
    init_db()
