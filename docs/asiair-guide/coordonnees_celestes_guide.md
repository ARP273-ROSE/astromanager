# Les coordonnees celestes expliquees simplement

*Guide pour debutants en astronomie, proprietaires d'une monture equatoriale GoTo (ZWO AM3N)*

---

## Table des matieres

1. [La sphere celeste : le ciel comme un grand dome](#1-la-sphere-celeste--le-ciel-comme-un-grand-dome)
2. [RA et DEC : la longitude et la latitude du ciel](#2-ra-et-dec--la-longitude-et-la-latitude-du-ciel)
3. [Alt et Az : le systeme "local" du ciel](#3-alt-et-az--le-systeme-local-du-ciel)
4. [Pourquoi votre monture equatoriale utilise RA/DEC](#4-pourquoi-votre-monture-equatoriale-utilise-radec)
5. [La mise en station (alignement polaire)](#5-la-mise-en-station-alignement-polaire)
6. [Comment votre monture GoTo trouve les objets](#6-comment-votre-monture-goto-trouve-les-objets)
7. [Le meridien et le retournement de monture](#7-le-meridien-et-le-retournement-de-monture)
8. [Comprendre les erreurs de guidage : RA vs DEC](#8-comprendre-les-erreurs-de-guidage--ra-vs-dec)
9. [Resume avec analogies](#9-resume-avec-analogies)

---

## 1. La sphere celeste : le ciel comme un grand dome

### L'idee de base

Imaginez que vous etes a l'interieur d'une immense boule transparente. Toutes les etoiles, les galaxies et les nebuleuses sont "collees" a la surface interieure de cette boule. C'est ce qu'on appelle la **sphere celeste**.

Bien sur, en realite, les etoiles sont a des distances enormement differentes les unes des autres. Mais depuis la Terre, on a l'impression qu'elles sont toutes sur un meme "dome" au-dessus de nos tetes. Les astronomes ont decide d'utiliser cette illusion a leur avantage : plutot que de se soucier des distances, ils ont cree un systeme pour decrire **dans quelle direction** on regarde.

### Analogie simple

> Pensez a un planetarium. Vous etes assis au centre, et toutes les etoiles sont projetees sur le dome au-dessus de vous. La sphere celeste, c'est exactement ce dome -- sauf qu'il vous entoure completement, y compris sous vos pieds (la partie que vous ne voyez pas car le sol la cache).

La Terre tourne sur elle-meme a l'interieur de cette sphere. C'est pour cela que les etoiles semblent se "deplacer" d'est en ouest au cours de la nuit : en realite, c'est nous qui tournons, pas elles.

---

## 2. RA et DEC : la longitude et la latitude du ciel

### Le systeme de coordonnees equatoriales

Pour reperer un endroit sur Terre, on utilise la **latitude** (nord-sud) et la **longitude** (est-ouest). Les astronomes ont fait exactement la meme chose pour le ciel, en projetant le systeme de la Terre sur la sphere celeste :

| Sur Terre | Sur la sphere celeste | Role |
|-----------|----------------------|------|
| Latitude | **Declinaison (DEC)** | Mesure nord-sud |
| Longitude | **Ascension Droite (RA)** | Mesure est-ouest |
| Equateur | **Equateur celeste** | Ligne de reference nord-sud |
| Poles Nord/Sud | **Poles celestes Nord/Sud** | Points autour desquels le ciel semble tourner |

### La Declinaison (DEC)

La declinaison fonctionne exactement comme la latitude terrestre :

- **DEC = 0 degres** : l'objet se trouve sur l'equateur celeste (l'extension de l'equateur terrestre dans le ciel).
- **DEC = +90 degres** : c'est le pole Nord celeste (le point exact autour duquel toutes les etoiles de l'hemisphere nord semblent tourner -- tres pres de l'etoile Polaire).
- **DEC = -90 degres** : c'est le pole Sud celeste.
- **DEC = +45 degres** : l'objet est a mi-chemin entre l'equateur celeste et le pole Nord celeste.

La declinaison s'exprime en **degres (°), minutes d'arc (') et secondes d'arc ('')**. Par exemple : DEC = +41° 16' 09''.

> **Analogie :** Si vous etes a Paris (latitude ~49° Nord), un objet a DEC +49° passera exactement a la verticale au-dessus de votre tete au cours de la nuit.

### L'Ascension Droite (RA) -- et pourquoi c'est en heures

Voila la partie qui surprend les debutants : l'ascension droite ne s'exprime **pas en degres**, mais en **heures, minutes et secondes de temps** (h, m, s).

**Pourquoi ?** Parce que la Terre fait un tour complet (360 degres) en 24 heures. Le ciel "defile" donc devant nous comme une horloge :

- 24 heures de RA = 360 degres (un tour complet)
- 1 heure de RA = 15 degres
- 1 minute de RA = 15 minutes d'arc
- 1 seconde de RA = 15 secondes d'arc

Un objet a RA = 6h 00m 00s est situe a un quart du tour (90 degres) d'un objet a RA = 0h 00m 00s.

> **Analogie de l'horloge :** Imaginez une immense horloge dont le cadran serait la sphere celeste. Les "heures" de RA sont des tranches du ciel qui defilent les unes apres les autres au fur et a mesure que la Terre tourne. Si une etoile a RA = 12h passe dans votre telescope en ce moment, l'etoile a RA = 13h y arrivera environ une heure plus tard.

**Exemple concret :** La nebuleuse d'Orion (M42) a pour coordonnees :
- RA = 5h 35m 17s
- DEC = -5° 23' 28''

Cela signifie qu'elle se trouve un peu au sud de l'equateur celeste (-5 degres) et dans la "tranche horaire" 5h35 du ciel.

### Pourquoi ce systeme est si pratique

L'enorme avantage de RA/DEC : **les coordonnees d'un objet ne changent quasiment pas.** La nebuleuse d'Orion sera toujours a RA 5h35m, DEC -5°23', que vous observiez depuis Paris, depuis Tokyo, a 21h ou a 3h du matin. C'est une "adresse permanente" dans le ciel.

*(En realite, les coordonnees changent tres lentement sur des decennies a cause d'un phenomene appele precession, mais pour une nuit d'observation, c'est parfaitement fixe.)*

---

## 3. Alt et Az : le systeme "local" du ciel

### Altitude et Azimut

Il existe un deuxieme systeme, plus intuitif mais moins pratique pour l'astronomie : le systeme **Alt-Az** (Altitude-Azimut), aussi appele systeme **horizontal** :

- **Altitude (Alt)** : a quelle hauteur se trouve l'objet au-dessus de l'horizon.
  - 0° = sur l'horizon
  - 90° = pile au-dessus de votre tete (le **zenith**)
  - Les valeurs negatives = sous l'horizon (invisible)

- **Azimut (Az)** : dans quelle direction horizontale se trouve l'objet.
  - 0° = Nord
  - 90° = Est
  - 180° = Sud
  - 270° = Ouest

### Analogie simple

> Vous etes debout dans un champ. Quelqu'un vous demande "ou est cet avion dans le ciel ?". Vous repondez naturellement : "regarde vers le sud-est (azimut ~135°), a environ 45 degres au-dessus de l'horizon (altitude 45°)". C'est exactement le systeme Alt-Az.

### Le gros probleme : ca change tout le temps

Comme la Terre tourne, les etoiles semblent se deplacer continuellement dans le ciel. En consequence, l'altitude et l'azimut d'un objet **changent a chaque seconde**.

De plus, deux personnes situees a des endroits differents ne verront pas le meme objet au meme Alt-Az au meme moment.

**Exemple :** La nebuleuse d'Orion aura un Alt-Az completement different si vous regardez depuis Paris ou depuis Marseille, et son Alt-Az change constamment au cours de la nuit a mesure que la Terre tourne.

### Alors, pourquoi Alt-Az existe-t-il ?

Ce systeme est utile pour decrire rapidement ou quelque chose se trouve **pour vous, maintenant**. Les applications d'astronomie sur telephone l'utilisent souvent pour vous indiquer dans quelle direction pointer votre regard. Certaines montures simples (montures "azimutales") utilisent aussi ce systeme.

---

## 4. Pourquoi votre monture equatoriale utilise RA/DEC

### Le probleme de la rotation terrestre

Le defi fondamental de l'astrophotographie, c'est que la Terre tourne. Si votre telescope est immobile, les etoiles dessinent des trainees sur votre image au bout de quelques secondes. Il faut donc que le telescope **suive** le mouvement apparent des etoiles.

### La solution geniale de la monture equatoriale

Votre ZWO AM3N est une **monture equatoriale**. Son principe est elegant :

1. **Un axe est aligne avec l'axe de rotation de la Terre** (on appelle cela l'axe polaire ou axe RA). Cet axe pointe vers le pole Nord celeste (approximativement vers l'etoile Polaire).

2. **Le deuxieme axe est perpendiculaire au premier** (c'est l'axe DEC). Il permet de "monter" ou "descendre" vers le nord ou le sud celeste.

Une fois le telescope pointe sur un objet, il suffit de faire tourner **un seul axe** (l'axe RA) a la meme vitesse que la Terre pour compenser parfaitement la rotation terrestre. C'est comme si on "detournait" la rotation de la Terre.

> **Analogie du tourne-disque :** Imaginez un tourne-disque vinyle. L'aiguille suit le sillon parce que le disque tourne. Votre monture equatoriale fait pareil : son axe RA tourne au meme rythme que la "rotation" du ciel (un tour en ~23h 56m, ce qu'on appelle le jour sideral). Si l'alignement est parfait, une etoile reste parfaitement immobile dans votre oculaire ou sur votre capteur.

### Pourquoi pas une monture Alt-Az pour l'astrophoto ?

Une monture Alt-Az doit bouger ses **deux** axes simultanement pour suivre un objet, et le fait de maniere non uniforme (parfois plus vite, parfois plus lentement). Pire : meme en suivant parfaitement l'objet au centre de l'image, le **champ de vision tourne** lentement autour du centre au cours de la nuit (on appelle cela la **rotation de champ**). Ce probleme n'existe pas avec une monture equatoriale correctement alignee.

---

## 5. La mise en station (alignement polaire)

### De quoi s'agit-il ?

La "mise en station" (en anglais : **polar alignment**) consiste a orienter precisement l'axe polaire de votre monture de sorte qu'il pointe exactement vers le pole Nord celeste.

### Pourquoi c'est crucial

Si l'axe RA de votre monture n'est pas parfaitement aligne avec l'axe de rotation terrestre, alors le mouvement de suivi en RA seul ne suffit plus. Les etoiles vont lentement "deriver" en declinaison au fil du temps. Plus votre alignement est precis, moins cette derive est importante, et plus vos photos de longue pose seront nettes.

> **Analogie de la porte :** Imaginez que vous voulez faire tourner une porte sur ses gonds pour suivre le mouvement d'un train qui passe. Si les gonds sont droits et bien alignes, la porte tourne parfaitement. Mais si les gonds sont de travers, la porte va aussi monter ou descendre en tournant -- elle ne suivra pas correctement le train. C'est exactement ce qui se passe quand la mise en station est mauvaise : l'axe RA "tourne" votre telescope, mais pas exactement dans la bonne direction.

### En pratique avec votre AM3N

Votre ZWO AM3N peut utiliser plusieurs methodes de mise en station :
- **Viseur polaire :** un petit telescope integre dans l'axe RA qui permet de centrer l'etoile Polaire a la bonne position.
- **Mise en station electronique via ASIAIR :** le logiciel prend des photos, mesure la position des etoiles, calcule l'erreur d'alignement, et vous guide pour la corriger. C'est la methode la plus precise et la plus simple.
- **Methode de la derive :** plus traditionnelle, elle consiste a observer la derive d'une etoile pour ajuster l'alignement.

Une mise en station precise a quelques minutes d'arc pres est suffisante pour la plupart des setups. Avec le plate solving de l'ASIAIR, on atteint facilement une precision de moins d'une minute d'arc.

---

## 6. Comment votre monture GoTo trouve les objets

### Le principe general

Quand vous selectionnez un objet dans l'ASIAIR ou une application de planetarium et que vous appuyez sur "GoTo", voici ce qui se passe :

#### Etape 1 : Le catalogue

Votre logiciel dispose d'un **catalogue** -- une base de donnees contenant les coordonnees RA/DEC de milliers d'objets celestes (galaxies, nebuleuses, amas d'etoiles, etc.). Par exemple, quand vous choisissez "M31" (la galaxie d'Andromede), le logiciel sait qu'elle se trouve a RA 0h 42m 44s, DEC +41° 16' 09''.

#### Etape 2 : Le modele d'alignement

La monture doit savoir comment ses moteurs correspondent a des positions dans le ciel. Pour cela, elle utilise un **modele d'alignement** construit lors de la procedure d'alignement initiale :

- **Alignement classique (1, 2 ou 3 etoiles) :** La monture vous demande de pointer vers des etoiles connues (par exemple Vega, Arcturus). Vous centrez chaque etoile et confirmez. La monture compare la position ou ses moteurs se trouvent avec la position theorique de l'etoile. Avec ces points de reference, elle construit un modele mathematique pour convertir les coordonnees RA/DEC en positions de ses moteurs.

- **Avec le plate solving (resolution astrometrique) :** C'est la methode moderne et la plus efficace, celle qu'utilise votre ASIAIR. Au lieu de centrer manuellement des etoiles, l'ASIAIR prend une photo du ciel, puis un algorithme compare le motif des etoiles dans l'image avec un catalogue de reference. En quelques secondes, il determine precisement ou le telescope pointe (les coordonnees RA/DEC exactes du centre de l'image). C'est comme si quelqu'un regardait une photo de la Terre prise depuis l'espace et reconnaissait instantanement quel pays c'est en comparant les cotes, les fleuves, etc. Le plate solving fait pareil avec les etoiles.

#### Etape 3 : Le deplacement (slew)

La monture calcule combien de degres chaque moteur doit tourner pour passer de sa position actuelle a la position cible, puis elle effectue le deplacement. En general, un premier GoTo vous amene "pres" de la cible, puis un plate solve confirme ou affine la position.

#### Etape 4 : Le suivi (tracking)

Une fois sur la cible, la monture active le **suivi sideral** : l'axe RA tourne a la vitesse de rotation de la Terre (~15 secondes d'arc par seconde de temps) pour garder l'objet immobile dans le champ.

> **Analogie du GPS :** Le GoTo, c'est comme un GPS pour le ciel. Le catalogue est la "carte", le modele d'alignement est le "calibrage" du GPS (il doit savoir ou il se trouve), et le plate solving est comme la localisation par satellite qui corrige en permanence la position reelle.

---

## 7. Le meridien et le retournement de monture

### Qu'est-ce que le meridien ?

Le **meridien** est une ligne imaginaire qui part du Nord, passe par le zenith (le point juste au-dessus de votre tete) et descend vers le Sud. Il divise le ciel en deux moities : **est** et **ouest**.

Quand un objet celeste traverse le meridien, on dit qu'il effectue un **transit** (ou passage au meridien). C'est le moment ou l'objet est au plus haut dans le ciel et ou les conditions d'observation sont les meilleures (vous regardez a travers le moins d'atmosphere possible).

### Le probleme mecanique

Votre AM3N, comme toute monture equatoriale de type "allemande" (German Equatorial Mount ou GEM), a le telescope d'un cote de l'axe DEC et un contrepoids (ou rien, dans le cas de l'AM3N qui peut fonctionner sans contrepoids pour des charges legeres) de l'autre cote.

Quand un objet est a l'est du meridien, le telescope est positionne d'un certain cote de la monture. Si la monture continue a suivre l'objet apres qu'il a traverse le meridien et est passe a l'ouest, le telescope risque de **heurter le trepied ou de se retrouver dans une position dangereuse** (tube vers le bas, contrepoids en haut).

### Le retournement au meridien (meridian flip)

Pour eviter ce probleme, la monture effectue un **retournement** : elle fait pivoter les deux axes de 180 degres pour repositionner le telescope de l'autre cote, puis re-pointe la meme cible.

Concretement :
1. L'objet approche du meridien.
2. La monture (ou votre logiciel ASIAIR) detecte qu'il est temps de retourner.
3. Les deux axes pivotent. Le telescope passe de l'autre cote de la monture.
4. La monture re-pointe l'objet.
5. Souvent, un plate solve est effectue pour recentrer precisement la cible.

**Consequence importante pour vos images :** Apres un retournement, l'image dans votre camera sera **tournee de 180 degres** par rapport aux images prises avant le retournement. Les logiciels d'empilement (stacking) comme PixInsight, Siril ou DeepSkyStacker gerent cela automatiquement grace aux metadonnees ou a l'alignement par etoiles.

> **Analogie :** Imaginez que vous portez une camera au bout d'une perche, du cote droit de votre corps, pour filmer un oiseau. L'oiseau passe devant vous et continue de l'autre cote. Plutot que de vous tordre inconfortablement, vous basculez la perche de l'autre cote (du cote gauche) -- mais maintenant votre camera est "a l'envers" par rapport a avant. Voila le retournement au meridien.

---

## 8. Comprendre les erreurs de guidage : RA vs DEC

### Le guidage (autoguiding)

En astrophotographie, meme avec une monture excellente comme l'AM3N, de petites imperfections mecaniques font que le suivi n'est pas parfait. Pour corriger ces imperfections en temps reel, on utilise le **guidage** (autoguiding) : une petite camera observe une etoile de reference et envoie des corrections a la monture des que l'etoile derive.

Le logiciel de guidage (PHD2 ou le guidage integre de l'ASIAIR) affiche des **erreurs** mesurees en **secondes d'arc ('')** separement pour les deux axes : RA et DEC.

### Les erreurs en RA

L'erreur en RA est generalement la plus grande des deux. Pourquoi ? Parce que :

1. **L'erreur periodique (Periodic Error, PE) :** C'est la source principale d'erreur en RA. Meme avec la technologie harmonique de l'AM3N (qui reduit beaucoup ce probleme par rapport aux montures a vis sans fin classiques), il reste de petites imperfections mecaniques dans les engrenages. Ces imperfections creent une erreur qui **se repete cycliquement** a chaque rotation de l'engrenage. Votre AM3N a une erreur periodique specifiee a ±15 secondes d'arc sans correction -- ce qui est deja tres bon.

2. **Le suivi actif :** L'axe RA est le seul qui tourne en permanence pour suivre la rotation du ciel. Toute imprecision de ce mouvement constant se traduit directement en erreur RA.

> **Analogie :** Imaginez que vous marchez sur un tapis roulant (c'est le suivi RA). Si le tapis a de petites irregularites, vous allez micro-trebucher periodiquement -- c'est l'erreur periodique. Par contre, vous ne bougez pas lateralement (DEC), donc pas de source d'erreur "mecanique" dans cette direction.

### Les erreurs en DEC

L'erreur en DEC est generalement plus petite et provient de causes differentes :

1. **Erreur de mise en station :** Si votre alignement polaire n'est pas parfait, les etoiles derivent lentement en DEC. C'est une derive **constante dans une seule direction**, pas une oscillation.

2. **Turbulence atmospherique (seeing) :** L'atmosphere fait "danser" les etoiles dans toutes les directions. Cela affecte RA et DEC de maniere egale.

3. **Flexion differentielle :** De legeres flexions mecaniques entre la lunette de guidage et le telescope principal.

### Lire vos chiffres de guidage

Quand votre logiciel affiche par exemple :

```
RA : 1.2"  |  DEC : 0.7"
```

Cela signifie :

- **RA 1.2'' (secondes d'arc RMS)** : En moyenne, votre etoile guide oscille de 1.2 secondes d'arc autour de sa position ideale sur l'axe RA. C'est la valeur "Root Mean Square" (une sorte de moyenne statistique).

- **DEC 0.7'' (secondes d'arc RMS)** : En moyenne, votre etoile guide oscille de 0.7 secondes d'arc sur l'axe DEC.

**Ces valeurs sont-elles bonnes ?** Cela depend de votre resolution (taille des pixels par rapport a la focale) :

| Erreur RMS totale | Appreciation |
|-------------------|-------------|
| < 0.5'' | Excellent (ciel tres stable, guidage parfait) |
| 0.5'' - 1.0'' | Tres bon (suffisant pour la plupart des setups) |
| 1.0'' - 1.5'' | Correct (acceptable pour focales courtes/moyennes) |
| 1.5'' - 2.0'' | Moyen (risque de trainee sur longues focales) |
| > 2.0'' | A ameliorer |

L'erreur RMS totale se calcule : `sqrt(RA² + DEC²)`. Avec RA = 1.2'' et DEC = 0.7'', cela donne `sqrt(1.44 + 0.49) = sqrt(1.93) ≈ 1.39''`.

**Regle pratique :** Si votre erreur RMS totale est inferieure a votre **echelle de pixel** (la taille angulaire d'un pixel de votre camera), vous ne verrez probablement pas de trainee sur vos images. Si elle est superieure, les etoiles seront legerement allongees.

### Comment interpreter et corriger

| Ce que vous observez | Cause probable | Solution |
|---------------------|---------------|----------|
| RA oscille regulierement (sinusoide) | Erreur periodique | Activer PEC (correction d'erreur periodique) ; le guidage la corrige aussi |
| RA derive dans une direction | Vitesse de suivi incorrecte | Verifier le taux de suivi sideral |
| DEC derive lentement dans une direction | Mauvaise mise en station | Refaire l'alignement polaire |
| DEC oscille (va-et-vient) | Seeing, flexion, ou surcompensation du guidage | Reduire l'agressivite du guidage en DEC, verifier le jeu (backlash) |
| Les deux axes sont erratiques | Mauvais seeing, vent, vibrations | Attendre de meilleures conditions, verifier la stabilite du trepied |

---

## 9. Resume avec analogies

### Le memo complet

| Concept | Analogie | En une phrase |
|---------|----------|---------------|
| **Sphere celeste** | Le dome d'un planetarium | Un globe imaginaire autour de la Terre sur lequel on projette les etoiles |
| **RA (Ascension Droite)** | Les fuseaux horaires de la Terre | La "longitude" du ciel, en heures, car le ciel defile comme une horloge |
| **DEC (Declinaison)** | La latitude terrestre | La "latitude" du ciel, en degres nord (+) ou sud (-) |
| **Alt (Altitude)** | "A quelle hauteur dans le ciel ?" | L'angle entre l'horizon et l'objet, en degres |
| **Az (Azimut)** | "Dans quelle direction de la boussole ?" | La direction horizontale (Nord=0°, Est=90°, Sud=180°, Ouest=270°) |
| **Monture equatoriale** | Un tourne-disque incline | Un des axes est aligne avec la rotation terrestre, un seul moteur suffit pour suivre |
| **Mise en station** | Aligner les gonds d'une porte | Orienter l'axe polaire de la monture vers le pole Nord celeste |
| **GoTo** | Un GPS pour le ciel | La monture utilise un catalogue + un modele pour trouver et pointer un objet |
| **Plate solving** | Reconnaissance de motifs (comme Shazam pour les etoiles) | Un algorithme identifie les etoiles dans une photo pour determiner ou pointe le telescope |
| **Meridien** | La ligne Nord-Zenith-Sud | Ligne imaginaire separant l'est et l'ouest du ciel |
| **Retournement** | Changer la perche d'epaule | La monture bascule le telescope de l'autre cote pour eviter une collision mecanique |
| **Erreur RA** | Les micro-a-coups d'un tapis roulant | Oscillations dues aux imperfections mecaniques du suivi |
| **Erreur DEC** | Une derive laterale en marchant | Souvent causee par un alignement polaire imparfait |
| **Erreur periodique** | Un pneu legerement ovale | Erreur cyclique des engrenages qui revient a chaque tour |
| **Secondes d'arc ('')** | 1/3600e de degre | Unite de mesure des angles tres petits (la pleine Lune fait ~1800'') |

### La grande image

```
                        Pole Nord celeste (+90° DEC)
                              *  (Polaire)
                             /|\
                            / | \
                           /  |  \
    Etoiles a l'Est      /   |   \      Etoiles a l'Ouest
    (se levent)          /    |    \     (se couchent)
                        /     |     \
    ─────────────── Horizon ──┼── Horizon ───────────────
                        \     |     /
                         \    |    /
                          \   |   /
                           \  |  /
                            \ | /
                             \|/
                        Pole Sud celeste (-90° DEC)

    L'axe RA de votre AM3N pointe vers le Pole Nord celeste.
    Il tourne pour compenser la rotation de la Terre.
    L'axe DEC pointe perpendiculairement pour "monter" ou "descendre".

    Le meridien est la ligne verticale au centre (Nord → Zenith → Sud).
```

### En resume

- **RA/DEC** = adresse permanente d'un objet dans le ciel (comme une adresse postale)
- **Alt/Az** = description de ou se trouve l'objet pour vous maintenant (comme "c'est la maison la-bas a droite")
- **Votre monture** convertit les adresses permanentes (RA/DEC) en mouvements de moteurs
- **Le suivi** = un seul moteur (RA) tourne pour compenser la rotation terrestre
- **Le guidage** = une camera de surveillance qui verifie que le suivi est bien precis et corrige les petites erreurs
- **Le plate solving** = un systeme de reconnaissance qui identifie ou le telescope pointe en "lisant" les etoiles

---

*Ce guide a ete redige pour les utilisateurs de la monture ZWO AM3N, mais les concepts s'appliquent a toute monture equatoriale GoTo.*
