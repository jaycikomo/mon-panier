"""Mon Panier familial — API privée PostgreSQL (version initiale)."""
from __future__ import annotations

import hashlib
import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode
import hmac
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

import jwt
import psycopg
from argon2 import PasswordHasher, exceptions as argon_errors
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Path, Query
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
SMTP_HOST = os.environ.get("PANIER_SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("PANIER_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("PANIER_SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("PANIER_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("PANIER_SMTP_FROM", "").strip()
RESET_URL = os.environ.get("PANIER_RESET_URL", "https://jaycikomo.github.io/mon-panier/")
MAIL_CONFIGURED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM and
                       RESET_URL.startswith("https://") and
                       RESET_URL.startswith(("https://jaycikomo.github.io/mon-panier/",
                                              "https://82.66.229.233/essai-famille")))
logger = logging.getLogger("mon-panier")



def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5)


def error(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def normalize_email(email: str) -> str:
    return str(email).strip().lower()


def issue_token(account_id: UUID) -> str:
    with db() as conn:
        account = conn.execute(
            "SELECT auth_revision FROM accounts WHERE id=%s", (account_id,)).fetchone()
    if not account:
        error(401, "Compte introuvable")
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(account_id), "iat": now, "ver": account["auth_revision"],
                       "exp": now + timedelta(minutes=15)},
                      JWT_SECRET, algorithm="HS256")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(conn, account_id: UUID) -> dict:
    """Rotateable 60-day refresh session; only its SHA-256 digest reaches PostgreSQL."""
    refresh = secrets.token_urlsafe(48)
    conn.execute(
        """INSERT INTO auth_sessions(token_hash, account_id, expires_at)
           VALUES (%s,%s,now()+interval '60 days')""",
        (token_digest(refresh), account_id))
    return {"access_token": issue_token(account_id), "refresh_token": refresh,
            "expires_in": 15 * 60}


def send_password_reset_email(recipient: str, url: str):
    try:
        message = EmailMessage()
        message["From"] = SMTP_FROM
        message["To"] = recipient
        message["Subject"] = "Mon Panier - reinitialisation de votre mot de passe"
        message.set_content(
            "Vous avez demande un nouveau mot de passe Mon Panier.\n\n"
            "Le lien suivant est valable pendant 30 minutes et une seule fois :\n"
            + url + "\n\nSi vous n'etes pas a l'origine de cette demande, ignorez ce message.")
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=12,
                                  context=ssl.create_default_context()) as smtp:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Echec envoi e-mail de reinitialisation Mon Panier")


def actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        error(401, "Authentification nécessaire")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        account_id = UUID(payload["sub"])
        with db() as conn:
            account = conn.execute(
                "SELECT auth_revision FROM accounts WHERE id=%s", (account_id,)).fetchone()
        if not account or int(payload.get("ver", 0)) != account["auth_revision"]:
            error(401, "Session invalidee : reconnectez-vous")
        return account_id
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
    unavailable_stores: list[Literal['aldi', 'lidl-destrousse', 'netto', 'inter']] | None = Field(default=None, max_length=4)
    expected_version: int | None = Field(default=None, ge=0)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=30, max_length=200)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)


class FamilyMenu(BaseModel):
    plan: list[list[str]] = Field(min_length=7, max_length=7)
    recipes: dict[str, dict] = Field(min_length=1, max_length=60)
    expected_version: int = Field(default=0, ge=0)


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


class Favorite(BaseModel):
    starred: bool


class WeeklyArchive(BaseModel):
    plan: list[list[str]] = Field(min_length=7, max_length=7)
    recipes: dict[str, dict] = Field(min_length=1, max_length=60)
    completed_recipes: list[str] = Field(default_factory=list, max_length=60)
    starred_recipes: list[str] = Field(default_factory=list, max_length=60)


class RecipeProgress(BaseModel):
    is_done: bool


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
    with db() as conn:
        session = issue_session(conn, account["id"])
    return {**session, "household_id": family["id"]}


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
        session = issue_session(conn, account["id"])
    return {**session, "display_name": account["display_name"]}


