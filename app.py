import os
from flask import Flask, request, render_template, redirect, url_for
from sqlalchemy import create_engine, text
from datetime import datetime, date
from model.predict import predict_single_task, batch_predict_missing_tasks
import pandas as pd
import pickle
from train_model import retrain_model


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

        # 今日使える時間の85%（分単位）
        available = conn.execute(text("""
            SELECT available_hours FROM available_time WHERE weekday = :wd
        """), {"wd": weekday}).scalar() or 0
        limit_minutes = int(available * 60 * 0.85)

        # 未完了タスク（予測時間あり）を締切昇順で取得
        candidates = conn.execute(text("""
            SELECT id, predicted_time FROM task
            WHERE time_spent IS NULL AND predicted_time IS NOT NULL AND is_deleted = 0
            ORDER BY due_date ASC, predicted_time ASC
        """)).fetchall()

        total = 0.0  # 分単位で累積
        for task in candidates:
            if task.predicted_time is None:
                continue

            try:
                predicted_minutes = float(task.predicted_time) * 60  # ← 🔧 時間 → 分に変換
            except (ValueError, TypeError):
                continue

            if total + predicted_minutes <= limit_minutes:
                conn.execute(text("""
                    UPDATE task
                    SET assigned_for_today = 1, assigned_date = :today
                    WHERE id = :id
                """), {"id": task.id, "today": today_str})
                total += predicted_minutes
            else:
                break

    print(f"[DEBUG] today={today_str}, weekday={weekday}, limit_minutes={limit_minutes}")
    print(f"[DEBUG] task候補数={len(candidates)}")

    for task in candidates:
        print(f"[DEBUG] タスクID {task.id} → predicted_minutes = {predicted_minutes}")


@app.before_request
def before_request():
    # setup や timetable ページからのアクセスはタスク自動生成をスキップする
    if request.endpoint not in ("setup", "edit_timetable", "static"):
        maybe_generate_today_tasks()

@app.route("/")
def index():
    from model.predict import batch_predict_missing_tasks
    batch_predict_missing_tasks()

    def format_time(minutes_float):
        if minutes_float is None:
            return "-"
        try:
            total_minutes = int(round(float(minutes_float)))
            if total_minutes == 0 and float(minutes_float) > 0:
                total_minutes = 1  # 小数点切り捨てによるゼロ回避
            h, m = divmod(total_minutes, 60)
            return f"{h}時間{m}分" if h else f"{m}分"
        except Exception as e:
            print(e)
            return "-"


    with engine.begin() as conn:
        # 曜日の変換
        today_weekday_name = datetime.now().strftime("%A")
        today_weekday = weekday_mapping[today_weekday_name]

        # tasks_today の取得と辞書への変換
        tasks_today_result = conn.execute(text("""
            SELECT * FROM task
            WHERE assigned_for_today = 1 AND is_completed = 0 AND is_deleted = 0
            ORDER BY due_date
        """)).mappings().all()
        tasks_today = [dict(row) for row in tasks_today_result]


        tasks_remaining = conn.execute(text("""
            SELECT * FROM task
            WHERE assigned_for_today = 0 AND is_completed = 0 AND is_deleted = 0
            ORDER BY due_date
        """)).mappings().all()
        tasks_remaining = [dict(now) for now in tasks_remaining]


        # timetable の取得と辞書への変換
        timetable_result = conn.execute(text("""
            SELECT * FROM timetable
            WHERE weekday = :weekday
            ORDER BY period
        """), {"weekday": today_weekday}).mappings().all()
        timetable = [dict(row) for row in timetable_result]

        # 完了タスクの ID を取得（チェックボックス表示用）
        completed_task_ids = conn.execute(text("""
            SELECT id FROM task WHERE is_completed = 1
        """)).mappings().all()
        completed_tasks = {str(row.id) for row in completed_task_ids}

        # 各タスクの予想時間表示を追加
        for task in tasks_today:
            task["predicted_time_display"] = format_time(task["predicted_time"])
        for task in tasks_remaining:
            task["predicted_time_display"] = format_time(task["predicted_time"])

    return render_template("index.html",
                           tasks_today=tasks_today,
                           tasks_remaining=tasks_remaining,
                           timetable=timetable,
                           completed_tasks=completed_tasks)




from sqlalchemy import text

