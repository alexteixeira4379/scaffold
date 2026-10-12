"""Canonical candidate declarations and stable resume credential ownership.

Legacy JSON is a read-only migration snapshot. Canonical updates never write it.
"""

import json
import re
from datetime import UTC, date, datetime

from sqlalchemy import select
from scaffold.country_codes import exact_country, ISO_COUNTRIES
from scaffold.models.candidate.candidate_application_data import CandidateApplicationData
from scaffold.models.candidate.candidates import Candidate
from scaffold.models.candidate.candidate_work_permissions import CandidateWorkPermission
from scaffold.models.resume.resume_profiles import ResumeProfile
from scaffold.models.resume.resume_profile_credentials import ResumeProfileCredential
from scaffold.constants.schema_enums import ResumeProfileSource


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def wire_date(value):
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def metadata(source, stamp, candidate_id):
    return (
        {"source": source, "candidate_id": candidate_id, "updated_at": wire_date(stamp)}
        if source
        else None
    )


def legacy_document(value, candidate_id):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        return None
    declaration = value.get("declaration")
    if (
        not isinstance(declaration, dict)
        or declaration.get("source") != "candidate_declared"
        or declaration.get("candidate_id") != candidate_id
    ):
        return None
    try:
        stamp = datetime.fromisoformat(declaration["updated_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    return value


def legacy_permission(text):
    if not isinstance(text, str):
        return None
    match = re.fullmatch(r"(yes|no|sim|nao|não)\b\s*[-,:()]?\s*(.*?)\s*\)?", text.strip(), re.I)
    if match is None or not (country := exact_country(match[2].strip().rstrip(")"))):
        return None
    flag = {"yes": "yes", "sim": "yes", "no": "no", "nao": "no", "não": "no"}[match[1].casefold()]
    return {
        "country": country,
        "authorization": flag,
        "sponsorship": "unknown",
        "valid_until": None,
        "declaration_source": "legacy_explicit",
        "declared_at": None,
    }


def parse_expiry(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Invalid declaration date")
    return date.fromisoformat(value)


def legacy_seed(row):
    """Pure, conservative normalization used by migration and bounded backfill.

    Unknown defaults cannot erase an older, unambiguous country-specific fact.
    Conflicting accessibility text remains in its existing field and legacy JSON.
    """
    candidate_id = row["candidate_id"]
    doc = legacy_document(row.get("legal_information"), candidate_id)
    permissions = {}
    if old := legacy_permission(row.get("work_authorization")):
        permissions[old["country"]] = old
    updates = {}
    if doc is None:
        return updates, list(permissions.values())
    stamp = (
        datetime.fromisoformat(doc["declaration"]["updated_at"].replace("Z", "+00:00"))
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    for record in doc.get("work_permissions") or []:
        if not isinstance(record, dict) or record.get("country") not in ISO_COUNTRIES:
            continue
        if record.get("authorization", "unknown") not in {"yes", "no", "unknown"} or record.get(
            "sponsorship", "unknown"
        ) not in {"yes", "no", "unknown"}:
            continue
        try:
            expiry = parse_expiry(record.get("valid_until"))
        except (TypeError, ValueError):
            continue
        previous = permissions.get(record["country"], {})
        auth = record.get("authorization", "unknown")
        sponsor = record.get("sponsorship", "unknown")
        if auth == "unknown" and previous.get("authorization") in {"yes", "no"}:
            auth = previous["authorization"]
        known = auth in {"yes", "no"} or sponsor in {"yes", "no"}
        permissions[record["country"]] = {
            "country": record["country"],
            "authorization": auth,
            "sponsorship": sponsor,
            "valid_until": expiry,
            "declaration_source": "candidate_declared" if known else None,
            "declared_at": stamp if known else None,
        }
    if doc.get("work_permissions"):
        updates["work_permissions_adopted"] = True
    accommodations = doc.get("accommodations") or {}
    if isinstance(accommodations, dict):
        request = accommodations.get("requested", "unknown")
        detail = accommodations.get("details")
        existing = row.get("accessibility_resources")
        if request in {"yes", "no", "unknown"} and (detail is None or isinstance(detail, str)):
            if request == "no":
                updates.update(
                    accommodation_requested="no",
                    accessibility_resources=None,
                    accommodations_adopted=True,
                )
            elif (request in {"yes", "no"} or detail) and not (
                existing and detail and existing != detail
            ):
                updates["accommodation_requested"] = request
                updates["accommodations_adopted"] = bool(request in {"yes", "no"} or detail)
                if detail:
                    updates["accessibility_resources"] = detail
    notes = doc.get("context_notes")
    if isinstance(notes, str) and len(notes) <= 4000:
        updates["application_context_notes"] = notes
    if updates or any(
        p.get("declaration_source") == "candidate_declared" for p in permissions.values()
    ):
        updates.update(
            information_adopted=True,
            information_source="candidate_declared",
            information_declared_at=stamp,
        )
    return updates, list(permissions.values())


def credential_identity(record, item):
    name = record.get("name", record.get("nome", ""))
    if (
        str(name).strip().casefold()
        != str(item.get("name", item.get("nome", ""))).strip().casefold()
    ):
        return False
    if "credential_type" in item and str(record.get("credential_type")) != str(
        item["credential_type"]
    ):
        return False
    if "credential_type" not in item and str(record.get("credential_type")) != "certification":
        return False
    for field in ("issuer", "reference"):
        if (
            record.get(field)
            and item.get(field)
            and str(record[field]).strip().casefold() != str(item[field]).strip().casefold()
        ):
            return False
    return True


async def canonical_projection(session, candidate_id, data=None):
    data = data or await session.scalar(
        select(CandidateApplicationData).where(
            CandidateApplicationData.candidate_id == candidate_id
        )
    )
    if data is not None and data.candidate_id != candidate_id:
        raise ValueError("Candidate information ownership mismatch")
    doc = legacy_document(data.legal_information, candidate_id) if data else None
    rows = (
        await session.scalars(
            select(CandidateWorkPermission)
            .where(CandidateWorkPermission.candidate_id == candidate_id)
            .order_by(CandidateWorkPermission.country)
        )
    ).all()
    permissions = [
        {
            "country": row.country,
            "authorization": row.authorization,
            "sponsorship": row.sponsorship,
            "valid_until": row.valid_until.isoformat() if row.valid_until else None,
            "declaration": metadata(row.declaration_source, row.declared_at, candidate_id),
        }
        for row in rows
    ]
    work_adopted = bool(data and data.work_permissions_adopted)
    if not work_adopted and not permissions and doc:
        permissions = [
            {
                **record,
                "declaration": doc["declaration"]
                if record.get("authorization") in {"yes", "no"}
                or record.get("sponsorship") in {"yes", "no"}
                else None,
            }
            for record in doc.get("work_permissions") or []
            if isinstance(record, dict)
            and record.get("country") in ISO_COUNTRIES
            and record.get("authorization", "unknown") in {"yes", "no", "unknown"}
            and record.get("sponsorship", "unknown") in {"yes", "no", "unknown"}
        ]
    profile = await session.scalar(
        select(ResumeProfile).where(ResumeProfile.candidate_id == candidate_id)
    )
    credentials = []
    if profile:
        records = (
            await session.scalars(
                select(ResumeProfileCredential)
                .where(
                    ResumeProfileCredential.resume_profile_id == profile.id,
                    ResumeProfileCredential.credential_type != "course",
                )
                .order_by(ResumeProfileCredential.order_index, ResumeProfileCredential.id)
            )
        ).all()
        credentials = [
            {
                "id": row.id,
                "credential_type": str(row.credential_type),
                "name": row.nome,
                "issuer": row.issuer,
                "reference": row.reference,
                "valid_until": row.valid_until.isoformat() if row.valid_until else None,
                "declaration": metadata(row.declaration_source, row.declared_at, candidate_id),
            }
            for row in records
        ]
    credentials_adopted = bool(data and data.credentials_adopted)
    if not credentials_adopted and doc:
        for item in doc.get("professional_credentials") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            matches = [record for record in credentials if credential_identity(record, item)]
            baseline = matches[0] if len(matches) == 1 else {}
            known = {
                field: value
                for field, value in item.items()
                if value not in (None, "")
                and field in {"name", "issuer", "reference", "valid_until"}
            }
            value = {
                **baseline,
                **known,
                "credential_type": baseline.get("credential_type", "other"),
                "id": baseline.get("id"),
                "declaration": doc["declaration"],
            }
            if len(matches) == 1:
                credentials[credentials.index(matches[0])] = value
            else:
                credentials.append(value)
    accommodations = {
        "requested": (data.accommodation_requested or "unknown") if data else "unknown",
        "details": data.accessibility_resources if data else None,
    }
    if (
        data
        and not data.accommodations_adopted
        and doc
        and isinstance(doc.get("accommodations"), dict)
    ):
        seeded, _ = legacy_seed(
            {
                "candidate_id": candidate_id,
                "legal_information": data.legal_information,
                "accessibility_resources": data.accessibility_resources,
                "work_authorization": data.work_authorization,
            }
        )
        if seeded.get("accommodations_adopted"):
            accommodations["requested"] = seeded.get(
                "accommodation_requested", accommodations["requested"]
            )
            accommodations["details"] = seeded.get(
                "accessibility_resources", accommodations["details"]
            )
    return {
        "schema_version": 1,
        "work_permissions": permissions,
        "work_permissions_adopted": work_adopted,
        "accommodations": accommodations,
        "accommodations_adopted": bool(data and data.accommodations_adopted),
        "professional_credentials": credentials,
        "credentials_adopted": credentials_adopted,
        "context_notes": data.application_context_notes if data else None,
        "declaration": metadata(data.information_source, data.information_declared_at, candidate_id)
        if data
        else None,
    }


async def stable_credentials(
    session,
    profile,
    items,
    *,
    candidate_id,
    professional_only=False,
    declare=False,
    preserve_private=False,
):
    """Stable, scoped upsert; explicit lists remove only their own section/subset."""
    if profile.candidate_id != candidate_id:
        raise ValueError("Credential profile ownership mismatch")
    rows = (
        await session.scalars(
            select(ResumeProfileCredential)
            .where(ResumeProfileCredential.resume_profile_id == profile.id)
            .with_for_update()
        )
    ).all()
    by_id = {row.id: row for row in rows}
    retained = set()
    used = set()
    did_change = False
    for position, item in enumerate(items):
        item = dict(item)
        row_id = item.get("id")
        created = False
        if row_id is not None:
            if row_id in used or row_id not in by_id:
                raise ValueError("Credential ownership or duplicate ID mismatch")
            row = by_id[row_id]
            if professional_only and str(row.credential_type) == "course":
                raise ValueError("Course is outside professional credential update")
        else:
            name = str(item.get("nome", item.get("name", ""))).strip()
            kind = item.get("credential_type", "other")
            matches = [
                row
                for row in rows
                if row.id not in used
                and credential_identity(
                    {
                        "name": row.nome,
                        "credential_type": str(row.credential_type),
                        "issuer": row.issuer,
                        "reference": row.reference,
                    },
                    item,
                )
            ]
            row = matches[0] if len(matches) == 1 else None
            if row is None:
                row = ResumeProfileCredential(
                    resume_profile_id=profile.id,
                    nome=name,
                    credential_type=kind,
                    order_index=position,
                )
                created = True
                did_change = True
                row.order_index = (
                    max((existing.order_index or 0 for existing in rows), default=-1) + 1
                    if professional_only
                    else position
                )
                session.add(row)
                await session.flush()
                by_id[row.id] = row
        used.add(row.id)
        retained.add(row.id)
        changed = False
        for field in ("nome", "credential_type", "issuer", "reference", "valid_until"):
            source_key = "name" if field == "nome" and "name" in item else field
            if source_key not in item:
                continue
            value = parse_expiry(item[source_key]) if field == "valid_until" else item[source_key]
            if str(getattr(row, field)) != str(value):
                changed = True
            setattr(row, field, value)
        if not declare and changed:
            row.declaration_source, row.declared_at = None, None
        if declare and (changed or item.get("confirm") is True or created):
            row.declaration_source, row.declared_at = "candidate_declared", utcnow()
            did_change = True
        did_change = did_change or changed
        if not professional_only and row.order_index != position:
            row.order_index = position
            did_change = True
    for row in rows:
        if (
            row.id not in retained
            and (not professional_only or str(row.credential_type) != "course")
            and not (preserve_private and str(row.credential_type) in {"license", "other"})
        ):
            await session.delete(row)
            did_change = True
    profile._credential_change = did_change
    await session.flush()
    profile.credentials = (
        await session.scalars(
            select(ResumeProfileCredential)
            .where(ResumeProfileCredential.resume_profile_id == profile.id)
            .order_by(ResumeProfileCredential.order_index, ResumeProfileCredential.id)
        )
    ).all()
    return profile.credentials


async def backfill_legacy_credentials(session, candidate_id):
    """Run only after all enum readers support license/other; bounded by caller."""
    await session.scalar(select(Candidate.id).where(Candidate.id == candidate_id).with_for_update())
    profile = await session.scalar(
        select(ResumeProfile).where(ResumeProfile.candidate_id == candidate_id).with_for_update()
    )
    data = await session.scalar(
        select(CandidateApplicationData)
        .where(CandidateApplicationData.candidate_id == candidate_id)
        .with_for_update()
    )
    if data is None or data.credentials_adopted:
        return False
    doc = legacy_document(data.legal_information, candidate_id)
    if not doc or not doc.get("professional_credentials"):
        data.credentials_adopted = True
        return False
    projected = await canonical_projection(session, candidate_id, data)

    if profile is None:
        profile = ResumeProfile(
            candidate_id=candidate_id,
            source=ResumeProfileSource.DIRECT_API,
            summary=None,
            revision=1,
        )
        session.add(profile)
        await session.flush()
    items = projected["professional_credentials"]
    await stable_credentials(
        session, profile, items, candidate_id=candidate_id, professional_only=True, declare=False
    )
    stamp = (
        datetime.fromisoformat(doc["declaration"]["updated_at"].replace("Z", "+00:00"))
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    for legacy in doc["professional_credentials"]:
        matches = [
            row
            for row in profile.credentials
            if credential_identity(
                {
                    "name": row.nome,
                    "credential_type": str(row.credential_type),
                    "issuer": row.issuer,
                    "reference": row.reference,
                },
                legacy,
            )
        ]
        if not matches:
            # Unclassified legacy records were deliberately stored as other.
            matches = [
                row
                for row in profile.credentials
                if credential_identity(
                    {
                        "name": row.nome,
                        "credential_type": str(row.credential_type),
                        "issuer": row.issuer,
                        "reference": row.reference,
                    },
                    {**legacy, "credential_type": "other"},
                )
            ]
        if len(matches) != 1:
            raise ValueError("Ambiguous credential migration remains in read-only legacy snapshot")
        matches[0].declaration_source, matches[0].declared_at = "candidate_declared", stamp
    data.credentials_adopted = True
    return True
