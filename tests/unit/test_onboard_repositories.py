from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import TypeAdapter
from sqlalchemy.dialects import mysql

from scaffold.constants.schema_enums import OnboardPhase, OnboardStepLayoutKind
from scaffold.models.onboard.onboard_steps import OnboardStep
from scaffold.repositories.onboard_repositories import OnboardStepRepository
from scaffold.whatsapp import LayoutBlock

# --- Model / table structure --------------------------------------------------


def test_onboard_step_tablename_is_onboard_steps() -> None:
    assert OnboardStep.__tablename__ == "onboard_steps"


def test_onboard_step_expected_columns_exist() -> None:
    expected = {
        "id",
        "phase",
        "step_key",
        "step_order",
        "prompt_text",
        "layout_kind",
        "layout_spec",
        "accepted_answers",
        "answer_format",
        "active",
        "created_at",
        "updated_at",
    }

    actual = set(OnboardStep.__table__.columns.keys())

    assert expected == actual


def test_onboard_step_step_key_has_unique_constraint() -> None:
    from sqlalchemy import UniqueConstraint

    unique_over_step_key = [
        constraint
        for constraint in OnboardStep.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and [c.name for c in constraint.columns] == ["step_key"]
    ]
    unique_indexes_over_step_key = [
        index
        for index in OnboardStep.__table__.indexes
        if index.unique and [c.name for c in index.columns] == ["step_key"]
    ]

    assert len(unique_over_step_key) + len(unique_indexes_over_step_key) >= 1


# --- Repository query compilation (mocked AsyncSession) -----------------------


async def test_get_by_step_key_targets_onboard_steps_and_filters_step_key() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    session.execute.return_value = result

    repository = OnboardStepRepository()
    await repository.get_by_step_key(session, "select_plan")

    compiled = str(session.execute.await_args.args[0].compile(dialect=mysql.dialect()))
    assert "FROM onboard_steps" in compiled
    assert "onboard_steps.step_key" in compiled


async def test_list_by_phase_filters_phase_and_active_ordered_by_step_order_then_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    repository = OnboardStepRepository()
    await repository.list_by_phase(session, OnboardPhase.SELECT_PLAN)

    compiled = str(session.execute.await_args.args[0].compile(dialect=mysql.dialect()))
    assert "onboard_steps.phase" in compiled
    assert "onboard_steps.active" in compiled
    assert "ORDER BY onboard_steps.step_order, onboard_steps.id" in compiled


async def test_list_active_ordered_filters_active_ordered_by_step_order_then_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    repository = OnboardStepRepository()
    await repository.list_active_ordered(session)

    compiled = str(session.execute.await_args.args[0].compile(dialect=mysql.dialect()))
    assert "onboard_steps.active" in compiled
    assert "ORDER BY onboard_steps.step_order, onboard_steps.id" in compiled


# --- OnboardPhase enum ---------------------------------------------------------


def test_onboard_phase_has_exact_seven_members_in_order() -> None:
    assert [(m.name, m.value) for m in OnboardPhase] == [
        ("BASE_PROFILE", "base_profile"),
        ("SELECT_PLAN", "select_plan"),
        ("CONFIRM_JOBS", "confirm_jobs"),
        ("CREATE_RESUME", "create_resume"),
        ("FINISH_RESUME", "finish_resume"),
        ("GENERATE_CHECKOUT", "generate_checkout"),
        ("WAIT_ACTIVATION", "wait_activation"),
    ]


# --- Seed roteiro validity -----------------------------------------------------


def _load_seed_rows() -> list[dict[str, Any]]:
    """Load the 0024 migration module in isolation and capture the rows it would
    bulk-insert, without touching a real database or alembic runtime."""

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "core"
        / "versions"
        / "0024_onboard_steps.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_0024_onboard_steps", migration_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    captured: list[dict[str, Any]] = []

    def _capture_bulk_insert(_table: Any, rows: list[dict[str, Any]]) -> None:
        captured.extend(rows)

    module.op.f = lambda name: name  # type: ignore[attr-defined]
    module.op.create_table = MagicMock()  # type: ignore[attr-defined]
    module.op.bulk_insert = _capture_bulk_insert  # type: ignore[attr-defined]

    module.upgrade()
    return captured


@pytest.fixture(scope="module")
def seed_rows() -> list[dict[str, Any]]:
    return _load_seed_rows()


def test_seed_has_exactly_one_row_per_phase(seed_rows: list[dict[str, Any]]) -> None:
    phases = [row["phase"] for row in seed_rows]

    assert sorted(phases) == sorted(m.value for m in OnboardPhase)


def test_seed_step_order_is_strictly_ascending(seed_rows: list[dict[str, Any]]) -> None:
    orders = [row["step_order"] for row in seed_rows]

    assert all(earlier < later for earlier, later in zip(orders, orders[1:]))


def test_seed_step_keys_are_unique(seed_rows: list[dict[str, Any]]) -> None:
    step_keys = [row["step_key"] for row in seed_rows]

    assert len(set(step_keys)) == len(step_keys)


def test_seed_layout_specs_validate_and_render_against_wave1_contract(
    seed_rows: list[dict[str, Any]],
) -> None:
    adapter: TypeAdapter[Any] = TypeAdapter(LayoutBlock)

    rendered = []
    for row in seed_rows:
        block = {"kind": row["layout_kind"], **row["layout_spec"]}
        layout = adapter.validate_python(block)
        rendered.append(layout.render())

    assert len(rendered) == len(seed_rows)


def test_seed_every_rendered_layout_is_a_typed_cloud_api_fragment(
    seed_rows: list[dict[str, Any]],
) -> None:
    """Hardens criterion (e): validating is not enough, each layout must also
    render into a well-formed Cloud API fragment (a dict carrying a ``type``)."""

    adapter: TypeAdapter[Any] = TypeAdapter(LayoutBlock)

    for row in seed_rows:
        block = {"kind": row["layout_kind"], **row["layout_spec"]}
        rendered = adapter.validate_python(block).render()
        assert isinstance(rendered, dict) and isinstance(rendered.get("type"), str)


def test_seed_has_exactly_one_row_for_each_of_the_seven_phases(
    seed_rows: list[dict[str, Any]],
) -> None:
    """Reinforces criterion (d): the roteiro carries exactly one row per phase,
    i.e. exactly as many rows as there are OnboardPhase members (7)."""

    assert len(seed_rows) == len(list(OnboardPhase))


def test_seed_phase_values_are_valid_onboard_phase_members(
    seed_rows: list[dict[str, Any]],
) -> None:
    valid = {m.value for m in OnboardPhase}

    assert all(row["phase"] in valid for row in seed_rows)


def test_seed_layout_kind_values_are_valid_onboard_step_layout_kind_members(
    seed_rows: list[dict[str, Any]],
) -> None:
    valid = {m.value for m in OnboardStepLayoutKind}

    assert all(row["layout_kind"] in valid for row in seed_rows)
