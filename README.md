# 🥬 Mon Panier — Guide complet pour débuter

> **Ce document s'adresse à quelqu'un qui ne connaît ni GitHub, ni Python, ni les workflows.** Il explique toute la chaîne : comment l'application fonctionne sur un téléphone, comment les ingrédients sont recherchés, comment les menus sont créés, comment les données sont enregistrées et ce qui coûte (ou non) des tokens d'intelligence artificielle.

**Ouvrir l'application :** https://jaycikomo.github.io/mon-panier/  
**Voir le code source :** https://github.com/jaycikomo/mon-panier  
**Guide technique complémentaire :** [IA-DEMARRAGE.md](IA-DEMARRAGE.md)

---

## 📖 Sommaire

1. [L'application en une minute](#1--lapplication-en-une-minute)
2. [Comment s'en servir au quotidien](#2--comment-sen-servir-au-quotidien)
3. [Les cinq grandes technologies utilisées](#3--les-cinq-grandes-technologies-utilisées)
4. [Où sont les fichiers dans GitHub ?](#4--où-sont-les-fichiers-dans-github-)
5. [Le fonctionnement complet, de A à Z](#5--le-fonctionnement-complet-de-a-à-z)
6. [Le catalogue Lidl, Aldi et Netto](#6--le-catalogue-lidl-aldi-et-netto)
7. [Le programme de recettes sur quatre semaines](#7--le-programme-de-recettes-sur-quatre-semaines)
8. [C'est quoi un workflow YAML ?](#8--cest-quoi-un-workflow-yaml-)
9. [À quoi sert le programme Python ?](#9--à-quoi-sert-le-programme-python-)
10. [À quoi sert un fichier JSON ?](#10--à-quoi-sert-un-fichier-json-)
11. [Comment le navigateur lit les résultats et conserve tes choix](#11--comment-le-navigateur-lit-les-résultats-et-conserve-tes-choix)
12. [Tokens, coût et sécurité](#12--tokens-coût-et-sécurité)
13. [Vérifier un workflow et résoudre les erreurs](#13--vérifier-un-workflow-et-résoudre-les-erreurs)
14. [Modifier l'application sans tout casser](#14--modifier-lapplication-sans-tout-casser)
15. [Petit dictionnaire pour débuter](#15--petit-dictionnaire-pour-débuter)

---

## 1 — L'application en une minute

**Mon Panier** est un site web qui fonctionne sur ordinateur, iPhone et Android. Il aide à :

- Organiser **7 jours de repas**, avec petit-déjeuner, déjeuner, collation et dîner.
- Consulter les recettes, les étapes de préparation et les quantités.
- Estimer les **calories et macronutriments** : protéines, glucides et lipides.
- Construire la liste de courses correspondant au menu et au nombre de personnes.
- Cocher les produits achetés, ajouter des articles personnels, chercher un produit et partager une liste.
- Choisir des magasins et signaler qu'un article n'y a pas été trouvé.
- Conserver une copie des semaines précédentes dans le navigateur.

**Objectifs indicatifs du programme :** environ **1 915 kcal, 130 g de protéines, 180 g de glucides et 75 g de lipides par adulte et par jour**. Ce sont des estimations de planification, pas un diagnostic ou un conseil médical personnalisé.

**Important :** Mon Panier n'est pas une application qui consulte les stocks réels des magasins. Elle connaît des *références de produits* et permet de noter les indisponibilités rencontrées pendant les courses.

## 2 — Comment s'en servir au quotidien

### Première ouverture

1. Ouvrir https://jaycikomo.github.io/mon-panier/.
2. Sélectionner les commerces utilisés. Pour une nouvelle installation, les choix proposés sont **Lidl La Destrousse, Aldi La Bouilladisse et Netto La Destrousse**.
3. Accéder à **Ma semaine** et consulter les menus proposés.
4. Ouvrir **Liste de courses** et ajuster le nombre de personnes (de 1 à 8).
5. Cocher les produits au fur et à mesure des achats.

L'application contient cinq rubriques :

| Rubrique | À quoi elle sert |
|---|---|
| **📅 Ma semaine** | Voir les repas du lundi au dimanche et les estimations nutritionnelles. |
| **🗂️ Archives** | Revoir les semaines précédentes conservées sur cet appareil et éventuellement réutiliser un ancien menu. |
| **✅ Liste de courses** | Voir les produits nécessaires, leurs quantités et leur magasin attribué. |
| **🍽️ Recettes** | Consulter les plats et leurs préparations. |
| **📍 Mes commerces** | Sélectionner ou retirer des magasins, marchés et commerces de proximité. |

### Quand un produit manque en rayon

La priorité de courses est **Lidl La Destrousse → Aldi La Bouilladisse → Netto La Destrousse**.

**Exemple :** du riz est attribué à Lidl.

1. Tu ne le trouves pas chez Lidl : clique sur **« Pas disponible chez Lidl »**.
2. L'application propose alors **Aldi La Bouilladisse**.
3. S'il manque aussi chez Aldi, elle propose **Netto La Destrousse**.
4. Si tu as sélectionné d'autres enseignes (par exemple Intermarché), elles peuvent servir de repli.
5. Un bouton permet d'annuler les signalements d'indisponibilité pour cet article.

Ce mécanisme est **une préférence de magasin enregistrée sur ton appareil**, pas une preuve qu'Aldi ou Netto ont le produit en stock.

### Autres possibilités pratiques

- **Remplacer un ingrédient** par une alternative proposée : la liste et les estimations sont recalculées.
- **Ajouter un produit personnel** avec son nom et éventuellement sa quantité ; tu peux ensuite le supprimer.
- **Changer de magasin manuellement** pour un article.
- **Partager la liste** sous forme de texte (Messages, WhatsApp ou copier-coller), ou transmettre un lien permettant d'importer une copie.
- **Afficher ou masquer des illustrations**, quand elles existent déjà.

**Attention au partage :** deux téléphones ne partagent pas une liste synchronisée en temps réel. Le partage transmet une **copie** des données à un instant donné.

## 3 — Les cinq grandes technologies utilisées

Voici l'idée la plus importante du projet :

| Technologie | Fichiers | Son travail, en langage simple |
|---|---|---|
| **YAML** | `.yml` | Dit à GitHub **QUAND** lancer un travail et quelles étapes effectuer. |
| **Python** | `.py` | Décrit **COMMENT** récupérer des produits, créer des recettes et calculer les menus. |
| **JSON** | `.json` | **ENREGISTRE** des informations lisibles par d'autres programmes. |
| **HTML + CSS + JavaScript** | `index.html` | **AFFICHE** l'interface, gère les clics et lit les données enregistrées. |
| **GitHub / GitHub Actions / GitHub Pages** | Services en ligne | **HÉBERGENT**, **EXÉCUTENT automatiquement** et **PUBLIENT** l'application. |

Une analogie :

- Le **YAML**, c'est le calendrier et la liste d'instructions du chef d'équipe.
- Le **Python**, c'est le cuisinier qui prépare les recettes.
- Le **JSON**, c'est le cahier où l'on note les recettes et les courses.
- Le **HTML/CSS/JavaScript**, c'est la vitrine et les boutons accessibles à l'utilisateur.
- **GitHub**, c'est à la fois l'armoire de rangement, l'atelier automatique et l'hébergeur du site.

## 4 — Où sont les fichiers dans GitHub ?

Un **dépôt GitHub** (ou *repository*) est un dossier de projet conservé en ligne. Dans ce projet, la structure importante est :

```text
mon-panier/                           ← RACINE du projet
│
├── README.md                         ← CE GUIDE : point de départ pour débuter
├── IA-DEMARRAGE.md                   ← Explications techniques complémentaires
├── index.html                        ← L'application : HTML + CSS + JavaScript
│
├── scripts/
│   ├── generate_ai_week.py           ← Génération et publication des menus
│   └── sync_store_catalog.py        ← Récupération des références alimentaires
│
├── data/
│   ├── retail/
│   │   ├── official-references.json  ← Références identifiées sur sites officiels
│   │   └── catalog.json              ← Catalogue consolidé utilisé par l'application
│   │
│   └── ai/
│       ├── latest.json               ← Menus de la semaine actuellement publiée
│       ├── weeks/                    ← Une sauvegarde JSON par semaine
│       └── batches/                  ← Lots de 4 semaines (créés à la 1re génération)
│
├── .github/
│   └── workflows/
│       ├── catalogue-enseignes.yml   ← Synchronisation gratuite du catalogue
│       ├── recettes-ia.yml           ← Publication du lundi / génération si nécessaire
│       └── tests-menus.yml           ← Tests automatiques gratuits
│
└── tests/
    └── test_monthly_menu.py          ← Programme qui vérifie le cycle mensuel
```

**« À la racine »** signifie directement dans `mon-panier/`, au même niveau que `index.html`. GitHub affiche automatiquement `README.md` sur la page d'accueil du dépôt.

**Note :** le dossier `data/ai/batches/` n'apparaît qu'après une **première génération réussie** avec le nouveau système. Il n'est pas indispensable à l'ouverture du site.

## 5 — Le fonctionnement complet, de A à Z

```text
       DIMANCHE                                  LUNDI
 ┌──────────────────────┐                ┌──────────────────────┐
 │ catalogue-enseignes  │                │ recettes-ia.yml      │
 │        .yml          │                │ Vérifie la sauvegarde│
 └──────────┬───────────┘                └──────────┬───────────┘
            │                                       │
            ▼                                       ▼
 ┌──────────────────────┐             Semaine déjà enregistrée ?
 │ sync_store_catalog.py│                    /          \
 │ Source officielle +  │                 OUI            NON
 │ Open Food Facts      │                  │              │
 └──────────┬───────────┘                  │              ▼
            │                              │       Appel à l'IA
            ▼                              │       puis calcul Python
 ┌──────────────────────┐                  │              │
 │ data/retail/         │                  │              ▼
 │    catalog.json      │                  │       4 semaines enregistrées
 └──────────┬───────────┘                  │              │
            │                              └──────┬───────┘
            │                                     │
            │                                     ▼
            │                           data/ai/latest.json
            │                                     │
            └─────────────────┬───────────────────┘
                              ▼
                         index.html
                              │
                              ▼
                    SITE MON PANIER
              (navigateur et téléphone)
```

Ce qu'il faut bien distinguer :

1. **GitHub Actions travaille sur ses propres machines Linux temporaires.** Ton PC peut être éteint.
2. **Le résultat est conservé dans le dépôt GitHub**, grâce à un *commit* (enregistrement de modifications).
3. **GitHub Pages héberge le site** statique.
4. Quand tu ouvres Mon Panier, **JavaScript lit les JSON publiés** et met les menus et le catalogue à l'écran.
5. Tes coches, préférences et ajouts personnels sont conservés **localement dans ton navigateur**, et non dans le catalogue partagé sur GitHub.

## 6 — Le catalogue Lidl, Aldi et Netto

### D'où viennent les produits ?

Le script [`sync_store_catalog.py`](scripts/sync_store_catalog.py) exploite deux types de sources :

- **Des références de produits ou de gammes identifiées sur les sites officiels** de Lidl, Aldi et Netto, conservées dans `data/retail/official-references.json`.
- **Open Food Facts**, une base participative, lorsque son service répond correctement.

Il rassemble ensuite ces données dans [`data/retail/catalog.json`](data/retail/catalog.json).

Si Open Food Facts est en panne (par exemple une erreur **503**), les références officielles déjà enregistrées servent de **solution de secours**. On n'invente pas de produits ni de stocks.

Le catalogue contient notamment : le nom d'un produit, l'enseigne, l'ingrédient auquel il correspond, la source et parfois un lien vers la fiche.

### Attention à la différence « référencé » / « disponible »

Une fiche vue sur un site ne signifie **pas** que le produit est actuellement en rayon à La Destrousse ou La Bouilladisse. Les promotions anciennes et leurs prix ne doivent pas non plus être présentés comme des offres actuelles.

C'est précisément pour cela que Mon Panier te permet de signaler **« Pas disponible ici »**, puis de passer à l'enseigne suivante.

### Quand cette mise à jour s'exécute-t-elle ?

Le workflow [`catalogue-enseignes.yml`](.github/workflows/catalogue-enseignes.yml) est programmé :

- **Le dimanche à 05 h 20 UTC**, soit 07 h 20 en été / 06 h 20 en hiver en France.
- **Sans appel OpenAI** et donc sans consommation de tokens IA.
- Il peut également se lancer lorsqu'on modifie certains fichiers du catalogue ou du workflow, ou manuellement depuis GitHub.

L'état et le nombre de références peuvent varier suivant les sources accessibles. Le catalogue n'est pas un inventaire exhaustif.

## 7 — Le programme de recettes sur quatre semaines

### Pourquoi quatre semaines d'un coup ?

Interroger l'IA chaque lundi coûte des tokens. Le nouveau principe est donc de **préparer plusieurs semaines d'avance** et de réutiliser les sauvegardes.

**Une génération réussie produit :**

- **32 recettes de base** (5 petits-déjeuners, 11 déjeuners, 5 collations et 11 dîners).
- **4 semaines différentes** de menus, chacune avec 7 jours et 4 repas par jour.
- **20 recettes sélectionnées pour chaque semaine** (3 petits-déjeuners, 7 déjeuners, 3 collations et 7 dîners).
- Le calcul des quantités et des macros de chaque semaine.
- **Aucune nouvelle photo générée par l'IA.**

**Nuance importante :** les 20 recettes d'une semaine sont choisies parmi les 32 recettes de base. Cela ne représente **pas 80 recettes entièrement distinctes** sur les quatre semaines.

### Exemple de calendrier (si la première génération réussit)

| Lundi | Ce que fait le programme | Tokens IA |
|---|---|---|
| **19 octobre 2026** | Génère et sauvegarde les semaines du 19/10, 26/10, 02/11 et 09/11 | **1 appel texte payant** |
| **26 octobre** | Publie la semaine 2 depuis `weeks/` | **0** |
| **2 novembre** | Publie la semaine 3 depuis `weeks/` | **0** |
| **9 novembre** | Publie la semaine 4 depuis `weeks/` | **0** |
| **16 novembre** | Génère le lot suivant, si nécessaire | **1 appel texte payant** |

C'est un **cycle de quatre semaines**, pas forcément un mois civil. Si une génération échoue, ce calendrier se décale : il ne faut pas considérer les menus futurs comme déjà prêts avant de voir leurs fichiers sur GitHub.

### Comment Python choisit les repas ?

Le script [`generate_ai_week.py`](scripts/generate_ai_week.py) suit plusieurs étapes :

1. **Lit le catalogue des ingrédients** et les informations des enseignes.
2. **Demande 32 recettes à GPT-5 mini** lorsqu'aucune sauvegarde n'existe pour le nouveau cycle.
3. **Contrôle les recettes** : identifiants, ingrédients autorisés, quantités, type de repas et descriptions.
4. **Calcule les macros** à partir d'une table d'ingrédients (environ 4 kcal/g pour protéines et glucides, 9 kcal/g pour lipides).
5. **Ajuste les portions**, puis construit des journées visant les objectifs énergétiques et protéiques.
6. **Répartit les recettes sur quatre semaines**, en cherchant des menus variés.
7. **Écrit les fichiers JSON** de sauvegarde.
8. **Publie seulement la semaine courante** dans `latest.json`.

Les valeurs nutritionnelles restent des **estimations** ; elles ne remplacent pas les informations des emballages.

### Comment éviter une deuxième facture la semaine suivante ?

Le programme vérifie d'abord :

```text
La semaine actuelle est-elle déjà publiée ?
    OUI → ne rien faire, 0 appel IA
    NON ↓
Existe-t-elle déjà dans data/ai/weeks/ ?
    OUI → recopier cette semaine dans latest.json, 0 appel IA
    NON → produire le prochain lot avec l'IA, si la clé API est configurée
```

Cette vérification intervient **avant** de réclamer la clé OpenAI. Le script ne fait pas de second appel automatique lorsque le résultat de génération est invalide. Il peut toutefois en consommer lors d'une future exécution si aucun lot valide n'a été sauvegardé.

## 8 — C'est quoi un workflow YAML ?

Un **workflow** est une automatisation décrite dans un fichier `.yml` (ou `.yaml`). GitHub Actions lit ce fichier et exécute les instructions indiquées.

Voici un **exemple simplifié** du workflow des menus :

```yaml
name: Menus du lundi

on:
  schedule:
    - cron: '37 5 * * 1'
  workflow_dispatch:

jobs:
  menus:
    runs-on: ubuntu-latest
    steps:
      - name: Récupérer les fichiers
        uses: actions/checkout@v5

      - name: Installer Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.12'

      - name: Lancer le programme
        run: python scripts/generate_ai_week.py
```

| Mot YAML | Explication |
|---|---|
| `name` | Le nom affiché dans GitHub Actions. |
| `on` | L'événement qui déclenche l'automatisation. |
| `schedule` | Une programmation à date/heure régulière. |
| `cron` | L'expression indiquant minute, heure, jour, mois et jour de semaine. |
| `workflow_dispatch` | Permet un lancement manuel avec **Run workflow**. |
| `jobs` | Les tâches à exécuter. |
| `runs-on: ubuntu-latest` | Demande une machine Linux temporaire fournie par GitHub. |
| `steps` | Les étapes, dans l'ordre. |
| `uses` | Utilise une action GitHub existante (téléchargement du code, installation de Python…). |
| `run` | Exécute une commande comme dans un terminal. |

**Lire `37 5 * * 1` :** « à la minute 37 de l'heure 5 UTC, chaque lundi ». Cela donne **07 h 37 en heure d'été française** ou **06 h 37 en heure d'hiver**. GitHub peut démarrer une tâche planifiée avec un peu de retard.

**Attention :** les espaces et l'indentation sont importants en YAML. Si on les modifie mal, GitHub peut refuser le fichier.

### Les workflows installés dans Mon Panier

- [Catalogue des enseignes — gratuit](.github/workflows/catalogue-enseignes.yml) : le dimanche.
- [Menus depuis la sauvegarde — renouvellement IA si nécessaire](.github/workflows/recettes-ia.yml) : chaque lundi.
- [Tests des menus — gratuits](.github/workflows/tests-menus.yml) : après les changements concernés.
- **GitHub Pages** : met le site en ligne après les commits, avec son propre traitement de déploiement.

## 9 — À quoi sert le programme Python ?

Le langage **Python** sert à écrire les opérations qui font réellement le travail.

Quand le YAML contient cette ligne :

```yaml
run: python scripts/generate_ai_week.py
```

cela veut dire : « Ouvre le programme `generate_ai_week.py` et exécute ses instructions ».

Voici un petit **exemple pédagogique**, indépendant du code réel de Mon Panier :

```python
# Une fonction est un ensemble d'instructions qui porte un nom.
def calculer_calories(proteines, glucides, lipides):
    return 4 * proteines + 4 * glucides + 9 * lipides

resultat = calculer_calories(30, 40, 15)
print(resultat)  # 415 kcal
```

Explication :

- `def` définit une **fonction**.
- `proteines`, `glucides` et `lipides` sont les **valeurs reçues**.
- `return` renvoie le résultat d'un calcul.
- `print` affiche un message dans le journal d'exécution.
- `#` introduit un **commentaire** : Python ne l'exécute pas.

Dans le vrai programme de Mon Panier, certaines fonctions sont importantes :

| Fonction Python | Rôle |
|---|---|
| `ingredients()` | Lit les ingrédients et leurs macros dans `index.html`. |
| `retail_inventory()` | Lit les références documentées dans le catalogue des magasins. |
| `generate_recipes()` | Appelle l'API OpenAI uniquement pour un nouveau lot. |
| `validate()` | Vérifie que les recettes produites sont exploitables. |
| `rebalance_portions()` | Ajuste les portions en fonction des apports calculés. |
| `build_plan()` | Organise les recettes sur sept jours. |
| `select_week()` | Construit une semaine à partir de la banque de recettes. |
| `publish_cached_week()` | Republie une semaine préexistante, sans IA. |

Le programme du catalogue utilise quant à lui `sync_store_catalog.py` : il lit les sources et crée un fichier de données. **Il n'a pas besoin d'OpenAI.**

## 10 — À quoi sert un fichier JSON ?

**JSON** signifie *JavaScript Object Notation*. C'est un format de données, pas un programme.

Il peut conserver du **texte**, des **nombres**, des **listes** et des **objets**. Python peut l'écrire, et JavaScript peut le lire.

Voici un **exemple très réduit** de la forme des recettes sauvegardées dans Mon Panier :

```json
{
  "week": "2026-10-19",
  "batch_start": "2026-10-19",
  "batch_week_index": 1,
  "batch_weeks": 4,
  "recipes": {
    "ia-2026-10-19-b1": {
      "name": "Bol de skyr et banane",
      "meal": "Petit-déjeuner",
      "time": "10 min",
      "steps": "Préparer le bol, ajouter les ingrédients et servir.",
      "items": [
        { "id": "skyr", "g": 200 },
        { "id": "banane", "g": 100 },
        { "id": "avoine", "g": 50 }
      ],
      "source": "ia"
    }
  }
}
```

Il s'agit d'un **exemple de structure**, pas d'une vraie recette publiée : les fichiers réels contiennent aussi les 20 recettes de la semaine, le plan des 7 jours et des résumés nutritionnels.

Comment le lire ?

- `"week"` = la semaine à laquelle appartiennent les menus.
- `"recipes"` = l'ensemble des recettes.
- `"name"` = le nom d'une recette.
- `"items"` = la liste de ses ingrédients.
- `"id"` = le code interne d'un ingrédient.
- `"g"` = la quantité en **grammes pour une personne**.

Quelques fichiers clés :

| Fichier | Ce qu'il mémorise |
|---|---|
| [`data/ai/latest.json`](data/ai/latest.json) | La semaine que le site doit charger maintenant. |
| `data/ai/weeks/AAAA-MM-JJ.json` | Une semaine prête à être publiée. |
| `data/ai/batches/AAAA-MM-JJ.json` | Une banque de recettes pour un lot de quatre semaines. |
| [`data/retail/catalog.json`](data/retail/catalog.json) | Les références de produits liées aux ingrédients. |
| [`data/retail/official-references.json`](data/retail/official-references.json) | La liste des références repérées sur des sites officiels. |

**Pourquoi ne pas tout garder dans Python ?** Parce que Python s'arrête à la fin du workflow, tandis que les fichiers JSON restent enregistrés sur GitHub et peuvent être réutilisés plus tard.

## 11 — Comment le navigateur lit les résultats et conserve tes choix

Le fichier [`index.html`](index.html) contient en réalité **trois technologies** :

- **HTML** : la structure de la page, les titres, les cartes de recettes et les boutons.
- **CSS** : les couleurs, tailles, espacements et adaptations pour téléphone.
- **JavaScript** : les actions après un clic, le calcul de la liste, la lecture des JSON et la sauvegarde locale.

### Qui affiche la bonne semaine ?

Au chargement, le JavaScript consulte le contenu de `data/ai/latest.json` publié sur GitHub. Il vérifie que la date correspond à la semaine actuelle et que les recettes et menus ont une structure valide.

- Si tout est correct : il intègre les recettes et affiche **Semaine 1/4**, **2/4**, etc.
- Si le JSON est absent, ancien ou inaccessible : l'application conserve des **menus de secours** et peut signaler que la publication IA est en attente.
- Quand le catalogue des magasins est disponible, JavaScript affiche des liens vers les fiches référencées.

### Où vont tes coches et préférences ?

Les coches, magasins choisis, substitutions et produits personnels sont sauvegardés grâce à **`localStorage`**, un petit espace de mémoire du navigateur. La clé utilisée est `mon-panier-v1`.

Cela signifie :

- Si tu fermes la page puis la rouvres sur le **même navigateur**, tes choix peuvent être retrouvés.
- Si tu changes de téléphone, utilises un autre navigateur ou effaces les données du site, ils ne sont pas automatiquement transférés.
- Quand une nouvelle semaine commence, la liste de courses est **remise à zéro** pour cette semaine, et les anciens menus peuvent être archivés.
- Une **copie partagée** n'est pas une synchronisation en direct entre membres de la famille.

Les fichiers de recettes communs sont publiés sur GitHub ; **tes coches personnelles ne sont pas envoyées dans le dépôt GitHub**.

## 12 — Tokens, coût et sécurité

### Qu'est-ce qu'un token ?

Un token est une petite unité de texte utilisée par un modèle d'IA pour lire une demande et produire sa réponse. Les appels à l'API OpenAI sont facturés selon la consommation et le modèle.

| Action | Tokens OpenAI ? |
|---|---|
| Ouvrir le site, consulter des recettes ou cocher des courses | **Non** |
| Ajouter un article personnel ou le déplacer de Lidl à Aldi | **Non** |
| Actualiser le catalogue officiel / Open Food Facts | **Non** |
| Publier une semaine déjà enregistrée dans `weeks/` | **Non** |
| Lancer les tests automatiques GitHub | **Non** |
| Créer **un nouveau lot de quatre semaines** avec GPT-5 mini | **Oui** |
| Générer de nouvelles photos IA | **Non : fonctionnalité payante supprimée du générateur actuel** |

Le système vise **un appel texte pour quatre semaines**, *lorsqu'une génération réussit*. Un nouveau lot plus long peut demander davantage de tokens qu'une petite génération, donc **aucun montant fixe en euros n'est garanti**.

**L'abonnement ChatGPT Plus et les crédits de l'API OpenAI sont deux facturations distinctes.**

### Où se trouve la clé API ?

La clé `OPENAI_API_KEY` doit être enregistrée dans les **Secrets GitHub Actions**, pas dans les fichiers du site :

**GitHub → dépôt → Settings → Secrets and variables → Actions → Repository secrets**

Le workflow la fournit au script **sur le serveur temporaire GitHub** lorsqu'une génération est nécessaire. Le fichier `index.html` ne doit jamais contenir cette clé.

**Important :** ne publie jamais une clé API, un mot de passe ou un jeton dans un fichier JSON, du JavaScript ou une capture d'écran.

Tu peux suivre les dépenses sur https://platform.openai.com/usage et définir tes limites de budget dans la plateforme OpenAI.

## 13 — Vérifier un workflow et résoudre les erreurs

### Comment suivre ce qui se passe ?

1. Aller sur https://github.com/jaycikomo/mon-panier/actions.
2. Choisir le workflow dans le menu à gauche.
3. Ouvrir sa dernière exécution.
4. Ouvrir le **job**, puis l'étape qui t'intéresse.
5. Lire le **log** : c'est le journal des messages imprimés par la machine GitHub.

| Statut GitHub | Signification |
|---|---|
| ✅ **Success** | Le workflow a terminé correctement. |
| 🔄 **In progress** | Il est encore en train de travailler. |
| 🔴 **Failure** | Une étape a échoué ; ouvrir ses logs. |
| ⚪ **Queued / Pending** | GitHub attend une machine disponible. |
| ➖ **Cancelled** | Une exécution a été annulée. |

**Succès du workflow ≠ garantie de stocks réels** et **succès d'une récupération ≠ nouvelle recette IA**. Il faut vérifier le fichier de sortie attendu.

### Dépannages les plus courants

| Symptôme | Vérification / explication |
|---|---|
| **Les nouvelles recettes ne s'affichent pas.** | Vérifier que `latest.json` porte la date du lundi actuel, puis recharger le site. |
| **Le lundi, l'IA n'a pas été appelée.** | C'est **normal** lorsqu'une semaine est déjà enregistrée : le workflow la publie gratuitement. |
| **Le catalogue ne récupère rien.** | Vérifier ses logs. Open Food Facts peut répondre **503** ; le programme conserve les références officielles existantes. |
| **Un workflow est rouge.** | Ouvrir l'étape en échec. Il peut s'agir de réseau, de données invalides, d'un secret manquant ou d'un problème de publication Git. |
| **La génération IA échoue.** | Vérifier la clé API, les crédits, la réponse du modèle et les logs ; une génération échouée peut avoir consommé des tokens. |
| **Un produit est affiché mais n'est pas en rayon.** | Le catalogue documente une référence, **pas le stock actuel** ; utiliser « Pas disponible ici ». |
| **Mes coches ont disparu sur un autre téléphone.** | Normal : elles sont conservées localement, pas synchronisées entre appareils. |
| **Mes coches se sont remises à zéro lundi.** | C'est le changement de semaine prévu par l'application. |
| **GitHub lance un workflow en retard.** | Les planifications GitHub Actions ne garantissent pas une exécution à la minute exacte. |

### 🔔 Notifications automatiques en cas de panne

Le fichier [`.github/workflows/alertes.yml`](.github/workflows/alertes.yml) surveille les workflows du **catalogue**, des **menus du lundi**, des **tests** et du **déploiement GitHub Pages**.

Il est gratuit, sans clé supplémentaire et sans appel à OpenAI :

1. Un workflow se termine avec une erreur.
2. GitHub crée une **Issue** (« ticket ») avec le nom du workflow, la date, le résultat et le lien vers les logs.
3. Cette Issue est **assignée au propriétaire du dépôt** (`jaycikomo`), pour pouvoir déclencher une notification GitHub Mobile si l'application est configurée.
4. Si le même problème revient, l'Issue existante est commentée plutôt que dupliquée.
5. Lorsque ce workflow réussit de nouveau, l'Issue est automatiquement fermée.

**Pour recevoir une notification sur téléphone :**

1. Installer **GitHub Mobile** (iPhone ou Android) et se connecter au compte `jaycikomo`.
2. Dans l'application : **Profile → Settings → Notifications** (ou **Configure Notifications** selon l'appareil).
3. Activer les notifications push **Assignments / Affectations** et autoriser les notifications GitHub dans les réglages du téléphone.
4. Au besoin, régler **Watch** du dépôt pour suivre les événements pertinents.

**Pour recevoir aussi un e-mail :** ouvrir [les paramètres de notifications GitHub](https://github.com/settings/notifications), régler **Actions → Email**, et sélectionner **Only notify for failed workflows** si l'option est proposée. GitHub envoie alors les e-mails des exécutions concernées selon ses règles d'abonnement ; les alertes par Issue dépendent des préférences de notification du compte.

**Limites :** les annulations ordinaires (`cancelled`) sont ignorées pour éviter les faux signaux, et cette surveillance ne peut pas avertir si GitHub Actions lui-même est totalement indisponible, ni garantir une notification si les réglages du téléphone la bloquent. Il n'y a **pas de SMS direct** : cela exigerait un prestataire et un numéro de téléphone, potentiellement avec des frais.

### Est-ce qu'il faut cliquer sur « Run workflow » ?

**En fonctionnement normal : non.** Les workflows planifiés démarrent automatiquement.

Le bouton **Run workflow** sert à forcer une exécution manuelle, par exemple pour diagnostiquer un problème. Attention : si aucune nouvelle semaine n'est sauvegardée, **le workflow des recettes peut déclencher un appel API OpenAI payant**. Le workflow du catalogue, lui, ne consomme aucun token OpenAI.

## 14 — Modifier l'application sans tout casser

### Une méthode simple sur GitHub

1. Ouvrir https://github.com/jaycikomo/mon-panier.
2. Cliquer sur le fichier à consulter.
3. Cliquer sur l'icône **crayon** pour modifier le fichier, si tu as les droits.
4. Corriger **une seule chose à la fois**.
5. Choisir **Commit changes** pour enregistrer la modification.
6. Ouvrir l'onglet **Actions** et regarder si les tests / déploiements se passent bien.
7. Tester dans https://jaycikomo.github.io/mon-panier/.

**Un commit**, c'est une version enregistrée du projet, avec une description. Il permet de retrouver les modifications réalisées.

**Conseil important :** pour les changements importants, créer une branche ou une copie de sauvegarde avant de modifier `main`, puis tester avant de publier.

### Si tu veux changer…

- **L'apparence ou les boutons** : travailler dans `index.html` (HTML, CSS et JavaScript).
- **Les magasins / préférences par défaut** : regarder les variables `stores`, `defaults` et `STORE_PRIORITY` dans `index.html`.
- **Les références alimentaires** : modifier `data/retail/official-references.json` avec des sources vérifiables, puis laisser le workflow reconstruire le catalogue.
- **Les recettes, contraintes nutritionnelles ou nombre de semaines** : modifier `scripts/generate_ai_week.py` **et mettre à jour les tests**.
- **Les jours/heures des automatisations** : modifier les fichiers `.github/workflows/*.yml`.
- **Le comportement de publication** : regarder `data/ai/latest.json`, le workflow des menus et ses logs.
- **La documentation** : modifier ce `README.md` ou le guide complémentaire `IA-DEMARRAGE.md`.

Ne modifie pas à la main les JSON générés automatiquement sans comprendre leurs liens avec le code : un identifiant de recette cassé peut empêcher l'application de charger les menus.

## 15 — Petit dictionnaire pour débuter

| Mot | Définition simple |
|---|---|
| **Dépôt / repository** | Le dossier du projet hébergé sur GitHub. |
| **Racine** | Le dossier principal du dépôt, ici `mon-panier/`. |
| **Code source** | Les fichiers écrits par les développeurs : HTML, JavaScript, Python, YAML… |
| **Script** | Un fichier contenant un programme exécutable. |
| **GitHub Actions** | Service qui lance les scripts sur des machines temporaires. |
| **Workflow** | Un scénario automatisé décrit dans un fichier YAML. |
| **Job** | Une grande tâche d'un workflow. |
| **Step** | Une étape à l'intérieur d'un job. |
| **Runner** | L'ordinateur temporaire qui exécute le job. |
| **Cron** | Une écriture courte indiquant quand exécuter une tâche. |
| **YAML / YML** | Le format de configuration qui orchestre le workflow. |
| **Python / PY** | Un langage de programmation utilisé pour les calculs et traitements. |
| **JSON** | Un format pour enregistrer et transmettre des données structurées. |
| **HTML** | La structure des pages affichées. |
| **CSS** | Leur mise en forme graphique. |
| **JavaScript / JS** | Le comportement de la page dans le navigateur. |
| **API** | Une façon pour deux programmes de communiquer. |
| **Token IA** | Une unité de texte utilisée pour mesurer le travail d'un modèle. |
| **Secret GitHub** | Un réglage protégé permettant de fournir une clé API à un workflow. |
| **Commit** | Un enregistrement versionné des changements dans un dépôt. |
| **GitHub Pages** | L'hébergement gratuit du site web statique. |
| **LocalStorage** | Un espace de mémoire propre au navigateur qui conserve des préférences. |
| **Cache / sauvegarde** | Des résultats conservés pour ne pas refaire une opération déjà réalisée. |
| **Log** | Le journal qui raconte les étapes exécutées et les erreurs éventuelles. |

---

## ✅ À retenir absolument

**`YAML` décide quand travailler → `Python` exécute le travail → `JSON` conserve le résultat → `JavaScript` lit les données → `HTML/CSS` les affichent → `GitHub Pages` rend le site accessible.**

Et pour **Mon Panier** : le catalogue des enseignes est actualisé gratuitement ; le programme prépare normalement quatre semaines à la fois avec un appel texte IA, puis publie les semaines suivantes depuis les sauvegardes, sans nouveaux tokens.

**Dernière révision de ce guide : 18 octobre 2026.** Pour savoir ce qui s'est *réellement* exécuté ou publié, consulter les [exécutions GitHub Actions](https://github.com/jaycikomo/mon-panier/actions) et les JSON du dépôt.
