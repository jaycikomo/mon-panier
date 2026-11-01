"""Mon Panier familial — API privée PostgreSQL (version initiale)."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

import jwt
import psycopg
from argon2 import PasswordHasher, exceptions as argon_errors
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]
BOOTSTRAP_TOKEN = os.environ["BOOTSTRAP_TOKEN"]
ORIGINS = [x.strip() for x in os.environ.get("CORS_ORIGINS", "").split(",") if x.strip()]
if len(JWT_SECRET) < 40 or len(BOOTSTRAP_TOKEN) < 40 or not ORIGINS:
    raise RuntimeError("Secrets ou CORS_ORIGINS manquants / trop courts")

app = FastAPI(title="Mon Panier — API familiale", version="0.1.0",
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "X-Bootstrap-Token"])
bearer = HTTPBearer(auto_error=False)
hasher = PasswordHasher()
MealType = Literal["breakfast", "lunch", "dinner", "snack"]


def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5)


def error(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def normalize_email(email: str) -> str:
    return str(email).strip().lower()


def issue_token(account_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(account_id), "iat": now, "exp": now + timedelta(days=7)},
                      JWT_SECRET, algorithm="HS256")


def actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        error(401, "Authentification nécessaire")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        error(401, "Session expirée ou invalide")


def member(conn, household_id: UUID, account_id: UUID, owner: bool = False):
    row = conn.execute(
        "SELECT role FROM household_members WHERE household_id=%s AND account_id=%s",
        (household_id, account_id)).fetchone()
    if not row or (owner and row["role"] != "owner"):
        error(403, "Accès interdit à cette famille")
    return row["role"]


def event(conn, household_id: UUID, account_id: UUID, kind: str, payload: dict):
    conn.execute(
        "INSERT INTO sync_events(household_id,actor_id,kind,payload) VALUES (%s,%s,%s,%s)",
        (household_id, account_id, kind, Jsonb(payload)))


class Identity(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)


class Bootstrap(Identity):
    household_name: str = Field(default="Notre famille", min_length=1, max_length=120)


class Login(BaseModel):
    email: EmailStr
    password: str


class Join(Identity):
    invitation: str = Field(min_length=20, max_length=200)


class Shopping(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity_text: str = Field(default="", max_length=100)
    store_name: str = Field(default="", max_length=100)
    is_bought: bool = False
    expected_version: int | None = Field(default=None, ge=0)


class Ingredient(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    g: float = Field(ge=0, le=10000)


class Recipe(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    meal_type: MealType
    ingredients: list[Ingredient] = Field(min_length=1, max_length=100)
    nutrition: dict[str, float]
    instructions: str = Field(default="", max_length=20000)


class MealPlan(BaseModel):
    base_recipe_key: str = Field(min_length=1, max_length=100)
    selected_recipe_key: str = Field(min_length=1, max_length=100)
    mode: Literal["base", "adapted"] = "base"
    skipped: bool = False


class Consumption(BaseModel):
    meal_date: date
    meal_type: MealType
    recipe_key: str | None = Field(default=None, max_length=100)
    description: str = Field(default="", max_length=300)
    nutrition: dict[str, float] = Field(default_factory=dict)


class Pantry(BaseModel):
    quantity: float = Field(ge=0, le=1000000)
    unit: str = Field(default="g", min_length=1, max_length=20)


class Goals(BaseModel):
    kcal_target: int = Field(ge=1000, le=6000)
    protein_target: int = Field(ge=0, le=400)
    carb_target: int = Field(ge=0, le=800)
    fat_target: int = Field(ge=0, le=300)


@app.get("/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.post("/api/bootstrap")
def bootstrap(data: Bootstrap, x_bootstrap_token: str = Header(alias="X-Bootstrap-Token")):
    if not hmac.compare_digest(x_bootstrap_token, BOOTSTRAP_TOKEN):
        error(403, "Clé d'initialisation incorrecte")
    with db() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(3412980)")
        if conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
            error(409, "Initialisation déjà effectuée")
        account = conn.execute(
            "INSERT INTO accounts(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING id",
            (normalize_email(data.email), data.display_name, hasher.hash(data.password))).fetchone()
        family = conn.execute(
            "INSERT INTO households(name) VALUES (%s) RETURNING id",
            (data.household_name,)).fetchone()
        conn.execute(
            "INSERT INTO household_members(household_id,account_id,role) VALUES (%s,%s,'owner')",
            (family["id"], account["id"]))
    return {"access_token": issue_token(account["id"]), "household_id": family["id"]}


@app.post("/api/login")
def login(data: Login):
    with db() as conn:
        account = conn.execute(
            "SELECT id,password_hash,display_name FROM accounts WHERE email=%s",
            (normalize_email(data.email),)).fetchone()
        if not account:
            error(401, "Identifiants incorrects")
        try:
            hasher.verify(account["password_hash"], data.password)
        except (argon_errors.VerificationError, argon_errors.InvalidHashError):
            error(401, "Identifiants incorrects")
    return {"access_token": issue_token(account["id"]), "display_name": account["display_name"]}


@app.get("/api/me")
def me(account_id: UUID = Depends(actor)):
    with db() as conn:
        profile = conn.execute(
            """SELECT id,email,display_name,kcal_target,protein_target,carb_target,fat_target
               FROM accounts WHERE id=%s""", (account_id,)).fetchone()
        if not profile:
            error(401, "Compte introuvable")
        families = conn.execute(
            """SELECT h.id,h.name,m.role FROM households h
               JOIN household_members m ON m.household_id=h.id
               WHERE m.account_id=%s""", (account_id,)).fetchall()
    return {"profile": profile, "households": families}


@app.put("/api/me/goals")
def goals(data: Goals, account_id: UUID = Depends(actor)):
    with db() as conn:
        conn.execute(
            """UPDATE accounts SET kcal_target=%s,protein_target=%s,
               carb_target=%s,fat_target=%s WHERE id=%s""",
            (data.kcal_target, data.protein_target, data.carb_target,
             data.fat_target, account_id))
    return {"saved": True}


@app.post("/api/households/{hid}/invitations")
def invite(hid: UUID, account_id: UUID = Depends(actor)):
    with db() as conn:
        member(conn, hid, account_id, owner=True)
        token = secrets.token_urlsafe(30)
        digest = hashlib.sha256(token.encode()).hexdigest()
        conn.execute(
            """INSERT INTO invitations(token_hash,household_id,invited_by,expires_at)
               VALUES (%s,%s,%s,now()+interval '48 hours')""",
            (digest, hid, account_id))
    return {"invitation": token, "expires_in_hours": 48}


@app.post("/api/join")
def join(data: Join):
    digest = hashlib.sha256(data.invitation.encode()).hexdigest()
    with db() as conn:
        invite_row = conn.execute(
            """SELECT household_id FROM invitations
               WHERE token_hash=%s AND used_at IS NULL AND expires_at>now() FOR UPDATE""",
            (digest,)).fetchone()
        if not invite_row:
            error(400, "Invitation invalide ou expirée")
        if conn.execute("SELECT 1 FROM accounts WHERE email=%s",
                        (normalize_email(data.email),)).fetchone():
            error(409, "Adresse déjà utilisée")
        account = conn.execute(
            "INSERT INTO accounts(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING id",
            (normalize_email(data.email), data.display_name, hasher.hash(data.password))).fetchone()
        conn.execute(
            "INSERT INTO household_members(household_id,account_id,role) VALUES (%s,%s,'member')",
            (invite_row["household_id"], account["id"]))
        conn.execute("UPDATE invitations SET used_at=now() WHERE token_hash=%s", (digest,))
    return {"access_token": issue_token(account["id"]),
            "household_id": invite_row["household_id"]}


@app.get("/api/households/{hid}/snapshot")
def snapshot(hid: UUID, week: date, account_id: UUID = Depends(actor)):
    with db() as conn:
        member(conn, hid, account_id)
        shopping = conn.execute(
            "SELECT * FROM shopping_items WHERE household_id=%s AND week_key=%s ORDER BY name",
            (hid, week)).fetchall()
        recipes = conn.execute(
            "SELECT * FROM recipes WHERE household_id=%s ORDER BY name", (hid,)).fetchall()
        plans = conn.execute(
            """SELECT * FROM meal_plans WHERE household_id=%s
               AND meal_date BETWEEN %s AND %s ORDER BY meal_date,meal_type""",
            (hid, week, week + timedelta(days=6))).fetchall()
        consumed = conn.execute(
            """SELECT * FROM meal_consumptions WHERE household_id=%s
               AND meal_date BETWEEN %s AND %s ORDER BY consumed_at DESC""",
            (hid, week, week + timedelta(days=6))).fetchall()
        pantry = conn.execute(
            "SELECT * FROM pantry_items WHERE household_id=%s ORDER BY ingredient_key",
            (hid,)).fetchall()
        latest = conn.execute(
            "SELECT COALESCE(max(id),0) AS id FROM sync_events WHERE household_id=%s",
            (hid,)).fetchone()["id"]
    return {"shopping": shopping, "recipes": recipes, "plans": plans,
            "consumed": consumed, "pantry": pantry, "last_event_id": latest}


@app.get("/api/households/{hid}/events")
def changes(hid: UUID, after: int = Query(default=0, ge=0),
            account_id: UUID = Depends(actor)):
    with db() as conn:
        member(conn, hid, account_id)
        rows = conn.execute(
            """SELECT id,kind,payload,created_at FROM sync_events
               WHERE household_id=%s AND id>%s ORDER BY id LIMIT 200""",
            (hid, after)).fetchall()
    return {"events": rows}


@app.put("/api/households/{hid}/shopping/{week}/{key}")
def set_shopping(hid: UUID, week: date, key: str,
                 data: Shopping, account_id: UUID = Depends(actor)):
    if not 1 <= len(key) <= 100:
        error(422, "Identifiant invalide")
    with db() as conn:
        member(conn, hid, account_id)
        existing = conn.execute(
            """SELECT id,version FROM shopping_items WHERE household_id=%s
               AND week_key=%s AND ingredient_key=%s FOR UPDATE""",
            (hid, week, key)).fetchone()
        if existing and data.expected_version is not None and existing["version"] != data.expected_version:
            error(409, "Produit modifié sur un autre appareil : actualiser la liste")
        if not existing and data.expected_version not in (None, 0):
            error(409, "Liste actualisée sur un autre appareil")
        if existing:
            row = conn.execute(
                """UPDATE shopping_items SET name=%s,quantity_text=%s,store_name=%s,
                   is_bought=%s,bought_by=%s,updated_by=%s,updated_at=now(),
                   version=version+1 WHERE id=%s RETURNING *""",
                (data.name, data.quantity_text, data.store_name, data.is_bought,
                 account_id if data.is_bought else None, account_id, existing["id"])).fetchone()
        else:
            row = conn.execute(
                """INSERT INTO shopping_items
                   (household_id,week_key,ingredient_key,name,quantity_text,store_name,
                    is_bought,bought_by,updated_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (hid, week, key, data.name, data.quantity_text, data.store_name,
                 data.is_bought, account_id if data.is_bought else None, account_id)).fetchone()
        event(conn, hid, account_id, "shopping.changed",
              {"week": week.isoformat(), "key": key, "is_bought": data.is_bought,
               "version": row["version"]})
    return row


