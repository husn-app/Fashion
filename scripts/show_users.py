from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the absolute path to the sqlite.db file in the root directory
db_path = os.path.join(script_dir, '../sqllite.db')

# Create an engine for the SQLite database
engine = create_engine(f'sqlite:///{db_path}')

# Reflect the database schema
metadata = MetaData()
metadata.reflect(bind=engine)

# Assuming you have a table named 'user'
user_table = metadata.tables['user']

# Start a session
Session = sessionmaker(bind=engine)
session = Session()

# Query all rows from the user table
with engine.connect() as connection:
    result = connection.execute(user_table.select())
    for row in result:
        print(row)
