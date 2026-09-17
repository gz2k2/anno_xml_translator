# Refactored Architecture

## Files

- `Anno_XML_Translator.py`: Application entry point, window construction, tabview UI (Main Menu, Languages, Settings, Translation Settings), and UI event handling.
- `anno_translator/version.py`: Application version string (`APP_VERSION`).
- `anno_translator/constants.py`: Shared constants, application names (`APP_NAME` formatted with version, `APP_NAME_SHORT`), language mappings, and delimiters.
- `anno_translator/config_manager.py`: Settings, language profiles, and legacy configuration migration.
- `anno_translator/quality_manager.py`: Proper names, defined name translations, translation memory, and INI file CRUD services.
- `anno_translator/default_translation_data.py`: Immutable Python default dictionary definitions for proper names and name translations (always active and merged with INI files).
- `anno_translator/translation_engine.py`: Argos model management, downloads, XML translation, batching, and parallel execution.
- `anno_translator/paths.py`: Application directory path resolution.
- `anno_translator/__init__.py`: Package marker.

## Design

The application uses focused mixins so the existing CustomTkinter widget state remains available without introducing global variables. Each module has a single primary responsibility, detailed documentation, and explicit imports.

### Configuration & Quality Architecture
- **Tabview Architecture**:
  - `Main Menu`: File input/output, translation execution, status, and live log.
  - `Languages`: Profile selection, save/delete profiles, and target language checkboxes.
  - `Settings`: Translation mode (Sequential/Parallel), batch size, auto-batching threshold, processing mode (GPU/CPU precision), and default output folder.
  - `Translation Settings`: Fixed exclusions list at top, interactive comboboxes and input masks for managing `name_translations.ini` and `proper_names.ini`.
- **Default Translation Data Integration**:
  - Base translation definitions (such as Anno population tiers `Plebeians`, `Equites`, `Patricians`, etc.) are maintained in `anno_translator/default_translation_data.py`.
  - Quality manager services continuously merge default definitions with user-created entries in `config/name_translations.ini` and `config/proper_names.ini`, guaranteeing that base terms remain available regardless of INI state.

## Start

```bash
python Anno_XML_Translator.py
```

## Build

The existing PyInstaller build script can continue to use `Anno_XML_Translator.py` as its source. PyInstaller analyzes imports from the `anno_translator` package automatically.
