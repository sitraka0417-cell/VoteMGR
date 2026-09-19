# -*- coding: utf-8 -*-
"""
projection.py — Écran 2 : fenêtre de projection destinée à être affichée
en plein écran sur le vidéoprojecteur / 2e moniteur, face à l'assemblée.

Trois modes d'affichage :
  - idle       : logo + "VoteMGR by Sitraka Nambinintsoa" (aucun vote en cours)
  - vote       : grille des candidats du poste en cours, gros numéros/noms/scores,
                 pagination automatique si trop de candidats, clignotement au vote
  - resultats  : liste des élu(e)s (poste courant ou bureau complet)

Cette fenêtre ne contient JAMAIS les boutons +/- : elle est en lecture
seule, pilotée entièrement par l'écran du secrétaire (app/secretary.py).
"""

import os
import math
import tkinter as tk

COULEUR_FOND = "#0b1220"
COULEUR_CARTE = "#152238"
COULEUR_CARTE_FLASH = "#f2b90c"
COULEUR_TEXTE = "#f5f7fa"
COULEUR_TEXTE_FLASH = "#0b1220"
COULEUR_ACCENT = "#3a7bd5"
COULEUR_ELU = "#1f9d55"

DUREE_FLASH_MS = 2600
DUREE_PAGE_MS = 10000


