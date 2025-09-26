import re

from django.conf import settings
from haystack.forms import SearchForm
from haystack.inputs import AutoQuery, Raw
from haystack.query import SQ

from .utils import get_base_language, normalize_text


def _q(s: str) -> str:
    s = (s or "").strip()
    # Allow letters, digits, spaces, and hyphen; strip special operators
    s = re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _is_xapian() -> bool:
    try:
        connections = settings.HAYSTACK_CONNECTIONS.get("default", {}) or {}
        engine = connections.get("ENGINE", "")
        return "xapian" in str(engine).lower()
    except Exception:
        return False


def _use_normalized_fields() -> bool:
    """Decide whether normalized fields should be used."""
    try:
        flag = getattr(settings, "RANKED_SEARCH_USE_NORMALIZED_FIELDS", False)
        if bool(flag):
            return True
    except Exception:
        pass
    return _is_xapian()


class CMSWeightedSearchForm(SearchForm):
    """
    A search form that builds a weighted query to boost exact title matches.

    This form enhances the standard Haystack `SearchForm` by constructing a
    query that gives significant weight to exact matches in the title field.
    It also supports searching against normalized fields for accent-insensitive
    matching when available.
    """

    def search(self):
        """
        Constructs a weighted search query based on the user's input.

        The method gives the highest priority to exact title matches, followed
        by term matches in the title. It combines these with a broader search
        across multiple fields (content, tags, body).

        If normalized fields are in use (e.g., with the Xapian backend), the
        query is built against fields like `title_norm` and `content_norm`.
        Otherwise, it falls back to the original fields.

        Returns:
            SearchQuerySet: A Haystack SearchQuerySet filtered with the
                            weighted query, or an empty set if the query
                            is invalid.
        """
        if not self.is_valid() or not self.cleaned_data.get("q"):
            return self.no_query_found()

        user_q = self.cleaned_data["q"]
        q_auto = AutoQuery(user_q)
        q_raw = _q(user_q)
        base = get_base_language()
        q_norm = normalize_text(q_raw, base)

        if _use_normalized_fields():
            # Favor results that match the normalized fields
            exact_title = SQ(title_norm=Raw(f'"{q_norm}"^50'))
            term_title = SQ(title_norm=Raw(f"{q_norm}^10"))
            multi = (
                SQ(content_norm=AutoQuery(q_norm))
                | SQ(title_norm=AutoQuery(q_norm))
                | SQ(tags_norm=AutoQuery(q_norm))
                | SQ(body_norm=AutoQuery(q_norm))
            )
            return self.searchqueryset.filter(exact_title | term_title | multi)
        else:
            # Fall back to boosted original fields
            exact_title = SQ(title=Raw(f'"{q_raw}"^50'))
            # Add extra weight to simple title terms
            term_title = SQ(title=Raw(f"{q_raw}^10"))
            # Combine matches across the remaining fields
            multi = (
                SQ(content=q_auto)
                | SQ(title=q_auto)
                | SQ(tags=q_auto)
                | SQ(body=q_auto)
            )
            return self.searchqueryset.filter(exact_title | term_title | multi)
