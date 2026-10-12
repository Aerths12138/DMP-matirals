"""SQLAlchemy ORM models.

Import all models here so Alembic can discover them.
"""

from app.models.collection import Collection
from app.models.analysis import AnalysisResult
from app.models.assistant import AssistantActionExecution
from app.models.assistant_backup import AssistantEntityBackup
from app.models.assistant_conversation import AssistantConversation
from app.models.audit import AuditLog
from app.models.characterization import Characterization
from app.models.crystal_structure import CrystalStructure
from app.models.experiment import Experiment
from app.models.file import File
from app.models.research_knowledge import ResearchKnowledgeChunk
from app.models.material import Material
from app.models.measurement_dataset import MeasurementDataset, MeasurementPoint
from app.models.data_standard import MetadataTemplate, UnitDefinition
from app.models.permission import Permission, Role, role_permissions
from app.models.processing import ProcessingMethod
from app.models.project import Project, ProjectMember
from app.models.property import (
    ElectricalProperties,
    MagneticProperties,
    MechanicalProperties,
    OpticalProperties,
    Property,
    ThermalProperties,
)
from app.models.sample import Sample
from app.models.test import Test, TestMeasurement
from app.models.user import RefreshToken, User

__all__ = [
    "Collection",
    "AnalysisResult",
    "AssistantActionExecution",
    "AssistantEntityBackup",
    "AssistantConversation",
    "AuditLog",
    "Characterization",
    "CrystalStructure",
    "ElectricalProperties",
    "Experiment",
    "File",
    "ResearchKnowledgeChunk",
    "MagneticProperties",
    "Material",
    "MeasurementDataset",
    "MeasurementPoint",
    "MetadataTemplate",
    "MechanicalProperties",
    "OpticalProperties",
    "Permission",
    "ProcessingMethod",
    "Project",
    "ProjectMember",
    "Property",
    "RefreshToken",
    "Role",
    "Sample",
    "Test",
    "TestMeasurement",
    "ThermalProperties",
    "UnitDefinition",
    "User",
    "role_permissions",
]
