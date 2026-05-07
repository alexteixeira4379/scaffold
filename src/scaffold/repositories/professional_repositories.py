from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.professional.professional_collection_memberships import ProfessionalCollectionMembership
from scaffold.models.professional.professional_collections import ProfessionalCollection
from scaffold.models.professional.professional_entities import ProfessionalEntity
from scaffold.models.professional.professional_entity_aliases import ProfessionalEntityAlias
from scaffold.models.professional.professional_entity_hierarchy_relations import ProfessionalEntityHierarchyRelation
from scaffold.models.professional.professional_entity_relations import ProfessionalEntityRelation
from scaffold.models.professional.professional_entity_sources import ProfessionalEntitySource
from scaffold.repositories.base import AsyncRepository


class ProfessionalEntityRepository(AsyncRepository[ProfessionalEntity]):
    def __init__(self) -> None:
        super().__init__(ProfessionalEntity)

    async def get_by_identity(
        self,
        session: AsyncSession,
        entity_type: str,
        normalized_name: str,
        language: str | None,
    ) -> ProfessionalEntity | None:
        return await self.first_where(
            session,
            ProfessionalEntity.entity_type == entity_type,
            ProfessionalEntity.normalized_name == normalized_name,
            ProfessionalEntity.language == language,
        )

    async def list_by_entity_type(
        self,
        session: AsyncSession,
        entity_type: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalEntity]:
        return await self.list_where(
            session,
            ProfessionalEntity.entity_type == entity_type,
            order_by=(ProfessionalEntity.id,),
            limit=limit,
            offset=offset,
        )

    async def list_active_by_entity_type(
        self,
        session: AsyncSession,
        entity_type: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalEntity]:
        return await self.list_where(
            session,
            ProfessionalEntity.entity_type == entity_type,
            ProfessionalEntity.active == True,  # noqa: E712
            order_by=(ProfessionalEntity.id,),
            limit=limit,
            offset=offset,
        )


class ProfessionalEntityAliasRepository(AsyncRepository[ProfessionalEntityAlias]):
    def __init__(self) -> None:
        super().__init__(ProfessionalEntityAlias)

    async def list_by_entity_id(
        self,
        session: AsyncSession,
        entity_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalEntityAlias]:
        return await self.list_where(
            session,
            ProfessionalEntityAlias.entity_id == entity_id,
            order_by=(ProfessionalEntityAlias.id,),
            limit=limit,
            offset=offset,
        )

    async def list_by_normalized_alias(
        self,
        session: AsyncSession,
        normalized_alias: str,
        language: str | None = None,
    ) -> list[ProfessionalEntityAlias]:
        criteria = [ProfessionalEntityAlias.normalized_alias == normalized_alias]
        if language is not None:
            criteria.append(ProfessionalEntityAlias.language == language)
        return await self.list_where(session, *criteria, order_by=(ProfessionalEntityAlias.id,))


class ProfessionalEntitySourceRepository(AsyncRepository[ProfessionalEntitySource]):
    def __init__(self) -> None:
        super().__init__(ProfessionalEntitySource)

    async def get_by_source_external_id(
        self,
        session: AsyncSession,
        source: str,
        external_source_id: str,
    ) -> ProfessionalEntitySource | None:
        return await self.first_where(
            session,
            ProfessionalEntitySource.source == source,
            ProfessionalEntitySource.external_source_id == external_source_id,
        )

    async def list_by_entity_id(
        self,
        session: AsyncSession,
        entity_id: int,
    ) -> list[ProfessionalEntitySource]:
        return await self.list_where(
            session,
            ProfessionalEntitySource.entity_id == entity_id,
            order_by=(ProfessionalEntitySource.id,),
        )


