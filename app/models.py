# -*- coding: utf-8 -*-
"""
models.py — Modèle de données de VoteMGR (version Windows / secrétaire unique).

Fidèle à l'app Android d'origine (vaomiera) : il n'y a qu'UN seul type de
noeud. Chaque noeud peut, en même temps :
  - contenir des sous-noeuds (sections / sous-sections), ET
  - être directement votable (avoir des candidats, un vote en cours, etc.)
Il n'y a donc pas de distinction stricte "section" / "poste" côté modèle ;
`type` ne sert plus qu'à l'icône/l'intitulé par défaut dans l'arbre.

Tout l'état (votes en cours, numéros, élus, désignations, rôles, tours de
départage) vit dans ces objets ; il n'y a pas de notion admin/participant
ni de réseau : un seul secrétaire pilote l'écran 1 (contrôle) et pousse
l'affichage vers l'écran 2 (projection).
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
    """Un noeud de l'arbre : peut contenir des enfants (sections/sous-
    sections) ET/OU être lui-même votable (avoir des candidats), tout comme
    dans l'app Android d'origine — il n'y a qu'un seul type de noeud."""

    def __init__(self, nom, type_="section", id=None, nombre_sieges=1):
        self.id = id or nouvel_id()
        self.nom = nom
        self.type = type_               # indicatif seulement ("section" | "poste")
        self.enfants = []
        self.candidats = []
        self.nombre_sieges = nombre_sieges
        self.vote_lance = False
        self.vote_termine = False
        self.elus = []                  # liste d'ids Candidat élus (ou désignés)
        self.egalite_en_attente = []    # ids à égalité, en attente de départage
        self.tour = 1                   # numéro de tour (1 = premier tour)
        self.tour_precedent_id = None   # id du poste dont ce poste est le tour suivant
        self.majorite_absolue = False   # option : élu(e) seulement si >50% des voix
        self.majorite_non_atteinte = False  # vrai si majorité absolue demandée mais pas atteinte
        self.bulletins_nuls = 0
        self.bulletins_blancs = 0

        # ---- désignation directe (sans vote), comme l'app Android ----
        self.designes = []              # ids Candidat désignés sans vote (statut "designe")
        self.est_designation = False    # True si self.elus vient d'une désignation, pas d'un vote

        # ---- mode "rôles" (un vote, plusieurs postes classés), comme l'app Android ----
        self.mode_roles = False
        self.roles = []                 # [{"nom": "Président", "nombre": 1}, ...]

    # ---------- helpers arbre ----------
    def est_poste(self):
        return self.type == "poste"

    def est_votable(self):
        """Un noeud est 'votable' dès qu'il porte des candidats, qu'un vote
        y a déjà eu lieu/est en cours, ou qu'il a été explicitement créé
        comme 'poste' — exactement comme dans l'app Android, où tout noeud
        peut recevoir des candidats, section ou pas."""
        return bool(self.candidats) or self.est_poste() or self.vote_lance \
            or self.vote_termine or self.statut() != "attente"

    def statut(self):
        """Équivalent du champ 'statut' de l'app Android : 'attente' |
        'ouvert' | 'ferme' | 'designe'."""
        if self.est_designation:
            return "designe"
        if self.vote_lance:
            return "ouvert"
        if self.vote_termine:
            return "ferme"
        return "attente"

    def trouver(self, node_id):
        if self.id == node_id:
            return self
        for e in self.enfants:
            r = e.trouver(node_id)
            if r:
                return r
        return None

    def parcourir_postes(self):
        """Générateur : tous les noeuds votables de ce sous-arbre (y
        compris ce noeud lui-même s'il est votable)."""
        if self.est_votable():
            yield self
        for e in self.enfants:
            for p in e.parcourir_postes():
                yield p

    def candidat(self, cand_id):
        for c in self.candidats:
            if c.id == cand_id:
                return c
        return None

    # ---------- candidats ----------
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

    # ---------- validations avant d'ouvrir un vote (comme l'app Android) ----------
    def peut_lancer_vote(self):
        """Renvoie (ok: bool, message_erreur: str ou None)."""
        if not self.candidats:
            return False, "Ajoutez au moins un candidat avant de lancer le vote."
        if self.nombre_sieges <= 0:
            return False, "Le nombre de sièges à pourvoir doit être d'au moins 1."
        if self.nombre_sieges > len(self.candidats):
            return False, ("Le nombre de sièges à pourvoir (%d) ne peut pas dépasser "
                            "le nombre de candidats (%d)." % (self.nombre_sieges, len(self.candidats)))
        return True, None

    # ---------- vote ----------
    def lancer_vote(self):
        self._renumeroter()
        for c in self.candidats:
            c.votes = 0
        self.vote_lance = True
        self.vote_termine = False
        self.est_designation = False
        self.designes = []
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
        if self.mode_roles and self.roles:
            return self._terminer_vote_roles()
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
        return self._nouveau_tour(retenus, places_restantes, "2e tour")

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

    def _terminer_vote_roles(self):
        """Mode 'rôles' : le même vote est utilisé pour pourvoir plusieurs
        postes classés (ex: Président, puis Vice-Président...), attribués
        par tranches selon le score, comme resoudreRoles() côté Android."""
        self.vote_lance = False
        self.egalite_en_attente = []
        affectation = self.resoudre_roles()
        if affectation is None:
            # égalité non tranchée sur une tranche : on calcule quand même
            # les clairement-élus pour savoir où en est le départage global
            self.vote_termine = False
            return False
        self.elus = [cand_id for cand_id, _role in affectation]
        self.vote_termine = True
        return True

    def resoudre_roles(self):
        """Classe les candidats par score puis les attribue par tranches
        aux rôles définis dans self.roles (dans l'ordre). Renvoie une liste
        de tuples (candidat_id, nom_role), ou None si une tranche est à
        égalité (il faut alors un départage avant de pouvoir conclure)."""
        if not self.roles:
            return None
        classement = self.classement()
        resultat = []
        index = 0
        for role in self.roles:
            n = role.get("nombre", 0)
            dispo = classement[index:]
            if n <= 0 or not dispo:
                continue
            if n > len(dispo):
                n = len(dispo)
            seuil = dispo[n - 1].votes
            surs = [c for c in dispo if c.votes > seuil]
            a_departager = [c for c in dispo if c.votes == seuil]
            places_restantes = n - len(surs)
            if places_restantes > 0 and len(a_departager) > places_restantes:
                return None  # égalité non tranchée sur cette tranche
            retenus = surs + a_departager[:places_restantes] if places_restantes > 0 else surs
            for c in retenus:
                resultat.append((c.id, role.get("nom", "")))
            index += len(retenus)
        return resultat

    def designer_sans_vote(self, cand_ids):
        """Désigne directement un ou plusieurs candidats à ce poste, sans
        organiser de vote (équivalent du statut 'designe' côté Android)."""
        self.vote_lance = False
        self.vote_termine = True
        self.est_designation = True
        self.designes = list(cand_ids)
        self.elus = list(cand_ids)
        self.egalite_en_attente = []
        self.majorite_non_atteinte = False

    def refaire_le_vote(self):
        """« Modifier / Refaire le vote » : remet ce poste à l'état
        'attente' (comme un vote qui n'a jamais eu lieu), mais conserve la
        liste des candidats et les réglages (sièges, majorité, rôles) —
        exactement le comportement de l'app Android."""
        self.vote_lance = False
        self.vote_termine = False
        self.est_designation = False
        self.designes = []
        self.elus = []
        self.egalite_en_attente = []
        self.majorite_non_atteinte = False
        self.bulletins_blancs = 0
        self.bulletins_nuls = 0
        for c in self.candidats:
            c.votes = 0

    def creer_tour_departage(self):
        """Crée (et renvoie) un nouveau poste 'départage' contenant les
        candidats à égalité, pour le nombre de sièges restants
        (détection automatique)."""
        places_restantes = self.nombre_sieges - len(self.elus)
        cands = [self.candidat(cid) for cid in self.egalite_en_attente]
        cands = [c for c in cands if c]
        return self._nouveau_tour(cands, places_restantes, "départage (tour %d)" % (self.tour + 1))

    def creer_tour_manuel(self, cand_ids, nombre_sieges=None):
        """« Créer un second tour (ex-æquo) » — choix manuel : le
        secrétaire sélectionne lui-même N'IMPORTE LESQUELS des candidats
        d'origine pour un nouveau tour (pas forcément ceux à égalité),
        comme le bouton équivalent de l'app Android."""
        cands = [self.candidat(cid) for cid in cand_ids]
        cands = [c for c in cands if c]
        places = nombre_sieges if nombre_sieges else max(1, self.nombre_sieges - len(self.elus))
        return self._nouveau_tour(cands, places, "2e tour (choix manuel)")

    def _nouveau_tour(self, candidats_source, nombre_sieges, libelle):
        tour = Noeud(self.nom + " — " + libelle, type_="poste",
                     nombre_sieges=max(1, nombre_sieges))
        tour.tour = self.tour + 1
        tour.tour_precedent_id = self.id
        for c in candidats_source:
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
            "designes": self.designes,
            "est_designation": self.est_designation,
            "mode_roles": self.mode_roles,
            "roles": self.roles,
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
        n.designes = d.get("designes", [])
        n.est_designation = d.get("est_designation", False)
        n.mode_roles = d.get("mode_roles", False)
        n.roles = d.get("roles", [])
        n.candidats = [Candidat.from_dict(c) for c in d.get("candidats", [])]
        n.enfants = [Noeud.from_dict(e) for e in d.get("enfants", [])]
        return n


class Projet:
    def __init__(self, nom="Nouveau projet"):
        self.nom = nom
        self.date_creation = datetime.datetime.now().isoformat(timespec="seconds")
        self.sections = []   # liste de Noeud racine
        self.votants_presents = 0   # quorum simple : nombre de membres présents/votants
        self.liste_membres = []     # liste globale réutilisable de noms (comme "membres_courant" côté Android)
        self.sessions = []          # [{"label": "...", "presents": ["nom1", ...]}, ...]

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

    def tous_les_noeuds(self):
        """Tous les noeuds de l'arbre, votables ou non (pour parcourir
        toute la hiérarchie, ex: ajouter une sous-section)."""
        resultat = []
        def parcourir(n):
            resultat.append(n)
            for e in n.enfants:
                parcourir(e)
        for s in self.sections:
            parcourir(s)
        return resultat

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

    # ---------- liste globale de membres (réutilisable pour tous les votes) ----------
    def ajouter_membres(self, noms):
        """Ajoute des noms à la liste globale de membres, en ignorant les
        doublons (insensible à la casse/espaces) et en gardant l'ordre."""
        vus = {m.strip().lower() for m in self.liste_membres}
        ajoutes = 0
        for n in noms:
            n = (n or "").strip()
            if n and n.lower() not in vus:
                self.liste_membres.append(n)
                vus.add(n.lower())
                ajoutes += 1
        return ajoutes

    # ---------- vote ouvert unique (comme sousSectionOuverte côté Android) ----------
    def poste_vote_ouvert(self):
        """Renvoie le poste actuellement en vote (vote_lance=True) s'il y
        en a un, sinon None. L'app Android n'autorise qu'un seul vote
        ouvert à la fois dans tout le projet."""
        for p in self.tous_les_postes():
            if p.vote_lance:
                return p
        return None

    def peut_ouvrir_vote(self, noeud):
        """Renvoie (ok, message_erreur_ou_None)."""
        ouvert = self.poste_vote_ouvert()
        if ouvert is not None and ouvert.id != noeud.id:
            return False, ("Un vote est déjà en cours pour « %s ». "
                            "Fermez-le d'abord avant d'en ouvrir un autre." % ouvert.nom)
        return noeud.peut_lancer_vote()

    # ---------- badge "déjà élu ailleurs" ----------
    def calculer_elus_global(self):
        """Renvoie un dict {nom_en_minuscules: [liste des postes où cette
        personne est élue ou désignée]}, pour afficher un badge ⭐ partout
        où on choisit un candidat (comme calculerElusGlobal() côté
        Android)."""
        resultat = {}
        for poste in self.tous_les_postes():
            if not (poste.vote_termine and poste.elus):
                continue
            for cid in poste.elus:
                c = poste.candidat(cid)
                if not c:
                    continue
                cle = c.nom.strip().lower()
                resultat.setdefault(cle, []).append(poste.nom)
        return resultat

    # ---------- sessions / présence ----------
    def ajouter_session(self, label, presents=None):
        self.sessions.append({"label": label, "presents": list(presents or [])})

    def retirer_session(self, index):
        if 0 <= index < len(self.sessions):
            del self.sessions[index]

    def to_dict(self):
        return {
            "nom": self.nom,
            "date_creation": self.date_creation,
            "votants_presents": self.votants_presents,
            "liste_membres": self.liste_membres,
            "sessions": self.sessions,
            "sections": [s.to_dict() for s in self.sections],
        }

    @staticmethod
    def from_dict(d):
        p = Projet(d.get("nom", "Projet"))
        p.date_creation = d.get("date_creation", p.date_creation)
        p.votants_presents = d.get("votants_presents", 0)
        p.liste_membres = d.get("liste_membres", [])
        p.sessions = d.get("sessions", [])
        p.sections = [Noeud.from_dict(s) for s in d.get("sections", [])]
        return p
