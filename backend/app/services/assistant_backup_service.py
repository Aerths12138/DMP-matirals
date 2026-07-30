"""Temporary snapshots and one-time rollback for confirmed AI mutations."""

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_material_access, ensure_project_access, ensure_sample_access
from app.config import settings
from app.database import Base
from app.models.analysis import AnalysisResult
from app.models.assistant_backup import AssistantEntityBackup
from app.models.characterization import Characterization
from app.models.crystal_structure import CrystalStructure
from app.models.data_standard import MetadataTemplate, UnitDefinition
from app.models.experiment import Experiment
from app.models.material import Material
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
from app.models.user import User


BACKUP_ENTITY_MODELS = {
    "material": Material,
    "project": Project,
    "experiment": Experiment,
    "sample": Sample,
    "property": Property,
    "test": Test,
    "test_measurement": TestMeasurement,
    "characterization": Characterization,
}


def _encode(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return {"__assistant_type__": "uuid", "value": str(value)}
    if isinstance(value, datetime):
        return {"__assistant_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__assistant_type__": "date", "value": value.isoformat()}
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        value_type = value.get("__assistant_type__")
        if value_type == "uuid" and set(value) == {"__assistant_type__", "value"}:
            return uuid.UUID(value["value"])
        if value_type == "datetime" and set(value) == {"__assistant_type__", "value"}:
            return datetime.fromisoformat(value["value"])
        if value_type == "date" and set(value) == {"__assistant_type__", "value"}:
            return date.fromisoformat(value["value"])
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


async def _rows(db: AsyncSession, model, *conditions) -> list[dict]:
    table = model.__table__
    query = select(table)
    if conditions:
        query = query.where(*conditions)
    rows = (await db.execute(query)).mappings().all()
    return [_encode(dict(row)) for row in rows]


def _group(model, rows: list[dict]) -> dict:
    return {"table": model.__tablename__, "rows": rows}


async def _material_snapshot(db: AsyncSession, material_id: uuid.UUID, *, deep: bool) -> dict:
    material_rows = await _rows(db, Material, Material.id == material_id)
    if not material_rows:
        raise HTTPException(status_code=404, detail="Material not found")
    groups = [_group(Material, material_rows)]
    links: dict[str, list[dict]] = {}
    if not deep:
        return {"version": 1, "groups": groups, "links": links}

    for model in (
        CrystalStructure,
        Property,
        MechanicalProperties,
        ThermalProperties,
        ElectricalProperties,
        MagneticProperties,
        OpticalProperties,
        ProcessingMethod,
        Test,
    ):
        rows = await _rows(db, model, model.material_id == material_id)
        if rows:
            groups.append(_group(model, rows))

    test_ids = (
        await db.execute(select(Test.id).where(Test.material_id == material_id))
    ).scalars().all()
    if test_ids:
        measurement_rows = await _rows(
            db,
            TestMeasurement,
            TestMeasurement.test_id.in_(test_ids),
        )
        if measurement_rows:
            groups.append(_group(TestMeasurement, measurement_rows))

    sample_rows = (
        await db.execute(
            select(Sample.id, Sample.material_id).where(Sample.material_id == material_id)
        )
    ).mappings().all()
    if sample_rows:
        links["sample_material"] = [_encode(dict(row)) for row in sample_rows]
    return {"version": 1, "groups": groups, "links": links}


async def _project_snapshot(db: AsyncSession, project_id: uuid.UUID, *, deep: bool) -> dict:
    project_rows = await _rows(db, Project, Project.id == project_id)
    if not project_rows:
        raise HTTPException(status_code=404, detail="Project not found")
    groups = [_group(Project, project_rows)]
    links: dict[str, list[dict]] = {}
    if not deep:
        return {"version": 1, "groups": groups, "links": links}

    member_rows = await _rows(db, ProjectMember, ProjectMember.project_id == project_id)
    template_rows = await _rows(db, MetadataTemplate, MetadataTemplate.project_id == project_id)
    unit_rows = await _rows(db, UnitDefinition, UnitDefinition.project_id == project_id)
    experiment_rows = await _rows(db, Experiment, Experiment.project_id == project_id)
    for model, rows in (
        (ProjectMember, member_rows),
        (MetadataTemplate, template_rows),
        (UnitDefinition, unit_rows),
        (Experiment, experiment_rows),
    ):
        if rows:
            groups.append(_group(model, rows))

    experiment_ids = [
        _decode(row["id"])
        for row in experiment_rows
    ]
    sample_rows = []
    if experiment_ids:
        sample_rows = await _rows(db, Sample, Sample.experiment_id.in_(experiment_ids))
        if sample_rows:
            groups.append(_group(Sample, sample_rows))
    sample_ids = [_decode(row["id"]) for row in sample_rows]

    characterization_rows = []
    if sample_ids:
        processing_rows = await _rows(
            db,
            ProcessingMethod,
            ProcessingMethod.sample_id.in_(sample_ids),
        )
        characterization_rows = await _rows(
            db,
            Characterization,
            Characterization.sample_id.in_(sample_ids),
        )
        if processing_rows:
            groups.append(_group(ProcessingMethod, processing_rows))
        if characterization_rows:
            groups.append(_group(Characterization, characterization_rows))

        property_links = (
            await db.execute(
                select(Property.id, Property.sample_id).where(Property.sample_id.in_(sample_ids))
            )
        ).mappings().all()
        if property_links:
            links["property_sample"] = [_encode(dict(row)) for row in property_links]

    characterization_ids = [_decode(row["id"]) for row in characterization_rows]
    if characterization_ids:
        analysis_rows = await _rows(
            db,
            AnalysisResult,
            AnalysisResult.characterization_id.in_(characterization_ids),
        )
        if analysis_rows:
            groups.append(_group(AnalysisResult, analysis_rows))

    material_links = (
        await db.execute(
            select(Material.id, Material.project_id).where(Material.project_id == project_id)
        )
    ).mappings().all()
    if material_links:
        links["material_project"] = [_encode(dict(row)) for row in material_links]

    template_ids = [_decode(row["id"]) for row in template_rows]
    if template_ids:
        sample_template_links = (
            await db.execute(
                select(Sample.id, Sample.metadata_template_id).where(
                    Sample.metadata_template_id.in_(template_ids)
                )
            )
        ).mappings().all()
        characterization_template_links = (
            await db.execute(
                select(Characterization.id, Characterization.metadata_template_id).where(
                    Characterization.metadata_template_id.in_(template_ids)
                )
            )
        ).mappings().all()
        if sample_template_links:
            links["sample_template"] = [
                _encode(dict(row)) for row in sample_template_links
            ]
        if characterization_template_links:
            links["characterization_template"] = [
                _encode(dict(row)) for row in characterization_template_links
            ]

    return {"version": 1, "groups": groups, "links": links}


async def _sample_dependents_snapshot(
    db: AsyncSession,
    sample_ids: list[uuid.UUID],
) -> tuple[list[dict], dict[str, list[dict]]]:
    groups: list[dict] = []
    links: dict[str, list[dict]] = {}
    if not sample_ids:
        return groups, links

    processing_rows = await _rows(
        db, ProcessingMethod, ProcessingMethod.sample_id.in_(sample_ids)
    )
    characterization_rows = await _rows(
        db, Characterization, Characterization.sample_id.in_(sample_ids)
    )
    if processing_rows:
        groups.append(_group(ProcessingMethod, processing_rows))
    if characterization_rows:
        groups.append(_group(Characterization, characterization_rows))

    characterization_ids = [_decode(row["id"]) for row in characterization_rows]
    if characterization_ids:
        analysis_rows = await _rows(
            db,
            AnalysisResult,
            AnalysisResult.characterization_id.in_(characterization_ids),
        )
        if analysis_rows:
            groups.append(_group(AnalysisResult, analysis_rows))

    property_links = (
        await db.execute(
            select(Property.id, Property.sample_id).where(
                Property.sample_id.in_(sample_ids)
            )
        )
    ).mappings().all()
    if property_links:
        links["property_sample"] = [_encode(dict(row)) for row in property_links]
    return groups, links


async def _experiment_snapshot(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    *,
    deep: bool,
) -> dict:
    experiment_rows = await _rows(db, Experiment, Experiment.id == experiment_id)
    if not experiment_rows:
        raise HTTPException(status_code=404, detail="Experiment not found")
    groups = [_group(Experiment, experiment_rows)]
    links: dict[str, list[dict]] = {}
    if not deep:
        return {"version": 1, "groups": groups, "links": links}

    sample_rows = await _rows(db, Sample, Sample.experiment_id == experiment_id)
    if sample_rows:
        groups.append(_group(Sample, sample_rows))
    sample_ids = [_decode(row["id"]) for row in sample_rows]
    dependent_groups, dependent_links = await _sample_dependents_snapshot(db, sample_ids)
    groups.extend(dependent_groups)
    links.update(dependent_links)
    return {"version": 1, "groups": groups, "links": links}


async def _sample_snapshot(db: AsyncSession, sample_id: uuid.UUID, *, deep: bool) -> dict:
    sample_rows = await _rows(db, Sample, Sample.id == sample_id)
    if not sample_rows:
        raise HTTPException(status_code=404, detail="Sample not found")
    groups = [_group(Sample, sample_rows)]
    links: dict[str, list[dict]] = {}
    if deep:
        dependent_groups, dependent_links = await _sample_dependents_snapshot(
            db, [sample_id]
        )
        groups.extend(dependent_groups)
        links.update(dependent_links)
    return {"version": 1, "groups": groups, "links": links}


async def _property_snapshot(
    db: AsyncSession,
    property_id: uuid.UUID,
    *,
    deep: bool,
) -> dict:
    property_rows = await _rows(db, Property, Property.id == property_id)
    if not property_rows:
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "version": 1,
        "groups": [_group(Property, property_rows)],
        "links": {},
    }


