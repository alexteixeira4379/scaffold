from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.professional.professional_collection_memberships import ProfessionalCollectionMembership
from scaffold.models.professional.professional_collections import ProfessionalCollection
from scaffold.models.professional.professional_entities import ProfessionalEntity
from scaffold.models.professional.professional_entity_aliases import ProfessionalEntityAlias
from scaffold.models.professional.professional_entity_hierarchy_relations import ProfessionalEntityHierarchyRelation
from scaffold.models.professional.professional_entity_relations import ProfessionalEntityRelation
from scaffold.models.professional.professional_entity_sources import ProfessionalEntitySource
from scaffold.professional.normalization import deduplicate_normalized, normalize_text, split_alias_field

# CSV file → canonical entity_type mapping
ENTITY_CSVS: list[tuple[str, str]] = [
    ("skills_pt.csv", "skill"),
    ("occupations_pt.csv", "occupation"),
    ("skillGroups_pt.csv", "domain"),
    ("ISCOGroups_pt.csv", "domain"),
]

# Metadata keys to extract per CSV file
_META_KEYS: dict[str, tuple[str, ...]] = {
    "skills_pt.csv": ("conceptType", "skillType", "reuseLevel", "modifiedDate", "inScheme"),
    "occupations_pt.csv": ("conceptType", "iscoGroup", "regulatedProfessionNote", "modifiedDate", "code", "naceCode", "inScheme"),
    "skillGroups_pt.csv": ("conceptType", "code", "inScheme", "modifiedDate"),
    "ISCOGroups_pt.csv": ("conceptType", "code", "inScheme"),
}

# slug → (csv_filename, human_label)
COLLECTION_MAP: dict[str, tuple[str, str]] = {
    "digital_skills": ("digitalSkillsCollection_pt.csv", "Competências Digitais"),
    "digcomp_skills": ("digCompSkillsCollection_pt.csv", "Competências DigComp"),
    "green_skills": ("greenSkillsCollection_pt.csv", "Competências Verdes"),
    "language_skills": ("languageSkillsCollection_pt.csv", "Competências Linguísticas"),
    "research_skills": ("researchSkillsCollection_pt.csv", "Competências de Investigação"),
    "transversal_skills": ("transversalSkillsCollection_pt.csv", "Competências Transversais"),
    "research_occupations": ("researchOccupationsCollection_pt.csv", "Ocupações de Investigação"),
}


def csv_to_entity_type(csv_filename: str) -> str:
    """Return canonical entity_type for a given CSV filename."""
    for fname, etype in ENTITY_CSVS:
        if fname == csv_filename:
            return etype
    raise ValueError(f"Unknown CSV file: {csv_filename}")


def map_occ_skill_relation_type(relation_type: str) -> str:
    """Map ESCO occupationSkillRelations relationType to canonical relation_type."""
    if relation_type.lower() == "essential":
        return "essential_skill"
    return "optional_skill"


def map_skill_skill_relation_type(relation_type: str) -> str:
    """Map ESCO skillSkillRelations relationType to canonical relation_type."""
    if relation_type.lower() == "essential":
        return "essential_related_skill"
    return "optional_related_skill"


def _pick_description(row: dict[str, str]) -> str | None:
    for field in ("description", "definition", "scopeNote"):
        val = row.get(field, "").strip()
        if val:
            return val
    return None


def _build_metadata(row: dict[str, str], csv_file: str) -> dict[str, Any] | None:
    keys = _META_KEYS.get(csv_file, ())
    meta = {k: v for k in keys if (v := row.get(k, "").strip())}
    return meta or None


