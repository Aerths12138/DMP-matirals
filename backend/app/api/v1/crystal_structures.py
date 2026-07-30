"""CrystalStructure CRUD and CIF import endpoints."""

import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_material_access,
    get_db,
    material_visibility_condition,
    require_permission,
)
from app.models.crystal_structure import CrystalStructure
from app.models.material import Material
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.crystal_structure import (
    CrystalStructureCreate,
    CrystalStructureResponse,
    CrystalStructureUpdate,
)

router = APIRouter(prefix="/crystal-structures", tags=["Crystal Structures"])


async def _get_material(db: AsyncSession, material_id: uuid.UUID) -> Material:
    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return material


async def _get_structure(db: AsyncSession, structure_id: uuid.UUID) -> CrystalStructure:
    structure = await db.get(CrystalStructure, structure_id)
    if structure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crystal structure not found",
        )
    return structure


async def _ensure_structure_access(
    db: AsyncSession,
    current_user: User,
    structure: CrystalStructure,
    minimum_role: str,
) -> None:
    material = await _get_material(db, structure.material_id)
    await ensure_material_access(db, current_user, material, minimum_role)


@router.get("", response_model=PaginatedResponse[CrystalStructureResponse])
async def list_structures(
    pagination: PaginationParams = Depends(),
    material_id: str | None = None,
    crystal_system: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("crystal_structure:read")),
):
    """List visible crystal structures with optional filtering."""
    query = select(CrystalStructure)

    if material_id:
        material_uuid = uuid.UUID(material_id)
        material = await _get_material(db, material_uuid)
        await ensure_material_access(db, current_user, material, "viewer")
        query = query.where(CrystalStructure.material_id == material_uuid)
    else:
        query = query.join(Material, CrystalStructure.material_id == Material.id).where(
            material_visibility_condition(current_user)
        )
    if crystal_system:
        query = query.where(CrystalStructure.crystal_system == crystal_system)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size).order_by(CrystalStructure.created_at.desc())
    structures = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[CrystalStructureResponse.model_validate(item) for item in structures],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total > 0 else 0,
    )


@router.post("", response_model=CrystalStructureResponse, status_code=status.HTTP_201_CREATED)
async def create_structure(
    body: CrystalStructureCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("crystal_structure:create")),
):
    """Manually create a crystal structure entry."""
    material = await _get_material(db, body.material_id)
    await ensure_material_access(db, current_user, material, "editor")

    structure = CrystalStructure(
        **body.model_dump(exclude={"metadata_"}),
        metadata_=body.metadata_,
    )
    db.add(structure)
    await db.flush()
    await db.refresh(structure)
    return structure


@router.post("/import-cif", response_model=CrystalStructureResponse, status_code=status.HTTP_201_CREATED)
async def import_cif(
    material_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("crystal_structure:create")),
):
    """Upload and parse a CIF file to create a crystal structure entry."""
    if not file.filename or not file.filename.endswith(".cif"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .cif files are accepted",
        )

    material_uuid = uuid.UUID(material_id)
    material = await _get_material(db, material_uuid)
    await ensure_material_access(db, current_user, material, "editor")

    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser

        content = await file.read()
        cif_text = content.decode("utf-8")
        parser = CifParser(io.StringIO(cif_text))
        structure: Structure = parser.get_structures()[0]

        lattice = structure.lattice
        space_group = structure.get_space_group_info()
        crystal_structure = CrystalStructure(
            material_id=material_uuid,
            space_group=space_group[0] if space_group else None,
            space_group_num=space_group[1] if space_group else None,
            crystal_system=lattice.get_space_group_info()[0] if lattice else None,
            a=lattice.a if lattice else None,
            b=lattice.b if lattice else None,
            c=lattice.c if lattice else None,
            alpha=lattice.alpha if lattice else None,
            beta=lattice.beta if lattice else None,
            gamma=lattice.gamma if lattice else None,
            volume=lattice.volume if lattice else None,
            atomic_sites=[
                {
                    "element": str(site.species_string),
                    "x": float(site.x),
                    "y": float(site.y),
                    "z": float(site.z),
                    "occupancy": float(getattr(site, "occupancy", 1.0)),
                }
                for site in structure.sites
            ],
            cif_raw_data=parser.as_dict(),
            source_type="experimental",
            metadata_={"original_filename": file.filename},
        )
        db.add(crystal_structure)
        await db.flush()
        await db.refresh(crystal_structure)
        return crystal_structure
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse CIF file: {exc}",
        ) from exc


@router.get("/{structure_id}", response_model=CrystalStructureResponse)
async def get_structure(
    structure_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("crystal_structure:read")),
):
    structure = await _get_structure(db, uuid.UUID(structure_id))
    await _ensure_structure_access(db, current_user, structure, "viewer")
    return structure


@router.put("/{structure_id}", response_model=CrystalStructureResponse)
async def update_structure(
    structure_id: str,
    body: CrystalStructureUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("crystal_structure:update")),
):
    structure = await _get_structure(db, uuid.UUID(structure_id))
    await _ensure_structure_access(db, current_user, structure, "editor")

    update_data = body.model_dump(exclude_unset=True, exclude={"metadata_"})
    if body.metadata_ is not None:
        structure.metadata_ = body.metadata_
    for field, value in update_data.items():
        setattr(structure, field, value)

    await db.flush()
    await db.refresh(structure)
    return structure


@router.delete("/{structure_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_structure(
    structure_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("crystal_structure:delete")),
):
    structure = await _get_structure(db, uuid.UUID(structure_id))
    await _ensure_structure_access(db, current_user, structure, "owner")
    await db.delete(structure)