@app.post("/api/session/refresh")
def refresh_session(data: RefreshRequest):
    digest = token_digest(data.refresh_token)
    with db() as conn:
        existing = conn.execute(
            """SELECT account_id FROM auth_sessions
               WHERE token_hash=%s AND revoked_at IS NULL AND expires_at>now()
               FOR UPDATE""",
            (digest,)).fetchone()
        if not existing:
            error(401, "Session expiree : reconnectez-vous")
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=now(),last_used_at=now() WHERE token_hash=%s",
            (digest,))
        return issue_session(conn, existing["account_id"])


@app.post("/api/session/logout")
def logout_session(data: RefreshRequest):
    with db() as conn:
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=now() WHERE token_hash=%s",
            (token_digest(data.refresh_token),))
    return {"revoked": True}


@app.post("/api/password/change")
def change_password(data: ChangePassword, account_id: UUID = Depends(actor)):
    with db() as conn:
        account = conn.execute(
            "SELECT password_hash FROM accounts WHERE id=%s FOR UPDATE",
            (account_id,)).fetchone()
        if not account:
            error(401, "Compte introuvable")
        try:
            hasher.verify(account["password_hash"], data.current_password)
        except (argon_errors.VerificationError, argon_errors.InvalidHashError):
            error(403, "Mot de passe actuel incorrect")
        conn.execute(
            "UPDATE accounts SET password_hash=%s,auth_revision=auth_revision+1 WHERE id=%s",
            (hasher.hash(data.new_password), account_id))
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=now() WHERE account_id=%s AND revoked_at IS NULL",
            (account_id,))
    return {"changed": True, "relogin_required": True}


@app.post("/api/password-reset/request", status_code=202)
def request_reset(data: ResetRequest, background_tasks: BackgroundTasks):
    """No account enumeration and no plaintext reset token storage."""
    if not MAIL_CONFIGURED:
        error(503, "Recuperation par e-mail indisponible : serveur SMTP non configure")
    email = normalize_email(data.email)
    with db() as conn:
        account = conn.execute(
            "SELECT id FROM accounts WHERE email=%s", (email,)).fetchone()
        if account:
            recent = conn.execute(
                """SELECT 1 FROM password_reset_tokens
                   WHERE account_id=%s AND created_at>now()-interval '15 minutes'""",
                (account["id"],)).fetchone()
            if not recent:
                token = secrets.token_urlsafe(48)
                conn.execute(
                    """INSERT INTO password_reset_tokens(token_hash,account_id,expires_at)
                       VALUES (%s,%s,now()+interval '30 minutes')""",
                    (token_digest(token), account["id"]))
                # Fragment : le code ne transite pas dans les journaux HTTP de l'hebergeur web.
                url = RESET_URL.split("#")[0] + "#" + urlencode({"reset": token})
                background_tasks.add_task(send_password_reset_email, email, url)
    return {"message": "Si cette adresse appartient a un compte, un lien va etre envoye."}


