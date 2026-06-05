# tk_stub.py — headless tkinter stub for test environments
"""
Safe no-op classes that pass isinstance() and super().__init__() checks
without requiring a display or real tkinter installation.
"""

import sys


# ── Base widget ───────────────────────────────────────────────────────────────

class Tk:
    def __init__(self, *a, **k): pass

    def after(self, *a, **k): return 0

    def destroy(self): pass

    def mainloop(self): pass

    def protocol(self, *a, **k): pass

    def title(self, *a, **k): pass

    def resizable(self, *a, **k): pass

    def winfo_x(self): return 0

    def winfo_y(self): return 0

    def winfo_width(self): return 800

    def winfo_height(self): return 600

    def withdrawing(self): pass

    def update_idletasks(self): pass

    def geometry(self, *a, **k): pass

    def bind(self, *a, **k): pass

    def withdraw(self): pass

    def deiconify(self): pass

    def wait_window(self, *a, **k): pass

    def grab_set(self): pass

    def transient(self, *a, **k): pass


# ── Top-level widget classes (also referenced by the ttk namespace below) ─────

class Toplevel(Tk):
    pass


class Frame(Tk):
    pass


class ScrolledText(Tk):
    END = "end"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._text = ""

    def configure(self, **k): pass

    def insert(self, index, text):
        # index is ignored in this no-op stub; just accumulate
        self._text += text

    def see(self, *a, **k): pass

    def get(self, *a, **k): return self._text

    def delete(self, *a, **k): pass


class StringVar:
    def __init__(self, *a, **k): self._value = k.get("value", "")

    def get(self): return self._value

    def set(self, v): self._value = v

    def trace_add(self, *a, **k): pass


class IntVar(StringVar):
    def get(self): return int(self._value)


class DoubleVar(StringVar):
    def get(self): return float(self._value)


class messagebox:
    @staticmethod
    def showerror(*a, **k): pass

    @staticmethod
    def showwarning(*a, **k): pass

    @staticmethod
    def showinfo(*a, **k): pass


# ── ttk widget classes (also exposed at top-level for direct use) ─────────────

class TtkFrame(Tk):
    def pack(self, *a, **k): pass

    def grid(self, *a, **k): pass

    def columnconfigure(self, *a, **k): pass

    def rowconfigure(self, *a, **k): pass

    def config(self, *a, **k): pass

    def configure(self, *a, **k): pass


class TtkNotebook(Tk):
    def pack(self, *a, **k): pass

    def grid(self, *a, **k): pass

    def columnconfigure(self, *a, **k): pass

    def rowconfigure(self, *a, **k): pass

    def add(self, *a, **k): pass

    def config(self, *a, **k): pass

    def configure(self, *a, **k): pass


class TtkButton(Tk):
    def pack(self, *a, **k): pass

    def grid(self, *a, **k): pass

    def config(self, *a, **k): pass

    def configure(self, *a, **k): pass


class TtkEntry(Tk):
    def __init__(self, *a, **k): super().__init__(*a, **k)

    def grid(self, *a, **k): pass

    def pack(self, *a, **k): pass

    def columnconfigure(self, *a, **k): pass

    def rowconfigure(self, *a, **k): pass

    def config(self, *a, **k): pass

    def configure(self, *a, **k): pass

    def cget(self, *a, **k): return ""

    def delete(self, *a, **k): pass

    def insert(self, *a, **k): pass

    def get(self, *a, **k): return ""


class TtkLabel(Tk):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._text = k.get("text", "")

    def pack(self, *a, **k): pass

    def grid(self, *a, **k): pass

    def config(self, **k):
        if "text" in k:
            self._text = k["text"]

    def configure(self, *a, **k): pass

    def cget(self, key):
        if key == "text":
            return self._text
        return ""

    def columnconfigure(self, *a, **k): pass

    def rowconfigure(self, *a, **k): pass


class TtkCheckbutton(Tk):
    def pack(self, *a, **k): pass

    def grid(self, *a, **k): pass

    def config(self, *a, **k): pass

    def configure(self, *a, **k): pass

    def columnconfigure(self, *a, **k): pass

    def rowconfigure(self, *a, **k): pass


class TtkCombobox(Tk):
    def pack(self, *a, **k): pass

    def grid(self, *a, **k): pass

    def config(self, *a, **k): pass

    def configure(self, *a, **k): pass

    def columnconfigure(self, *a, **k): pass

    def rowconfigure(self, *a, **k): pass

    def current(self, *a, **k): pass

    def set(self, v): pass

    def get(self, *a, **k): return ""


class TtkSeparator(Tk):
    def pack(self, *a, **k): pass

    def grid(self, *a, **k): pass

    def columnconfigure(self, *a, **k): pass

    def rowconfigure(self, *a, **k): pass


# ── Fake ttk module (must be set up after all widget classes are defined) ─────

class _ttk_module:
    Frame = TtkFrame
    Notebook = TtkNotebook
    Button = TtkButton
    Entry = TtkEntry
    Label = TtkLabel
    Checkbutton = TtkCheckbutton
    Combobox = TtkCombobox
    Separator = TtkSeparator


ttk = _ttk_module()


# ── Module-level constants ────────────────────────────────────────────────────

W = "w"
HORIZONTAL = "horizontal"
BOTH = "both"
LEFT = "left"
RIGHT = "right"
X = "x"
Y = "y"
EW = "ew"
END = "end"
BOTH_EXPAND = ("both", "expand")


# ── Fake scrolledtext submodule ───────────────────────────────────────────────

class _scrolledtext_module:
    ScrolledText = ScrolledText
    END = END


scrolledtext = _scrolledtext_module()