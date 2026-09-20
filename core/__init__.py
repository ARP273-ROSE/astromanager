from pathlib import Path as _Path


def _lire_version() -> str:
    """La version vit dans le fichier VERSION, a la racine : une seule source.

    Ecrire le numero a deux endroits finit toujours par les faire diverger, et
    une application qui se croit en retard sur elle-meme propose une mise a
    jour a chaque demarrage, sans fin. Le fichier VERSION est celui que le
    workflow de publication compare au tag.

    Illisible : chaine vide, et la verification des mises a jour s'abstient
    plutot que de comparer n'importe quoi.
    """
    for base in (_Path(__file__).resolve().parent.parent,
                 _Path(__file__).resolve().parent):
        chemin = base / 'VERSION'
        try:
            texte = chemin.read_text(encoding='utf-8').strip()
            if texte:
                return texte
        except OSError:
            continue
    return ''


__version__ = _lire_version()