class FenetreProjection(tk.Toplevel):
    def __init__(self, master, logo_path=None):
        super().__init__(master)
        self.title("VoteMGR — Écran de projection")
        self.configure(bg=COULEUR_FOND)
        self.logo_path = logo_path
        self._logo_img = None
        self._plein_ecran = False

        self.conteneur = tk.Frame(self, bg=COULEUR_FOND)
        self.conteneur.pack(fill="both", expand=True)

        self._pages = []          # liste de listes de Candidat (pagination)
        self._index_page = 0
        self._cartes = {}         # cand_id -> (frame, label_score)
        self._job_rotation = None
        self._job_flash = {}
        self._poste_courant = None

        self.bind("<Escape>", lambda e: self.quitter_plein_ecran())
        self.protocol("WM_DELETE_WINDOW", self.withdraw)  # ne pas fermer par erreur

        self.afficher_idle()

    # ---------------- placement écran ----------------
    def placer_sur_ecran(self, ecran):
        self.geometry(ecran.geometrie())

    def basculer_plein_ecran(self):
        self._plein_ecran = not self._plein_ecran
        try:
            self.attributes("-fullscreen", self._plein_ecran)
        except tk.TclError:
            pass

    def quitter_plein_ecran(self):
        self._plein_ecran = False
        try:
            self.attributes("-fullscreen", False)
        except tk.TclError:
            pass

    # ---------------- utilitaire ----------------
    def _vider(self):
        if self._job_rotation:
            self.after_cancel(self._job_rotation)
            self._job_rotation = None
        for job in self._job_flash.values():
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._job_flash = {}
        for w in self.conteneur.winfo_children():
            w.destroy()
        self._cartes = {}

    # ---------------- mode IDLE ----------------
    def afficher_idle(self):
        self._poste_courant = None
        self._vider()
        centre = tk.Frame(self.conteneur, bg=COULEUR_FOND)
        centre.place(relx=0.5, rely=0.5, anchor="center")

        if self.logo_path and os.path.exists(self.logo_path):
            try:
                img = tk.PhotoImage(file=self.logo_path)
                # limite grossière de taille (PhotoImage ne redimensionne pas
                # nativement) : sous-échantillonnage si l'image est énorme
                if img.width() > 700:
                    facteur = max(1, img.width() // 700)
                    img = img.subsample(facteur, facteur)
                self._logo_img = img
                tk.Label(centre, image=img, bg=COULEUR_FOND).pack(pady=(0, 30))
            except Exception:
                pass

        tk.Label(centre, text="VoteMGR", font=("Segoe UI", 64, "bold"),
                 fg=COULEUR_TEXTE, bg=COULEUR_FOND).pack()
        tk.Label(centre, text="by Sitraka Nambinintsoa",
                 font=("Segoe UI", 22), fg="#8fa3c4", bg=COULEUR_FOND).pack(pady=(6, 0))

    # ---------------- mode VOTE ----------------
    def afficher_vote(self, poste):
        """(Re)construit l'affichage pour ce poste. À appeler quand le vote
        est lancé, ou que la liste de candidats change."""
        self._poste_courant = poste
        self._vider()

        tk.Label(self.conteneur, text=poste.nom, font=("Segoe UI", 30, "bold"),
                 fg=COULEUR_ACCENT, bg=COULEUR_FOND).pack(pady=(18, 6))

        candidats = list(poste.candidats)
        n = max(1, len(candidats))
        colonnes = 2 if n <= 8 else (3 if n <= 18 else 4)
        lignes_par_page = 5
        capacite = colonnes * lignes_par_page

        self._pages = [candidats[i:i + capacite]
                        for i in range(0, len(candidats), capacite)] or [[]]
        self._colonnes = colonnes
        self._index_page = 0
        self._afficher_page_courante()
        self._programmer_rotation()

    def _tailles_police(self, colonnes):
        if colonnes == 2:
            return ("Segoe UI", 50, "bold"), ("Segoe UI", 88, "bold")
        if colonnes == 3:
            return ("Segoe UI", 36, "bold"), ("Segoe UI", 66, "bold")
        return ("Segoe UI", 26, "bold"), ("Segoe UI", 48, "bold")

    def _afficher_page_courante(self):
        for w in list(self.conteneur.winfo_children())[1:]:
            w.destroy()
        self._cartes = {}

        grille = tk.Frame(self.conteneur, bg=COULEUR_FOND)
        grille.pack(fill="both", expand=True, padx=24, pady=10)

        police_nom, police_score = self._tailles_police(self._colonnes)
        page = self._pages[self._index_page] if self._pages else []

        for c in range(self._colonnes):
            grille.columnconfigure(c, weight=1, uniform="col")

        for i, cand in enumerate(page):
            ligne, col = divmod(i, self._colonnes)
            grille.rowconfigure(ligne, weight=1)
            carte = tk.Frame(grille, bg=COULEUR_CARTE, bd=0,
                              highlightthickness=2,
                              highlightbackground="#233047")
            carte.grid(row=ligne, column=col, sticky="nsew", padx=10, pady=8)

            entete = tk.Frame(carte, bg=COULEUR_CARTE)
            entete.pack(fill="x", padx=14, pady=(10, 0))
            lbl_num = tk.Label(entete, text="N° %d" % cand.numero,
                                font=("Segoe UI", 16, "bold"),
                                fg="#8fa3c4", bg=COULEUR_CARTE)
            lbl_num.pack(side="left")

            lbl_nom = tk.Label(carte, text=cand.nom, font=police_nom,
                                fg=COULEUR_TEXTE, bg=COULEUR_CARTE,
                                wraplength=1, justify="center")
            lbl_nom.pack(fill="x", padx=14, pady=(2, 0))
            # wraplength dynamique approximatif
            carte.update_idletasks()

            lbl_score = tk.Label(carte, text=str(cand.votes), font=police_score,
                                  fg=COULEUR_ACCENT, bg=COULEUR_CARTE)
            lbl_score.pack(pady=(2, 10))

            self._cartes[cand.id] = (carte, lbl_nom, lbl_score, entete, lbl_num)

        if len(self._pages) > 1:
            tk.Label(self.conteneur,
                     text="Page %d / %d" % (self._index_page + 1, len(self._pages)),
                     font=("Segoe UI", 14), fg="#5b6b85", bg=COULEUR_FOND).pack(pady=(0, 6))

    def _programmer_rotation(self):
        if self._job_rotation:
            self.after_cancel(self._job_rotation)
            self._job_rotation = None
        if len(self._pages) > 1:
            self._job_rotation = self.after(DUREE_PAGE_MS, self._page_suivante)

    def _page_suivante(self):
        self._index_page = (self._index_page + 1) % len(self._pages)
        self._afficher_page_courante()
        self._programmer_rotation()

    def rafraichir_scores(self, poste=None):
        """Met à jour les scores affichés sans reconstruire les cartes
        (appelé après chaque +/-)."""
        if self._poste_courant is None:
            return
        for cand in self._poste_courant.candidats:
            if cand.id in self._cartes:
                self._cartes[cand.id][2].config(text=str(cand.votes))

    def flash_candidat(self, cand_id):
        """Fait clignoter la carte du candidat qui vient de recevoir un
        point, pendant DUREE_FLASH_MS."""
        if cand_id not in self._cartes:
            return
        carte, lbl_nom, lbl_score, entete, lbl_num = self._cartes[cand_id]
        for w in (carte, entete):
            w.config(bg=COULEUR_CARTE_FLASH)
        for w in (lbl_nom, lbl_score, lbl_num):
            w.config(bg=COULEUR_CARTE_FLASH, fg=COULEUR_TEXTE_FLASH)

        if cand_id in self._job_flash:
            try:
                self.after_cancel(self._job_flash[cand_id])
            except Exception:
                pass

        def revenir():
            if cand_id in self._cartes and self._cartes[cand_id][0] == carte:
                for w in (carte, entete):
                    w.config(bg=COULEUR_CARTE)
                lbl_nom.config(bg=COULEUR_CARTE, fg=COULEUR_TEXTE)
                lbl_score.config(bg=COULEUR_CARTE, fg=COULEUR_ACCENT)
                lbl_num.config(bg=COULEUR_CARTE, fg="#8fa3c4")
            self._job_flash.pop(cand_id, None)

        self._job_flash[cand_id] = self.after(DUREE_FLASH_MS, revenir)

    # ---------------- mode RESULTATS ----------------
    def afficher_resultats(self, postes):
        """Affiche la liste des élu(e)s pour un ou plusieurs postes
        (ex: résultat d'un seul poste, ou bureau exécutif complet)."""
        self._poste_courant = None
        self._vider()

        if isinstance(postes, list):
            liste = postes
            titre = "Résultats — Bureau élu" if len(liste) > 1 else (
                "Résultats — " + liste[0].nom if liste else "Résultats")
        else:
            liste = [postes]
            titre = "Résultats — " + postes.nom

        tk.Label(self.conteneur, text=titre, font=("Segoe UI", 34, "bold"),
                 fg=COULEUR_ACCENT, bg=COULEUR_FOND).pack(pady=(24, 10))

        zone = tk.Frame(self.conteneur, bg=COULEUR_FOND)
        zone.pack(fill="both", expand=True, padx=40, pady=10)

        for poste in liste:
            bloc = tk.Frame(zone, bg=COULEUR_FOND)
            bloc.pack(fill="x", pady=10)
            if len(liste) > 1:
                tk.Label(bloc, text=poste.nom, font=("Segoe UI", 24, "bold"),
                         fg=COULEUR_TEXTE, bg=COULEUR_FOND, anchor="w").pack(fill="x")
            noms = [poste.candidat(cid).nom for cid in poste.elus
                    if poste.candidat(cid)]
            if not noms:
                tk.Label(bloc, text="— pas encore de résultat —",
                         font=("Segoe UI", 20), fg="#8fa3c4",
                         bg=COULEUR_FOND, anchor="w").pack(fill="x")
            for nom in noms:
                tk.Label(bloc, text="★  " + nom,
                         font=("Segoe UI", 40, "bold"),
                         fg=COULEUR_ELU, bg=COULEUR_FOND, anchor="w").pack(fill="x")
