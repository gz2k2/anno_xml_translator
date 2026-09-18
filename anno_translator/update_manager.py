"""Argos language-model update checking and installation.

This module adds an explicit, user-triggered update check for the installed
Argos Translate models. Argos never updates models on its own: once a package
is installed, the locally cached `.argosmodel` file is reused forever, even if
a newer revision was published in the online index.

The workflow implemented here is:

    1. Refresh the online package index.
    2. Compare the `package_version` of every installed package against the
       highest version offered online for the same language route.
    3. Ask the user for confirmation, listing the concrete routes and versions.
    4. Download all updates first, then replace the old packages.

All network and installation work runs in a background thread so the GUI stays
responsive; every widget access is marshalled back to the Tk main thread via
`self.after`.
"""

from __future__ import annotations

import os
import re
import threading
from tkinter import messagebox

import argostranslate.package
import argostranslate.translate


def parse_package_version(raw_version) -> tuple:
    """Convert a version string such as "1.9" or "1.0.2" into a comparable tuple.

    Unknown or unparsable values return (0,), which sorts below every real
    version and therefore never triggers a false update offer.
    """
    if not raw_version:
        return (0,)
    numbers = re.findall(r"\d+", str(raw_version))
    if not numbers:
        return (0,)
    return tuple(int(number) for number in numbers)


