"""Translation workflow for multilingual text blocks in modinfo.json files."""
from __future__ import annotations

import json
import os
import threading
import time
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .constants import AVAILABLE_LANGUAGES


# modinfo.json uses display-language keys rather than Argos language codes.
MODINFO_KEY_BY_SUFFIX = {
    "brazilian": "Brazilian",
    "chinese": "Chinese",
    "english": "English",
    "french": "French",
    "german": "German",
    "italian": "Italian",
    "japanese": "Japanese",
    "korean": "Korean",
    "polish": "Polish",
    "portuguese": "Portuguese",
    "russian": "Russian",
    "spanish": "Spanish",
    "taiwanese": "Taiwanese",
    "simplified_chinese": "Chinese",
    "traditional_chinese": "Taiwanese",
}

MODINFO_CODE_BY_KEY = {
    "Brazilian": "pb",
    "Chinese": "zh",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Polish": "pl",
    "Portuguese": "pt",
    "Russian": "ru",
    "Spanish": "es",
    "Taiwanese": "zt",
}


class ModinfoTranslationMixin:
    """Build the modinfo tab and translate multilingual JSON dictionaries."""

    def _build_modinfo_tab(self):
        self.modinfo_selected_file = ""
        self.modinfo_data = None
        self.modinfo_is_translating = False

        file_frame = ctk.CTkFrame(self.tab_modinfo)
        file_frame.pack(fill="x", padx=15, pady=(15, 5))
        self.modinfo_path_entry = ctk.CTkEntry(
            file_frame, placeholder_text="Select modinfo.json", width=550
        )
        self.modinfo_path_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)
        self.modinfo_browse_button = ctk.CTkButton(
            file_frame, text="Browse", width=100, command=self.select_modinfo_file
        )
        self.modinfo_browse_button.pack(side="right", padx=(5, 10), pady=10)

        source_frame = ctk.CTkFrame(self.tab_modinfo)
        source_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(
            source_frame, text="Source Language:", font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=(10, 8), pady=10)
        self.modinfo_source_combo = ctk.CTkComboBox(
            source_frame, values=list(MODINFO_CODE_BY_KEY), width=190, state="readonly",
            command=lambda _value: self._refresh_modinfo_preview()
        )
        self.modinfo_source_combo.set("English")
        self.modinfo_source_combo.pack(side="left", padx=5, pady=10)
        self.modinfo_target_label = ctk.CTkLabel(
            source_frame,
            text="Target languages are taken from the Languages tab.",
            text_color="gray",
        )
        self.modinfo_target_label.pack(side="left", padx=15, pady=10)

        # Explain the special handling of modinfo.json text fields.
        handling_frame = ctk.CTkFrame(self.tab_modinfo)
        handling_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(
            handling_frame,
            text=(
                "Translation behavior:\n"
                "• Category and ModName: copied unchanged from the selected source language "
                "to the selected target languages.\n"
                "• Description: translated into the selected target languages."
            ),
            anchor="w",
            justify="left",
            wraplength=820,
        ).pack(fill="x", padx=10, pady=8)

        info_frame = ctk.CTkFrame(self.tab_modinfo)
        info_frame.pack(fill="x", padx=15, pady=5)
        self.modinfo_info_label = ctk.CTkLabel(
            info_frame,
            text="No modinfo.json loaded.",
            anchor="w",
            justify="left",
        )
        self.modinfo_info_label.pack(fill="x", padx=10, pady=8)

        preview_frame = ctk.CTkFrame(self.tab_modinfo)
        preview_frame.pack(fill="both", expand=True, padx=15, pady=5)
        ctk.CTkLabel(
            preview_frame,
            text="Source Text Preview:",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 3))
        self.modinfo_preview = ctk.CTkTextbox(
            preview_frame, height=360, wrap="word", font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.modinfo_preview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.modinfo_preview.configure(state="disabled")

        self.modinfo_progress = ctk.CTkProgressBar(self.tab_modinfo)
        self.modinfo_progress.pack(fill="x", padx=15, pady=(8, 2))
        self.modinfo_progress.set(0)
        self.modinfo_status_label = ctk.CTkLabel(
            self.tab_modinfo, text="Ready", text_color="gray", anchor="w"
        )
        self.modinfo_status_label.pack(fill="x", padx=15, pady=(0, 5))

        self.modinfo_action_button = ctk.CTkButton(
            self.tab_modinfo,
            text="Translate modinfo.json",
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.toggle_modinfo_translation,
        )
        self.modinfo_action_button.pack(fill="x", padx=15, pady=(5, 15))

    def select_modinfo_file(self):
        path = filedialog.askopenfilename(
            title="Select modinfo.json",
            filetypes=[("modinfo.json", "modinfo.json"), ("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("The root element must be a JSON object.")
        except Exception as error:
            messagebox.showerror("Invalid modinfo.json", f"The file could not be loaded:\n\n{error}")
            return

        self.modinfo_selected_file = path
        self.modinfo_data = data
        self.modinfo_path_entry.delete(0, "end")
        self.modinfo_path_entry.insert(0, path)

        source_keys = self._collect_modinfo_language_keys(data)
        choices = [key for key in MODINFO_CODE_BY_KEY if key in source_keys]
        if not choices:
            choices = list(MODINFO_CODE_BY_KEY)
        self.modinfo_source_combo.configure(values=choices)
        self.modinfo_source_combo.set("English" if "English" in choices else choices[0])
        self._refresh_modinfo_preview()
        self.log_message(f"modinfo.json loaded: {path}")

    def _collect_modinfo_language_keys(self, value):
        keys = set()
        if isinstance(value, dict):
            keys.update(key for key in value if key in MODINFO_CODE_BY_KEY)
            for child in value.values():
                keys.update(self._collect_modinfo_language_keys(child))
        elif isinstance(value, list):
            for child in value:
                keys.update(self._collect_modinfo_language_keys(child))
        return keys

    def _find_multilingual_blocks(self, value, path=""):
        blocks = []
        if isinstance(value, dict):
            language_keys = [key for key in value if key in MODINFO_CODE_BY_KEY]
            if language_keys and any(isinstance(value.get(key), str) for key in language_keys):
                blocks.append((path or "<root>", value))
            else:
                for key, child in value.items():
                    child_path = f"{path}.{key}" if path else key
                    blocks.extend(self._find_multilingual_blocks(child, child_path))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                blocks.extend(self._find_multilingual_blocks(child, f"{path}[{index}]"))
        return blocks

    def _refresh_modinfo_preview(self):
        source_key = self.modinfo_source_combo.get()
        blocks = self._find_multilingual_blocks(self.modinfo_data) if self.modinfo_data else []
        lines = []
        available = 0
        for path, block in blocks:
            text = block.get(source_key)
            if isinstance(text, str):
                available += 1
                lines.append(f"[{path}]\n{text}")
        selected_targets = self._get_modinfo_targets(source_key)
        target_names = ", ".join(item[2] for item in selected_targets) or "None selected"
        self.modinfo_info_label.configure(
            text=(
                f"Translatable sections: {len(blocks)} | Source texts found: {available}\n"
                f"Targets from Languages tab: {target_names}"
            )
        )
        self.modinfo_preview.configure(state="normal")
        self.modinfo_preview.delete("1.0", "end")
        self.modinfo_preview.insert("1.0", "\n\n".join(lines) if lines else "No source texts found.")
        self.modinfo_preview.configure(state="disabled")

    def _get_modinfo_targets(self, source_key):
        targets = []
        seen_keys = set()
        for display_name, (var, code, suffix) in self.checkboxes.items():
            if not var.get():
                continue
            json_key = MODINFO_KEY_BY_SUFFIX.get(suffix)
            if not json_key or json_key == source_key or json_key in seen_keys:
                continue
            seen_keys.add(json_key)
            targets.append((code, json_key, display_name))
        return targets

    def toggle_modinfo_translation(self):
        if self.modinfo_is_translating:
            self.cancel_requested = True
            self.modinfo_action_button.configure(state="disabled", text="Canceling...")
            self.modinfo_status_label.configure(text="Cancellation requested...")
            return
        self.start_modinfo_translation()

    def start_modinfo_translation(self):
        if self.is_translating:
            messagebox.showinfo("Translation running", "Finish or cancel the XML translation first.")
            return
        if not self.modinfo_selected_file or not os.path.isfile(self.modinfo_selected_file):
            messagebox.showerror("Error", "Please select a valid modinfo.json file.")
            return
        source_key = self.modinfo_source_combo.get()
        source_code = MODINFO_CODE_BY_KEY.get(source_key)
        targets = self._get_modinfo_targets(source_key)
        if not source_code:
            messagebox.showerror("Error", "The selected source language is not supported.")
            return
        if not targets:
            messagebox.showerror("Error", "Select at least one different target language in the Languages tab.")
            return
        blocks = self._find_multilingual_blocks(self.modinfo_data)
        source_blocks = [(path, block) for path, block in blocks if isinstance(block.get(source_key), str)]
        if not source_blocks:
            messagebox.showerror("Error", f"No texts for source language '{source_key}' were found.")
            return

        self.modinfo_is_translating = True
        self.cancel_requested = False
        self.modinfo_progress.set(0)
        self.modinfo_browse_button.configure(state="disabled")
        self.modinfo_action_button.configure(
            text="Cancel Translation", fg_color="firebrick", hover_color="darkred"
        )
        threading.Thread(
            target=self._process_modinfo_translation,
            args=(source_key, source_code, targets, source_blocks),
            daemon=True,
        ).start()

    def _process_modinfo_translation(self, source_key, source_code, targets, source_blocks):
        started = time.time()
        try:
            functions = []
            for code, json_key, display_name in targets:
                if self.cancel_requested:
                    return
                self.after(0, lambda n=display_name: self.modinfo_status_label.configure(
                    text=f"Preparing language model: {n}"
                ))
                if not self.ensure_package_installed(source_code, code):
                    self.log_message(f"ERROR: modinfo target skipped, model unavailable: {display_name}")
                    continue
                translate_fn = self.get_translation_function(source_code, code)
                if translate_fn:
                    functions.append((code, json_key, display_name, translate_fn))
            if not functions:
                raise RuntimeError("No target language model could be initialized.")

            total = len(source_blocks) * len(functions)
            completed = 0
            for path, block in source_blocks:
                source_text = block[source_key]
                section_name = path.rsplit(".", 1)[-1].split("[", 1)[0]
                copy_without_translation = section_name in {"Category", "ModName"}

                for _code, json_key, display_name, translate_fn in functions:
                    if self.cancel_requested:
                        return
                    if copy_without_translation:
                        self.after(0, lambda p=path, n=display_name: self.modinfo_status_label.configure(
                            text=f"Copying {p} -> {n}"
                        ))
                        block[json_key] = source_text
                    else:
                        self.after(0, lambda p=path, n=display_name: self.modinfo_status_label.configure(
                            text=f"Translating {p} -> {n}"
                        ))
                        with self.translation_lock:
                            translated = translate_fn(source_text)
                        block[json_key] = "" if translated is None else str(translated)
                    completed += 1
                    self.after(0, lambda value=completed / total: self.modinfo_progress.set(value))

            output_path = os.path.join(
                os.path.dirname(self.modinfo_selected_file), "modinfo_translated.json"
            )
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(self.modinfo_data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            elapsed = self.format_seconds(time.time() - started)
            self.log_message(f"SAVED: File 'modinfo_translated.json' successfully created.")
            self.after(0, lambda: self._finish_modinfo_translation(output_path, elapsed))
        except Exception as error:
            self.log_message(f"CRITICAL ERROR: modinfo.json translation failed: {error}")
            self.after(0, lambda e=error: messagebox.showerror(
                "modinfo.json Translation Error", str(e)
            ))
        finally:
            self.after(0, self._reset_modinfo_ui)

    def _finish_modinfo_translation(self, output_path, elapsed):
        self.modinfo_status_label.configure(text=f"Done in {elapsed}: {output_path}")
        self.modinfo_progress.set(1)
        messagebox.showinfo(
            "Success",
            f"modinfo.json translation completed.\n\nSaved as:\n{output_path}\n\nRuntime: {elapsed}",
        )

    def _reset_modinfo_ui(self):
        canceled = self.cancel_requested
        self.modinfo_is_translating = False
        self.cancel_requested = False
        self.modinfo_browse_button.configure(state="normal")
        self.modinfo_action_button.configure(
            state="normal",
            text="Translate modinfo.json",
            fg_color=("#3a7ebf", "#1f538d"),
            hover_color=("#32689e", "#14375e"),
        )
        if canceled:
            self.modinfo_progress.set(0)
            self.modinfo_status_label.configure(text="Translation canceled")
