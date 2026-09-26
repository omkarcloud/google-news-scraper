"""Marshmallow request schemas for every /google-news/* route.

Generic fields live in the shared schema_fields.py; this module adds the
Google News resolvers (google_news/refs.py) and per-route schemas. Every
schema's load() output is the kwargs dict its endpoint function takes.

ONE param per input (tripadvisor QueryOrLinkField convention, never a
sibling `url` / `id` pair):
    topic        WORLD | BUSINESS | … | a topic id | a news.google.com/topics link
                 (a link with /sections/<id> also fills `section`)
    section      a tab name (Markets) | a section id | a /sections/ link
    publication  cnn.com | https://www.cnn.com | a publication id | its Google News link
    location     a place name | a place topic id | its Google News link
    author       authors[].id of any article | its Google News link
    story        story.id of any article | a news.google.com/stories link
    article      an article id | a news.google.com article link

Every feed takes `country` (ISO code, default US) + `language` (ISO code,
default: the country's main edition); the pair is validated against the
editions Google serves and handed to the endpoint as `edition` ("IN:hi").
"""
from marshmallow import ValidationError, post_load, validate, validates_schema

from google_news import refs
from google_news.editions import COUNTRY_NAMES, resolve_edition
from google_news.search import TIME_WINDOWS
from schema_fields import (BaseSchema, ChoiceField, DateField, Flag, PageField, QueryField, RefField,
                           StrippedString)

MAX_PAGE = 10


# ---- fields ------------------------------------------------------------------------------------------------------

class TopicField(RefField):
    resolver = staticmethod(refs.resolve_topic)


class SectionField(RefField):
    resolver = staticmethod(refs.resolve_section)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Length(max=500))
        super().__init__(**kwargs)


class PublicationField(RefField):
    resolver = staticmethod(refs.resolve_publication)


class LocationField(RefField):
    resolver = staticmethod(refs.resolve_location)


class AuthorField(RefField):
    resolver = staticmethod(refs.resolve_author)


class StoryField(RefField):
    resolver = staticmethod(refs.resolve_story)


class ArticleField(RefField):
    resolver = staticmethod(refs.resolve_article)


class SourceField(RefField):
    resolver = staticmethod(refs.resolve_source)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)


class CountryField(StrippedString):
    """ISO country code of the edition (US, GB, IN, …), default US."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", "US")
        kwargs.setdefault("validate", validate.Length(equal=2, error="Must be a 2-letter ISO country code."))
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        return value.upper() if value else "US"


class LanguageField(StrippedString):
    """ISO language code of the edition (en, hi, es, …); default: the
    country's main edition."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Length(min=2, max=10))
        super().__init__(**kwargs)


# ---- base schemas ------------------------------------------------------------------------------------------------

class EditionSchema(BaseSchema):
    """country + language -> edition (the ceid the endpoint takes)."""
    country = CountryField()
    language = LanguageField()

    @post_load
    def to_edition(self, data, **kwargs):
        country, language = data.pop("country", None), data.pop("language", None)
        try:
            data["edition"] = resolve_edition(country, language)
        except ValueError as e:
            field = "language" if (country or "US").upper().replace("UK", "GB") in COUNTRY_NAMES else "country"
            raise ValidationError(str(e), field_name=field)
        return data


class PagedEditionSchema(EditionSchema):
    page = PageField(max_page=MAX_PAGE)


# ---- routes ------------------------------------------------------------------------------------------------------

class EditionsSchema(BaseSchema):
    country = StrippedString(required=False, load_default=None, validate=validate.Length(equal=2))

    @post_load
    def upper(self, data, **kwargs):
        if data.get("country"):
            data["country"] = data["country"].upper().replace("UK", "GB")
        return data


class TopicsSchema(EditionSchema):
    pass


def _split_topic(data):
    ref = data.pop("topic")
    data["topic"] = ref["topic"]
    if ref.get("section") and not data.get("section"):
        data["section"] = ref["section"]
    return data


class TopicDetailsSchema(EditionSchema):
    topic = TopicField()
    section = SectionField()

    @post_load
    def split(self, data, **kwargs):
        return _split_topic(data)


class TopicArticlesSchema(PagedEditionSchema):
    topic = TopicField()
    section = SectionField()

    @post_load
    def split(self, data, **kwargs):
        return _split_topic(data)


class TopHeadlinesSchema(PagedEditionSchema):
    pass


class LocalHeadlinesSchema(PagedEditionSchema):
    location = LocationField(validate=validate.Length(max=300))


class PublicationDetailsSchema(EditionSchema):
    publication = PublicationField(validate=validate.Length(max=500))


class PublicationArticlesSchema(PagedEditionSchema):
    publication = PublicationField(validate=validate.Length(max=500))
    section = SectionField()


class AuthorArticlesSchema(PagedEditionSchema):
    author = AuthorField(validate=validate.Length(max=500))


class HomeSchema(EditionSchema):
    pass


class ShowcaseSchema(PagedEditionSchema):
    pass


class SearchSchema(PagedEditionSchema):
    query = QueryField(max_length=300)
    time_published = ChoiceField(list(TIME_WINDOWS), load_default="anytime")
    from_date = DateField(bound="past")
    to_date = DateField(bound="past")
    source = SourceField(validate=validate.Length(max=300))
    in_title = Flag(load_default=False)
    sort = ChoiceField(["relevance", "newest", "oldest"], load_default="relevance")
    resolve_links = Flag(load_default=True)

    @validates_schema
    def dates_in_order(self, data, **kwargs):
        if data.get("from_date") and data.get("to_date") and data["from_date"] > data["to_date"]:
            raise ValidationError("from_date must be on or before to_date.", field_name="from_date")


class StorySchema(EditionSchema):
    story = StoryField(validate=validate.Length(max=500))


class ArticleResolveSchema(BaseSchema):
    article = ArticleField(validate=validate.Length(max=2000))


class AutocompleteSchema(EditionSchema):
    query = QueryField(max_length=200)

