-- Mon Panier familial — PostgreSQL 17
-- Migration initiale idempotente. Aucune donnée existante n'est supprimée.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS households (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  display_name text NOT NULL,
  password_hash text NOT NULL,
  kcal_target integer NOT NULL DEFAULT 1900 CHECK (kcal_target BETWEEN 1000 AND 6000),
  protein_target integer NOT NULL DEFAULT 130 CHECK (protein_target BETWEEN 0 AND 400),
  carb_target integer NOT NULL DEFAULT 180 CHECK (carb_target BETWEEN 0 AND 800),
  fat_target integer NOT NULL DEFAULT 75 CHECK (fat_target BETWEEN 0 AND 300),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS household_members (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','member')),
  joined_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id, account_id)
);
CREATE TABLE IF NOT EXISTS invitations (
  token_hash text PRIMARY KEY,
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  invited_by uuid NOT NULL REFERENCES accounts(id),
  expires_at timestamptz NOT NULL,
  used_at timestamptz
);
CREATE TABLE IF NOT EXISTS shopping_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  week_key date NOT NULL,
  ingredient_key text NOT NULL CHECK (length(ingredient_key) BETWEEN 1 AND 100),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  quantity_text text NOT NULL DEFAULT '',
  store_name text NOT NULL DEFAULT '',
  is_bought boolean NOT NULL DEFAULT false,
  bought_by uuid REFERENCES accounts(id),
  updated_by uuid REFERENCES accounts(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version bigint NOT NULL DEFAULT 1,
  UNIQUE (household_id,week_key,ingredient_key)
);
CREATE INDEX IF NOT EXISTS idx_shopping_house_week ON shopping_items(household_id,week_key);
CREATE TABLE IF NOT EXISTS pantry_items (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  ingredient_key text NOT NULL,
  quantity numeric(12,2) NOT NULL DEFAULT 0 CHECK (quantity>=0),
  unit text NOT NULL DEFAULT 'g',
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id,ingredient_key)
);
CREATE TABLE IF NOT EXISTS recipes (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  recipe_key text NOT NULL,
  name text NOT NULL,
  meal_type text NOT NULL CHECK (meal_type IN ('breakfast','lunch','dinner','snack')),
  ingredients jsonb NOT NULL CHECK (jsonb_typeof(ingredients)='array'),
  nutrition jsonb NOT NULL CHECK (jsonb_typeof(nutrition)='object'),
  instructions text NOT NULL DEFAULT '',
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id,recipe_key)
);
CREATE INDEX IF NOT EXISTS idx_recipes_meal ON recipes(household_id,meal_type);
CREATE TABLE IF NOT EXISTS meal_plans (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  meal_date date NOT NULL,
  meal_type text NOT NULL CHECK (meal_type IN ('breakfast','lunch','dinner','snack')),
  base_recipe_key text NOT NULL,
  selected_recipe_key text NOT NULL,
  mode text NOT NULL DEFAULT 'base' CHECK (mode IN ('base','adapted')),
  skipped boolean NOT NULL DEFAULT false,
  updated_by uuid REFERENCES accounts(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id,meal_date,meal_type)
);
CREATE TABLE IF NOT EXISTS meal_consumptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  meal_date date NOT NULL,
  meal_type text NOT NULL CHECK (meal_type IN ('breakfast','lunch','dinner','snack')),
  recipe_key text,
  description text NOT NULL DEFAULT '',
  nutrition jsonb NOT NULL DEFAULT '{}'::jsonb,
  consumed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_consumed_day ON meal_consumptions(household_id,account_id,meal_date);
CREATE TABLE IF NOT EXISTS sync_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  actor_id uuid REFERENCES accounts(id),
  kind text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_house_id ON sync_events(household_id,id);


-- Migration additive 002 : statuts magasin, etoiles, archives familiales.
-- Mon Panier : signalements par magasin, favoris et archives familiales.
-- Migration ADDITIVE et idempotente : aucune suppression de donnees.
BEGIN;

ALTER TABLE shopping_items
  ADD COLUMN IF NOT EXISTS unavailable_stores jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS favorite_recipes (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  recipe_key text NOT NULL CHECK (length(recipe_key) BETWEEN 1 AND 100),
  starred boolean NOT NULL DEFAULT true,
  updated_by uuid REFERENCES accounts(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id, recipe_key)
);

CREATE TABLE IF NOT EXISTS weekly_recipe_archives (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  week_key date NOT NULL,
  plan jsonb NOT NULL CHECK (jsonb_typeof(plan) = 'array'),
  recipes jsonb NOT NULL CHECK (jsonb_typeof(recipes) = 'object'),
  archived_by uuid REFERENCES accounts(id),
  archived_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id, week_key)
);
CREATE INDEX IF NOT EXISTS idx_archives_house_week
  ON weekly_recipe_archives (household_id, week_key DESC);

COMMIT;


-- Migration additive 003 : menus, sessions, recuperation et progression recettes.
-- Mise a niveau additive 003 : menu de semaine actif commun a la famille.
-- Aucun DROP / aucune suppression des donnees existantes.
BEGIN;

CREATE TABLE IF NOT EXISTS family_week_menus (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  week_key date NOT NULL,
  plan jsonb NOT NULL CHECK (jsonb_typeof(plan) = 'array'),
  recipes jsonb NOT NULL CHECK (jsonb_typeof(recipes) = 'object'),
  version bigint NOT NULL DEFAULT 1,
  updated_by uuid REFERENCES accounts(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id, week_key)
);

CREATE INDEX IF NOT EXISTS idx_family_week_menus_house
  ON family_week_menus (household_id, week_key DESC);

ALTER TABLE accounts
  ADD COLUMN IF NOT EXISTS auth_revision bigint NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS auth_sessions (
  token_hash text PRIMARY KEY,
  account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  last_used_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_account
  ON auth_sessions(account_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  token_hash text PRIMARY KEY,
  account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  used_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_password_reset_account
  ON password_reset_tokens(account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS weekly_recipe_progress (
  household_id uuid NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  week_key date NOT NULL,
  recipe_key text NOT NULL CHECK (length(recipe_key) BETWEEN 1 AND 100),
  is_done boolean NOT NULL DEFAULT false,
  updated_by uuid REFERENCES accounts(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (household_id,week_key,recipe_key)
);
CREATE INDEX IF NOT EXISTS idx_recipe_progress_house_week
  ON weekly_recipe_progress (household_id,week_key);

ALTER TABLE weekly_recipe_archives
  ADD COLUMN IF NOT EXISTS completed_recipes jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE weekly_recipe_archives
  ADD COLUMN IF NOT EXISTS starred_recipes jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMIT;

