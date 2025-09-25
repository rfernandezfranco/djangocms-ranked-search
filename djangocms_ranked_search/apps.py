import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DjangoCMSRankedSearchConfig(AppConfig):
    name = "djangocms_ranked_search"
    verbose_name = "Django CMS Ranked Search"

    def ready(self):
        """Register the django CMS integration when it is available."""
        try:
            from . import cms_apps  # noqa: F401
        except Exception:
            logger.exception("Could not import cms_apps to register apphook")
            return

        try:
            from cms.apphook_pool import apphook_pool
            from cms.exceptions import AppAlreadyRegistered

            try:
                from .cms_apps import RankedSearchApphook

                apphook_pool.register(RankedSearchApphook)
                logger.info("Apphook registered with apphook_pool")
            except AppAlreadyRegistered:
                logger.debug("Apphook already registered; skipping duplicate")
            except Exception:
                logger.exception("Apphook registration failed")

            hooks = apphook_pool.get_apphooks()
            try:
                names = [
                    getattr(h, "__name__", type(h).__name__) for h in hooks
                ]
            except Exception:
                names = []
            hook_uses_tuples = any(isinstance(h, tuple) for h in hooks)
            if hook_uses_tuples and "RankedSearchApphook" not in names:
                logger.warning(
                    "Configure %s in CMS_APPHOOKS when using legacy mode.",
                    "Search (Ranked) -> djangocms_ranked_search.urls",
                )
        except Exception:
            return
