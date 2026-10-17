# Mon Panier — recettes générées chaque semaine par IA

## Architecture
- Site existant : GitHub Pages et `index.html`, utilisable même sans IA.
- Générateur : `scripts/generate_ai_week.py`, exécuté **côté GitHub Actions**, jamais dans le navigateur.
- Catalogue de produits/macros : lu dans `index.html`.
- Sorties publiques : `data/ai/latest.json` et `data/ai/weeks/AAAA-MM-JJ.json`.
- Photos des plats : `images/ia/AAAA-MM-JJ/` (jusqu'à 7 dîners par semaine), générées uniquement si l'API Images fonctionne.
- Le site lit `latest.json` depuis GitHub ; il garde une copie des recettes et archives localement pour la consultation ultérieure.

## Activation (une seule fois)
1. Créez une clé secrète API depuis https://platform.openai.com/api-keys . **L'API est facturée séparément de ChatGPT**, selon les modèles et la consommation. Activez la facturation API si nécessaire, et définissez votre budget dans la plateforme.
2. Ouvrez https://github.com/jaycikomo/mon-panier/settings/secrets/actions .
3. Cliquez sur **New repository secret**, nom **OPENAI_API_KEY**, valeur = votre clé API. Enregistrez.
4. Ouvrez https://github.com/jaycikomo/mon-panier/actions/workflows/recettes-ia.yml puis **Run workflow**, branche `main`. Cela créera les recettes de la semaine en cours.
5. Patientez jusqu'à ce que l'exécution soit verte. Vérifiez la présence de `data/ai/latest.json` sur GitHub. Actualisez l'application dans Safari.
6. Chaque lundi, GitHub Actions exécutera le même processus automatiquement (horaire UTC, légère variation possible). La mise à jour du fichier sur GitHub est récupérée directement par l'application.

## Photos et coût
Le générateur tente de créer jusqu'à **7 photos de dîners** avec le modèle Images API `gpt-image-1-mini`, qualité `low` ; les autres repas réutilisent les illustrations d'ingrédients. En cas d'échec, les recettes continuent de fonctionner avec les images existantes. Les photos sont des **illustrations générées**, pas les emballages réels des magasins.

Pour réduire les dépenses, définissez une variable de dépôt `AI_IMAGE_COUNT` égale à `0` ou `3` dans **Settings → Secrets and variables → Actions → Variables**. Le script limite à 7 maximum. L'API facture les appels aux recettes et aux images ; l'application ne peut pas garantir un prix fixe.

## Fonctionnement nutritionnel
L'IA rédige 20 recettes originales par semaine : 3 petits-déjeuners, 7 déjeuners, 3 collations, 7 dîners. Un algorithme calcule les macronutriments à partir des valeurs pour 100 g dans le catalogue, puis compose 7 journées visant **1915 kcal, 130 g de protéines, 180 g de glucides et 75 g de lipides**. Si aucune composition n'est assez proche ou qu'une réponse est invalide, le script échoue et **ne publie pas** de nouvelles recettes erronées. L'application conserve alors ses menus classiques. Les estimations ne remplacent pas les étiquettes nutritionnelles.

## Historique et partage
Le dépôt conserve les fichiers hebdomadaires dans `data/ai/weeks/`. L'application conserve aussi les recettes consultées dans le `localStorage` du navigateur pour rendre les anciens menus archivés consultables. Cela ne synchronise pas les coches entre appareils : le bouton Partager envoie une copie de la liste. Une vraie synchronisation familiale demanderait une base distante et une authentification.

## Dépannage
- **L'interface affiche “IA en préparation”** : vérifier que le secret `OPENAI_API_KEY` existe, que le workflow s'est exécuté avec succès, et que `data/ai/latest.json` correspond au lundi de cette semaine.
- **Workflow rouge** : dans **Actions → Mon Panier - Recettes IA du lundi**, ouvrir les logs. Un manque de crédits API, un accès au modèle indisponible, un JSON invalide ou une permission GitHub insuffisante peut empêcher la publication.
- **Images absentes** : vérifier l'accès à Images API et `AI_IMAGE_COUNT`. Le reste de l'application reste utilisable.
- **Site ancien en cache** : actualisez Safari puis rouvrez le site.
- **Automatisation désactivée** : GitHub peut désactiver les workflows planifiés des dépôts publics après 60 jours d'inactivité ; la réactiver dans l'onglet Actions si besoin.

**Sécurité :** ne commitez jamais la clé API dans `index.html`, un fichier du dépôt ou un lien de partage ; utilisez uniquement GitHub Secrets.
