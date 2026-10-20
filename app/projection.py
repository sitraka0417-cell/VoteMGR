# -*- coding: utf-8 -*-
"""
projection.py — Écran 2 : fenêtre de projection destinée à être affichée
en plein écran sur le vidéoprojecteur / 2e moniteur, face à l'assemblée.

Trois modes d'affichage :
  - idle       : logo (aucun vote en cours), fond TOUJOURS blanc
  - vote       : grille de candidats sous forme de barres (comme la
                 maquette fournie), colonnes/lignes ADAPTATIVES (de 1 à
                 ~200+ candidats), mise en avant en vert des candidats
                 actuellement en tête (selon le nombre de sièges), une
                 3e couleur pour une égalité à la limite, clignotement
                 quasi instantané à chaque vote.
  - resultats  : liste des élu(e)s (un poste, une section/sous-section
                 complète, ou le bureau exécutif complet), toujours
                 fusionnée (jamais de tour de départage affiché à part).

Cette fenêtre ne contient JAMAIS les boutons +/- : elle est en lecture
seule, pilotée entièrement par l'écran du secrétaire (app/secretary.py).
"""

import os
import math
import tkinter as tk

COULEUR_FOND = "#0a1120"
COULEUR_FOND_IDLE = "#ffffff"       # l'écran idle (logo) est TOUJOURS blanc
COULEUR_BARRE = "#7a1f2b"           # bordeaux/maroon, comme la maquette
COULEUR_BARRE_BORD = "#9c2c3a"
COULEUR_EN_TETE = "#1f9d55"         # vert : candidat actuellement en tête
COULEUR_EN_TETE_BORD = "#27c96c"
COULEUR_EGALITE = "#e08a1e"         # orange : égalité à la limite du seuil
COULEUR_EGALITE_BORD = "#f2a93c"
COULEUR_FLASH = "#f2c40c"
COULEUR_TEXTE = "#f5f7fa"
COULEUR_TEXTE_FLASH = "#241a00"
COULEUR_ACCENT = "#ffd84a"          # titre jaune, comme la maquette
COULEUR_SOUS_TITRE = "#bcd4f5"
COULEUR_ELU = "#28c76f"

