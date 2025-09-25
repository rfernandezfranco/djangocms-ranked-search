"""Lightweight Xapian integration for Haystack."""

from django.core.exceptions import ImproperlyConfigured


def _import_xapian_backend():
    """Resolve the available Xapian backend classes."""
    try:
        from haystack.backends.xapian_backend import (
            XapianEngine as _Engine,  # type: ignore
        )
        from haystack.backends.xapian_backend import (
            XapianSearchBackend as _Backend,
        )

        return _Engine, _Backend
    except Exception:
        pass

    try:
        from xapian_backend import XapianEngine as _Engine  # type: ignore
        from xapian_backend import XapianSearchBackend as _Backend

        return _Engine, _Backend
    except Exception:
        pass

    # No compatible Xapian backend was found
    raise ImproperlyConfigured(
        "No Xapian backend for Haystack was found. "
        "Install a compatible backend (e.g., haystack-xapian) "
        "and ensure it exposes XapianEngine and XapianSearchBackend."
    )


_EngineBase, _BackendBase = _import_xapian_backend()


class XapianLangBackend(_BackendBase):
    """Wrapper around the Xapian backend for future extensions."""

    pass


class XapianLangEngine(_EngineBase):
    backend = XapianLangBackend