@app.post("/api/password-reset/confirm")
def confirm_reset(data: ResetConfirm):
    digest = token_digest(data.token)
    with db() as conn:
        row = conn.execute(
            """SELECT account_id FROM password_reset_tokens
               WHERE token_hash=%s AND used_at IS NULL AND expires_at>now()
               FOR UPDATE""",
            (digest,)).fetchone()
        if not row:
            error(400, "Ce lien de recuperation est invalide ou expire")
        conn.execute(
            "UPDATE accounts SET password_hash=%s WHERE id=%s",
            (hasher.hash(data.new_password), row["account_id"]))
        conn.execute(
            "UPDATE password_reset_tokens SET used_at=now() WHERE token_hash=%s",
            (digest,))
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=now() WHERE account_id=%s AND revoked_at IS NULL",
            (row["account_id"],))
    return {"changed": True, "relogin_required": True}


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
    with db() as conn:
        session = issue_session(conn, account["id"])
    return {**session, "household_id": invite_row["household_id"]}


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
        favorites = conn.execute(
            "SELECT recipe_key,starred FROM favorite_recipes WHERE household_id=%s",
            (hid,)).fetchall()
        progress = conn.execute(
            "SELECT recipe_key,is_done FROM weekly_recipe_progress WHERE household_id=%s AND week_key=%s",
            (hid, week)).fetchall()
        latest = conn.execute(
            "SELECT COALESCE(max(id),0) AS id FROM sync_events WHERE household_id=%s",
            (hid,)).fetchone()["id"]
    return {"shopping": shopping, "recipes": recipes, "plans": plans,
            "consumed": consumed, "pantry": pantry, "favorites": favorites, "progress": progress,
            "last_event_id": latest}


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
                   is_bought=%s,bought_by=%s,unavailable_stores=COALESCE(%s,unavailable_stores),
                   updated_by=%s,updated_at=now(),version=version+1 WHERE id=%s RETURNING *""",
                (data.name, data.quantity_text, data.store_name, data.is_bought,
                 account_id if data.is_bought else None,
                 Jsonb(data.unavailable_stores) if data.unavailable_stores is not None else None,
                 account_id, existing["id"])).fetchone()
        else:
            row = conn.execute(
                """INSERT INTO shopping_items
                   (household_id,week_key,ingredient_key,name,quantity_text,store_name,
                    is_bought,bought_by,updated_by,unavailable_stores)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (hid, week, key, data.name, data.quantity_text, data.store_name,
                 data.is_bought, account_id if data.is_bought else None, account_id,
                 Jsonb(data.unavailable_stores or []))).fetchone()
        event(conn, hid, account_id, "shopping.changed",
              {"week": week.isoformat(), "key": key, "is_bought": data.is_bought,
               "unavailable_stores": row["unavailable_stores"], "version": row["version"]})
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


@app.get("/api/households/{hid}/week-menus/{week}")
def get_family_menu(hid: UUID, week: date, account_id: UUID = Depends(actor)):
    with db() as conn:
        member(conn, hid, account_id)
        row = conn.execute(
            """SELECT week_key,plan,recipes,version,updated_at
               FROM family_week_menus WHERE household_id=%s AND week_key=%s""",
            (hid, week)).fetchone()
    return {"menu": row}


@app.put("/api/households/{hid}/week-menus/{week}")
def set_family_menu(hid: UUID, week: date, data: FamilyMenu,
                    account_id: UUID = Depends(actor)):
    if week.weekday() != 0 or any(len(day) != 4 for day in data.plan):
        error(422, "Un menu familial commence un lundi et comprend quatre repas par jour")
    if any(key not in data.recipes for day in data.plan for key in day):
        error(422, "Recettes manquantes dans le menu familial")
    with db() as conn:
        member(conn, hid, account_id)
        old = conn.execute(
            """SELECT version FROM family_week_menus
               WHERE household_id=%s AND week_key=%s FOR UPDATE""",
            (hid, week)).fetchone()
        if old and old["version"] != data.expected_version:
            error(409, "Le menu familial a change depuis un autre telephone")
        if not old and data.expected_version != 0:
            error(409, "Le menu familial est introuvable : actualiser")
        if old:
            row = conn.execute(
                """UPDATE family_week_menus
                   SET plan=%s,recipes=%s,version=version+1,
                       updated_by=%s,updated_at=now()
                   WHERE household_id=%s AND week_key=%s
                   RETURNING week_key,plan,recipes,version,updated_at""",
                (Jsonb(data.plan), Jsonb(data.recipes), account_id, hid, week)).fetchone()
        else:
            row = conn.execute(
                """INSERT INTO family_week_menus(household_id,week_key,plan,recipes,updated_by)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (household_id,week_key) DO NOTHING
                   RETURNING week_key,plan,recipes,version,updated_at""",
                (hid, week, Jsonb(data.plan), Jsonb(data.recipes), account_id)).fetchone()
            if not row:
                error(409, "Le menu familial vient d'etre publie par un autre appareil")
        # On conserve aussi les semaines precedentes meme sans ouverture des telephones.
        conn.execute(
            """INSERT INTO weekly_recipe_archives
               (household_id,week_key,plan,recipes,archived_by,completed_recipes,starred_recipes)
               SELECT fm.household_id,fm.week_key,fm.plan,fm.recipes,fm.updated_by,
                      COALESCE((SELECT jsonb_agg(p.recipe_key) FROM weekly_recipe_progress p
                                WHERE p.household_id=fm.household_id AND p.week_key=fm.week_key
                                  AND p.is_done), '[]'::jsonb),
                      COALESCE((SELECT jsonb_agg(f.recipe_key) FROM favorite_recipes f
                                WHERE f.household_id=fm.household_id AND f.starred
                                  AND jsonb_exists(fm.recipes,f.recipe_key)), '[]'::jsonb)
               FROM family_week_menus fm WHERE fm.household_id=%s AND fm.week_key<%s
               ON CONFLICT (household_id,week_key) DO NOTHING""",
            (hid, week))
        event(conn, hid, account_id, "weekly-menu.changed",
              {"week": week.isoformat(), "version": row["version"]})
    return {"menu": row}


