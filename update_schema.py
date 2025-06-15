from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///database.db", echo=True)

def update_schema():
    with engine.connect() as conn:
        # PRAGMA を使って task テーブルのカラム情報を取得
        result = conn.execute(text("PRAGMA table_info(task)"))
        # 各列の名前はタプルのインデックス 1 に格納されている
        columns = [row[1] for row in result]
        
        # assigned_for_today 列がない場合は追加
        if "assigned_for_today" not in columns:
            conn.execute(text("ALTER TABLE task ADD COLUMN assigned_for_today INTEGER DEFAULT 0"))
            print("assigned_for_today 列を追加しました。")
        else:
            print("assigned_for_today 列は既に存在します。")
        
        # assigned_date 列もチェックして追加
        if "assigned_date" not in columns:
            conn.execute(text("ALTER TABLE task ADD COLUMN assigned_date DATE"))
            print("assigned_date 列を追加しました。")
        else:
            print("assigned_date 列は既に存在します。")

if __name__ == "__main__":
    update_schema()
