"""Shared immutable application constants.

Constants used by more than one module belong here. Importing them explicitly
prevents runtime NameError exceptions after code has been split into modules.
"""

from anno_translator.version import APP_VERSION

APP_NAME = f"Anno XML Translator by gz2k2 {APP_VERSION}"
APP_NAME_SHORT = "Anno XML Translator"

# Support link opened by the Ko-fi button in the application header.
KOFI_URL = "https://ko-fi.com/gz2k2"

AVAILABLE_LANGUAGES = {
    # Text in GUI - Languange Code Argos Translate - Filename
    # "English (en)": ("en", "english"),  # "en" is the language code used by Argos Translate, english is the file-name convention texts_english.xml
    # Argos Language Codes: https://www.argosopentech.com/argospm/index/

    # Anno 1800 file-name conventions.
    "Brazilian (pt-BR)": ("pb", "brazilian"),
    "Chinese (zh-CN)": ("zh", "chinese"),
    "English (en)": ("en", "english"),
    "French (fr)": ("fr", "french"),
    "German (de)": ("de", "german"),
    "Italian (it)": ("it", "italian"),
    "Japanese (ja)": ("ja", "japanese"),
    "Korean (ko)": ("ko", "korean"),
    "Polish (pl)": ("pl", "polish"),
    "Portuguese (pt-PT)": ("pt", "portuguese"),
    "Russian (ru)": ("ru", "russian"),
    "Spanish (es)": ("es", "spanish"),
    "Taiwanese (zh-TW)": ("zt", "taiwanese"),

    # Anno 117 uses additional file-name variants.
    "Simplified Chinese (zh, Anno 117)": ("zh", "simplified_chinese"),
    "Traditional Chinese (zt, Anno 117)": ("zt", "traditional_chinese"),
}

# XML comment marker that protects the following element from translation.
# Placed directly in front of a <Text> node (or in front of a block that
# contains <Text> nodes), the affected texts are copied to every output file
# unchanged:
#
#     <Text>
#       <!--!DONOTTRANSLATE-->
#       <Text>_____Test001_____</Text>
#       <LineId>2144000003</LineId>
#     </Text>
#
# Comparison is case-insensitive and ignores whitespace, a leading "!" and any
# underscores/hyphens, so "<!-- do_not_translate -->" works as well. Both the
# correct spelling and the common one-T variant are accepted, because a silently
# ignored marker would translate texts the user explicitly protected.
DO_NOT_TRANSLATE_MARKERS = frozenset({"DONOTTRANSLATE", "DONOTRANSLATE"})

# XML texts are joined with this delimiter for batch processing and split again
# after translation. Keep the value consistent across all translation modules.
BATCH_TEXT_DELIMITER = "\n"

# Target languages whose models are known to destroy or silently delete inline
# placeholder tokens. Observed with de -> zt: "0_Praefectus Lucius (Produktion)"
# was returned as "(制作)", i.e. the protected name was dropped entirely, which
# no placeholder repair strategy can recover.
#
# For these languages the translator uses segmentation instead of placeholders:
# protected names are cut out of the text before translation and reinserted
# afterwards, so they can never reach the model in the first place.
PLACEHOLDER_UNSAFE_LANGUAGES = {"zh", "zt", "ja", "ko"}

# A placeholder at the very end of a text is treated as trailing junk by most
# models and is simply dropped. Observed with de -> pb: every text of the form
# "Rekrutierungszentrum: <name>" lost its placeholder. Such texts therefore skip
# the placeholder route and use segmentation right away.
#
# After this many placeholder failures, a language route switches to
# segmentation for the rest of the run instead of retrying and discarding.
PLACEHOLDER_FAILURE_LIMIT = 3

# Maximum number of detailed placeholder warnings logged per language route.
# Further occurrences are counted but no longer printed individually.
PLACEHOLDER_WARNING_LIMIT = 2
