# Refactored Architecture

## Files

- `Anno_XML_Translator.py`: application entry point, window construction, and UI event handling.
- `anno_translator/config_manager.py`: settings, language profiles, and legacy configuration migration.
- `anno_translator/quality_manager.py`: proper names, defined name translations, and translation memory.
- `anno_translator/translation_engine.py`: Argos model management, downloads, XML translation, batching, and parallel execution.
- `anno_translator/__init__.py`: package marker.

## Design

The application uses focused mixins so the existing CustomTkinter widget state remains available without introducing global variables. Each module has a single primary responsibility, detailed English documentation, and explicit imports. Persistent files continue to be stored in the `config` directory next to the script or compiled executable.

## Start

```bash
python Anno_XML_Translator.py
```

## Build

The existing PyInstaller build script can continue to use `Anno_XML_Translator.py` as its source. PyInstaller analyzes imports from the `anno_translator` package automatically.