@app.delete("/api/households/{hid}/shopping/{week}/{key}")
def delete_shopping(hid: UUID, week: date, key: str, account_id: UUID = Depends(actor)):
    """Remove a manual shopping item and notify the other family devices."""
    if not 1 <= len(key) <= 100 or not key.startswith("custom-"):
        error(422, "Seuls les ajouts personnels peuvent être supprimés")
    with db() as conn:
        member(conn, hid, account_id)
        deleted = conn.execute(
            """DELETE FROM shopping_items WHERE household_id=%s
               AND week_key=%s AND ingredient_key=%s RETURNING id""",
            (hid, week, key)).fetchone()
        if deleted:
            event(conn, hid, account_id, "shopping.deleted",
                  {"week": week.isoformat(), "key": key})
    return {"deleted": bool(deleted)}


@app.put("/api/households/{hid}/pantry/{key}")
def set_pantry(hid: UUID, key: str, data: Pantry, account_id: UUID = Depends(actor)):
    if not 1 <= len(key) <= 100:
        error(422, "Identifiant invalide")
    with db() as conn:
        member(conn, hid, account_id)
        conn.execute(
            """INSERT INTO pantry_items(household_id,ingredient_key,quantity,unit)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT (household_id,ingredient_key) DO UPDATE
               SET quantity=EXCLUDED.quantity,unit=EXCLUDED.unit,updated_at=now()""",
            (hid, key, data.quantity, data.unit))
        event(conn, hid, account_id, "pantry.changed",
              {"key": key, "quantity": data.quantity, "unit": data.unit})
    return {"saved": True}


