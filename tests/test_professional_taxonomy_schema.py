from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from scaffold.models.job.job_professional_entities import JobProfessionalEntity
from scaffold.models.professional.professional_collection_memberships import ProfessionalCollectionMembership
from scaffold.models.professional.professional_collections import ProfessionalCollection
from scaffold.models.professional.professional_entities import ProfessionalEntity
from scaffold.models.professional.professional_entity_aliases import ProfessionalEntityAlias
from scaffold.models.professional.professional_entity_hierarchy_relations import ProfessionalEntityHierarchyRelation
from scaffold.models.professional.professional_entity_relations import ProfessionalEntityRelation
from scaffold.models.professional.professional_entity_sources import ProfessionalEntitySource


def _ddl(model) -> str:
    return str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))


def test_professional_entity_unique_constraint_covers_three_columns():
    uq_constraints = [
        c for c in ProfessionalEntity.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"entity_type", "normalized_name", "language"}


def test_professional_entity_ddl_contains_enum_values():
    ddl = _ddl(ProfessionalEntity)
    for value in ("skill", "occupation", "domain", "job_title"):
        assert value in ddl


def test_professional_entity_ddl_contains_indexes():
    ddl = _ddl(ProfessionalEntity)
    assert "normalized_name" in ddl
    assert "active" in ddl


def test_professional_entity_alias_unique_covers_four_columns():
    uq_constraints = [
        c for c in ProfessionalEntityAlias.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"entity_id", "normalized_alias", "language", "source"}


def test_professional_entity_sources_unique_on_source_and_external_id():
    uq_constraints = [
        c for c in ProfessionalEntitySource.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"source", "external_source_id"}


def test_professional_entity_relations_unique_covers_four_columns():
    uq_constraints = [
        c for c in ProfessionalEntityRelation.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"source_entity_id", "target_entity_id", "relation_type", "source"}


def test_professional_entity_relations_has_four_indexes():
    index_names = {i.name for i in ProfessionalEntityRelation.__table__.indexes}
    assert "ix_professional_entity_relations_source_entity" in index_names
    assert "ix_professional_entity_relations_target_entity" in index_names
    assert "ix_professional_entity_relations_type" in index_names
    assert "ix_professional_entity_relations_source" in index_names


def test_professional_entity_hierarchy_unique_covers_four_columns():
    uq_constraints = [
        c for c in ProfessionalEntityHierarchyRelation.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"child_entity_id", "parent_entity_id", "relation_type", "source"}


def test_professional_entity_hierarchy_has_four_indexes():
    index_names = {i.name for i in ProfessionalEntityHierarchyRelation.__table__.indexes}
    assert "ix_professional_entity_hierarchy_child" in index_names
    assert "ix_professional_entity_hierarchy_parent" in index_names
    assert "ix_professional_entity_hierarchy_type" in index_names
    assert "ix_professional_entity_hierarchy_source" in index_names


def test_professional_collections_unique_on_slug():
    uq_constraints = [
        c for c in ProfessionalCollection.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"slug"}


def test_professional_collection_memberships_unique_on_collection_and_entity():
    uq_constraints = [
        c for c in ProfessionalCollectionMembership.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"collection_id", "entity_id"}


def test_professional_entity_metadata_column_name_is_metadata():
    # Python attribute is entity_metadata but DB column must be named metadata
    col = ProfessionalEntity.__table__.c["metadata"]
    assert col.nullable is True


def test_professional_entity_relations_weight_is_nullable():
    col = ProfessionalEntityRelation.__table__.c["weight"]
    assert col.nullable is True


def test_professional_entity_active_has_server_default():
    col = ProfessionalEntity.__table__.c["active"]
    assert col.server_default is not None


def test_all_tables_have_bigint_pk():
    for model in [
        ProfessionalEntity,
        ProfessionalEntityAlias,
        ProfessionalEntitySource,
        ProfessionalEntityRelation,
        ProfessionalEntityHierarchyRelation,
        ProfessionalCollection,
        ProfessionalCollectionMembership,
        JobProfessionalEntity,
    ]:
        pk_col = model.__table__.c["id"]
        assert str(pk_col.type) == "BIGINT"


def test_job_professional_entities_has_expected_constraints_and_indexes():
    uq_constraints = [
        c for c in JobProfessionalEntity.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uq_constraints) == 1
    col_names = {c.name for c in uq_constraints[0].columns}
    assert col_names == {"job_id", "entity_id", "source_field"}

    fk_targets = {
        fk.column.table.name for fk in JobProfessionalEntity.__table__.foreign_keys
    }
    assert fk_targets == {"jobs", "professional_entities"}

    indexes = {index.name for index in JobProfessionalEntity.__table__.indexes}
    assert "ix_job_professional_entities_job_id" in indexes
    assert "ix_job_professional_entities_entity_id" in indexes
    assert "ix_job_professional_entities_job_id_source_field" in indexes


def test_job_professional_entities_ddl_contains_numeric_columns():
    ddl = _ddl(JobProfessionalEntity)
    assert "matched_text" in ddl
    assert "confidence NUMERIC(5, 4)" in ddl
    assert "weight NUMERIC(6, 2)" in ddl