DUREE_FLASH_MS = 320          # quasi instantané : une fraction de seconde
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

        self._pages = []          # liste de listes de Candidat (pagination, dernier recours)
        self._index_page = 0
        self._cartes = {}         # cand_id -> dict(canvas, etat, flash_actif)
        self._job_rotation = None
        self._job_flash = {}
        self._poste_courant = None
        self._colonnes = 2
        self._lignes = 1

        self.bind("<Escape>", lambda e: self.quitter_plein_ecran())
        self.protocol("WM_DELETE_WINDOW", self.withdraw)  # ne pas fermer par erreur

        self.afficher_idle()

    # ---------------- placement écran ----------------
    def placer_sur_ecran(self, ecran):
        self.geometry(ecran.geometrie())
        self._largeur_cible = ecran.largeur
        self._hauteur_cible = ecran.hauteur

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

    def forcer_plein_ecran(self, etat=True):
        """Comme basculer_plein_ecran, mais fixe l'état voulu au lieu de
        l'inverser — utile quand on repositionne la fenêtre sans savoir
        dans quel état elle était déjà."""
        self._plein_ecran = etat
        try:
            self.attributes("-fullscreen", etat)
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

    def _dimensions_disponibles(self):
        """Renvoie (largeur, hauteur) utilisables, en se basant sur la
        taille réelle de la fenêtre (déjà placée en plein écran sur le bon
        moniteur)."""
        self.update_idletasks()
        l = self.winfo_width() or getattr(self, "_largeur_cible", 1280)
        h = self.winfo_height() or getattr(self, "_hauteur_cible", 720)
        if l < 200 or h < 200:
            l = getattr(self, "_largeur_cible", 1280)
            h = getattr(self, "_hauteur_cible", 720)
        return l, h

    # ---------------- mode IDLE ----------------
    def afficher_idle(self):
        """Hors vote : uniquement le logo (assets/logo.png), plein écran
        avec juste une petite marge, fond TOUJOURS BLANC (quel que soit le
        thème choisi, pour un rendu propre du logo). S'il n'y a pas de
        logo disponible, on retombe sur un texte simple pour que l'écran
        ne soit jamais vide."""
        self._poste_courant = None
        self._vider()
        self.conteneur.configure(bg=COULEUR_FOND_IDLE)
        largeur, hauteur = self._dimensions_disponibles()

        centre = tk.Frame(self.conteneur, bg=COULEUR_FOND_IDLE)
        centre.place(relx=0.5, rely=0.5, anchor="center")

        logo_affiche = False
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                img = tk.PhotoImage(file=self.logo_path)
                # Plein écran "à une petite marge près" : le logo peut
                # occuper jusqu'à ~92% de l'écran.
                marge_pct = 0.92
                max_l = max(200, int(largeur * marge_pct))
                max_h = max(200, int(hauteur * marge_pct))
                if img.width() > max_l or img.height() > max_h:
                    facteur = max(1, math.ceil(max(img.width() / max_l,
                                                     img.height() / max_h)))
                    img = img.subsample(facteur, facteur)
                elif img.width() < max_l * 0.5 and img.height() < max_h * 0.5:
                    # logo trop petit : on l'agrandit pour remplir l'écran
                    zoom = max(1, min(int(max_l / max(1, img.width())),
                                       int(max_h / max(1, img.height()))))
                    if zoom > 1:
                        img = img.zoom(zoom, zoom)
                self._logo_img = img
                tk.Label(centre, image=img, bg=COULEUR_FOND_IDLE).pack()
                logo_affiche = True
            except Exception:
                logo_affiche = False

        if not logo_affiche:
            tk.Label(centre, text="VoteMGR", font=("Segoe UI", 64, "bold"),
                     fg="#1a1a1a", bg=COULEUR_FOND_IDLE).pack()
            tk.Label(centre, text="by Sitraka Nambinintsoa",
                     font=("Segoe UI", 22), fg="#555555", bg=COULEUR_FOND_IDLE).pack(pady=(6, 0))

    # ---------------- mode VOTE : disposition adaptative (barres) ----------------
    def _calculer_disposition(self, n, largeur, hauteur):
        """Choisit le nombre de colonnes/lignes de BARRES horizontales qui
        remplit le mieux l'écran pour n candidats. Objectif : jusqu'à
        200+ candidats sur un seul écran, avec une police qui s'adapte
        plutôt que de paginer (pagination en tout dernier recours)."""
        n = max(1, n)
        zone_h = hauteur - 170   # réserve pour titre + sous-titre + marges
        meilleur = None
        max_colonnes = min(n, 8 if n <= 64 else 10)
        for colonnes in range(1, max_colonnes + 1):
            lignes = math.ceil(n / colonnes)
            cell_w = largeur / colonnes
            cell_h = zone_h / lignes
            # cellule "barre" : on vise un ratio large (~3.4 : 1), pas une
            # carte carrée
            ratio = cell_w / max(cell_h, 1)
            penalite = abs(ratio - 3.4) * 0.08
            score = min(cell_w / 3.4, cell_h) * (1 - penalite)
            if meilleur is None or score > meilleur[0]:
                meilleur = (score, colonnes, lignes, cell_w, cell_h)
        _, colonnes, lignes, cell_w, cell_h = meilleur
        return colonnes, lignes, cell_w, cell_h

    def afficher_vote(self, poste):
        """(Re)construit l'affichage pour ce poste. À appeler quand le vote
        est lancé, ou que la liste de candidats change."""
        self._poste_courant = poste
        self._vider()
        self.conteneur.configure(bg=COULEUR_FOND)

        titre, sous_titre = self._titre_poste(poste)
        tk.Label(self.conteneur, text=titre, font=("Segoe UI", 28, "bold"),
                 fg=COULEUR_ACCENT, bg=COULEUR_FOND).pack(pady=(14, 0))
        if sous_titre:
            tk.Label(self.conteneur, text=sous_titre, font=("Segoe UI", 18),
                     fg=COULEUR_SOUS_TITRE, bg=COULEUR_FOND).pack(pady=(0, 4))
        self._n_header_widgets = len(self.conteneur.winfo_children())

        candidats = list(poste.candidats)
        n = max(1, len(candidats))
        largeur, hauteur = self._dimensions_disponibles()
        colonnes, lignes, cell_w, cell_h = self._calculer_disposition(n, largeur, hauteur)

        capacite = colonnes * lignes
        if cell_h < 36 and n > capacite:
            lignes_page = max(1, int((hauteur - 170) // 36))
            capacite = colonnes * lignes_page

        self._pages = [candidats[i:i + capacite]
                        for i in range(0, len(candidats), capacite)] or [[]]
        self._colonnes = colonnes
        self._lignes = lignes
        self._cell_w, self._cell_h = cell_w, cell_h
        self._index_page = 0
        self._afficher_page_courante()
        self._programmer_rotation()

    def _titre_poste(self, poste):
        """(titre, sous_titre) pour l'affichage. Si le secrétaire a fourni
        un helper externe (self.titre_fn, branché par secretary.py avec la
        hiérarchie section/sous-section du projet), on l'utilise ;
        sinon on retombe simplement sur le nom du poste."""
        fn = getattr(self, "titre_fn", None)
        if fn:
            try:
                return fn(poste)
            except Exception:
                pass
        return poste.nom, None

    def _tailles_police(self, cell_w, cell_h):
        """Police dérivée de la taille réelle de la barre."""
        base = min(cell_w / 16.0, cell_h / 2.6)
        taille_nom = max(11, min(34, int(base)))
        taille_score = max(11, min(26, int(base * 0.85)))
        return (("Segoe UI", taille_nom, "bold"),
                ("Segoe UI", taille_score, "bold"))

    def _candidats_en_tete(self):
        """Renvoie (ids_en_tete_vert, ids_egalite_orange) selon le nombre
        de sièges à pourvoir du poste courant, mis à jour en direct à
        chaque vote. Corrige le bug où tous les N premiers (même à 0 voix,
        même à égalité totale) étaient mis en avant dès qu'UN SEUL
        candidat marquait un point : seuls les candidats ayant RÉELLEMENT
        des voix, et réellement dans les n meilleurs (ou à égalité stricte
        sur la dernière place qualificative), sont mis en avant."""
        if self._poste_courant is None:
            return set(), set()
        n = max(1, getattr(self._poste_courant, "nombre_sieges", 1))
        classement = self._poste_courant.classement()
        avec_voix = [c for c in classement if c.votes > 0]
        if not avec_voix:
            return set(), set()
        if len(avec_voix) <= n:
            # tout le monde qui a au moins une voix est en tête (pas assez
            # de candidats avec voix pour qu'il y ait une vraie limite)
            return {c.id for c in avec_voix}, set()
        seuil = avec_voix[n - 1].votes
        verts = {c.id for c in avec_voix[:n] if c.votes > seuil}
        a_la_limite = [c for c in avec_voix if c.votes == seuil]
        if len(a_la_limite) > (n - len(verts)):
            # égalité réelle à la limite : couleur dédiée, pas "vert"
            return verts, {c.id for c in a_la_limite}
        verts |= {c.id for c in a_la_limite}
        return verts, set()

    def _etat_candidat(self, cand_id, verts=None, egalites=None):
        if verts is None or egalites is None:
            verts, egalites = self._candidats_en_tete()
        if cand_id in egalites:
            return "egalite"
        if cand_id in verts:
            return "tete"
        return "normal"

    @staticmethod
    def _rect_arrondi(canvas, x0, y0, x1, y1, r, **kw):
        points = [
            x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
        ]
        return canvas.create_polygon(points, smooth=True, **kw)

    def _dessiner_barre(self, canvas, w, h, cand, etat, police_nom, police_score):
        """Dessine une barre horizontale (pill) : numéro + nom à gauche,
        badge circulaire avec le score à droite — comme la maquette."""
        canvas.delete("all")
        marge_h = max(3, int(h * 0.08))
        marge_l = max(4, int(w * 0.012))
        x0, y0 = marge_l, marge_h
        x1, y1 = w - marge_l, h - marge_h
        rayon = max(6, int((y1 - y0) * 0.5))

        if etat == "tete":
            fond, bord = COULEUR_EN_TETE, COULEUR_EN_TETE_BORD
        elif etat == "egalite":
            fond, bord = COULEUR_EGALITE, COULEUR_EGALITE_BORD
        else:
            fond, bord = COULEUR_BARRE, COULEUR_BARRE_BORD

        self._rect_arrondi(canvas, x0, y0, x1, y1, rayon, fill=fond, outline=bord, width=2)

        diam = (y1 - y0) * 0.86
        cx = x1 - rayon - 2
        cy = (y0 + y1) / 2
        canvas.create_oval(cx - diam / 2, cy - diam / 2, cx + diam / 2, cy + diam / 2,
                            fill="#ffffff", outline=bord, width=2)
        canvas.create_text(cx, cy, text=str(cand.votes), font=police_score, fill="#111111")

        texte = "%d. %s" % (cand.numero, cand.nom)
        zone_texte_x1 = cx - diam / 2 - 10
        canvas.create_text(x0 + 16, cy, anchor="w", text=texte, font=police_nom,
                            fill=COULEUR_TEXTE, width=max(40, int(zone_texte_x1 - (x0 + 16))))
        if etat == "tete":
            canvas.create_text(x1 - diam - 14, y0 + (y1 - y0) * 0.12, anchor="e",
                                text="★", font=("Segoe UI", max(10, int(police_score[1] * 0.8))),
                                fill="#ffffff")

    def _afficher_page_courante(self):
        n_entete = getattr(self, "_n_header_widgets", 1)
        for w in list(self.conteneur.winfo_children())[n_entete:]:
            w.destroy()
        self._cartes = {}

        grille = tk.Frame(self.conteneur, bg=COULEUR_FOND)
        grille.pack(fill="both", expand=True, padx=16, pady=4)

        for c in range(self._colonnes):
            grille.columnconfigure(c, weight=1, uniform="col")
        page = self._pages[self._index_page] if self._pages else []
        lignes_page = math.ceil(len(page) / self._colonnes) if page else 1
        for r in range(max(1, lignes_page)):
            grille.rowconfigure(r, weight=1)

        police_nom, police_score = self._tailles_police(self._cell_w, self._cell_h)
        verts, egalites = self._candidats_en_tete()

        for i, cand in enumerate(page):
            ligne, col = divmod(i, self._colonnes)
            canvas = tk.Canvas(grille, bg=COULEUR_FOND, highlightthickness=0, bd=0)
            canvas.grid(row=ligne, column=col, sticky="nsew", padx=6, pady=4)

            def redessiner(event, cv=canvas, c=cand, pn=police_nom, ps=police_score):
                etat = self._etat_candidat(c.id)
                self._dessiner_barre(cv, event.width, event.height, c, etat, pn, ps)
                if c.id in self._cartes:
                    self._cartes[c.id]["etat"] = etat

            canvas.bind("<Configure>", redessiner)
            self._cartes[cand.id] = {"canvas": canvas,
                                      "etat": self._etat_candidat(cand.id, verts, egalites),
                                      "flash_actif": False}

        # force un calcul de géométrie immédiat pour que les barres soient
        # dessinées tout de suite (pas d'attente d'un évènement <Configure>
        # différé — important pour que le premier affichage et les flashs
        # soient instantanés).
        grille.update_idletasks()
        for cand_id, info in self._cartes.items():
            cv = info["canvas"]
            w, h = cv.winfo_width(), cv.winfo_height()
            if w > 1 and h > 1:
                cand = self._poste_courant.candidat(cand_id) if self._poste_courant else None
                if cand:
                    self._dessiner_barre(cv, w, h, cand, info["etat"], police_nom, police_score)

        if len(self._pages) > 1:
            tk.Label(self.conteneur,
                     text="Page %d / %d" % (self._index_page + 1, len(self._pages)),
                     font=("Segoe UI", 13), fg="#5b6b85", bg=COULEUR_FOND).pack(pady=(0, 4))

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

    def _redessiner_carte(self, cand_id):
        info = self._cartes.get(cand_id)
        if info is None or self._poste_courant is None:
            return
        canvas = info["canvas"]
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        cand = self._poste_courant.candidat(cand_id)
        if cand is None:
            return
        police_nom, police_score = self._tailles_police(self._cell_w, self._cell_h)
        etat = self._etat_candidat(cand_id)
        self._dessiner_barre(canvas, w, h, cand, etat, police_nom, police_score)
        info["etat"] = etat

    def rafraichir_scores(self, poste=None):
        """Met à jour les scores affichés (appelé après chaque +/-), et
        recalcule en direct quels candidats sont actuellement en tête /
        à égalité (mis en avant visuellement selon le nombre de sièges)."""
        if self._poste_courant is None:
            return
        verts, egalites = self._candidats_en_tete()
        for cand in self._poste_courant.candidats:
            info = self._cartes.get(cand.id)
            if info is None:
                continue
            nouvel_etat = self._etat_candidat(cand.id, verts, egalites)
            if nouvel_etat != info.get("etat") or info.get("flash_actif"):
                continue  # un flash est en cours : ne pas l'écraser ici
            self._redessiner_carte(cand.id)
        # second passage : les cartes dont l'état a changé (même en flash,
        # elles seront redessinées correctement à la fin du flash puisque
        # info["etat"] est déjà à jour pour la prochaine fois)
        for cand in self._poste_courant.candidats:
            info = self._cartes.get(cand.id)
            if info is None:
                continue
            info["etat"] = self._etat_candidat(cand.id, verts, egalites)

    def flash_candidat(self, cand_id):
        """Fait clignoter la barre du candidat qui vient de recevoir un
        point : apparition INSTANTANÉE (dès l'appel, sans délai), ne dure
        qu'une fraction de seconde, puis revient directement à l'état
        normal (vert/orange/normal selon le classement à jour)."""
        info = self._cartes.get(cand_id)
        if info is None or self._poste_courant is None:
            return
        canvas = info["canvas"]
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        cand = self._poste_courant.candidat(cand_id)
        if cand is None:
            return
        info["flash_actif"] = True
        canvas.delete("all")
        marge_h = max(3, int(h * 0.08))
        marge_l = max(4, int(w * 0.012))
        rayon = max(6, int((h - 2 * marge_h) * 0.5))
        self._rect_arrondi(canvas, marge_l, marge_h, w - marge_l, h - marge_h, rayon,
                            fill=COULEUR_FLASH, outline=COULEUR_FLASH, width=2)
        police_nom, police_score = self._tailles_police(self._cell_w, self._cell_h)
        canvas.create_text(marge_l + 16, h / 2, anchor="w",
                            text="%d. %s" % (cand.numero, cand.nom),
                            font=police_nom, fill=COULEUR_TEXTE_FLASH,
                            width=max(40, int(w * 0.6)))
        canvas.create_text(w - marge_l - 30, h / 2, text=str(cand.votes),
                            font=police_score, fill=COULEUR_TEXTE_FLASH)

        if cand_id in self._job_flash:
            try:
                self.after_cancel(self._job_flash[cand_id])
            except Exception:
                pass

        def revenir():
            info["flash_actif"] = False
            self._job_flash.pop(cand_id, None)
            self._redessiner_carte(cand_id)

        self._job_flash[cand_id] = self.after(DUREE_FLASH_MS, revenir)

    # ---------------- mode RESULTATS ----------------
    def afficher_resultats(self, postes, titre=None, sous_titre=None):
        """Affiche la liste des élu(e)s/désigné(e)s pour un ou plusieurs
        postes (résultat d'une section/sous-section entière, ou bureau
        exécutif complet). Les résultats affichés sont toujours les
        résultats FINAUX fusionnés (jamais un tour de départage affiché à
        part) : c'est à l'appelant (secretary.py) de passer une liste déjà
        filtrée avec Projet.postes_resultat()."""
        self._poste_courant = None
        self._vider()
        self.conteneur.configure(bg=COULEUR_FOND)

        if isinstance(postes, list):
            liste = postes
        else:
            liste = [postes]

        if titre is None:
            titre = "Résultats — Bureau élu" if len(liste) > 1 else (
                "Résultats — " + liste[0].nom if liste else "Résultats")

        tk.Label(self.conteneur, text=titre, font=("Segoe UI", 32, "bold"),
                 fg=COULEUR_ACCENT, bg=COULEUR_FOND).pack(pady=(22, 2))
        if sous_titre:
            tk.Label(self.conteneur, text=sous_titre, font=("Segoe UI", 19),
                     fg=COULEUR_SOUS_TITRE, bg=COULEUR_FOND).pack(pady=(0, 8))

        zone_ext = tk.Frame(self.conteneur, bg=COULEUR_FOND)
        zone_ext.pack(fill="both", expand=True, padx=10, pady=6)
        canvas_zone = tk.Canvas(zone_ext, bg=COULEUR_FOND, highlightthickness=0)
        scrollbar = tk.Scrollbar(zone_ext, orient="vertical", command=canvas_zone.yview)
        zone = tk.Frame(canvas_zone, bg=COULEUR_FOND)
        zone.bind("<Configure>", lambda e: canvas_zone.configure(scrollregion=canvas_zone.bbox("all")))
        canvas_zone.create_window((0, 0), window=zone, anchor="n")
        canvas_zone.configure(yscrollcommand=scrollbar.set)
        canvas_zone.pack(side="left", fill="both", expand=True, padx=30)
        scrollbar.pack(side="right", fill="y")

        for poste in liste:
            bloc = tk.Frame(zone, bg=COULEUR_FOND)
            bloc.pack(fill="x", pady=10)
            if len(liste) > 1:
                tk.Label(bloc, text=poste.nom, font=("Segoe UI", 22, "bold"),
                         fg=COULEUR_TEXTE, bg=COULEUR_FOND, anchor="w").pack(fill="x")

            if poste.mode_roles and poste.roles:
                groupes = poste.resultat_roles_groupe()
                if not groupes:
                    tk.Label(bloc, text="— pas encore de résultat —",
                             font=("Segoe UI", 18), fg="#8fa3c4",
                             bg=COULEUR_FOND, anchor="w").pack(fill="x")
                else:
                    for g in groupes:
                        tk.Label(bloc, text=g["nom_role"], font=("Segoe UI", 18, "bold"),
                                 fg=COULEUR_SOUS_TITRE, bg=COULEUR_FOND, anchor="w").pack(
                            fill="x", pady=(6, 0))
                        for c in g["candidats"]:
                            tk.Label(bloc, text="★  " + c.nom,
                                     font=("Segoe UI", 28, "bold"),
                                     fg=COULEUR_ELU, bg=COULEUR_FOND, anchor="w").pack(fill="x")
                continue

            noms = [poste.candidat(cid).nom for cid in poste.elus
                    if poste.candidat(cid)]
            if not noms:
                tk.Label(bloc, text="— pas encore de résultat —",
                         font=("Segoe UI", 18), fg="#8fa3c4",
                         bg=COULEUR_FOND, anchor="w").pack(fill="x")
            for nom in noms:
                tk.Label(bloc, text="★  " + nom,
                         font=("Segoe UI", 34, "bold"),
                         fg=COULEUR_ELU, bg=COULEUR_FOND, anchor="w").pack(fill="x")