@app.put("/api/households/{hid}/recipes/{key}")
def set_recipe(hid: UUID, key: str, data: Recipe,
               account_id: UUID = Depends(actor)):
    if not 1 <= len(key) <= 100:
        error(422, "Identifiant invalide")
    with db() as conn:
        member(conn, hid, account_id)
        conn.execute(
            """INSERT INTO recipes
               (household_id,recipe_key,name,meal_type,ingredients,nutrition,instructions)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (household_id,recipe_key) DO UPDATE SET
               name=EXCLUDED.name,meal_type=EXCLUDED.meal_type,
               ingredients=EXCLUDED.ingredients,nutrition=EXCLUDED.nutrition,
               instructions=EXCLUDED.instructions,updated_at=now()""",
            (hid, key, data.name, data.meal_type,
             Jsonb([i.model_dump() for i in data.ingredients]),
             Jsonb(data.nutrition), data.instructions))
        event(conn, hid, account_id, "recipe.changed", {"key": key})
    return {"saved": True}


@app.put("/api/households/{hid}/plans/{day}/{kind}")
def set_plan(hid: UUID, day: date, kind: MealType, data: MealPlan,
             account_id: UUID = Depends(actor)):
    with db() as conn:
        member(conn, hid, account_id)
        current = conn.execute(
            """SELECT base_recipe_key FROM meal_plans
               WHERE household_id=%s AND meal_date=%s AND meal_type=%s FOR UPDATE""",
            (hid, day, kind)).fetchone()
        baseline = current["base_recipe_key"] if current else data.base_recipe_key
        if data.mode == "base" and data.selected_recipe_key != baseline:
            error(422, "Le mode de base doit utiliser la recette initiale")
        row = conn.execute(
            """INSERT INTO meal_plans
               (household_id,meal_date,meal_type,base_recipe_key,selected_recipe_key,
                mode,skipped,updated_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (household_id,meal_date,meal_type) DO UPDATE SET
               selected_recipe_key=EXCLUDED.selected_recipe_key,mode=EXCLUDED.mode,
               skipped=EXCLUDED.skipped,updated_by=EXCLUDED.updated_by,
               updated_at=now()
               RETURNING *""",
            (hid, day, kind, baseline, data.selected_recipe_key, data.mode,
             data.skipped, account_id)).fetchone()
        event(conn, hid, account_id, "plan.changed",
              {"date": day.isoformat(), "meal_type": kind, "mode": data.mode})
    return row


