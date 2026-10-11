"""Email metadata contracts; no received content or extracted codes in broker payloads."""

from scaffold.email.contracts import EmailForwardRequested, EmailInboundRequested

__all__ = ["EmailInboundRequested", "EmailForwardRequested"]
