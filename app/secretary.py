# -*- coding: utf-8 -*-
"""
secretary.py — Écran 1 : fenêtre de contrôle du secrétaire.

C'est lui/elle qui saisit les votes (au fur et à mesure que le bureau de
vote annonce chaque nom lu sur les bulletins), gère l'arborescence
sections/postes/candidats, et décide de ce qui est projeté sur l'écran 2.

Fidèle au fonctionnement de l'app Android d'origine (vaomiera) : tout
noeud peut contenir des sous-noeuds ET être lui-même votable, un seul
vote peut être ouvert à la fois dans tout le projet, et on retrouve les
mêmes fonctionnalités (désignation sans vote, mode "rôles", sessions de
présence, badge "déjà élu ailleurs", etc.) — seule la distinction
admin/participant en réseau n'existe pas ici (un seul secrétaire, votes
au bulletin papier).
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

# ================= Internationalisation (français / anglais) =================
# Dictionnaire de traduction : clé -> {"fr": ..., "en": ...}. self.t(cle)
# renvoie le texte dans la langue courante (repli sur le français si la
# clé n'existe pas encore). Couvre les menus, la barre d'outils et le
# panneau de vote ; les boîtes de dialogue secondaires moins fréquentes
# restent en français si elles ne sont pas listées ici.
I18N = {
    "titre_fenetre": {"fr": "VoteMGR — Écran secrétaire", "en": "VoteMGR — Secretary screen"},
    "menu_fichier": {"fr": "Fichier", "en": "File"},
    "menu_nouveau_projet": {"fr": "Nouveau projet", "en": "New project"},
    "menu_ouvrir": {"fr": "Ouvrir...", "en": "Open..."},
    "menu_enregistrer": {"fr": "Enregistrer", "en": "Save"},
    "menu_enregistrer_sous": {"fr": "Enregistrer sous...", "en": "Save as..."},
    "menu_quitter": {"fr": "Quitter", "en": "Quit"},
    "menu_projet": {"fr": "Projet", "en": "Project"},
    "menu_importer_membres": {"fr": "👥 Importer la liste des membres (réutilisable pour tous les votes)...",
                               "en": "👥 Import the member list (reusable for all votes)..."},
    "menu_importer_poste": {"fr": "Importer une liste directement dans le poste sélectionné...",
                             "en": "Import a list directly into the selected seat..."},
    "menu_sessions": {"fr": "🗓 Sessions / présence...", "en": "🗓 Sessions / attendance..."},
    "menu_export_pdf": {"fr": "Exporter tous les résultats en PDF...", "en": "Export all results to PDF..."},
    "menu_rechercher": {"fr": "Rechercher un poste / un candidat...", "en": "Search a seat / a candidate..."},
    "menu_quorum": {"fr": "Définir le nombre de votants présents (quorum)...",
                     "en": "Set the number of voters present (quorum)..."},
    "menu_annuler": {"fr": "Annuler la dernière action (Ctrl+Z)", "en": "Undo last action (Ctrl+Z)"},
    "menu_ecran": {"fr": "Écran de projection", "en": "Projection screen"},
    "menu_ouvrir_ecran": {"fr": "Ouvrir l'écran de projection", "en": "Open the projection screen"},
    "menu_configurer_ecran": {"fr": "Configurer l'écran (dupliqué / étendu)...",
                               "en": "Configure the screen (duplicate / extend)..."},
    "menu_plein_ecran": {"fr": "Basculer plein écran (projection)", "en": "Toggle fullscreen (projection)"},
    "menu_revenir_logo": {"fr": "Revenir au logo (écran 2)", "en": "Back to logo (screen 2)"},
    "menu_bureau_complet": {"fr": "Projeter le bureau élu complet", "en": "Project the full elected board"},
    "menu_aide": {"fr": "Aide", "en": "Help"},
    "menu_a_propos": {"fr": "À propos", "en": "About"},

    "rechercher_label": {"fr": "Rechercher un poste ou un candidat :", "en": "Search a seat or a candidate:"},
    "bouton_annuler_ctrlz": {"fr": "↩ Annuler (Ctrl+Z)", "en": "↩ Undo (Ctrl+Z)"},
    "theme_sombre": {"fr": "🌙 Thème sombre", "en": "🌙 Dark theme"},
    "theme_clair": {"fr": "☀ Thème clair", "en": "☀ Light theme"},
    "langue_bouton": {"fr": "🌐 EN", "en": "🌐 FR"},

    "bouton_section": {"fr": "+ Section", "en": "+ Section"},
    "bouton_sous_section": {"fr": "+ Sous-section / sous-poste", "en": "+ Sub-section / sub-seat"},
    "bouton_renommer": {"fr": "Renommer", "en": "Rename"},
    "bouton_supprimer": {"fr": "Supprimer", "en": "Delete"},

    "panneau_vide": {"fr": "Sélectionnez une section ou un poste dans l'arbre à gauche,\nou créez-en un nouveau.",
                      "en": "Select a section or a seat in the tree on the left,\nor create a new one."},
    "contient": {"fr": "Contient", "en": "Contains"},
    "ajouter_enfant": {"fr": "+ Ajouter une sous-section / un sous-poste ici",
                        "en": "+ Add a sub-section / sub-seat here"},
    "vote_pour": {"fr": "Vote pour « %s » :", "en": "Vote for “%s”:"},
    "sieges_a_pourvoir": {"fr": "Sièges à pourvoir :", "en": "Seats to fill:"},
    "appliquer": {"fr": "Appliquer", "en": "Apply"},
    "postes_multiples": {"fr": "🎭 Postes multiples (mode rôles)...", "en": "🎭 Multiple seats (roles mode)..."},
    "majorite_absolue_check": {"fr": "Exiger la majorité absolue (>50% des voix exprimées) pour être élu(e) — "
                                      "désactivé par défaut",
                                "en": "Require an absolute majority (>50% of votes cast) to be elected — "
                                      "off by default"},
    "mode_roles_actif": {"fr": "Mode rôles actif : ", "en": "Roles mode active: "},
    "votants_participation": {"fr": "Votants présents : %d · Voix exprimées pour ce poste : %d (%.0f%%)",
                               "en": "Voters present: %d · Votes cast for this seat: %d (%.0f%%)"},

    "ajouter_candidat": {"fr": "+ Ajouter un candidat", "en": "+ Add a candidate"},
    "depuis_membres": {"fr": "👥 Depuis la liste des membres", "en": "👥 From the member list"},
    "importer_fichier_poste": {"fr": "Importer une liste (fichier) pour ce poste",
                                "en": "Import a list (file) for this seat"},
    "exporter_pdf_poste": {"fr": "📄 Exporter ce poste en PDF", "en": "📄 Export this seat to PDF"},

    "lancer_vote": {"fr": "▶ Lancer le vote", "en": "▶ Start the vote"},
    "designer_sans_vote": {"fr": "🏷 Désigner sans vote", "en": "🏷 Appoint without a vote"},
    "terminer_vote": {"fr": "■ Terminer le vote", "en": "■ Close the vote"},
    "reinitialiser_vote": {"fr": "🔄 Réinitialiser le vote (à 0)", "en": "🔄 Reset the vote (to 0)"},
    "projeter_poste": {"fr": "📽 Projeter ce poste (écran 2)", "en": "📽 Project this seat (screen 2)"},
    "projeter_resultats": {"fr": "🏆 Projeter les résultats", "en": "🏆 Project the results"},
    "modifier_refaire": {"fr": "↻ Modifier / Refaire le vote", "en": "↻ Edit / Redo the vote"},
    "creer_departage": {"fr": "⚖ Égalité : créer un tour de départage", "en": "⚖ Tie: create a tie-break round"},
    "creer_tour_majorite": {"fr": "🔁 Majorité non atteinte : créer un 2e tour",
                             "en": "🔁 Majority not reached: create a 2nd round"},
    "second_tour_manuel": {"fr": "⚖ Créer un second tour (ex-æquo, choix manuel)",
                            "en": "⚖ Create a second round (tie, manual pick)"},
    "astuce_clavier": {"fr": "Astuce : tapez directement le numéro du candidat au clavier "
                             "(ex: 1 puis 2 en moins de 2s pour le n°12) pour lui ajouter une voix.",
                        "en": "Tip: type the candidate's number directly on the keyboard "
                              "(e.g. 1 then 2 within 2s for n°12) to add a vote."},

    "bulletins_blancs": {"fr": "Bulletins blancs", "en": "Blank ballots"},
    "bulletins_nuls": {"fr": "Bulletins nuls", "en": "Spoiled ballots"},
    "colonne_numero": {"fr": "N°", "en": "No."},
    "colonne_candidat": {"fr": "Candidat", "en": "Candidate"},
    "colonne_voix": {"fr": "Voix", "en": "Votes"},
    "aucun_candidat": {"fr": "Aucun candidat pour ce poste pour l'instant.", "en": "No candidate for this seat yet."},
    "retirer": {"fr": "Retirer", "en": "Remove"},

    "statut_attente": {"fr": "pas encore lancé", "en": "not started yet"},
    "statut_ouvert": {"fr": "🔴 en cours", "en": "🔴 in progress"},
    "statut_ferme": {"fr": "✅ terminé", "en": "✅ closed"},
    "statut_designe": {"fr": "🏷 désigné", "en": "🏷 appointed"},

    "pret": {"fr": "Prêt.", "en": "Ready."},
    "non_enregistre": {"fr": "(non enregistré)", "en": "(not saved)"},

    "export_pdf_titre": {"fr": "Exporter en PDF", "en": "Export to PDF"},
    "export_pdf_question": {"fr": "Que voulez-vous exporter ?", "en": "What do you want to export?"},
    "export_pdf_elus": {"fr": "Candidats élus uniquement", "en": "Elected candidates only"},
    "export_pdf_deroulement": {"fr": "Déroulement complet du vote (toutes les voix)",
                                "en": "Full voting process (all votes)"},
    "exporter": {"fr": "Exporter", "en": "Export"},
    "annuler": {"fr": "Annuler", "en": "Cancel"},
}


def _t(lang, cle, *fmt):
    entree = I18N.get(cle)
    texte = entree.get(lang, entree.get("fr")) if entree else cle
    if fmt:
        try:
            return texte % fmt
        except Exception:
            return texte
    return texte


class SecretaryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VoteMGR")
        self.geometry("1200x760")
        self.minsize(900, 520)
        # Démarre agrandie pour que tout soit visible d'emblée, quelle
        # que soit la résolution de l'écran (évite les boutons "coupés"
        # en bas de fenêtre) ; la molette/barre de défilement du panneau
        # de droite prend ensuite le relais si la fenêtre est redimensionnée.
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass

        self.projet = Projet("Nouveau projet")
        self.chemin_fichier = None
        self.noeud_selectionne_id = None
        self.projection = None
        self.ecrans = monitors.lister_ecrans()
        self.mode_projection = "auto"     # "auto" | "duplique" | "etendu"
        self.index_ecran_manuel = None    # index choisi en mode "étendu"

        # saisie clavier des numéros de candidats (ex: taper 1 puis 2 -> n°12)
        self._buffer_saisie = ""
        self._job_saisie = None

        # pile pour "Annuler la dernière action" (＋/－ de vote uniquement)
        self._pile_annulation = []

        self.theme = "clair"
        self.lang = "fr"   # "fr" | "en"

        self._construire_menu()
        self._construire_layout()
        self._rafraichir_arbre()
        self._rafraichir_titre()
        self._appliquer_theme(self.theme)

        self.bind_all("<Key>", self._on_touche_globale)
        self.bind_all("<Control-z>", lambda e: self._annuler_derniere_action())

        self.protocol("WM_DELETE_WINDOW", self._quitter)
        self.after(60000, self._autosave_periodique)

    # ================= langue =================
    def t(self, cle, *fmt):
        return _t(self.lang, cle, *fmt)

    def _basculer_langue(self):
        self.lang = "en" if self.lang == "fr" else "fr"
        self._rafraichir_textes_interface()

    def _rafraichir_textes_interface(self):
        """Reconstruit le menu et les textes statiques dans la langue
        courante, puis réaffiche le panneau en cours (arbre + panneau de
        droite) pour que tout reste cohérent."""
        self._construire_menu()
        self.title(self.t("titre_fenetre"))
        self._rafraichir_titre()
        self.label_recherche.config(text=self.t("rechercher_label"))
        self.bouton_annuler_barre.config(text=self.t("bouton_annuler_ctrlz"))
        self.bouton_theme.config(text=self.t("theme_sombre") if self.theme == "clair" else self.t("theme_clair"))
        self.bouton_langue.config(text=self.t("langue_bouton"))
        self.bouton_section.config(text=self.t("bouton_section"))
        self.bouton_sous_section.config(text=self.t("bouton_sous_section"))
        self.bouton_renommer.config(text=self.t("bouton_renommer"))
        self.bouton_supprimer.config(text=self.t("bouton_supprimer"))
        self._rafraichir_arbre()
        noeud = self._noeud_courant()
        if noeud is not None:
            self._afficher_panneau_poste(noeud)
        else:
            self._afficher_panneau_vide()
        self._statut(self.t("pret"))

    # ================= construction UI =================
    def _construire_menu(self):
        barre = tk.Menu(self)
        t = self.t

        m_fichier = tk.Menu(barre, tearoff=0)
        m_fichier.add_command(label=t("menu_nouveau_projet"), command=self.nouveau_projet)
        m_fichier.add_command(label=t("menu_ouvrir"), command=self.ouvrir_projet)
        m_fichier.add_command(label=t("menu_enregistrer"), command=self.enregistrer_projet)
        m_fichier.add_command(label=t("menu_enregistrer_sous"), command=self.enregistrer_projet_sous)
        m_fichier.add_separator()
        m_fichier.add_command(label=t("menu_quitter"), command=self._quitter)
        barre.add_cascade(label=t("menu_fichier"), menu=m_fichier)

        m_projet = tk.Menu(barre, tearoff=0)
        m_projet.add_command(label=t("menu_importer_membres"),
                              command=self.importer_liste_membres_dialog)
        m_projet.add_command(label=t("menu_importer_poste"),
                              command=self.importer_liste_dialog)
        m_projet.add_separator()
        m_projet.add_command(label=t("menu_sessions"),
                              command=self.afficher_sessions_dialog)
        m_projet.add_command(label=t("menu_export_pdf"),
                              command=self.exporter_pdf_dialog)
        m_projet.add_command(label=t("menu_rechercher"),
                              command=lambda: self.champ_recherche.focus_set())
        m_projet.add_separator()
        m_projet.add_command(label=t("menu_quorum"),
                              command=self._definir_votants_presents)
        m_projet.add_command(label=t("menu_annuler"),
                              command=self._annuler_derniere_action)
        barre.add_cascade(label=t("menu_projet"), menu=m_projet)

        m_ecran = tk.Menu(barre, tearoff=0)
        m_ecran.add_command(label=t("menu_ouvrir_ecran"),
                             command=self.ouvrir_ecran_projection)
        m_ecran.add_command(label=t("menu_configurer_ecran"),
                             command=self._configurer_ecran_projection)
        m_ecran.add_command(label=t("menu_plein_ecran"),
                             command=self._basculer_plein_ecran_projection)
        m_ecran.add_command(label=t("menu_revenir_logo"),
                             command=self._projeter_idle)
        m_ecran.add_command(label=t("menu_bureau_complet"),
                             command=self.projeter_bureau_complet)
        barre.add_cascade(label=t("menu_ecran"), menu=m_ecran)

        m_aide = tk.Menu(barre, tearoff=0)
        m_aide.add_command(label=t("menu_a_propos"), command=self._a_propos)
        barre.add_cascade(label=t("menu_aide"), menu=m_aide)

        self.config(menu=barre)

    def _construire_layout(self):
        # ---- barre de recherche ----
        barre_recherche = ttk.Frame(self, padding=(8, 6))
        barre_recherche.pack(fill="x")
        self.label_recherche = ttk.Label(barre_recherche, text=self.t("rechercher_label"))
        self.label_recherche.pack(side="left")
        self.var_recherche = tk.StringVar()
        self.champ_recherche = ttk.Entry(barre_recherche, textvariable=self.var_recherche, width=40)
        self.champ_recherche.pack(side="left", padx=6)
        self.champ_recherche.bind("<KeyRelease>", lambda e: self._rechercher())

        self.combo_resultats = ttk.Combobox(barre_recherche, width=60, state="readonly")
        self.combo_resultats.pack(side="left", padx=6, fill="x", expand=True)
        self.combo_resultats.bind("<<ComboboxSelected>>", self._aller_au_resultat)
        self._resultats_recherche = []

        self.bouton_annuler_barre = ttk.Button(barre_recherche, text=self.t("bouton_annuler_ctrlz"),
                                                command=self._annuler_derniere_action)
        self.bouton_annuler_barre.pack(side="right", padx=(6, 0))
        self.bouton_theme = ttk.Button(barre_recherche, text=self.t("theme_sombre"),
                                        command=self._basculer_theme)
        self.bouton_theme.pack(side="right", padx=(6, 0))
        self.bouton_langue = ttk.Button(barre_recherche, text=self.t("langue_bouton"),
                                         command=self._basculer_langue)
        self.bouton_langue.pack(side="right", padx=(6, 0))

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
        self.bouton_section = ttk.Button(boutons_arbre, text=self.t("bouton_section"),
                                          command=self.ajouter_section)
        self.bouton_section.pack(side="left", padx=2)
        self.bouton_sous_section = ttk.Button(boutons_arbre, text=self.t("bouton_sous_section"),
                                               command=self.ajouter_sous_section)
        self.bouton_sous_section.pack(side="left", padx=2)
        self.bouton_renommer = ttk.Button(boutons_arbre, text=self.t("bouton_renommer"),
                                           command=self.renommer_noeud)
        self.bouton_renommer.pack(side="left", padx=2)
        self.bouton_supprimer = ttk.Button(boutons_arbre, text=self.t("bouton_supprimer"),
                                            command=self.supprimer_noeud)
        self.bouton_supprimer.pack(side="left", padx=2)

        # Le panneau de droite est placé dans un Canvas défilant : quels
        # que soient la résolution ou le facteur d'échelle de l'écran,
        # TOUT reste accessible en faisant défiler (barre à droite, ou
        # molette de la souris), aucun bouton ne peut rester caché.
        cadre_panneau_externe = ttk.Frame(principal)
        principal.add(cadre_panneau_externe, weight=3)

        self._canvas_panneau = tk.Canvas(cadre_panneau_externe, highlightthickness=0)
        scrollbar_panneau = ttk.Scrollbar(cadre_panneau_externe, orient="vertical",
                                           command=self._canvas_panneau.yview)
        self.cadre_panneau = ttk.Frame(self._canvas_panneau, padding=10)

        self._fenetre_panneau_id = self._canvas_panneau.create_window(
            (0, 0), window=self.cadre_panneau, anchor="nw")
        self.cadre_panneau.bind(
            "<Configure>",
            lambda e: self._canvas_panneau.configure(scrollregion=self._canvas_panneau.bbox("all")))
        self._canvas_panneau.bind(
            "<Configure>",
            lambda e: self._canvas_panneau.itemconfigure(self._fenetre_panneau_id, width=e.width))
        self._canvas_panneau.configure(yscrollcommand=scrollbar_panneau.set)
        self._canvas_panneau.pack(side="left", fill="both", expand=True)
        scrollbar_panneau.pack(side="right", fill="y")

        def _molette(event):
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            self._canvas_panneau.yview_scroll(int(delta), "units")

        self._canvas_panneau.bind("<Enter>", lambda e: (
            self._canvas_panneau.bind_all("<MouseWheel>", _molette),
            self._canvas_panneau.bind_all("<Button-4>", _molette),
            self._canvas_panneau.bind_all("<Button-5>", _molette)))
        self._canvas_panneau.bind("<Leave>", lambda e: (
            self._canvas_panneau.unbind_all("<MouseWheel>"),
            self._canvas_panneau.unbind_all("<Button-4>"),
            self._canvas_panneau.unbind_all("<Button-5>")))

        self._afficher_panneau_vide()

        # ---- barre de statut ----
        self.var_statut = tk.StringVar(value=self.t("pret"))
        ttk.Label(self, textvariable=self.var_statut, relief="sunken",
                  anchor="w", padding=(6, 2)).pack(fill="x", side="bottom")

    # ================= thème clair / sombre =================
    def _basculer_theme(self):
        self.theme = "sombre" if self.theme == "clair" else "clair"
        self._appliquer_theme(self.theme)

    def _appliquer_theme(self, mode):
        couleurs = THEMES[mode]
        self.bouton_theme.config(
            text=self.t("theme_clair") if mode == "sombre" else self.t("theme_sombre"))

        self.configure(bg=couleurs["bg"])
        if hasattr(self, "_canvas_panneau"):
            self._canvas_panneau.configure(bg=couleurs["bg"])

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
            self._afficher_panneau_poste(noeud)

    # ================= arbre =================
    def _rafraichir_arbre(self):
        self.arbre.delete(*self.arbre.get_children())
        for section in self.projet.sections:
            self._inserer_noeud("", section)

    def _inserer_noeud(self, parent_iid, noeud):
        prefixe = "🗳 " if noeud.est_votable() else "📁 "
        suffixe = ""
        statut = noeud.statut()
        if statut == "ferme":
            suffixe = "  " + self.t("statut_ferme")
        elif statut == "ouvert":
            suffixe = "  🔴 " + ("vote en cours" if self.lang == "fr" else "vote in progress")
        elif statut == "designe":
            suffixe = "  " + self.t("statut_designe")
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
        self._afficher_panneau_poste(noeud)

    def _noeud_courant(self):
        if not self.noeud_selectionne_id:
            return None
        return self.projet.trouver(self.noeud_selectionne_id)

    # ---- badge "déjà élu ailleurs" (⭐), comme calculerElusGlobal() côté Android ----
    def _badge_elu(self, nom, poste_a_exclure=None):
        g = self._elus_global_cache
        postes = g.get(nom.strip().lower())
        if not postes:
            return ""
        if poste_a_exclure is not None:
            postes = [p for p in postes if p != poste_a_exclure]
            if not postes:
                return ""
        return " ⭐ (déjà élu/désigné à %s)" % ", ".join(postes)

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
        """Comme dans l'app Android : on peut ajouter un sous-noeud sous
        N'IMPORTE QUEL noeud (section ou poste), puisqu'il n'y a qu'un
        seul type de noeud — celui-ci pourra à son tour recevoir des
        candidats ou d'autres sous-noeuds."""
        parent = self._noeud_courant()
        if parent is None:
            messagebox.showinfo("Sous-section", "Sélectionnez d'abord une section ou un poste.")
            return
        nom = simpledialog.askstring("Nouvelle sous-section / sous-poste",
                                      "Nom :", parent=self)
        if not nom:
            return
        n = Noeud(nom, type_="section")
        parent.enfants.append(n)
        self._rafraichir_arbre()
        self._selectionner(n.id)
        self._statut("« %s » ajouté(e) sous « %s »." % (nom, parent.nom))

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
        ttk.Label(self.cadre_panneau, text=self.t("panneau_vide"),
                  justify="center").pack(expand=True)

    def _afficher_panneau_poste(self, noeud):
        """Panneau unique pour tout noeud (section ET/OU poste), comme
        dans l'app Android : montre d'abord ce que le noeud contient
        (s'il a des sous-noeuds), puis — toujours — la zone de vote pour
        ce noeud lui-même, qu'il ait déjà des candidats ou non."""
        self._vider_panneau()
        p = self.cadre_panneau
        couleurs = THEMES[self.theme]
        self._elus_global_cache = self.projet.calculer_elus_global()

        entete = ttk.Frame(p)
        entete.pack(fill="x")
        ttk.Label(entete, text=noeud.nom, font=("Segoe UI", 18, "bold")).pack(side="left")

        # ---- contenu (sous-sections / sous-postes) ----
        if noeud.enfants:
            cadre_contenu = ttk.LabelFrame(p, text=self.t("contient"))
            cadre_contenu.pack(fill="x", pady=(8, 10))
            for e in noeud.enfants:
                statut_e = e.statut()
                libelle_statut = {"attente": self.t("statut_attente"), "ouvert": self.t("statut_ouvert"),
                                   "ferme": self.t("statut_ferme"), "designe": self.t("statut_designe")}[statut_e]
                ttk.Label(cadre_contenu, text=" • %s — %s" % (e.nom, libelle_statut)).pack(anchor="w")

        ttk.Button(p, text=self.t("ajouter_enfant"),
                   command=lambda: self._ajouter_enfant_rapide(noeud)).pack(anchor="w", pady=(0, 10))

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(0, 10))
        ttk.Label(p, text=self.t("vote_pour", noeud.nom),
                  font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 6))

        ligne_sieges = ttk.Frame(p)
        ligne_sieges.pack(fill="x", pady=(2, 4))
        ttk.Label(ligne_sieges, text=self.t("sieges_a_pourvoir")).pack(side="left")
        var_sieges = tk.IntVar(value=noeud.nombre_sieges)
        spin = ttk.Spinbox(ligne_sieges, from_=1, to=50, width=5, textvariable=var_sieges,
                            state="disabled" if noeud.vote_lance else "normal")
        spin.pack(side="left", padx=6)

        var_majorite = tk.BooleanVar(value=noeud.majorite_absolue)

        def appliquer_sieges():
            noeud.nombre_sieges = max(1, var_sieges.get())
            noeud.majorite_absolue = var_majorite.get()
            self._statut(("Réglages mis à jour pour « %s »." if self.lang == "fr"
                           else "Settings updated for “%s”.") % noeud.nom)

        ttk.Button(ligne_sieges, text=self.t("appliquer"), command=appliquer_sieges,
                   state="disabled" if noeud.vote_lance else "normal").pack(side="left")
        ttk.Button(ligne_sieges, text=self.t("postes_multiples"),
                   command=lambda: self._configurer_roles(noeud),
                   state="disabled" if noeud.vote_lance else "normal").pack(side="left", padx=(10, 0))

        ligne_majorite = ttk.Frame(p)
        ligne_majorite.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(
            ligne_majorite, variable=var_majorite,
            text=self.t("majorite_absolue_check"),
            state="disabled" if noeud.vote_lance or noeud.mode_roles else "normal",
            command=appliquer_sieges).pack(side="left")

        if noeud.mode_roles and noeud.roles:
            total = sum(r.get("nombre", 0) for r in noeud.roles)
            suffixe_places = (" — %d place(s) au total" if self.lang == "fr"
                               else " — %d seat(s) total") % total
            ttk.Label(p, text=self.t("mode_roles_actif") +
                      ", ".join("%s (%d)" % (r["nom"], r["nombre"]) for r in noeud.roles) +
                      suffixe_places,
                      foreground="#8a5a00").pack(anchor="w", pady=(0, 6))

        # ---- quorum / participation ----
        if self.projet.votants_presents:
            exprimes = noeud.voix_exprimees()
            participation = (exprimes / self.projet.votants_presents * 100) \
                if self.projet.votants_presents else 0
            ttk.Label(p, text=self.t("votants_participation",
                                      self.projet.votants_presents, exprimes, participation),
                      foreground="#5b6b85").pack(anchor="w", pady=(0, 6))

        # ---- actions candidats ----
        actions_cand = ttk.Frame(p)
        actions_cand.pack(fill="x", pady=(0, 8))
        ttk.Button(actions_cand, text=self.t("ajouter_candidat"),
                   command=lambda: self._ajouter_candidat(noeud)).pack(side="left", padx=(0, 6))
        ttk.Button(actions_cand, text=self.t("depuis_membres"),
                   command=lambda: self._ajouter_depuis_membres(noeud)).pack(side="left", padx=(0, 6))
        ttk.Button(actions_cand, text=self.t("importer_fichier_poste"),
                   command=lambda: self._importer_pour_poste(noeud)).pack(side="left", padx=(0, 6))
        if PDF_DISPONIBLE:
            ttk.Button(actions_cand, text=self.t("exporter_pdf_poste"),
                       command=lambda: self._exporter_pdf_poste(noeud)).pack(side="left")

        # ---- actions vote ----
        actions_vote = ttk.Frame(p)
        actions_vote.pack(fill="x", pady=(0, 6))

        statut = noeud.statut()
        if statut == "attente":
            ttk.Button(actions_vote, text=self.t("lancer_vote"), style="Accent.TButton",
                       command=lambda: self._lancer_vote(noeud)).pack(side="left", padx=(0, 6))
            ttk.Button(actions_vote, text=self.t("designer_sans_vote"),
                       command=lambda: self._designer_sans_vote(noeud)).pack(side="left", padx=(0, 6))
        if statut == "ouvert":
            ttk.Button(actions_vote, text=self.t("terminer_vote"),
                       command=lambda: self._terminer_vote(noeud)).pack(side="left", padx=(0, 6))
            ttk.Button(actions_vote, text=self.t("reinitialiser_vote"),
                       command=lambda: self._reinitialiser_vote(noeud)).pack(side="left", padx=(0, 6))
        if statut in ("ouvert", "ferme"):
            ttk.Button(actions_vote, text=self.t("projeter_poste"),
                       command=lambda: self._projeter_poste(noeud)).pack(side="left", padx=(0, 6))
        if statut == "ferme":
            ttk.Button(actions_vote, text=self.t("projeter_resultats"),
                       command=lambda: self._projeter_resultats(noeud)).pack(side="left", padx=(0, 6))
        if statut in ("ferme", "designe"):
            ttk.Button(actions_vote, text=self.t("modifier_refaire"),
                       command=lambda: self._refaire_le_vote(noeud)).pack(side="left", padx=(0, 6))
        if noeud.egalite_en_attente:
            ttk.Button(actions_vote, text=self.t("creer_departage"),
                       command=lambda: self._creer_departage(noeud)).pack(side="left", padx=(0, 6))
        if noeud.majorite_non_atteinte:
            ttk.Button(actions_vote, text=self.t("creer_tour_majorite"),
                       command=lambda: self._creer_tour_majorite(noeud)).pack(side="left", padx=(0, 6))
        if statut == "ferme" and noeud.candidats and len(noeud.candidats) >= 2:
            ttk.Button(actions_vote, text=self.t("second_tour_manuel"),
                       command=lambda: self._creer_tour_manuel(noeud)).pack(side="left", padx=(0, 6))

        if noeud.vote_lance:
            ttk.Label(p, text=self.t("astuce_clavier"),
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

            ligne_compteur(ligne_bb, self.t("bulletins_blancs"), lambda: noeud.bulletins_blancs,
                           lambda: maj_blancs(1), lambda: maj_blancs(-1))
            ligne_compteur(ligne_bb, self.t("bulletins_nuls"), lambda: noeud.bulletins_nuls,
                           lambda: maj_nuls(1), lambda: maj_nuls(-1))

        # ---- liste candidats ----
        if noeud.candidats or statut != "attente" or not noeud.enfants:
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
            for texte, larg in ((self.t("colonne_numero"), 4), (self.t("colonne_candidat"), 44),
                                 (self.t("colonne_voix"), 6), ("", 14)):
                ttk.Label(entetes, text=texte, width=larg, font=("Segoe UI", 9, "bold")).pack(side="left")

            for c in noeud.classement():
                ligne = ttk.Frame(conteneur)
                ligne.pack(fill="x", pady=2)
                est_elu_ici = c.id in noeud.elus
                marque = " 🏷" if (est_elu_ici and noeud.est_designation) else (" 🏅" if est_elu_ici else "")
                badge = self._badge_elu(c.nom, poste_a_exclure=noeud.nom) if not est_elu_ici else ""
                ttk.Label(ligne, text=str(c.numero), width=4).pack(side="left")
                ttk.Label(ligne, text=c.nom + marque + badge, width=44).pack(side="left")
                var_score = tk.StringVar(value=str(c.votes))
                lbl_score = ttk.Label(ligne, textvariable=var_score, width=6)
                lbl_score.pack(side="left")

                if noeud.vote_lance:
                    ttk.Button(ligne, text="－", width=3,
                               command=lambda cid=c.id, v=var_score: self._voter(noeud, cid, -1, v)).pack(side="left")
                    ttk.Button(ligne, text="＋", width=3,
                               command=lambda cid=c.id, v=var_score: self._voter(noeud, cid, 1, v)).pack(side="left", padx=(4, 10))
                if statut == "attente":
                    ttk.Button(ligne, text=self.t("retirer"), width=8,
                               command=lambda cid=c.id: self._retirer_candidat(noeud, cid)).pack(side="left", padx=(10, 0))

            if not noeud.candidats:
                ttk.Label(conteneur, text=self.t("aucun_candidat")).pack(anchor="w", pady=10)

    # ================= actions candidats =================
    def _ajouter_candidat(self, noeud):
        nom = simpledialog.askstring("Nouveau candidat", "Nom du candidat :", parent=self)
        if not nom:
            return
        noeud.ajouter_candidat(nom)
        self._rafraichir_arbre()
        self._selectionner(noeud.id)
        self._statut("Candidat « %s » ajouté à « %s »." % (nom, noeud.nom))

    def _retirer_candidat(self, noeud, cand_id):
        noeud.retirer_candidat(cand_id)
        self._afficher_panneau_poste(noeud)

    def _ajouter_enfant_rapide(self, noeud):
        nom = simpledialog.askstring("Ajouter", "Nom de la sous-section / du sous-poste :", parent=self)
        if not nom:
            return
        n = Noeud(nom, type_="section")
        noeud.enfants.append(n)
        self._rafraichir_arbre()
        self._selectionner(n.id)

    def _ajouter_depuis_membres(self, noeud):
        """Ajout de candidats depuis la liste globale des membres, avec de
        vraies cases à cocher (une par membre, scrollables) plutôt qu'une
        simple sélection multiple dans une liste."""
        if not self.projet.liste_membres:
            messagebox.showinfo(
                "Liste des membres" if self.lang == "fr" else "Member list",
                "Aucune liste de membres importée pour l'instant.\n\n"
                "Utilisez d'abord Projet > « Importer la liste des membres » "
                "pour charger une liste réutilisable pour tous les votes."
                if self.lang == "fr" else
                "No member list imported yet.\n\n"
                "First use Project > “Import the member list” to load a "
                "list reusable for all votes.")
            return
        g = self.projet.calculer_elus_global()
        couleurs = THEMES[self.theme]

        fenetre = tk.Toplevel(self)
        fenetre.title("Ajouter des candidats depuis la liste des membres"
                       if self.lang == "fr" else "Add candidates from the member list")
        fenetre.geometry("480x560")
        fenetre.transient(self)
        fenetre.grab_set()
        fenetre.configure(bg=couleurs["bg"])

        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack(fill="both", expand=True)
        texte_intro = ("Cochez un ou plusieurs membres à ajouter comme "
                        "candidats pour « %s » :" % noeud.nom) if self.lang == "fr" else (
            "Check one or more members to add as candidates for “%s”:" % noeud.nom)
        ttk.Label(cadre, text=texte_intro, wraplength=440, justify="left").pack(anchor="w", pady=(0, 8))

        deja = {c.nom.strip().lower() for c in noeud.candidats}

        # zone défilante de cases à cocher (utile si la liste est longue)
        cadre_scroll = ttk.Frame(cadre)
        cadre_scroll.pack(fill="both", expand=True)
        canvas = tk.Canvas(cadre_scroll, highlightthickness=0, bg=couleurs["bg_arbre"])
        scrollbar = ttk.Scrollbar(cadre_scroll, orient="vertical", command=canvas.yview)
        conteneur = ttk.Frame(canvas)
        conteneur.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=conteneur, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _molette(event):
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            canvas.yview_scroll(int(delta), "units")
        canvas.bind("<Enter>", lambda e: (canvas.bind_all("<MouseWheel>", _molette),
                                           canvas.bind_all("<Button-4>", _molette),
                                           canvas.bind_all("<Button-5>", _molette)))
        canvas.bind("<Leave>", lambda e: (canvas.unbind_all("<MouseWheel>"),
                                           canvas.unbind_all("<Button-4>"),
                                           canvas.unbind_all("<Button-5>")))

        variables = []
        for nom in self.projet.liste_membres:
            deja_present = nom.strip().lower() in deja
            badge = " ⭐" if nom.strip().lower() in g else ""
            var = tk.BooleanVar(value=False)
            chk = ttk.Checkbutton(conteneur, text=nom + badge, variable=var,
                                   state="disabled" if deja_present else "normal")
            chk.pack(anchor="w", pady=1)
            if deja_present:
                var.set(True)
            variables.append((nom, var, deja_present))

        def ajouter_selection():
            ajoutes = 0
            for nom, var, deja_present in variables:
                if var.get() and not deja_present:
                    noeud.ajouter_candidat(nom)
                    ajoutes += 1
            self._rafraichir_arbre()
            self._selectionner(noeud.id)
            self._statut(("%d candidat(s) ajouté(s) depuis la liste des membres." if self.lang == "fr"
                           else "%d candidate(s) added from the member list.") % ajoutes)
            fenetre.destroy()

        boutons = ttk.Frame(cadre)
        boutons.pack(fill="x", pady=(8, 0))
        ttk.Button(boutons, text="Ajouter la sélection" if self.lang == "fr" else "Add selection",
                   style="Accent.TButton", command=ajouter_selection).pack(side="left")
        ttk.Button(boutons, text="Fermer" if self.lang == "fr" else "Close",
                   command=fenetre.destroy).pack(side="left", padx=6)

    def _importer_pour_poste(self, noeud):
        chemin = filedialog.askopenfilename(
            title="Importer une liste de candidats",
            filetypes=[("CSV, TXT ou JSON", "*.csv *.txt *.json"), ("Tous fichiers", "*.*")])
        if not chemin:
            return
        try:
            noms = storage.importer_candidats(chemin)
        except Exception as e:
            messagebox.showerror("Import", "Impossible de lire ce fichier :\n%s" % e)
            return
        if not noms:
            messagebox.showwarning(
                "Import",
                "Aucun candidat trouvé dans ce fichier.\n\n"
                "Vérifiez qu'il contient un nom par ligne (ou une colonne "
                "'nom'), et qu'il n'est pas vide.")
            return
        for nom in noms:
            noeud.ajouter_candidat(nom)
        self._rafraichir_arbre()
        self._selectionner(noeud.id)
        messagebox.showinfo(
            "Import réussi",
            "%d candidat(s) importé(s) pour « %s » :\n\n%s"
            % (len(noms), noeud.nom, "\n".join("• " + n for n in noms[:15]) +
               ("\n…" if len(noms) > 15 else "")))
        self._statut("%d candidat(s) importé(s) pour « %s »." % (len(noms), noeud.nom))

    def importer_liste_dialog(self):
        noeud = self._noeud_courant()
        if noeud is None:
            messagebox.showinfo("Importer", "Sélectionnez d'abord un poste (ou une section) dans l'arbre.")
            return
        self._importer_pour_poste(noeud)

    def importer_liste_membres_dialog(self):
        chemin = filedialog.askopenfilename(
            title="Importer la liste des membres (réutilisable pour tous les votes)",
            filetypes=[("CSV, TXT ou JSON", "*.csv *.txt *.json"), ("Tous fichiers", "*.*")])
        if not chemin:
            return
        try:
            noms = storage.importer_candidats(chemin)
        except Exception as e:
            messagebox.showerror("Import", "Impossible de lire ce fichier :\n%s" % e)
            return
        if not noms:
            messagebox.showwarning("Import", "Aucun nom trouvé dans ce fichier.")
            return
        ajoutes = self.projet.ajouter_membres(noms)
        storage.sauvegarde_auto(self.projet)
        messagebox.showinfo(
            "Import réussi",
            "%d nouveau(x) nom(s) ajouté(s) à la liste des membres (%d au total)."
            % (ajoutes, len(self.projet.liste_membres)))
        self._statut("Liste des membres mise à jour (%d au total)." % len(self.projet.liste_membres))

    # ================= désignation sans vote / mode rôles =================
    def _designer_sans_vote(self, noeud):
        if not noeud.candidats:
            messagebox.showinfo(
                "Désigner sans vote",
                "Ajoutez d'abord au moins un candidat (ou importez-en) avant de pouvoir le/la désigner.")
            return
        g = self.projet.calculer_elus_global()

        fenetre = tk.Toplevel(self)
        fenetre.title("Désigner sans vote — %s" % noeud.nom)
        fenetre.geometry("460x480")
        fenetre.transient(self)
        fenetre.grab_set()

        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack(fill="both", expand=True)
        ttk.Label(cadre, text="Choisissez directement la ou les personnes à nommer "
                               "à « %s », sans organiser de vote :" % noeud.nom,
                  wraplength=420, justify="left").pack(anchor="w", pady=(0, 8))

        liste = tk.Listbox(cadre, selectmode="extended")
        liste.pack(fill="both", expand=True)
        for c in noeud.candidats:
            badge = self._badge_elu(c.nom)
            liste.insert("end", c.nom + badge)

        def valider():
            indices = liste.curselection()
            if not indices:
                messagebox.showwarning("Désigner", "Sélectionnez au moins une personne.")
                return
            cand_ids = [noeud.candidats[i].id for i in indices]
            noeud.designer_sans_vote(cand_ids)
            self._rafraichir_arbre()
            self._selectionner(noeud.id)
            storage.sauvegarde_auto(self.projet)
            self._statut("« %s » désigné(e)(s) sans vote pour « %s »."
                         % (", ".join(noeud.candidat(cid).nom for cid in cand_ids), noeud.nom))
            fenetre.destroy()

        boutons = ttk.Frame(cadre)
        boutons.pack(fill="x", pady=(8, 0))
        ttk.Button(boutons, text="Désigner", style="Accent.TButton", command=valider).pack(side="left")
        ttk.Button(boutons, text="Annuler", command=fenetre.destroy).pack(side="left", padx=6)

    def _configurer_roles(self, noeud):
        fenetre = tk.Toplevel(self)
        fenetre.title("Postes multiples (mode rôles) — %s" % noeud.nom)
        fenetre.geometry("460x480")
        fenetre.transient(self)
        fenetre.grab_set()

        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack(fill="both", expand=True)
        ttk.Label(cadre, text="Un même vote peut pourvoir plusieurs postes classés "
                               "par score (ex : Président = 1er, Vice-Président = 2e...).",
                  wraplength=420, justify="left").pack(anchor="w", pady=(0, 10))

        roles = [dict(r) for r in noeud.roles]  # copie de travail
        liste = tk.Listbox(cadre, height=8)
        liste.pack(fill="both", expand=False)

        def rafraichir():
            liste.delete(0, "end")
            for r in roles:
                liste.insert("end", "%s : %d place(s)" % (r["nom"], r["nombre"]))

        rafraichir()

        ligne_ajout = ttk.Frame(cadre)
        ligne_ajout.pack(fill="x", pady=(10, 4))
        var_nom = tk.StringVar()
        var_nb = tk.IntVar(value=1)
        ttk.Entry(ligne_ajout, textvariable=var_nom, width=20).pack(side="left", padx=(0, 6))
        ttk.Spinbox(ligne_ajout, from_=1, to=50, width=5, textvariable=var_nb).pack(side="left", padx=(0, 6))

        def ajouter_role():
            nom = var_nom.get().strip()
            if not nom:
                return
            roles.append({"nom": nom, "nombre": max(1, var_nb.get())})
            var_nom.set("")
            rafraichir()

        ttk.Button(ligne_ajout, text="+ Ajouter un poste", command=ajouter_role).pack(side="left")

        def supprimer_role():
            sel = liste.curselection()
            if not sel:
                return
            del roles[sel[0]]
            rafraichir()

        ttk.Button(cadre, text="Supprimer le poste sélectionné", command=supprimer_role).pack(anchor="w", pady=(4, 10))

        def valider():
            if not roles:
                messagebox.showwarning("Mode rôles", "Ajoutez au moins un poste.")
                return
            noeud.roles = roles
            noeud.mode_roles = True
            noeud.majorite_absolue = False
            noeud.nombre_sieges = sum(r["nombre"] for r in roles)
            self._afficher_panneau_poste(noeud)
            self._statut("Mode rôles activé pour « %s » (%d poste(s))." % (noeud.nom, len(roles)))
            fenetre.destroy()

        def desactiver():
            noeud.mode_roles = False
            noeud.roles = []
            self._afficher_panneau_poste(noeud)
            fenetre.destroy()

        boutons = ttk.Frame(cadre)
        boutons.pack(fill="x", side="bottom")
        ttk.Button(boutons, text="Valider", style="Accent.TButton", command=valider).pack(side="left")
        ttk.Button(boutons, text="Désactiver le mode rôles", command=desactiver).pack(side="left", padx=6)
        ttk.Button(boutons, text="Annuler", command=fenetre.destroy).pack(side="left")

    # ================= actions vote =================
    def _lancer_vote(self, noeud):
        ok, message = self.projet.peut_ouvrir_vote(noeud)
        if not ok:
            messagebox.showwarning("Vote", message)
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

    def _refaire_le_vote(self, noeud):
        if not messagebox.askyesno(
                "Modifier / Refaire le vote",
                "Remettre « %s » à l'état « pas encore voté » ?\n\n"
                "Les candidats et les réglages (sièges, majorité, rôles) sont "
                "conservés, mais les résultats et désignations actuels seront effacés."
                % noeud.nom):
            return
        noeud.refaire_le_vote()
        self._rafraichir_arbre()
        self._selectionner(noeud.id)
        storage.sauvegarde_auto(self.projet)
        self._statut("« %s » remis à zéro pour revoter." % noeud.nom)

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
        if noeud is None or not noeud.vote_lance:
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
        if noeud is not None:
            self._afficher_panneau_poste(noeud)

    # ================= sessions / présence =================
    def afficher_sessions_dialog(self):
        fenetre = tk.Toplevel(self)
        fenetre.title("Sessions / présence")
        fenetre.geometry("520x480")
        fenetre.transient(self)
        fenetre.grab_set()

        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack(fill="both", expand=True)
        ttk.Label(cadre, text="Enregistrez des sessions d'émargement distinctes "
                               "(ex : « Jour 1 - Matin »), chacune avec sa propre "
                               "liste de personnes présentes.",
                  wraplength=480, justify="left").pack(anchor="w", pady=(0, 10))

        liste = tk.Listbox(cadre, height=8)
        liste.pack(fill="both", expand=False)

        def rafraichir():
            liste.delete(0, "end")
            for s in self.projet.sessions:
                liste.insert("end", "%s — %d présent(s)" % (s["label"], len(s["presents"])))

        rafraichir()

        def nouvelle_session():
            label = simpledialog.askstring("Nouvelle session", "Nom de la session (ex: Jour 1 - Matin) :",
                                            parent=fenetre)
            if not label:
                return
            if not self.projet.liste_membres:
                self.projet.ajouter_session(label, [])
                rafraichir()
                storage.sauvegarde_auto(self.projet)
                return
            self._choisir_presents_pour_session(fenetre, label, rafraichir)

        def supprimer_session():
            sel = liste.curselection()
            if not sel:
                return
            self.projet.retirer_session(sel[0])
            rafraichir()
            storage.sauvegarde_auto(self.projet)

        boutons = ttk.Frame(cadre)
        boutons.pack(fill="x", pady=(10, 0))
        ttk.Button(boutons, text="+ Nouvelle session", style="Accent.TButton",
                   command=nouvelle_session).pack(side="left")
        ttk.Button(boutons, text="Supprimer la session sélectionnée",
                   command=supprimer_session).pack(side="left", padx=6)
        ttk.Button(boutons, text="Fermer", command=fenetre.destroy).pack(side="right")

    def _choisir_presents_pour_session(self, parent_fenetre, label, callback_rafraichir):
        fenetre = tk.Toplevel(parent_fenetre)
        fenetre.title("Présents — %s" % label)
        fenetre.geometry("420x480")
        fenetre.transient(parent_fenetre)
        fenetre.grab_set()

        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack(fill="both", expand=True)
        ttk.Label(cadre, text="Cochez les membres présents pour « %s » :" % label).pack(anchor="w", pady=(0, 6))

        liste = tk.Listbox(cadre, selectmode="extended")
        liste.pack(fill="both", expand=True)
        for nom in self.projet.liste_membres:
            liste.insert("end", nom)

        def valider():
            presents = [self.projet.liste_membres[i] for i in liste.curselection()]
            self.projet.ajouter_session(label, presents)
            storage.sauvegarde_auto(self.projet)
            callback_rafraichir()
            fenetre.destroy()

        ttk.Button(cadre, text="Valider", style="Accent.TButton", command=valider).pack(anchor="w", pady=(8, 0))

    def _choisir_mode_export_pdf(self, callback_suite):
        """Petite boîte de dialogue : « Candidats élus uniquement » ou
        « Déroulement complet du vote ». Appelle callback_suite(mode) avec
        mode = "elus" ou "deroulement" si le secrétaire valide, sinon
        n'appelle rien (annulé)."""
        fenetre = tk.Toplevel(self)
        fenetre.title(self.t("export_pdf_titre"))
        fenetre.geometry("440x220")
        fenetre.transient(self)
        fenetre.grab_set()
        couleurs = THEMES[self.theme]
        fenetre.configure(bg=couleurs["bg"])

        cadre = ttk.Frame(fenetre, padding=16)
        cadre.pack(fill="both", expand=True)
        ttk.Label(cadre, text=self.t("export_pdf_question"),
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

        var_mode = tk.StringVar(value="deroulement")
        ttk.Radiobutton(cadre, variable=var_mode, value="elus",
                        text=self.t("export_pdf_elus")).pack(anchor="w", pady=3)
        ttk.Radiobutton(cadre, variable=var_mode, value="deroulement",
                        text=self.t("export_pdf_deroulement")).pack(anchor="w", pady=3)

        def valider():
            mode = var_mode.get()
            fenetre.destroy()
            callback_suite(mode)

        boutons = ttk.Frame(cadre)
        boutons.pack(fill="x", side="bottom", pady=(16, 0))
        ttk.Button(boutons, text=self.t("exporter"), style="Accent.TButton",
                   command=valider).pack(side="left")
        ttk.Button(boutons, text=self.t("annuler"), command=fenetre.destroy).pack(side="left", padx=6)

    def _exporter_pdf_poste(self, noeud):
        if not PDF_DISPONIBLE:
            messagebox.showerror("Export PDF", "Le module 'reportlab' n'est pas installé.")
            return

        def suite(mode):
            chemin = filedialog.asksaveasfilename(
                title="Exporter ce poste en PDF", defaultextension=".pdf",
                initialfile="resultats_%s.pdf" % noeud.nom.replace(" ", "_"),
                filetypes=[("Fichier PDF", "*.pdf")])
            if not chemin:
                return
            try:
                exporter_pdf(chemin, self.projet, postes=[noeud], mode=mode)
                self._statut("PDF exporté pour « %s » : %s" % (noeud.nom, chemin))
                messagebox.showinfo("Export PDF", "Résultats exportés avec succès :\n%s" % chemin)
            except Exception as e:
                messagebox.showerror("Export PDF", "Erreur pendant l'export :\n%s" % e)

        self._choisir_mode_export_pdf(suite)

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
        elif noeud.mode_roles:
            self._statut("Égalité détectée dans le mode rôles pour « %s »." % noeud.nom)
            messagebox.showinfo(
                "Égalité (mode rôles)",
                "Il y a égalité sur une des tranches de postes pour « %s ».\n"
                "Utilisez « Créer un second tour (ex-æquo) » pour départager "
                "manuellement, puis reclôturez." % noeud.nom)
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

    def _creer_tour_manuel(self, noeud):
        """« Créer un second tour (ex-æquo) » avec un choix manuel des
        candidats, comme le bouton équivalent de l'app Android (pas limité
        aux seuls candidats strictement à égalité)."""
        fenetre = tk.Toplevel(self)
        fenetre.title("Second tour (choix manuel) — %s" % noeud.nom)
        fenetre.geometry("440x480")
        fenetre.transient(self)
        fenetre.grab_set()

        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack(fill="both", expand=True)
        ttk.Label(cadre, text="Choisissez librement au moins 2 candidats à "
                               "reprendre pour un second tour de « %s » :" % noeud.nom,
                  wraplength=400, justify="left").pack(anchor="w", pady=(0, 8))

        liste = tk.Listbox(cadre, selectmode="extended")
        liste.pack(fill="both", expand=True)
        for c in noeud.classement():
            liste.insert("end", "%s (%d voix)" % (c.nom, c.votes))

        def valider():
            indices = liste.curselection()
            if len(indices) < 2:
                messagebox.showwarning("Second tour", "Sélectionnez au moins 2 candidats.")
                return
            classement = noeud.classement()
            cand_ids = [classement[i].id for i in indices]
            tour = noeud.creer_tour_manuel(cand_ids)
            parent = self._trouver_parent(noeud.id)
            if parent is None:
                self.projet.sections.append(tour)
            else:
                parent.enfants.append(tour)
            self._rafraichir_arbre()
            self._selectionner(tour.id)
            self._statut("Second tour (choix manuel) créé : « %s »." % tour.nom)
            fenetre.destroy()

        boutons = ttk.Frame(cadre)
        boutons.pack(fill="x", pady=(8, 0))
        ttk.Button(boutons, text="Créer le second tour", style="Accent.TButton", command=valider).pack(side="left")
        ttk.Button(boutons, text="Annuler", command=fenetre.destroy).pack(side="left", padx=6)

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
            self._positionner_projection()
            return
        logo = CHEMIN_LOGO if os.path.exists(CHEMIN_LOGO) else None
        self.projection = FenetreProjection(self, logo_path=logo)
        self._positionner_projection()
        self._statut("Écran de projection ouvert (%d écran(s) détecté(s), mode : %s)."
                     % (len(self.ecrans), self._libelle_mode_projection()))

    def _libelle_mode_projection(self):
        return {"auto": "automatique", "duplique": "dupliqué",
                "etendu": "étendu"}.get(self.mode_projection, "automatique")

    def _positionner_projection(self):
        """Place et met en plein écran la fenêtre de projection selon le
        mode choisi (automatique / dupliqué / étendu + écran manuel),
        pour que ça corresponde vraiment au mode d'affichage Windows
        (Win+P : Dupliquer / Étendre)."""
        if self.projection is None:
            return

        if self.mode_projection == "duplique":
            # Le projecteur recopie l'écran principal (mode "Dupliquer"
            # de Windows) : on affiche donc en plein écran sur l'écran
            # principal lui-même, qui est mirroré sur le vidéoprojecteur.
            if self.ecrans:
                self.projection.placer_sur_ecran(self.ecrans[0])
        elif self.mode_projection == "etendu":
            # Mode "Étendre" : un vrai 2e écran, avec ses propres
            # coordonnées — on choisit l'écran désigné manuellement
            # (ou le 2e détecté par défaut).
            idx = self.index_ecran_manuel
            if idx is None:
                idx = 1 if len(self.ecrans) > 1 else 0
            idx = max(0, min(idx, len(self.ecrans) - 1))
            if self.ecrans:
                self.projection.placer_sur_ecran(self.ecrans[idx])
        else:
            # Automatique : 2e écran s'il y en a un, sinon fenêtré sur
            # l'écran principal.
            if len(self.ecrans) > 1:
                self.projection.placer_sur_ecran(self.ecrans[1])
            else:
                self.projection.geometry("1024x600+80+80")

        self.after(300, lambda: self.projection.forcer_plein_ecran(True))

    def _basculer_plein_ecran_projection(self):
        if self.projection is None:
            self.ouvrir_ecran_projection()
        else:
            self.projection.basculer_plein_ecran()

    def _configurer_ecran_projection(self):
        fenetre = tk.Toplevel(self)
        fenetre.title("Configurer l'écran de projection")
        fenetre.geometry("520x420")
        fenetre.transient(self)
        fenetre.grab_set()

        cadre = ttk.Frame(fenetre, padding=14)
        cadre.pack(fill="both", expand=True)

        ttk.Label(cadre, text="Écrans détectés :", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        liste_ecrans_widget = tk.Listbox(cadre, height=5)
        liste_ecrans_widget.pack(fill="x", pady=(4, 4))

        def rafraichir_liste_ecrans():
            self.ecrans = monitors.lister_ecrans()
            liste_ecrans_widget.delete(0, "end")
            for i, e in enumerate(self.ecrans):
                liste_ecrans_widget.insert("end", "Écran %d%s : %dx%d à (%d, %d)" % (
                    i + 1, "  [principal]" if e.principal else "",
                    e.largeur, e.hauteur, e.x, e.y))
            combo_ecran_manuel["values"] = ["Écran %d" % (i + 1) for i in range(len(self.ecrans))]
            if not combo_ecran_manuel.get() and self.ecrans:
                combo_ecran_manuel.current(min(1, len(self.ecrans) - 1))

        ttk.Button(cadre, text="🔄 Redétecter les écrans (si vous venez de changer "
                                "le mode d'affichage Windows)",
                   command=rafraichir_liste_ecrans).pack(anchor="w", pady=(0, 10))

        ttk.Label(cadre, text="Mode de projection :", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        var_mode = tk.StringVar(value=self.mode_projection)
        ttk.Radiobutton(
            cadre, variable=var_mode, value="auto",
            text="Automatique — 2e écran si détecté, sinon fenêtré ici").pack(anchor="w", pady=2)
        ttk.Radiobutton(
            cadre, variable=var_mode, value="duplique",
            text="Dupliqué — le vidéoprojecteur recopie l'écran principal "
                 "(mode Windows « Dupliquer »)").pack(anchor="w", pady=2)
        ligne_etendu = ttk.Frame(cadre)
        ligne_etendu.pack(fill="x", pady=2)
        ttk.Radiobutton(
            ligne_etendu, variable=var_mode, value="etendu",
            text="Étendu — écran séparé (mode Windows « Étendre ») :").pack(side="left")
        combo_ecran_manuel = ttk.Combobox(ligne_etendu, width=10, state="readonly")
        combo_ecran_manuel.pack(side="left", padx=6)

        ttk.Label(cadre,
                  text="Astuce : dans Windows, Touche Windows + P permet de choisir "
                       "Dupliquer / Étendre / Deuxième écran uniquement. Réglez le bon "
                       "mode des DEUX côtés (Windows et ici) pour un résultat fiable.",
                  foreground="#5b6b85", wraplength=480, justify="left").pack(anchor="w", pady=(12, 12))

        def appliquer():
            self.mode_projection = var_mode.get()
            if self.mode_projection == "etendu" and combo_ecran_manuel.get():
                self.index_ecran_manuel = int(combo_ecran_manuel.get().split()[-1]) - 1
            fenetre.destroy()
            if self.projection is not None and self.projection.winfo_exists():
                self._positionner_projection()
            self._statut("Mode de projection : %s." % self._libelle_mode_projection())

        boutons = ttk.Frame(cadre)
        boutons.pack(fill="x", side="bottom")
        ttk.Button(boutons, text="Appliquer", style="Accent.TButton",
                   command=appliquer).pack(side="right")
        ttk.Button(boutons, text="Annuler", command=fenetre.destroy).pack(side="right", padx=6)

        rafraichir_liste_ecrans()

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

        def suite(mode):
            chemin = filedialog.asksaveasfilename(
                title="Exporter les résultats en PDF", defaultextension=".pdf",
                filetypes=[("Fichier PDF", "*.pdf")])
            if not chemin:
                return
            try:
                exporter_pdf(chemin, self.projet, mode=mode)
                self._statut("PDF exporté : %s" % chemin)
                messagebox.showinfo("Export PDF", "Résultats exportés avec succès :\n%s" % chemin)
            except Exception as e:
                messagebox.showerror("Export PDF", "Erreur pendant l'export :\n%s" % e)

        self._choisir_mode_export_pdf(suite)

    # ================= divers =================
    def _autosave_periodique(self):
        storage.sauvegarde_auto(self.projet)
        self.after(120000, self._autosave_periodique)

    def _rafraichir_titre(self):
        nom_fichier = os.path.basename(self.chemin_fichier) if self.chemin_fichier else self.t("non_enregistre")
        self.title("%s — %s — %s" % (self.t("titre_fenetre"), self.projet.nom, nom_fichier))

    def _statut(self, texte):
        self.var_statut.set(texte)

    def _a_propos(self):
        if self.lang == "fr":
            messagebox.showinfo(
                "À propos de VoteMGR",
                "VoteMGR — gestion de vote d'assemblée générale\n"
                "par Sitraka Nambinintsoa\n\n"
                "Écran 1 : contrôle du secrétaire.\n"
                "Écran 2 : projection pour l'assemblée.")
        else:
            messagebox.showinfo(
                "About VoteMGR",
                "VoteMGR — general assembly voting management\n"
                "by Sitraka Nambinintsoa\n\n"
                "Screen 1: secretary control.\n"
                "Screen 2: projection for the assembly.")

    def _quitter(self):
        storage.sauvegarde_auto(self.projet)
        self.destroy()
