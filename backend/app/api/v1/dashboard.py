"""Dashboard statistics endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, material_visibility_condition, require_permission
from app.models.material import Material
from app.models.test import Test
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:read")),
):
    """Return dashboard statistics."""
    visible_material = material_visibility_condition(current_user)
    # Material count
    mat_total = (
        await db.execute(select(func.count()).select_from(Material).where(visible_material))
    ).scalar() or 0

    # Material type distribution
    type_rows = (
        await db.execute(
            select(Material.material_type, func.count())
            .where(visible_material)
            .group_by(Material.material_type)
        )
    ).all()
    material_types = [{"type": t, "count": c} for t, c in type_rows]

    # User count
    user_total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

    # Test count
    test_total = (
        await db.execute(
            select(func.count())
            .select_from(Test)
            .join(Material)
            .where(visible_material)
        )
    ).scalar() or 0

    # Recent materials (last 5)
    recent = await db.execute(
        select(Material)
        .where(visible_material)
        .order_by(Material.created_at.desc())
        .limit(5)
    )
    recent_materials = [
        {
            "id": str(m.id),
            "name": m.name,
            "material_type": m.material_type,
            "formula_string": m.formula_string,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in recent.scalars().all()
    ]

    # Recent tests (last 5)
    recent_tests = await db.execute(
        select(Test)
        .join(Material)
        .where(visible_material)
        .order_by(Test.created_at.desc())
        .limit(5)
    )
    recent_test_list = [
        {
            "id": str(t.id),
            "test_name": t.test_name,
            "test_method": t.test_method,
            "material_id": str(t.material_id),
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in recent_tests.scalars().all()
    ]

    return {
        "materials_total": mat_total,
        "material_types": material_types,
        "users_total": user_total,
        "tests_total": test_total,
        "recent_materials": recent_materials,
        "recent_tests": recent_test_list,
    }