class ProfessionalEntityRelationRepository(AsyncRepository[ProfessionalEntityRelation]):
    def __init__(self) -> None:
        super().__init__(ProfessionalEntityRelation)

    async def list_by_source_entity_id(
        self,
        session: AsyncSession,
        entity_id: int,
        relation_type: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalEntityRelation]:
        criteria = [ProfessionalEntityRelation.source_entity_id == entity_id]
        if relation_type is not None:
            criteria.append(ProfessionalEntityRelation.relation_type == relation_type)
        return await self.list_where(
            session,
            *criteria,
            order_by=(ProfessionalEntityRelation.id,),
            limit=limit,
            offset=offset,
        )

    async def list_by_target_entity_id(
        self,
        session: AsyncSession,
        entity_id: int,
        relation_type: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalEntityRelation]:
        criteria = [ProfessionalEntityRelation.target_entity_id == entity_id]
        if relation_type is not None:
            criteria.append(ProfessionalEntityRelation.relation_type == relation_type)
        return await self.list_where(
            session,
            *criteria,
            order_by=(ProfessionalEntityRelation.id,),
            limit=limit,
            offset=offset,
        )


class ProfessionalEntityHierarchyRelationRepository(AsyncRepository[ProfessionalEntityHierarchyRelation]):
    def __init__(self) -> None:
        super().__init__(ProfessionalEntityHierarchyRelation)

    async def list_children_of_parent(
        self,
        session: AsyncSession,
        parent_entity_id: int,
        relation_type: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalEntityHierarchyRelation]:
        criteria = [ProfessionalEntityHierarchyRelation.parent_entity_id == parent_entity_id]
        if relation_type is not None:
            criteria.append(ProfessionalEntityHierarchyRelation.relation_type == relation_type)
        return await self.list_where(
            session,
            *criteria,
            order_by=(ProfessionalEntityHierarchyRelation.id,),
            limit=limit,
            offset=offset,
        )

    async def list_parents_of_child(
        self,
        session: AsyncSession,
        child_entity_id: int,
        relation_type: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalEntityHierarchyRelation]:
        criteria = [ProfessionalEntityHierarchyRelation.child_entity_id == child_entity_id]
        if relation_type is not None:
            criteria.append(ProfessionalEntityHierarchyRelation.relation_type == relation_type)
        return await self.list_where(
            session,
            *criteria,
            order_by=(ProfessionalEntityHierarchyRelation.id,),
            limit=limit,
            offset=offset,
        )


class ProfessionalCollectionRepository(AsyncRepository[ProfessionalCollection]):
    def __init__(self) -> None:
        super().__init__(ProfessionalCollection)

    async def get_by_slug(self, session: AsyncSession, slug: str) -> ProfessionalCollection | None:
        return await self.first_where(session, ProfessionalCollection.slug == slug)


class ProfessionalCollectionMembershipRepository(AsyncRepository[ProfessionalCollectionMembership]):
    def __init__(self) -> None:
        super().__init__(ProfessionalCollectionMembership)

    async def list_by_collection_id(
        self,
        session: AsyncSession,
        collection_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalCollectionMembership]:
        return await self.list_where(
            session,
            ProfessionalCollectionMembership.collection_id == collection_id,
            order_by=(ProfessionalCollectionMembership.id,),
            limit=limit,
            offset=offset,
        )

    async def list_by_entity_id(
        self,
        session: AsyncSession,
        entity_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfessionalCollectionMembership]:
        return await self.list_where(
            session,
            ProfessionalCollectionMembership.entity_id == entity_id,
            order_by=(ProfessionalCollectionMembership.id,),
            limit=limit,
            offset=offset,
        )


professional_entity_repository = ProfessionalEntityRepository()
professional_entity_alias_repository = ProfessionalEntityAliasRepository()
professional_entity_source_repository = ProfessionalEntitySourceRepository()
professional_entity_relation_repository = ProfessionalEntityRelationRepository()
professional_entity_hierarchy_relation_repository = ProfessionalEntityHierarchyRelationRepository()
professional_collection_repository = ProfessionalCollectionRepository()
professional_collection_membership_repository = ProfessionalCollectionMembershipRepository()
