from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"
    FILLED = "filled"
    EXPIRED = "expired"
    DRAFT = "draft"
    DUPLICATE = "duplicate"
    SUSPENDED = "suspended"


class RemoteType(StrEnum):
    UNKNOWN = "unknown"
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    FLEXIBLE = "flexible"


class EmploymentType(StrEnum):
    UNKNOWN = "unknown"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    FREELANCER = "freelancer"


class ExperienceLevel(StrEnum):
    UNKNOWN = "unknown"
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    MID_SENIOR = "mid_senior"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    LEAD = "lead"
    EXECUTIVE = "executive"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CHURNED = "churned"
    BLOCKED = "blocked"
    ONBOARDING = "onboarding"


class LanguagePreference(StrEnum):
    PT_BR = "pt-BR"
    EN_US = "en-US"
    ES = "es"
    FR = "fr"


class JobMatchStatus(StrEnum):
    PENDING = "pending"
    SCORED = "scored"
    SHORTLISTED = "shortlisted"
    RECOMMENDED = "recommended"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
    CONVERTED = "converted"
    STALE = "stale"


class JobApplicationStatus(StrEnum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    HIRED = "hired"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"
    CANCELLED = "cancelled"


class ApplyMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    ASSISTED = "assisted"


class ApplicationRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class ApplicationStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ApplicationMessageStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
    CANCELLED = "cancelled"
    DELIVERED = "delivered"


class MessageChannel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    WEBHOOK = "webhook"
    INTERNAL = "internal"


class MessageType(StrEnum):
    TRANSACTIONAL = "transactional"
    MARKETING = "marketing"
    STATUS = "status"
    ALERT = "alert"
    DIGEST = "digest"
    REMINDER = "reminder"


class ApplicationArtifactType(StrEnum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    SCREENSHOT = "screenshot"
    FORM_DUMP = "form_dump"
    ATTACHMENT = "attachment"
    EXPORT = "export"
    OTHER = "other"


class ApplicationFailureType(StrEnum):
    NETWORK = "network"
    VALIDATION = "validation"
    CAPTCHA = "captcha"
    TIMEOUT = "timeout"
    PARSE = "parse"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    PLATFORM = "platform"
    BOT = "bot"
    UNKNOWN = "unknown"


class BillingPaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    REQUIRES_ACTION = "requires_action"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class BillingSubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    PAUSED = "paused"


class SearchRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class SearchDefinitionScopeType(StrEnum):
    CANDIDATE = "candidate"
    PRESET = "preset"
    GLOBAL = "global"
    SYSTEM = "system"
    TEMPLATE = "template"


class AtsProviderDomainType(StrEnum):
    MAIN = "main"
    REDIRECT = "redirect"
    ALIAS = "alias"
    STAGING = "staging"


class ScraperType(StrEnum):
    HTTP = "http"
    BROWSER = "browser"
    HYBRID = "hybrid"
    RPC = "rpc"


class AtsAuthType(StrEnum):
    NONE = "none"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    COOKIE = "cookie"
    BROWSER = "browser"
    CUSTOM = "custom"


class AtsPaginationType(StrEnum):
    NONE = "none"
    OFFSET = "offset"
    CURSOR = "cursor"
    PAGE = "page"
    LINK = "link"


class CompanyDomainType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ALIAS = "alias"


class ResumeSessionType(StrEnum):
    BUILDER = "builder"
    IMPORT = "import"
    WIZARD = "wizard"
    REPAIR = "repair"


class ResumeSessionStatus(StrEnum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"
    PAUSED = "paused"


class ResumeDocumentFormat(StrEnum):
    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"
    TXT = "txt"
    RTF = "rtf"
    MD = "md"


class ResumeStepInputType(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTISELECT = "multiselect"
    BOOLEAN = "boolean"
    FILE = "file"
    NUMBER = "number"
    DATE = "date"
    RICH_TEXT = "rich_text"


def members(e: type[StrEnum]) -> tuple[str, ...]:
    return tuple(m.value for m in e)


JOB_DISCOVERY_SOURCE_KIND_EXAMPLES = frozenset(
    {"api", "scraper", "feed", "partner", "custom", "archive", "embedded"}
)
ATS_PROVIDER_KIND_EXAMPLES = frozenset(
    {"api", "scraper", "feed", "partner", "custom", "archive", "embedded"}
)
