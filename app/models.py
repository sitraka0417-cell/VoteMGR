# -*- coding: utf-8 -*-
"""
models.py — Modèle de données de VoteMGR (version Windows / secrétaire unique).

Structure générale d'un projet :

Projet
 └── sections[]  (arbre récursif de Noeud)
      Noeud (type = "section")
        └── enfants[] (autres Noeud : sous-sections ou postes)
      Noeud (type = "poste")
        └── candidats[]  (liste de Candidat, ce sont les postes réellement
                           votables — ex: "Président", "Trésorier", ...)

Un "poste" représente un exéco (poste du bureau exécutif) à pourvoir.
Une "section" est un simple conteneur (ex: une région, une commission...).

Tout l'état (votes en cours, numéros, élus) vit dans ces objets ; il n'y a
plus de notion admin/participant ni de réseau : un seul secrétaire pilote
l'écran 1 (contrôle) et pousse l'affichage vers l'écran 2 (projection).
"""

import uuid
import datetime


def nouvel_id():
    return uuid.uuid4().hex[:8]


class Candidat:
    def __init__(self, nom, id=None, numero=0, votes=0):
        self.id = id or nouvel_id()
        self.nom = nom
        self.numero = numero
        self.votes = votes

    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "numero": self.numero,
            "votes": self.votes,
        }

    @staticmethod
    def from_dict(d):
        return Candidat(d.get("nom", ""), id=d.get("id"),
                         numero=d.get("numero", 0), votes=d.get("votes", 0))


class Noeud:
    """Un noeud de l'arbre : soit une 'section' (conteneur), soit un
    'poste' (poste votable, feuille avec des candidats)."""

    def __init__(self, nom, type_="section", id=None, nombre_sieges=1):
        self.id = id or nouvel_id()
        self.nom = nom
        self.type = type_               # "section" | "poste"
        self.enfants = []               # pour type == "section"
        self.candidats = []             # pour type == "poste"
        self.nombre_sieges = nombre_sieges
        self.vote_lance = False
        self.vote_termine = False
        self.elus = []                  # liste d'ids Candidat élus
        self.egalite_en_attente = []    # ids à égalité, en attente de départage
        self.tour = 1                   # numéro de tour (1 = premier tour)
        self.tour_precedent_id = None   # id du poste dont ce poste est le tour suivant
        self.majorite_absolue = False   # option : élu(e) seulement si >50% des voix
        self.majorite_non_atteinte = False  # vrai si majorité absolue demandée mais pas atteinte
        self.bulletins_nuls = 0
        self.bulletins_blancs = 0

    # ---------- helpers arbre ----------
    def est_poste(self):
        return self.type == "poste"

    def trouver(self, node_id):
        if self.id == node_id:
            return self
        for e in self.enfants:
            r = e.trouver(node_id)
            if r:
                return r
        return None

    def parcourir_postes(self):
        """Générateur : tous les noeuds de type 'poste' de ce sous-arbre."""
        if self.est_poste():
            yield self
        for e in self.enfants:
            for p in e.parcourir_postes():
                yield p

    def candidat(self, cand_id):
        for c in self.candidats:
            if c.id == cand_id:
                return c
        return None

    # ---------- vote ----------
    def ajouter_candidat(self, nom):
        c = Candidat(nom)
        self.candidats.append(c)
        self._renumeroter()
        return c

    def retirer_candidat(self, cand_id):
        self.candidats = [c for c in self.candidats if c.id != cand_id]
        self._renumeroter()

    def _renumeroter(self):
        for i, c in enumerate(self.candidats, start=1):
            c.numero = i

    def lancer_vote(self):
        self._renumeroter()
        for c in self.candidats:
            c.votes = 0
        self.vote_lance = True
        self.vote_termine = False
        self.elus = []
        self.egalite_en_attente = []

    def voter(self, cand_id, delta=1):
        c = self.candidat(cand_id)
        if c is None:
            return None
        c.votes = max(0, c.votes + delta)
        return c

    def classement(self):
        return sorted(self.candidats, key=lambda c: (-c.votes, c.numero))

    def voix_exprimees(self):
        return sum(c.votes for c in self.candidats)

    def modifier_bulletins_nuls(self, delta):
        self.bulletins_nuls = max(0, self.bulletins_nuls + delta)

    def modifier_bulletins_blancs(self, delta):
        self.bulletins_blancs = max(0, self.bulletins_blancs + delta)

    def terminer_vote(self):
        """Calcule les élus. Renvoie True si terminé proprement (plus rien
        à faire), False s'il faut une action du secrétaire (égalité à
        départager, ou majorité absolue non atteinte)."""
        if self.majorite_absolue:
            return self._terminer_vote_majorite()
        return self._terminer_vote_normal()

    def _terminer_vote_majorite(self):
        """Mode 'majorité absolue' : un(e) candidat(e) n'est élu(e) que
        s'il/elle obtient strictement plus de 50% des voix exprimées pour
        ce poste."""
        self.vote_lance = False
        self.egalite_en_attente = []
        classement = self.classement()
        total = self.voix_exprimees()
        seuil = total / 2.0
        eligibles = [c for c in classement if total > 0 and c.votes > seuil]
        eligibles = eligibles[: self.nombre_sieges]
        self.elus = [c.id for c in eligibles]
        self.vote_termine = True
        self.majorite_non_atteinte = len(self.elus) < self.nombre_sieges
        return not self.majorite_non_atteinte

    def creer_tour_majorite(self):
        """Crée un 2e tour (majorité non atteinte au 1er tour) : reprend
        les meilleur·es candidat·es restant·es (majorité relative admise
        au tour suivant, comme dans l'usage courant des AG)."""
        places_restantes = self.nombre_sieges - len(self.elus)
        deja_elus = set(self.elus)
        restants = [c for c in self.classement() if c.id not in deja_elus]
        nb_a_garder = max(places_restantes * 2, min(2, len(restants)))
        retenus = restants[:nb_a_garder]

        tour = Noeud(self.nom + " — 2e tour", type_="poste",
                     nombre_sieges=max(1, places_restantes))
        tour.tour = self.tour + 1
        tour.tour_precedent_id = self.id
        tour.majorite_absolue = False
        for c in retenus:
            tour.candidats.append(Candidat(c.nom))
        tour._renumeroter()
        return tour

    def _terminer_vote_normal(self):
        """Mode standard : les nombre_sieges meilleurs scores sont élus,
        avec gestion d'égalité en bas de tableau (départage)."""
        self.vote_lance = False
        self.majorite_non_atteinte = False
        classement = self.classement()
        n = self.nombre_sieges
        if len(classement) <= n:
            self.elus = [c.id for c in classement]
            self.vote_termine = True
            self.egalite_en_attente = []
            return True

        seuil = classement[n - 1].votes
        surs = [c for c in classement if c.votes > seuil]
        a_departager = [c for c in classement if c.votes == seuil]
        places_restantes = n - len(surs)

        if places_restantes <= 0:
            self.elus = [c.id for c in surs[:n]]
            self.vote_termine = True
            self.egalite_en_attente = []
            return True

        if len(a_departager) <= places_restantes:
            self.elus = [c.id for c in surs] + [c.id for c in a_departager]
            self.vote_termine = True
            self.egalite_en_attente = []
            return True

        # égalité réelle : il faut un tour de départage
        self.elus = [c.id for c in surs]
        self.egalite_en_attente = [c.id for c in a_departager]
        self.vote_termine = False
        return False

    def creer_tour_departage(self):
        """Crée (et renvoie) un nouveau poste 'départage' contenant les
        candidats à égalité, pour le nombre de sièges restants."""
        places_restantes = self.nombre_sieges - len(self.elus)
        tour = Noeud(self.nom + " — départage (tour %d)" % (self.tour + 1),
                     type_="poste", nombre_sieges=max(1, places_restantes))
        tour.tour = self.tour + 1
        tour.tour_precedent_id = self.id
        for cand_id in self.egalite_en_attente:
            c = self.candidat(cand_id)
            if c:
                tour.candidats.append(Candidat(c.nom))
        tour._renumeroter()
        return tour

    # ---------- (dé)sérialisation ----------
    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "type": self.type,
            "nombre_sieges": self.nombre_sieges,
            "vote_lance": self.vote_lance,
            "vote_termine": self.vote_termine,
            "elus": self.elus,
            "egalite_en_attente": self.egalite_en_attente,
            "tour": self.tour,
            "tour_precedent_id": self.tour_precedent_id,
            "majorite_absolue": self.majorite_absolue,
            "majorite_non_atteinte": self.majorite_non_atteinte,
            "bulletins_nuls": self.bulletins_nuls,
            "bulletins_blancs": self.bulletins_blancs,
            "candidats": [c.to_dict() for c in self.candidats],
            "enfants": [e.to_dict() for e in self.enfants],
        }

    @staticmethod
    def from_dict(d):
        n = Noeud(d.get("nom", ""), type_=d.get("type", "section"),
                  id=d.get("id"), nombre_sieges=d.get("nombre_sieges", 1))
        n.vote_lance = d.get("vote_lance", False)
        n.vote_termine = d.get("vote_termine", False)
        n.elus = d.get("elus", [])
        n.egalite_en_attente = d.get("egalite_en_attente", [])
        n.tour = d.get("tour", 1)
        n.tour_precedent_id = d.get("tour_precedent_id")
        n.majorite_absolue = d.get("majorite_absolue", False)
        n.majorite_non_atteinte = d.get("majorite_non_atteinte", False)
        n.bulletins_nuls = d.get("bulletins_nuls", 0)
        n.bulletins_blancs = d.get("bulletins_blancs", 0)
        n.candidats = [Candidat.from_dict(c) for c in d.get("candidats", [])]
        n.enfants = [Noeud.from_dict(e) for e in d.get("enfants", [])]
        return n