@app.put("/api/households/{hid}/recipe-progress/{week}/{key}")
def update_recipe_progress(hid: UUID, week: date, key: str, data: RecipeProgress,
                           account_id: UUID = Depends(actor)):
    if not 1 <= len(key) <= 100 or week.weekday() != 0:
        error(422, "Recette ou semaine invalide")
    with db() as conn:
        member(conn, hid, account_id)
        conn.execute(
            """INSERT INTO weekly_recipe_progress
               (household_id,week_key,recipe_key,is_done,updated_by)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (household_id,week_key,recipe_key) DO UPDATE SET
               is_done=EXCLUDED.is_done,updated_by=EXCLUDED.updated_by,updated_at=now()""",
            (hid, week, key, data.is_done, account_id))
        event(conn, hid, account_id, "recipe-progress.changed",
              {"week": week.isoformat(), "key": key, "is_done": data.is_done})
    return {"saved": True, "recipe_key": key, "is_done": data.is_done}


@app.put("/api/households/{hid}/favorites/{key}")
def set_favorite(hid: UUID, key: str, data: Favorite,
                 account_id: UUID = Depends(actor)):
    """A single family-wide star, independent of the purchased list."""
    if not 1 <= len(key) <= 100:
        error(422, "Identifiant de recette invalide")
    with db() as conn:
        member(conn, hid, account_id)
        conn.execute(
            """INSERT INTO favorite_recipes(household_id,recipe_key,starred,updated_by)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT (household_id,recipe_key) DO UPDATE
               SET starred=EXCLUDED.starred,updated_by=EXCLUDED.updated_by,
                   updated_at=now()""",
            (hid, key, data.starred, account_id))
        event(conn, hid, account_id, "favorite.changed",
              {"key": key, "starred": data.starred})
    return {"saved": True, "recipe_key": key, "starred": data.starred}


@app.get("/api/households/{hid}/archives")
def list_archives(hid: UUID, account_id: UUID = Depends(actor)):
    with db() as conn:
        member(conn, hid, account_id)
        rows = conn.execute(
            """SELECT week_key,plan,recipes,completed_recipes,starred_recipes,archived_at FROM weekly_recipe_archives
               WHERE household_id=%s ORDER BY week_key DESC LIMIT 52""",
            (hid,)).fetchall()
    return {"archives": rows}


@app.put("/api/households/{hid}/archives/{week}")
def save_archive(hid: UUID, week: date, data: WeeklyArchive,
                 account_id: UUID = Depends(actor)):
    """The first saved historical menu remains the family's baseline."""
    if week.weekday() != 0 or any(len(day) != 4 for day in data.plan):
        error(422, "Archives : semaine de lundi et quatre recettes par jour requises")
    if any(key not in data.recipes for day in data.plan for key in day):
        error(422, "Archive incomplète : définitions de recettes manquantes")
    with db() as conn:
        member(conn, hid, account_id)
        row = conn.execute(
            """INSERT INTO weekly_recipe_archives
               (household_id,week_key,plan,recipes,completed_recipes,starred_recipes,archived_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (household_id,week_key) DO NOTHING
               RETURNING week_key""",
            (hid, week, Jsonb(data.plan), Jsonb(data.recipes),
             Jsonb(data.completed_recipes), Jsonb(data.starred_recipes), account_id)).fetchone()
        if row:
            event(conn, hid, account_id, "archive.saved", {"week": week.isoformat()})
    return {"saved": bool(row), "week": week.isoformat()}


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
