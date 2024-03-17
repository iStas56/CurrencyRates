from database import Base
from sqlalchemy import Column, Integer, String, DateTime, Float


class Rates(Base):
    __tablename__ = 'rates'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, nullable=False)
    title = Column(String, nullable=False)
    rate = Column(Float, nullable=False)
    created_at = Column(DateTime)


class Currency(Base):
    __tablename__ = 'currency'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, nullable=False)
    title = Column(String, nullable=False)
