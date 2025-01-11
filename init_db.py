import sqlite3
import os

def initialize_database():
    with sqlite3.connect("app.db") as conn:
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        
        # Create user_files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                upload_date DATETIME NOT NULL,
                extracted_text TEXT,
                FOREIGN KEY (username) REFERENCES users (username)
            );
        """)
    print("Database initialized successfully!")

if __name__ == "__main__":
    initialize_database()