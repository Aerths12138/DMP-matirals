"""Persisted, source-citable chunks for the research-document RAG layer."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ResearchKnowledgeChunk(Base):
    """One bounded excerpt extracted from an uploaded research attachment.

    Chunks intentionally inherit access control from ``files`` instead of
    carrying a copied project id.  This prevents a stale ACL copy from making a
    private attachment retrievable after its parent changes.
    """

    __tablename__ = "research_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("file_id", "chunk_index", name="uq_research_knowledge_file_chunk"),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    file_id = Column(
        Uuid,
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    token_count = Column(Integer, nullable=False, default=0)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    source_type = Column(String(30), nullable=False, default="text")
    source_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    file = relationship("File", back_populates="knowledge_chunks", lazy="selectin")
