"""Property Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PropertyBase(BaseModel):
    property_type: str = Field(default="other", max_length=50)
    property_name: str = Field(max_length=200)
    value_number: float | None = None
    value_text: str | None = Field(default=None, max_length=500)
    uncertainty: float | None = None
    unit: str | None = Field(default=None, max_length=50)
    conditions: dict = {}
    test_method: str | None = Field(default=None, max_length=200)
    source_type: str = Field(default="experimental", max_length=30)
    source_doi: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    metadata_: dict = Field(default={}, serialization_alias="metadata")


class PropertyCreate(PropertyBase):
    material_id: uuid.UUID
    sample_id: uuid.UUID | None = None
    # Accept "metadata" from JSON input
    metadata_: dict = Field(default={}, serialization_alias="metadata", validation_alias="metadata")


class PropertyUpdate(BaseModel):
    property_type: str | None = Field(default=None, max_length=50)
    property_name: str | None = Field(default=None, max_length=200)
    value_number: float | None = None
    value_text: str | None = None
    uncertainty: float | None = None
    unit: str | None = None
    conditions: dict | None = None
    test_method: str | None = None
    source_type: str | None = None
    source_doi: str | None = None
    notes: str | None = None
    metadata_: dict | None = Field(default=None, serialization_alias="metadata", validation_alias="metadata")


class PropertyResponse(PropertyBase):
    id: uuid.UUID
    material_id: uuid.UUID
    sample_id: uuid.UUID | None = None
    is_validated: bool = False
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PropertyComparisonMaterial(BaseModel):
    id: uuid.UUID
    name: str
    material_type: str
    project_id: uuid.UUID | None = None


class PropertyComparisonMeasurement(BaseModel):
    id: uuid.UUID
    material_id: uuid.UUID
    sample_id: uuid.UUID | None = None
    property_type: str
    property_name: str
    value_number: float
    uncertainty: float | None = None
    unit: str | None = None
    conditions: dict = Field(default_factory=dict)
    test_method: str | None = None
    created_at: datetime
    measurement_count: int


class PropertyComparisonResponse(BaseModel):
    materials: list[PropertyComparisonMaterial]
    measurements: list[PropertyComparisonMeasurement]


class PropertyComparisonSample(BaseModel):
    id: uuid.UUID
    sample_code: str
    batch_number: str | None = None
    material_id: uuid.UUID | None = None
    material_name: str | None = None
    experiment_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    form: str | None = None
    status: str


class SamplePropertyComparisonResponse(BaseModel):
    samples: list[PropertyComparisonSample]
    measurements: list[PropertyComparisonMeasurement]


class PropertyBulkCreate(BaseModel):
    """Bulk import wrapper."""
    properties: list[PropertyCreate]


class MechanicalPropertiesBase(BaseModel):
    tensile_strength: float | None = None
    yield_strength: float | None = None
    elastic_modulus: float | None = None
    elongation_at_break: float | None = None
    hardness: float | None = None
    hardness_type: str | None = Field(default=None, max_length=20)
    fracture_toughness: float | None = None
    flexural_strength: float | None = None
    impact_strength: float | None = None
    temperature: float | None = None
    strain_rate: float | None = None
    metadata: dict = {}


class MechanicalPropertiesCreate(MechanicalPropertiesBase):
    material_id: uuid.UUID


class MechanicalPropertiesResponse(MechanicalPropertiesBase):
    id: uuid.UUID
    material_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ThermalPropertiesBase(BaseModel):
    thermal_conductivity: float | None = None
    specific_heat_capacity: float | None = None
    thermal_expansion_coefficient: float | None = None
    glass_transition_temp: float | None = None
    melting_temp: float | None = None
    decomposition_temp: float | None = None
    heat_deflection_temp: float | None = None
    vicat_softening_temp: float | None = None
    metadata: dict = {}


class ThermalPropertiesCreate(ThermalPropertiesBase):
    material_id: uuid.UUID


class ThermalPropertiesResponse(ThermalPropertiesBase):
    id: uuid.UUID
    material_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
