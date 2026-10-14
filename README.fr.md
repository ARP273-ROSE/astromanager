# AstroManager

*English version: [README.md](README.md).*

**AstroManager** gère et analyse les fichiers d'astrophotographie (FITS, XISF,
FITS.FZ) : analyse de dossiers entiers, qualité des poses, compression, édition
d'en-têtes en masse, gestion des flats, suivi des cibles, carte du ciel,
calendrier des nuits, statistiques N.I.N.A., export WBPP pour PixInsight,
optimisation du stockage. L'interface est en français et en anglais : la langue
du système au premier lancement, puis celle choisie dans les réglages.

Le détail des fonctions est dans le [README anglais](README.md) et dans le
manuel [`USER_MANUAL_FR.pdf`](USER_MANUAL_FR.pdf).

## Télécharger

Paquets prêts à l'emploi, Python compris, sur la
[page des versions](https://github.com/ARP273-ROSE/astromanager/releases/latest) :

| Système | Fichier |
|---|---|
| Windows | `AstroManager-Setup.exe` — lien permanent : [dernier installeur](https://github.com/ARP273-ROSE/astromanager/releases/latest/download/AstroManager-Setup.exe) |
| macOS (Apple Silicon / Intel) | `AstroManager-X.Y.Z-macos-arm64.dmg` / `-macos-x86_64.dmg` |
| Linux (x86_64 / ARM64) | `AstroManager-X.Y.Z-linux-x86_64.tar.gz` / `-linux-arm64.tar.gz`, puis `./installer.sh` |

Aucun droit d'administrateur n'est demandé. Les réglages, la base et les
rapports vivent hors du dossier d'installation (`%APPDATA%\AstroManager` sous
Windows, `~/.astromanager` ailleurs) : ils survivent aux mises à jour.

- **Windows** peut afficher « Windows a protégé votre ordinateur » au premier
  lancement (installeur non signé) : *Informations complémentaires*, puis
  *Exécuter quand même*.
- **macOS** : glisser l'application dans Applications, puis la première fois
  *clic droit > Ouvrir*.
- **Linux** : décompresser l'archive et lancer `./installer.sh` (installation
  dans `~/.local/share`, entrée de menu, sans sudo).

## Mises à jour

L'application installée cherche une nouvelle version au démarrage (réglable
dans *Outils > Réglages*) et sur demande (*Aide > Vérifier les mises à jour*).
Elle ne télécharge que la petite archive applicative, vérifie qu'elle vient de
GitHub, la déballe et redémarre, sur les trois systèmes. Les notes de version
s'affichent dans la langue de l'interface.

## Rapports de problème

Au premier lancement, l'application demande l'accord pour envoyer
automatiquement un court rapport technique en cas de plantage ou de gel
(version, système, trace de l'erreur ; aucun de vos fichiers). Ce choix se
modifie dans le menu *Aide*, où *Signaler un problème* permet aussi d'écrire
un signalement.

## Depuis les sources

```bash
git clone https://github.com/ARP273-ROSE/astromanager.git
cd astromanager
pip install -r requirements.txt
python astromanager.py            # interface
python astromanager.py --help     # analyse en ligne de commande
```

Tests : `python -m pytest -q tests/` (interface : sous `xvfb-run` sous Linux).

## Licence

MIT — voir [LICENSE](LICENSE).
