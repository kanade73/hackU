from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///database.db")

with engine.begin() as conn:
    result = conn.execute(text("SELECT * FROM timetable"))
    for row in result:
        print(row)
