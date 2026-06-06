"""
format_editor.py — GUI for managing signal format presets and custom formats.

Provides a notebook tab ``_SignalFormatsTab`` and a dialog
``FormatEditorDialog`` for token-tagging sample messages into regex
patterns.
"""

from __future__ import annotations

import logging
import re
import tkinter as tk
from tkinter import ttk, messagebox

from format_manager import (
    FormatManager,
    SignalFormatProfile,
    TaggedToken,
    build_regex_from_tokens,
    tokenize_sample,
    get_manager,
)

_log = logging.getLogger(__name__)

_TAG_OPTIONS = ["literal", "ignore", "action", "symbol", "entry", "sl", "tp1", "tp2"]

# -------------------------------------------------------------------
# Format Editor Dialog
# -------------------------------------------------------------------


class FormatEditorDialog(tk.Toplevel):
    """
    Modal dialog for creating or editing a custom signal format.

    Token-tagger UI:
      1. Paste a sample message and click Tokenize.
      2. Use the dropdown next to each word to label it.
      3. Generated regex updates automatically.
      4. Paste up to 3 test samples and click **Run Tests**.
      5. Click **Save** to store the profile.
    """

    def __init__(
        self,
        master: tk.Tk | tk.Toplevel,
        format_manager: FormatManager,
        on_save: callable | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Custom Signal Format Editor")
        self.geometry("700x750")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._format_manager = format_manager
        self._on_save = on_save

        self._tokens: list[str] = []
        self._tag_vars: list[tk.StringVar] = []
        self._combos: list[ttk.Combobox] = []

        # -- Top: name row -----------------------------------------------
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Format Name:").pack(side="left", padx=4)
        self._name_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._name_var, width=40).pack(side="left", padx=4)

        # -- Sample message ----------------------------------------------
        sample_frame = ttk.LabelFrame(self, text="Sample Message", padding=8)
        sample_frame.pack(fill="x", padx=8, pady=4)

        self._sample_text = tk.Text(sample_frame, height=4, width=70)
        self._sample_text.pack(fill="x")
        ttk.Button(
            sample_frame, text="Tokenize", command=self._on_tokenize
        ).pack(anchor="e", pady=4)

        # -- Token grid --------------------------------------------------
        self._token_container = ttk.LabelFrame(self, text="Tag Each Word", padding=8)
        self._token_container.pack(fill="both", expand=True, padx=8, pady=4)

        # Placeholder label (hidden after tokenize)
        self._token_placeholder = ttk.Label(
            self._token_container, text="Click Tokenize to load words from the sample."
        )
        self._token_placeholder.pack()

        self._token_grid = ttk.Frame(self._token_container)
        # not packed until tokenize

        # -- Generated regex ---------------------------------------------
        regex_frame = ttk.LabelFrame(self, text="Generated Regex", padding=8)
        regex_frame.pack(fill="x", padx=8, pady=4)
        self._regex_var = tk.StringVar()
        ttk.Entry(regex_frame, textvariable=self._regex_var, state="readonly").pack(
            fill="x"
        )

        # -- Test area ---------------------------------------------------
        test_frame = ttk.LabelFrame(self, text="Test Your Format", padding=8)
        test_frame.pack(fill="x", padx=8, pady=4)

        self._test_samples: list[tk.Text] = []
        self._test_results: list[ttk.Label] = []
        for i in range(3):
            row = ttk.Frame(test_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"Sample {i + 1}:").pack(side="left")
            txt = tk.Text(row, height=2, width=45)
            txt.pack(side="left", padx=4)
            self._test_samples.append(txt)
            lbl = ttk.Label(row, text="—")
            lbl.pack(side="left", padx=4)
            self._test_results.append(lbl)

        ttk.Button(test_frame, text="Run Tests", command=self._on_test).pack(
            anchor="e", pady=4
        )

        # -- Buttons -----------------------------------------------------
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        ttk.Button(btn_frame, text="Save", command=self._on_save_click).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=4
        )

        self.wait_window()

    # -- internal helpers -----------------------------------------------

    def _on_tokenize(self) -> None:
        text = self._sample_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty Sample", "Paste a sample message first.")
            return
        self._tokens = tokenize_sample(text)
        self._build_token_grid()
        self._update_regex()

    def _build_token_grid(self) -> None:
        # Clear old
        for combo in self._combos:
            combo.destroy()
        self._combos.clear()
        self._tag_vars.clear()
        for widget in self._token_grid.winfo_children():
            widget.destroy()
        self._token_placeholder.pack_forget()
        self._token_grid.pack(fill="both", expand=True)

        for i, token in enumerate(self._tokens):
            row = i // 4
            col = (i % 4) * 2
            cell = ttk.Frame(self._token_grid)
            cell.grid(row=row, column=col, columnspan=2, padx=6, pady=4, sticky="w")

            ttk.Label(cell, text=token, font=("Consolas", 9, "bold")).pack(anchor="w")
            var = tk.StringVar(value="literal")
            var.trace_add("write", lambda *args, idx=i: self._update_regex())
            self._tag_vars.append(var)

            combo = ttk.Combobox(
                cell,
                textvariable=var,
                values=_TAG_OPTIONS,
                state="readonly",
                width=12,
            )
            combo.pack(anchor="w")
            self._combos.append(combo)

    def _update_regex(self) -> None:
        if not self._tokens:
            return
        tagged = [
            TaggedToken(text=tk, tag=var.get())
            for tk, var in zip(self._tokens, self._tag_vars)
        ]
        rx = build_regex_from_tokens(tagged)
        self._regex_var.set(rx)

    def _on_test(self) -> None:
        rx = self._regex_var.get()
        if not rx:
            messagebox.showwarning("No Regex", "Tokenize a sample first.")
            return
        try:
            fm = FormatManager()
            samples = [t.get("1.0", "end").strip() for t in self._test_samples]
            results = fm.test_pattern(rx, samples)
        except ValueError as exc:
            messagebox.showerror("Regex Error", str(exc))
            return

        for lbl, sig in zip(self._test_results, results):
            if sig is None:
                lbl.config(text="No match", foreground="red")
            else:
                lbl.config(
                    text=f"✓ {sig.action} {sig.symbol} E={sig.entry}",
                    foreground="green",
                )

    def _on_save_click(self) -> None:
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Missing Name", "Enter a name for this format.")
            return

        rx = self._regex_var.get()
        if not rx:
            messagebox.showerror("Missing Regex", "Tokenize a sample first.")
            return

        try:
            compiled = re.compile(rx, re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            messagebox.showerror("Invalid Regex", str(exc))
            return

        # Check required named groups
        required = {"action", "entry", "sl", "tp1", "tp2"}
        found = set(compiled.groupindex.keys())
        missing = required - found
        if missing:
            messagebox.showerror(
                "Missing Fields",
                f"Your regex is missing these required fields: {', '.join(sorted(missing))}",
            )
            return

        try:
            profile = self._format_manager.add_custom_profile(
                name=name, pattern=rx, template=None
            )
            self._format_manager.save_to_config()
            _log.info("Saved custom format '%s' (%s).", profile.name, profile.id)
            if self._on_save:
                self._on_save(profile)
        except ValueError as exc:
            messagebox.showerror("Save Failed", str(exc))
            return

        self.destroy()


# -------------------------------------------------------------------
# Signal Formats Tab
# -------------------------------------------------------------------


class _SignalFormatsTab(ttk.Frame):
    """
    Notebook tab listing built-in and custom signal format profiles.
    Users can add or delete custom formats from here.
    """

    def __init__(
        self,
        parent: ttk.Notebook,
        format_manager: FormatManager,
        logger: logging.Logger,
    ) -> None:
        super().__init__(parent)
        self._format_manager = format_manager
        self._log = logger

        content = ttk.Frame(self, padding=16)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="Signal Formats", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        # Profile list
        self._tree = ttk.Treeview(
            content,
            columns=("type", "id", "pattern"),
            show="headings",
            height=12,
        )
        self._tree.heading("#0", text="Name")
        self._tree.heading("type", text="Type")
        self._tree.heading("id", text="ID")
        self._tree.heading("pattern", text="Pattern")
        self._tree.column("#0", width=180)
        self._tree.column("type", width=80, anchor="center")
        self._tree.column("id", width=140)
        self._tree.column("pattern", width=300)
        self._tree.pack(fill="both", expand=True, pady=4)

        # Detail pane
        detail_frame = ttk.LabelFrame(content, text="Selected Format", padding=8)
        detail_frame.pack(fill="x", pady=8)
        self._detail_var = tk.StringVar(value="Select a format to view its pattern.")
        ttk.Label(detail_frame, textvariable=self._detail_var, wraplength=650).pack(
            fill="x"
        )

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill="x", pady=8)
        ttk.Button(btn_frame, text="Add Custom Format", command=self._on_add).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="Delete Selected", command=self._on_delete).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="Refresh", command=self._refresh).pack(
            side="left", padx=4
        )

        self._refresh()

    def _refresh(self) -> None:
        """Reload the tree from the format manager."""
        for item in self._tree.get_children():
            self._tree.delete(item)
        for profile in self._format_manager.all_profiles():
            typ = "Built-in" if profile.is_builtin else "Custom"
            self._tree.insert(
                "",
                "end",
                iid=profile.id,
                text=profile.name,
                values=(typ, profile.id, profile.pattern),
            )
        self._detail_var.set("Select a format to view its pattern.")

    def _on_select(self, _event: tk.Event) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        profile = self._format_manager.all_profiles()
        item = self._tree.item(sel[0])
        self._detail_var.set(f"ID: {item['values'][1]}\nPattern: {item['values'][2]}")

    def _on_add(self) -> None:
        FormatEditorDialog(self, self._format_manager, on_save=self._on_profile_added)

    def _on_profile_added(self, _profile: SignalFormatProfile) -> None:
        self._refresh()
        self._log.info("Custom format added: %s", _profile.name)

    def _on_delete(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a custom format to delete.")
            return
        profile_id = sel[0]
        profile = next(
            (p for p in self._format_manager.all_profiles() if p.id == profile_id), None
        )
        if profile is None or profile.is_builtin:
            messagebox.showwarning("Built-in", "Built-in presets cannot be deleted.")
            return
        if messagebox.askyesno(
            "Confirm Delete", f"Delete custom format '{profile.name}'?"
        ):
            if self._format_manager.delete_custom_profile(profile_id):
                self._format_manager.save_to_config()
                self._refresh()
                self._log.info("Deleted custom format %s.", profile_id)
