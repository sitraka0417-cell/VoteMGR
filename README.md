# VoteMGR — Windows (secrétaire unique, double écran)

Application de bureau Windows pour dépouiller à la voix les votes d'une
assemblée générale (élection du bureau exécutif : Président,
Vice-Président, Secrétaire, Trésorier, etc.), avec un écran de contrôle
pour le/la secrétaire et un écran de projection pour l'assemblée.

Portée de la même idée que l'app Android **vaomiera / VoteMGR**, mais
adaptée à un usage différent :

| Android (vaomiera)                         | Windows (ce projet)                              |
|---------------------------------------------|---------------------------------------------------|
| Rôles Admin / Participant, vote en réseau (IP) | Une seule personne (le/la secrétaire), aucun réseau |
| Chaque participant vote sur son téléphone   | Le secrétaire clique **+** à chaque nom annoncé par le bureau de vote (bulletins papier) |
| Un seul écran                                | **2 écrans** : contrôle (secrétaire) + projection (assemblée) |
| —                                             | Numérotation des candidats, gros affichage, pagination, clignotement au vote |

Le reste (sections / sous-sections, gestion des postes du bureau exécutif,
sauvegarde, import de liste de candidats, export PDF) reprend le même
principe que l'app Android.

## Fonctionnalités ajoutées sur demande

- **Thème clair / sombre** : bouton en haut de l'écran secrétaire (🌙/☀),
  change les couleurs de toute la fenêtre de contrôle. L'écran de
  projection reste toujours en thème sombre (lisibilité depuis le fond
  de la salle).
- **Saisie clavier des numéros** : pendant un vote, on peut taper le
  numéro du candidat au clavier (ex: touche « 1 » puis « 2 » en moins de
  2 secondes → vote pour le candidat n°12) au lieu de cliquer sur ＋.
  Fonctionne partout sauf dans un champ de texte (recherche, dialogues).
- **Majorité absolue (optionnelle)** : case à cocher par poste, désactivée
  par défaut. Si activée, un candidat n'est élu que s'il obtient
  strictement plus de 50% des voix exprimées ; sinon un bouton
  « Créer un 2e tour » propose un second tour avec les candidats restants.
- **Annuler la dernière action** (bouton + Ctrl+Z) : annule le dernier
  ＋/－ de vote (clic ou clavier), même si on a changé de poste depuis.
- **Quorum / votants présents** : menu *Projet > Définir le nombre de
  votants présents*, affiche ensuite le taux de participation par poste.
- **Bulletins blancs / nuls** : compteurs dédiés par poste (＋/－ pendant
  le vote), inclus dans l'export PDF, sans affecter le classement des
  candidats.
- **Export PDF par poste** : bouton « 📄 Exporter ce poste en PDF » en plus
  de l'export global (menu Projet).

## Comment ça marche

- **Écran 1 (secrétaire)** : arbre des sections/postes à gauche, panneau
  du poste sélectionné à droite (liste des candidats numérotés, boutons
  **＋ / －** actifs seulement pendant un vote lancé). C'est le
  secrétaire qui lance le vote, clique + à chaque bulletin annoncé, clôt
  le vote, et décide ce qui est projeté sur l'écran 2.
