# Mon Panier — quatre semaines en une seule génération IA

## Fonctionnement depuis le 18 octobre 2026
- **Un lundi sur quatre**, si aucune semaine sauvegardée n'est disponible, GitHub appelle **une seule fois** le modèle texte GPT-5 mini pour préparer **32 recettes de base**.
- Le script crée et valide immédiatement quatre semaines de menus de 7 jours, avec **20 recettes sélectionnées par semaine** : petit-déjeuner, déjeuner, collation et dîner.
- Les recettes de base peuvent revenir à plusieurs semaines, mais les choix et combinaisons changent. Ce ne sont pas 80 nouvelles recettes distinctes.
- Les quatre semaines sont enregistrées dans `data/ai/weeks/AAAA-MM-JJ.json` et le lot dans `data/ai/batches/AAAA-MM-JJ.json`.
- **Chaque lundi suivant**, GitHub copie la semaine préenregistrée dans `data/ai/latest.json`. **Zéro token OpenAI** les semaines 2, 3 et 4.
- Le lundi après la quatrième semaine, un **nouveau lot de quatre semaines** est préparé si le secret API est toujours actif.
- Les fichiers hebdomadaires sont conservés ; l'interface affiche « Semaine 1/4 » à « Semaine 4/4 ».
- Le catalogue Lidl / Aldi / Netto est actualisé le dimanche avec des sources gratuites ; **aucun stock local n'est garanti**.

## Calendrier du premier lot
Les prochaines dates sont :
1. **Lundi 19 octobre 2026** : génération payante unique du lot (semaines du 19 et du 26 octobre, du 2 et du 9 novembre).
2. **Lundi 26 octobre 2026** : publication depuis la sauvegarde, sans appel IA.
3. **Lundi 2 novembre 2026** : publication depuis la sauvegarde, sans appel IA.
4. **Lundi 9 novembre 2026** : publication depuis la sauvegarde, sans appel IA.
5. **Lundi 16 novembre 2026** : nouveau lot de quatre semaines, un appel IA.

Ces dates restent conditionnées à l'exécution réussie du générateur et au fonctionnement de GitHub Actions.

## GitHub Actions
- [Menus du lundi depuis sauvegarde mensuelle](https://github.com/jaycikomo/mon-panier/actions/workflows/recettes-ia.yml) : `37 5 * * 1` (05 h 37 UTC, retard possible).
- [Catalogue gratuit des enseignes](https://github.com/jaycikomo/mon-panier/actions/workflows/catalogue-enseignes.yml) : `20 5 * * 0` (dimanche, UTC).
- [Tests sans IA](https://github.com/jaycikomo/mon-panier/actions/workflows/tests-menus.yml) : vérifie les quatre semaines et le cache.

Si une nouvelle semaine est déjà sauvegardée, le générateur la publie **avant même de vérifier la clé API**. Si elle est déjà publiée, il ne fait rien. Lancer manuellement le workflow dans la semaine ne provoque donc pas de nouvelle facture tant que cette semaine est déjà enregistrée.

## Coûts et sécurité
- **1 appel de génération texte pour 4 semaines** dans le fonctionnement normal, avec `gpt-5-mini`.
- **0 génération d'image IA** (le code de génération d'images a été retiré).
- **0 token pour consulter les recettes, cocher les courses et signaler un article absent chez Lidl / Aldi / Netto**.
- L'API OpenAI est facturée séparément de ChatGPT Plus. Le tarif réel dépend des tokens consommés.
- Le workflow ne retente pas automatiquement l'appel payant si la réponse JSON est invalide. Une nouvelle exécution future non sauvegardée peut être facturée ; surveillez la consommation dans [OpenAI API Usage](https://platform.openai.com/usage).
- La clé reste exclusivement dans le secret GitHub `OPENAI_API_KEY`, jamais dans les fichiers publiés.

## Nutrition
Les macros sont recalculées en Python à partir du catalogue générique et les 7 journées visent environ **1 915 kcal, 130 g de protéines, 180 g de glucides et 75 g de lipides par adulte**. Un menu invalide n'est pas publié. Les estimations peuvent différer des étiquettes de marques et des portions réellement consommées.

## Dépannage
- Si `data/ai/latest.json` ne correspond pas au lundi courant, ouvrir le workflow **Menus du lundi depuis sauvegarde mensuelle** et lire son erreur. Sur une semaine déjà enregistrée, il ne doit pas appeler OpenAI.
- En cas de manque de crédit au renouvellement du lot, la génération ne publiera pas une nouvelle semaine et les menus habituels restent disponibles.
- Le site ne synchronise pas les listes de courses entre téléphones : partage par lien = copie, pas synchronisation en temps réel.
- GitHub peut retarder l'exécution planifiée ; actualisez l'application après la publication.
