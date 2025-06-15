import os
import pandas as pd
import pickle
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine

# 絶対パスを使って database.db を指定（必要に応じて）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

# DBへ接続（エンジン作成）
engine = create_engine(DATABASE_URI)

# データ読み込み：task テーブルから time_spent に値があるレコードを取得
df = pd.read_sql(
    "SELECT subject, category, difficulty, due_date, created_at, time_spent FROM task WHERE time_spent IS NOT NULL",
    engine
)
if df.empty:
    print("❌ 学習に使えるデータが存在しません。task テーブルに time_spent があるデータを追加してください。")
    exit()

# 特徴量の追加
df['days_until_due'] = (pd.to_datetime(df['due_date']) - pd.to_datetime(df['created_at'])).dt.days
df['weekday'] = pd.to_datetime(df['created_at']).dt.weekday  # 月曜 = 0

# 説明変数（特徴量）と目的変数に分離
X_raw = df[['subject', 'category', 'difficulty', 'days_until_due', 'weekday']]
y = df['time_spent']

# カテゴリ変数のエンコード
encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
X_cat = encoder.fit_transform(X_raw[['subject', 'category']])
X_cat_df = pd.DataFrame(X_cat, columns=encoder.get_feature_names_out(['subject', 'category']))

# 数値特徴量とカテゴリエンコード結果の結合
X_final = pd.concat([X_raw.drop(columns=['subject', 'category']).reset_index(drop=True), X_cat_df], axis=1)

# 学習データとテストデータに分割（例として test_size=0.2, random_state=42）
X_train, X_test, y_train, y_test = train_test_split(X_final, y, test_size=0.2, random_state=42)

# モデル作成と学習（RandomForestRegressor を使用）
model = RandomForestRegressor()
model.fit(X_train, y_train)

# モデルやエンコーダ用の保存ディレクトリを作成（存在しなければ）
os.makedirs("model", exist_ok=True)

# 学習済みモデルの保存
with open("model/model.pkl", "wb") as f:
    pickle.dump(model, f)

# カテゴリ変数エンコーダの保存
with open("model/encoder.pkl", "wb") as f:
    pickle.dump(encoder, f)

print("✅ モデル学習完了")
