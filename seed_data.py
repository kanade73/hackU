import os
import pandas as pd
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, inspect
from train_model import retrain_model  # train_model.py に retrain_model がある前提

# DBの接続設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URI)

# is_deleted カラムが無いときだけ追加
inspector = inspect(engine)
if 'is_deleted' not in [col['name'] for col in inspector.get_columns('task')]:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE task ADD COLUMN is_deleted INTEGER DEFAULT 0"))
        print("✅ is_deleted カラムを追加しました")
else:
    print("ℹ️ is_deleted カラムはすでに存在しています。")

# 教科・カテゴリの候補
subjects = ["キャリア教育基礎", "選択独語第一", "微分積分学第一", "Academic Spoken English"]
categories = ["小テスト", "レポート", "復習", "予習", "課題", "グループワーク"]
difficulty_range = [1, 2, 3, 4, 5]

# データ生成関数（すべて is_deleted = 1）
def generate_task_data(subject, n=60):
    now = datetime.now()
    rows = []
    for _ in range(n):
        category = random.choice(categories)
        difficulty = random.choice(difficulty_range)
        created_at = now - timedelta(days=random.randint(5, 20))
        due_date = created_at + timedelta(days=random.randint(1, 14))
        time_spent = round(random.uniform(5, 70), 1)  # 分単位
        rows.append({
            "subject": subject,
            "category": category,
            "difficulty": difficulty,
            "due_date": due_date.strftime("%Y-%m-%d %H:%M:%S"),
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "time_spent": time_spent,
            "is_deleted": 1
        })
    return rows

# 全教科のデータを生成
all_tasks = []
for subject in subjects:
    all_tasks.extend(generate_task_data(subject, n=60))

df = pd.DataFrame(all_tasks)

# DBに追加（全件 is_deleted=1 のダミーデータ）
with engine.begin() as conn:
    df.to_sql("task", con=conn, if_exists="append", index=False)

print(f"✅ {len(df)} 件の学習用ダミーデータを task テーブルに追加しました（is_deleted=1）")

# モデル再学習
retrain_model()
