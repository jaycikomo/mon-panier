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
- L'API retourne un jeton d'accès de 15 minutes, automatiquement renouvelable grâce à une session de 60 jours d'inactivité (rotation à chaque ouverture). Un changement de mot de passe invalide les sessions actives. Le client gère les erreurs 401 et 409.
- Activer le timer systemd de sauvegarde quotidienne. Une vérification `pg_restore --list` ne remplace pas un test de restauration intégral périodique.
- Les achats cochés ne représentent pas nécessairement le stock restant : la table `pantry_items` est indépendante.
- Les valeurs nutritionnelles proviennent des recettes importées et restent des **estimations**.

## Endpoints principaux
- `GET /health`
- `POST /api/bootstrap`, `POST /api/login`, `POST /api/join`
- `POST /api/session/refresh`, `POST /api/session/logout`
- `POST /api/password/change`
- `POST /api/password-reset/request`, `POST /api/password-reset/confirm`
- `GET /api/me`, `PUT /api/me/goals`
- `POST /api/households/{id}/invitations`
- `GET /api/households/{id}/snapshot?week=YYYY-MM-DD`
- `GET /api/households/{id}/events?after=N` : événements à interroger toutes les quelques secondes côté client
- `PUT /api/households/{id}/shopping/{week}/{ingredient_key}`
- `PUT /api/households/{id}/favorites/{recipe_key}`
- `GET/PUT /api/households/{id}/week-menus/{monday}`
- `PUT /api/households/{id}/recipe-progress/{monday}/{recipe_key}`
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
- Planifier des restaurations complètes sur une VM de test et surveiller l'espace disque.
- Configurer le stockage hors VM après choix du point de montage Proxmox/NAS.
- Configurer un relais SMTP sécurisé pour activer le mot de passe oublié.

## Mise à niveau 003 — menu familial, comptes et recettes faites/à faire

**Ne pas lancer la migration 003 avant d'avoir confirmé le succès de la version 002 et une nouvelle sauvegarde.** Depuis la VM `mon-panier-api` en root :

```sh
cd /opt/mon-panier
install -d -m 700 /var/backups/mon-panier
umask 077
docker compose exec -T db pg_dump -U monpanier -d monpanier -Fc > /var/backups/mon-panier/avant-migration-003.dump
test -s /var/backups/mon-panier/avant-migration-003.dump
docker compose exec -T db pg_restore --list < /var/backups/mon-panier/avant-migration-003.dump > /dev/null
cd /opt/mon-panier/source
git status --short
git pull --ff-only
cd /opt/mon-panier
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U monpanier -d monpanier < source/backend/migrations/003_family_menu_sessions_recipe_progress.sql
docker compose up -d --build api
curl -fsS http://127.0.0.1:8085/health
```

Les menus actuels et leurs définitions de recettes sont enregistrés pour la famille. Les coches « Faite » / « À faire » sont hebdomadaires ; les étoiles sont indépendantes et persistent entre les semaines. Archives et favoris sont conservés sur le serveur. L'accueil va directement au planning ; « Mes commerces » reste dans le menu et « Archives » est placé en dernier.

### Rester connecté et récupérer son compte

Les jetons d'accès ont une durée de vie courte ; la session est renouvelée automatiquement lors d'une utilisation régulière. La session de renouvellement expire après 60 jours d'inactivité, ou immédiatement après une déconnexion / réinitialisation du mot de passe. Une application web ne peut promettre une session absolument infinie en toute sécurité.

L'envoi d'un lien « mot de passe oublié » demande de configurer, **uniquement dans le fichier .env privé de la VM** :

- `PANIER_SMTP_HOST` : serveur SMTP
- `PANIER_SMTP_PORT` : 587 (STARTTLS) ou 465 (TLS direct)
- `PANIER_SMTP_USER` et `PANIER_SMTP_PASSWORD` : compte autorisé à envoyer
- `PANIER_SMTP_FROM` : adresse d'envoi
- `PANIER_RESET_URL` : `https://jaycikomo.github.io/mon-panier/` par défaut

Le code de récupération est aléatoire, stocké seulement sous forme hachée, envoyé par e-mail, valable 30 minutes et utilisable une fois. Un délai de 15 minutes limite la répétition des demandes pour un même compte. Sans SMTP, cette fonction indique explicitement qu'elle n'est pas encore disponible. Ne jamais envoyer les identifiants SMTP dans une conversation ni les commiter dans Git.

Après vérification de `docker compose config -q` et comparaison des modifications locales éventuelles, intégrer les variables `PANIER_SMTP_*` à la configuration active de l'API. Ne pas remplacer le `compose.yaml` actif sans vérifier les différences avec le fichier versionné.

### Sauvegardes de nuit

Les fichiers versionnés :

- `backend/backup/mon-panier-backup.sh`
- `backend/backup/mon-panier-backup.service`
- `backend/backup/mon-panier-backup.timer`

Installation contrôlée :

```sh
cd /opt/mon-panier
install -m 700 source/backend/backup/mon-panier-backup.sh /usr/local/sbin/mon-panier-backup
install -m 644 source/backend/backup/mon-panier-backup.service /etc/systemd/system/mon-panier-backup.service
install -m 644 source/backend/backup/mon-panier-backup.timer /etc/systemd/system/mon-panier-backup.timer
systemctl daemon-reload
systemctl start mon-panier-backup.service
systemctl enable --now mon-panier-backup.timer
systemctl list-timers mon-panier-backup.timer --no-pager
ls -lh /var/backups/mon-panier/daily/
```

Le timer déclenche une sauvegarde PostgreSQL vers 03h15, avec retard aléatoire maximum de 15 minutes, et une exécution de rattrapage si la VM était éteinte. Les fichiers sont créés avec droits restreints et vérifiés avec `pg_restore --list`. **Aucune sauvegarde n'est automatiquement supprimée** : surveiller la place disque.

Une deuxième copie hors VM est possible avec `PANIER_OFFSITE_DIR`, qui doit pointer sur un vrai point de montage sous `/mnt/` (NAS, stockage indépendant) ; le script refuse d'écrire dans un dossier local non monté. La cible reste à choisir et monter avec l'administrateur Proxmox.
