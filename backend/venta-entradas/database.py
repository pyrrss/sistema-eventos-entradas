from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

URL_BASEDATOS = "postgresql://ventas:ventas_dev@db_ventas:5432/db_ventas"

engine = create_engine(URL_BASEDATOS)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()