class ModelUpdateMixin:
    """Provide the "Check for Model Updates" feature used by the Settings tab."""

    # ------------------------------------------------------------------
    # Entry point (button command)
    # ------------------------------------------------------------------
    def check_for_model_updates(self):
        """Start the update check in a background thread."""
        if getattr(self, "is_translating", False):
            messagebox.showinfo(
                "Model Update",
                "A translation is currently running.\n\n"
                "Please wait until it has finished before checking for model updates."
            )
            return

        # Guard against a second click while a check is still running.
        if getattr(self, "_model_update_running", False):
            return
        self._model_update_running = True

        self.cancel_requested = False
        self._set_model_update_button_state(False, "Checking...")
        self.log_message("Checking online index for newer language models...")

        threading.Thread(target=self._model_update_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------
    def _model_update_worker(self):
        """Collect available updates and hand the result back to the UI thread."""
        try:
            updates = self._collect_model_updates()
        except Exception as error:
            self.log_message(f"ERROR: Model update check failed: {error}")
            self.after(0, lambda: self._finish_model_update_check(
                None, f"The update check failed:\n\n{error}"
            ))
            return

        self.after(0, lambda: self._finish_model_update_check(updates, None))

    def _collect_model_updates(self):
        """Return [(installed_package, available_package)] for outdated models."""
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        installed_packages = argostranslate.package.get_installed_packages()

        # Keep only the highest published version per language route.
        newest_available = {}
        for package in available_packages:
            route = (package.from_code, package.to_code)
            current_best = newest_available.get(route)
            if (current_best is None
                    or parse_package_version(package.package_version)
                    > parse_package_version(current_best.package_version)):
                newest_available[route] = package

        updates = []
        for installed in installed_packages:
            candidate = newest_available.get((installed.from_code, installed.to_code))
            if candidate is None:
                continue
            if (parse_package_version(candidate.package_version)
                    > parse_package_version(installed.package_version)):
                updates.append((installed, candidate))

        updates.sort(key=lambda pair: (pair[0].from_code, pair[0].to_code))
        self.log_message(
            f"Update check finished: {len(installed_packages)} installed model(s), "
            f"{len(updates)} update(s) available."
        )
        return updates

    # ------------------------------------------------------------------
    # User confirmation
    # ------------------------------------------------------------------
    def _finish_model_update_check(self, updates, error_message):
        """Show the result of the check and ask whether to install the updates."""
        self._set_model_update_button_state(True, "Check for Model Updates")
        self._model_update_running = False

        if error_message:
            messagebox.showerror("Model Update", error_message)
            return

        if not updates:
            messagebox.showinfo(
                "Model Update",
                "All installed language models are up to date."
            )
            return

        summary_lines = [
            f"  {installed.from_code} -> {installed.to_code}:  "
            f"{installed.package_version or '?'}  ->  {candidate.package_version}"
            for installed, candidate in updates
        ]
        # Keep the dialog readable if many models are outdated.
        shown = summary_lines[:15]
        if len(summary_lines) > len(shown):
            shown.append(f"  ... and {len(summary_lines) - len(shown)} more")

        confirmed = messagebox.askyesno(
            "Model Update",
            f"{len(updates)} newer language model(s) found:\n\n"
            + "\n".join(shown)
            + "\n\nDo you want to download and install these updates now?"
        )
        if not confirmed:
            self.log_message("Model update canceled by user.")
            return

        self._model_update_running = True
        self._set_model_update_button_state(False, "Updating...")
        threading.Thread(
            target=self._perform_model_updates, args=(updates,), daemon=True
        ).start()

    # ------------------------------------------------------------------
    # Download and installation
    # ------------------------------------------------------------------
    def _perform_model_updates(self, updates):
        """Download every update first, then replace the installed packages.

        Downloading before uninstalling matters: if a download fails or is
        canceled, the existing model stays installed and the application remains
        fully usable.
        """
        installed_count = 0
        failed_routes = []
        try:
            downloaded = []
            for installed, candidate in updates:
                if self.cancel_requested:
                    break
                route = f"{candidate.from_code} -> {candidate.to_code}"
                links = getattr(candidate, "links", None)
                if not links:
                    self.log_message(f"ERROR: No download link for {route}.")
                    failed_routes.append(route)
                    continue

                target_name = f"{candidate.from_code}_{candidate.to_code}.argosmodel"
                target_path = os.path.join(self.packages_dir, target_name)
                temp_path = target_path + ".new"

                self.log_message(
                    f"Starting download to '{self.packages_dir}'... "
                    f"({route}, version {candidate.package_version})"
                )
                try:
                    success = self.download_file_with_progress(links[0], temp_path)
                except Exception as error:
                    self.log_message(f"ERROR: Download failed for {route}: {error}")
                    success = False

                if not success or self.cancel_requested:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    if not self.cancel_requested:
                        failed_routes.append(route)
                    continue

                self.log_message(f"Download completed: {route}")
                downloaded.append((installed, candidate, target_path, temp_path))

            # Replace the old packages only after all downloads are done.
            for installed, candidate, target_path, temp_path in downloaded:
                route = f"{candidate.from_code} -> {candidate.to_code}"
                try:
                    try:
                        argostranslate.package.uninstall(installed)
                    except Exception as error:
                        # Not fatal: installing the newer package still works,
                        # the old revision simply stays on disk.
                        self.log_message(
                            f"WARNING: Old package {route} could not be removed: {error}"
                        )
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    os.replace(temp_path, target_path)
                    argostranslate.package.install_from_path(target_path)
                    installed_count += 1
                    self.log_message(
                        f"SAVED: Model {route} updated to version "
                        f"{candidate.package_version}."
                    )
                except Exception as error:
                    self.log_message(f"ERROR: Installation failed for {route}: {error}")
                    failed_routes.append(route)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
        finally:
            self.after(
                0,
                lambda: self._finish_model_update_install(installed_count, failed_routes)
            )

    def _finish_model_update_install(self, installed_count, failed_routes):
        """Reset the UI and report the installation result."""
        self._set_model_update_button_state(True, "Check for Model Updates")
        self._model_update_running = False
        self.progress.set(0)
        self.status_label.configure(text="Ready")

        if self.cancel_requested:
            self.cancel_requested = False
            self.log_message("Model update canceled.")
            messagebox.showinfo("Model Update", "The model update was canceled.")
            return

        message = f"Updated language models: {installed_count}"
        if failed_routes:
            message += "\n\nFailed:\n" + "\n".join(f"  {route}" for route in failed_routes)
            messagebox.showwarning("Model Update", message)
        else:
            messagebox.showinfo("Model Update", message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_model_update_button_state(self, enabled: bool, text: str):
        """Enable/disable the Settings button; safe to call from any thread."""
        button = getattr(self, "btn_check_model_updates", None)
        if button is None:
            return
        self.after(
            0,
            lambda: button.configure(state="normal" if enabled else "disabled", text=text)
        )
