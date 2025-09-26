import re
from functools import lru_cache

from aldryn_common.paginator import DiggPaginator
from aldryn_search.views import AldrynSearchView
from django.conf import settings
from django.core.paginator import InvalidPage

from .forms import CMSWeightedSearchForm
from .utils import get_base_language, normalize_text

# Use RERANK_* settings to fine-tune reranking behaviour


def _get_base_language():
    # Prefer the explicit rerank language and fall back to the detected one
    code = getattr(settings, "RERANK_LANGUAGE", "auto")
    if code and str(code).lower() != "auto":
        base = str(code)
        return str(base).split("-")[0].split("_")[0].lower() or "en"
    return get_base_language()


def _build_tokenizer():
    """Return a tokenizer driven by available analyzers or a regex fallback."""
    base = _get_base_language()
    try:
        from whoosh.analysis import LanguageAnalyzer, StandardAnalyzer

        try:
            analyzer = LanguageAnalyzer(base)
        except Exception:
            analyzer = StandardAnalyzer()

        def _tok(text: str):
            return [t.text for t in analyzer(text)]

        return _tok
    except Exception:
        word_re = re.compile(r"[\w\d]+", re.UNICODE)

        def _tok(text: str):
            return word_re.findall(text)

        return _tok


TOKENIZE = _build_tokenizer()


@lru_cache(maxsize=50000)
def _normalize(s: str) -> str:
    # Reuse the same normalization used by the backend
    return normalize_text(s, base_lang=_get_base_language())


def _stopset():
    # Assemble the stopword overrides defined in settings
    base = set(getattr(settings, "RERANK_STOPWORDS_ADD", set()))
    base -= set(getattr(settings, "RERANK_STOPWORDS_REMOVE", set()))
    return base


STOP_EXTRA = _stopset()


@lru_cache(maxsize=50000)
def _tokens(s: str):
    """Tokenize and filter custom stopwords and short tokens."""
    s = _normalize(s)
    toks = TOKENIZE(s)
    return [t for t in toks if t not in STOP_EXTRA and len(t) > 1]


def _jaccard(query: str, title: str) -> float:
    A, B = set(_tokens(query)), set(_tokens(title))
    return (len(A & B) / float(len(A | B))) if A and B else 0.0


class CMSWeightedSearchView(AldrynSearchView):
    """
    A search view that performs in-memory re-ranking of results.

    This view overrides the default pagination behavior to fetch a larger pool
    of initial results from the search backend. It then re-ranks these results
    using a scoring algorithm that prioritizes exact title matches and token
    similarity (Jaccard index) before falling back to the backend score.
    """

    form_class = CMSWeightedSearchForm

    def paginate_queryset(self, queryset, page_size):
        """
        Re-ranks a queryset in memory and returns a single page of results.

        This method fetches a configurable pool of results (defined by
        `RERANK_POOL`) from the initial queryset. It then sorts these items
        based on a multi-tiered algorithm:
        1.  Exact match between the normalized query and normalized title.
        2.  Jaccard similarity score between query and title tokens.
        3.  The original score from the search backend (descending).
        4.  The number of tokens in the title (ascending, to favor brevity).
        5.  The normalized title itself (for deterministic ordering).

        Args:
            queryset (SearchQuerySet): The initial queryset from Haystack.
            page_size (int): The number of items to display per page.

        Returns:
            tuple: A tuple with (paginator, page, object_list, has_other_pages)
                as expected by AldrynSearchView.
        """
        raw_q = self.request.GET.get("q", "")
        ceiling = getattr(settings, "RERANK_CEILING", 1000)
        # Control the amount of results processed for reranking
        pool = getattr(settings, "RERANK_POOL", None)
        if not pool:
            pool = max(int(page_size) * 10, 200)
        pool = min(int(pool), int(ceiling))

        # Clamp the query to the required window size
        try:
            queryset.query.set_limits(0, pool)
        except Exception:
            pass
        items = list(queryset)

        # Cache normalized text and tokens for reuse
        q_norm = _normalize(raw_q)
        q_tokens = set(_tokens(raw_q))
        title_norm_cache = {}
        title_tokens_cache = {}

        def key(res):
            title = getattr(res, "title", "") or ""

            # Skip recomputing normalization for repeated titles
            t_norm = title_norm_cache.get(title)
            if t_norm is None:
                t_norm = _normalize(title)
                title_norm_cache[title] = t_norm

            exact = t_norm == q_norm
            # Fall back to token similarity when there is no exact match
            pct = 0.0
            toks_len = 0
            if not exact:
                toks = title_tokens_cache.get(title)
                if toks is None:
                    toks = _tokens(title)
                    title_tokens_cache[title] = toks
                toks_len = len(toks)
                if q_tokens and toks:
                    toks_set = set(toks)
                    inter = len(q_tokens & toks_set)
                    union = len(q_tokens | toks_set)
                    pct = (inter / float(union)) if union else 0.0

            score = getattr(res, "score", 0.0) or 0.0
            # Sort by exact match, similarity, score, and token length
            return (not exact, -pct, -score, toks_len, t_norm)

        items.sort(key=key)

        paginator = DiggPaginator(items, page_size)
        page_num = self.request.GET.get("page") or 1
        try:
            page = paginator.page(page_num)
        except InvalidPage:
            page = paginator.page(1)

        # Preserve the return signature expected by ListView/AldrynSearchView
        return paginator, page, page.object_list, (paginator.num_pages > 1)
