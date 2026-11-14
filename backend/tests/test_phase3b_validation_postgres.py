"""Synthetic T-02 snapshot checks against a disposable PostgreSQL fixture."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from app.common.enums import DoseStatus, DoseType, Gender
from app.modules.admin.schemas import (
    UpdateStudentProfileRequest,
    VaccineCreateRequest,
    VaccineDoseConfigInput,
    VaccineUpdateRequest,
)
from app.modules.admin.students.service import StudentAdminService
from app.modules.admin.vaccines.service import VaccineCatalogService
from app.modules.audit.service import AuditService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.vaccination_scheme.models import (
    StudentSchemeVersion,
    StudentVaccine,
    StudentVaccineDose,
)
from app.modules.vaccination_scheme.repository import SchemeRepository, VaccineRepository
from app.modules.vaccination_scheme.service import SchemeService
from app.modules.vaccines.models import VaccineDoseConfig, VaccineRule
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "t02_profile_changes.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_postgres_profile_reconciliation_keeps_synthetic_history(
    integration_engine,
    integration_accounts,
    case,
):
    if integration_engine.dialect.name != "postgresql":
        pytest.skip("T-02 PostgreSQL JSONB evidence requires a disposable PostgreSQL URL")

    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    async with sessions() as db:
        admin = await db.get(User, integration_accounts["app_admin"])
        student_id = integration_accounts["student"]
        student = await db.get(User, student_id)
        initial_value = Gender(case["from"]) if case["field"] == "sex" else case["from"]
        setattr(student.profile, case["field"], initial_value)
        await db.commit()

        scheme_service = SchemeService(SchemeRepository(db), VaccineRepository(db))
        audit = AuditService(db)
        catalog = VaccineCatalogService(db, scheme_service, audit)
        vaccine = await catalog.create_vaccine(
            admin,
            VaccineCreateRequest(
                name="Synthetic PostgreSQL rehearsal",
                code=f"T02_PG_{case['id'].replace('-', '_').upper()}",
                applies_to="all",
                dose_configs=[
                    VaccineDoseConfigInput(dose_number=1, label="Synthetic applied dose"),
                    VaccineDoseConfigInput(
                        dose_number=2,
                        label="Synthetic titer",
                        is_required=False,
                        dose_type=DoseType.TITER,
                    ),
                ],
            ),
        )
        assignment = await db.scalar(
            select(StudentVaccine).where(
                StudentVaccine.user_id == student_id,
                StudentVaccine.vaccine_id == vaccine.id,
            )
        )
        doses = list(
            (
                await db.scalars(
                    select(StudentVaccineDose)
                    .where(StudentVaccineDose.student_vaccine_id == assignment.id)
                    .order_by(StudentVaccineDose.dose_number)
                )
            ).all()
        )
        reviewed_at = datetime(2025, 3, 2, 10, 0, tzinfo=timezone.utc)
        doses[0].status = DoseStatus.APPROVED
        doses[0].applied_date = date(2025, 3, 1)
        doses[0].admin_notes = "synthetic reviewed dose"
        doses[0].reviewed_by = admin.id
        doses[0].reviewed_at = reviewed_at
        doses[1].status = DoseStatus.APPROVED
        doses[1].titer_value = "synthetic-titer-value"
        doses[1].reviewed_by = admin.id
        doses[1].reviewed_at = reviewed_at
        await db.commit()

        baseline = await scheme_service.append_scheme_version(
            student_id,
            "synthetic:t02:baseline",
        )
        await db.commit()
        old_snapshot = baseline.snapshot
        service = StudentAdminService(
            db,
            UserRepository(db),
            scheme_service,
            audit,
            NotificationService(NotificationRepository(db)),
        )
        await service.update_student_profile(
            admin,
            student_id,
            UpdateStudentProfileRequest(**{case["field"]: case["to"]}),
        )

        versions_after = list(
            (
                await db.scalars(
                    select(StudentSchemeVersion)
                    .where(StudentSchemeVersion.user_id == student_id)
                    .order_by(StudentSchemeVersion.version_number)
                )
            ).all()
        )
        assert versions_after[-2].reason == "profile:reconciliation:before"
        assert versions_after[-1].reason == "profile:reconciliation:after"
        assert versions_after[-2].snapshot == old_snapshot
        before_v2, after_v2 = versions_after[-2].snapshot, versions_after[-1].snapshot
        assert before_v2["profile"][case["field"]] == case["from"]
        assert after_v2["profile"][case["field"]] == case["to"]
        assert after_v2["vaccines"][0]["doses"] == before_v2["vaccines"][0]["doses"]

        active_config_ids = set(
            (
                await db.scalars(
                    select(VaccineDoseConfig.id).where(
                        VaccineDoseConfig.vaccine_id == vaccine.id,
                        VaccineDoseConfig.is_active.is_(True),
                    )
                )
            ).all()
        )
        assert {dose["config_id"] for dose in after_v2["vaccines"][0]["doses"]} == {
            str(config_id) for config_id in active_config_ids
        }


@pytest.mark.asyncio
async def test_postgres_catalog_change_keeps_old_snapshot_and_clinical_history(
    integration_engine,
    integration_accounts,
):
    if integration_engine.dialect.name != "postgresql":
        pytest.skip("T-02 PostgreSQL JSONB evidence requires a disposable PostgreSQL URL")

    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    async with sessions() as db:
        admin = await db.get(User, integration_accounts["app_admin"])
        student_id = integration_accounts["student"]
        scheme_service = SchemeService(SchemeRepository(db), VaccineRepository(db))
        catalog = VaccineCatalogService(db, scheme_service, AuditService(db))
        vaccine = await catalog.create_vaccine(
            admin,
            VaccineCreateRequest(
                name="Synthetic catalog version",
                code="T02_PG_CATALOG",
                applies_to="all",
                dose_configs=[
                    VaccineDoseConfigInput(dose_number=1, label="Original dose"),
                    VaccineDoseConfigInput(
                        dose_number=2,
                        label="Synthetic titer",
                        is_required=False,
                        dose_type=DoseType.TITER,
                    ),
                ],
            ),
        )
        assignment = await db.scalar(
            select(StudentVaccine).where(
                StudentVaccine.user_id == student_id,
                StudentVaccine.vaccine_id == vaccine.id,
            )
        )
        doses = list(
            (
                await db.scalars(
                    select(StudentVaccineDose)
                    .where(StudentVaccineDose.student_vaccine_id == assignment.id)
                    .order_by(StudentVaccineDose.dose_number)
                )
            ).all()
        )
        reviewed_at = datetime(2025, 5, 6, 12, 30, tzinfo=timezone.utc)
        doses[0].status = DoseStatus.APPROVED
        doses[0].applied_date = date(2025, 5, 5)
        doses[0].reviewed_by = admin.id
        doses[0].reviewed_at = reviewed_at
        doses[1].status = DoseStatus.APPROVED
        doses[1].titer_value = "synthetic-positive"
        doses[1].reviewed_by = admin.id
        doses[1].reviewed_at = reviewed_at
        await db.commit()

        baseline = await scheme_service.append_scheme_version(
            student_id,
            "synthetic:t02:catalog:baseline",
        )
        await db.commit()
        baseline_id = baseline.id
        original_snapshot = baseline.snapshot

        await catalog.update_vaccine(
            admin,
            vaccine.id,
            VaccineUpdateRequest(
                name="Synthetic catalog version updated",
                dose_configs=[
                    VaccineDoseConfigInput(dose_number=1, label="Updated dose"),
                    VaccineDoseConfigInput(
                        dose_number=2,
                        label="Synthetic titer",
                        is_required=False,
                        dose_type=DoseType.TITER,
                    ),
                    VaccineDoseConfigInput(dose_number=3, label="New dose"),
                ],
            ),
        )

        historical = await db.get(StudentSchemeVersion, baseline_id)
        versions = list(
            (
                await db.scalars(
                    select(StudentSchemeVersion)
                    .where(StudentSchemeVersion.user_id == student_id)
                    .order_by(StudentSchemeVersion.version_number)
                )
            ).all()
        )
        assert historical.snapshot == original_snapshot
        assert [version.reason for version in versions[-2:]] == [
            "catalog:update:before",
            "catalog:update:after",
        ]
        before_v2, after_v2 = (version.snapshot["vaccines"][0] for version in versions[-2:])
        assert before_v2["doses"][0]["label"] == "Original dose"
        assert after_v2["doses"][0]["label"] == "Updated dose"
        assert len(after_v2["doses"]) == 3
        assert after_v2["doses"][0]["status"] == DoseStatus.APPROVED.value
        assert after_v2["doses"][0]["applied_date"] == "2025-05-05"
        assert after_v2["doses"][0]["reviewed_by"] == str(admin.id)
        assert after_v2["doses"][0]["reviewed_at"] == reviewed_at.isoformat()
        assert after_v2["doses"][1]["status"] == DoseStatus.APPROVED.value
        assert after_v2["doses"][1]["titer_value"] == "synthetic-positive"
        assert after_v2["doses"][1]["reviewed_by"] == str(admin.id)
        assert after_v2["doses"][1]["reviewed_at"] == reviewed_at.isoformat()

        active_config_ids = set(
            (
                await db.scalars(
                    select(VaccineDoseConfig.id).where(
                        VaccineDoseConfig.vaccine_id == vaccine.id,
                        VaccineDoseConfig.is_active.is_(True),
                    )
                )
            ).all()
        )
        assert {dose["config_id"] for dose in after_v2["doses"]} == {
            str(config_id) for config_id in active_config_ids
        }


@pytest.mark.asyncio
async def test_postgres_rule_change_appends_version_without_rewriting_history(
    integration_engine,
    integration_accounts,
    monkeypatch,
):
    if integration_engine.dialect.name != "postgresql":
        pytest.skip("T-02 PostgreSQL JSONB evidence requires a disposable PostgreSQL URL")

    from app.db import seed

    sessions = async_sessionmaker(integration_engine, expire_on_commit=False)
    async with sessions() as db:
        admin = await db.get(User, integration_accounts["app_admin"])
        student_id = integration_accounts["student"]
        scheme_service = SchemeService(SchemeRepository(db), VaccineRepository(db))
        catalog = VaccineCatalogService(db, scheme_service, AuditService(db))
        vaccine = await catalog.create_vaccine(
            admin,
            VaccineCreateRequest(
                name="Synthetic rule version",
                code="T02_PG_RULE",
                applies_to="all",
                dose_configs=[VaccineDoseConfigInput(dose_number=1, label="Dose")],
            ),
        )
        old_rule = VaccineRule(
            vaccine_id=vaccine.id,
            rule_type="schedule",
            rule_config={"intervals": [{"from_dose": 1, "to_dose": 2, "months": 1}]},
            description="Synthetic original rule",
        )
        db.add(old_rule)
        await db.commit()
        db.expire(vaccine, ["rules"])
        baseline = await scheme_service.append_scheme_version(
            student_id,
            "synthetic:t02:rule:baseline",
        )
        await db.commit()
        baseline_id = baseline.id
        original_snapshot = baseline.snapshot

        monkeypatch.setattr(
            seed,
            "_build_vaccine_catalog",
            lambda: [
                {
                    "code": "T02_PG_RULE",
                    "rules": [
                        {
                            "rule_type": "schedule",
                            "rule_config": {
                                "intervals": [{"from_dose": 1, "to_dose": 2, "months": 2}]
                            },
                            "description": "Synthetic updated rule",
                        }
                    ],
                }
            ],
        )
        await seed.sync_vaccine_schedule_rules(db)

        historical = await db.get(StudentSchemeVersion, baseline_id)
        versions = list(
            (
                await db.scalars(
                    select(StudentSchemeVersion)
                    .where(StudentSchemeVersion.user_id == student_id)
                    .order_by(StudentSchemeVersion.version_number)
                )
            ).all()
        )
        assert historical.snapshot == original_snapshot
        assert [version.reason for version in versions[-2:]] == [
            "catalog:rules:before",
            "catalog:rules:after",
        ]
        assert versions[-2].snapshot["vaccines"][0]["rules"][0]["rule_config"] == {
            "intervals": [{"from_dose": 1, "to_dose": 2, "months": 1}]
        }
        assert versions[-1].snapshot["vaccines"][0]["rules"][0]["rule_config"] == {
            "intervals": [{"from_dose": 1, "to_dose": 2, "months": 2}]
        }
        await db.refresh(old_rule)
        assert old_rule.is_active is False
        active_rules = list(
            (
                await db.scalars(
                    select(VaccineRule).where(
                        VaccineRule.vaccine_id == vaccine.id,
                        VaccineRule.rule_type == "schedule",
                        VaccineRule.is_active.is_(True),
                    )
                )
            ).all()
        )
        assert len(active_rules) == 1
        assert active_rules[0].rule_config == {
            "intervals": [{"from_dose": 1, "to_dose": 2, "months": 2}]
        }
