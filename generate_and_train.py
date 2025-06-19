import os
import pandas as pd
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from train_model import retrain_model  # train_model.py に retrain_model がある前提

# DBの接続設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URI)

from sqlalchemy import text
from sqlalchemy import create_engine, text, inspect

engine = create_engine("sqlite:///database.db")
inspector = inspect(engine)

# is_deleted カラムが無いときだけ追加
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

# データ生成
def generate_task_data(subject, n=30):
    now = datetime.now()
    rows = []
    for _ in range(n):
        category = random.choice(categories)
        difficulty = random.choice(difficulty_range)
        created_at = now - timedelta(days=random.randint(5, 20))
        due_date = created_at + timedelta(days=random.randint(1, 14))
        time_spent = round(random.uniform(30, 180), 1)  # 分単位
        rows.append({
            "subject": subject,
            "category": category,
            "difficulty": difficulty,
            "due_date": due_date.strftime("%Y-%m-%d %H:%M:%S"),
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "time_spent": time_spent
        })
    return rows

# すべての教科のデータを生成して DataFrame 化
all_tasks = []
for subject in subjects:
    all_tasks.extend(generate_task_data(subject, n=60))

df = pd.DataFrame(all_tasks)
df["is_deleted"] = 1  # 学習用なので表示対象外にする


# DBに追加
with engine.begin() as conn:
    df.to_sql("task", con=conn, if_exists="append", index=False)

print(f"✅ {len(df)} 件のデータを task テーブルに追加しました")

# モデルを再学習
retrain_model()
