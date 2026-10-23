from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from datetime import datetime
from . import Base

class PortalTransaction(Base):
    __tablename__ = "portal_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_type = Column(String, nullable=False, index=True)  # "subscriber" or "beneficiary"
    user_id = Column(Integer, nullable=False, index=True)
    transaction_type = Column(String, nullable=False)  # "RECEIVED" or "GIVEN"
    business_name = Column(String, nullable=False)
    counterparty_name = Column(String, nullable=False)
    counterparty_type = Column(String, nullable=True)  # "Subscriber", "Beneficiary", "Customer"
    amount = Column(Float, nullable=False, default=0.0)
    description = Column(String, nullable=True)
    transaction_date = Column(String, nullable=False)
    status = Column(String, default="Verified")  # "Verified", "Pending", "Completed"
    created_at = Column(DateTime, default=datetime.utcnow)


class PortalReferral(Base):
    __tablename__ = "portal_referrals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    referral_code = Column(String, unique=True, index=True, nullable=False)
    referrer_type = Column(String, nullable=False, index=True)  # "subscriber" or "beneficiary"
    referrer_id = Column(Integer, nullable=False, index=True)
    referrer_name = Column(String, nullable=False)
    partner_business_name = Column(String, nullable=False)
    partner_business_category = Column(String, nullable=True)
    client_name = Column(String, nullable=False)
    client_phone = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, default="Under Review")  # "Under Review", "Verified", "Transacted", "Rejected"
    reward_points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class RewardClaim(Base):
    __tablename__ = "reward_claims"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    claim_reference = Column(String, unique=True, index=True, nullable=False)
    user_type = Column(String, nullable=False, index=True)  # "subscriber" or "beneficiary"
    user_id = Column(Integer, nullable=False, index=True)
    user_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    points = Column(Integer, nullable=True, default=0)
    payout_method = Column(String, nullable=False)  # e.g. "UPI (name@upi)" or "Bank A/C" or "Voucher (Amazon)"
    status = Column(String, default="Pending")  # "Pending", "Approved", "Disbursed", "Rejected"
    reviewed_by = Column(String, nullable=True, default="Admin / Accounts")
    verification_notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RewardRecord(Base):
    __tablename__ = "reward_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_type = Column(String, nullable=False, index=True)  # "subscriber" or "beneficiary"
    user_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # "business_given", "induction", "bonus"
    business_name = Column(String, nullable=False)
    details = Column(String, nullable=True)
    business_date = Column(String, nullable=False)
    business_given_amount = Column(Float, default=0.0)
    subscriber_inductions = Column(Integer, default=0)
    beneficiary_inductions = Column(Integer, default=0)
    eligible_reward = Column(Float, default=0.0)
    claimed_reward = Column(Float, default=0.0)
    remaining_reward = Column(Float, default=0.0)
    claim_status = Column(String, default="No")  # "Yes", "Pending", "No", "Available"
    created_at = Column(DateTime, default=datetime.utcnow)


class PortalNotification(Base):
    __tablename__ = "portal_notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_type = Column(String, nullable=False, index=True)  # "subscriber" or "beneficiary"
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String, default="system")  # "business", "rewards", "referrals", "inductions", "system"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PortalJob(Base):
    __tablename__ = "portal_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subscriber_id = Column(Integer, nullable=True)
    business_name = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    job_type = Column(String, default="Full Time")  # "Full Time", "Part Time", "Immediate", "Internship"
    location = Column(String, nullable=False)
    salary_range = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    contact_phone = Column(String, nullable=True)
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)


class PortalJobApplication(Base):
    __tablename__ = "portal_job_applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, nullable=False, index=True)
    beneficiary_id = Column(Integer, nullable=False, index=True)
    beneficiary_name = Column(String, nullable=False)
    status = Column(String, default="Applied")  # "Applied", "Shortlisted", "Selected"
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriberOffer(Base):
    __tablename__ = "subscriber_offers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subscriber_id = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    discount_tag = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    valid_until = Column(String, nullable=True)
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriberProduct(Base):
    __tablename__ = "subscriber_products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subscriber_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    price = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriberSuccessStory(Base):
    __tablename__ = "subscriber_success_stories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subscriber_id = Column(Integer, nullable=False, index=True)
    client_name = Column(String, nullable=False)
    story = Column(Text, nullable=False)
    rating = Column(Integer, default=5)
    date = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriberUpdateRequest(Base):
    __tablename__ = "subscriber_update_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subscriber_id = Column(Integer, nullable=False, index=True)
    proposed_changes = Column(Text, nullable=False)  # JSON string of proposed fields
    status = Column(String, default="Pending Review")  # "Pending Review", "Approved", "Rejected"
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
