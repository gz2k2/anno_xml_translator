"""Persistent configuration and language-profile services.

This module isolates file-system persistence from the graphical user interface.
The mixin expects the host application to provide widget attributes created by
its UI builder. Keeping persistence here makes configuration behavior easier to
test and prevents the main window class from becoming a monolithic controller.
"""

import configparser
import json
import os
import shutil
from tkinter import messagebox
import customtkinter as ctk


class ConfigurationMixin:
    """Provide migration, profile persistence, and application settings I/O."""

    def _migrate_legacy_config_files(self):
        """Move existing configuration files from the old root location to config/."""
        config_names = (
            "language_profiles.json",
            "config.ini",
            "proper_names.ini",
            "name_translations.ini",
            "translation_memory.ini",
        )
        for file_name in config_names:
            old_path = os.path.join(self.app_dir, file_name)
            new_path = os.path.join(self.config_dir, file_name)
            if os.path.isfile(old_path) and not os.path.exists(new_path):
                try:
                    shutil.move(old_path, new_path)
                    print(f"Migrated configuration file: {old_path} -> {new_path}")
                except OSError as error:
                    print(f"Could not migrate configuration file '{file_name}': {error}")
    def _load_profiles(self):
        """
        Loads user-saved language profiles from the JSON configuration file.
        If the file doesn't exist, establishes default profiles for Anno 1800 and Anno 117.
        """
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    self.profiles = json.load(f)
            except Exception as e:
                print(f"Error loading profiles: {e}")
                self.profiles = {}

        # Fallback / Default Profiles for Anno titles
        self.profiles["Anno 1800"] = [
            "Brazilian (pt-BR)", "Chinese (zh-CN)", "English (en)",
            "French (fr)", "German (de)", "Italian (it)", "Japanese (ja)",
            "Korean (ko)", "Polish (pl)", "Portuguese (pt-PT)", "Russian (ru)",
            "Spanish (es)", "Taiwanese (zh-TW)"
        ]

        self.profiles["Anno 117"] = [
            "Brazilian (pt-BR)", "English (en)", "French (fr)", "German (de)",
            "Italian (it)", "Japanese (ja)", "Korean (ko)", "Polish (pl)",
            "Russian (ru)", "Simplified Chinese (zh, Anno 117)", "Spanish (es)",
            "Traditional Chinese (zt, Anno 117)"
        ]

        self._save_profiles_to_disk()
    def _save_profiles_to_disk(self):
        """
        Writes the current language profiles dictionary to a local JSON file.
        """
        try:
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Profiles could not be saved:\n{e}")
    def _load_settings_from_config(self):
        """
        Loads saved translation settings from the `config.ini` file 
        and updates the respective UI elements accordingly.
        """
        config = configparser.ConfigParser()
        selected_profile = "Anno 117"
        theme = "Dark"
        
        if os.path.exists(self.config_file):
            try:
                config.read(self.config_file, encoding="utf-8")
                if "Settings" in config:
                    settings = config["Settings"]

                    # Load theme setting (defaulting to Dark)
                    if "theme" in settings:
                        loaded_theme = settings["theme"].strip().capitalize()
                        if loaded_theme in ["Dark", "Light"]:
                            theme = loaded_theme

                    # Load mode setting into UI component
                    if "mode" in settings and settings["mode"] in ["Parallel", "One-by-One"]:
                        self.mode_combo.set(settings["mode"])

                    # Load batch size setting
                    if "batch_size" in settings and settings["batch_size"] in ["1", "5", "10", "25", "50"]:
                        self.batch_combo.set(settings["batch_size"])

                    # Load auto-batch toggle
                    if "auto_batch_enabled" in settings:
                        self.auto_batch_var.set(settings.getboolean("auto_batch_enabled", fallback=True))

                    # Load auto-batch max character threshold
                    if "auto_batch_max_chars" in settings:
                        self.auto_batch_entry.delete(0, "end")
                        self.auto_batch_entry.insert(0, settings["auto_batch_max_chars"])

                    # Load compute precision type
                    if "compute_type" in settings:
                        stored_compute_type = settings["compute_type"]
                        if stored_compute_type in self.compute_type_labels_reverse:
                            self.compute_combo.set(
                                self.compute_type_labels_reverse[stored_compute_type]
                            )
                        elif stored_compute_type in self.compute_type_labels:
                            self.compute_combo.set(stored_compute_type)

                    # Load default output directory
                    if "default_output_directory" in settings:
                        default_output_directory = settings["default_output_directory"].strip()
                        self.default_output_entry.delete(0, "end")
                        self.default_output_entry.insert(0, default_output_directory)
                        if default_output_directory and not self.out_entry.get().strip():
                            self.output_directory = default_output_directory
                            self.out_entry.delete(0, "end")
                            self.out_entry.insert(0, default_output_directory)

                    # Load user exclusions string
                    if "exclude_list" in settings:
                        self.exclude_entry.delete(0, "end")
                        self.exclude_entry.insert(0, settings["exclude_list"])

                    # Load translation quality settings
                    if "proper_names_enabled" in settings:
                        self.proper_names_enabled_var.set(settings.getboolean("proper_names_enabled", fallback=True))
                    if "name_translations_enabled" in settings:
                        self.name_translations_enabled_var.set(settings.getboolean("name_translations_enabled", fallback=True))
                    if "translation_memory_enabled" in settings:
                        self.translation_memory_enabled_var.set(settings.getboolean("translation_memory_enabled", fallback=True))
                    if "translation_memory_auto_store" in settings:
                        self.translation_memory_auto_store_var.set(settings.getboolean("translation_memory_auto_store", fallback=True))
                    # Load active profile selection
                    if "selected_profile" in settings and settings["selected_profile"] in self.profiles:
                        selected_profile = settings["selected_profile"]

            except Exception as e:
                print(f"Error loading settings from config.ini: {e}")

        # Apply theme setting
        ctk.set_appearance_mode(theme)
        if hasattr(self, "theme_switch"):
            if theme == "Dark":
                self.theme_switch.select()
            else:
                self.theme_switch.deselect()

        # Set dropdown and populate checkboxes for the selected profile
        self.profile_combo.set(selected_profile)
        self.load_profile(selected_profile)
    def _save_settings_to_config(self, *args):
        """
        Gathers current UI inputs and saves them into the `config.ini` file for persistence.
        """
        theme_val = "Dark"
        if hasattr(self, "theme_switch"):
            theme_val = "Dark" if self.theme_switch.get() == 1 else "Light"
        elif ctk.get_appearance_mode().lower() == "light":
            theme_val = "Light"

        config = configparser.ConfigParser()
        config["Settings"] = {
            "theme": theme_val,
            "mode": self.mode_combo.get(),
            "batch_size": self.batch_combo.get(),
            "auto_batch_enabled": str(self.auto_batch_var.get()),
            "auto_batch_max_chars": self.auto_batch_entry.get().strip(),
            "compute_type": self._get_selected_compute_type(),
            "default_output_directory": self.default_output_entry.get().strip(),
            "exclude_list": self.exclude_entry.get().strip(),
            "proper_names_enabled": str(self.proper_names_enabled_var.get()),
            "name_translations_enabled": str(self.name_translations_enabled_var.get()),
            "translation_memory_enabled": str(self.translation_memory_enabled_var.get()),
            "translation_memory_auto_store": str(self.translation_memory_auto_store_var.get()),
            "selected_profile": self.profile_combo.get()
        }

        try:
            with open(self.config_file, "w", encoding="utf-8") as configfile:
                config.write(configfile)
        except Exception as e:
            print(f"Error saving config.ini: {e}")
