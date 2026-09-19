# -*- coding: utf-8 -*-
"""
monitors.py — Détection des écrans connectés (pour placer l'écran de
projection sur le 2e moniteur). Utilise uniquement ctypes + user32.dll
(aucune dépendance externe type pywin32 nécessaire).

Sur un système non-Windows (développement), on retombe sur un seul
"écran" correspondant à l'écran principal détecté par Tkinter.
"""

import sys


class Ecran:
    def __init__(self, x, y, largeur, hauteur, principal=False):
        self.x = x
        self.y = y
        self.largeur = largeur
        self.hauteur = hauteur
        self.principal = principal

    def geometrie(self):
        return "%dx%d+%d+%d" % (self.largeur, self.hauteur, self.x, self.y)

    def __repr__(self):
        return "Ecran(%dx%d @ %d,%d%s)" % (
            self.largeur, self.hauteur, self.x, self.y,
            ", principal" if self.principal else "")


def lister_ecrans():
    """Renvoie la liste des Ecran détectés. Le premier de la liste est
    toujours l'écran principal."""
    if sys.platform.startswith("win"):
        ecrans = _lister_ecrans_windows()
        if ecrans:
            return ecrans
    return _lister_ecran_tkinter()


def _lister_ecrans_windows():
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        ecrans = []

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.POINTER(wintypes.RECT), ctypes.c_double)

        def _callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            r = lprcMonitor.contents
            ecrans.append(Ecran(r.left, r.top, r.right - r.left,
                                 r.bottom - r.top))
            return 1

        user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_callback), 0)

        if not ecrans:
            return []

        # l'écran principal est celui qui contient (0,0)
        for e in ecrans:
            if e.x <= 0 <= e.x + e.largeur and e.y <= 0 <= e.y + e.hauteur:
                e.principal = True
                break
        if not any(e.principal for e in ecrans):
            ecrans[0].principal = True

        ecrans.sort(key=lambda e: (not e.principal, e.x))
        return ecrans
    except Exception:
        return []


def _lister_ecran_tkinter():
    try:
        import tkinter as tk
        racine = tk.Tk()
        racine.withdraw()
        largeur = racine.winfo_screenwidth()
        hauteur = racine.winfo_screenheight()
        racine.destroy()
        return [Ecran(0, 0, largeur, hauteur, principal=True)]
    except Exception:
        return [Ecran(0, 0, 1280, 720, principal=True)]

