from aldryn_search.helpers import get_plugin_index_data
from aldryn_search.utils import get_index_base
from cms.models import Title
from django.db import models
from django.utils.html import strip_tags
from haystack import indexes

from .utils import get_base_language, normalize_text


class CMSTitleRankedIndex(get_index_base()):
    """
    A Haystack `SearchIndex` for django CMS `Title` objects.

    This index is responsible for preparing and defining the searchable data
    associated with a CMS page title. It creates standard fields like `title`,
    `body`, and `tags`, and also adds normalized, accent-insensitive variants
    (e.g., `title_norm`, `body_norm`) to improve search quality with custom
    backends.
    """

    haystack_use_for_indexing = True
    index_title = True

    # Boost: title > tags > body
    title = indexes.CharField(stored=True, boost=6.0)
    tags = indexes.CharField(stored=True, null=True, boost=3.0)
    body = indexes.CharField(stored=True, null=True, boost=1.0)
    url = indexes.CharField(indexed=False, stored=True)

    # Normalized fields for backends that expect folded text
    title_norm = indexes.CharField(stored=False, boost=6.0)
    tags_norm = indexes.CharField(stored=False, null=True, boost=3.0)
    body_norm = indexes.CharField(stored=False, null=True, boost=1.0)
    content_norm = indexes.CharField(stored=False, null=True)

    def get_model(self):
        return Title

    def index_queryset(self, using=None):
        self._get_backend(using)
        language = self.get_current_language(using)
        qs = Title.objects
        public = getattr(qs, "public", None)
        if callable(public):
            qs = public()
        else:
            qs = qs.filter(publisher_is_draft=False)
        # Limit the queryset to published titles in the active language
        try:
            # The published field exists in modern projects
            Title._meta.get_field("published")
            qs = qs.filter(published=True)
        except Exception:
            # Keep using the public/publisher_is_draft filter otherwise
            pass
        return (
            qs.filter(language=language)
            .select_related("page")
            .prefetch_related("page__placeholders")
        )

    def get_url(self, obj):
        """Return the absolute URL for the page associated with the Title."""
        try:
            return obj.page.get_absolute_url(language=obj.language)
        except Exception:
            return obj.page.get_absolute_url()

    def prepare_title(self, obj):
        """
        Prepare the title field by finding the best available title.

        It tries to get the title from the title object itself, then falls
        back to the page's page title, menu title, or slug.
        """
        return (
            (obj.title or "").strip()
            or getattr(
                obj.page,
                "get_page_title",
                lambda lang=None: "",
            )(obj.language)
            or getattr(
                obj.page,
                "get_menu_title",
                lambda lang=None: "",
            )(obj.language)
            or getattr(
                obj.page,
                "get_title",
                lambda lang=None: "",
            )(obj.language)
            or getattr(
                obj.page,
                "get_slug",
                lambda lang=None: "",
            )(obj.language)
            or ""
        )

    def get_search_data(self, title_obj, language, request):
        """
        Aggregate all searchable text content from a page's plugins.

        This method iterates through all placeholders and plugins on a page,
        extracting text content using `get_plugin_index_data`. It also
        inspects common field names (e.g., `body`, `text`, `caption`) on
        plugin instances as a fallback.

        Args:
            title_obj (Title): The CMS Title object being indexed.
            language (str): The active language.
            request: The current request object.

        Returns:
            str: A single string containing all extracted plain text.
        """
        bits = []
        page = title_obj.page

        for ph in page.placeholders.all():
            for base_plugin in ph.get_plugins(language=language):
                extracted = get_plugin_index_data(base_plugin, request) or []
                for t in extracted:
                    if t:
                        bits.append(strip_tags(t))

                if not extracted:
                    instance, _ = base_plugin.get_plugin_instance()
                    if not instance:
                        continue

                    for fname in (
                        "content",
                        "body",
                        "text",
                        "description",
                        "caption",
                        "label",
                        "name",
                        "title",
                    ):
                        if hasattr(instance, fname):
                            val = getattr(instance, fname)
                            if isinstance(val, str) and val.strip():
                                bits.append(strip_tags(val))

                    try:
                        for f in instance._meta.get_fields():
                            if isinstance(
                                f,
                                (models.CharField, models.TextField),
                            ):
                                val = getattr(instance, f.name, "")
                                if isinstance(val, str) and val.strip():
                                    bits.append(strip_tags(val))
                    except Exception:
                        pass

        doc = " ".join(filter(None, bits)).strip()
        doc = " ".join(doc.split())
        return doc

    def prepare_tags(self, obj):
        """Extract and combine tags from the page or title extension."""
        try:
            return " ".join(t.name for t in obj.page.tags.all())
        except Exception:
            pass
        try:
            ext = getattr(obj, "titleextension", None)
            if ext and hasattr(ext, "tags"):
                return " ".join(t.name for t in ext.tags.all())
        except Exception:
            pass
        if hasattr(obj, "tags"):
            try:
                return " ".join(t.name for t in obj.tags.all())
            except Exception:
                pass
        return ""

    def prepare_fields(self, title_obj, language, request):
        """
        Prepare all fields for indexing, including raw and normalized versions.

        This method populates the `prepared_data` dictionary, which is used by
        Haystack to build the search index document. It sets the standard
        fields (`title`, `tags`, `body`, `url`) and also generates the
        normalized, accent-folded versions (`title_norm`, `tags_norm`,
        `body_norm`) for use by custom search backends.
        """
        super().prepare_fields(title_obj, language, request)
        # Preserve raw values for display and analyzers with custom folding
        self.prepared_data["title"] = self.prepare_title(title_obj)
        self.prepared_data["tags"] = self.prepare_tags(title_obj)
        self.prepared_data["url"] = self.get_url(title_obj)
        # Keep body aligned with the assembled document
        self.prepared_data["body"] = self.prepared_data.get("text", "")

        # Prepare normalized variants reused by different backends
        base = get_base_language()
        try:
            raw_doc = self.get_search_data(title_obj, language, request) or ""
        except Exception:
            raw_doc = self.prepared_data.get("text", "") or ""

        self.prepared_data["title_norm"] = normalize_text(
            self.prepared_data.get("title", ""),
            base,
        )
        self.prepared_data["tags_norm"] = normalize_text(
            self.prepared_data.get("tags", ""),
            base,
        )
        # Derive normalized variants from the combined document
        self.prepared_data["body_norm"] = normalize_text(raw_doc, base)
        self.prepared_data["content_norm"] = self.prepared_data["body_norm"]
