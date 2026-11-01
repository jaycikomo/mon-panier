# Mon Panier — API familiale (branche de préparation)

L'application publique GitHub Pages reste inchangée sur `main`. Cette branche fournit un backend expérimental, à valider sur la VM `mon-panier-api` avant raccordement des téléphones.

## Architecture
- PostgreSQL 17 : données familiales, non publié sur l'hôte.
- FastAPI : authentification, membres, courses, recettes, menus, consommations, suggestions.
- API accessible **uniquement sur 127.0.0.1:8085** pendant les essais.
- HTTPS sur l'IP publique Freebox **non configuré à ce stade**.
- Aucun secret commité : `.env` reste sur la VM et doit être sauvegardé séparément.

## Déploiement initial sur la VM
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
- `PUT /api/households/{id}/pantry/{ingredient_key}`
- `PUT /api/households/{id}/recipes/{recipe_key}`
- `PUT /api/households/{id}/plans/{date}/{breakfast|lunch|dinner|snack}`
- `POST /api/households/{id}/consumptions`
- `GET /api/households/{id}/suggestions?day=...&kind=...&week=...`

## Restant à développer et tester
1. Tests réels du backend et premiers comptes.
2. Connexion de la PWA existante à l'API : migration volontaire des données locales, affichage de la synchronisation et résolution de conflits.
3. Tableau de bord repas mobile, confirmation « déjà consommé », substitutions des recettes et rétablissement du menu original.
4. Reverse proxy HTTPS avec certificat IP renouvelé automatiquement, contrôle d'accès, rate limiting et sauvegardes.