@app.post("/api/households/{hid}/consumptions")
def consume(hid: UUID, data: Consumption, account_id: UUID = Depends(actor)):
    with db() as conn:
        member(conn, hid, account_id)
        row = conn.execute(
            """INSERT INTO meal_consumptions
               (household_id,account_id,meal_date,meal_type,recipe_key,description,nutrition)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (hid, account_id, data.meal_date, data.meal_type, data.recipe_key,
             data.description, Jsonb(data.nutrition))).fetchone()
        event(conn, hid, account_id, "meal.consumed",
              {"date": data.meal_date.isoformat(), "meal_type": data.meal_type})
    return row


@app.get("/api/households/{hid}/suggestions")
def suggestions(hid: UUID, day: date, kind: MealType,
                week: date, account_id: UUID = Depends(actor)):
    """Rank saved recipes by purchased ingredients and remaining personal kcal.
    Estimated numbers are provided by the recipe catalogue, not verified product labels.
    """
    with db() as conn:
        member(conn, hid, account_id)
        bought = conn.execute(
            """SELECT ingredient_key FROM shopping_items
               WHERE household_id=%s AND week_key=%s AND is_bought=true""",
            (hid, week)).fetchall()
        stocked = conn.execute(
            "SELECT ingredient_key FROM pantry_items WHERE household_id=%s AND quantity>0",
            (hid,)).fetchall()
        recipes = conn.execute(
            "SELECT * FROM recipes WHERE household_id=%s AND meal_type=%s",
            (hid, kind)).fetchall()
        consumed = conn.execute(
            "SELECT nutrition FROM meal_consumptions WHERE household_id=%s AND account_id=%s AND meal_date=%s",
            (hid, account_id, day)).fetchall()
        goals = conn.execute(
            "SELECT kcal_target,protein_target,carb_target,fat_target FROM accounts WHERE id=%s",
            (account_id,)).fetchone()
    available = {x["ingredient_key"] for x in bought} | {x["ingredient_key"] for x in stocked}
    eaten = sum(float(x["nutrition"].get("cal", 0)) for x in consumed)
    remaining = max(0, goals["kcal_target"] - eaten)
    ranked = []
    for recipe in recipes:
        ingredients = [i["id"] for i in recipe["ingredients"] if "id" in i]
        covered = [x for x in ingredients if x in available]
        missing = [x for x in ingredients if x not in available]
        coverage = len(covered) / max(1, len(ingredients))
        kcal = float(recipe["nutrition"].get("cal", 0))
        penalty = max(0, kcal - remaining) / max(1, goals["kcal_target"])
        ranked.append({
            "recipe_key": recipe["recipe_key"], "name": recipe["name"],
            "nutrition": recipe["nutrition"], "available_ratio": round(coverage, 2),
            "missing_ingredients": missing, "estimated_kcal_remaining": remaining,
            "score": round(coverage * 100 - penalty * 40, 1)
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return {"suggestions": ranked[:12],
            "note": "Estimations nutritionnelles ; un achat coché ne garantit pas le stock restant."}
