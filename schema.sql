-- 課題テーブル
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

-- 曜日ごとの使える時間
CREATE TABLE IF NOT EXISTS available_time (
    weekday INTEGER PRIMARY KEY,
    available_hours REAL
);

-- 時間割テーブル
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weekday INTEGER NOT NULL,
    period INTEGER NOT NULL,
    subject TEXT NOT NULL
);
