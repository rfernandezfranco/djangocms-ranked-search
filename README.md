# Django CMS Ranked Search

Django CMS Ranked Search is a drop-in enhancement for django CMS projects that rely on
Haystack. It boosts the most relevant results (titles, exact phrases) while
providing accent-insensitive matching and language-aware scoring.

## Features
- Promotes exact title hits and short, high-quality matches automatically.
- Normalises accents and ligatures.
- Adapts analysers and stopwords to the active language or a configured
  fallback.
- Works with the standard Aldryn Search view, preserving pagination and layout.

## Requirements
Install these dependencies in your django CMS project:

- `Django>=3.2`
- `django-cms>=3.11`
- `django-haystack>=3.2`
- `aldryn-search>=2.0`
- `Whoosh>=2.7`

Optional (only if you plan to use Xapian):

- Extra `xapian`: `haystack-xapian>=1.2.3`

## Installation
1. Install the package (and optional Xapian extra if required):
   ```bash
   pip install djangocms-ranked-search
   pip install "djangocms-ranked-search[xapian]"  # with Xapian support
   ```
2. Add the app to `INSTALLED_APPS`:
   ```python
   INSTALLED_APPS = [
       # ...
       "djangocms_ranked_search",
   ]
   ```
3. Configure your Haystack connection:
   ```python
   HAYSTACK_CONNECTIONS = {
       "default": {
           "ENGINE": "djangocms_ranked_search.whoosh_backend.WhooshLangEngine",
           "PATH": os.path.join(BASE_DIR, "whoosh_index"),
       }
   }
   # Switch ENGINE to "djangocms_ranked_search.xapian_backend.XapianLangEngine"
   # when using Xapian.
   ```
4. Publish a search page in django CMS and select **Search (Ranked)** as the
   application.
5. Rebuild the index:
   ```bash
   python manage.py clear_index --noinput
   python manage.py rebuild_index --noinput
   ```

## Configuration
All settings are optional and live in `settings.py`.

- `RANKED_SEARCH_LANGUAGE`: base language code used for analyzers
  (defaults to the project language).
- `RANKED_SEARCH_KEEP_ENYE`: keep the distinction between "ñ" and "n" when
  normalising (boolean).
- `RANKED_SEARCH_FOLDING_PROFILE`: per-language rules describing which
  characters to preserve or replace. Example:
  ```python
  RANKED_SEARCH_FOLDING_PROFILE = {
      "default": {"preserve": [], "replace": {}},
      "es": {"preserve": ["ñ", "Ñ"]},
      "de": {"replace": {"ß": "ss", "ẞ": "SS"}},
      "fr": {"replace": {"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"}},
  }
  ```
- `RERANK_LANGUAGE`: force reranking to use a specific language code or "auto"
  to follow project defaults.
- `RERANK_POOL`: maximum number of results re-evaluated in memory (defaults to
  `max(10 * page_size, 200)`).
- `RERANK_CEILING`: hard cap applied to `RERANK_POOL`.
- `RERANK_STOPWORDS_ADD` / `RERANK_STOPWORDS_REMOVE`: fine-tune domain-specific
  stopwords utilised during reranking.

> **Rebuild the index** whenever you change folding or language settings so that
> stored data reflects the new behaviour.

## Usage
- Navigate to the published **Search (Ranked)** page.
- Enter queries with or without accents and review the elevated results.
- Each entry displays the familiar title, snippet, and link arranged by
  relevance.

## Tips & Maintenance
- Adjust `RANKED_SEARCH_FOLDING_PROFILE` or `RANKED_SEARCH_KEEP_ENYE` if certain
  characters require special handling.
- Re-run `rebuild_index` after large content imports or configuration changes to
  keep search results consistent.

## Support & Compatibility
Django CMS Ranked Search can run alongside existing search pages. Create a dedicated
page for evaluation, then replace your legacy view once you are satisfied with
ranking quality.
