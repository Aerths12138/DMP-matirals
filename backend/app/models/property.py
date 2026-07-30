"""Property models — generic JSON-based + type-specific tables."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Property(Base):
    """Generic property: one row per measurement.  Long-tail properties go here."""

    __tablename__ = "properties"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    sample_id = Column(Uuid, ForeignKey("samples.id", ondelete="SET NULL"))
    property_type = Column(String(50), nullable=False)  # mechanical, thermal, electrical, magnetic, optical
    property_name = Column(String(200), nullable=False)  # tensile_strength, thermal_conductivity, etc.
    value_number = Column(Float)
    value_text = Column(String(500))
    uncertainty = Column(Float)
    unit = Column(String(50))  # MPa, W/mK, S/cm, etc.
    conditions = Column(JSON, default=dict)  # {"temperature":25,"temperature_unit":"C","atmosphere":"air"}
    test_method = Column(String(200))  # ASTM D638, ISO 527, etc.
    source_type = Column(String(30), default="experimental")
    source_doi = Column(String(200))
    source_file_id = Column(Uuid, ForeignKey("files.id"))
    is_validated = Column(Boolean, default=False)
    validated_by = Column(Uuid, ForeignKey("users.id"))
    notes = Column(Text)
    metadata_ = Column("metadata", JSON, default=dict)
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    material = relationship("Material", back_populates="properties")
    sample = relationship("Sample", foreign_keys=[sample_id])
    source_file = relationship("File", foreign_keys=[source_file_id])

    def __repr__(self) -> str:
        return f"<Property {self.property_name}={self.value_number} {self.unit}>"


class MechanicalProperties(Base):
    __tablename__ = "mechanical_properties"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    tensile_strength = Column(Float)  # MPa
    yield_strength = Column(Float)  # MPa
    elastic_modulus = Column(Float)  # GPa
    elongation_at_break = Column(Float)  # %
    hardness = Column(Float)
    hardness_type = Column(String(20))  # Vickers, Rockwell, Brinell
    fracture_toughness = Column(Float)  # MPa*m^0.5
    flexural_strength = Column(Float)  # MPa
    impact_strength = Column(Float)  # kJ/m^2
    temperature = Column(Float)  # test temperature in °C
    strain_rate = Column(Float)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    material = relationship("Material", back_populates="mechanical_properties")


class ThermalProperties(Base):
    __tablename__ = "thermal_properties"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    thermal_conductivity = Column(Float)  # W/mK
    specific_heat_capacity = Column(Float)  # J/kgK
    thermal_expansion_coefficient = Column(Float)  # 10^-6/K
    glass_transition_temp = Column(Float)  # °C (Tg, for polymers)
    melting_temp = Column(Float)  # °C (Tm)
    decomposition_temp = Column(Float)  # °C (Td)
    heat_deflection_temp = Column(Float)  # °C (HDT)
    vicat_softening_temp = Column(Float)  # °C
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    material = relationship("Material", back_populates="thermal_properties")


class ElectricalProperties(Base):
    __tablename__ = "electrical_properties"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    electrical_conductivity = Column(Float)  # S/cm
    electrical_resistivity = Column(Float)  # Ohm*cm
    dielectric_constant = Column(Float)
    dielectric_strength = Column(Float)  # kV/mm
    band_gap = Column(Float)  # eV
    ionic_conductivity = Column(Float)  # S/cm
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    material = relationship("Material", back_populates="electrical_properties")


class MagneticProperties(Base):
    __tablename__ = "magnetic_properties"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    saturation_magnetization = Column(Float)  # emu/g
    coercivity = Column(Float)  # Oe
    remanence = Column(Float)  # emu/g
    curie_temperature = Column(Float)  # °C
    magnetic_susceptibility = Column(Float)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    material = relationship("Material", back_populates="magnetic_properties")


class OpticalProperties(Base):
    __tablename__ = "optical_properties"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    refractive_index = Column(Float)
    transmittance = Column(Float)  # %
    absorbance = Column(Float)
    band_gap_optical = Column(Float)  # eV
    photoluminescence_peak = Column(Float)  # nm
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    material = relationship("Material", back_populates="optical_properties")
