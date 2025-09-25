from django.conf import settings
from haystack.backends.whoosh_backend import WhooshEngine, WhooshSearchBackend
from haystack.constants import DJANGO_CT, DJANGO_ID, ID
from haystack.exceptions import SearchBackendError
from whoosh.analysis import (
    CharsetFilter,
    LowercaseFilter,
    RegexTokenizer,
    StemFilter,
    StopFilter,
)
from whoosh.fields import BOOLEAN, DATETIME
from whoosh.fields import ID as WHOOSH_ID
from whoosh.fields import (
    IDLIST,
    KEYWORD,
    NGRAM,
    NGRAMWORDS,
    NUMERIC,
    TEXT,
    Schema,
)

from .utils import build_charset_map


def _get_base_language():
    """Return the base language from settings (e.g., 'es', 'en')."""
    code = (
        getattr(settings, "RANKED_SEARCH_LANGUAGE", None)
        or getattr(settings, "HAYSTACK_LANGUAGE", None)
        or getattr(settings, "LANGUAGE_CODE", "en")
    )
    code = code or "en"
    # Normalise formats like "es-ES" or "pt_BR"
    code = str(code).split("-")[0].split("_")[0].lower()
    if not code:
        code = "en"
    return code


class WhooshLangBackend(WhooshSearchBackend):
    """Whoosh backend with accent folding and language-aware filters."""

    def _charset_filter(self):
        """Build a charset filter according to the language profile."""
        base_lang = _get_base_language()
        cmap = build_charset_map(base_lang)
        return CharsetFilter(cmap)

    def get_analyzer(self):
        # Build the analyzer by chaining the language filters
        base_lang = _get_base_language()
        try:
            stop_filter = StopFilter(lang=base_lang)
        except Exception:
            stop_filter = StopFilter(lang="en")
        try:
            stem_filter = StemFilter(lang=base_lang)
        except Exception:
            stem_filter = StemFilter(lang="en")

        return (
            RegexTokenizer()
            | self._charset_filter()
            | LowercaseFilter()
            | stop_filter
            | stem_filter
        )

    def build_schema(self, fields):
        """Define the schema using the analyzer for TEXT fields."""
        schema_fields = {
            ID: WHOOSH_ID(stored=True, unique=True),
            DJANGO_CT: WHOOSH_ID(stored=True),
            DJANGO_ID: WHOOSH_ID(stored=True),
        }
        initial_key_count = len(schema_fields)
        content_field_name = ""

        for field_name, field_class in fields.items():
            if field_class.is_multivalued:
                if field_class.indexed is False:
                    schema_fields[field_class.index_fieldname] = IDLIST(
                        stored=True,
                        field_boost=field_class.boost,
                    )
                else:
                    schema_fields[field_class.index_fieldname] = KEYWORD(
                        stored=True,
                        commas=True,
                        scorable=True,
                        field_boost=field_class.boost,
                    )
            elif field_class.field_type in ["date", "datetime"]:
                schema_fields[field_class.index_fieldname] = DATETIME(
                    stored=field_class.stored,
                    sortable=True,
                )
            elif field_class.field_type == "integer":
                schema_fields[field_class.index_fieldname] = NUMERIC(
                    stored=field_class.stored,
                    numtype=int,
                    field_boost=field_class.boost,
                )
            elif field_class.field_type == "float":
                schema_fields[field_class.index_fieldname] = NUMERIC(
                    stored=field_class.stored,
                    numtype=float,
                    field_boost=field_class.boost,
                )
            elif field_class.field_type == "boolean":
                schema_fields[field_class.index_fieldname] = BOOLEAN(
                    stored=field_class.stored
                )
            elif field_class.field_type == "ngram":
                schema_fields[field_class.index_fieldname] = NGRAM(
                    minsize=3,
                    maxsize=15,
                    stored=field_class.stored,
                    field_boost=field_class.boost,
                )
            elif field_class.field_type == "edge_ngram":
                schema_fields[field_class.index_fieldname] = NGRAMWORDS(
                    minsize=2,
                    maxsize=15,
                    at="start",
                    stored=field_class.stored,
                    field_boost=field_class.boost,
                )
            else:
                schema_fields[field_class.index_fieldname] = TEXT(
                    stored=field_class.stored,
                    analyzer=self.get_analyzer(),
                    field_boost=field_class.boost,
                    sortable=True,
                )

            if field_class.document is True:
                content_field_name = field_class.index_fieldname
                schema_fields[field_class.index_fieldname].spelling = True

        if len(schema_fields) <= initial_key_count:
            raise SearchBackendError(
                "No fields were found in any search_indexes. "
                "Please correct this before attempting to search."
            )

        return (content_field_name, Schema(**schema_fields))


class WhooshLangEngine(WhooshEngine):
    backend = WhooshLangBackend
