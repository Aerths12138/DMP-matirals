"""AnalysisResult model — ML inference results with version tracking."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        Index(
            "uq_analysis_latest_per_type",
            "characterization_id",
            "analysis_type",
            unique=True,
            sqlite_where=text("is_latest = 1"),
            postgresql_where=text("is_latest"),
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    characterization_id = Column(
        Uuid,
        ForeignKey("characterizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_type = Column(String(100), nullable=False)  # cnn_classification, cellpose_segmentation, feature_extraction
    pipeline_name = Column(String(200))  # sem_fusion_pipeline_v2
    model_name = Column(String(200))  # efficientnet_b0, DINOv2_ViT-S
    model_version = Column(String(50))
    result_data = Column(JSON, nullable=False, default=dict)
    # {"predicted_class":"Compatible","confidence":0.92,
    #  "probabilities":{"Incompatible":0.03,"Partially compatible":0.05,"Compatible":0.92},
    #  "sharpness_score":0.23,"pss":0.12,"dms":0.34,"iss":0.08}
    segmentation_data = Column(JSON, default=None)
    # mask overlay paths, n_particles, morphology features
    quality_metrics = Column(JSON, default=dict)  # {"accuracy":0.92,"f1_macro":0.89}
    source_file_id = Column(Uuid, ForeignKey("files.id"))
    processing_time_ms = Column(Integer)
    gpu_used = Column(Boolean, default=False)
    error_message = Column(Text)
    is_latest = Column(Boolean, default=True)
    previous_version_id = Column(Uuid, ForeignKey("analysis_results.id"))
    run_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    characterization = relationship("Characterization", back_populates="analysis_results")
    source_file = relationship("File", foreign_keys=[source_file_id], lazy="selectin")
    runner = relationship("User", foreign_keys=[run_by], lazy="selectin")

    def __repr__(self) -> str:
        return f"<AnalysisResult {self.analysis_type} v{self.model_version}>"
