"""Translation-quality data management.

The services in this module manage protected names, language-specific name
translations, and exact-match translation memory. File writes are serialized by
the lock owned by the host application, which avoids corruption during parallel
translation runs.
"""

import configparser
import hashlib
import os
import re
import subprocess
import sys

from tkinter import messagebox
from anno_translator.default_translation_data import (
    DEFAULT_PROPER_NAMES,
    DEFAULT_PROPER_NAMES_SETTINGS,
    DEFAULT_NAME_TRANSLATIONS,
    DEFAULT_NAME_TRANSLATIONS_SETTINGS,
)


class TranslationQualityMixin:
    """Manage terminology protection and persistent translation memory."""

    def _get_selected_compute_type(self):
        """Return the internal compute type for the user-friendly dropdown label."""
        selected_value = self.compute_combo.get()
        return self.compute_type_labels.get(selected_value, selected_value)
    def _ensure_quality_files(self):
        """Create editable INI files for protected proper names and translation memory."""
        if not os.path.exists(self.proper_names_file):
            config = configparser.ConfigParser(interpolation=None)
            config.optionxform = str
            config["ProperNames"] = DEFAULT_PROPER_NAMES
            config["Settings"] = DEFAULT_PROPER_NAMES_SETTINGS
            with open(self.proper_names_file, "w", encoding="utf-8") as handle:
                config.write(handle)
        if not os.path.exists(self.name_translations_file):
            config = configparser.ConfigParser(interpolation=None)
            config.optionxform = str
            config["Settings"] = DEFAULT_NAME_TRANSLATIONS_SETTINGS
            for section, entries in DEFAULT_NAME_TRANSLATIONS.items():
                config[section] = entries

            with open(self.name_translations_file, "w", encoding="utf-8") as handle:
                config.write(handle)
        if not os.path.exists(self.translation_memory_file):
            config = configparser.ConfigParser(interpolation=None)
            config.optionxform = str
            config["Info"] = {
                "description": "Automatically generated translation memory. Entries are grouped by language route."
            }
            with open(self.translation_memory_file, "w", encoding="utf-8") as handle:
                config.write(handle)
    def _load_proper_names(self):
        """Load proper names combining default_translation_data and proper_names.ini."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        names_set = {val.strip() for val in DEFAULT_PROPER_NAMES.values() if val.strip()}
        self.proper_names_case_sensitive = False
        try:
            config.read(self.proper_names_file, encoding="utf-8")
            if config.has_section("ProperNames"):
                for _, value in config.items("ProperNames"):
                    if value.strip():
                        names_set.add(value.strip())
            self.proper_names_case_sensitive = config.getboolean(
                "Settings", "case_sensitive", fallback=False
            )
        except Exception as error:
            print(f"Error loading proper_names.ini: {error}")

        self.proper_names = sorted(names_set, key=len, reverse=True)

    def _load_name_translations(self):
        """Load multilingual proper-name definitions combining defaults and name_translations.ini."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        self.name_translations_case_sensitive = False
        try:
            config.read(self.name_translations_file, encoding="utf-8")
            self.name_translations_case_sensitive = config.getboolean(
                "Settings", "case_sensitive", fallback=False
            )
        except Exception as error:
            print(f"Error reading settings from name_translations.ini: {error}")

        merged_data = self.get_name_translations_dict()
        self.name_translations = []
        for section, trans_map in merged_data.items():
            translations = {
                lang.strip().casefold(): value.strip()
                for lang, value in trans_map.items()
                if lang.strip() and value.strip()
            }
            if translations:
                self.name_translations.append((section, translations))

    def get_proper_names_list(self):
        """Return a list of proper name strings loaded combining defaults and proper_names.ini."""
        return list(self.proper_names)

    def save_proper_name(self, new_name, old_name=None):
        """Add or update a proper name entry in proper_names.ini."""
        new_name = new_name.strip()
        if not new_name:
            return False
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        try:
            config.read(self.proper_names_file, encoding="utf-8")
            if not config.has_section("ProperNames"):
                config.add_section("ProperNames")

            # Check if old_name exists and replace it, or update existing key
            found_key = None
            for key, val in config.items("ProperNames"):
                if val.strip() == (old_name or new_name):
                    found_key = key
                    break

            if found_key:
                config.set("ProperNames", found_key, new_name)
            else:
                existing_keys = list(config.options("ProperNames"))
                new_key = f"name_{len(existing_keys) + 1:03d}"
                config.set("ProperNames", new_key, new_name)

            with open(self.proper_names_file, "w", encoding="utf-8") as handle:
                config.write(handle)
            self._load_proper_names()
            return True
        except Exception as error:
            print(f"Error saving proper name to proper_names.ini: {error}")
            return False

    def delete_proper_name(self, name):
        """Delete a proper name entry from proper_names.ini."""
        name = name.strip()
        if not name:
            return False
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        try:
            config.read(self.proper_names_file, encoding="utf-8")
            if config.has_section("ProperNames"):
                for key, val in list(config.items("ProperNames")):
                    if val.strip() == name:
                        config.remove_option("ProperNames", key)
                with open(self.proper_names_file, "w", encoding="utf-8") as handle:
                    config.write(handle)
                self._load_proper_names()
                return True
        except Exception as error:
            print(f"Error deleting proper name from proper_names.ini: {error}")
        return False

    def get_name_translations_dict(self):
        """Return a dictionary of {section_name: {lang_code: text}} merging defaults and name_translations.ini."""
        result = {
            section: dict(entries)
            for section, entries in DEFAULT_NAME_TRANSLATIONS.items()
        }
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        try:
            config.read(self.name_translations_file, encoding="utf-8")
            for section in config.sections():
                if section.casefold() == "settings":
                    continue
                ini_entries = {
                    lang: val for lang, val in config.items(section) if lang.strip() and val.strip()
                }
                if ini_entries:
                    if section in result:
                        result[section].update(ini_entries)
                    else:
                        result[section] = ini_entries
        except Exception as error:
            print(f"Error reading name_translations.ini: {error}")
        return result

    def save_name_translation(self, section_name, translations_dict, old_section_name=None):
        """Add or update a section in name_translations.ini."""
        section_name = section_name.strip()
        if not section_name:
            return False
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        try:
            config.read(self.name_translations_file, encoding="utf-8")

            if old_section_name and old_section_name != section_name and config.has_section(old_section_name):
                config.remove_section(old_section_name)

            if not config.has_section(section_name):
                config.add_section(section_name)
            else:
                for option in list(config.options(section_name)):
                    config.remove_option(section_name, option)

            for lang, text in translations_dict.items():
                if lang.strip() and text.strip():
                    config.set(section_name, lang.strip(), text.strip())

            with open(self.name_translations_file, "w", encoding="utf-8") as handle:
                config.write(handle)
            self._load_name_translations()
            return True
        except Exception as error:
            print(f"Error saving section '{section_name}' to name_translations.ini: {error}")
            return False

    def delete_name_translation(self, section_name):
        """Delete a section from name_translations.ini."""
        section_name = section_name.strip()
        if not section_name:
            return False
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        try:
            config.read(self.name_translations_file, encoding="utf-8")
            if config.has_section(section_name):
                config.remove_section(section_name)
                with open(self.name_translations_file, "w", encoding="utf-8") as handle:
                    config.write(handle)
                self._load_name_translations()
                return True
        except Exception as error:
            print(f"Error deleting section '{section_name}' from name_translations.ini: {error}")
        return False
    def _load_translation_memory(self):
        """Load all source/target pairs from translation_memory.ini."""
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.optionxform = str
        memory = {}
        try:
            config.read(self.translation_memory_file, encoding="utf-8")
            for section in config.sections():
                if not section.startswith("TM_"):
                    continue
                route = config.get(section, "route", fallback="")
                source = config.get(section, "source", fallback=None)
                target = config.get(section, "target", fallback=None)
                if source is not None and target is not None:
                    memory.setdefault(route, {})[source] = target
            self.translation_memory = memory
        except Exception as error:
            print(f"Error loading translation_memory.ini: {error}")
    def clear_translation_memory(self):
        """Delete all translation-memory entries after explicit confirmation."""
        entry_count = sum(len(entries) for entries in self.translation_memory.values())
        confirmed = messagebox.askyesno(
            "Clear Translation Memory",
            "Do you really want to delete the complete Translation Memory?\n\n"
            f"Stored entries: {entry_count}\n\n"
            "This action cannot be undone.",
            icon="warning"
        )
        if not confirmed:
            return

        try:
            config = configparser.ConfigParser(interpolation=None)
            config.optionxform = str
            config["Info"] = {
                "description": (
                    "Automatically generated translation memory. "
                    "Entries are grouped by language route."
                )
            }
            with self.translation_memory_lock:
                with open(self.translation_memory_file, "w", encoding="utf-8") as handle:
                    config.write(handle)
                self.translation_memory = {}

            self.log_message(
                f"Translation Memory cleared successfully. Deleted entries: {entry_count}."
            )
            messagebox.showinfo(
                "Translation Memory",
                "Translation Memory was cleared successfully.\n\n"
                f"Deleted entries: {entry_count}"
            )
        except Exception as error:
            self.log_message(f"ERROR clearing Translation Memory: {error}")
            messagebox.showerror(
                "Translation Memory Error",
                f"Translation Memory could not be cleared:\n\n{error}"
            )
    def reload_quality_files(self):
        self._load_proper_names()
        self._load_name_translations()
        self._load_translation_memory()
        self.log_message(
            f"Reloaded quality files: {len(self.proper_names)} protected names, "
            f"{len(self.name_translations)} translated names, "
            f"{sum(len(entries) for entries in self.translation_memory.values())} memory entries."
        )
    def _open_local_file(self, path):
        """Open a local configuration file with the operating system's default editor."""
        try:
            if os.name == "nt":
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception as error:
            messagebox.showerror("Error", f"File could not be opened:\n{error}")
    def _memory_route(self, source_code, target_code):
        return f"{source_code}_to_{target_code}"
    def _get_memory_translation(self, source_code, target_code, source_text):
        route = self._memory_route(source_code, target_code)
        with self.translation_memory_lock:
            return self.translation_memory.get(route, {}).get(source_text)
    def _store_memory_translation(self, source_code, target_code, source_text, target_text):
        """Persist one exact translation pair in an INI section identified by a stable hash."""
        if not source_text or not target_text or source_text == target_text:
            return
        route = self._memory_route(source_code, target_code)
        with self.translation_memory_lock:
            route_memory = self.translation_memory.setdefault(route, {})
            if source_text in route_memory:
                return
            route_memory[source_text] = target_text
            config = configparser.ConfigParser(interpolation=None, strict=False)
            config.optionxform = str
            config.read(self.translation_memory_file, encoding="utf-8")
            digest = hashlib.sha256((route + "\0" + source_text).encode("utf-8")).hexdigest()[:16]
            section = f"TM_{route}_{digest}"
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, "route", route)
            config.set(section, "source", source_text)
            config.set(section, "target", target_text)
            with open(self.translation_memory_file, "w", encoding="utf-8") as handle:
                config.write(handle)
    def _protect_translated_names(self, text, source_code, target_code):
        """Protect a source-language proper name and restore its defined target-language form."""
        if not self.name_translations_enabled_var.get() or not self.name_translations:
            return text, {}

        source_code = source_code.casefold()
        target_code = target_code.casefold()
        flags = 0 if self.name_translations_case_sensitive else re.IGNORECASE
        candidates = []
        for section, translations in self.name_translations:
            source_name = translations.get(source_code)
            if not source_name:
                continue
            target_name = translations.get(target_code, source_name)
            candidates.append((source_name, target_name, section))

        candidates.sort(key=lambda item: len(item[0]), reverse=True)
        protected = text
        restore_map = {}
        for index, (source_name, target_name, _section) in enumerate(candidates):
            token = f"ZXQNAME{index:04d}QXZ"
            pattern = re.compile(re.escape(source_name), flags)
            if pattern.search(protected):
                protected = pattern.sub(token, protected)
                restore_map[token] = target_name
        return protected, restore_map
    def _protect_proper_names(self, text):
        """Replace configured proper names with robust placeholders and return a restore map."""
        if not self.proper_names_enabled_var.get() or not self.proper_names:
            return text, {}
        flags = 0 if self.proper_names_case_sensitive else re.IGNORECASE
        protected = text
        restore_map = {}
        for index, name in enumerate(self.proper_names):
            token = f"ZXQPROPER{index:04d}QXZ"
            pattern = re.compile(re.escape(name), flags)
            if pattern.search(protected):
                protected = pattern.sub(token, protected)
                restore_map[token] = name
        return protected, restore_map
    @staticmethod
    def _restore_proper_names(text, restore_map):
        restored = text
        for token, name in restore_map.items():
            # Models may insert spaces around the placeholder; accept those variants too.
            flexible = r"\s*".join(re.escape(char) for char in token)
            restored = re.sub(flexible, name, restored, flags=re.IGNORECASE)
        return restored
