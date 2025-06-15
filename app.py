import os
from flask import Flask, request, render_template, redirect, url_for
from sqlalchemy import create_engine, text
from datetime import datetime, date
from model.predict import predict_single_task, batch_predict_missing_tasks

# 絶対パスを使ってデータベースファイルを指定する
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

app = Flask(__name__)
engine = create_engine(DATABASE_URI, echo=True)

# 英語曜日とその数値へのマッピング（index.html 用）
weekday_mapping = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

# 日本語曜日リストとそのマッピング（setup 用）
jp_days = ["月", "火", "水", "木", "金", "土", "日"]
jp_to_int = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}

# 必要なタスク予測のバッチ処理（必要なら両箇所呼び出しを調整）
batch_predict_missing_tasks()

def maybe_generate_today_tasks():
    today = date.today()
    today_str = today.isoformat()
    weekday = today.weekday()

    with engine.begin() as conn:
        # 既に今日のタスクが割り当てられているかチェック
        count = conn.execute(text("""
            SELECT COUNT(*) FROM task
            WHERE assigned_for_today = 1 AND assigned_date = :today
        """), {"today": today_str}).scalar()

        if count > 0:
            return  # 今日のタスクリストが既に生成されている

        # 前日までの割り当てをリセット
        conn.execute(text("""
            UPDATE task
            SET assigned_for_today = 0, assigned_date = NULL
            WHERE assigned_for_today = 1
        """))

        # 今日使える時間の60%を取得（分単位）
        available = conn.execute(text("""
            SELECT available_hours FROM available_time WHERE weekday = :wd
        """), {"wd": weekday}).scalar() or 0
        limit_minutes = available * 60 * 0.6

        # 未完了タスク（予測時間あり）を締切昇順で取得
        candidates = conn.execute(text("""
            SELECT * FROM task
            WHERE time_spent IS NULL AND predicted_time IS NOT NULL
            ORDER BY due_date ASC, predicted_time ASC
        """)).fetchall()

        total = 0
        for task in candidates:
            if total + task.predicted_time <= limit_minutes:
                # 今日やることとして登録
                conn.execute(text("""
                    UPDATE task
                    SET assigned_for_today = 1, assigned_date = :today
                    WHERE id = :id
                """), {"id": task.id, "today": today_str})
                total += task.predicted_time
            else:
                break  # 時間上限超過のため、以降は残す

@app.before_request
def before_request():
    # setup や timetable ページからのアクセスはタスク自動生成をスキップする
    if request.endpoint not in ("setup", "edit_timetable", "static"):
        maybe_generate_today_tasks()

@app.route("/")
def index():
    with engine.begin() as conn:
        today_weekday_name = datetime.now().strftime("%A")
        today_weekday = weekday_mapping[today_weekday_name]

        # 本日のタスク（assigned_for_today が1のもの）
        tasks_today = conn.execute(text("""
            SELECT * FROM task
            WHERE assigned_for_today = 1
            ORDER BY due_date
        """)).fetchall()

        # 未割当・または残りのタスク
        tasks_remaining = conn.execute(text("""
            SELECT * FROM task
            WHERE assigned_for_today = 0
            ORDER BY due_date
        """)).fetchall()

        # 今週の時間割（本日の曜日のもの）
        timetable = conn.execute(text("""
            SELECT * FROM timetable
            WHERE weekday = :weekday
            ORDER BY period
        """), {"weekday": today_weekday}).fetchall()

    return render_template("index.html", tasks_today=tasks_today, tasks_remaining=tasks_remaining, timetable=timetable)

@app.route("/start_task/<int:task_id>")
def start_task(task_id):
    return render_template("start_task.html", task_id=task_id)

@app.route("/finish_task/<int:task_id>", methods=["POST"])
def finish_task(task_id):
    try:
        time_spent = float(request.form["time_spent"])
    except (ValueError, KeyError):
        return "Invalid input", 400

    with engine.begin() as conn:
        stmt = text("UPDATE task SET time_spent = :time_spent WHERE id = :task_id")
        conn.execute(stmt, {"time_spent": time_spent, "task_id": task_id})
    return redirect(url_for("index"))

