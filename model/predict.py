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
        print("🟡 新しい予測対象のタスクはありません")
        return

    # 日付の変換と前処理
    df_new['due_date'] = pd.to_datetime(df_new['due_date'], errors='coerce')
    df_new['created_at'] = pd.to_datetime(df_new['created_at'], errors='coerce')
    df_new = df_new.dropna(subset=['due_date', 'created_at'])

    if df_new.empty:
        print("❌ 有効な日付データがないため、予測できません")
        return

    # 特徴量の作成
    df_new['days_until_due'] = (df_new['due_date'] - df_new['created_at']).dt.days
    df_new['weekday'] = df_new['created_at'].dt.weekday

    # 説明変数の整備
    X_raw = df_new[['subject', 'category', 'difficulty', 'days_until_due', 'weekday']]

    # カテゴリ変数をエンコード
    try:
        X_cat = encoder.transform(X_raw[['subject', 'category']])
        X_cat_df = pd.DataFrame(X_cat, columns=encoder.get_feature_names_out(['subject', 'category']))
    except Exception as e:
        print(f"❌ カテゴリ変数のエンコードに失敗しました: {e}")
        return

    # 数値データと連結
    X_final = pd.concat([X_raw.drop(columns=['subject', 'category']).reset_index(drop=True), X_cat_df], axis=1)

    # 予測
    try:
        predicted_times = model.predict(X_final)
    except Exception as e:
        print(f"❌ モデル予測に失敗しました: {e}")
        return

    df_new['predicted_time'] = predicted_times

    # DBに保存
    with engine.begin() as conn:
        for _, row in df_new.iterrows():
            conn.execute(
                text("UPDATE task SET predicted_time = :predicted_time WHERE id = :id"),
            {"predicted_time": float(row['predicted_time']), "id": int(row['id'])}
        )

    print(f"✅ 起動時に {len(df_new)} 件のタスクの予測が完了し、データベースに保存されました")


def predict_single_task(subject, category, difficulty, due_date, created_at):
    """
    単一タスクの所要時間を予測する関数。
    新しいタスクを追加するときに使用。
    """
    try:
        due_date_parsed = pd.to_datetime(due_date, errors='coerce')
        created_at_parsed = pd.to_datetime(created_at, errors='coerce')

        if pd.isnull(due_date_parsed) or pd.isnull(created_at_parsed):
            print("❌ 日付が不正なため、予測できません")
            return 0.0

        days_until_due = (due_date_parsed - created_at_parsed).days
        weekday = created_at_parsed.weekday()

        X_raw = pd.DataFrame([{
            'subject': subject,
            'category': category,
            'difficulty': difficulty,
            'days_until_due': days_until_due,
            'weekday': weekday
        }])

        try:
            X_cat = encoder.transform(X_raw[['subject', 'category']])
            X_cat_df = pd.DataFrame(X_cat, columns=encoder.get_feature_names_out(['subject', 'category']))
        except Exception as e:
            print(f"❌ 単一タスクのエンコードに失敗: {e}")
            return 0.0

        X_final = pd.concat(
            [X_raw.drop(columns=['subject', 'category']).reset_index(drop=True), X_cat_df],
            axis=1
        )

        predicted_time = model.predict(X_final)[0]

        # 極端に小さい値（例: 0.0分）は最低1分に丸める（任意）
        return round(max(float(predicted_time), 1.0), 1)

    except Exception as e:
        print(f"❌ 単一タスクの予測中にエラーが発生しました: {e}")
        return 0.0
