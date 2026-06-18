"""Base model class for all SQLAlchemy models."""

from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models.
    
    Automatically tracks when records are created and modified.
    """
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Timestamp when record was created"
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Timestamp when record was last modified"
    )