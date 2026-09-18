"""Default data definitions for proper names and name translations.

Edit these dictionaries to easily add, modify, or remove default entries.
These default entries are always active and merged with any entries from INI files.
"""

DEFAULT_PROPER_NAMES = {
}

DEFAULT_PROPER_NAMES_SETTINGS = {
    "case_sensitive": "false"
}

DEFAULT_NAME_TRANSLATIONS_SETTINGS = {
    "case_sensitive": "false"
}

# Each section key represents one logical proper name or term.
# Each inner dictionary maps language codes (de, en, fr, etc.) to translation text.
DEFAULT_NAME_TRANSLATIONS = {
    "Plebeians": {
        "pb": "Plebeus",
        "en": "Plebeians",
        "fr": "Plébéiens",
        "de": "Plebejer",
        "it": "Plebei",
        "ja": "プレブス",
        "ko": "평민",
        "pl": "Plebejusze",
        "ru": "Плебеи",
        "zh": "平民",
        "es": "Plebeyos",
        "zt": "平民"
    },
    "Equites": {
        "pb": "Equites",
        "en": "Equites",
        "fr": "Equites",
        "de": "Equites",
        "it": "Equites",
        "ja": "エクィテス",
        "ko": "기사",
        "pl": "Ekwici",
        "ru": "Эквиты",
        "zh": "骑士",
        "es": "Équites",
        "zt": "騎士"
    },
    "Patricians": {
        "pb": "Patrícios",
        "en": "Patricians",
        "fr": "Patriciens",
        "de": "Patrizier",
        "it": "Patrizi",
        "ja": "パトリキ",
        "ko": "파트리키",
        "pl": "Patrycjusze",
        "ru": "Патриции",
        "zh": "贵族",
        "es": "Patricios",
        "zt": "貴族"
    },
    "Liberti": {
        "pb": "Liberti",
        "en": "Liberti",
        "fr": "Liberti",
        "de": "Liberti",
        "it": "Liberti",
        "ja": "リベルトゥス",
        "ko": "자유민",
        "pl": "Wyzwoleńcy",
        "ru": "Либертины",
        "zh": "自由民",
        "es": "Libertos",
        "zt": "自由民"
    },
    "Waders": {
        "pb": "Pernaltas",
        "en": "Waders",
        "fr": "Tourbiers",
        "de": "Wanderer",
        "it": "Limicoli",
        "ja": "ウェーダー",
        "ko": "물지기",
        "pl": "Wędrowcy",
        "ru": "Болотники",
        "zh": "沼人",
        "es": "Légamos",
        "zt": "沼人"
    },
    "Smiths": {
        "pb": "Ferreiros",
        "en": "Smiths",
        "fr": "Forgerons",
        "de": "Schmiede",
        "it": "Fabbri",
        "ja": "スミス",
        "ko": "대장장이",
        "pl": "Rzemieślnicy",
        "ru": "Кузнецы",
        "zh": "铁匠",
        "es": "Forjeros",
        "zt": "鐵匠"
    },
    "Aldermen": {
        "pb": "Edis",
        "en": "Aldermen",
        "fr": "Aldermen",
        "de": "Älteste",
        "it": "Aldermanni",
        "ja": "アルダー",
        "ko": "장로",
        "pl": "Starsi",
        "ru": "Олдермены",
        "zh": "长老",
        "es": "Álderes",
        "zt": "長老"
    },
    "Mercators": {
        "pb": "Mercatores",
        "en": "Mercators",
        "fr": "Mercators",
        "de": "Mercatoren",
        "it": "Mercator",
        "ja": "メルカトル",
        "ko": "상인",
        "pl": "Merkatorzy",
        "ru": "Меркаторы",
        "zh": "商人",
        "es": "Mercadores",
        "zt": "商人"
    },
    "Nobles": {
        "pb": "Nobres",
        "en": "Nobles",
        "fr": "Nobles",
        "de": "Edelmänner",
        "it": "Nobili",
        "ja": "ノビレス",
        "ko": "귀족",
        "pl": "Wielmożowie",
        "ru": "Кельтская знать",
        "zh": "领主",
        "es": "Nobles",
        "zt": "領主"
    }
}
