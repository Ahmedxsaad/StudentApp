# models.py

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, ForeignKey, Text,
    DateTime, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    """
    Represents an application user and associated auth/info fields.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="student")
    verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_token_expires_at = Column(DateTime, nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)
    national_id = Column(String, unique=True, nullable=True)
    subscribed_to_notifications = Column(Boolean, default=True)
    unsubscribe_token = Column(String, nullable=True)
    auth_token = Column(String, nullable=True)
    profile_pic_url = Column(String, nullable=True)
    time_spent_seconds = Column(Float, default=0.0)
    auth_token_expires_at = Column(DateTime, nullable=True)
    verification_failures = Column(Integer, default=0)
    verification_cooldown_step = Column(Integer, default=0)
    verification_locked_until = Column(DateTime, nullable=True)
    refresh_token_hash = Column(String, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)

    reclamations = relationship("Reclamation", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Student(Base):
    """
    Represents a student entity with academic info and relationships.
    """
    __tablename__ = "students"

    id = Column(String, primary_key=True)
    prenom = Column(String, nullable=False)
    nom = Column(String, nullable=False)
    moy_an_year1 = Column(Float, nullable=True)
    section = Column(String, nullable=True)
    display_id = Column(String, nullable=True)
    bonus = Column(Float, default=0.0)
    ai_report = Column(Text, nullable=True)
    year1_rank = Column(Integer, nullable=True)

    grades_s1 = relationship("GradeSemester1", back_populates="student")
    grades_s2 = relationship("GradeSemester2", back_populates="student")


class Matiere(Base):
    """
    Represents a course/subject with weights and overall coefficient.
    """
    __tablename__ = "matieres"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    semester = Column(Integer, nullable=False)
    has_tp = Column(Boolean, default=False)
    weights_ds = Column(Float, nullable=False)
    weights_tp = Column(Float, nullable=True)
    weights_exam = Column(Float, nullable=False)
    overall_weight = Column(Float, nullable=False)
    section = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "section", "semester", name="_unique_matiere_name_section_semester"),
    )

    grades_s1 = relationship("GradeSemester1", back_populates="matiere")
    grades_s2 = relationship("GradeSemester2", back_populates="matiere")


class GradeSemester1(Base):
    """
    Grades for semester 1, linked to a student and a Matiere.
    """
    __tablename__ = "grades_s1"

    id = Column(Integer, primary_key=True)
    student_id = Column(String, ForeignKey("students.id"))
    matiere_id = Column(Integer, ForeignKey("matieres.id"))
    ds = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    exam = Column(Float, nullable=True)
    final = Column(Float, nullable=True)

    student = relationship("Student", back_populates="grades_s1")
    matiere = relationship("Matiere", back_populates="grades_s1")


class GradeSemester2(Base):
    """
    Grades for semester 2, linked to a student and a Matiere.
    """
    __tablename__ = "grades_s2"

    id = Column(Integer, primary_key=True)
    student_id = Column(String, ForeignKey("students.id"))
    matiere_id = Column(Integer, ForeignKey("matieres.id"))
    ds = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    exam = Column(Float, nullable=True)
    final = Column(Float, nullable=True)

    student = relationship("Student", back_populates="grades_s2")
    matiere = relationship("Matiere", back_populates="grades_s2")


class Reclamation(Base):
    """
    Reclamations submitted by a user for various issues.
    """
    __tablename__ = "reclamations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    reclamation_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_solved = Column(Boolean, default=False)

    user = relationship("User", back_populates="reclamations")


class Notification(Base):
    """
    Notifications sent to a user about updates or announcements.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="notifications")


class Advertisement(Base):
    """
    Advertisement entries with optional rank-based targeting.
    """
    __tablename__ = "advertisements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_url = Column(String, nullable=False)
    target_link = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)
    click_count = Column(Integer, default=0)
    min_rank_percent = Column(Integer, nullable=True)
    max_rank_percent = Column(Integer, nullable=True)
    delay_dashboard = Column(Integer, nullable=True)
    delay_statistics = Column(Integer, nullable=True)


class AppVersionLock(Base):
    """
    Defines a minimum version for each named application.
    """
    __tablename__ = "app_version_locks"

    id = Column(Integer, primary_key=True, index=True)
    app_name = Column(String(100), unique=True, nullable=False)
    min_version = Column(String(20), nullable=False)


class AdvertisementClick(Base):
    """
    Records user clicks on advertisements for analytics.
    """
    __tablename__ = "advertisement_clicks"

    id = Column(Integer, primary_key=True)
    advertisement_id = Column(Integer, ForeignKey("advertisements.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    click_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
