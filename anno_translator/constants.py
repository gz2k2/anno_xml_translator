"""Shared immutable application constants.

Constants used by more than one module belong here. Importing them explicitly
prevents runtime NameError exceptions after code has been split into modules.
"""

APP_NAME = "Anno XML Translator by gz2k2 v0.10 beta"
APP_NAME_SHORT = "Anno XML Translator"

AVAILABLE_LANGUAGES = {
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

# XML texts are joined with this delimiter for batch processing and split again
# after translation. Keep the value consistent across all translation modules.
BATCH_TEXT_DELIMITER = "\n"
