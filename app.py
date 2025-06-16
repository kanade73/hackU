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

        # 今日使える時間の60%（分単位）
        available = conn.execute(text("""
            SELECT available_hours FROM available_time WHERE weekday = :wd
        """), {"wd": weekday}).scalar() or 0
        limit_minutes = int(available * 60 * 0.6)

        # 未完了タスク（予測時間あり）を締切昇順で取得
        candidates = conn.execute(text("""
            SELECT id, predicted_time FROM task
            WHERE time_spent IS NULL AND predicted_time IS NOT NULL
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
        stmt = text("UPDATE task SET time_spent = :time_spent WHERE id = :task_id")
        conn.execute(stmt, {"time_spent": time_spent, "task_id": task_id})
    return redirect(url_for("index"))

@app.route("/add_task", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        # タスク追加処理（POST 時）
        subject = request.form["subject"]
        category = request.form["category"]
        difficulty = int(request.form["difficulty"])
        due_date = request.form["due_date"]

        # タスク予測などの処理（例）
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
    
    # GET 時: 月～金の時間割情報を5×5グリッドとして取得する
    # 対象曜日（英語）は "Monday"～"Friday"。weekday_mapping の定義例：
    # weekday_mapping = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, ...}
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    # DBから対象曜日（数値：0～4）の時間割情報を全件取得（全曜日の情報を横断して取得）
    with engine.begin() as conn:
        results = conn.execute(text("""
            SELECT * FROM timetable
            WHERE weekday IN (0, 1, 2, 3, 4)
            ORDER BY weekday, period
        """)).fetchall()
    
    # timetable_grid: 5行（各行は period 1～5） × 5列（各列は Monday～Friday）の2次元リストを初期化
    timetable_grid = [["" for _ in range(5)] for _ in range(5)]
    
    # 結果から timetable_grid を埋める
    # ※ DBの各レコードには、row.weekday (0～4) と row.period (1～?) があると仮定
    for row in results:
        # 対象は period 1～5 とする
        if 1 <= row.period <= 5 and 0 <= row.weekday < 5:
            timetable_grid[row.period - 1][row.weekday] = row.subject

    # timetable_grid という変数名でテンプレートに渡す
    return render_template("add_task.html", timetable_grid=timetable_grid)



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
        # 「いったん終了」時のフォームから送信される time_spent はあくまで現時点の目安として使用するが、
        # タスク完了状態にはしないため、進捗が100%でない場合は DB の time_spent は更新しません。
        time_spent = float(request.form["time_spent"])
        assert 0 <= progress_percent <= 100
    except (ValueError, KeyError, AssertionError):
        return "Invalid input", 400

    with engine.begin() as conn:
        task = conn.execute(text("SELECT predicted_time FROM task WHERE id = :id"), {"id": task_id}).fetchone()
        if task and task.predicted_time is not None:
            original_time = float(task.predicted_time)
            # 進捗に応じた残り時間を計算。最低10分は残す
            remaining_time = max(original_time * (1 - progress_percent / 100), 10)
            
            if progress_percent < 100:
                # 進捗更新の場合：time_spentはそのままで、predicted_time（残り作業時間）のみ更新
                conn.execute(text("""
                    UPDATE task
                    SET predicted_time = :remaining_time
                    WHERE id = :id
                """), {
                    "remaining_time": remaining_time,
                    "id": task_id
                })
            else:
                # 100%の場合は、タスク完了とみなして time_spent などを更新し、完了フラグを立てる（必要なら is_completed も更新）
                conn.execute(text("""
                    UPDATE task
                    SET predicted_time = :remaining_time,
                        time_spent = :time_spent,
                        is_completed = 1
                    WHERE id = :id
                """), {
                    "remaining_time": remaining_time,
                    "time_spent": time_spent,
                    "id": task_id
                })

    return redirect(url_for("index"))




if __name__ == "__main__":
    # 重複しないよう、必要に応じてバッチ処理を呼び出してください
    batch_predict_missing_tasks()
    app.run(debug=True)
