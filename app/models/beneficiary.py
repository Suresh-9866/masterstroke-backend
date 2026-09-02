from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from . import Base

class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    beneficiary_name = Column(String, nullable=False, index=True)
    status = Column(String, default="Active")
    whatsapp_number = Column(String, nullable=True)
    location = Column(String, nullable=True)
    total_business_given = Column(Float, default=0.0)
    s_member_induction = Column(String, default="Pending")
    b_member_induction = Column(String, default="Pending")
    total_rewards_gained = Column(Integer, default=0)
    benefit_claim_status = Column(String, default="Not Claimed")
    email = Column(String, nullable=True)
    subscriber_name = Column(String, nullable=True)
    subscriber_id = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    jobs_taken = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
