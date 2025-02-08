from database import create_tables, engine
from sqlalchemy_utils import database_exists, create_database

def init_database():
    # Create database if it doesn't exist
    if not database_exists(engine.url):
        create_database(engine.url)
        print(f"Database created at {engine.url}")
    
    # Create tables
    create_tables()
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_database()
