# reset_db.py
from sqlalchemy import create_engine, text
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URI, echo=True)

def reset_data():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM task"))
        conn.execute(text("DELETE FROM timetable"))
        print("Database reset completed.")

if __name__ == "__main__":
    reset_data()
