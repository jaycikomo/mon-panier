# Mon Panier — API familiale et archives

L'application publique GitHub Pages et la VM familiale sont déjà en service. Les améliorations sont préparées sur `feature/stocks-archives-favoris` et doivent être déployées côté API avant leur publication sur `main`.

## Architecture
- PostgreSQL 17 : données familiales, non publié sur l'hôte.
- FastAPI : authentification, membres, courses, recettes, menus, consommations, suggestions.
- FastAPI accessible **uniquement sur 127.0.0.1:8085** depuis l'hôte, via Nginx HTTPS sur le port public 443.
- PostgreSQL est isolé sur le réseau Docker, sans port public.
- Aucun secret commité : `.env` reste sur la VM et doit être sauvegardé séparément.

## Déploiement initial sur une VM neuve
```sh
cd /opt/mon-panier
apt-get install -y git
git clone --depth 1 --branch feature/api-familiale --single-branch https://github.com/jaycikomo/mon-panier.git source
grep -q '^JWT_SECRET=' .env || printf 'JWT_SECRET=%s\n' "$(openssl rand -hex 48)" >> .env
grep -q '^BOOTSTRAP_TOKEN=' .env || printf 'BOOTSTRAP_TOKEN=%s\n' "$(openssl rand -hex 48)" >> .env
grep -q '^CORS_ORIGINS=' .env || printf 'CORS_ORIGINS=https://jaycikomo.github.io\n' >> .env
chmod 600 .env
cp -a compose.yaml compose.db-only.backup.yaml
cp source/backend/compose.full.yml compose.yaml
docker compose config -q
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U monpanier -d monpanier < source/backend/schema.sql
docker compose up -d --build api
curl -fsS http://127.0.0.1:8085/health
```

## Mise à niveau 002 — magasins, favoris, archives

Sur la VM `mon-panier-api` (jamais sur le nœud Proxmox `pve`), sauvegarder la base avant toute évolution. Les commandes supposent que le dépôt est déjà présent sous `/opt/mon-panier/source` et que l’utilisateur est root.

```sh
hostname
cd /opt/mon-panier
install -d -m 700 /var/backups/mon-panier
umask 077
docker compose exec -T db pg_dump -U monpanier -d monpanier -Fc > /var/backups/mon-panier/avant-evolution-002.dump
test -s /var/backups/mon-panier/avant-evolution-002.dump
docker compose exec -T db pg_restore --list < /var/backups/mon-panier/avant-evolution-002.dump > /dev/null
cd /opt/mon-panier/source
git fetch origin feature/stocks-archives-favoris
git switch -c feature/stocks-archives-favoris --track origin/feature/stocks-archives-favoris
cd /opt/mon-panier
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U monpanier -d monpanier < source/backend/migrations/002_stores_archives_favorites.sql
docker compose up -d --build api
docker compose ps
curl -fsS http://127.0.0.1:8085/health
curl -fsS --resolve 82.66.229.233:443:127.0.0.1 https://82.66.229.233/health
```

Cette migration est **additive, idempotente**, et ne supprime aucune famille, recette ou achat. Ne pas réexécuter `schema.sql` comme opération de mise à jour. Vérifier que la base et l'API répondent avant de copier les fichiers de l'interface en prévisualisation, puis avant de publier la branche dans `main`.

```sh
install -d -m 755 /var/www/mon-panier-preview
install -m 644 /opt/mon-panier/source/index.html /var/www/mon-panier-preview/index.html
install -m 644 /opt/mon-panier/source/family-sync.js /var/www/mon-panier-preview/family-sync.js
curl -s -o /dev/null -w "Page test : HTTP %{http_code}\\n" --resolve 82.66.229.233:443:127.0.0.1 https://82.66.229.233/essai-famille
```

- Chaque produit possède quatre cases de signalement **manuel** « pas disponible » (Lidl, Aldi, Netto, Intermarché). Ce ne sont pas des informations de stock vérifiées.
- Les étoiles sont partagées dans `favorite_recipes`.
- Chaque semaine archivée et ses définitions de recettes sont enregistrées dans `weekly_recipe_archives`. L'envoi est retenté lors de la reconnexion de l'application ; 52 semaines maximum sont renvoyées au client.
- La navigation « Mon compte » permet de se connecter à la famille et de la gérer.

## Sécurité
- Exposer seulement un reverse proxy HTTPS sur 443, après tests des comptes et protections contre tentatives répétées de connexion.
- Ne **jamais** rediriger la Freebox vers les ports 5432, 8085, 8006 ou 22.
- Les routes d'écriture sont réservées aux membres authentifiés ; l'initialisation exige BOOTSTRAP_TOKEN et ne peut être effectuée qu'une fois.
- L'API retourne un jeton Bearer expirant après 7 jours. Le futur client doit prendre en charge déconnexion, erreurs 401 et conflits 409.
- Mettre en place `pg_dump` quotidien et restauration testée avant usage familial réel.
- Les achats cochés ne représentent pas nécessairement le stock restant : la table `pantry_items` est indépendante.
- Les valeurs nutritionnelles proviennent des recettes importées et restent des **estimations**.

## Endpoints principaux
- `GET /health`
- `POST /api/bootstrap`, `POST /api/login`, `POST /api/join`
- `GET /api/me`, `PUT /api/me/goals`
- `POST /api/households/{id}/invitations`
- `GET /api/households/{id}/snapshot?week=YYYY-MM-DD`
- `GET /api/households/{id}/events?after=N` : événements à interroger toutes les quelques secondes côté client
- `PUT /api/households/{id}/shopping/{week}/{ingredient_key}`
- `PUT /api/households/{id}/favorites/{recipe_key}`
- `GET /api/households/{id}/archives`
- `PUT /api/households/{id}/archives/{monday}`
- `PUT /api/households/{id}/pantry/{ingredient_key}`
- `PUT /api/households/{id}/recipes/{recipe_key}`
- `PUT /api/households/{id}/plans/{date}/{breakfast|lunch|dinner|snack}`
- `POST /api/households/{id}/consumptions`
- `GET /api/households/{id}/suggestions?day=...&kind=...&week=...`

## Restant à développer et tester
- Tableau de bord repas mobile, confirmation « déjà consommé » et adaptations guidées par les achats.
- Vérifier périodiquement le renouvellement du certificat IP à durée courte.
- Automatiser les sauvegardes PostgreSQL et tester leur restauration.
