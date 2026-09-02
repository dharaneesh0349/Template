"""
Database schema & initialization for CloudStack Template Automation.
Supports SQLite (development/standalone) and PostgreSQL (production).
"""

import os
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, JSON, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class Execution(Base):
    __tablename__ = "executions"

    id = Column(String(64), primary_key=True, index=True)
    status = Column(String(32), default="in_progress", index=True)  # in_progress, completed, failed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    ssh_host = Column(String(255), nullable=False)
    ssh_port = Column(String(16), default="22")
    ssh_username = Column(String(128), default="root")
    cloudstack_username = Column(String(128), default="centos")
    hypervisor_type = Column(String(64), default="auto")
    
    # JSON-encoded details
    detected_environment = Column(JSON, nullable=True)
    validation_checks = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    next_steps = Column(JSON, nullable=True)
    
    # Relationship to detailed steps
    steps = relationship("ExecutionStepRecord", back_populates="execution", cascade="all, delete-orphan", order_by="ExecutionStepRecord.created_at")

    def to_dict(self):
        return {
            "execution_id": self.id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "ssh_host": self.ssh_host,
            "ssh_port": int(self.ssh_port) if str(self.ssh_port).isdigit() else 22,
            "ssh_username": self.ssh_username,
            "cloudstack_username": self.cloudstack_username,
            "hypervisor_type": self.hypervisor_type,
            "detected_environment": self.detected_environment,
            "validation_checks": self.validation_checks,
            "error_message": self.error_message,
            "next_steps": self.next_steps,
            "execution_steps": [s.to_dict() for s in self.steps] if self.steps else []
        }


class ExecutionStepRecord(Base):
    __tablename__ = "execution_steps"

    id = Column(String(64), primary_key=True)
    execution_id = Column(String(64), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    command = Column(Text, nullable=True)
    status = Column(String(32), default="pending")  # pending, running, completed, failed, skipped
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    execution = relationship("Execution", back_populates="steps")

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "command": self.command,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "timestamp": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


def get_db_url() -> str:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/cloudstack_automation.db")
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_url


def init_db(engine=None):
    if engine is None:
        db_url = get_db_url()
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        engine = create_engine(db_url, connect_args=connect_args, echo=False)
    
    Base.metadata.create_all(engine)
    print(f"Database schema initialized successfully on {engine.url}")
    return engine


if __name__ == "__main__":
    init_db()
