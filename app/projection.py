# -*- coding: utf-8 -*-
"""
projection.py — Écran 2 : fenêtre de projection destinée à être affichée
en plein écran sur le vidéoprojecteur / 2e moniteur, face à l'assemblée.

Trois modes d'affichage :
  - idle       : logo (aucun vote en cours)
  - vote       : grille des candidats du poste en cours, taille de police
                 ADAPTATIVE (dépend du nombre de candidats, pour que tout
                 le monde tienne sur un seul écran jusqu'à ~30 candidats),
                 avec mise en avant visuelle des candidats actuellement
                 en tête (selon le nombre de sièges à pourvoir), et
                 clignotement à chaque vote. Pagination automatique en
                 dernier recours seulement si vraiment trop de candidats.
  - resultats  : liste des élu(e)s (poste courant ou bureau complet)

Cette fenêtre ne contient JAMAIS les boutons +/- : elle est en lecture
seule, pilotée entièrement par l'écran du secrétaire (app/secretary.py).
"""

import os
import math
import tkinter as tk

COULEUR_FOND = "#0a1120"
COULEUR_FOND_HAUT = "#111c33"      # pour le dégradé de fond
COULEUR_CARTE_HAUT = "#1c2d4a"     # dégradé carte (haut, plus clair)
COULEUR_CARTE_BAS = "#111b2e"      # dégradé carte (bas, plus sombre)
COULEUR_CARTE_BORD = "#2c3f61"
COULEUR_OMBRE = "#040810"
COULEUR_CARTE_FLASH = "#f2b90c"
COULEUR_TEXTE = "#f5f7fa"
COULEUR_TEXTE_FLASH = "#1a1400"
COULEUR_ACCENT = "#4e8fe8"
COULEUR_ELU = "#28c76f"
COULEUR_LEADER_HAUT = "#2a5a3a"    # dégradé carte "en tête" (haut)
COULEUR_LEADER_BAS = "#163826"    # dégradé carte "en tête" (bas)
COULEUR_LEADER_BORD = "#28c76f"