@app.route("/add_task", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        subject = request.form["subject"]
        category = request.form["category"]
        difficulty = int(request.form["difficulty"])
        due_date = request.form["due_date"]
        created_at = datetime.now()

        predicted_time = predict_single_task(subject, category, difficulty, due_date, created_at)

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO task (subject, category, difficulty, due_date, created_at, predicted_time)
                VALUES (:subject, :category, :difficulty, :due_date, :created_at, :predicted_time)
            """), {
                "subject": subject,
                "category": category,
                "difficulty": difficulty,
                "due_date": due_date,
                "created_at": created_at,
                "predicted_time": predicted_time
            })

        return redirect(url_for("index"))

    # GET時、時間割データも渡す
    today_weekday_name = datetime.now().strftime("%A")
    today_weekday = weekday_mapping[today_weekday_name]
    with engine.begin() as conn:
        timetable = conn.execute(text("""
            SELECT * FROM timetable
            WHERE weekday = :weekday
            ORDER BY period
        """), {"weekday": today_weekday}).fetchall()

    return render_template("add_task.html", timetable=timetable)

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "POST":
        # setup.html のフォームでは、曜日は日本語のリスト ["月", "火", "水", "木", "金", "土", "日"]
        available_times = {}
        for index, day in enumerate(jp_days):
            # フォームフィールド名 "available_<index>"
            available_times[day] = float(request.form.get(f"available_{index}", 0))
        
        timetable_entries = []
        # 各曜日の時間割入力（フィールド名例: "timetable_0_1" ～ "timetable_6_6"）
        for index, day in enumerate(jp_days):
            for period in range(1, 7):
                field_name = f"timetable_{index}_{period}"
                subject = request.form.get(field_name, "").strip()
                if subject:
                    timetable_entries.append({
                        "weekday": jp_to_int[day],
                        "period": period,
                        "subject": subject
                    })

        with engine.begin() as conn:
            # 保存 available_time
            conn.execute(text("DELETE FROM available_time"))
            for day, hours in available_times.items():
                conn.execute(text("INSERT INTO available_time (weekday, available_hours) VALUES (:weekday, :hours)"),
                             {"weekday": jp_to_int[day], "hours": hours})

            # 保存時間割
            conn.execute(text("DELETE FROM timetable"))
            for entry in timetable_entries:
                conn.execute(text("""
                    INSERT INTO timetable (weekday, period, subject)
                    VALUES (:weekday, :period, :subject)
                """), entry)

        return redirect(url_for("index"))

    return render_template("setup.html")

@app.route("/timetable", methods=["GET", "POST"])
def edit_timetable():
    days = list(weekday_mapping.keys())  # 例: ["Monday", ...]
    if request.method == "POST":
        timetable_entries = []
        # 各曜日の時間割を更新　※投稿フォームのフィールド名は "Monday_1", ... となっている前提の場合
        for day in days:
            for period in range(1, 7):
                subject = request.form.get(f"{day}_{period}")
                if subject:
                    timetable_entries.append({
                        "weekday": weekday_mapping[day],
                        "period": period,
                        "subject": subject
                    })

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM timetable"))
            for entry in timetable_entries:
                conn.execute(text("""
                    INSERT INTO timetable (weekday, period, subject)
                    VALUES (:weekday, :period, :subject)
                """), entry)

        return redirect(url_for("edit_timetable"))

    with engine.begin() as conn:
        result = conn.execute(text("SELECT * FROM timetable")).fetchall()

    # タイムテーブルを曜日ごとの配列に変換（例: {"Monday": ["数学", "英語", ...], ...}）
    timetable_dict = {day: [""] * 6 for day in days}
    reverse_weekday_mapping = {v: k for k, v in weekday_mapping.items()}
    for row in result:
        day_name = reverse_weekday_mapping.get(row.weekday, "Unknown")
        timetable_dict[day_name][row.period - 1] = row.subject

    return render_template("edit_timetable.html", timetable=timetable_dict, days=days)

if __name__ == "__main__":
    # 重複しないよう、必要に応じてバッチ処理を呼び出してください
    batch_predict_missing_tasks()
    app.run(debug=True)
