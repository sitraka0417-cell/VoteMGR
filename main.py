# -*- coding: utf-8 -*-
"""
main.py — Point d'entrée de VoteMGR (Windows).

Lancement en développement :   python main.py
Lancement une fois compilé :   VoteMGR.exe (voir installer/build.bat)
"""

import sys
import os
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.secretary import SecretaryApp


def main():
    app = SecretaryApp()
    try:
        style = ttk.Style(app)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
    except Exception:
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
