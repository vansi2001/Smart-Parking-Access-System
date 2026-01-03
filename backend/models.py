import datetime
from sqlalchemy import Column, Integer, String, DateTime
from database import Base


class ParkingRecord(Base):
    __tablename__ = 'parking_records'

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(Integer, index=True)  # 1 = check-in, 0 = check-out
    filename = Column(String, nullable=False)
    size = Column(Integer, nullable=True)
