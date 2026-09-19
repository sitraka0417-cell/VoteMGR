# -*- coding: utf-8 -*-
"""
secretary.py — Écran 1 : fenêtre de contrôle du secrétaire.

C'est lui/elle qui saisit les votes (au fur et à mesure que le bureau de
vote annonce chaque nom lu sur les bulletins), gère l'arborescence
sections/postes/candidats, et décide de ce qui est projeté sur l'écran 2.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from . import storage
from . import monitors
from .models import Projet, Noeud
from .projection import FenetreProjection

try:
    from .pdf_export import exporter_pdf
    PDF_DISPONIBLE = True
except Exception:
    PDF_DISPONIBLE = False

DOSSIER_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
CHEMIN_LOGO = os.path.join(DOSSIER_ASSETS, "logo.png")

DELAI_SAISIE_CLAVIER_MS = 2000   # latence max entre deux chiffres tapés (ex: 1 puis 2 -> n°12)

THEMES = {
    "clair": {
        "bg": "#f4f6f9", "fg": "#1a1a1a", "bg_widget": "#ffffff",
        "bg_saisie": "#ffffff", "bg_arbre": "#ffffff", "accent": "#1a73e8",
        "bg_carte": "#ffffff", "select": "#d7e6fb",
    },
    "sombre": {
        "bg": "#1e222a", "fg": "#e8e8e8", "bg_widget": "#262b35",
        "bg_saisie": "#2b303b", "bg_arbre": "#20242c", "accent": "#5b9bf7",
        "bg_carte": "#262b35", "select": "#33465e",
    },
}


class SecretaryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VoteMGR — Écran secrétaire")
        self.geometry("1200x760")
        self.minsize(980, 620)

        self.projet = Projet("Nouveau projet")
        self.chemin_fichier = None
        self.noeud_selectionne_id = None
        self.projection = None
        self.ecrans = monitors.lister_ecrans()

        # saisie clavier des numéros de candidats (ex: taper 1 puis 2 -> n°12)
        self._buffer_saisie = ""
        self._job_saisie = None

        # pile pour "Annuler la dernière action" (＋/－ de vote uniquement)
        self._pile_annulation = []

        self.theme = "clair"

        self._construire_menu()
        self._construire_layout()
        self._rafraichir_arbre()
        self._rafraichir_titre()
        self._appliquer_theme(self.theme)

        self.bind_all("<Key>", self._on_touche_globale)
        self.bind_all("<Control-z>", lambda e: self._annuler_derniere_action())

        self.protocol("WM_DELETE_WINDOW", self._quitter)
        self.after(60000, self._autosave_periodique)

    # ================= construction UI =================
    def _construire_menu(self):
        barre = tk.Menu(self)

        m_fichier = tk.Menu(barre, tearoff=0)
        m_fichier.add_command(label="Nouveau projet", command=self.nouveau_projet)
        m_fichier.add_command(label="Ouvrir...", command=self.ouvrir_projet)
        m_fichier.add_command(label="Enregistrer", command=self.enregistrer_projet)
        m_fichier.add_command(label="Enregistrer sous...", command=self.enregistrer_projet_sous)
        m_fichier.add_separator()
        m_fichier.add_command(label="Quitter", command=self._quitter)
        barre.add_cascade(label="Fichier", menu=m_fichier)

        m_projet = tk.Menu(barre, tearoff=0)
        m_projet.add_command(label="Importer une liste de candidats...",
                              command=self.importer_liste_dialog)
        m_projet.add_command(label="Exporter tous les résultats en PDF...",
                              command=self.exporter_pdf_dialog)
        m_projet.add_command(label="Rechercher un poste / un candidat...",
                              command=lambda: self.champ_recherche.focus_set())
        m_projet.add_separator()
        m_projet.add_command(label="Définir le nombre de votants présents (quorum)...",
                              command=self._definir_votants_presents)
        m_projet.add_command(label="Annuler la dernière action (Ctrl+Z)",
                              command=self._annuler_derniere_action)
        barre.add_cascade(label="Projet", menu=m_projet)

        m_ecran = tk.Menu(barre, tearoff=0)
        m_ecran.add_command(label="Ouvrir l'écran de projection",
                             command=self.ouvrir_ecran_projection)
        m_ecran.add_command(label="Basculer plein écran (projection)",
                             command=self._basculer_plein_ecran_projection)
        m_ecran.add_command(label="Revenir au logo (écran 2)",
                             command=self._projeter_idle)
        m_ecran.add_command(label="Projeter le bureau élu complet",
                             command=self.projeter_bureau_complet)
        barre.add_cascade(label="Écran de projection", menu=m_ecran)

        m_aide = tk.Menu(barre, tearoff=0)
        m_aide.add_command(label="À propos", command=self._a_propos)
        barre.add_cascade(label="Aide", menu=m_aide)

        self.config(menu=barre)

    def _construire_layout(self):
        # ---- barre de recherche ----
        barre_recherche = ttk.Frame(self, padding=(8, 6))
        barre_recherche.pack(fill="x")
        ttk.Label(barre_recherche, text="Rechercher un poste ou un candidat :").pack(side="left")
        self.var_recherche = tk.StringVar()
        self.champ_recherche = ttk.Entry(barre_recherche, textvariable=self.var_recherche, width=40)
        self.champ_recherche.pack(side="left", padx=6)
        self.champ_recherche.bind("<KeyRelease>", lambda e: self._rechercher())

        self.combo_resultats = ttk.Combobox(barre_recherche, width=60, state="readonly")
        self.combo_resultats.pack(side="left", padx=6, fill="x", expand=True)
        self.combo_resultats.bind("<<ComboboxSelected>>", self._aller_au_resultat)
        self._resultats_recherche = []

        ttk.Button(barre_recherche, text="↩ Annuler (Ctrl+Z)",
                   command=self._annuler_derniere_action).pack(side="right", padx=(6, 0))
        self.bouton_theme = ttk.Button(barre_recherche, text="🌙 Thème sombre",
                                        command=self._basculer_theme)
        self.bouton_theme.pack(side="right", padx=(6, 0))

        # ---- zone principale : arbre + panneau ----
        principal = ttk.Panedwindow(self, orient="horizontal")
        principal.pack(fill="both", expand=True)

        cadre_arbre = ttk.Frame(principal, padding=6)
        principal.add(cadre_arbre, weight=1)

        self.arbre = ttk.Treeview(cadre_arbre, show="tree")
        self.arbre.pack(fill="both", expand=True)
        self.arbre.bind("<<TreeviewSelect>>", self._on_selection_arbre)

        boutons_arbre = ttk.Frame(cadre_arbre)
        boutons_arbre.pack(fill="x", pady=6)
        ttk.Button(boutons_arbre, text="+ Section",
                   command=self.ajouter_section).pack(side="left", padx=2)
        ttk.Button(boutons_arbre, text="+ Sous-section",
                   command=self.ajouter_sous_section).pack(side="left", padx=2)
        ttk.Button(boutons_arbre, text="+ Poste (exéco)",
                   command=self.ajouter_poste).pack(side="left", padx=2)
        ttk.Button(boutons_arbre, text="Renommer",
                   command=self.renommer_noeud).pack(side="left", padx=2)
        ttk.Button(boutons_arbre, text="Supprimer",
                   command=self.supprimer_noeud).pack(side="left", padx=2)

        self.cadre_panneau = ttk.Frame(principal, padding=10)
        principal.add(self.cadre_panneau, weight=3)

        self._afficher_panneau_vide()

        # ---- barre de statut ----
        self.var_statut = tk.StringVar(value="Prêt.")
        ttk.Label(self, textvariable=self.var_statut, relief="sunken",
                  anchor="w", padding=(6, 2)).pack(fill="x", side="bottom")

    # ================= thème clair / sombre =================
    def _basculer_theme(self):
        self.theme = "sombre" if self.theme == "clair" else "clair"
        self._appliquer_theme(self.theme)

    def _appliquer_theme(self, mode):
        couleurs = THEMES[mode]
        self.bouton_theme.config(
            text="☀ Thème clair" if mode == "sombre" else "🌙 Thème sombre")

        self.configure(bg=couleurs["bg"])

        style = ttk.Style(self)
        base_theme = "clam"
        if base_theme in style.theme_names():
            style.theme_use(base_theme)

        style.configure(".", background=couleurs["bg"], foreground=couleurs["fg"],
                         fieldbackground=couleurs["bg_saisie"])
        for widget in ("TFrame", "TLabelframe", "TLabelframe.Label", "TPanedwindow"):
            style.configure(widget, background=couleurs["bg"], foreground=couleurs["fg"])
        style.configure("TLabel", background=couleurs["bg"], foreground=couleurs["fg"])
        style.configure("TButton", background=couleurs["bg_widget"], foreground=couleurs["fg"])
        style.map("TButton", background=[("active", couleurs["select"])])
        style.configure("Accent.TButton", background=couleurs["accent"], foreground="#ffffff",
                         font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", couleurs["accent"])])
        style.configure("TEntry", fieldbackground=couleurs["bg_saisie"], foreground=couleurs["fg"])
        style.configure("TCombobox", fieldbackground=couleurs["bg_saisie"], foreground=couleurs["fg"])
        style.configure("TSpinbox", fieldbackground=couleurs["bg_saisie"], foreground=couleurs["fg"])
        style.configure("TCheckbutton", background=couleurs["bg"], foreground=couleurs["fg"])
        style.configure("Treeview", background=couleurs["bg_arbre"], fieldbackground=couleurs["bg_arbre"],
                         foreground=couleurs["fg"])
        style.map("Treeview", background=[("selected", couleurs["select"])])

        # ré-affiche le panneau courant pour que les widgets tk "bruts"
        # (Canvas de la liste de candidats) reprennent aussi les couleurs
        noeud = self._noeud_courant()
        if noeud is not None:
            if noeud.est_poste():
                self._afficher_panneau_poste(noeud)
            else:
                self._afficher_panneau_section(noeud)

    # ================= arbre =================
    def _rafraichir_arbre(self):
        self.arbre.delete(*self.arbre.get_children())
        for section in self.projet.sections:
            self._inserer_noeud("", section)

    def _inserer_noeud(self, parent_iid, noeud):
        prefixe = "🗳 " if noeud.est_poste() else "📁 "
        suffixe = ""
        if noeud.est_poste():
            if noeud.vote_termine:
                suffixe = "  ✅ terminé"
            elif noeud.vote_lance:
                suffixe = "  🔴 vote en cours"
        iid = self.arbre.insert(parent_iid, "end", iid=noeud.id,
                                 text=prefixe + noeud.nom + suffixe, open=True)
        for enfant in noeud.enfants:
            self._inserer_noeud(iid, enfant)
        return iid

    def _on_selection_arbre(self, event=None):
        sel = self.arbre.selection()
        if not sel:
            return
        self.noeud_selectionne_id = sel[0]
        noeud = self.projet.trouver(self.noeud_selectionne_id)
        if noeud is None:
            return
        if noeud.est_poste():
            self._afficher_panneau_poste(noeud)
        else:
            self._afficher_panneau_section(noeud)

    def _noeud_courant(self):
        if not self.noeud_selectionne_id:
            return None
        return self.projet.trouver(self.noeud_selectionne_id)

    # ---- gestion arbre : ajout / suppression / renommage ----
    def ajouter_section(self):
        nom = simpledialog.askstring("Nouvelle section", "Nom de la section :", parent=self)
        if not nom:
            return
        n = Noeud(nom, type_="section")
        self.projet.sections.append(n)
        self._rafraichir_arbre()
        self._selectionner(n.id)
        self._statut("Section « %s » ajoutée." % nom)

    def ajouter_sous_section(self):
        parent = self._noeud_courant()
        if parent is None or parent.est_poste():
            messagebox.showinfo("Sous-section", "Sélectionnez d'abord une section.")
            return
        nom = simpledialog.askstring("Nouvelle sous-section", "Nom de la sous-section :", parent=self)
        if not nom:
            return
        n = Noeud(nom, type_="section")
        parent.enfants.append(n)
        self._rafraichir_arbre()
        self._selectionner(n.id)
        self._statut("Sous-section « %s » ajoutée sous « %s »." % (nom, parent.nom))

    def ajouter_poste(self):
        parent = self._noeud_courant()
        nom = simpledialog.askstring("Nouveau poste", "Nom du poste (ex: Président, Trésorier...) :", parent=self)
        if not nom:
            return
        n = Noeud(nom, type_="poste")
        if parent is None or parent.est_poste():
            self.projet.sections.append(n)
        else:
            parent.enfants.append(n)
        self._rafraichir_arbre()
        self._selectionner(n.id)
        self._statut("Poste « %s » créé." % nom)

    def renommer_noeud(self):
        noeud = self._noeud_courant()
        if noeud is None:
            return
        nouveau = simpledialog.askstring("Renommer", "Nouveau nom :", initialvalue=noeud.nom, parent=self)
        if not nouveau:
            return
        noeud.nom = nouveau
        self._rafraichir_arbre()
        self._selectionner(noeud.id)

    def supprimer_noeud(self):
        noeud = self._noeud_courant()
        if noeud is None:
            return
        if not messagebox.askyesno("Supprimer", "Supprimer « %s » et tout son contenu ?" % noeud.nom):
            return
        self._retirer_du_parent(noeud.id)
        self.noeud_selectionne_id = None
        self._rafraichir_arbre()
        self._afficher_panneau_vide()

    def _retirer_du_parent(self, node_id):
        self.projet.sections = [s for s in self.projet.sections if s.id != node_id]
        def parcourir(n):
            n.enfants = [e for e in n.enfants if e.id != node_id]
            for e in n.enfants:
                parcourir(e)
        for s in self.projet.sections:
            parcourir(s)

    def _selectionner(self, node_id):
        self.arbre.selection_set(node_id)
        self.arbre.see(node_id)
        self._on_selection_arbre()

    # ================= panneaux =================
    def _vider_panneau(self):
        for w in self.cadre_panneau.winfo_children():
            w.destroy()

    def _afficher_panneau_vide(self):
        self._vider_panneau()
        ttk.Label(self.cadre_panneau,
                  text="Sélectionnez une section ou un poste dans l'arbre à gauche,\n"
                       "ou créez-en un nouveau.",
                  justify="center").pack(expand=True)

    def _afficher_panneau_section(self, noeud):
        self._vider_panneau()
        ttk.Label(self.cadre_panneau, text=noeud.nom,
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(self.cadre_panneau,
                  text="Section (conteneur). Ajoutez des sous-sections ou des "
                       "postes à pourvoir depuis les boutons de gauche.").pack(
            anchor="w", pady=(4, 12))

        postes = list(noeud.parcourir_postes())
        if postes:
            ttk.Label(self.cadre_panneau, text="Postes contenus :",
                       font=("Segoe UI", 11, "bold")).pack(anchor="w")
            for p in postes:
                etat = "terminé" if p.vote_termine else ("en cours" if p.vote_lance else "pas encore lancé")
                ttk.Label(self.cadre_panneau, text=" • %s — %s" % (p.nom, etat)).pack(anchor="w")

    def _afficher_panneau_poste(self, noeud):
        self._vider_panneau()
        p = self.cadre_panneau
        couleurs = THEMES[self.theme]

        entete = ttk.Frame(p)
        entete.pack(fill="x")
        ttk.Label(entete, text=noeud.nom, font=("Segoe UI", 18, "bold")).pack(side="left")

        ligne_sieges = ttk.Frame(p)
        ligne_sieges.pack(fill="x", pady=(2, 4))
        ttk.Label(ligne_sieges, text="Sièges à pourvoir :").pack(side="left")
        var_sieges = tk.IntVar(value=noeud.nombre_sieges)
        spin = ttk.Spinbox(ligne_sieges, from_=1, to=50, width=5, textvariable=var_sieges,
                            state="disabled" if noeud.vote_lance else "normal")
        spin.pack(side="left", padx=6)

        var_majorite = tk.BooleanVar(value=noeud.majorite_absolue)

        def appliquer_sieges():
            noeud.nombre_sieges = max(1, var_sieges.get())
            noeud.majorite_absolue = var_majorite.get()
            self._statut("Réglages mis à jour pour « %s »." % noeud.nom)

        ttk.Button(ligne_sieges, text="Appliquer", command=appliquer_sieges,
                   state="disabled" if noeud.vote_lance else "normal").pack(side="left")

        ligne_majorite = ttk.Frame(p)
        ligne_majorite.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(
            ligne_majorite, variable=var_majorite,
            text="Exiger la majorité absolue (>50% des voix exprimées) pour être élu(e) — "
                 "désactivé par défaut",
            state="disabled" if noeud.vote_lance else "normal",
            command=appliquer_sieges).pack(side="left")

        # ---- quorum / participation ----
        if self.projet.votants_presents:
            exprimes = noeud.voix_exprimees()
            participation = (exprimes / self.projet.votants_presents * 100) \
                if self.projet.votants_presents else 0
            ttk.Label(p, text="Votants présents : %d · Voix exprimées pour ce poste : %d (%.0f%%)"
                      % (self.projet.votants_presents, exprimes, participation),
                      foreground="#5b6b85").pack(anchor="w", pady=(0, 6))

        # ---- actions candidats ----
        actions_cand = ttk.Frame(p)
        actions_cand.pack(fill="x", pady=(0, 8))
        ttk.Button(actions_cand, text="+ Ajouter un candidat",
                   command=lambda: self._ajouter_candidat(noeud)).pack(side="left", padx=(0, 6))
        ttk.Button(actions_cand, text="Importer une liste pour ce poste",
                   command=lambda: self._importer_pour_poste(noeud)).pack(side="left", padx=(0, 6))
        if PDF_DISPONIBLE:
            ttk.Button(actions_cand, text="📄 Exporter ce poste en PDF",
                       command=lambda: self._exporter_pdf_poste(noeud)).pack(side="left")

        # ---- actions vote ----
        actions_vote = ttk.Frame(p)
        actions_vote.pack(fill="x", pady=(0, 6))

        if not noeud.vote_lance and not noeud.vote_termine:
            ttk.Button(actions_vote, text="▶ Lancer le vote", style="Accent.TButton",
                       command=lambda: self._lancer_vote(noeud)).pack(side="left", padx=(0, 6))
        if noeud.vote_lance:
            ttk.Button(actions_vote, text="■ Terminer le vote",
                       command=lambda: self._terminer_vote(noeud)).pack(side="left", padx=(0, 6))
            ttk.Button(actions_vote, text="🔄 Réinitialiser le vote (à 0)",
                       command=lambda: self._reinitialiser_vote(noeud)).pack(side="left", padx=(0, 6))
        if noeud.vote_lance or noeud.vote_termine:
            ttk.Button(actions_vote, text="📽 Projeter ce poste (écran 2)",
                       command=lambda: self._projeter_poste(noeud)).pack(side="left", padx=(0, 6))
        if noeud.vote_termine:
            ttk.Button(actions_vote, text="🏆 Projeter les résultats",
                       command=lambda: self._projeter_resultats(noeud)).pack(side="left", padx=(0, 6))
        if noeud.egalite_en_attente:
            ttk.Button(actions_vote, text="⚖ Égalité : créer un tour de départage",
                       command=lambda: self._creer_departage(noeud)).pack(side="left", padx=(0, 6))
        if noeud.majorite_non_atteinte:
            ttk.Button(actions_vote, text="🔁 Majorité non atteinte : créer un 2e tour",
                       command=lambda: self._creer_tour_majorite(noeud)).pack(side="left", padx=(0, 6))

        if noeud.vote_lance:
            ttk.Label(p, text="Astuce : tapez directement le numéro du candidat au clavier "
                               "(ex: 1 puis 2 en moins de 2s pour le n°12) pour lui ajouter une voix.",
                      foreground="#5b6b85").pack(anchor="w", pady=(0, 6))

        # ---- bulletins nuls / blancs ----
        if noeud.vote_lance or noeud.bulletins_nuls or noeud.bulletins_blancs:
            ligne_bb = ttk.Frame(p)
            ligne_bb.pack(fill="x", pady=(0, 8))
            ligne_bb.pack_propagate(True)

            def ligne_compteur(parent, libelle, valeur_getter, incr, decr):
                cadre = ttk.Frame(parent)
                cadre.pack(side="left", padx=(0, 24))
                ttk.Label(cadre, text=libelle + " :").pack(side="left")
                var = tk.StringVar(value=str(valeur_getter()))
                if noeud.vote_lance:
                    ttk.Button(cadre, text="－", width=3, command=decr).pack(side="left", padx=(6, 0))
                ttk.Label(cadre, textvariable=var, width=3, anchor="center").pack(side="left")
                if noeud.vote_lance:
                    ttk.Button(cadre, text="＋", width=3, command=incr).pack(side="left")
                return var

            def maj_blancs(delta):
                noeud.modifier_bulletins_blancs(delta)
                self._afficher_panneau_poste(noeud)
                storage.autosave_rapide(self.projet)

            def maj_nuls(delta):
                noeud.modifier_bulletins_nuls(delta)
                self._afficher_panneau_poste(noeud)
                storage.autosave_rapide(self.projet)

            ligne_compteur(ligne_bb, "Bulletins blancs", lambda: noeud.bulletins_blancs,
                           lambda: maj_blancs(1), lambda: maj_blancs(-1))
            ligne_compteur(ligne_bb, "Bulletins nuls", lambda: noeud.bulletins_nuls,
                           lambda: maj_nuls(1), lambda: maj_nuls(-1))

        # ---- liste candidats ----
        cadre_liste = ttk.Frame(p)
        cadre_liste.pack(fill="both", expand=True)
        canvas = tk.Canvas(cadre_liste, highlightthickness=0, bg=couleurs["bg_arbre"])
        scrollbar = ttk.Scrollbar(cadre_liste, orient="vertical", command=canvas.yview)
        conteneur = ttk.Frame(canvas)
        conteneur.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=conteneur, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        entetes = ttk.Frame(conteneur)
        entetes.pack(fill="x", pady=(0, 4))
        for texte, larg in (("N°", 4), ("Candidat", 40), ("Voix", 6), ("", 14)):
            ttk.Label(entetes, text=texte, width=larg, font=("Segoe UI", 9, "bold")).pack(side="left")

        for c in noeud.classement():
            ligne = ttk.Frame(conteneur)
            ligne.pack(fill="x", pady=2)
            fond_elu = " 🏅" if c.id in noeud.elus else ""
            ttk.Label(ligne, text=str(c.numero), width=4).pack(side="left")
            ttk.Label(ligne, text=c.nom + fond_elu, width=40).pack(side="left")
            var_score = tk.StringVar(value=str(c.votes))
            lbl_score = ttk.Label(ligne, textvariable=var_score, width=6)
            lbl_score.pack(side="left")

            if noeud.vote_lance:
                ttk.Button(ligne, text="－", width=3,
                           command=lambda cid=c.id, v=var_score: self._voter(noeud, cid, -1, v)).pack(side="left")
                ttk.Button(ligne, text="＋", width=3,
                           command=lambda cid=c.id, v=var_score: self._voter(noeud, cid, 1, v)).pack(side="left", padx=(4, 10))
            if not noeud.vote_lance:
                ttk.Button(ligne, text="Retirer", width=8,
                           command=lambda cid=c.id: self._retirer_candidat(noeud, cid)).pack(side="left", padx=(10, 0))

        if not noeud.candidats:
            ttk.Label(conteneur, text="Aucun candidat pour ce poste pour l'instant.").pack(anchor="w", pady=10)

    # ================= actions candidats =================
    def _ajouter_candidat(self, noeud):
        nom = simpledialog.askstring("Nouveau candidat", "Nom du candidat :", parent=self)
        if not nom:
            return
        noeud.ajouter_candidat(nom)
        self._afficher_panneau_poste(noeud)
        self._statut("Candidat « %s » ajouté à « %s »." % (nom, noeud.nom))

    def _retirer_candidat(self, noeud, cand_id):
        noeud.retirer_candidat(cand_id)
        self._afficher_panneau_poste(noeud)

    def _importer_pour_poste(self, noeud):
        chemin = filedialog.askopenfilename(
            title="Importer une liste de candidats",
            filetypes=[("CSV ou JSON", "*.csv *.json"), ("Tous fichiers", "*.*")])
        if not chemin:
            return
        try:
            noms = storage.importer_candidats(chemin)
        except Exception as e:
            messagebox.showerror("Import", "Impossible de lire ce fichier :\n%s" % e)
            return
        for nom in noms:
            noeud.ajouter_candidat(nom)
        self._afficher_panneau_poste(noeud)
        self._statut("%d candidat(s) importé(s) pour « %s »." % (len(noms), noeud.nom))

    def importer_liste_dialog(self):
        noeud = self._noeud_courant()
        if noeud is None or not noeud.est_poste():
            messagebox.showinfo("Importer", "Sélectionnez d'abord un poste dans l'arbre.")
            return
        self._importer_pour_poste(noeud)

    # ================= actions vote =================
    def _lancer_vote(self, noeud):
        if not noeud.candidats:
            messagebox.showwarning("Vote", "Ajoutez au moins un candidat avant de lancer le vote.")
            return
        if not messagebox.askyesno(
                "Lancer le vote",
                "Lancer le vote pour « %s » avec %d candidat(s) ?\n"
                "Les compteurs seront remis à zéro." % (noeud.nom, len(noeud.candidats))):
            return
        noeud.lancer_vote()
        self._rafraichir_arbre()
        self._selectionner(noeud.id)
        self._projeter_poste(noeud)
        storage.sauvegarde_auto(self.projet)
        self._statut("Vote lancé pour « %s »." % noeud.nom)

    def _reinitialiser_vote(self, noeud):
        if not messagebox.askyesno("Réinitialiser", "Remettre tous les compteurs de « %s » à zéro ?" % noeud.nom):
            return
        for c in noeud.candidats:
            c.votes = 0
        self._afficher_panneau_poste(noeud)
        if self.projection is not None:
            self.projection.rafraichir_scores()

    def _voter(self, noeud, cand_id, delta, var_score=None, enregistrer_undo=True):
        c = noeud.voter(cand_id, delta)
        if c is None:
            return None
        if var_score is not None:
            var_score.set(str(c.votes))
        if self.projection is not None:
            self.projection.rafraichir_scores()
            if delta > 0:
                self.projection.flash_candidat(cand_id)
        storage.autosave_rapide(self.projet)
        if enregistrer_undo:
            self._pile_annulation.append((noeud.id, cand_id, delta))
            del self._pile_annulation[:-50]  # garde les 50 dernières actions
        return c

    # ---- saisie clavier des numéros pendant un vote ----
    def _on_touche_globale(self, event):
        widget = event.widget
        if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Spinbox, tk.Spinbox,
                                ttk.Combobox, tk.Text)):
            return  # laisser taper normalement dans les champs de saisie
        noeud = self._noeud_courant()
        if noeud is None or not noeud.est_poste() or not noeud.vote_lance:
            return
        car = event.char
        if not car or not car.isdigit():
            return
        self._buffer_saisie += car
        self._statut("Saisie clavier : n° %s_  (validation automatique dans 2s, "
                     "ou tapez le chiffre suivant)" % self._buffer_saisie)
        if self._job_saisie:
            self.after_cancel(self._job_saisie)
        self._job_saisie = self.after(
            DELAI_SAISIE_CLAVIER_MS, lambda n=noeud: self._valider_saisie_clavier(n))

    def _valider_saisie_clavier(self, noeud):
        tampon = self._buffer_saisie
        self._buffer_saisie = ""
        self._job_saisie = None
        if not tampon:
            return
        numero = int(tampon)
        cand = next((c for c in noeud.candidats if c.numero == numero), None)
        if cand is None:
            self._statut("Aucun candidat n°%d pour « %s »." % (numero, noeud.nom))
            return
        c = self._voter(noeud, cand.id, 1)
        if c is None:
            return
        self._statut("Vote au clavier enregistré : n°%d — %s (total %d voix)."
                     % (cand.numero, cand.nom, c.votes))
        if self.noeud_selectionne_id == noeud.id:
            self._afficher_panneau_poste(noeud)

    def _annuler_derniere_action(self):
        if not self._pile_annulation:
            self._statut("Rien à annuler.")
            return
        noeud_id, cand_id, delta = self._pile_annulation.pop()
        noeud = self.projet.trouver(noeud_id)
        if noeud is None:
            self._statut("Impossible d'annuler : poste introuvable.")
            return
        c = noeud.voter(cand_id, -delta)
        if self.projection is not None:
            self.projection.rafraichir_scores()
        storage.autosave_rapide(self.projet)
        if self.noeud_selectionne_id == noeud_id:
            self._afficher_panneau_poste(noeud)
        if c is not None:
            self._statut("Action annulée : n°%d — %s (« %s », total %d voix)."
                         % (c.numero, c.nom, noeud.nom, c.votes))

    def _definir_votants_presents(self):
        valeur = simpledialog.askinteger(
            "Votants présents",
            "Nombre de membres présents / votants (quorum) :",
            initialvalue=self.projet.votants_presents or 0, minvalue=0, parent=self)
        if valeur is None:
            return
        self.projet.votants_presents = valeur
        self._statut("Nombre de votants présents fixé à %d." % valeur)
        noeud = self._noeud_courant()
        if noeud is not None and noeud.est_poste():
            self._afficher_panneau_poste(noeud)

    def _exporter_pdf_poste(self, noeud):
        if not PDF_DISPONIBLE:
            messagebox.showerror("Export PDF", "Le module 'reportlab' n'est pas installé.")
            return
        chemin = filedialog.asksaveasfilename(
            title="Exporter ce poste en PDF", defaultextension=".pdf",
            initialfile="resultats_%s.pdf" % noeud.nom.replace(" ", "_"),
            filetypes=[("Fichier PDF", "*.pdf")])
        if not chemin:
            return
        try:
            exporter_pdf(chemin, self.projet, postes=[noeud])
            self._statut("PDF exporté pour « %s » : %s" % (noeud.nom, chemin))
            messagebox.showinfo("Export PDF", "Résultats exportés avec succès :\n%s" % chemin)
        except Exception as e:
            messagebox.showerror("Export PDF", "Erreur pendant l'export :\n%s" % e)

    def _creer_tour_majorite(self, noeud):
        tour = noeud.creer_tour_majorite()
        parent = self._trouver_parent(noeud.id)
        if parent is None:
            self.projet.sections.append(tour)
        else:
            parent.enfants.append(tour)
        self._rafraichir_arbre()
        self._selectionner(tour.id)
        self._statut("2e tour créé : « %s »." % tour.nom)

    def _terminer_vote(self, noeud):
        if not messagebox.askyesno("Terminer le vote", "Clôturer le vote pour « %s » ?" % noeud.nom):
            return
        complet = noeud.terminer_vote()
        self._rafraichir_arbre()
        self._selectionner(noeud.id)
        storage.sauvegarde_auto(self.projet)
        if complet:
            self._statut("Vote terminé pour « %s ». %d élu(e)(s)." % (noeud.nom, len(noeud.elus)))
        elif noeud.majorite_non_atteinte:
            self._statut("Majorité absolue non atteinte pour « %s »." % noeud.nom)
            messagebox.showinfo(
                "Majorité absolue non atteinte",
                "Aucun candidat n'a obtenu plus de 50%% des voix exprimées pour "
                "« %s » (ou pas pour tous les sièges).\n"
                "Utilisez le bouton « Créer un 2e tour »." % noeud.nom)
        else:
            self._statut("Égalité détectée pour « %s » : un tour de départage est nécessaire." % noeud.nom)
            messagebox.showinfo(
                "Égalité",
                "Il y a égalité entre %d candidat(s) pour les %d dernière(s) place(s).\n"
                "Utilisez le bouton « Créer un tour de départage »."
                % (len(noeud.egalite_en_attente), noeud.nombre_sieges - len(noeud.elus)))

    def _creer_departage(self, noeud):
        tour = noeud.creer_tour_departage()
        parent = self._trouver_parent(noeud.id)
        if parent is None:
            self.projet.sections.append(tour)
        else:
            parent.enfants.append(tour)
        self._rafraichir_arbre()
        self._selectionner(tour.id)
        self._statut("Tour de départage créé : « %s »." % tour.nom)

    def _trouver_parent(self, node_id):
        def chercher(n):
            for e in n.enfants:
                if e.id == node_id:
                    return n
                r = chercher(e)
                if r:
                    return r
            return None
        for s in self.projet.sections:
            if s.id == node_id:
                return None
            r = chercher(s)
            if r:
                return r
        return None

    # ================= écran de projection =================
    def ouvrir_ecran_projection(self):
        if self.projection is not None and self.projection.winfo_exists():
            self.projection.deiconify()
            self.projection.lift()
            return
        logo = CHEMIN_LOGO if os.path.exists(CHEMIN_LOGO) else None
        self.projection = FenetreProjection(self, logo_path=logo)

        if len(self.ecrans) > 1:
            self.projection.placer_sur_ecran(self.ecrans[1])
        else:
            self.projection.geometry("1024x600+80+80")
        self.after(300, self.projection.basculer_plein_ecran)
        self._statut("Écran de projection ouvert (%d écran(s) détecté(s))." % len(self.ecrans))

    def _basculer_plein_ecran_projection(self):
        if self.projection is None:
            self.ouvrir_ecran_projection()
        else:
            self.projection.basculer_plein_ecran()

    def _projeter_idle(self):
        if self.projection is None:
            self.ouvrir_ecran_projection()
        self.projection.afficher_idle()

    def _projeter_poste(self, noeud):
        if self.projection is None:
            self.ouvrir_ecran_projection()
        self.projection.afficher_vote(noeud)
        self._statut("« %s » projeté sur l'écran 2." % noeud.nom)

    def _projeter_resultats(self, noeud):
        if self.projection is None:
            self.ouvrir_ecran_projection()
        if not messagebox.askyesno("Projeter les résultats",
                                    "Afficher les résultats de « %s » à l'assemblée ?" % noeud.nom):
            return
        self.projection.afficher_resultats(noeud)
        self._statut("Résultats de « %s » projetés." % noeud.nom)

    def projeter_bureau_complet(self):
        postes_termines = [p for p in self.projet.tous_les_postes() if p.vote_termine]
        if not postes_termines:
            messagebox.showinfo("Bureau élu", "Aucun poste n'a encore de résultat.")
            return
        if self.projection is None:
            self.ouvrir_ecran_projection()
        self.projection.afficher_resultats(postes_termines)

    # ================= recherche =================
    def _rechercher(self):
        texte = self.var_recherche.get()
        resultats = self.projet.rechercher(texte)
        self._resultats_recherche = resultats
        affichage = []
        for poste, cand, motif in resultats:
            if motif == "poste":
                affichage.append("📁 Poste : %s" % poste.nom)
            else:
                elu = " (élu)" if cand.id in poste.elus else ""
                affichage.append("👤 %s%s — poste : %s" % (cand.nom, elu, poste.nom))
        self.combo_resultats["values"] = affichage
        if affichage:
            self.combo_resultats.current(0)

    def _aller_au_resultat(self, event=None):
        idx = self.combo_resultats.current()
        if idx < 0 or idx >= len(self._resultats_recherche):
            return
        poste, cand, motif = self._resultats_recherche[idx]
        self._selectionner(poste.id)

    # ================= fichiers =================
    def nouveau_projet(self):
        if not messagebox.askyesno("Nouveau projet", "Créer un nouveau projet ? Les données non enregistrées seront perdues."):
            return
        nom = simpledialog.askstring("Nouveau projet", "Nom du projet :", initialvalue="Nouveau projet", parent=self)
        self.projet = Projet(nom or "Nouveau projet")
        self.chemin_fichier = None
        self._rafraichir_arbre()
        self._afficher_panneau_vide()
        self._rafraichir_titre()

    def ouvrir_projet(self):
        chemin = filedialog.askopenfilename(
            title="Ouvrir un projet VoteMGR",
            filetypes=[("Projet VoteMGR", "*.vmgr *.json"), ("Tous fichiers", "*.*")])
        if not chemin:
            return
        try:
            self.projet = storage.charger_projet(chemin)
            self.chemin_fichier = chemin
        except Exception as e:
            messagebox.showerror("Ouvrir", "Impossible d'ouvrir ce projet :\n%s" % e)
            return
        self._rafraichir_arbre()
        self._afficher_panneau_vide()
        self._rafraichir_titre()
        self._statut("Projet chargé : %s" % chemin)

    def enregistrer_projet(self):
        if not self.chemin_fichier:
            return self.enregistrer_projet_sous()
        try:
            storage.enregistrer_projet(self.projet, self.chemin_fichier)
            self._statut("Projet enregistré : %s" % self.chemin_fichier)
        except Exception as e:
            messagebox.showerror("Enregistrer", "Erreur d'enregistrement :\n%s" % e)

    def enregistrer_projet_sous(self):
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer le projet sous...", defaultextension=".vmgr",
            filetypes=[("Projet VoteMGR", "*.vmgr")])
        if not chemin:
            return
        self.chemin_fichier = chemin
        self.enregistrer_projet()
        self._rafraichir_titre()

    def exporter_pdf_dialog(self):
        if not PDF_DISPONIBLE:
            messagebox.showerror(
                "Export PDF",
                "Le module 'reportlab' n'est pas installé.\n"
                "Installez-le avec : pip install reportlab")
            return
        chemin = filedialog.asksaveasfilename(
            title="Exporter les résultats en PDF", defaultextension=".pdf",
            filetypes=[("Fichier PDF", "*.pdf")])
        if not chemin:
            return
        try:
            exporter_pdf(chemin, self.projet)
            self._statut("PDF exporté : %s" % chemin)
            messagebox.showinfo("Export PDF", "Résultats exportés avec succès :\n%s" % chemin)
        except Exception as e:
            messagebox.showerror("Export PDF", "Erreur pendant l'export :\n%s" % e)

    # ================= divers =================
    def _autosave_periodique(self):
        storage.sauvegarde_auto(self.projet)
        self.after(120000, self._autosave_periodique)

    def _rafraichir_titre(self):
        nom_fichier = os.path.basename(self.chemin_fichier) if self.chemin_fichier else "(non enregistré)"
        self.title("VoteMGR — %s — %s" % (self.projet.nom, nom_fichier))

    def _statut(self, texte):
        self.var_statut.set(texte)

    def _a_propos(self):
        messagebox.showinfo(
            "À propos de VoteMGR",
            "VoteMGR — gestion de vote d'assemblée générale\n"
            "par Sitraka Nambinintsoa\n\n"
            "Écran 1 : contrôle du secrétaire.\n"
            "Écran 2 : projection pour l'assemblée.")

    def _quitter(self):
        storage.sauvegarde_auto(self.projet)
        self.destroy()
