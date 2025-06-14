from flask import Flask, request, render_template, redirect, url_for
from sqlalchemy import create_engine, text
from datetime import datetime
from model.predict import predict_single_task, batch_predict_missing_tasks

app = Flask(__name__)
engine = create_engine('sqlite:///database.db')

# 曜日名を数値に変換するマッピング（テーブル定義では weekday カラムは整数型）
weekday_mapping = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

# バッチ処理で未予測のタスクを一括予測
batch_predict_missing_tasks()

@app.route("/")
def index():
    with engine.begin() as conn:
        tasks = conn.execute(text("""
            SELECT * FROM task
            WHERE predicted_time IS NOT NULL
        """)).fetchall()

        # 今日の曜日名から整数に変換
        today_weekday_name = datetime.now().strftime("%A")
        today_weekday = weekday_mapping[today_weekday_name]

        timetable = conn.execute(text("""
            SELECT * FROM timetable
            WHERE weekday = :weekday
            ORDER BY period
        """), {"weekday": today_weekday}).fetchall()
        
    return render_template("index.html", tasks=tasks, timetable=timetable)

@app.route("/start_task/<int:task_id>")
def start_task(task_id):
    return render_template("start_task.html", task_id=task_id)

@app.route("/finish_task/<int:task_id>", methods=["POST"])
def finish_task(task_id):
    try:
        time_spent = float(request.form["time_spent"])  # 単位は分
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

        # 所要時間を予測
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

    # GET時：曜日変換してタイムテーブルを取得
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
        # 曜日ごとの利用可能時間（フォームのキーは曜日名）
        available_times = {
            day: float(request.form.get(day, 0)) for day in weekday_mapping.keys()
        }

        # 時間割の登録
        timetable_entries = []
        for day in weekday_mapping.keys():
            for period in range(1, 7):
                subject_key = f"{day}_{period}_subject"
                if subject_key in request.form and request.form[subject_key]:
                    timetable_entries.append({
                        "weekday": weekday_mapping[day],
                        "period": period,
                        "subject": request.form[subject_key]
                    })

        with engine.begin() as conn:
            # available_time テーブルの初期化と挿入（available_time テーブルのカラム名は weekday, available_hours としている前提）
            conn.execute(text("DELETE FROM available_time"))
            for day, hours in available_times.items():
                conn.execute(text("INSERT INTO available_time (weekday, available_hours) VALUES (:weekday, :hours)"),
                             {"weekday": weekday_mapping[day], "hours": hours})

            # timetable テーブルの初期化と挿入
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
    days = list(weekday_mapping.keys())  # ["Monday", ... "Sunday"]
    if request.method == "POST":
        timetable_entries = []
        for day in days:
            for period in range(1, 7):
                subject = request.form.get(f"{day}_{period}_subject")
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

    # 数値として登録されている曜日を、曜日名に変換して辞書形式に整形
    timetable_dict = {day: [""] * 6 for day in days}
    reverse_weekday_mapping = {v: k for k, v in weekday_mapping.items()}
    for row in result:
        day_name = reverse_weekday_mapping.get(row.weekday, "Unknown")
        timetable_dict[day_name][row.period - 1] = row.subject

    return render_template("edit_timetable.html", timetable=timetable_dict, days=days)


if __name__ == "__main__":
    from model.predict import batch_predict_missing_tasks
    batch_predict_missing_tasks()
    app.run(debug=True)
