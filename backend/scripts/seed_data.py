"""Seed demo data for development and testing."""

import asyncio
import uuid

from sqlalchemy import select

from app.database import async_session, engine, Base
from app.models import *  # noqa — register all models
from app.models.material import Material
from app.models.user import User
from app.utils.security import hash_password


async def seed():
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        existing = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if existing is not None:
            print("Admin user already exists — skipping seed.")
            return

        admin = User(
            id=uuid.uuid4(),
            username="admin",
            email="admin@materials-dmp.com",
            hashed_password=hash_password("admin123"),
            display_name="Administrator",
            is_active=True,
            is_approved=True,
            role_id=1,
            department="IT",
        )
        db.add(admin)
        await db.flush()

        demo_materials = [
            Material(
                name="PVDF-HFP Polymer Blend 15%",
                material_type="polymer",
                composition=[{"monomer": "PVDF", "mole_percent": 70}, {"monomer": "HFP", "mole_percent": 15}],
                formula_string="(C2H2F2)n-(C3F6)m",
                description="Poly(vinylidene fluoride-co-hexafluoropropylene) blend for SEM compatibility study",
                aliases=["PVDF-HFP", "Kynar Flex"],
                created_by=admin.id,
            ),
            Material(
                name="Stainless Steel 316L",
                material_type="metal",
                composition=[
                    {"element": "Fe", "amount": 65.0, "unit": "wt%"},
                    {"element": "Cr", "amount": 17.0, "unit": "wt%"},
                    {"element": "Ni", "amount": 12.0, "unit": "wt%"},
                    {"element": "Mo", "amount": 2.5, "unit": "wt%"},
                ],
                formula_string="Fe-Cr-Ni-Mo",
                description="Austenitic stainless steel, low carbon version for improved corrosion resistance",
                created_by=admin.id,
            ),
        ]
        for m in demo_materials:
            db.add(m)

        await db.commit()
        print("Demo data seeded successfully (admin/admin123).")


if __name__ == "__main__":
    asyncio.run(seed())
