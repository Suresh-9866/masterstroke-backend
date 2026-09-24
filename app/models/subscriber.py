from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
from . import Base

class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    business_name = Column(String, nullable=False, index=True)
    business_category = Column(String, nullable=False, index=True)
    owner_name = Column(String, nullable=False)
    total_business_taken = Column(Float, default=0.0)
    total_business_given = Column(Float, default=0.0)
    business_count = Column(Integer, default=0)
    leads = Column(Integer, default=0)
    s_member_induction = Column(String, default="Pending")
    b_member_induction = Column(String, default="Pending")
    total_rewards_gained = Column(Integer, default=0)
    benefit_claim_status = Column(String, default="Not Claimed")
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    location = Column(String, nullable=True)
    joined_date = Column(String, nullable=True)
    business_sub_category = Column(String, nullable=True)
    established_year = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    address = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    gst_number = Column(String, nullable=True)
    about_business = Column(String, nullable=True)
    target_customers = Column(String, nullable=True)
    enrollment_duration = Column(String, nullable=True)
    renewal_date = Column(String, nullable=True)
    referrer_type = Column(String, nullable=True)
    referrer_name = Column(String, nullable=True)
    referrer_phone = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    ad_image = Column(String, nullable=True)
    ad_description = Column(String, nullable=True)
    ad_start_date = Column(String, nullable=True)
    ad_end_date = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

