import sqlite3
import os

DB_NAME = "app.db"

def initialize_database():
    """Creates the database and users table."""
    if not os.path.exists(DB_NAME):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );
            """)
            print("Database and 'users' table created successfully!")
    else:
        print("Database already exists.")

if __name__ == "__main__":
    initialize_database()
