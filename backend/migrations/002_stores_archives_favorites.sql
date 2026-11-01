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
