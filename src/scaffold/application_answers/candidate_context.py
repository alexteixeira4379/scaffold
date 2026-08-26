"""Load candidate data from the database for answering questions."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from scaffold.application_answers.contracts import CandidateContext, StoragePort
from scaffold.repositories import (
    candidate_preference_repository,
    candidate_repository,
    cover_letter_version_repository,
    resume_version_repository,
)

logger = logging.getLogger(__name__)


async def load_candidate_context(
    session_factory: async_sessionmaker[AsyncSession],
    candidate_id: int,
    *,
    storage_client: StoragePort | None = None,
) -> CandidateContext:
    """Load all candidate data needed for answering application questions.

    Args:
        session_factory: SQLAlchemy async session factory.
        candidate_id: ID of the candidate.
        storage_client: Optional StoragePort implementation for downloading files.

    Returns:
        Populated CandidateContext dataclass.
    """
    ctx = CandidateContext(candidate_id=candidate_id)

    async with session_factory() as session:
        # Load candidate base data
        candidate = await candidate_repository.get(session, candidate_id)
        if candidate is None:
            logger.warning("candidate_not_found candidate_id=%d", candidate_id)
            return ctx

        ctx.full_name = candidate.full_name or ""
        ctx.email = candidate.email or ""
        ctx.phone = candidate.phone
        ctx.country = candidate.country
        ctx.location = candidate.location
        ctx.linkedin_url = candidate.linkedin_url

        # Load preferences
        prefs = await candidate_preference_repository.get_by_candidate_id(session, candidate_id)
        if prefs is not None:
            ctx.target_country = prefs.target_country
            ctx.target_location = prefs.target_location
            ctx.min_salary = float(prefs.min_salary) if prefs.min_salary is not None else None
            ctx.currency = prefs.currency

        # Load application data (optional table)
        app_data = await _load_application_data(session, candidate_id)
        if app_data is not None:
            ctx.years_of_experience = app_data.years_of_experience
            ctx.work_authorization = app_data.work_authorization
            ctx.citizenship = app_data.citizenship
            ctx.education_level = app_data.education_level
            ctx.languages = app_data.languages or []
            ctx.availability = app_data.availability
            ctx.gender = app_data.gender
            ctx.veteran_status = app_data.veteran_status
            ctx.disability_status = app_data.disability_status
            ctx.custom_answers = app_data.custom_answers or {}

        # Load resume path
        resumes = await resume_version_repository.list_by_candidate_id(
            session, candidate_id, limit=1
        )
        if resumes:
            resume = resumes[0]
            if resume.storage_url and storage_client is not None:
                ctx.resume_local_path = await _download_file(
                    storage_client, resume.storage_url, f"resume_{candidate_id}"
                )

        # Load cover letter path
        cover_letters = await cover_letter_version_repository.list_by_candidate_id(
            session, candidate_id, limit=1
        )
        if cover_letters:
            cl = cover_letters[0]
            if cl.storage_url and storage_client is not None:
                ctx.cover_letter_local_path = await _download_file(
                    storage_client, cl.storage_url, f"cover_letter_{candidate_id}"
                )

    return ctx


async def _load_application_data(session: AsyncSession, candidate_id: int) -> object | None:
    """Load CandidateApplicationData if the table/repo exists."""
    try:
        from scaffold.repositories import candidate_application_data_repository

        return await candidate_application_data_repository.get_by_candidate_id(
            session, candidate_id
        )
    except (ImportError, AttributeError):
        logger.debug("candidate_application_data_repository not available, skipping")
        return None


async def _download_file(storage_client: StoragePort, storage_url: str, prefix: str) -> str | None:
    """Download a file from storage to a temp path.

    The scaffold StorageClient.get(key) returns a StoredObjectBody with a .body: bytes
    attribute, or None if the key doesn't exist.
    """
    try:
        # Extract key from URL — storage_url may be a full URL or just a key
        key = storage_url
        if "://" in storage_url:
            from urllib.parse import urlparse

            parsed = urlparse(storage_url)
            # Remove leading slash and bucket name
            path_parts = parsed.path.lstrip("/").split("/", 1)
            key = path_parts[1] if len(path_parts) > 1 else path_parts[0]

        # Determine file extension
        ext = Path(key).suffix or ".pdf"
        tmp = tempfile.NamedTemporaryFile(prefix=f"{prefix}_", suffix=ext, delete=False)
        tmp_path = tmp.name
        tmp.close()

        result = await storage_client.get(key)
        if result is None:
            return None

        # scaffold.storage.StoredObjectBody has .body: bytes
        # Support both the real StoredObjectBody and raw bytes for testing
        if hasattr(result, "body"):
            data: bytes = result.body  # type: ignore[union-attr]
        elif isinstance(result, bytes):
            data = result
        elif isinstance(result, str):
            data = result.encode("utf-8")
        else:
            logger.warning(
                "file_download_unexpected_type url=%s type=%s", storage_url, type(result)
            )
            return None

        Path(tmp_path).write_bytes(data)
        return tmp_path
    except Exception as exc:
        logger.warning("file_download_failed url=%s error=%s", storage_url, exc)

    return None
