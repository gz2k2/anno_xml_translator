"""Translation-quality data management.

The services in this module manage protected names, language-specific name
translations, and exact-match translation memory. File writes are serialized by
the lock owned by the host application, which avoids corruption during parallel
translation runs.
"""

import configparser
import difflib
import hashlib
import os
import re
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

    # ------------------------------------------------------------------
    # Placeholder configuration
    # ------------------------------------------------------------------
    # Placeholders must survive a round trip through the NMT model. Digit
    # sequences are NOT safe: CJK models (zh / zt) normalize or truncate them,
    # which turned "1A2B0000B2A1" into "1A2B000B2A1". Repeated letters are not
    # safe either: "QzxAAAxzQ" came back as "QzxAAxAzQ", i.e. the model moved a
    # marker character into the token body and destroyed the suffix.
    #
    # Therefore the token body uses an alphabet WITHOUT the marker characters
    # Q/X/Z and never produces two identical characters in a row. This keeps the
    # markers unique, makes damage detectable, and keeps fuzzy repair reliable.
    _TOKEN_PREFIX = "Qzx"
    _TOKEN_SUFFIX = "xzQ"

    # Body alphabet: no Q/X/Z (reserved as markers), no O (confusable with 0).
    _TOKEN_BODY_ALPHABET = "ABCDEFGHIJKLMNPRSTUVWY"

    # Characters that identify a placeholder even when it is mangled.
    _TOKEN_MARKER_CHARS = "qxz"

    # Minimum similarity required before a damaged fragment is accepted as a
    # placeholder. Validated empirically: damaged tokens score >= 0.75, ordinary
    # words score <= 0.35.
    _TOKEN_FUZZY_THRESHOLD = 0.62

    # Index offset so that name-translation tokens can never collide with
    # proper-name tokens (both restore maps are applied to the same string).
    _NAME_TRANSLATION_INDEX_OFFSET = 500

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

        # Never store texts that still contain an unresolved placeholder.
        if self._contains_placeholder_residue(target_text):
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

    # ------------------------------------------------------------------
    # Placeholder creation / protection
    # ------------------------------------------------------------------
    @staticmethod
    def _boundary_pattern(name, flags):
        """Compile a name pattern that cannot match inside a longer identifier.

        Without this guard, the entry "0_Praefectus" also matches inside
        "00_Praefectus" and leaves a stray "0" in front of the placeholder.
        That is exactly what produced the observed Simplified Chinese output
        "0 个0_Praefectus 专家(财务)" for the source "00_Praefectus Specialists".

        Word boundaries are only applied on the side where the name actually
        starts or ends with a word character, so names wrapped in punctuation
        still match correctly.
        """
        prefix = r"(?<!\w)" if re.match(r"\w", name) else ""
        suffix = r"(?!\w)" if re.search(r"\w$", name) else ""
        return re.compile(prefix + re.escape(name) + suffix, flags)

    @classmethod
    def _make_token(cls, index):
        """Build a letters-only placeholder for the given index.

        Each of the three body positions uses a different rotation of the body
        alphabet, so consecutive identical characters cannot occur. Example:
        index 0 -> "QzxAHPxzQ".
        """
        alphabet = cls._TOKEN_BODY_ALPHABET
        size = len(alphabet)
        digits = (
            (index // (size * size)) % size,
            (index // size) % size,
            index % size,
        )
        # Per-position rotation keeps the three characters distinct.
        rotations = (0, 7, 14)
        letters = "".join(
            alphabet[(digit + rotation) % size]
            for digit, rotation in zip(digits, rotations)
        )
        return f"{cls._TOKEN_PREFIX}{letters}{cls._TOKEN_SUFFIX}"

    @classmethod
    def _placeholder_residue_pattern(cls):
        """Return a regex matching any (possibly damaged) placeholder in a text.

        Marker characters directly adjacent to the token are consumed as well,
        so a duplicated marker ("QQzxAHTxzQ") cannot leave a stray character
        behind after the replacement.
        """
        marker_run = f"[{cls._TOKEN_MARKER_CHARS}{cls._TOKEN_MARKER_CHARS.upper()}]*"
        return re.compile(
            marker_run
            + r"\s*".join(re.escape(c) for c in cls._TOKEN_PREFIX)
            + r"\s*(.{0,12}?)\s*"
            + r"\s*".join(re.escape(c) for c in cls._TOKEN_SUFFIX)
            + marker_run,
            flags=re.IGNORECASE,
        )

    @classmethod
    def _token_length_bounds(cls):
        """Return the plausible (min, max) character length of a damaged token."""
        token_length = len(cls._TOKEN_PREFIX) + 3 + len(cls._TOKEN_SUFFIX)
        return max(4, token_length - 4), token_length + 4

    @classmethod
    def _marker_count(cls, text):
        """Count marker characters (q/x/z) in a fragment."""
        return sum(1 for char in text.lower() if char in cls._TOKEN_MARKER_CHARS)

    @classmethod
    def _contains_placeholder_residue(cls, text, restore_map=None):
        """True if the text still contains an unresolved placeholder fragment.

        Without `restore_map` only literal markers are detected. With it, the
        check additionally looks for heavily damaged tokens using a deliberately
        low similarity threshold: a false alarm merely triggers the safe
        segmentation fallback, whereas a missed token would corrupt the export.
        """
        if not text:
            return False

        if cls._placeholder_residue_pattern().search(text):
            return True

        # A lone prefix or suffix also counts as residue.
        if (re.search(re.escape(cls._TOKEN_PREFIX), text, flags=re.IGNORECASE)
                or re.search(re.escape(cls._TOKEN_SUFFIX), text, flags=re.IGNORECASE)):
            return True

        if not restore_map:
            return False

        # Heuristic detection of badly mangled tokens.
        min_length, max_length = cls._token_length_bounds()
        tokens_upper = [token.upper() for token in restore_map]
        detection_threshold = 0.5

        for match in re.finditer(r"[A-Za-z]+", text):
            fragment = match.group(0)
            if not (min_length - 2 <= len(fragment) <= max_length):
                continue
            if cls._marker_count(fragment) < 2:
                continue
            upper_fragment = fragment.upper()
            for token_upper in tokens_upper:
                if difflib.SequenceMatcher(None, upper_fragment, token_upper).ratio() >= detection_threshold:
                    return True
        return False

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
        start_index = self._NAME_TRANSLATION_INDEX_OFFSET
        for index, (source_name, target_name, _section) in enumerate(candidates, start=start_index):
            token = self._make_token(index)
            pattern = self._boundary_pattern(source_name, flags)
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
            token = self._make_token(index)
            pattern = self._boundary_pattern(name, flags)
            if pattern.search(protected):
                protected = pattern.sub(token, protected)
                restore_map[token] = name
        return protected, restore_map

    # ------------------------------------------------------------------
    # Placeholder restoration
    # ------------------------------------------------------------------
    @classmethod
    def _restore_proper_names(cls, text, restore_map):
        """Restore placeholders, tolerating spacing and model-mangled tokens.

        Three passes with increasing tolerance:

        Pass 1 - exact token, whitespace tolerant. Handles the normal case.
        Pass 2 - intact markers, damaged body. Handles dropped, duplicated, or
                 reordered body characters.
        Pass 3 - damaged markers. Scans for letter runs of plausible length that
                 carry at least two marker characters and fuzzy-matches them
                 against the full token. This catches cases such as
                 "QzxAAAxzQ" -> "QzxAAxAzQ", where the model pulled a marker
                 character into the token body and destroyed the suffix.
        """
        if not restore_map:
            return text

        restored = text

        # --- Pass 1: exact token, optionally separated by whitespace. --------
        for token, name in restore_map.items():
            flexible = r"\s*".join(re.escape(char) for char in token)
            restored = re.sub(flexible, name, restored, flags=re.IGNORECASE)

        # --- Pass 2: intact markers, damaged body. ---------------------------
        prefix_len = len(cls._TOKEN_PREFIX)
        suffix_len = len(cls._TOKEN_SUFFIX)
        bodies = {
            token[prefix_len:-suffix_len].upper(): name
            for token, name in restore_map.items()
        }

        def _repair_body(match):
            damaged = re.sub(r"\s+", "", match.group(1)).upper()
            if damaged in bodies:
                return bodies[damaged]
            best = difflib.get_close_matches(damaged, list(bodies), n=1, cutoff=0.3)
            return bodies[best[0]] if best else match.group(0)

        restored = cls._placeholder_residue_pattern().sub(_repair_body, restored)

        # --- Pass 3: damaged markers, whole-token fuzzy match. ---------------
        if not cls._contains_placeholder_residue(restored):
            return restored

        tokens_upper = {token.upper(): name for token, name in restore_map.items()}
        min_length, max_length = cls._token_length_bounds()

        def _best_match(span):
            """Return the name for a fragment that is a damaged token, else None."""
            compact = re.sub(r"\s+", "", span).upper()
            if not (min_length <= len(compact) <= max_length):
                return None

            # A genuine placeholder always carries several marker characters,
            # which is what keeps ordinary words out of this repair path.
            if cls._marker_count(compact) < 2:
                return None

            best_name = None
            best_ratio = cls._TOKEN_FUZZY_THRESHOLD
            for token_upper, name in tokens_upper.items():
                ratio = difflib.SequenceMatcher(None, compact, token_upper).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_name = name
            return best_name

        # Scan word by word. A damaged token is usually one "word", but the
        # model may also have split it across up to three space-separated parts,
        # so short groups of neighboring words are evaluated as well.
        words = list(re.finditer(r"[A-Za-z]+", restored))
        replacements = []
        index = 0
        while index < len(words):
            matched = False
            for group_size in (3, 2, 1):
                if index + group_size > len(words):
                    continue
                start = words[index].start()
                end = words[index + group_size - 1].end()
                span = restored[start:end]
                # Multi-word groups must be separated by spaces only.
                if group_size > 1 and not re.fullmatch(r"[A-Za-z ]+", span):
                    continue
                name = _best_match(span)
                if name is not None:
                    replacements.append((start, end, name))
                    index += group_size
                    matched = True
                    break
            if not matched:
                index += 1

        # Apply from the end so earlier offsets stay valid.
        for start, end, name in reversed(replacements):
            restored = restored[:start] + name + restored[end:]

        return restored

    @classmethod
    def _has_lost_placeholder(cls, text, restore_map):
        """True if an expected name is missing from the translated text.

        This catches the most destructive failure mode, observed with de -> zt:
        the model deletes the placeholder entirely instead of mangling it. No
        repair is possible because nothing is left to match, and the residue
        check cannot fire either. Comparing against the expected replacements is
        the only reliable detection.
        """
        if not restore_map:
            return False
        for name in restore_map.values():
            if name and name not in text:
                return True
        return False

    def warn_about_name_variants(self, texts):
        """Report identifiers that merely contain a protected name.

        Example from the shipped mod files: "0_Praefectus" is protected, but the
        source also contains "00_Praefectus", which is a different identifier and
        therefore stays unprotected. Boundary matching prevents corruption, yet
        the longer variant is still translated, so the user is told to add it.
        """
        protected = set(self.proper_names)
        for _section, translations in self.name_translations:
            protected.update(translations.values())
        protected = {name for name in protected if name}
        if not protected:
            return

        reported = set()
        for text in texts:
            for word in re.findall(r"[\w][\w\-\.]*", text or ""):
                if word in protected or word in reported:
                    continue
                for name in protected:
                    if name in word and name != word:
                        self.log_message(
                            f"WARNING: '{word}' contains the protected name '{name}' "
                            f"but is not protected itself. Add it to proper_names.ini "
                            f"if it should stay untranslated."
                        )
                        reported.add(word)
                        break

    # ------------------------------------------------------------------
    # Placeholder-free fallback
    # ------------------------------------------------------------------
    def get_protected_name_pairs(self, source_code, target_code):
        """Return [(source_name, target_name)] for every active protection.

        Used by the segmentation fallback in the translation engine, which
        avoids placeholders entirely by translating only the text fragments
        between the protected names. Sorted longest-first so that a longer name
        is matched before a shorter name contained in it.
        """
        pairs = []

        if self.name_translations_enabled_var.get() and self.name_translations:
            source_key = source_code.casefold()
            target_key = target_code.casefold()
            for _section, translations in self.name_translations:
                source_name = translations.get(source_key)
                if source_name:
                    pairs.append((source_name, translations.get(target_key, source_name)))

        if self.proper_names_enabled_var.get():
            # Proper names are kept identical in every target language.
            for name in self.proper_names:
                pairs.append((name, name))

        pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
        return pairs

    def split_on_protected_names(self, text, pairs):
        """Split text into [(fragment, replacement_or_None)] segments.

        A segment with a replacement is a protected name and must not be sent to
        the translation model at all. Every other segment is free text.
        """
        if not pairs:
            return [(text, None)]

        # Case sensitivity is only enforced when BOTH features request it.
        flags = 0
        if not (self.name_translations_case_sensitive and self.proper_names_case_sensitive):
            flags = re.IGNORECASE

        lookup = {}
        alternatives = []
        for index, (source_name, target_name) in enumerate(pairs):
            group = f"n{index}"
            lookup[group] = target_name
            # Same boundary guard as the placeholder route, so a shorter name
            # cannot match inside a longer identifier.
            left = r"(?<!\w)" if re.match(r"\w", source_name) else ""
            right = r"(?!\w)" if re.search(r"\w$", source_name) else ""
            alternatives.append(f"{left}(?P<{group}>{re.escape(source_name)}){right}")

        pattern = re.compile("|".join(alternatives), flags)

        segments = []
        position = 0
        for match in pattern.finditer(text):
            if match.start() > position:
                segments.append((text[position:match.start()], None))
            group = match.lastgroup
            segments.append((match.group(0), lookup.get(group, match.group(0))))
            position = match.end()

        if position < len(text):
            segments.append((text[position:], None))

        return segments or [(text, None)]
