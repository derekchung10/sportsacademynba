"""Shared utility helpers used across services."""
from datetime import datetime, timezone


def build_child_info(lead) -> str:
    """Build a child info string from a lead. Used by interaction processor and context service."""
    child_info = lead.child_name or ""
    if lead.child_age:
        child_info += f" (age {lead.child_age})"
    return child_info


def utcnow() -> datetime:
    """Return timezone-aware UTC now. Replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)