class Projet:
    def __init__(self, nom="Nouveau projet"):
        self.nom = nom
        self.date_creation = datetime.datetime.now().isoformat(timespec="seconds")
        self.sections = []   # liste de Noeud racine
        self.votants_presents = 0   # quorum : nombre de membres présents/votants

    def trouver(self, node_id):
        for s in self.sections:
            r = s.trouver(node_id)
            if r:
                return r
        return None

    def tous_les_postes(self):
        postes = []
        for s in self.sections:
            postes.extend(list(s.parcourir_postes()))
        return postes

    def rechercher(self, texte):
        """Recherche simple (insensible à la casse) sur les noms de postes
        et de candidats. Renvoie une liste de tuples
        (poste, candidat_ou_None, motif)."""
        texte = (texte or "").strip().lower()
        resultats = []
        if not texte:
            return resultats
        for poste in self.tous_les_postes():
            if texte in poste.nom.lower():
                resultats.append((poste, None, "poste"))
            for c in poste.candidats:
                if texte in c.nom.lower():
                    resultats.append((poste, c, "candidat"))
        return resultats

    def to_dict(self):
        return {
            "nom": self.nom,
            "date_creation": self.date_creation,
            "votants_presents": self.votants_presents,
            "sections": [s.to_dict() for s in self.sections],
        }

    @staticmethod
    def from_dict(d):
        p = Projet(d.get("nom", "Projet"))
        p.date_creation = d.get("date_creation", p.date_creation)
        p.votants_presents = d.get("votants_presents", 0)
        p.sections = [Noeud.from_dict(s) for s in d.get("sections", [])]
        return p