async def _test_snapshot(
    db: AsyncSession,
    test_id: uuid.UUID,
    *,
    deep: bool,
) -> dict:
    test_rows = await _rows(db, Test, Test.id == test_id)
    if not test_rows:
        raise HTTPException(status_code=404, detail="Test not found")
    groups = [_group(Test, test_rows)]
    if deep:
        measurement_rows = await _rows(
            db, TestMeasurement, TestMeasurement.test_id == test_id
        )
        if measurement_rows:
            groups.append(_group(TestMeasurement, measurement_rows))
    return {"version": 1, "groups": groups, "links": {}}


async def _test_measurement_snapshot(
    db: AsyncSession,
    measurement_id: uuid.UUID,
    *,
    deep: bool,
) -> dict:
    measurement_rows = await _rows(
        db,
        TestMeasurement,
        TestMeasurement.id == measurement_id,
    )
    if not measurement_rows:
        raise HTTPException(status_code=404, detail="Test measurement not found")
    return {
        "version": 1,
        "groups": [_group(TestMeasurement, measurement_rows)],
        "links": {},
    }


async def _characterization_snapshot(
    db: AsyncSession,
    characterization_id: uuid.UUID,
    *,
    deep: bool,
) -> dict:
    characterization_rows = await _rows(
        db,
        Characterization,
        Characterization.id == characterization_id,
    )
    if not characterization_rows:
        raise HTTPException(status_code=404, detail="Characterization not found")
    groups = [_group(Characterization, characterization_rows)]
    if deep:
        analysis_rows = await _rows(
            db,
            AnalysisResult,
            AnalysisResult.characterization_id == characterization_id,
        )
        if analysis_rows:
            groups.append(_group(AnalysisResult, analysis_rows))
    return {"version": 1, "groups": groups, "links": {}}


