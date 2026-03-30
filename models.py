from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, nullable=True)

    vehicles = relationship("Vehicle", back_populates="owner")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="vehicles")
    reports = relationship("Report", back_populates="vehicle")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    plate = Column(String, nullable=False)
    issue = Column(String, nullable=False)
    note = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)

    vehicle = relationship("Vehicle", back_populates="reports")
