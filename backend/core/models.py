import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    glossaries = relationship("Glossary", back_populates="user", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="empty") # empty, analyzing, ready, completed
    video_title = Column(String, default="")
    
    # S3 ključevi za skladištenje fajlova
    video_s3_key = Column(String, nullable=True)
    vocals_s3_key = Column(String, nullable=True)
    no_vocals_s3_key = Column(String, nullable=True)
    visual_context_s3_key = Column(String, nullable=True)
    dubbed_audio_s3_key = Column(String, nullable=True)
    final_video_s3_key = Column(String, nullable=True)
    
    costs = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="projects")
    segments = relationship("Segment", back_populates="project", cascade="all, delete-orphan")

class Segment(Base):
    __tablename__ = "segments"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    segment_id = Column(Integer, primary_key=True) # Hronološki indeks (0, 1, 2...) koji se koristi na frontendu
    start = Column(Float, nullable=False)
    end = Column(Float, nullable=False)
    original = Column(String, default="")
    translated = Column(String, default="")
    voice_type = Column(String, default="clone") # clone, male
    volume = Column(Float, default=0.0)
    speed = Column(Float, default=1.0)
    pitch = Column(Float, default=0.0)
    bg_volume = Column(Float, default=0.0)
    
    # S3 ključ za izgenerisani audio fajl
    tts_s3_key = Column(String, nullable=True)
    tts_duration = Column(Float, nullable=True)
    status = Column(String, default="edited") # edited, previewed

    project = relationship("Project", back_populates="segments")

class Glossary(Base):
    __tablename__ = "glossaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_word = Column(String, nullable=False)
    target_word = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="glossaries")
