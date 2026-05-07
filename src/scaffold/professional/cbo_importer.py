from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.constants.schema_enums import ProfessionalEntityType
from scaffold.models.professional.professional_entities import ProfessionalEntity
from scaffold.models.professional.professional_entity_aliases import ProfessionalEntityAlias
from scaffold.models.professional.professional_entity_hierarchy_relations import (
    ProfessionalEntityHierarchyRelation,
)
from scaffold.models.professional.professional_entity_relations import ProfessionalEntityRelation
from scaffold.models.professional.professional_entity_sources import ProfessionalEntitySource
from scaffold.professional.normalization import normalize_text

_BASE_LEVELS: tuple[tuple[str, str, ProfessionalEntityType], ...] = (
    ("CBO2002 - Grande Grupo.csv", "grande_grupo", ProfessionalEntityType.DOMAIN),
    ("CBO2002 - SubGrupo Principal.csv", "subgrupo_principal", ProfessionalEntityType.DOMAIN),
    ("CBO2002 - SubGrupo.csv", "subgrupo", ProfessionalEntityType.DOMAIN),
    ("CBO2002 - Familia.csv", "familia", ProfessionalEntityType.DOMAIN),
    ("CBO2002 - Ocupacao.csv", "ocupacao", ProfessionalEntityType.OCCUPATION),
)


def clean_label(text: str) -> str:
    return " ".join(text.strip().split())


def make_cbo_external_id(kind: str, raw_identifier: str) -> str:
    value = clean_label(raw_identifier)
    if not value:
        raise ValueError("raw_identifier must not be empty")
    if kind in {"grande_area", "atividade"}:
        digest = hashlib.sha1(normalize_text(value).encode("utf-8")).hexdigest()
        return f"{kind}:{digest}"
    return f"{kind}:{value}"


def profile_area_relation_type() -> str:
    return "cbo_area"


def profile_activity_relation_type() -> str:
    return "cbo_activity"


def entity_type_key(entity_type: ProfessionalEntityType | str) -> str:
    if isinstance(entity_type, ProfessionalEntityType):
        return entity_type.value
    return str(entity_type)


