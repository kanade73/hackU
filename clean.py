from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///database.db")

with engine.begin() as conn:
    delete_query = text("""
        DELETE FROM timetable
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM timetable
            GROUP BY weekday, period, subject
        )
    """)
    conn.execute(delete_query)

    # 削除後の確認用にデータを再度表示
    result = conn.execute(text("SELECT * FROM timetable"))
    for row in result:
        print(row)
