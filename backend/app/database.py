import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_URL = URL.create(
    "postgresql+psycopg",
    username=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host="localhost",
    port=5432,
    database=os.getenv("POSTGRES_DB"),
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