DUREE_FLASH_MS = 4200       # clignotement plus long
DELAI_RETOUR_FLASH_MS = 550  # petit délai avant de revenir à l'état normal
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
        self._cartes = {}         # cand_id -> dict(canvas, items, en_tete, flash_actif)
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
        """Renvoie (largeur, hauteur) utilisables pour la grille de
        candidats, en se basant sur la taille réelle de la fenêtre (déjà
        placée en plein écran sur le bon moniteur)."""
        self.update_idletasks()
        l = self.winfo_width() or getattr(self, "_largeur_cible", 1280)
        h = self.winfo_height() or getattr(self, "_hauteur_cible", 720)
        if l < 200 or h < 200:
            l = getattr(self, "_largeur_cible", 1280)
            h = getattr(self, "_hauteur_cible", 720)
        return l, h

    # ---------------- mode IDLE ----------------
    def afficher_idle(self):
        """Hors vote : uniquement le logo (assets/logo.png), bien centré
        et redimensionné pour ne JAMAIS dépasser l'écran (ni être coupé).
        S'il n'y a pas de logo disponible, on retombe sur un texte simple
        pour que l'écran ne soit jamais vide."""
        self._poste_courant = None
        self._vider()
        largeur, hauteur = self._dimensions_disponibles()

        centre = tk.Frame(self.conteneur, bg=COULEUR_FOND)
        centre.place(relx=0.5, rely=0.5, anchor="center")

        logo_affiche = False
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                img = tk.PhotoImage(file=self.logo_path)
                # Le logo ne doit jamais dépasser ~70% de l'écran (ni en
                # largeur, ni en hauteur), sinon il "mange" l'écran et
                # peut sembler coupé selon le moniteur.
                max_l = max(200, int(largeur * 0.70))
                max_h = max(200, int(hauteur * 0.70))
                if img.width() > max_l or img.height() > max_h:
                    facteur = max(1, math.ceil(max(img.width() / max_l,
                                                     img.height() / max_h)))
                    img = img.subsample(facteur, facteur)
                self._logo_img = img
                tk.Label(centre, image=img, bg=COULEUR_FOND).pack()
                logo_affiche = True
            except Exception:
                logo_affiche = False

        if not logo_affiche:
            tk.Label(centre, text="VoteMGR", font=("Segoe UI", 64, "bold"),
                     fg=COULEUR_TEXTE, bg=COULEUR_FOND).pack()
            tk.Label(centre, text="by Sitraka Nambinintsoa",
                     font=("Segoe UI", 22), fg="#8fa3c4", bg=COULEUR_FOND).pack(pady=(6, 0))

    # ---------------- mode VOTE : disposition adaptative ----------------
    def _calculer_disposition(self, n, largeur, hauteur):
        """Choisit le nombre de colonnes/lignes qui remplit le mieux
        l'écran pour n candidats (favorise des cartes ni trop étroites,
        ni trop basses), et renvoie (colonnes, lignes, cell_w, cell_h).
        Objectif : que TOUS les candidats tiennent sur un seul écran
        jusqu'à une trentaine, avec une police qui s'adapte plutôt que de
        paginer."""
        n = max(1, n)
        zone_h = hauteur - 150   # réserve pour le titre du poste + marges
        meilleur = None
        for colonnes in range(1, min(n, 7) + 1):
            lignes = math.ceil(n / colonnes)
            cell_w = largeur / colonnes
            cell_h = zone_h / lignes
            # on pénalise les cartes trop "écrasées" (trop larges et
            # basses, ou trop étroites et hautes) pour garder un format
            # lisible, proche d'une carte de visite
            ratio = cell_w / max(cell_h, 1)
            penalite = abs(ratio - 1.6) * 0.15
            score = min(cell_w, cell_h * 1.6) * (1 - penalite)
            if meilleur is None or score > meilleur[0]:
                meilleur = (score, colonnes, lignes, cell_w, cell_h)
        _, colonnes, lignes, cell_w, cell_h = meilleur
        return colonnes, lignes, cell_w, cell_h

    def afficher_vote(self, poste):
        """(Re)construit l'affichage pour ce poste. À appeler quand le vote
        est lancé, ou que la liste de candidats change."""
        self._poste_courant = poste
        self._vider()

        tk.Label(self.conteneur, text=poste.nom, font=("Segoe UI", 30, "bold"),
                 fg=COULEUR_ACCENT, bg=COULEUR_FOND).pack(pady=(16, 4))

        candidats = list(poste.candidats)
        n = max(1, len(candidats))
        largeur, hauteur = self._dimensions_disponibles()
        colonnes, lignes, cell_w, cell_h = self._calculer_disposition(n, largeur, hauteur)

        # Capacité d'une page = colonnes x lignes calculées pour ce nombre
        # de candidats. On ne pagine QUE si même la plus petite police
        # lisible ne suffirait pas (cas extrême, très grand nombre de
        # candidats) — repli de sécurité, jamais le cas normal (<= ~30).
        capacite = colonnes * lignes
        if cell_h < 90 and n > capacite:
            # recalcule une capacité raisonnable par page avec une taille
            # de carte minimale lisible
            lignes_page = max(1, int((hauteur - 150) // 90))
            capacite = colonnes * lignes_page

        self._pages = [candidats[i:i + capacite]
                        for i in range(0, len(candidats), capacite)] or [[]]
        self._colonnes = colonnes
        self._lignes = lignes
        self._cell_w, self._cell_h = cell_w, cell_h
        self._index_page = 0
        self._afficher_page_courante()
        self._programmer_rotation()

    def _tailles_police(self, cell_w, cell_h):
        """Police dérivée de la taille réelle de la carte — grande si peu
        de candidats, plus petite (mais toujours lisible) s'ils sont
        nombreux."""
        base = min(cell_w / 7.0, cell_h / 4.2)
        taille_nom = max(13, min(56, int(base)))
        taille_score = max(16, min(96, int(base * 1.55)))
        taille_num = max(10, min(20, int(base * 0.45)))
        return (("Segoe UI", taille_nom, "bold"),
                ("Segoe UI", taille_score, "bold"),
                ("Segoe UI", taille_num, "bold"))

    def _candidats_en_tete(self):
        """Ids des candidats actuellement en tête, selon le nombre de
        sièges à pourvoir du poste (mis en avant visuellement, mis à jour
        en direct à chaque vote)."""
        if self._poste_courant is None:
            return set()
        n = max(1, getattr(self._poste_courant, "nombre_sieges", 1))
        classement = self._poste_courant.classement()
        if not classement:
            return set()
        tete = classement[:n]
        if any(c.votes > 0 for c in tete):
            return {c.id for c in tete}
        return set()  # personne n'a encore de voix : pas de mise en avant

    def _dessiner_carte(self, canvas, w, h, cand, en_tete, police_nom, police_score, police_num):
        """Dessine une carte "pro" avec un effet de profondeur simulé :
        ombre portée décalée + dégradé vertical + bordure lumineuse pour
        les candidats actuellement en tête."""
        canvas.delete("all")
        marge = max(4, int(min(w, h) * 0.035))
        decalage_ombre = max(3, int(min(w, h) * 0.02))
        rayon = max(8, int(min(w, h) * 0.06))

        x0, y0 = marge, marge
        x1, y1 = w - marge, h - marge

        # ombre portée (rectangle sombre légèrement décalé derrière la carte)
        self._rect_arrondi(canvas, x0 + decalage_ombre, y0 + decalage_ombre,
                            x1 + decalage_ombre, y1 + decalage_ombre, rayon,
                            fill=COULEUR_OMBRE, outline="")

        haut = COULEUR_LEADER_HAUT if en_tete else COULEUR_CARTE_HAUT
        bas = COULEUR_LEADER_BAS if en_tete else COULEUR_CARTE_BAS
        bord = COULEUR_LEADER_BORD if en_tete else COULEUR_CARTE_BORD

        # dégradé vertical simulé par bandes horizontales
        n_bandes = max(6, int(y1 - y0))
        for i in range(n_bandes):
            t = i / max(1, n_bandes - 1)
            couleur = self._interpoler_couleur(haut, bas, t)
            by0 = y0 + (y1 - y0) * i / n_bandes
            by1 = y0 + (y1 - y0) * (i + 1) / n_bandes
            canvas.create_rectangle(x0, by0, x1, by1 + 1, fill=couleur, outline="")

        # re-arrondit les coins par-dessus (masque les bandes qui dépassent)
        self._rect_arrondi(canvas, x0, y0, x1, y1, rayon, fill="",
                            outline=bord, width=3 if en_tete else 2)
        self._masquer_coins(canvas, x0, y0, x1, y1, rayon, COULEUR_FOND)

        # liseré lumineux en haut de carte (effet "glossy")
        canvas.create_line(x0 + rayon, y0 + 2, x1 - rayon, y0 + 2,
                            fill=self._interpoler_couleur(haut, "#ffffff", 0.25), width=2)

        item_num = canvas.create_text(x0 + 14, y0 + 14, anchor="nw",
                                       text="N° %d" % cand.numero, font=police_num,
                                       fill="#9fb3d6" if not en_tete else "#bfe9cf")
        if en_tete:
            canvas.create_text(x1 - 14, y0 + 14, anchor="ne", text="★ EN TÊTE",
                                font=police_num, fill=COULEUR_LEADER_BORD)

        texte_nom = cand.nom
        item_nom = canvas.create_text((x0 + x1) / 2, (y0 + y1) * 0.46,
                                       text=texte_nom, font=police_nom,
                                       fill=COULEUR_TEXTE, width=int((x1 - x0) * 0.9),
                                       justify="center")
        item_score = canvas.create_text((x0 + x1) / 2, y1 - (y1 - y0) * 0.18,
                                         text=str(cand.votes), font=police_score,
                                         fill=COULEUR_ELU if en_tete else COULEUR_ACCENT)
        return {"fond_haut": haut, "fond_bas": bas, "bord": bord,
                "item_nom": item_nom, "item_score": item_score, "item_num": item_num}

    @staticmethod
    def _interpoler_couleur(c1, c2, t):
        def hex_vers_rgb(c):
            c = c.lstrip("#")
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        r1, g1, b1 = hex_vers_rgb(c1)
        r2, g2, b2 = hex_vers_rgb(c2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return "#%02x%02x%02x" % (r, g, b)

    @staticmethod
    def _rect_arrondi(canvas, x0, y0, x1, y1, r, **kw):
        points = [
            x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
        ]
        return canvas.create_polygon(points, smooth=True, **kw)

    def _masquer_coins(self, canvas, x0, y0, x1, y1, r, couleur_fond):
        """Masque les 4 coins carrés laissés par le dégradé en bandes avec
        la couleur de fond, pour un rendu arrondi propre."""
        for (cx, cy) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            canvas.create_rectangle(cx - r, cy - r, cx + r, cy + r,
                                     fill=couleur_fond, outline="", tags="masque")
            canvas.tag_lower("masque")

    def _afficher_page_courante(self):
        for w in list(self.conteneur.winfo_children())[1:]:
            w.destroy()
        self._cartes = {}

        grille = tk.Frame(self.conteneur, bg=COULEUR_FOND)
        grille.pack(fill="both", expand=True, padx=20, pady=6)

        for c in range(self._colonnes):
            grille.columnconfigure(c, weight=1, uniform="col")
        page = self._pages[self._index_page] if self._pages else []
        lignes_page = math.ceil(len(page) / self._colonnes) if page else 1
        for r in range(max(1, lignes_page)):
            grille.rowconfigure(r, weight=1)

        police_nom, police_score, police_num = self._tailles_police(self._cell_w, self._cell_h)
        en_tete = self._candidats_en_tete()

        for i, cand in enumerate(page):
            ligne, col = divmod(i, self._colonnes)
            canvas = tk.Canvas(grille, bg=COULEUR_FOND, highlightthickness=0, bd=0)
            canvas.grid(row=ligne, column=col, sticky="nsew", padx=10, pady=8)

            def redessiner(event, cv=canvas, c=cand, pn=police_nom, ps=police_score, pnum=police_num):
                etat_tete = c.id in self._candidats_en_tete()
                items = self._dessiner_carte(cv, event.width, event.height, c, etat_tete, pn, ps, pnum)
                if c.id in self._cartes:
                    self._cartes[c.id].update(items)
                    self._cartes[c.id]["en_tete"] = etat_tete

            canvas.bind("<Configure>", redessiner)
            self._cartes[cand.id] = {"canvas": canvas, "en_tete": cand.id in en_tete,
                                      "flash_actif": False}

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
        police_nom, police_score, police_num = self._tailles_police(self._cell_w, self._cell_h)
        en_tete = cand_id in self._candidats_en_tete()
        items = self._dessiner_carte(canvas, w, h, cand, en_tete, police_nom, police_score, police_num)
        info.update(items)
        info["en_tete"] = en_tete

    def rafraichir_scores(self, poste=None):
        """Met à jour les scores affichés (appelé après chaque +/-), et
        recalcule en direct quels candidats sont actuellement en tête
        (mis en avant visuellement selon le nombre de sièges)."""
        if self._poste_courant is None:
            return
        en_tete = self._candidats_en_tete()
        for cand in self._poste_courant.candidats:
            info = self._cartes.get(cand.id)
            if info is None:
                continue
            nouvel_etat = cand.id in en_tete
            if nouvel_etat != info.get("en_tete") or not info.get("flash_actif"):
                self._redessiner_carte(cand.id)
            elif "item_score" in info:
                try:
                    info["canvas"].itemconfigure(info["item_score"], text=str(cand.votes))
                except Exception:
                    self._redessiner_carte(cand.id)

    def flash_candidat(self, cand_id):
        """Fait clignoter la carte du candidat qui vient de recevoir un
        point. Plus long qu'avant, avec un petit délai avant de revenir à
        l'état normal (pour bien laisser le temps à l'assemblée de voir
        qui vient de marquer un point)."""
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
        marge = max(4, int(min(w, h) * 0.035))
        rayon = max(8, int(min(w, h) * 0.06))
        self._rect_arrondi(canvas, marge, marge, w - marge, h - marge, rayon,
                            fill=COULEUR_CARTE_FLASH, outline=COULEUR_CARTE_FLASH, width=3)
        police_nom, police_score, police_num = self._tailles_police(self._cell_w, self._cell_h)
        canvas.create_text((marge + w - marge) / 2, h * 0.46, text=cand.nom,
                            font=police_nom, fill=COULEUR_TEXTE_FLASH,
                            width=int((w - 2 * marge) * 0.9), justify="center")
        canvas.create_text((marge + w - marge) / 2, h - (h - marge) * 0.18,
                            text=str(cand.votes), font=police_score, fill=COULEUR_TEXTE_FLASH)
        canvas.create_text(marge + 14, marge + 14, anchor="nw", text="N° %d" % cand.numero,
                            font=police_num, fill=COULEUR_TEXTE_FLASH)

        if cand_id in self._job_flash:
            try:
                self.after_cancel(self._job_flash[cand_id])
            except Exception:
                pass

        def revenir():
            info["flash_actif"] = False
            self._job_flash.pop(cand_id, None)
            self.after(DELAI_RETOUR_FLASH_MS, lambda: self._redessiner_carte(cand_id))

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
