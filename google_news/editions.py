"""Google News editions: the (country, language) pairs news.google.com
serves, and the request context every rpc carries.

An edition is named by its `ceid` ("IN:hi"); `hl` is the UI language Google
itself puts in the edition's links (validated 2026-09-26 by fetching every
edition's /rss and reading the channel link back: all 90 answered 200 with
their own ceid). Any other pair is silently canonicalised by Google to one of
these (DK:da -> NO:no, IN:kn -> IN:hi, MX:en -> US:en, …), so the API rejects
it with the list of languages the country does have.

Public params: `country` (ISO code, default US) + `language` (ISO 639-1 base
code: "es" picks US:es-419 in the US and ES:es in Spain, "pt" BR:pt-419 or
PT:pt-150, "zh" CN:zh-Hans or TW/HK:zh-Hant). With no language the country's
default edition (the first listed) is used.
"""

# (ceid, hl) — per country, the default edition first.
EDITIONS = [
    ("US:en", "en-US"), ("US:es-419", "es-419"),
    ("GB:en", "en-GB"), ("CA:en", "en-CA"), ("CA:fr", "fr-CA"), ("AU:en", "en-AU"), ("NZ:en", "en-NZ"),
    ("IE:en", "en-IE"),
    ("IN:en", "en-IN"), ("IN:hi", "hi"), ("IN:bn", "bn"), ("IN:mr", "mr"), ("IN:ta", "ta"), ("IN:te", "te"),
    ("IN:gu", "gu-IN"), ("IN:ml", "ml"), ("IN:pa", "pa-IN"),
    ("PK:en", "en-PK"), ("BD:bn", "bn"), ("SG:en", "en-SG"), ("MY:en", "en-MY"), ("MY:ms", "ms-MY"),
    ("PH:en", "en-PH"), ("ID:id", "id"), ("ID:en", "en-ID"), ("IL:he", "he"), ("IL:en", "en-IL"),
    ("ZA:en", "en-ZA"), ("NG:en", "en-NG"), ("KE:en", "en-KE"), ("GH:en", "en-GH"), ("UG:en", "en-UG"),
    ("TZ:en", "en-TZ"), ("ET:en", "en-ET"), ("BW:en", "en-BW"), ("NA:en", "en-NA"), ("ZW:en", "en-ZW"),
    ("AE:ar", "ar"), ("EG:ar", "ar"), ("SA:ar", "ar"), ("LB:ar", "ar"), ("MA:fr", "fr"), ("SN:fr", "fr"),
    ("FR:fr", "fr"), ("BE:fr", "fr"), ("BE:nl", "nl"), ("CH:de", "de"), ("CH:fr", "fr"), ("DE:de", "de"),
    ("AT:de", "de"), ("NL:nl", "nl"), ("IT:it", "it"), ("ES:es", "es"), ("ES:ca", "ca-ES"),
    ("PT:pt-150", "pt-PT"), ("BR:pt-419", "pt-BR"),
    ("MX:es-419", "es-419"), ("AR:es-419", "es-419"), ("CL:es-419", "es-419"), ("CO:es-419", "es-419"),
    ("PE:es-419", "es-419"), ("VE:es-419", "es-419"), ("CU:es-419", "es-419"),
    ("SE:sv", "sv"), ("NO:no", "no"), ("FI:fi", "fi-FI"), ("PL:pl", "pl"), ("CZ:cs", "cs"), ("SK:sk", "sk"),
    ("HU:hu", "hu"), ("RO:ro", "ro"), ("BG:bg", "bg"), ("GR:el", "el"), ("TR:tr", "tr"),
    ("UA:uk", "uk"), ("UA:ru", "ru"), ("RU:ru", "ru"), ("RS:sr", "sr"), ("SI:sl", "sl"),
    ("LT:lt", "lt"), ("LV:lv", "lv"), ("LV:en", "en-LV"), ("EE:et", "et-EE"),
    ("JP:ja", "ja"), ("KR:ko", "ko"), ("CN:zh-Hans", "zh-CN"), ("TW:zh-Hant", "zh-TW"), ("HK:zh-Hant", "zh-HK"),
    ("VN:vi", "vi"), ("TH:th", "th"),
]

COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia", "NZ": "New Zealand",
    "IE": "Ireland", "IN": "India", "PK": "Pakistan", "BD": "Bangladesh", "SG": "Singapore", "MY": "Malaysia",
    "PH": "Philippines", "ID": "Indonesia", "IL": "Israel", "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya",
    "GH": "Ghana", "UG": "Uganda", "TZ": "Tanzania", "ET": "Ethiopia", "BW": "Botswana", "NA": "Namibia",
    "ZW": "Zimbabwe", "AE": "United Arab Emirates", "EG": "Egypt", "SA": "Saudi Arabia", "LB": "Lebanon",
    "MA": "Morocco", "SN": "Senegal", "FR": "France", "BE": "Belgium", "CH": "Switzerland", "DE": "Germany",
    "AT": "Austria", "NL": "Netherlands", "IT": "Italy", "ES": "Spain", "PT": "Portugal", "BR": "Brazil",
    "MX": "Mexico", "AR": "Argentina", "CL": "Chile", "CO": "Colombia", "PE": "Peru", "VE": "Venezuela",
    "CU": "Cuba", "SE": "Sweden", "NO": "Norway", "FI": "Finland", "PL": "Poland", "CZ": "Czechia",
    "SK": "Slovakia", "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria", "GR": "Greece", "TR": "Türkiye",
    "UA": "Ukraine", "RU": "Russia", "RS": "Serbia", "SI": "Slovenia", "LT": "Lithuania", "LV": "Latvia",
    "EE": "Estonia", "JP": "Japan", "KR": "South Korea", "CN": "China", "TW": "Taiwan", "HK": "Hong Kong",
    "VN": "Vietnam", "TH": "Thailand",
}

LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "hi": "Hindi", "bn": "Bengali", "mr": "Marathi",
    "ta": "Tamil", "te": "Telugu", "gu": "Gujarati", "ml": "Malayalam", "pa": "Punjabi", "ms": "Malay",
    "id": "Indonesian", "he": "Hebrew", "ar": "Arabic", "nl": "Dutch", "de": "German", "it": "Italian",
    "ca": "Catalan", "pt": "Portuguese", "sv": "Swedish", "no": "Norwegian", "fi": "Finnish", "pl": "Polish",
    "cs": "Czech", "sk": "Slovak", "hu": "Hungarian", "ro": "Romanian", "bg": "Bulgarian", "el": "Greek",
    "tr": "Turkish", "uk": "Ukrainian", "ru": "Russian", "sr": "Serbian", "sl": "Slovenian", "lt": "Lithuanian",
    "lv": "Latvian", "et": "Estonian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "vi": "Vietnamese",
    "th": "Thai",
}
# Variants worth naming (the base-code name otherwise).
VARIANT_NAMES = {"es-419": "Spanish (Latin America)", "pt-419": "Portuguese (Brazil)",
                 "pt-150": "Portuguese (Portugal)", "zh-Hans": "Chinese (Simplified)",
                 "zh-Hant": "Chinese (Traditional)"}
# Aliases customers pass for a base code.
LANGUAGE_ALIASES = {"iw": "he", "nb": "no", "nn": "no", "in": "id"}

HL = dict(EDITIONS)
DEFAULT_EDITION = "US:en"

# Experiment flags the site sends in every request context.
_CTX_FLAGS = ["FINANCE_TOP_INDICES", "GENESIS_PUBLISHER_SECTION", "WEB_TEST_1_0_0"]


class Edition:
    """One edition: `ceid` "IN:hi", `country` "IN", `language` "hi" (base
    code), `variant` "hi" / "es-419", `hl` "hi" / "en-US"."""
    __slots__ = ("ceid", "country", "variant", "language", "hl")

    def __init__(self, ceid):
        self.ceid = ceid
        self.country, self.variant = ceid.split(":", 1)
        self.language = self.variant.split("-")[0]
        self.hl = HL[ceid]

    def context(self):
        """The request-context block every rpc carries."""
        head = [self.hl, self.country, _CTX_FLAGS, None, None, 1, 1, self.ceid,
                None, None, None, None, None, None, None, 0]
        return [head, self.hl, self.country, 1, [3, 5, 9, 19], 1, 1, "985646084", 0, 0, None, 0]

    def query(self):
        """The hl / gl / ceid query every news.google.com link carries."""
        return {"hl": self.hl, "gl": self.country, "ceid": self.ceid}

    def summary(self):
        return {"country": self.country, "language": self.language, "edition": self.ceid}


def edition(ceid):
    return Edition(ceid if ceid in HL else DEFAULT_EDITION)


def country_editions(country):
    return [c for c, _hl in EDITIONS if c.split(":")[0] == country]


def resolve_edition(country=None, language=None):
    """(country, language) -> the ceid of a real edition. Raises ValueError
    with the languages the country has when the pair does not exist."""
    country = (country or "US").upper()
    if country == "UK":
        country = "GB"
    options = country_editions(country)
    if not options:
        raise ValueError(f"Google News has no {country} edition. Countries with an edition: "
                         f"{', '.join(sorted(COUNTRY_NAMES))} (see /google-news/editions).")
    if not language:
        return options[0]
    lang = language.replace("_", "-")
    base = LANGUAGE_ALIASES.get(lang.split("-")[0].lower(), lang.split("-")[0].lower())
    for ceid in options:
        variant = ceid.split(":", 1)[1]
        if variant.lower() == lang.lower() or variant.split("-")[0] == base:
            return ceid
    langs = ", ".join(ceid.split(":", 1)[1].split("-")[0] for ceid in options)
    raise ValueError(f"The {COUNTRY_NAMES.get(country, country)} edition of Google News is available in: {langs}.")


def language_name(variant):
    return VARIANT_NAMES.get(variant) or LANGUAGE_NAMES.get(variant.split("-")[0])


def list_editions(country=None):
    """Every edition (optionally one country's), default edition first."""
    rows, seen = [], set()
    for ceid, _hl in EDITIONS:
        code, variant = ceid.split(":", 1)
        if country and code != country:
            continue
        rows.append({
            "country": code,
            "country_name": COUNTRY_NAMES.get(code),
            "language": variant.split("-")[0],
            "language_name": language_name(variant),
            "edition": ceid,
            "is_default": code not in seen,
        })
        seen.add(code)
    return rows