from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import create_engine, text


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        # フォームから available_time の取得
        available_time_entries = []
        for i in range(7):  # 月〜日：0〜6
            hours = request.form.get(f"available_{i}", 0)
            try:
                available_hours = float(hours)
            except ValueError:
                available_hours = 0
            available_time_entries.append({
                "weekday": i,
                "available_hours": available_hours
            })

        # フォームから timetable の取得（1〜5限、月〜土：0〜5）
        timetable_entries = []
        for day_index in range(6):  # 月〜土
            for period in range(1, 6):  # 1〜5限
                key = f"timetable_{day_index}_{period}"
                subject = request.form.get(key, "").strip()
                if subject:
                    timetable_entries.append({
                        "weekday": day_index,
                        "period": period,
                        "subject": subject
                    })

        with engine.begin() as conn:
            # 1. available_time を保存（上書き）
            conn.execute(text("DELETE FROM available_time"))
            for entry in available_time_entries:
                conn.execute(text("""
                    INSERT INTO available_time (weekday, available_hours)
                    VALUES (:weekday, :available_hours)
                """), entry)

            # 2. timetable を保存（上書き）
            conn.execute(text("DELETE FROM timetable"))
            for entry in timetable_entries:
                conn.execute(text("""
                    INSERT INTO timetable (weekday, period, subject)
                    VALUES (:weekday, :period, :subject)
                """), entry)

            # 3. 今日のタスク割当をリセット（assigned_for_todayフラグをクリア）
            conn.execute(text("""
                UPDATE task
                SET assigned_for_today = 0, assigned_date = NULL
                WHERE assigned_for_today = 1
            """))

        # 4. 今日のやることリストを再選定（available_timeの60%で）
        maybe_generate_today_tasks()

        return redirect(url_for("index"))

    # GET時のフォーム描画
    return render_template("setup.html")





@app.route("/start_task/<int:task_id>")
def start_task(task_id):
    with engine.begin() as conn:
        task = conn.execute(text("SELECT id FROM task WHERE id = :id"), {"id": task_id}).fetchone()
        if not task:
            return "タスクが見つかりません", 404
    return render_template("start_task.html", task_id=task_id)

@app.route("/finish_task/<int:task_id>", methods=["POST"])
def finish_task(task_id):
    try:
        time_spent = float(request.form["time_spent"])
    except (ValueError, KeyError):
        return "Invalid input", 400

    with engine.begin() as conn:
        stmt = text("""
            UPDATE task
            SET time_spent = :time_spent,
                is_completed = 1
            WHERE id = :task_id
        """)
        conn.execute(stmt, {"time_spent": time_spent, "task_id": task_id})

    return redirect(url_for("index"))


