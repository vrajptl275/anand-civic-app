import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    print("Initiating Database Migration from SQLite to PostgreSQL...")

    # 1. Push application context to initialize PSQL schemas
    from app import app, db
    with app.app_context():
        db.create_all()
        print("Schema successfully pushed to PostgreSQL.")

    # 2. Connect to SQLite
    sqlite_path = 'instance/app.db'
    if not os.path.exists(sqlite_path):
        print(f"SQLite DB not found at {sqlite_path}. Nothing to migrate.")
        return

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sl_cursor = sqlite_conn.cursor()

    # 3. Connect to PostgreSQL
    pg_url = os.environ.get('DATABASE_URL')
    print(f"Connecting to PostgreSQL at {pg_url}")
    
    pg_conn = psycopg2.connect(pg_url)
    pg_cursor = pg_conn.cursor()
    
    # Clean slate on Postgres to avoid Foreign Key violations
    pg_cursor.execute("TRUNCATE TABLE notifications, complaints, users, departments RESTART IDENTITY CASCADE;")
    pg_conn.commit()

    # Tables to migrate safely in order of dependencies (plural)
    tables = ['departments', 'users', 'complaints', 'notifications']
    
    for table in tables:
        print(f"Migrating [{table}] table...")
        try:
            sl_cursor.execute(f"SELECT * FROM {table}")
            rows = sl_cursor.fetchall()
            
            if not rows:
                print(f"  > Table {table} is empty. Skipping.")
                continue

            columns = rows[0].keys()
            col_names = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            
            bool_cols = {'is_active', 'is_read', 'is_fake'}

            insert_query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
            for row in rows:
                new_row = list(row)
                # Cast SQLite integers to python booleans for Postgres
                for i, col in enumerate(columns):
                    if col in bool_cols:
                        new_row[i] = bool(new_row[i])
                        
                pg_cursor.execute(insert_query, tuple(new_row))
                
            print(f"  > Successfully migrated {len(rows)} records from {table}.")
            pg_conn.commit() # Commit each table successfully
        except Exception as e:
            pg_conn.rollback() # VERY important to purge transaction state
            print(f"  > Error on table {table}: {e}")

    # Update auto-increment sequences for PostgreSQL
    for table in tables:
        try:
            pg_cursor.execute(f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id)+1 FROM {table}), 1), false);")
        except Exception as e:
            pass # Some tables might not have standard sequence names

    pg_conn.commit()
    print("====================================")
    print("Migration operation fully completed.")
    print("====================================")
    
    sqlite_conn.close()
    pg_conn.close()

if __name__ == '__main__':
    migrate()
