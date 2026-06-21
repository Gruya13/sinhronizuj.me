import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.core.database import Base

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringhex.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(value)
        else:
            if isinstance(value, uuid.UUID):
                return value.hex
            else:
                return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)

class User(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, server_default="false")
    created_at = Column(DateTime, default=datetime.utcnow)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    glossaries = relationship("Glossary", back_populates="user", cascade="all, delete-orphan")
    translation_memories = relationship("TranslationMemory", back_populates="user", cascade="all, delete-orphan")
    wiki_rules = relationship("WikiRule", back_populates="user", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")

class Segment(Base):
    __tablename__ = "segments"

    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
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
    active_speaker = Column(Boolean, default=True, server_default="true")
    
    # S3 ključ za izgenerisani audio fajl
    tts_s3_key = Column(String, nullable=True)
    tts_duration = Column(Float, nullable=True)
    status = Column(String, default="edited") # edited, previewed
    needs_retranslation = Column(Boolean, default=False, server_default="false")
    actual_speed_factor = Column(Float, default=1.0, server_default="1.0")
    confidence_score = Column(Integer, default=5, server_default="5")

    project = relationship("Project", back_populates="segments")

class Glossary(Base):
    __tablename__ = "glossaries"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_word = Column(String, nullable=False)
    target_word = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="glossaries")

class Waitlist(Base):
    __tablename__ = "waitlist"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending") # pending, approved, rejected

class Job(Base):
    __tablename__ = "jobs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False) # e.g. "dubbing"
    status = Column(String, default="pending") # pending, running, completed, failed
    current_phase = Column(String, nullable=True) # e.g. "transcription", "translation", "tts", "mixing"
    attempt = Column(Integer, default=1, server_default="1")
    current_artifact_keys = Column(JSON, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="jobs")

class TranslationMemory(Base):
    __tablename__ = "translation_memory"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    source_text = Column(String, nullable=False)
    target_text = Column(String, nullable=False)
    embedding = Column(JSON, nullable=True) # Lista float-ova za kosinusnu sličnost
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="translation_memories")
    project = relationship("Project")

class WikiRule(Base):
    __tablename__ = "wiki_rules"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    category = Column(String, default="general")
    is_global = Column(Boolean, default=False, server_default="false")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="wiki_rules")
