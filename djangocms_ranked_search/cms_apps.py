from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool
from django.utils.translation import gettext_lazy as _


@apphook_pool.register
class RankedSearchApphook(CMSApp):
    """Apphook that publishes the search URLs."""

    app_name = "ranked_search"
    name = _("Search (Ranked)")

    def get_urls(self, page=None, language=None, **kwargs):
        return ["djangocms_ranked_search.urls"]