class CboImporter:
    BATCH_SIZE = 500

    def __init__(self, session: AsyncSession, dataset_dir: Path, source: str = "cbo") -> None:
        self._session = session
        self._dataset_dir = dataset_dir
        self._source = source
        self._identity_to_id: dict[tuple[str, str, str], int] = {}
        self._external_to_id: dict[str, int] = {}
        self._code_to_id: dict[str, int] = {}
        self._stats: dict[str, int] = {
            "entities": 0,
            "aliases": 0,
            "sources": 0,
            "relations": 0,
            "hierarchy_relations": 0,
            "collections": 0,
            "memberships": 0,
            "skipped": 0,
        }

    async def run(self) -> dict[str, int]:
        await self._prime_caches()
        await self._load_base_entities()
        await self._load_occupation_aliases()
        await self._load_profile_entities_and_relations()
        return self._stats

    async def _prime_caches(self) -> None:
        result = await self._session.execute(
            select(
                ProfessionalEntity.id,
                ProfessionalEntity.entity_type,
                ProfessionalEntity.normalized_name,
                ProfessionalEntity.language,
            )
        )
        for entity_id, entity_type, normalized_name, language in result:
            if language is None:
                continue
            self._identity_to_id[(entity_type_key(entity_type), normalized_name, language)] = entity_id

        result = await self._session.execute(
            select(
                ProfessionalEntitySource.external_source_id,
                ProfessionalEntitySource.entity_id,
            ).where(ProfessionalEntitySource.source == self._source)
        )
        for external_source_id, entity_id in result:
            if external_source_id:
                self._external_to_id[external_source_id] = entity_id

    def _read_csv(self, filename: str) -> Iterator[dict[str, str]]:
        path = self._dataset_dir / filename
        with open(path, newline="", encoding="latin-1") as handle:
            yield from csv.DictReader(handle, delimiter=";")

    async def _insert_ignore(self, model: type, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        stmt = mysql_insert(model.__table__).prefix_with("IGNORE").values(rows)
        result = await self._session.execute(stmt)
        return result.rowcount

    async def _ensure_entity(
        self,
        *,
        entity_type: ProfessionalEntityType,
        canonical_name: str,
        language: str,
        external_source_id: str,
        external_source_uri: str,
        source_label: str | None,
        metadata: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> int:
        if external_source_id in self._external_to_id:
            return self._external_to_id[external_source_id]

        normalized_name = normalize_text(canonical_name)
        identity = (entity_type_key(entity_type), normalized_name, language)
        entity_id = self._identity_to_id.get(identity)

        if entity_id is None:
            existing = await self._session.execute(
                select(ProfessionalEntity.id).where(
                    ProfessionalEntity.entity_type == entity_type,
                    ProfessionalEntity.normalized_name == normalized_name,
                    ProfessionalEntity.language == language,
                ).limit(1)
            )
            entity_id = existing.scalar_one_or_none()

        if entity_id is None:
            entity = ProfessionalEntity(
                entity_type=entity_type,
                canonical_name=canonical_name,
                normalized_name=normalized_name,
                language=language,
                description=description,
                entity_metadata=metadata,
                active=True,
            )
            self._session.add(entity)
            await self._session.flush()
            entity_id = entity.id
            self._stats["entities"] += 1

        self._identity_to_id[identity] = entity_id

        rows = [{
            "entity_id": entity_id,
            "source": self._source,
            "external_source_id": external_source_id,
            "external_source_uri": external_source_uri,
            "source_label": source_label,
            "metadata": metadata,
        }]
        self._stats["sources"] += await self._insert_ignore(ProfessionalEntitySource, rows)
        self._external_to_id[external_source_id] = entity_id
        return entity_id

    async def _load_base_entities(self) -> None:
        hierarchy_batch: list[dict[str, Any]] = []

        for filename, level, entity_type in _BASE_LEVELS:
            reader = self._read_csv(filename)
            for row in reader:
                code = clean_label(row.get("CODIGO", ""))
                title = clean_label(row.get("TITULO", ""))
                if not code or not title:
                    self._stats["skipped"] += 1
                    continue

                external_id = make_cbo_external_id(level, code)
                entity_id = await self._ensure_entity(
                    entity_type=entity_type,
                    canonical_name=title,
                    language="pt",
                    external_source_id=external_id,
                    external_source_uri=f"cbo2002://{level}/{code}",
                    source_label=title,
                    metadata={"cbo_level": level, "cbo_code": code},
                )
                self._code_to_id[external_id] = entity_id

                parent_external_id: str | None = None
                if level == "subgrupo_principal":
                    parent_external_id = make_cbo_external_id("grande_grupo", code[:1])
                elif level == "subgrupo":
                    parent_external_id = make_cbo_external_id("subgrupo_principal", code[:2])
                elif level == "familia":
                    parent_external_id = make_cbo_external_id("subgrupo", code[:3])
                elif level == "ocupacao":
                    parent_external_id = make_cbo_external_id("familia", code[:4])

                if parent_external_id is not None:
                    parent_id = self._code_to_id.get(parent_external_id)
                    if parent_id is None:
                        self._stats["skipped"] += 1
                    else:
                        hierarchy_batch.append({
                            "child_entity_id": entity_id,
                            "parent_entity_id": parent_id,
                            "relation_type": "broader",
                            "depth": 1,
                            "source": self._source,
                        })

                        if len(hierarchy_batch) >= self.BATCH_SIZE:
                            self._stats["hierarchy_relations"] += await self._insert_ignore(
                                ProfessionalEntityHierarchyRelation,
                                hierarchy_batch,
                            )
                            hierarchy_batch = []

        if hierarchy_batch:
            self._stats["hierarchy_relations"] += await self._insert_ignore(
                ProfessionalEntityHierarchyRelation,
                hierarchy_batch,
            )

        await self._session.commit()

    async def _load_occupation_aliases(self) -> None:
        batch: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()

        reader = self._read_csv("CBO2002 - Sinonimo.csv")
        for row in reader:
            code = clean_label(row.get("CODIGO", ""))
            alias = clean_label(row.get("TITULO", ""))
            if not code or not alias:
                self._stats["skipped"] += 1
                continue

            entity_id = self._code_to_id.get(make_cbo_external_id("ocupacao", code))
            if entity_id is None:
                self._stats["skipped"] += 1
                continue

            normalized_alias = normalize_text(alias)
            key = (entity_id, normalized_alias)
            if key in seen:
                continue
            seen.add(key)

            batch.append({
                "entity_id": entity_id,
                "alias": alias,
                "normalized_alias": normalized_alias,
                "language": "pt",
                "source": self._source,
            })

            if len(batch) >= self.BATCH_SIZE:
                self._stats["aliases"] += await self._insert_ignore(ProfessionalEntityAlias, batch)
                batch = []

        if batch:
            self._stats["aliases"] += await self._insert_ignore(ProfessionalEntityAlias, batch)

        await self._session.commit()

    async def _load_profile_entities_and_relations(self) -> None:
        hierarchy_batch: list[dict[str, Any]] = []
        relation_batch: list[dict[str, Any]] = []

        reader = self._read_csv("CBO2002 - PerfilOcupacional.csv")
        for row in reader:
            occupation_code = clean_label(row.get("COD_OCUPACAO", ""))
            area_label = clean_label(row.get("NOME_GRANDE_AREA", ""))
            area_code = clean_label(row.get("SGL_GRANDE_AREA", ""))
            activity_label = clean_label(row.get("NOME_ATIVIDADE", ""))
            activity_code = clean_label(row.get("COD_ATIVIDADE", ""))

            if not occupation_code or not area_label or not activity_label:
                self._stats["skipped"] += 1
                continue

            occupation_id = self._code_to_id.get(make_cbo_external_id("ocupacao", occupation_code))
            if occupation_id is None:
                self._stats["skipped"] += 1
                continue

            area_id = await self._ensure_entity(
                entity_type=ProfessionalEntityType.DOMAIN,
                canonical_name=area_label,
                language="pt",
                external_source_id=make_cbo_external_id("grande_area", area_label),
                external_source_uri=f"cbo2002://grande_area/{hashlib.sha1(normalize_text(area_label).encode('utf-8')).hexdigest()}",
                source_label=area_label,
                metadata={"cbo_level": "grande_area", "cbo_area_code": area_code},
            )
            activity_id = await self._ensure_entity(
                entity_type=ProfessionalEntityType.SKILL,
                canonical_name=activity_label,
                language="pt",
                external_source_id=make_cbo_external_id("atividade", activity_label),
                external_source_uri=f"cbo2002://atividade/{hashlib.sha1(normalize_text(activity_label).encode('utf-8')).hexdigest()}",
                source_label=activity_label,
                metadata={"cbo_level": "atividade", "cbo_activity_code": activity_code},
            )

            hierarchy_batch.append({
                "child_entity_id": activity_id,
                "parent_entity_id": area_id,
                "relation_type": "broader",
                "depth": 1,
                "source": self._source,
            })
            relation_batch.append({
                "source_entity_id": occupation_id,
                "target_entity_id": area_id,
                "relation_type": profile_area_relation_type(),
                "source": self._source,
                "metadata": {
                    "cbo_occupation_code": occupation_code,
                    "cbo_area_code": area_code,
                },
            })
            relation_batch.append({
                "source_entity_id": occupation_id,
                "target_entity_id": activity_id,
                "relation_type": profile_activity_relation_type(),
                "source": self._source,
                "metadata": {
                    "cbo_occupation_code": occupation_code,
                    "cbo_area_code": area_code,
                    "cbo_activity_code": activity_code,
                },
            })

            if len(hierarchy_batch) >= self.BATCH_SIZE:
                self._stats["hierarchy_relations"] += await self._insert_ignore(
                    ProfessionalEntityHierarchyRelation,
                    hierarchy_batch,
                )
                hierarchy_batch = []

            if len(relation_batch) >= self.BATCH_SIZE:
                self._stats["relations"] += await self._insert_ignore(
                    ProfessionalEntityRelation,
                    relation_batch,
                )
                relation_batch = []

        if hierarchy_batch:
            self._stats["hierarchy_relations"] += await self._insert_ignore(
                ProfessionalEntityHierarchyRelation,
                hierarchy_batch,
            )
        if relation_batch:
            self._stats["relations"] += await self._insert_ignore(
                ProfessionalEntityRelation,
                relation_batch,
            )

        await self._session.commit()