class EscoImporter:
    BATCH_SIZE = 500

    def __init__(self, session: AsyncSession, dataset_dir: Path, source: str = "esco") -> None:
        self._session = session
        self._dataset_dir = dataset_dir
        self._source = source
        self._uri_to_id: dict[str, int] = {}
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

    async def run(self, reset: bool = True) -> dict[str, int]:
        if reset:
            await self._reset()
        await self._load_entities()
        await self._load_aliases()
        await self._load_sources()
        await self._load_collections()
        await self._load_relations()
        await self._load_hierarchy()
        await self._load_memberships()
        return self._stats

    async def _reset(self) -> None:
        for model in [
            ProfessionalCollectionMembership,
            ProfessionalCollection,
            ProfessionalEntityHierarchyRelation,
            ProfessionalEntityRelation,
            ProfessionalEntitySource,
            ProfessionalEntityAlias,
            ProfessionalEntity,
        ]:
            await self._session.execute(delete(model))
        await self._session.commit()

    def _read_csv(self, filename: str) -> Iterator[dict[str, str]]:
        path = self._dataset_dir / filename
        with open(path, newline="", encoding="utf-8") as f:
            yield from csv.DictReader(f)

    async def _insert_ignore(self, model: type, rows: list[dict]) -> int:
        """Bulk INSERT IGNORE — silently skips rows that violate unique constraints."""
        if not rows:
            return 0
        stmt = mysql_insert(model.__table__).prefix_with("IGNORE").values(rows)
        result = await self._session.execute(stmt)
        return result.rowcount

    async def _flush_entities(self, batch: list[ProfessionalEntity], uri_batch: list[str]) -> None:
        self._session.add_all(batch)
        await self._session.flush()
        for entity, uri in zip(batch, uri_batch):
            self._uri_to_id[uri] = entity.id
        self._stats["entities"] += len(batch)

    async def _load_entities(self) -> None:
        batch: list[ProfessionalEntity] = []
        uri_batch: list[str] = []
        # Guard against duplicate (entity_type, normalized_name, language) within the CSV set
        seen_identities: set[tuple[str, str, str]] = set()

        for csv_file, entity_type in ENTITY_CSVS:
            for row in self._read_csv(csv_file):
                uri = row.get("conceptUri", "").strip()
                label = row.get("preferredLabel", "").strip()
                if not uri or not label or uri in self._uri_to_id:
                    continue

                normalized = normalize_text(label)
                identity = (entity_type, normalized, "pt")
                if identity in seen_identities:
                    self._stats["skipped"] += 1
                    continue
                seen_identities.add(identity)

                entity = ProfessionalEntity(
                    entity_type=entity_type,
                    canonical_name=label,
                    normalized_name=normalized,
                    language="pt",
                    description=_pick_description(row),
                    entity_metadata=_build_metadata(row, csv_file),
                    active=True,
                )
                batch.append(entity)
                uri_batch.append(uri)

                if len(batch) >= self.BATCH_SIZE:
                    await self._flush_entities(batch, uri_batch)
                    batch = []
                    uri_batch = []

        if batch:
            await self._flush_entities(batch, uri_batch)

        await self._session.commit()

    async def _load_aliases(self) -> None:
        batch: list[dict] = []
        seen: set[tuple[int, str]] = set()

        for csv_file, _ in ENTITY_CSVS:
            for row in self._read_csv(csv_file):
                uri = row.get("conceptUri", "").strip()
                entity_id = self._uri_to_id.get(uri)
                if entity_id is None:
                    continue

                canonical_normalized = normalize_text(row.get("preferredLabel", ""))
                raw_texts: list[str] = []
                for field in ("altLabels", "hiddenLabels"):
                    raw = row.get(field, "")
                    if raw:
                        raw_texts.extend(split_alias_field(raw))

                for alias_text in deduplicate_normalized(raw_texts):
                    normalized = normalize_text(alias_text)
                    if not normalized or normalized == canonical_normalized:
                        continue
                    key = (entity_id, normalized)
                    if key in seen:
                        continue
                    seen.add(key)

                    batch.append({
                        "entity_id": entity_id,
                        "alias": alias_text,
                        "normalized_alias": normalized,
                        "language": "pt",
                        "source": self._source,
                    })

                    if len(batch) >= self.BATCH_SIZE:
                        self._stats["aliases"] += await self._insert_ignore(ProfessionalEntityAlias, batch)
                        batch = []

        if batch:
            self._stats["aliases"] += await self._insert_ignore(ProfessionalEntityAlias, batch)

        await self._session.commit()

    async def _load_sources(self) -> None:
        batch: list[dict] = []

        for csv_file, _ in ENTITY_CSVS:
            for row in self._read_csv(csv_file):
                uri = row.get("conceptUri", "").strip()
                entity_id = self._uri_to_id.get(uri)
                if entity_id is None:
                    continue

                batch.append({
                    "entity_id": entity_id,
                    "source": self._source,
                    "external_source_id": uri,
                    "external_source_uri": uri,
                    "source_label": row.get("preferredLabel", "").strip() or None,
                })

                if len(batch) >= self.BATCH_SIZE:
                    self._stats["sources"] += await self._insert_ignore(ProfessionalEntitySource, batch)
                    batch = []

        if batch:
            self._stats["sources"] += await self._insert_ignore(ProfessionalEntitySource, batch)

        await self._session.commit()

    async def _load_collections(self) -> None:
        for slug, (_, label) in COLLECTION_MAP.items():
            col = ProfessionalCollection(slug=slug, label=label)
            self._session.add(col)

        await self._session.flush()
        self._stats["collections"] += len(COLLECTION_MAP)
        await self._session.commit()

    async def _load_relations(self) -> None:
        batch: list[dict] = []

        # occupation → skill relations
        for row in self._read_csv("occupationSkillRelations_pt.csv"):
            occ_uri = row.get("occupationUri", "").strip()
            skill_uri = row.get("skillUri", "").strip()
            occ_id = self._uri_to_id.get(occ_uri)
            skill_id = self._uri_to_id.get(skill_uri)

            if occ_id is None or skill_id is None:
                self._stats["skipped"] += 1
                continue

            relation_type = map_occ_skill_relation_type(row.get("relationType", ""))
            batch.append({
                "source_entity_id": occ_id,
                "target_entity_id": skill_id,
                "relation_type": relation_type,
                "source": self._source,
                "metadata": {
                    "raw_relation_type": row.get("relationType", ""),
                    "raw_skill_type": row.get("skillType", ""),
                },
            })

            if len(batch) >= self.BATCH_SIZE:
                self._stats["relations"] += await self._insert_ignore(ProfessionalEntityRelation, batch)
                batch = []

        # skill → skill relations
        for row in self._read_csv("skillSkillRelations_pt.csv"):
            original_uri = row.get("originalSkillUri", "").strip()
            related_uri = row.get("relatedSkillUri", "").strip()
            src_id = self._uri_to_id.get(original_uri)
            tgt_id = self._uri_to_id.get(related_uri)

            if src_id is None or tgt_id is None:
                self._stats["skipped"] += 1
                continue

            relation_type = map_skill_skill_relation_type(row.get("relationType", ""))
            batch.append({
                "source_entity_id": src_id,
                "target_entity_id": tgt_id,
                "relation_type": relation_type,
                "source": self._source,
                "metadata": {
                    "raw_relation_type": row.get("relationType", ""),
                    "raw_original_skill_type": row.get("originalSkillType", ""),
                    "raw_related_skill_type": row.get("relatedSkillType", ""),
                },
            })

            if len(batch) >= self.BATCH_SIZE:
                self._stats["relations"] += await self._insert_ignore(ProfessionalEntityRelation, batch)
                batch = []

        if batch:
            self._stats["relations"] += await self._insert_ignore(ProfessionalEntityRelation, batch)

        await self._session.commit()

    async def _load_hierarchy(self) -> None:
        batch: list[dict] = []

        for csv_file in ("broaderRelationsOccPillar_pt.csv", "broaderRelationsSkillPillar_pt.csv"):
            for row in self._read_csv(csv_file):
                child_uri = row.get("conceptUri", "").strip()
                parent_uri = row.get("broaderUri", "").strip()
                child_id = self._uri_to_id.get(child_uri)
                parent_id = self._uri_to_id.get(parent_uri)

                if child_id is None or parent_id is None:
                    self._stats["skipped"] += 1
                    continue

                batch.append({
                    "child_entity_id": child_id,
                    "parent_entity_id": parent_id,
                    "relation_type": "broader",
                    "depth": 1,
                    "source": self._source,
                })

                if len(batch) >= self.BATCH_SIZE:
                    self._stats["hierarchy_relations"] += await self._insert_ignore(ProfessionalEntityHierarchyRelation, batch)
                    batch = []

        if batch:
            self._stats["hierarchy_relations"] += await self._insert_ignore(ProfessionalEntityHierarchyRelation, batch)

        await self._session.commit()

    async def _load_memberships(self) -> None:
        from sqlalchemy import select as sa_select

        # load collection_id by slug
        result = await self._session.execute(
            sa_select(ProfessionalCollection.slug, ProfessionalCollection.id)
        )
        slug_to_collection_id: dict[str, int] = {row[0]: row[1] for row in result}

        batch: list[dict] = []

        for slug, (csv_file, _) in COLLECTION_MAP.items():
            collection_id = slug_to_collection_id.get(slug)
            if collection_id is None:
                continue

            for row in self._read_csv(csv_file):
                uri = row.get("conceptUri", "").strip()
                entity_id = self._uri_to_id.get(uri)
                if entity_id is None:
                    self._stats["skipped"] += 1
                    continue

                batch.append({"collection_id": collection_id, "entity_id": entity_id})

                if len(batch) >= self.BATCH_SIZE:
                    self._stats["memberships"] += await self._insert_ignore(ProfessionalCollectionMembership, batch)
                    batch = []

        if batch:
            self._stats["memberships"] += await self._insert_ignore(ProfessionalCollectionMembership, batch)

        await self._session.commit()
