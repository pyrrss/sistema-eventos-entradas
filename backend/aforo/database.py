from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

URL_BASEDATOS = "postgresql+psycopg2://aforo:aforo_dev@db_aforo:5432/db_aforo"

engine = create_engine(URL_BASEDATOS)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()