@app.route("/add_task", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        subject = request.form["subject"]
        category = request.form["category"]
        difficulty = int(request.form["difficulty"])
        due_date = request.form["due_date"]

        predicted_time = predict_single_task(subject, category, difficulty, due_date, datetime.now())

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO task (subject, category, difficulty, due_date, created_at, predicted_time)
                VALUES (:subject, :category, :difficulty, :due_date, :created_at, :predicted_time)
            """), {
                "subject": subject,
                "category": category,
                "difficulty": difficulty,
                "due_date": due_date,
                "created_at": datetime.now(),
                "predicted_time": predicted_time
            })
        return redirect(url_for("index"))

    # GET: 時間割表示
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    timetable_grid = [["" for _ in range(6)] for _ in range(5)]  # period (行) × weekday (列)

    with engine.begin() as conn:
        results = conn.execute(text("""
            SELECT weekday, period, subject FROM timetable
            WHERE weekday IN (0, 1, 2, 3, 4, 5)
            ORDER BY weekday, period
        """)).mappings().all()

    for row in results:
        weekday = row["weekday"]
        period = row["period"]
        subject = row["subject"]

        if 1 <= period <= 5 and 0 <= weekday <= 5:
            timetable_grid[period - 1][weekday] = subject

    return render_template("add_task.html", timetable_grid=timetable_grid)


@app.route("/start_selected_task", methods=["GET"])
def start_selected_task():
    # 「今日やること」から選ばれたタスク
    task_id = request.args.get("selected_task_id")
    
    # 「今残っているやることリスト」から選ばれたタスク（今日やることより優先度は低い）
    if not task_id:
        task_id = request.args.get("selected_remaining_task_id")

    if task_id:
        return redirect(url_for("start_task", task_id=task_id))
    else:
        return redirect(url_for("index"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    # 英語の曜日リストとそのマッピング
    eng_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    eng_to_int = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6
    }

    if request.method == "POST":
        # --- ① 利用可能時間の更新 ---
        available_times = {}
        for index, day in enumerate(eng_days):
            value = request.form.get(f"available_{index}", "")
            try:
                available_times[day] = float(value)
            except ValueError:
                available_times[day] = 0.0
            print(f"[DEBUG] Available time for {day}: {available_times[day]}")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM available_time"))
            for day, hours in available_times.items():
                conn.execute(
                    text("""
                        INSERT INTO available_time (weekday, available_hours)
                        VALUES (:weekday, :hours)
                    """),
                    {"weekday": eng_to_int[day], "hours": hours}
                )

        # --- ② 時間割 (timetable) の更新：全件削除して再作成 ---
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM timetable"))
            for day in eng_days:
                for period in range(1, 6):
                    field_name = f"timetable_{day}_{period}"
                    subject = request.form.get(field_name, "").strip()
                    print(f"[DEBUG] Field '{field_name}': '{subject}'")
                    if subject:
                        conn.execute(
                            text("""
                                INSERT INTO timetable (weekday, period, subject)
                                VALUES (:weekday, :period, :subject)
                            """),
                            {"weekday": eng_to_int[day], "period": period, "subject": subject}
                        )
            rows = conn.execute(text("SELECT weekday, period, subject FROM timetable")).fetchall()
            if rows:
                print("[DEBUG] Registered timetable records:")
                for row in rows:
                    print(f"  {eng_days[row.weekday]} {row.period} period: {row.subject}")
            else:
                print("[DEBUG] Timetable table is empty after INSERTs!")

        # --- ③ タスクリスト生成アルゴリズムの再実行 ---
        maybe_generate_today_tasks()

        # ★ キャッシュクリアのためにエンジンのコネクションプールをクリア ★
        engine.dispose()
        # または、エンジン作成時に expire_on_commit=True を設定する方法も検討してください。

        return redirect(url_for("index"))

    # GET 時の処理
    with engine.begin() as conn:
        available_times = {}
        rows = conn.execute(text("SELECT weekday, available_hours FROM available_time")).fetchall()
        for row in rows:
            available_times[eng_days[row.weekday]] = row.available_hours

        timetable_entries = {}
        rows = conn.execute(text("SELECT weekday, period, subject FROM timetable")).fetchall()
        for row in rows:
            timetable_entries[(row.weekday, row.period)] = row.subject

    timetable_grid = []
    for day_idx in range(len(eng_days)):
        day_row = []
        for period in range(1, 7):
            day_row.append(timetable_entries.get((day_idx, period), ""))
        timetable_grid.append(day_row)

    return render_template("setup.html",
                           available_times=available_times,
                           timetable_grid=timetable_grid,
                           eng_days=eng_days)

from flask import request, jsonify
# app.py
@app.route("/delete_task", methods=["POST"])
def delete_task():
    data = request.get_json()
    if not data or "id" not in data:
        return jsonify({"error": "タスクIDが指定されていません"}), 400

    task_id = data["id"]

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE task SET is_deleted = 1 WHERE id = :id
            """), {"id": task_id})
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/timetable", methods=["GET", "POST"])
def edit_timetable():
    # 今回は Monday～Saturday のみ対象とする
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    
    if request.method == "POST":
        timetable_entries = []
        # 各曜日の時間割を更新（フォームのフィールド名は "Monday_1", ... "Saturday_5" となる前提）
        for day in days:
            for period in range(1, 6):  # 5限まで
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

    # timetable_dict のキーを Monday～Saturday、各曜日は5つの期間で初期化
    timetable_dict = {day: [""] * 5 for day in days}
    # 反転マッピング：対象曜日のみ（月～Saturday）を対象とする
    reverse_weekday_mapping = {v: k for k, v in weekday_mapping.items() if k in days}
    for row in result:
        # row.weekday は整数（例: 0 = Monday, ..., 5 = Saturday）と想定
        day_name = reverse_weekday_mapping.get(row.weekday, "Unknown")
        if day_name != "Unknown" and 1 <= row.period <= 5:
            timetable_dict[day_name][row.period - 1] = row.subject

    return render_template("edit_timetable.html", timetable=timetable_dict, days=days)


@app.route("/partial_finish_task/<int:task_id>", methods=["POST"])
def partial_finish_task(task_id):
    try:
        progress_percent = int(request.form["progress"])
        time_spent = float(request.form["time_spent"])
        assert 0 <= progress_percent <= 100
    except (ValueError, KeyError, AssertionError):
        return "Invalid input", 400

    with engine.begin() as conn:
        task = conn.execute(text("SELECT predicted_time FROM task WHERE id = :id"), {"id": task_id}).fetchone()
        if not task:
            return "Task not found", 404

        original_time = float(task.predicted_time) if task.predicted_time is not None else 0

        # 進捗に応じた残り時間を計算。最低10分は残す
        remaining_time = max(original_time * (1 - progress_percent / 100), 10)

        if progress_percent < 100:
            # 途中終了時は predicted_time を減らすだけ
            conn.execute(text("""
                UPDATE task
                SET predicted_time = :remaining_time
                WHERE id = :id
            """), {"remaining_time": remaining_time, "id": task_id})
        else:
            # 完了時は time_spent 更新＆完了フラグも立てる
            conn.execute(text("""
                UPDATE task
                SET predicted_time = :remaining_time,
                    time_spent = :time_spent,
                    is_completed = 1
                WHERE id = :id
            """), {"remaining_time": remaining_time, "time_spent": time_spent, "id": task_id})

    return redirect(url_for("index"))





if __name__ == "__main__":
    # 重複しないよう、必要に応じてバッチ処理を呼び出してください
    batch_predict_missing_tasks()
    app.run(debug=True)
