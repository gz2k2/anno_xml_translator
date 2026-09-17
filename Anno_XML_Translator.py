import os
import sys
import time
import json
import re
import shutil
import threading
import configparser
import io
import fnmatch
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
import customtkinter as ctk
from anno_translator.config_manager import ConfigurationMixin
from anno_translator.quality_manager import TranslationQualityMixin
from anno_translator.translation_engine import TranslationEngineMixin
from anno_translator.constants import APP_NAME, APP_NAME_SHORT, AVAILABLE_LANGUAGES
from anno_translator.paths import get_application_directory
from tkinter import filedialog, messagebox, simpledialog

# --- Extended Imports for Custom Download & Progress ---
import requests
import argostranslate.package
import argostranslate.translate

# Configure CustomTkinter appearance (Dark mode is default)
ctk.set_appearance_mode("Dark")

class AnnoXMLTranslatorApp(
    ConfigurationMixin, TranslationQualityMixin, TranslationEngineMixin, ctk.CTk
):
    """
    Main Application Class for the Anno Mod XML Text Translator.
    Provides a GUI to parse Anno Mod XML files and translate them into multiple
    languages using offline Argos Translate language models.
    """
    
    def __init__(self):
        super().__init__()

        # Setup main window properties
        self.title(APP_NAME)
        self.geometry("900x900")
        self.resizable(False, False)

        # Initialize application state variables
        self.selected_file = ""
        self.output_directory = ""
        self.is_translating = False
        self.cancel_requested = False
        self.start_time = None
        self.checkboxes = {}
        self.translation_lock = threading.Lock()  # <--- Lock for parallel/concurrent thread access

        # Persistent data is stored next to the script or compiled executable.
        self.app_dir = get_application_directory()
        self.packages_dir = os.path.join(self.app_dir, "argos_packages")
        self.config_dir = os.path.join(self.app_dir, "config")
        os.makedirs(self.packages_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)

        # All editable configuration files are stored in the config subfolder.
        self.profiles_file = os.path.join(self.config_dir, "language_profiles.json")
        self.config_file = os.path.join(self.config_dir, "config.ini")
        self.proper_names_file = os.path.join(self.config_dir, "proper_names.ini")
        self.name_translations_file = os.path.join(self.config_dir, "name_translations.ini")
        self.translation_memory_file = os.path.join(self.config_dir, "translation_memory.ini")

        # Move legacy configuration files from the application root once.
        self._migrate_legacy_config_files()
        self.profiles = {}
        self.proper_names = []
        self.name_translations = []
        self.translation_memory = {}
        self.translation_memory_lock = threading.Lock()

        # User-friendly labels for the internal CTranslate2 compute types.
        self.compute_type_labels = {
            "GPU - Fast and efficient (float16)": "float16",
            "CPU - Fast, low memory usage (int8)": "int8",
            "Maximum compatibility (float32)": "float32"
        }
        self.compute_type_labels_reverse = {
            value: label for label, value in self.compute_type_labels.items()
        }

        self._ensure_quality_files()
        self._load_proper_names()
        self._load_name_translations()
        self._load_translation_memory()

        # Initialize core components
        self._setup_hardware_acceleration()
        self._load_profiles()
        self._build_ui()
        self._load_settings_from_config()

        # Intercept window close event (optional hook)
        #self.protocol("WM_DELETE_WINDOW", self._cleanup_on_close)


    def _setup_hardware_acceleration(self):
        """
        Configures Argos Translate environmental variables.
        Forces the use of CUDA/GPU (if available) and points Argos Translate to the local package directories.
        Note: STANZA_RESOURCES_DIR and NLTK_DATA are set globally before imports to ensure correct path initialization.
        """
        os.environ["ARGOS_DEVICE_TYPE"] = "cuda"
        os.environ["ARGOS_DATA_DIR"] = self.packages_dir

    def _cleanup_on_close(self):
        """Deletes the local temporary folder when closing the application."""
        try:
            if os.path.exists(_temp_dir):
                shutil.rmtree(_temp_dir)
                print(f"Temp folder successfully deleted: {_temp_dir}")
        except Exception as e:
            print(f"Error deleting the temp folder: {e}")
        
        # Close the main window and terminate the application
        self.destroy()

    def _load_tree_safely(self, file_path):
        """Liest die XML-Datei ein und maskiert rohe &-Zeichen, die zu Parse-Fehlern führen."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Ersetzt & das nicht bereits Teil einer Entity (wie &amp;, &lt;, etc.) ist durch &amp;
        fixed_content = re.sub(r'&(?!([a-zA-Z0-9#]+;))', '&amp;', content)
        
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        return ET.parse(io.StringIO(fixed_content), parser=parser)





    def _build_ui(self):
        """
        Constructs and layouts the entire Graphical User Interface (GUI), 
        including headers, tabs, file selection, settings, and logs.
        """
        # --- Header Section ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(15, 5))

        self.title_label = ctk.CTkLabel(
            self.header_frame, text=APP_NAME_SHORT, font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(side="left")

        self.theme_switch = ctk.CTkSwitch(
            self.header_frame, text="Dark Mode", command=self.toggle_theme
        )
        if ctk.get_appearance_mode().lower() == "dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
        self.theme_switch.pack(side="right")

        # --- Setup Tabview ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=5)

        self.tab_main = self.tabview.add("Main Menu")
        self.tab_lang = self.tabview.add("Languages")
        self.tab_settings = self.tabview.add("Settings")

        # ==========================================
        # TAB 1: MAIN MENU
        # ==========================================

        # 1. File Selection Frame
        self.file_frame = ctk.CTkFrame(self.tab_main)
        self.file_frame.pack(fill="x", padx=10, pady=5)

        self.path_entry = ctk.CTkEntry(
            self.file_frame, placeholder_text="Select source file (e.g., texts_english.xml)", width=450
        )
        self.path_entry.pack(side="left", padx=(10, 5), pady=10, expand=True, fill="x")

        self.btn_browse = ctk.CTkButton(
            self.file_frame, text="Browse", command=self.select_file, width=100
        )
        self.btn_browse.pack(side="right", padx=(5, 10), pady=10)

        # 2. Output Folder Frame
        self.out_frame = ctk.CTkFrame(self.tab_main)
        self.out_frame.pack(fill="x", padx=10, pady=5)

        self.out_entry = ctk.CTkEntry(
            self.out_frame, placeholder_text="Output folder (Default: Source file folder)", width=450
        )
        self.out_entry.pack(side="left", padx=(10, 5), pady=10, expand=True, fill="x")

        self.btn_out_browse = ctk.CTkButton(
            self.out_frame, text="Select Folder", command=self.select_output_dir, width=100
        )
        self.btn_out_browse.pack(side="right", padx=(5, 10), pady=10)

        # 3. Status & Timer Elements
        self.progress = ctk.CTkProgressBar(self.tab_main, orientation="horizontal")
        self.progress.pack(fill="x", padx=10, pady=(10, 2))
        self.progress.set(0)

        self.progress_count_label = ctk.CTkLabel(
            self.tab_main, text="Texts: 0/0", anchor="w", text_color="gray"
        )
        self.progress_count_label.pack(fill="x", padx=10, pady=(0, 2))

        self.timer_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.timer_frame.pack(fill="x", padx=10, pady=2, before=self.progress_count_label)

        self.status_label = ctk.CTkLabel(self.timer_frame, text="Ready", text_color="gray")
        self.status_label.pack(side="left")

        self.time_label = ctk.CTkLabel(self.timer_frame, text="Runtime: 00:00:00 | ETA: --:--:--", text_color="gray")
        self.time_label.pack(side="right")

        # 4. Current Translation Text Preview Window
        self.translation_preview_frame = ctk.CTkFrame(self.tab_main)
        self.translation_preview_frame.pack(fill="x", padx=10, pady=(5, 2))

        self.sent_text_label = ctk.CTkLabel(
            self.translation_preview_frame, text="Sent Text:", anchor="w", font=ctk.CTkFont(weight="bold")
        )
        self.sent_text_label.pack(fill="x", padx=10, pady=(5, 0))

        self.sent_textbox = ctk.CTkTextbox(self.translation_preview_frame, height=90, wrap="word")
        self.sent_textbox.pack(fill="x", padx=10, pady=(2, 5))

        self.received_text_label = ctk.CTkLabel(
            self.translation_preview_frame, text="Received Translation:", anchor="w", font=ctk.CTkFont(weight="bold")
        )
        self.received_text_label.pack(fill="x", padx=10, pady=(0, 0))

        self.received_textbox = ctk.CTkTextbox(self.translation_preview_frame, height=105, wrap="word")
        self.received_textbox.pack(fill="x", padx=10, pady=(2, 5))

        # Disable preview textboxes so they remain Read-Only for user
        for textbox in (self.sent_textbox, self.received_textbox):
            textbox.configure(state="disabled")

        # 5. Log Window with header label
        self.log_header_label = ctk.CTkLabel(
            self.tab_main, text="Log:", font=ctk.CTkFont(weight="bold"), anchor="w"
        )
        self.log_header_label.pack(fill="x", padx=10, pady=(5, 0))

        self.log_frame = ctk.CTkFrame(self.tab_main, height=120)
        self.log_frame.pack(fill="x", padx=10, pady=(2, 5))

        self.log_textbox = ctk.CTkTextbox(
            self.log_frame, font=ctk.CTkFont(family="Consolas", size=11), wrap="word", height=110
        )
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)

        # 6. Display of selected target languages below the log window
        self.target_langs_label = ctk.CTkLabel(
            self.tab_main, text="Target Languages: None selected", font=ctk.CTkFont(weight="bold"), text_color="gray", anchor="w"
        )
        self.target_langs_label.pack(fill="x", padx=10, pady=(2, 5))

        # ==========================================
        # MAIN ACTION BUTTON (Pinned to bottom of Main Menu tab)
        # ==========================================
        self.btn_action = ctk.CTkButton(
            self.tab_main,
            text="Start Translation",
            command=self.toggle_translation,
            font=ctk.CTkFont(size=15, weight="bold"),
            height=40
        )
        self.btn_action.pack(fill="x", padx=10, pady=(5, 10))

        # ==========================================
        # TAB 2: LANGUAGES
        # ==========================================
        
        # --- Profile Management Controls ---
        self.profile_frame = ctk.CTkFrame(self.tab_lang)
        self.profile_frame.pack(fill="x", padx=15, pady=(15, 5))

        self.profile_label = ctk.CTkLabel(
            self.profile_frame, text="Language Profile:", font=ctk.CTkFont(weight="bold")
        )
        self.profile_label.pack(side="left", padx=(10, 5), pady=10)

        self.profile_combo = ctk.CTkComboBox(
            self.profile_frame,
            values=list(self.profiles.keys()),
            command=self.on_profile_selected,
            width=180,
            state="readonly",
        )
        self.profile_combo.pack(side="left", padx=5, pady=10)

        self.btn_save_profile = ctk.CTkButton(
            self.profile_frame, text="Save Profile", width=120, command=self.save_current_profile
        )
        self.btn_save_profile.pack(side="left", padx=5, pady=10)

        self.btn_delete_profile = ctk.CTkButton(
            self.profile_frame, text="Delete Profile", width=110, fg_color="firebrick", hover_color="darkred", command=self.delete_current_profile
        )
        self.btn_delete_profile.pack(side="left", padx=5, pady=10)

        # Selection Control Buttons (Select All / Deselect All)
        self.lang_ctrl_frame = ctk.CTkFrame(self.tab_lang, fg_color="transparent")
        self.lang_ctrl_frame.pack(fill="x", padx=15, pady=(5, 10))

        self.btn_select_all = ctk.CTkButton(
            self.lang_ctrl_frame, text="Select All", width=120, command=self.select_all_languages
        )
        self.btn_select_all.pack(side="left", padx=(0, 10))

        self.btn_deselect_all = ctk.CTkButton(
            self.lang_ctrl_frame, text="Deselect All", width=120, command=self.deselect_all_languages
        )
        self.btn_deselect_all.pack(side="left")

        # Scrollable Frame for Language Checkboxes
        self.grid_frame = ctk.CTkScrollableFrame(self.tab_lang)
        self.grid_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Dynamically build language checkboxes in a grid layout
        row, col = 0, 0
        for display_name, (lang_code, lang_suffix) in AVAILABLE_LANGUAGES.items():
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                self.grid_frame, text=display_name, variable=var, command=self._on_checkbox_toggled
            )
            cb.grid(row=row, column=col, sticky="w", padx=15, pady=10)
            self.checkboxes[display_name] = (var, lang_code, lang_suffix)

            col += 1
            if col > 1:  # Two columns layout configuration
                col = 0
                row += 1


        # ==========================================
        # TAB 3: SETTINGS
        # ==========================================
        self.settings_frame = ctk.CTkFrame(self.tab_settings)
        self.settings_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Mode Selection Setting
        self.mode_label = ctk.CTkLabel(self.settings_frame, text="Translation Mode:", font=ctk.CTkFont(weight="bold"))
        self.mode_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.mode_combo = ctk.CTkComboBox(
            self.settings_frame, values=["Parallel", "One-by-One"], width=150, command=self._save_settings_to_config
        )
        self.mode_combo.set("Parallel")
        self.mode_combo.grid(row=0, column=1, padx=15, pady=(15, 5), sticky="w")

        # Batch Size Setting
        self.batch_label = ctk.CTkLabel(self.settings_frame, text="Batch Size (Texts):", font=ctk.CTkFont(weight="bold"))
        self.batch_label.grid(row=1, column=0, padx=15, pady=10, sticky="w")

        self.batch_combo = ctk.CTkComboBox(
            self.settings_frame, values=["1", "5", "10", "25", "50"], width=150, command=self._save_settings_to_config
        )
        self.batch_combo.set("10")
        self.batch_combo.grid(row=1, column=1, padx=15, pady=10, sticky="w")

        # Auto-Batching Settings
        self.auto_batch_label = ctk.CTkLabel(self.settings_frame, text="Auto-Batching (by characters):", font=ctk.CTkFont(weight="bold"))
        self.auto_batch_label.grid(row=2, column=0, padx=15, pady=10, sticky="w")

        self.auto_batch_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.auto_batch_frame.grid(row=2, column=1, padx=15, pady=10, sticky="w")

        self.auto_batch_var = ctk.BooleanVar(value=True)
        self.auto_batch_checkbox = ctk.CTkCheckBox(
            self.auto_batch_frame, text="Enable", variable=self.auto_batch_var, command=self._save_settings_to_config
        )
        self.auto_batch_checkbox.pack(side="left", padx=(0, 10))

        self.auto_batch_entry = ctk.CTkEntry(self.auto_batch_frame, placeholder_text="Max Characters", width=100)
        self.auto_batch_entry.insert(0, "250")
        self.auto_batch_entry.pack(side="left")
        self.auto_batch_entry.bind("<FocusOut>", self._save_settings_to_config)
        self.auto_batch_entry.bind("<Return>", self._save_settings_to_config)

        # Processing mode / internal compute type setting
        self.compute_label = ctk.CTkLabel(
            self.settings_frame,
            text="Processing Mode:",
            font=ctk.CTkFont(weight="bold")
        )
        self.compute_label.grid(row=3, column=0, padx=15, pady=10, sticky="w")

        self.compute_combo = ctk.CTkComboBox(
            self.settings_frame,
            values=list(self.compute_type_labels.keys()),
            width=315,
            command=self._save_settings_to_config
        )
        self.compute_combo.set("CPU - Fast, low memory usage (int8)")
        self.compute_combo.grid(row=3, column=1, padx=15, pady=10, sticky="w")

        # Default output directory setting
        self.default_output_label = ctk.CTkLabel(
            self.settings_frame,
            text="Default Output Folder:",
            font=ctk.CTkFont(weight="bold")
        )
        self.default_output_label.grid(row=4, column=0, padx=15, pady=10, sticky="w")

        self.default_output_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.default_output_frame.grid(row=4, column=1, padx=15, pady=10, sticky="ew")
        self.default_output_entry = ctk.CTkEntry(
            self.default_output_frame,
            placeholder_text="Empty = source file folder",
            width=250
        )
        self.default_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.default_output_entry.bind("<FocusOut>", self._save_settings_to_config)
        self.default_output_entry.bind("<Return>", self._save_settings_to_config)
        ctk.CTkButton(
            self.default_output_frame,
            text="Select Folder",
            width=105,
            command=self.select_default_output_dir
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            self.default_output_frame,
            text="Clear",
            width=65,
            command=self.clear_default_output_dir
        ).pack(side="left")

        # Exclusions & Ignored Words Setting
        self.exclude_label = ctk.CTkLabel(self.settings_frame, text="Fixed Exclusions:", font=ctk.CTkFont(weight="bold"))
        self.exclude_label.grid(row=5, column=0, padx=15, pady=10, sticky="nw")

        self.exclude_info_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.exclude_info_frame.grid(row=5, column=1, padx=15, pady=10, sticky="ew")

        self.exclude_entry = ctk.CTkEntry(
            self.exclude_info_frame, placeholder_text="e.g., quest_*, research_*, Custom Text", width=350
        )
        self.exclude_entry.insert(0, "quest_*, research_*")
        self.exclude_entry.pack(fill="x", pady=(0, 5))
        self.exclude_entry.bind("<FocusOut>", self._save_settings_to_config)
        self.exclude_entry.bind("<Return>", self._save_settings_to_config)

        self.exclude_hint = ctk.CTkLabel(
            self.exclude_info_frame,
            text="Complete-text exclusions, case-insensitive. '*' matches any following characters.\n"
                 "Example: test_text* excludes Test_Text, test_TEXT and test_text1234.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        )
        self.exclude_hint.pack(anchor="w")

        # Translation quality settings
        self.quality_label = ctk.CTkLabel(
            self.settings_frame, text="Translation Quality:", font=ctk.CTkFont(weight="bold")
        )
        self.quality_label.grid(row=6, column=0, padx=15, pady=(15, 5), sticky="nw")
        self.quality_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.quality_frame.grid(row=6, column=1, padx=15, pady=(15, 5), sticky="ew")

        self.proper_names_enabled_var = ctk.BooleanVar(value=True)
        self.proper_names_checkbox = ctk.CTkCheckBox(
            self.quality_frame, text="Protect proper names from proper_names.ini",
            variable=self.proper_names_enabled_var, command=self._save_settings_to_config
        )
        self.proper_names_checkbox.pack(anchor="w", pady=(0, 6))

        self.name_translations_enabled_var = ctk.BooleanVar(value=True)
        self.name_translations_checkbox = ctk.CTkCheckBox(
            self.quality_frame, text="Use defined name translations from name_translations.ini",
            variable=self.name_translations_enabled_var, command=self._save_settings_to_config
        )
        self.name_translations_checkbox.pack(anchor="w", pady=(0, 6))

        self.translation_memory_enabled_var = ctk.BooleanVar(value=True)
        self.translation_memory_checkbox = ctk.CTkCheckBox(
            self.quality_frame, text="Use Translation Memory",
            variable=self.translation_memory_enabled_var, command=self._save_settings_to_config
        )
        self.translation_memory_checkbox.pack(anchor="w", pady=(0, 6))

        self.translation_memory_auto_store_var = ctk.BooleanVar(value=True)
        self.translation_memory_auto_store_checkbox = ctk.CTkCheckBox(
            self.quality_frame, text="Automatically store new translations",
            variable=self.translation_memory_auto_store_var, command=self._save_settings_to_config
        )
        self.translation_memory_auto_store_checkbox.pack(anchor="w", pady=(0, 8))

        self.quality_buttons = ctk.CTkFrame(self.quality_frame, fg_color="transparent")
        self.quality_buttons.pack(fill="x")
        ctk.CTkButton(
            self.quality_buttons, text="Reload INI Files", width=120,
            command=self.reload_quality_files
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            self.quality_buttons, text="Open Proper Names", width=135,
            command=lambda: self._open_local_file(self.proper_names_file)
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            self.quality_buttons, text="Open Name Translations", width=155,
            command=lambda: self._open_local_file(self.name_translations_file)
        ).pack(side="left", padx=(0, 8))
        # Translation Memory actions are placed in a separate row.
        self.translation_memory_buttons = ctk.CTkFrame(
            self.quality_frame, fg_color="transparent"
        )
        self.translation_memory_buttons.pack(fill="x", pady=(8, 0))

        ctk.CTkButton(
            self.translation_memory_buttons,
            text="Open Translation Memory",
            width=155,
            command=lambda: self._open_local_file(self.translation_memory_file)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            self.translation_memory_buttons,
            text="Clear Translation Memory",
            width=165,
            fg_color="firebrick",
            hover_color="darkred",
            command=self.clear_translation_memory
        ).pack(side="left")














    # --- Profile Management Methods ---

    def on_profile_selected(self, selected_profile):
        """Callback triggered when a new language profile is selected from the combobox."""
        self.load_profile(selected_profile)
        self._save_settings_to_config()
        self.log_message(f"Language profile '{selected_profile}' loaded.")

    def load_profile(self, profile_name):
        """
        Activates checkboxes for the languages saved within the specified profile.
        
        Args:
            profile_name (str): The dictionary key for the requested profile.
        """
        if profile_name not in self.profiles:
            return

        selected_langs = self.profiles[profile_name]
        for name, (var, _, _) in self.checkboxes.items():
            var.set(name in selected_langs)

        self.update_target_languages_display()

    def save_current_profile(self):
        """Prompts user for a profile name via dialog and saves currently ticked languages."""
        selected_langs = [name for name, (var, _, _) in self.checkboxes.items() if var.get()]

        if not selected_langs:
            messagebox.showwarning("Warning", "Please select at least one language to save a profile!")
            return

        profile_name = simpledialog.askstring("Save Profile", "Enter a name for the language profile:")
        if not profile_name:
            return

        profile_name = profile_name.strip()
        if not profile_name:
            return

        if profile_name in ["Anno 117", "Anno 1800"]:
            messagebox.showerror("Error", f"The default profile '{profile_name}' cannot be overwritten!")
            return

        # Assign selected languages and save profile to disk
        self.profiles[profile_name] = selected_langs
        self._save_profiles_to_disk()

        # Update ComboBox values and active selection
        profile_list = list(self.profiles.keys())
        self.profile_combo.configure(values=profile_list)
        self.profile_combo.set(profile_name)
        self._save_settings_to_config()
        self.log_message(f"Profile '{profile_name}' saved.")

    def delete_current_profile(self):
        """Deletes the active profile, barring default immutable profiles."""
        current_profile = self.profile_combo.get()

        if current_profile in ["Anno 117", "Anno 1800"]:
            messagebox.showerror("Error", f"The default profile '{current_profile}' cannot be deleted!")
            return

        if current_profile not in self.profiles:
            return

        confirm = messagebox.askyesno("Delete Profile", f"Do you really want to delete the profile '{current_profile}'?")
        if confirm:
            del self.profiles[current_profile]
            self._save_profiles_to_disk()

            # Refresh list and fallback to default profile 'Anno 117'
            profile_list = list(self.profiles.keys())
            self.profile_combo.configure(values=profile_list)
            
            self.profile_combo.set("Anno 117")
            self.load_profile("Anno 117")
            self._save_settings_to_config()
            self.log_message(f"Profile '{current_profile}' deleted.")

    # --- General Helper Methods ---

    def _on_checkbox_toggled(self):
        """Callback to update summary labels when a language checkbox is toggled manually."""
        self.update_target_languages_display()

    def update_target_languages_display(self):
        """Updates the text label in the Main Menu summarizing currently selected target languages."""
        selected = [name for name, (var, _, _) in self.checkboxes.items() if var.get()]
        if selected:
            # Split languages into chunks (e.g., max 5 languages per line for clean text wrapping)
            chunk_size = 5
            chunks = [", ".join(selected[i:i + chunk_size]) for i in range(0, len(selected), chunk_size)]
            langs_formatted = "\n".join(chunks)
            
            text_str = f"Target Languages ({len(selected)}):\n{langs_formatted}"
        else:
            text_str = "Target Languages: None selected"

        self.target_langs_label.configure(text=text_str)

    def select_all_languages(self):
        """Ticks all language checkboxes simultaneously."""
        for var, _, _ in self.checkboxes.values():
            var.set(True)
        self.update_target_languages_display()

    def deselect_all_languages(self):
        """Unticks all language checkboxes simultaneously."""
        for var, _, _ in self.checkboxes.values():
            var.set(False)
        self.update_target_languages_display()

    def log_message(self, message):
        """
        Thread-safe method to append messages to the scrolling log UI.
        Applies specific color tags to strings containing keywords like ERROR or SAVED.
        
        Args:
            message (str): Text string to output to the UI log.
        """
        def _append():
            timestamp = time.strftime("[%H:%M:%S] ")
            self.log_textbox.configure(state="normal")
            
            # Configure custom color tags for distinct log severity levels
            self.log_textbox.tag_config("green_log", foreground="#2ecc71")
            self.log_textbox.tag_config("red_log", foreground="#e74c3c")
            self.log_textbox.tag_config("yellow_log", foreground="#f1c40f")
            
            if message.startswith("SAVED:"):
                self.log_textbox.insert("end", timestamp)
                self.log_textbox.insert("end", message + "\n", "green_log")

            elif message.startswith("ERROR:") or message.startswith("CRITICAL ERROR:"):
                self.log_textbox.insert("end", timestamp)
                self.log_textbox.insert("end", message + "\n", "red_log")

            elif (message.startswith("Download:") or 
                  message.startswith("Starting download to") or 
                  message.startswith("Download completed")):
                self.log_textbox.insert("end", timestamp)
                self.log_textbox.insert("end", message + "\n", "yellow_log")

            else:
                self.log_textbox.insert("end", timestamp + message + "\n")
                
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")

        # Safely interact with Tkinter main thread using self.after
        self.after(0, _append)

    def toggle_theme(self):
        """Toggles between Dark and Light CustomTkinter application themes."""
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")
        self._save_settings_to_config()

    def select_default_output_dir(self):
        """Select and persist the default output directory."""
        initial_dir = self.default_output_entry.get().strip()
        if not os.path.isdir(initial_dir):
            initial_dir = self.app_dir
        folder = filedialog.askdirectory(
            title="Select Default Output Folder",
            initialdir=initial_dir
        )
        if folder:
            self.default_output_entry.delete(0, "end")
            self.default_output_entry.insert(0, folder)
            self.output_directory = folder
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, folder)
            self._save_settings_to_config()
            self.log_message(f"Default output folder set: {folder}")

    def clear_default_output_dir(self):
        """Clear the configured default and return to the source-file-folder behavior."""
        self.default_output_entry.delete(0, "end")
        self._save_settings_to_config()
        if self.selected_file:
            source_folder = os.path.dirname(self.selected_file)
            self.output_directory = source_folder
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, source_folder)
        else:
            self.output_directory = ""
            self.out_entry.delete(0, "end")
        self.log_message("Default output folder cleared. Source file folder will be used.")

    def select_file(self):
        """Opens a file dialog for the user to select the source XML file."""
        path = filedialog.askopenfilename(
            title="Select Anno XML File",
            filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")]
        )
        if path:
            self.selected_file = path
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)

            # Use the configured default output folder. If none is configured,
            # retain the original behavior and use the source file folder.
            configured_default = self.default_output_entry.get().strip()
            default_dir = configured_default or os.path.dirname(path)
            self.output_directory = default_dir
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, default_dir)
            self.log_message(f"File loaded: {os.path.basename(path)}")

    def select_output_dir(self):
        """Opens a directory dialog for the user to select the output destination folder."""
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_directory = folder
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, folder)
            self.log_message(f"Output folder set: {folder}")

    def get_selected_languages(self):
        """Returns a list of tuples containing data for all currently checked target languages."""
        return [
            (code, suffix, name) 
            for name, (var, code, suffix) in self.checkboxes.items() 
            if var.get()
        ]








    def toggle_translation(self):
        """Action handler attached to the main action button. Toggles Start/Cancel state."""
        if self.is_translating:
            self.cancel_requested = True
            self.log_message("Cancellation requested...")
            self.btn_action.configure(state="disabled", text="Canceling...")
        else:
            self.start_translation()

    def start_translation(self):
        """Performs pre-flight checks and initialization before launching the background translation thread."""
        if not self.selected_file or not os.path.exists(self.selected_file):
            messagebox.showerror("Error", "Please select a valid XML file!")
            return

        out_dir = self.out_entry.get().strip()
        if not out_dir:
            out_dir = (
                self.default_output_entry.get().strip()
                or os.path.dirname(self.selected_file)
            )

        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Output folder could not be created:\n{e}")
                return

        self.output_directory = out_dir

        selected_langs = self.get_selected_languages()
        if not selected_langs:
            messagebox.showerror("Error", "Please select at least one target language!")
            return

        source_code = self.detect_source_language_code()
        # Filter out source language from target languages list
        filtered_langs = [l for l in selected_langs if l[0] != source_code]

        if not filtered_langs:
            messagebox.showinfo("Information", "No target languages selected (or language matches source language).")
            return

        # Force UI to switch back to Main Menu tab
        self.tabview.set("Main Menu")

        self.is_translating = True
        self.cancel_requested = False
        self.start_time = time.time()

        # Update action buttons state and appearance
        self.btn_action.configure(text="Cancel Translation", fg_color="firebrick", hover_color="darkred")
        self.btn_browse.configure(state="disabled")
        self.btn_out_browse.configure(state="disabled")

        mode = self.mode_combo.get()
        self.log_message(f"--- Translation started (Mode: {mode}) ---")

        if mode == "Parallel":
            target_target = self.process_parallel_translation
        else:
            target_target = self.process_multi_translation

        # Start background daemon thread
        threading.Thread(
            target=target_target, 
            args=(source_code, filtered_langs), 
            daemon=True
        ).start()




    def update_status_and_time(self, text, progress_val, elapsed, remaining):
        """Helper to thread-safely update GUI timing and progress indicator widgets."""
        def _update():
            self.status_label.configure(text=text)
            self.progress.set(progress_val)
            
            elapsed_str = self.format_seconds(elapsed)
            if remaining > 0 and progress_val < 1.0:
                eta_str = f"~{self.format_seconds(remaining)}"
            else:
                eta_str = "00:00:00"

            self.time_label.configure(text=f"Runtime: {elapsed_str} | ETA: {eta_str}")

        self.after(0, _update)

    def update_translation_preview(self, sent_text, received_text):
        """Helper to thread-safely update real-time translation preview textboxes."""
        def _update():
            for textbox, value in (
                (self.sent_textbox, sent_text),
                (self.received_textbox, received_text),
            ):
                textbox.configure(state="normal")
                textbox.delete("1.0", "end")
                textbox.insert("1.0", "" if value is None else str(value))
                textbox.configure(state="disabled")

        self.after(0, _update)

    def update_progress_count(self, language_name, processed_count, total_count):
        """Thread-safe UI label modification for XML node counters."""
        self.after(
            0,
            lambda: self.progress_count_label.configure(
                text=f"[{language_name}] Texts: {processed_count}/{total_count}"
            )
        )

    def reset_ui(self):
        """Restores default buttons and unlocks the user interface post-translation loop."""
        self.is_translating = False
        self.cancel_requested = False

        def _reset():
            self.btn_action.configure(
                state="normal", 
                text="Start Translation", 
                fg_color=("#3a7ebf", "#1f538d"), 
                hover_color=("#32689e", "#14375e")
            )
            self.btn_browse.configure(state="normal")
            self.btn_out_browse.configure(state="normal")

        self.after(0, _reset)


if __name__ == "__main__":
    app = AnnoXMLTranslatorApp()
    app.mainloop()