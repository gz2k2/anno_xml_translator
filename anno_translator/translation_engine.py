"""Argos model acquisition and XML translation workflows.

This module contains the computational work of the application: model lookup,
download, protected-fragment translation, sequential processing, and concurrent
processing. UI updates are delegated to methods supplied by the main window.
"""

import fnmatch
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import argostranslate.package
import argostranslate.translate
import requests
from tkinter import messagebox

from .constants import (
    AVAILABLE_LANGUAGES,
    BATCH_TEXT_DELIMITER,
    DO_NOT_TRANSLATE_MARKERS,
    PLACEHOLDER_FAILURE_LIMIT,
    PLACEHOLDER_UNSAFE_LANGUAGES,
    PLACEHOLDER_WARNING_LIMIT,
)


class TranslationEngineMixin:
    """Provide model management and complete translation workflows."""

    def get_user_exclusions(self):
        """
        Parses custom exclusion words and characters from the UI input field.

        Returns:
            list: List of stripped strings serving as translation exclusions.
        """
        raw_text = self.exclude_entry.get()
        if not raw_text:
            return []
        exclusions = [item.strip() for item in raw_text.split(",") if item.strip()]
        return exclusions

    def format_seconds(self, seconds):
        """Converts raw seconds into a formatted HH:MM:SS time string."""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def detect_source_language_code(self):
        """
        Attempts to guess the source file's language code based on its filename prefix or suffix.
        Defaults to 'de' (German) if no matching pattern is found.
        """
        filename = os.path.basename(self.selected_file).lower()
        for _, (code, suffix) in AVAILABLE_LANGUAGES.items():
            if f"_{suffix}" in filename or f"-{suffix}" in filename:
                return code
        return "de"

    def download_file_with_progress(self, url, dest_path):
        """
        Downloads a remote file via URL while streaming real-time progress updates to the GUI progress bar.

        Args:
            url (str): Direct HTTP download link.
            dest_path (str): Local destination path where the file will be saved.

        Returns:
            bool: True if downloaded completely, False if canceled or failed.
        """
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_length = response.headers.get('content-length')
        total_bytes = int(total_length) if total_length else 0
        downloaded_bytes = 0
        chunk_size = 1024 * 1024  # 1MB chunk size
        start_time = time.time()

        with open(dest_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if self.cancel_requested:
                    break
                if chunk:
                    file.write(chunk)
                    downloaded_bytes += len(chunk)

                    now = time.time()
                    elapsed = now - start_time
                    speed_mb = (downloaded_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0

                    if total_bytes > 0:
                        progress = downloaded_bytes / total_bytes
                        percent = progress * 100

                        if total_bytes >= 1024 * 1024 * 1024:
                            downloaded_str = f"{downloaded_bytes / (1024**3):.2f}"
                            total_str = f"{total_bytes / (1024**3):.2f} GB"
                        else:
                            downloaded_str = f"{downloaded_bytes / (1024**2):.1f}"
                            total_str = f"{total_bytes / (1024**2):.1f} MB"

                        status_text = f"Download: {percent:.1f}% - {downloaded_str}/{total_str} ({speed_mb:.2f} MB/s)"

                        # Thread-safe UI updates using self.after
                        self.after(0, lambda p=progress, s=status_text: (
                            self.progress.set(p),
                            self.status_label.configure(text=s)
                        ))

        return downloaded_bytes == total_bytes or total_bytes == 0

    def get_translation_function(self, source_code, target_code):
        """
        Retrieves a callable translation function from Argos Translate.
        If a direct translation model is missing, it sets up a pivot translation route via English.
        Also wraps the return function to handle ignored characters, delimiter splitting, and underscore preservation.

        Args:
            source_code (str): Source language abbreviation code.
            target_code (str): Target language abbreviation code.

        Returns:
            Callable[[str], str] or None: Wrapped string-to-string translation function.
        """
        installed_languages = argostranslate.translate.get_installed_languages()
        from_lang = next((x for x in installed_languages if x.code == source_code), None)
        to_lang = next((x for x in installed_languages if x.code == target_code), None)

        base_fn = None

        # 1. Try direct translation route
        if from_lang and to_lang:
            translation_obj = from_lang.get_translation(to_lang)
            if translation_obj:
                try:
                    translation_obj.underlying_translation.argos_model.device = "cuda"
                    translation_obj.underlying_translation.argos_model.compute_type = self._get_selected_compute_type()
                except Exception:
                    pass
                base_fn = lambda text: translation_obj.translate(text)

        # 2. Fallback: Pivot via English (e.g., German -> English -> Japanese)
        if not base_fn and source_code != "en" and target_code != "en":
            en_lang = next((x for x in installed_languages if x.code == "en"), None)
            if from_lang and en_lang and to_lang:
                trans1 = from_lang.get_translation(en_lang)
                trans2 = en_lang.get_translation(to_lang)
                if trans1 and trans2:
                    for t in (trans1, trans2):
                        try:
                            t.underlying_translation.argos_model.device = "cuda"
                            t.underlying_translation.argos_model.compute_type = self._get_selected_compute_type()
                        except Exception:
                            pass
                    # Chain translations sequentially
                    base_fn = lambda text: trans2.translate(trans1.translate(text))

        if not base_fn:
            return None

        # ------------------------------------------------------------------
        # Underscores are never sent to the model: the text
        # is cut at every underscore run, only the fragments in between are
        # translated, and the runs are re-inserted verbatim. This cannot fail.
        # ------------------------------------------------------------------
        _underscore_run = re.compile(r"_+")
        # Matches any letter (including CJK/Cyrillic) but no digits and no "_".
        _contains_letter = re.compile(r"[^\W\d_]", re.UNICODE)

        _raw_base_fn = base_fn

        # A fragment cut out of an underscore text is not a sentence, but the
        # model still treats it as one and appends final punctuation. Observed
        # with de -> pb: "_____Test001_____" came back as "_____Teste001._____".
        # Punctuation that the source fragment did not have is therefore removed
        # again. Only characters that were ADDED are stripped, so a fragment that
        # legitimately ends with "." or "!" keeps its punctuation.
        _added_punctuation = ".。．,，;；:：!！?？、"

        def _strip_added_punctuation(source_core: str, translated_core: str) -> str:
            """Remove trailing punctuation the model invented for a fragment."""
            if not translated_core:
                return translated_core
            source_tail = source_core.rstrip()[-1:] if source_core.rstrip() else ""
            if source_tail and source_tail in _added_punctuation:
                # The source itself ends with punctuation: keep the translation.
                return translated_core
            cleaned = translated_core.rstrip()
            while cleaned and cleaned[-1] in _added_punctuation:
                cleaned = cleaned[:-1].rstrip()
            # Never return an empty string if the model produced actual content.
            return cleaned or translated_core

        def _translate_fragment(fragment: str) -> str:
            """Translate one fragment; pure numbers/symbols stay untouched."""
            if not fragment or not _contains_letter.search(fragment):
                return fragment
            leading, core, trailing = re.match(
                r'^(\s*)(.*?)(\s*)$', fragment, re.DOTALL
            ).groups()
            if not core:
                return fragment
            translated_core = _raw_base_fn(core)
            translated_core = "" if translated_core is None else str(translated_core)
            translated_core = _strip_added_punctuation(core, translated_core)
            return f"{leading}{translated_core}{trailing}"

        def _translate_keeping_underscores(text: str) -> str:
            """Translate a text while preserving every underscore run exactly."""
            if not text:
                return text
            text = str(text)
            if "_" not in text:
                return _raw_base_fn(text)

            rebuilt = []
            position = 0
            for match in _underscore_run.finditer(text):
                rebuilt.append(_translate_fragment(text[position:match.start()]))
                rebuilt.append(match.group(0))  # underscore run, verbatim
                position = match.end()
            rebuilt.append(_translate_fragment(text[position:]))
            return "".join(rebuilt)

        _punctuation_class = "[" + re.escape(_added_punctuation) + "]"
        _punct_before_underscore = re.compile(rf"{_punctuation_class}+\s*(?=_)")
        _punct_after_underscore = re.compile(rf"(?<=_)\s*{_punctuation_class}+")
        _punct_at_end = re.compile(rf"\s*{_punctuation_class}+\s*$")

        def _clean_underscore_punctuation(source: str, result: str) -> str:
            """Remove invented punctuation around underscore runs.

            The fragment-level cleanup only covers texts that were translated by
            '_translate_keeping_underscores'. A result can also come from the
            segmentation fallback or straight from the Translation Memory, where
            a previously stored bad value would reappear unchanged. This final
            pass therefore runs on every result: punctuation is only removed at
            positions where the SOURCE has none, so legitimate punctuation is
            never lost.
            """
            if not source or not result or "_" not in source:
                return result
            cleaned = result
            if not _punct_before_underscore.search(source):
                cleaned = _punct_before_underscore.sub("", cleaned)
            if not _punct_after_underscore.search(source):
                cleaned = _punct_after_underscore.sub("", cleaned)
            if not _punct_at_end.search(source):
                cleaned = _punct_at_end.sub("", cleaned)
            return cleaned or result

        base_fn = _translate_keeping_underscores

        # Retrieve dynamic user exclusions list
        exclusions = self.get_user_exclusions()

        def should_exclude(t_str: str) -> bool:
            """Match complete-text exclusions case-insensitively with '*' wildcard support."""
            normalized_text = str(t_str).strip().casefold()
            for exclusion in exclusions:
                pattern = exclusion.strip().casefold()
                if pattern and fnmatch.fnmatchcase(normalized_text, pattern):
                    return True
            return False

        def translate_preserving_markup(text: str) -> str:
            """Translate a text while keeping [...] blocks and <...> tags untouched."""
            if not text:
                return text

            # 1. Custom Parser: Recognizes nested brackets [...] and HTML/XML tags <...>
            parts = []
            current = ""
            depth_square = 0
            depth_angle = 0

            i = 0
            while i < len(text):
                char = text[i]

                if char == '<' and depth_square == 0:
                    if depth_angle == 0 and current:
                        parts.append(current)
                        current = ""
                    depth_angle += 1
                    current += char
                elif char == '>' and depth_square == 0:
                    if depth_angle > 0:
                        depth_angle -= 1
                        current += char
                        if depth_angle == 0:
                            parts.append(current)
                            current = ""
                    else:
                        current += char
                elif char == '[' and depth_angle == 0:
                    if depth_square == 0 and current:
                        parts.append(current)
                        current = ""
                    depth_square += 1
                    current += char
                elif char == ']' and depth_angle == 0:
                    if depth_square > 0:
                        depth_square -= 1
                        current += char
                        if depth_square == 0:
                            parts.append(current)
                            current = ""
                    else:
                        current += char
                else:
                    current += char
                i += 1

            if current:
                parts.append(current)

            # 2. Translate text fragments while preserving formatting blocks
            result = []
            for part in parts:
                is_bracket = part.startswith('[') and part.endswith(']') and len(part) >= 2
                is_html_tag = part.startswith('<') and part.endswith('>') and len(part) >= 2

                if is_bracket or is_html_tag:
                    result.append(part)
                else:
                    if part.strip() and not should_exclude(part):
                        match = re.match(r'^(\s*)(.*?)(\s*)$', part, re.DOTALL)
                        if match:
                            prefix, core, suffix = match.groups()
                            translated_core = base_fn(core)
                            result.append(f"{prefix}{translated_core}{suffix}")
                        else:
                            result.append(str(base_fn(part)))
                    else:
                        result.append(part)

            return "".join(result)

        def translate_by_segmentation(text: str) -> str:
            """Placeholder-free fallback used when a token could not be restored.

            The text is split at the protected names. Only the fragments between
            the names are sent to the model; the names themselves are inserted
            in their defined target form. This cannot fail, but the model loses
            the sentence context around each name, so it is used as a fallback
            only.
            """
            pairs = self.get_protected_name_pairs(source_code, target_code)
            segments = self.split_on_protected_names(text, pairs)

            rebuilt = []
            for fragment, replacement in segments:
                if replacement is not None:
                    rebuilt.append(replacement)
                elif fragment.strip() and not should_exclude(fragment):
                    match = re.match(r'^(\s*)(.*?)(\s*)$', fragment, re.DOTALL)
                    if match:
                        prefix, core, suffix = match.groups()
                        rebuilt.append(f"{prefix}{translate_preserving_markup(core)}{suffix}")
                    else:
                        rebuilt.append(translate_preserving_markup(fragment))
                else:
                    rebuilt.append(fragment)
            return "".join(rebuilt)

        # Per-route state. Each target language gets its own translation
        # function, so this closure is effectively per route. Access is
        # serialized by self.translation_lock in parallel mode.
        route_state = {
            # CJK models delete inline tokens, so they never use placeholders.
            "segmentation_first": target_code.casefold() in PLACEHOLDER_UNSAFE_LANGUAGES,
            "failures": 0,
            "warnings": 0,
        }

        def placeholder_route_is_risky(protected_text, token_map):
            """True if the placeholder sits where models tend to discard it.

            A token at the very end of a text is read as trailing junk and gets
            dropped. Observed with de -> pb, where every "Rekrutierungszentrum:
            <name>" text lost its placeholder. Detecting this up front avoids a
            wasted translation pass and the resulting warning.
            """
            if not token_map:
                return False
            stripped = protected_text.strip()
            return any(stripped.endswith(token) for token in token_map)

        def report_placeholder_failure(reason, discarded):
            """Log a placeholder failure, throttled, and adapt the route."""
            route_state["failures"] += 1
            if route_state["warnings"] < PLACEHOLDER_WARNING_LIMIT:
                route_state["warnings"] += 1
                self.log_message(
                    f"WARNING [{source_code}->{target_code}]: Placeholder {reason}, "
                    f"retranslating without placeholders. Discarded: {discarded}"
                )
            # After repeated failures the model is clearly unreliable for inline
            # tokens on this route, so stop using them altogether.
            if (not route_state["segmentation_first"]
                    and route_state["failures"] >= PLACEHOLDER_FAILURE_LIMIT):
                route_state["segmentation_first"] = True
                self.log_message(
                    f"[{source_code}->{target_code}] Placeholders failed "
                    f"{route_state['failures']} times. Switching to segmentation "
                    f"for the rest of this language; further warnings suppressed."
                )

        def translate_single_chunk(text: str) -> str:
            """
            Translate one text using the protection strategy that is reliable
            for this target language.

            Latin/Cyrillic targets use the placeholder route, which preserves
            the full sentence context. CJK targets, texts whose placeholder sits
            at the end, and routes that already failed repeatedly use
            segmentation instead.
            """
            if not text or should_exclude(text):
                return text

            if self.translation_memory_enabled_var.get():
                memory_result = self._get_memory_translation(source_code, target_code, text)
                if memory_result is not None:
                    # Entries stored by an older build can still contain the
                    # invented punctuation, so the cleanup runs here as well.
                    return _clean_underscore_punctuation(text, memory_result)

            original_text = text

            if route_state["segmentation_first"]:
                translated_result = translate_by_segmentation(original_text)
            else:
                protected, translated_name_map = self._protect_translated_names(
                    text, source_code, target_code
                )
                protected, proper_name_map = self._protect_proper_names(protected)
                all_tokens = {**proper_name_map, **translated_name_map}

                if placeholder_route_is_risky(protected, all_tokens):
                    # Expected situation, not an error: no warning is logged.
                    translated_result = translate_by_segmentation(original_text)
                else:
                    translated_result = translate_preserving_markup(protected)
                    translated_result = self._restore_proper_names(
                        translated_result, proper_name_map
                    )
                    translated_result = self._restore_proper_names(
                        translated_result, translated_name_map
                    )

                    # Safety net for the remaining cases. Two independent
                    # failure modes: residue (a mangled token survived) and
                    # loss (a token was deleted). Either discards the result.
                    if all_tokens:
                        damaged = self._contains_placeholder_residue(
                            translated_result, all_tokens
                        )
                        lost = self._has_lost_placeholder(translated_result, all_tokens)
                        if damaged or lost:
                            report_placeholder_failure(
                                "damaged" if damaged else "deleted by the model",
                                translated_result,
                            )
                            translated_result = translate_by_segmentation(original_text)

            # Final guard, independent of the route that produced the result.
            translated_result = _clean_underscore_punctuation(
                original_text, translated_result
            )

            if (self.translation_memory_enabled_var.get()
                    and self.translation_memory_auto_store_var.get()):
                self._store_memory_translation(
                    source_code, target_code, original_text, translated_result
                )

            return translated_result

        def wrapped_translate(text: str) -> str:
            """
            Handles multi-line batched texts by splitting at BATCH_TEXT_DELIMITER,
            processing each chunk individually, and reassembling them.
            """
            if not text:
                return text

            # IMPORTANT: If the whole text (or a single line) matches an exclusion
            # pattern, return the original immediately and untouched.
            if should_exclude(text):
                return text

            if BATCH_TEXT_DELIMITER in text:
                lines = text.split(BATCH_TEXT_DELIMITER)
                result_lines = []
                for line in lines:
                    if should_exclude(line):
                        result_lines.append(line)
                    else:
                        result_lines.append(translate_single_chunk(line))
                return BATCH_TEXT_DELIMITER.join(result_lines)

            return translate_single_chunk(text)

        return wrapped_translate

    def ensure_package_installed(self, from_code, to_code):
        """
        Checks if the required translation model package is installed. If not,
        attempts to download it. Utilizes a pivot download through English if direct package is absent.

        Args:
            from_code (str): Source language abbreviation.
            to_code (str): Target language abbreviation.

        Returns:
            bool: True if installed/ready, False otherwise.
        """
        if self._try_install_or_download_package(from_code, to_code):
            return True

        # Pivot route attempt via English
        if from_code != "en" and to_code != "en":
            self.log_message(f"No direct index for {from_code} -> {to_code} found.")
            self.log_message(f"Language will be translated to English first, then to {to_code}.")

            step1 = self._try_install_or_download_package(from_code, "en")
            step2 = self._try_install_or_download_package("en", to_code)

            if step1 and step2:
                return True

        self.log_message(f"ERROR: No language package for {from_code} -> {to_code} found in the online index!")
        return False

    def _try_install_or_download_package(self, from_code, to_code):
        """Helper method to check, download, and install a specific Argos model package."""
        installed_languages = argostranslate.translate.get_installed_languages()
        from_lang = next(filter(lambda x: x.code == from_code, installed_languages), None)

        if from_lang:
            translation = next(filter(lambda x: x.to_lang.code == to_code, from_lang.translations_from), None)
            if translation:
                return True

        local_package_name = f"{from_code}_{to_code}.argosmodel"
        local_package_path = os.path.join(self.packages_dir, local_package_name)

        if os.path.exists(local_package_path):
            self.log_message(f"Installing local language model: {local_package_name}...")
            argostranslate.package.install_from_path(local_package_path)
            return True

        self.log_message(f"Searching for package in online index: {from_code} -> {to_code}...")
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()

        package_to_install = next(
            filter(lambda x: x.from_code == from_code and x.to_code == to_code, available_packages),
            None
        )

        if package_to_install:
            if hasattr(package_to_install, 'links') and package_to_install.links:
                package_url = package_to_install.links[0]
            else:
                return False

            self.log_message(f"Starting download to '{self.packages_dir}'...")
            success = self.download_file_with_progress(package_url, local_package_path)

            if success and not self.cancel_requested:
                self.log_message("Download completed. Installing language package...")
                argostranslate.package.install_from_path(local_package_path)
                self.log_message(f"Language model {from_code} -> {to_code} successfully saved and installed.")
                return True
            else:
                if os.path.exists(local_package_path):
                    os.remove(local_package_path)
                return False

        return False

    def find_target_text_nodes(self, root):
        """
        Crawls the XML document tree for `<Text>` nodes containing translatable string data.

        Args:
            root (xml.etree.ElementTree.Element): The root element of the XML document.

        Returns:
            list: List of matching XML text elements.
        """
        target_nodes = []
        self._skipped_node_count = 0

        def _is_translatable(element):
            return (
                element.tag == "Text"
                and len(element) == 0
                and element.text
                and element.text.strip()
            )

        def _collect(element, blocked):
            """Walk the tree and honor <!--!DONOTRANSLATE--> markers."""
            if _is_translatable(element):
                if blocked:
                    self._skipped_node_count += 1
                else:
                    target_nodes.append(element)

            # A marker applies to the NEXT element sibling only. Blocking is
            # inherited by the whole subtree, so the marker may also be placed
            # in front of a container such as <ModOp> or the outer <Text>.
            marker_active = False
            for child in element:
                if child.tag is ET.Comment:
                    if self._is_do_not_translate_comment(child):
                        marker_active = True
                    continue
                _collect(child, blocked or marker_active)
                marker_active = False

        _collect(root, False)
        return target_nodes

    @staticmethod
    def _is_do_not_translate_comment(comment_element):
        """True if an XML comment is the DONOTTRANSLATE marker.

        Matching is deliberately tolerant: case, surrounding whitespace, a
        leading "!" and any underscores or hyphens are ignored, so all of
        "<!--!DONOTRANSLATE-->", "<!-- DoNotTranslate -->" and
        "<!--!DO_NOT_TRANSLATE-->" are recognized as the same instruction.
        """
        raw_text = comment_element.text or ""
        normalized = re.sub(r"[\s_\-!]+", "", raw_text).upper()
        return normalized in DO_NOT_TRANSLATE_MARKERS

    def _log_do_not_translate_count(self):
        """Report how many texts were excluded by a DONOTTRANSLATE marker."""
        skipped = getattr(self, "_skipped_node_count", 0)
        if skipped:
            self.log_message(
                f"{skipped} text(s) marked with <!--!DONOTRANSLATE--> are copied "
                f"unchanged into every output file."
            )

    def process_parallel_translation(self, source_code, target_languages):
        """
        Translates all chosen languages concurrently using a ThreadPoolExecutor.
        Batches XML text nodes together based on settings to optimize compute efficiency.
        """
        try:
            batch_size = int(self.batch_combo.get())
            auto_batch_size = self.auto_batch_var.get()
            max_batch_chars = 1000

            active_langs = []

            # Setup XML trees and translation functions for every language before execution
            for lang_code, lang_suffix, display_name in target_languages:
                if self.cancel_requested:
                    break

                self.log_message(f"Checking language package for: {display_name}")
                if self.ensure_package_installed(source_code, lang_code):
                    fn = self.get_translation_function(source_code, lang_code)
                    if fn:
                        tree = self._load_tree_safely(self.selected_file)
                        root = tree.getroot()
                        nodes = self.find_target_text_nodes(root)
                        active_langs.append({
                            "code": lang_code,
                            "suffix": lang_suffix,
                            "name": display_name,
                            "fn": fn,
                            "tree": tree,
                            "nodes": nodes
                        })

            if not active_langs or self.cancel_requested:
                return

            # One-time hint about identifiers that contain a protected name.
            self.warn_about_name_variants(
                [node.text for node in active_langs[0]["nodes"]]
            )
            self._log_do_not_translate_count()

            total_texts = len(active_langs[0]["nodes"])
            total_langs = len(active_langs)
            total_overall = total_texts * total_langs
            overall_processed = 0

            if total_texts == 0:
                self.log_message("WARNING: No texts to translate found.")
                return

            batch_start = 0
            while batch_start < total_texts and not self.cancel_requested:
                ref_nodes = active_langs[0]["nodes"]

                # Dynamic batch scaling by character count limit
                if auto_batch_size:
                    try:
                        entered_max = int(self.auto_batch_entry.get())
                        if entered_max > 0:
                            max_batch_chars = entered_max
                    except ValueError:
                        pass

                    batch_count = 0
                    batch_char_count = 0
                    while batch_start + batch_count < total_texts:
                        candidate_text = ref_nodes[batch_start + batch_count].text.strip()
                        added_chars = len(candidate_text)
                        if batch_count > 0:
                            added_chars += len(BATCH_TEXT_DELIMITER)
                        if batch_count > 0 and batch_char_count + added_chars > max_batch_chars:
                            break
                        batch_count += 1
                        batch_char_count += added_chars
                else:
                    batch_count = min(batch_size, total_texts - batch_start)

                batch_indices = list(range(batch_start, batch_start + batch_count))
                batch_start += batch_count

                original_texts = [ref_nodes[i].text.strip() for i in batch_indices]
                combined_text = BATCH_TEXT_DELIMITER.join(original_texts)

                translations_map = {}
                preview_translations = []

                def translate_task(lang_info):
                    with self.translation_lock:  # <--- Synchronized access to model translation calls
                        res = lang_info["fn"](combined_text)
                    return lang_info["name"], res

                # Dispatch identical text payloads to different translation models concurrently
                with ThreadPoolExecutor(max_workers=min(total_langs, 8)) as executor:
                    futures = [executor.submit(translate_task, lang) for lang in active_langs]
                    for future in as_completed(futures):
                        name, result_text = future.result()
                        translations_map[name] = "" if result_text is None else str(result_text)

                # Reassemble results back into the respective XML Tree memory structures
                for lang in active_langs:
                    lang_name = lang["name"]
                    trans_combined = translations_map.get(lang_name, "")
                    translated_texts = trans_combined.split(BATCH_TEXT_DELIMITER)

                    # Handle split delimiter errors by falling back safely to one-by-one with lock protection
                    if len(translated_texts) != len(original_texts):
                        with self.translation_lock:  # <--- Secure fallback access with lock
                            translated_texts = [str(lang["fn"](t) or "") for t in original_texts]
                    else:
                        translated_texts = [t.strip() for t in translated_texts]

                    preview_translations.append(f"[{lang_name}]:\n{trans_combined}")

                    for idx, trans_t in zip(batch_indices, translated_texts):
                        lang["nodes"][idx].text = trans_t

                    overall_processed += len(batch_indices)

                self.update_translation_preview(combined_text, "\n".join(preview_translations))

                progress_val = overall_processed / total_overall
                elapsed = time.time() - self.start_time
                remaining = ((elapsed / progress_val) - elapsed) if progress_val > 0 else 0

                self.update_progress_count("Parallel All", overall_processed // total_langs, total_texts)
                self.update_status_and_time(
                    f"Parallel: {overall_processed}/{total_overall} total texts processed...",
                    progress_val,
                    elapsed,
                    remaining
                )

            # Export finished XML files to disk
            if not self.cancel_requested:
                for lang in active_langs:
                    out_filename = f"texts_{lang['suffix']}.xml"
                    out_path = os.path.join(self.output_directory, out_filename)
                    lang["tree"].write(out_path, encoding="utf-8", xml_declaration=True)
                    self.log_message(f"SAVED: File '{out_filename}' successfully created.")

            total_elapsed = time.time() - self.start_time
            if self.cancel_requested:
                self.log_message("=== CANCELED: Translation stopped. ===")
                self.update_status_and_time("Translation canceled", 0, total_elapsed, 0)
            else:
                self.update_status_and_time(f"Done! {total_langs} language(s) translated in parallel.", 1.0, total_elapsed, 0)
                self.log_message(f"=== SUCCESS: All {total_langs} language(s) finished in {self.format_seconds(total_elapsed)} ===")
                messagebox.showinfo(
                    "Success",
                    f"Parallel translation completed!\n\nRuntime: {self.format_seconds(total_elapsed)}\n{total_langs} file(s) generated at:\n{self.output_directory}"
                )

        except Exception as err:
            self.log_message(f"CRITICAL ERROR: {str(err)}")
            self.update_status_and_time(f"Error: {str(err)}", 0, 0, 0)
            messagebox.showerror("Error", f"An error occurred:\n{str(err)}")
        finally:
            self.reset_ui()

    def process_multi_translation(self, source_code, target_languages):
        """
        Translates languages strictly sequentially (One-by-One mode).
        More memory-efficient as it keeps only a single target model loaded in memory at a time.
        """
        try:
            batch_size = int(self.batch_combo.get())
            auto_batch_size = self.auto_batch_var.get()
            max_batch_chars = 1000

            total_langs = len(target_languages)
            total_texts_per_language = None
            overall_processed_count = 0

            # Loop linearly through each target language
            for lang_idx, (lang_code, lang_suffix, display_name) in enumerate(target_languages, start=1):
                if self.cancel_requested:
                    break

                self.log_message(f"Preparing language [{lang_idx}/{total_langs}]: {display_name}")

                if not self.ensure_package_installed(source_code, lang_code):
                    if self.cancel_requested:
                        break
                    continue

                translate_fn = self.get_translation_function(source_code, lang_code)
                if not translate_fn:
                    self.log_message(f"ERROR: Translation for {source_code} -> {lang_code} could not be initialized.")
                    continue

                tree = self._load_tree_safely(self.selected_file)
                root = tree.getroot()
                elements_to_translate = self.find_target_text_nodes(root)
                total_elements = len(elements_to_translate)

                if total_texts_per_language is None:
                    total_texts_per_language = total_elements
                    # One-time hint about identifiers containing a protected name.
                    self.warn_about_name_variants(
                        [node.text for node in elements_to_translate]
                    )
                    self._log_do_not_translate_count()

                total_overall_texts = total_texts_per_language * total_langs

                self.update_progress_count(display_name, 0, total_elements)
                if lang_idx == 1:
                    self.update_status_and_time(
                        f"Total: {overall_processed_count}/{total_overall_texts} texts processed...",
                        0,
                        time.time() - self.start_time,
                        0
                    )

                if total_elements == 0:
                    self.log_message("WARNING: No texts to translate found.")
                    continue

                processed_count = 0
                batch_start = 0

                while batch_start < total_elements:
                    if self.cancel_requested:
                        break

                    auto_batch_size = self.auto_batch_var.get()
                    if auto_batch_size:
                        try:
                            entered_max_batch_chars = int(self.auto_batch_entry.get())
                            if entered_max_batch_chars > 0:
                                max_batch_chars = entered_max_batch_chars
                        except ValueError:
                            pass

                    # Character-based Dynamic Batching logic
                    if auto_batch_size:
                        batch_elements = []
                        batch_char_count = 0
                        while batch_start + len(batch_elements) < total_elements:
                            candidate = elements_to_translate[batch_start + len(batch_elements)]
                            candidate_text = candidate.text.strip()
                            added_chars = len(candidate_text)
                            if batch_elements:
                                added_chars += len(BATCH_TEXT_DELIMITER)
                            if batch_elements and batch_char_count + added_chars > max_batch_chars:
                                break
                            batch_elements.append(candidate)
                            batch_char_count += added_chars
                    # Flat Batching logic
                    else:
                        batch_elements = elements_to_translate[batch_start:batch_start + batch_size]

                    batch_start += len(batch_elements)

                    original_texts = [elem.text.strip() for elem in batch_elements]
                    combined_text = BATCH_TEXT_DELIMITER.join(original_texts)

                    if auto_batch_size:
                        self.log_message(
                            f"[{display_name}] {len(combined_text)} / {max_batch_chars} characters. "
                            f"Batch size set to {len(batch_elements)}."
                        )

                    translated_combined = translate_fn(combined_text)
                    translated_combined = "" if translated_combined is None else str(translated_combined)
                    translated_texts = translated_combined.split(BATCH_TEXT_DELIMITER)

                    # Delimiter mismatch fallback: Translate text blocks individually
                    if len(translated_texts) != len(original_texts):
                        self.log_message(
                            f"WARNING [{display_name}]: Delimiter mismatch! "
                            f"(Expected: {len(original_texts)} blocks, "
                            f"Received: {len(translated_texts)} blocks).\n"
                            f"Sent: {combined_text}\n"
                            f"Returned: {translated_combined}"
                        )
                        translated_texts = [
                            str(translate_fn(text) or "")
                            for text in original_texts
                        ]
                    else:
                        translated_texts = [text.strip() for text in translated_texts]

                    self.update_translation_preview(combined_text, translated_combined)

                    # Reattach results back to XML objects and advance progress counters
                    for _ in translated_texts:
                        processed_count += 1
                        overall_processed_count += 1

                        self.update_progress_count(display_name, processed_count, total_elements)

                        progress_val = ((lang_idx - 1) + (processed_count / total_elements)) / total_langs
                        elapsed_seconds = time.time() - self.start_time
                        remaining_seconds = (
                            (elapsed_seconds / progress_val) - elapsed_seconds
                            if progress_val > 0 else 0
                        )
                        self.update_status_and_time(
                            f"Total: {overall_processed_count}/{total_overall_texts} texts processed...",
                            progress_val,
                            elapsed_seconds,
                            remaining_seconds
                        )

                    for elem, trans_text in zip(batch_elements, translated_texts):
                        elem.text = trans_text

                    progress_val = ((lang_idx - 1) + (processed_count / total_elements)) / total_langs
                    elapsed_seconds = time.time() - self.start_time
                    remaining_seconds = (elapsed_seconds / progress_val) - elapsed_seconds if progress_val > 0 else 0

                    self.update_status_and_time(
                        f"Total: {overall_processed_count}/{total_overall_texts} texts processed...",
                        progress_val,
                        elapsed_seconds,
                        remaining_seconds
                    )

                # Export single language file upon completion of loop
                if not self.cancel_requested:
                    output_filename = f"texts_{lang_suffix}.xml"
                    output_path = os.path.join(self.output_directory, output_filename)
                    tree.write(output_path, encoding="utf-8", xml_declaration=True)
                    self.log_message(f"SAVED: File '{output_filename}' successfully created.")

            total_elapsed = time.time() - self.start_time
            if self.cancel_requested:
                self.log_message("=== CANCELED: Translation stopped. ===")
                self.update_status_and_time("Translation canceled", 0, total_elapsed, 0)
            else:
                self.update_status_and_time(
                    f"Done! {total_langs} language(s) translated.",
                    1.0,
                    total_elapsed,
                    0
                )
                self.log_message(f"=== SUCCESS: All {total_langs} language(s) finished in {self.format_seconds(total_elapsed)} ===")
                messagebox.showinfo(
                    "Success",
                    f"Translation completed!\n\nRuntime: {self.format_seconds(total_elapsed)}\n{total_langs} file(s) generated at:\n{self.output_directory}"
                )

        except Exception as err:
            self.log_message(f"CRITICAL ERROR: {str(err)}")
            self.update_status_and_time(f"Error: {str(err)}", 0, 0, 0)
            messagebox.showerror("Error", f"An error occurred:\n{str(err)}")
        finally:
            self.reset_ui()
