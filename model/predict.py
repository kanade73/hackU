# model/predict.py

import pandas as pd
import pickle
from datetime import datetime
from sqlalchemy import create_engine

# モデルとエンコーダの読み込み
with open("model/model.pkl", "rb") as f:
    model = pickle.load(f)

with open("model/encoder.pkl", "rb") as f:
    encoder = pickle.load(f)

# DB接続
engine = create_engine('sqlite:///database.db')


def batch_predict_missing_tasks():
    """
    DB内の predicted_time が NULL のタスクに対して予測を実行し、データベースを更新する。
    Flaskアプリ起動時に一度だけ実行される。
    """
    df_new = pd.read_sql("""
        SELECT id, subject, category, difficulty, due_date, created_at
        FROM task
        WHERE time_spent IS NULL AND predicted_time IS NULL
    """, engine)

    if df_new.empty:
        print("新しい予測対象のタスクはありません")
        return

    # 特徴量の追加
    df_new['days_until_due'] = (
        pd.to_datetime(df_new['due_date']) - pd.to_datetime(df_new['created_at'])
    ).dt.days
    df_new['weekday'] = pd.to_datetime(df_new['created_at']).dt.weekday

    # 説明変数の前処理
    X_raw = df_new[['subject', 'category', 'difficulty', 'days_until_due', 'weekday']]
    X_cat = encoder.transform(X_raw[['subject', 'category']])
    X_cat_df = pd.DataFrame(X_cat, columns=encoder.get_feature_names_out(['subject', 'category']))
    X_final = pd.concat(
        [X_raw.drop(columns=['subject', 'category']).reset_index(drop=True), X_cat_df],
        axis=1
    )

    # 予測
    predicted_times = model.predict(X_final)
    df_new['predicted_time'] = predicted_times

    # DBに保存
    with engine.begin() as conn:
        for _, row in df_new.iterrows():
            conn.execute(
                "UPDATE task SET predicted_time = ? WHERE id = ?",
                (float(row['predicted_time']), int(row['id']))
            )

    print("✅ 起動時に予測が完了し、データベースに保存されました！")


def predict_single_task(subject, category, difficulty, due_date, created_at):
    """
    単一タスクの所要時間を予測する関数。
    新しいタスクを追加するときに使用。
    """
    days_until_due = (pd.to_datetime(due_date) - pd.to_datetime(created_at)).days
    weekday = pd.to_datetime(created_at).weekday()

    X_raw = pd.DataFrame([{
        'subject': subject,
        'category': category,
        'difficulty': difficulty,
        'days_until_due': days_until_due,
        'weekday': weekday
    }])

    X_cat = encoder.transform(X_raw[['subject', 'category']])
    X_cat_df = pd.DataFrame(X_cat, columns=encoder.get_feature_names_out(['subject', 'category']))
    X_final = pd.concat(
        [X_raw.drop(columns=['subject', 'category']).reset_index(drop=True), X_cat_df],
        axis=1
    )

    predicted_time = model.predict(X_final)[0]
    return predicted_time