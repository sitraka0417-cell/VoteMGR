# -*- coding: utf-8 -*-
"""
storage.py — Sauvegarde/chargement de projet (.vmgr = JSON) + import de
listes de candidats (CSV ou JSON) + sauvegarde automatique.
"""

import json
import os
import csv
import datetime

from .models import Projet

DOSSIER_DONNEES = os.path.join(os.path.expanduser("~"), "VoteMGR")
DOSSIER_SAUVEGARDES = os.path.join(DOSSIER_DONNEES, "sauvegardes_auto")
FICHIER_AUTOSAVE = os.path.join(DOSSIER_DONNEES, "autosave.vmgr")


def assurer_dossiers():
    os.makedirs(DOSSIER_DONNEES, exist_ok=True)
    os.makedirs(DOSSIER_SAUVEGARDES, exist_ok=True)


def enregistrer_projet(projet: Projet, chemin: str):
    assurer_dossiers()
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(projet.to_dict(), f, ensure_ascii=False, indent=2)


def charger_projet(chemin: str) -> Projet:
    with open(chemin, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Projet.from_dict(data)


def sauvegarde_auto(projet: Projet):
    """Écrit l'état courant dans autosave.vmgr ET garde un historique
    horodaté dans sauvegardes_auto/ (utile en cas de coupure pendant
    l'assemblée)."""
    assurer_dossiers()
    try:
        enregistrer_projet(projet, FICHIER_AUTOSAVE)
        horodatage = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        chemin_histo = os.path.join(
            DOSSIER_SAUVEGARDES, "backup_%s.vmgr" % horodatage)
        enregistrer_projet(projet, chemin_histo)
        nettoyer_vieilles_sauvegardes()
    except Exception:
        # une sauvegarde automatique ne doit jamais interrompre le vote
        pass


def nettoyer_vieilles_sauvegardes(garder=40):
    """Ne garde que les N sauvegardes automatiques les plus récentes."""
    try:
        fichiers = sorted(
            (f for f in os.listdir(DOSSIER_SAUVEGARDES) if f.endswith(".vmgr")),
            reverse=True,
        )
        for f in fichiers[garder:]:
            os.remove(os.path.join(DOSSIER_SAUVEGARDES, f))
    except Exception:
        pass


def autosave_rapide(projet: Projet):
    """Écrit juste autosave.vmgr (rapide, appelé à chaque +/- de vote),
    sans garder d'historique horodaté."""
    assurer_dossiers()
    try:
        enregistrer_projet(projet, FICHIER_AUTOSAVE)
    except Exception:
        pass


def importer_candidats(chemin: str):
    """Importe une liste de noms de candidats depuis un fichier CSV ou JSON.

    CSV attendu : soit une colonne 'nom', soit simplement un nom par ligne.
    JSON attendu : soit ["Nom 1", "Nom 2", ...],
                   soit [{"nom": "Nom 1"}, {"nom": "Nom 2"}, ...].
    Renvoie une liste de chaînes (noms), nettoyée des doublons/vides,
    en conservant l'ordre.
    """
    ext = os.path.splitext(chemin)[1].lower()
    noms = []

    if ext == ".json":
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if isinstance(item, str):
                noms.append(item)
            elif isinstance(item, dict):
                noms.append(item.get("nom") or item.get("name") or "")
    else:
        with open(chemin, "r", encoding="utf-8-sig", newline="") as f:
            contenu = f.read()
        f_lignes = contenu.splitlines()
        # essaie de détecter un CSV avec en-tête "nom"
        try:
            reader = csv.DictReader(f_lignes)
            champs = [c.strip().lower() for c in (reader.fieldnames or [])]
            if "nom" in champs or "name" in champs:
                cle = "nom" if "nom" in champs else "name"
                # DictReader garde la casse d'origine des clés -> retrouver la vraie clé
                vraie_cle = reader.fieldnames[champs.index(cle)]
                for row in reader:
                    noms.append((row.get(vraie_cle) or "").strip())
            else:
                raise ValueError("pas d'en-tête reconnu")
        except Exception:
            # simple liste, une valeur par ligne (1re colonne si virgules)
            for ligne in f_lignes:
                ligne = ligne.strip()
                if not ligne:
                    continue
                premiere_colonne = ligne.split(",")[0].strip()
                if premiere_colonne.lower() in ("nom", "name"):
                    continue
                noms.append(premiere_colonne)

    # nettoyage : enlève vides et doublons en gardant l'ordre
    vus = set()
    resultat = []
    for n in noms:
        n = (n or "").strip()
        if n and n.lower() not in vus:
            vus.add(n.lower())
            resultat.append(n)
    return resultat
