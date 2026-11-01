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