- **Réglage de l'écran de projection** : menu *Écran de projection >
  Configurer l'écran (dupliqué / étendu)...* — liste les écrans détectés
  (avec un bouton pour les redétecter si vous changez le mode Windows,
  Touche Windows + P, sans redémarrer l'appli), et laisse choisir entre
  *Automatique*, *Dupliqué* (le vidéoprojecteur recopie l'écran
  principal) ou *Étendu* (choix manuel de l'écran).
- **Écran 2 (projection)** :
  - Aucun vote en cours → logo (`assets/logo.png`) + texte
    « VoteMGR by Sitraka Nambinintsoa ».
  - Vote en cours → grille des candidats (2 à 4 colonnes selon le
    nombre), numéro + nom + score en très grande taille, pagination
    automatique toutes les 10 s si trop de candidats pour tenir sur un
    écran. Le candidat qui vient de recevoir un point clignote 2-3 s.
  - Fin de vote → sur confirmation du secrétaire, affichage des élu(e)s
    (poste par poste, ou bureau complet).
  - Les boutons **+ / -** ne s'affichent jamais sur l'écran 2.

Une **recherche** en haut de l'écran 1 permet de retrouver un poste par
son nom, ou un candidat par son nom (et de voir sur quel poste il/elle
se trouve).

## Structure du projet

```
votemgr/
  main.py                 point d'entrée (python main.py)
  .github/workflows/
    build-windows.yml      compilation automatique .exe via GitHub Actions
  app/
    models.py              arbre sections/postes/candidats, logique de vote et départage
    storage.py              sauvegarde/chargement de projet (.vmgr = JSON), import CSV/JSON, autosave
    pdf_export.py           export des résultats en PDF (reportlab)
    monitors.py              détection des écrans Windows (pour placer l'écran 2)
    secretary.py            écran 1 (fenêtre de contrôle)
    projection.py            écran 2 (fenêtre de projection)
  assets/
    logo.png                 à ajouter (voir assets/LISEZ-MOI.txt)
  exemples/
    exemple_projet.vmgr      petit projet de démo, prêt à ouvrir (Fichier > Ouvrir)
  installer/
    build.bat                 compile l'exécutable Windows (PyInstaller)
    votemgr.iss                script Inno Setup pour créer VoteMGR-Setup.exe
  requirements.txt
```

Format de sauvegarde : fichiers `.vmgr` (du JSON lisible). Une sauvegarde
automatique est écrite dans `%USERPROFILE%\VoteMGR\` pendant l'utilisation
(protection en cas de coupure de courant / fermeture accidentelle pendant
l'assemblée), avec un historique horodaté dans
`%USERPROFILE%\VoteMGR\sauvegardes_auto\`.

## Lancer en développement

Nécessite Python 3.10+ (avec Tkinter, inclus par défaut sur Windows).

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Ouvrez ensuite `exemples\exemple_projet.vmgr` (menu Fichier > Ouvrir)
pour un premier essai rapide.

## Compilation automatique via GitHub Actions

Le workflow `.github/workflows/build-windows.yml` est inclus : à chaque
`git push` sur `main` (ou manuellement depuis l'onglet **Actions >
Build VoteMGR (Windows) > Run workflow**), GitHub compile automatiquement
l'application sur une machine Windows et vous donne :

- **VoteMGR-portable-windows** : le dossier `VoteMGR.exe` prêt à l'emploi
  (pas besoin d'installateur, juste dézipper et lancer).
- **VoteMGR-Setup** : l'installateur `.exe` (si Inno Setup a pu être
  installé sur le runner — sinon seul le portable est disponible, ce
  n'est pas bloquant).

Pour récupérer le résultat : onglet **Actions** du dépôt → cliquer sur
le run le plus récent → section **Artifacts** en bas de page.

Si l'onglet Actions affiche « Get started with GitHub Actions » au lieu
de lancer une compilation, c'est que le fichier
`.github/workflows/build-windows.yml` n'est pas encore poussé sur GitHub
(vérifiez qu'il est bien présent dans votre dépôt, dossier `.github/workflows/`).

## Compiler sans connexion Internet

Une fois les paquets Python présents sur la machine, PyInstaller compile
entièrement en local — aucune donnée n'est envoyée sur le réseau pendant
la compilation elle-même. Procédure pour pouvoir compiler ensuite sur un
PC totalement hors-ligne (salle sans Wi-Fi le jour de l'AG, par exemple) :

**Une seule fois, sur un PC connecté à Internet :**

1. Lancez `installer\preparer_hors_ligne.bat` (double-clic, ou depuis une
   invite de commandes) — télécharge `reportlab`, `pyinstaller` et leurs
   dépendances dans un dossier `vendor\` à l'intérieur du projet.
2. Pensez aussi, une seule fois également :
   - à installer Python (télécharger l'installateur `.exe` une fois
     depuis python.org, il fonctionne ensuite hors-ligne sur d'autres PC
     avec le même installateur) ;
   - à installer [Inno Setup](https://jrsoftware.org/isinfo.php) si vous
     voulez aussi générer `VoteMGR-Setup.exe` (l'installateur lui-même
     n'a pas besoin d'Internet après son installation).

**Ensuite, sur n'importe quel PC Windows, avec ou sans Internet :**

- Copiez le dossier `votemgr\` complet (avec le sous-dossier `vendor\`) —
  clé USB, disque externe, peu importe.
- Lancez `installer\build.bat` : il détecte automatiquement `vendor\` et
  installe les dépendances **sans toucher au réseau**, puis compile
  `VoteMGR.exe` normalement.

Le dossier `vendor\` est volontairement exclu de Git (`.gitignore`,
car assez lourd) — gardez-le en local ou sur votre clé USB, pas besoin
de le pousser sur GitHub.

À noter : GitHub Actions (section précédente) fonctionne à l'inverse —
c'est un service *dans le cloud*, donc il a par nature besoin d'Internet ;
il ne remplace pas une compilation hors-ligne, c'est une alternative pour
quand vous êtes connecté et ne voulez pas installer Python vous-même.

## Compiler en .exe puis créer l'installateur Windows (en local)

1. **Placez votre logo** : copiez votre `logo.png` dans `assets/`.
2. **Compilez l'exécutable** :
   ```bat
   installer\build.bat
   ```
   → produit `dist\VoteMGR\VoteMGR.exe` (dossier complet, portable).
3. **Créez l'installateur** (optionnel mais demandé) :
   - Installez [Inno Setup](https://jrsoftware.org/isinfo.php) (gratuit).
   - Ouvrez `installer\votemgr.iss` avec « Inno Setup Compiler » et cliquez
     **Compile** (ou en ligne de commande : `ISCC installer\votemgr.iss`).
   - Résultat : `installer\Output\VoteMGR-Setup.exe`, un installateur
     classique (icône Bureau, menu Démarrer, désinstalleur).

## Publier sur GitHub

```bash
git init
git add .
git commit -m "VoteMGR Windows — v1"
git branch -M main
git remote add origin <URL-de-votre-dépôt>
git push -u origin main
```

Le `.gitignore` fourni exclut déjà `dist/`, `build/`, `installer/Output/`
et les fichiers compilés — seul le code source part sur GitHub. Pensez à
créer une **Release** GitHub et à y attacher `VoteMGR-Setup.exe` (généré
en local, pas à commiter directement : il est assez lourd).

## Suggestions pour améliorer l'idée (au-delà de ce qui est déjà inclus)

- **Deux moniteurs non détectés** : sur certains PC/projecteurs (mode
  "dupliquer" au lieu de "étendre"), un seul écran est vu par Windows —
  le menu *Écran de projection > Basculer plein écran* permet de forcer
  l'affichage même dans ce cas, mais autant le rappeler à l'utilisateur
  avant l'AG (tester le double écran la veille).
- **Impression directe** du PDF généré, sans repasser par un lecteur PDF
  externe (ajout possible avec `win32print` si besoin plus tard).
- **Historique des tours** consultable dans l'interface (actuellement les
  tours de départage/2e tour apparaissent comme des postes séparés dans
  l'arbre, ce qui les garde traçables, mais un onglet dédié « historique »
  pourrait les regrouper visuellement).

## Licence / crédit

VoteMGR — by Sitraka Nambinintsoa.
