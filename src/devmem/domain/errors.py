from __future__ import annotations


class DevMemError(Exception):
    """Base exception for DevMem failures."""


class TenantIsolationError(DevMemError):
    """Raised when a read or write lacks an explicit tenant scope."""


class OptionalFeatureError(DevMemError):
    """Raised when an optional feature is selected without its extra installed."""