async def create_backup(
    *,
    action_execution_id: uuid.UUID,
    tool_name: str,
    operation: str,
    entity_type: str,
    entity_id: uuid.UUID,
    db: AsyncSession,
    current_user: User,
) -> AssistantEntityBackup | None:
    if operation not in {"update", "delete"}:
        return None
    deep = operation == "delete"
    if entity_type == "material":
        material = await db.get(Material, entity_id)
        if material is None:
            raise HTTPException(status_code=404, detail="Material not found")
        entity_name = material.name
        snapshot = await _material_snapshot(db, entity_id, deep=deep)
    elif entity_type == "project":
        project = await db.get(Project, entity_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        entity_name = project.name
        snapshot = await _project_snapshot(db, entity_id, deep=deep)
    elif entity_type == "experiment":
        experiment = await db.get(Experiment, entity_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        entity_name = experiment.name
        snapshot = await _experiment_snapshot(db, entity_id, deep=deep)
    elif entity_type == "sample":
        sample = await db.get(Sample, entity_id)
        if sample is None:
            raise HTTPException(status_code=404, detail="Sample not found")
        entity_name = sample.sample_code
        snapshot = await _sample_snapshot(db, entity_id, deep=deep)
    elif entity_type == "property":
        prop = await db.get(Property, entity_id)
        if prop is None:
            raise HTTPException(status_code=404, detail="Property not found")
        entity_name = prop.property_name
        snapshot = await _property_snapshot(db, entity_id, deep=deep)
    elif entity_type == "test":
        test = await db.get(Test, entity_id)
        if test is None:
            raise HTTPException(status_code=404, detail="Test not found")
        entity_name = test.test_name
        snapshot = await _test_snapshot(db, entity_id, deep=deep)
    elif entity_type == "test_measurement":
        measurement = await db.get(TestMeasurement, entity_id)
        if measurement is None:
            raise HTTPException(status_code=404, detail="Test measurement not found")
        entity_name = measurement.property_name
        snapshot = await _test_measurement_snapshot(
            db, entity_id, deep=deep
        )
    elif entity_type == "characterization":
        characterization = await db.get(Characterization, entity_id)
        if characterization is None:
            raise HTTPException(status_code=404, detail="Characterization not found")
        entity_name = characterization.title or characterization.technique
        snapshot = await _characterization_snapshot(db, entity_id, deep=deep)
    else:
        raise HTTPException(status_code=422, detail="Unsupported backup entity type")

    now = datetime.utcnow()
    action_text = "修改" if operation == "update" else "删除"
    backup = AssistantEntityBackup(
        id=uuid.uuid4(),
        action_execution_id=action_execution_id,
        user_id=current_user.id,
        tool_name=tool_name,
        operation=operation,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        summary=f"回退 AI {action_text}：{entity_name}",
        snapshot=snapshot,
        created_at=now,
        expires_at=now + timedelta(hours=settings.ASSISTANT_BACKUP_RETENTION_HOURS),
    )
    db.add(backup)
    await db.flush()
    return backup


async def finalize_backup(
    backup: AssistantEntityBackup | None,
    db: AsyncSession,
) -> None:
    if backup is None or backup.operation != "update":
        return
    table = BACKUP_ENTITY_MODELS[backup.entity_type].__table__
    row = (
        await db.execute(select(table).where(table.c.id == backup.entity_id))
    ).mappings().one()
    backup.post_snapshot = _encode(dict(row))
    await db.flush()


async def purge_expired_backups(db: AsyncSession) -> None:
    await db.execute(
        delete(AssistantEntityBackup).where(
            AssistantEntityBackup.expires_at <= datetime.utcnow()
        )
    )


async def list_available_backups(
    db: AsyncSession,
    current_user: User,
) -> list[AssistantEntityBackup]:
    await purge_expired_backups(db)
    result = await db.execute(
        select(AssistantEntityBackup)
        .where(
            AssistantEntityBackup.user_id == current_user.id,
            AssistantEntityBackup.restored_at.is_(None),
            AssistantEntityBackup.expires_at > datetime.utcnow(),
        )
        .order_by(AssistantEntityBackup.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


def _is_admin(current_user: User) -> bool:
    return current_user.role is not None and current_user.role.name == "admin"


def _require_permission(current_user: User, codename: str) -> None:
    if current_user.role is None:
        allowed = False
    else:
        permissions = {permission.codename for permission in current_user.role.permissions}
        allowed = "admin" in permissions or codename in permissions
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions: {codename}")


def _main_snapshot_row(backup: AssistantEntityBackup) -> dict:
    groups = backup.snapshot.get("groups", [])
    if not groups or not groups[0].get("rows"):
        raise HTTPException(status_code=409, detail="Backup snapshot is incomplete")
    return _decode(groups[0]["rows"][0])


async def _authorize_restore(
    backup: AssistantEntityBackup,
    db: AsyncSession,
    current_user: User,
) -> None:
    if backup.user_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="This backup belongs to another user")
    main_row = _main_snapshot_row(backup)
    if backup.entity_type == "material":
        permission = "material:update" if backup.operation == "update" else "material:delete"
        _require_permission(current_user, permission)
        if backup.operation == "update":
            material = await db.get(Material, backup.entity_id)
            if material is None:
                raise HTTPException(status_code=404, detail="Material not found")
            await ensure_material_access(db, current_user, material, "editor")
            old_project_id = main_row.get("project_id")
            if old_project_id is not None:
                await ensure_project_access(db, current_user, old_project_id, "editor")
        elif main_row.get("project_id") is not None:
            await ensure_project_access(db, current_user, main_row["project_id"], "owner")
    elif backup.entity_type == "project":
        permission = "experiment:update" if backup.operation == "update" else "experiment:delete"
        _require_permission(current_user, permission)
        if backup.operation == "update":
            project = await db.get(Project, backup.entity_id)
            if project is None:
                raise HTTPException(status_code=404, detail="Project not found")
            await ensure_project_access(db, current_user, backup.entity_id, "editor")
    elif backup.entity_type == "experiment":
        permission = "experiment:update" if backup.operation == "update" else "experiment:delete"
        minimum_role = "editor" if backup.operation == "update" else "owner"
        _require_permission(current_user, permission)
        await ensure_project_access(
            db,
            current_user,
            main_row["project_id"],
            minimum_role,
        )
    elif backup.entity_type == "sample":
        permission = "sample:update" if backup.operation == "update" else "sample:delete"
        minimum_role = "editor" if backup.operation == "update" else "owner"
        _require_permission(current_user, permission)
        experiment_id = main_row.get("experiment_id")
        if experiment_id is None:
            is_owner = main_row.get("created_by") == current_user.id
            if not is_owner and not _is_admin(current_user):
                raise HTTPException(status_code=403, detail="Insufficient sample access")
        else:
            experiment = await db.get(Experiment, experiment_id)
            if experiment is None:
                raise HTTPException(status_code=404, detail="Experiment not found")
            await ensure_project_access(
                db,
                current_user,
                experiment.project_id,
                minimum_role,
            )
    elif backup.entity_type in {"property", "test"}:
        permission = (
            "property:update" if backup.operation == "update" else "property:delete"
        )
        minimum_role = "editor" if backup.operation == "update" else "owner"
        _require_permission(current_user, permission)
        material = await db.get(Material, main_row["material_id"])
        if material is None:
            raise HTTPException(status_code=404, detail="Material not found")
        await ensure_material_access(
            db, current_user, material, minimum_role
        )
    elif backup.entity_type == "test_measurement":
        permission = (
            "property:update" if backup.operation == "update" else "property:delete"
        )
        minimum_role = "editor" if backup.operation == "update" else "owner"
        _require_permission(current_user, permission)
        test = await db.get(Test, main_row["test_id"])
        if test is None:
            raise HTTPException(status_code=404, detail="Test not found")
        material = await db.get(Material, test.material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="Material not found")
        await ensure_material_access(
            db,
            current_user,
            material,
            minimum_role,
        )
    elif backup.entity_type == "characterization":
        permission = (
            "characterization:update"
            if backup.operation == "update"
            else "characterization:delete"
        )
        minimum_role = "editor" if backup.operation == "update" else "owner"
        _require_permission(current_user, permission)
        sample = await db.get(Sample, main_row["sample_id"])
        if sample is None:
            raise HTTPException(status_code=404, detail="Sample not found")
        await ensure_sample_access(db, current_user, sample, minimum_role)
    else:
        raise HTTPException(status_code=422, detail="Unsupported backup entity type")


async def _insert_missing_rows(db: AsyncSession, table, encoded_rows: list[dict]) -> None:
    for encoded_row in encoded_rows:
        row = _decode(encoded_row)
        existing = await db.execute(select(table.c.id).where(table.c.id == row["id"]))
        if existing.scalar_one_or_none() is None:
            await db.execute(table.insert().values(**row))


async def _restore_links(db: AsyncSession, links: dict[str, list[dict]]) -> None:
    link_specs = {
        "sample_material": (Sample.__table__, "material_id"),
        "material_project": (Material.__table__, "project_id"),
        "property_sample": (Property.__table__, "sample_id"),
        "sample_template": (Sample.__table__, "metadata_template_id"),
        "characterization_template": (
            Characterization.__table__,
            "metadata_template_id",
        ),
    }
    for link_name, encoded_rows in links.items():
        if link_name not in link_specs:
            continue
        table, field = link_specs[link_name]
        for encoded_row in encoded_rows:
            row = _decode(encoded_row)
            await db.execute(
                update(table).where(table.c.id == row["id"]).values({field: row[field]})
            )


async def restore_backup(
    backup_id: uuid.UUID,
    db: AsyncSession,
    current_user: User,
) -> AssistantEntityBackup:
    backup = await db.get(AssistantEntityBackup, backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    if backup.restored_at is not None:
        raise HTTPException(status_code=409, detail="Backup has already been restored")
    now = datetime.utcnow()
    if backup.expires_at <= now:
        raise HTTPException(status_code=410, detail="Backup has expired")
    await _authorize_restore(backup, db, current_user)

    newer = await db.scalar(
        select(AssistantEntityBackup.id).where(
            AssistantEntityBackup.entity_type == backup.entity_type,
            AssistantEntityBackup.entity_id == backup.entity_id,
            AssistantEntityBackup.created_at > backup.created_at,
            AssistantEntityBackup.restored_at.is_(None),
            AssistantEntityBackup.expires_at > now,
        )
    )
    if newer is not None:
        raise HTTPException(status_code=409, detail="Restore the newest version first")

    main_table = BACKUP_ENTITY_MODELS[backup.entity_type].__table__
    if backup.operation == "update":
        current_row = (
            await db.execute(select(main_table).where(main_table.c.id == backup.entity_id))
        ).mappings().one_or_none()
        if current_row is None:
            raise HTTPException(status_code=404, detail="Entity no longer exists")
        if backup.post_snapshot is not None and _encode(dict(current_row)) != backup.post_snapshot:
            raise HTTPException(
                status_code=409,
                detail="Entity changed after this backup; refusing to overwrite newer data",
            )
        old_row = _main_snapshot_row(backup)
        values = {key: value for key, value in old_row.items() if key != "id"}
        await db.execute(
            update(main_table).where(main_table.c.id == backup.entity_id).values(**values)
        )
    else:
        for group in backup.snapshot.get("groups", []):
            table = Base.metadata.tables[group["table"]]
            await _insert_missing_rows(db, table, group.get("rows", []))
        await _restore_links(db, backup.snapshot.get("links", {}))

    backup.restored_at = now
    backup.restored_by = current_user.id
    await db.flush()
    return backup
