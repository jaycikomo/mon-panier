#!/usr/bin/env python3
"""Génère une nouvelle semaine de vraies recettes IA et des photos optionnelles.
À exécuter uniquement sur GitHub Actions : jamais de clé API dans index.html.
"""
import base64
import datetime as dt
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
LATEST = ROOT / "data/ai/latest.json"
MODEL = os.environ.get("AI_TEXT_MODEL", "gpt-5-mini")
IMAGE_MODEL = os.environ.get("AI_IMAGE_MODEL", "gpt-image-1-mini")
API_KEY = os.getenv("OPENAI_API_KEY", "")
TARGET = {"p": 130, "c": 180, "f": 75, "cal": 1915}

def request(endpoint, payload, timeout=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/" + endpoint,
        data=body,
        headers={"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.load(res)
    except urllib.error.HTTPError as ex:
        message = ex.read(4000).decode("utf-8", "replace")
        raise RuntimeError(f"Erreur API OpenAI ({ex.code}) : {message}") from ex

def ingredients():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    match = re.search(r"<script>window\.APP_DATA = (\{[^\n]+\});", html)
    if not match:
        raise RuntimeError("Catalogue APP_DATA introuvable dans index.html")
    return json.loads(match.group(1))["ingredients"]

def current_monday():
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    return (today - dt.timedelta(days=today.weekday())).isoformat()

def retail_inventory(catalogue):
    """Limite les recettes aux ingrédients documentés chez Lidl/Aldi/Netto,
    uniquement si la couverture permet des menus variés et équilibrés.
    Sinon, utilise le catalogue alimentaire existant sans inventer de stock.
    """
    path = ROOT / "data" / "retail" / "catalog.json"
    if not path.exists():
        print("Catalogue enseignes absent : ingrédients habituels conservés.")
        return catalogue, {"mode": "fallback", "reason": "Aucune synchronisation de produits"}
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        available = {i for i, v in snapshot.get("evidence", {}).items()
                     if i in catalogue and any(v.get(s) for s in ("lidl", "aldi", "netto"))}
        aisles = {
            "Viandes & poissons": 4, "Produits laitiers": 2,
            "Féculents": 4, "Fruits & légumes": 7, "Épicerie & huiles": 2,
        }
        enough = len(available) >= 24 and all(
            sum(catalogue[i]["aisle"] == aisle for i in available) >= required
            for aisle, required in aisles.items()
        )
        if not enough:
            print("Catalogue partiel (", len(available),
                  "ingrédients), recettes habituelles conservées.")
            return catalogue, {"mode": "fallback", "matches": len(available),
                               "documented_ids": sorted(available),
                               "reason": "Référencement incomplet"}
        selected = {i: value for i, value in catalogue.items() if i in available}
        print("Recettes limitées à", len(selected),
              "ingrédients rapprochés des catalogues Lidl, Aldi et Netto.")
        return selected, {"mode": "evidence", "matches": len(selected),
                          "documented_ids": sorted(available),
                          "source": "Open Food Facts", "updated": snapshot.get("updated")}
    except (OSError, ValueError, TypeError, KeyError) as err:
        print("Catalogue produits inexploitable :", err)
        return catalogue, {"mode": "fallback", "reason": "Catalogue invalide"}

def generate_recipes(catalogue, week, retail_meta):
    inventory = [{"id": key, "nom": val["name"], "P": val["macros"][0],
                  "G": val["macros"][1], "L": val["macros"][2]}
                 for key, val in catalogue.items()]
    previous = []
    history_dir = ROOT / "data/ai/weeks"
    if history_dir.is_dir():
        for p in sorted(history_dir.glob("*.json"))[-8:]:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                previous.extend(r.get("name", "") for r in data.get("recipes", {}).values())
            except (OSError, ValueError):
                continue
    if not previous and LATEST.exists():
        data = json.loads(LATEST.read_text(encoding="utf-8"))
        previous = [r.get("name", "") for r in data.get("recipes", {}).values()]
    month = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"][int(week[5:7])-1]
    instructions = (
        "Tu es cuisinier et diététicien pédagogique. Conçois EXACTEMENT 20 recettes "
        "originales en français pour une famille qui fait principalement ses courses "
        "en priorité chez Lidl (La Destrousse), puis Aldi (La Bouilladisse), puis "
        "Netto (La Destrousse). Privilégie les produits de base bon marché "
        "et les ingrédients généralement référencés dans ces trois enseignes : "
        "œufs, skyr, viande, poisson courant, conserves, féculents et fruits/légumes de saison. "
        "Évite les produits rares, spécialisés ou spécifiques à une marque et propose "
        "des préparations réalisables avec une offre de supermarché standard. "
        "Tu ne connais PAS les stocks ni les promotions en temps réel : ne les invente pas. "
        "Intermarché, les autres magasins et marchés sont des solutions de repli. "
        "Chaque recette doit contenir un titre, 2-4 phrases "
        "de préparation concrètes, un temps (ex: '20 min'), et des ingrédients pesés CRUS "
        "en grammes pour UNE personne. Les recettes de la semaine doivent être nouvelles et "
        "différentes des recettes précédentes. Pas de suppléments, médicaments ni d'allégations médicales. "
        "Retourne exclusivement un objet JSON avec une propriété 'recipes' contenant 20 objets. "
        "Répartition stricte: 3 Petit-déjeuner, 7 Déjeuner, 3 Collation, 7 Dîner. "
        "Chaque objet doit avoir seulement les propriétés id (b1/b2/b3, l1..l7, s1..s3, d1..d7), "
        "name, meal, time, steps, items; items = tableau d'objets {id,g}. "
        "Chaque id d'ingrédient doit exister dans le catalogue fourni, g est entier >0. "
        "Au moins 3 ingrédients par recette et au maximum 8. "
        "Cuisine accessible, ingrédients de saison en " + month + " et recettes variées. "
        "Visée nutritionnelle à partir des valeurs /100 g ci-dessous : "
        "Petit-déjeuner environ 450kcal P30 G50 L14; Déjeuner 600kcal P45 G55 L18; "
        "Collation 240kcal P20 G25 L8; Dîner 625kcal P35 G50 L35. "
        "Objectif journalier total ~1915 kcal, P130 G180 L75. "
        "Ne déduis pas les valeurs des aliments si déjà fournies; les chiffres seront recalculés. "
        "Évite les anciennes recettes : " + json.dumps(previous[-25:], ensure_ascii=False)
    )
    result = request("chat/completions", {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": "Semaine du " + week + ". Catalogue (valeurs par 100 g): " +
             json.dumps(inventory, ensure_ascii=False, separators=(",", ":")) +
             (". Ingrédients également documentés dans les fiches enseignes (référencement, pas stock): " +
              ",".join(retail_meta.get("documented_ids", []))
              if retail_meta.get("documented_ids") else "")}
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 16000
    })
    output = result["choices"][0]["message"]["content"]
    if not output:
        raise RuntimeError("Réponse de l'IA vide")
    return json.loads(output)["recipes"]

def validate(raw, catalogue, week):
    groups = {"b": ("Petit-déjeuner", 3), "l": ("Déjeuner", 7),
              "s": ("Collation", 3), "d": ("Dîner", 7)}
    if not isinstance(raw, list) or len(raw) != 20:
        raise ValueError("20 recettes sont nécessaires")
    expected = {f"{prefix}{n}" for prefix, (_, count) in groups.items() for n in range(1, count + 1)}
    output = {}
    for rec in raw:
        rid = str(rec.get("id", ""))
        if rid not in expected or rid in output:
            raise ValueError("ID recette invalide/dupliqué : " + rid)
        prefix = rid[0]
        if rec.get("meal") != groups[prefix][0]:
            raise ValueError("Type de repas incorrect : " + rid)
        name, steps, time = (str(rec.get(k, "")).strip() for k in ("name", "steps", "time"))
        if not 5 <= len(name) <= 110 or len(steps) < 35 or not 1 <= len(time) <= 30:
            raise ValueError("Description incomplète : " + rid)
        items = rec.get("items")
        if not isinstance(items, list) or not 3 <= len(items) <= 8:
            raise ValueError("Quantités manquantes : " + rid)
        normalized = []
        for item in items:
            iid, qty = str(item.get("id", "")), item.get("g")
            if iid not in catalogue or isinstance(qty, bool) or not isinstance(qty, (int, float)) or not 2 <= qty <= 400:
                raise ValueError(f"Ingrédient/quantité invalide ({rid}): {iid} {qty}")
            normalized.append({"id": iid, "g": round(qty)})
        key = f"ia-{week}-{rid}"
        output[key] = {"name": name, "meal": groups[prefix][0],
                       "time": time, "steps": steps, "items": normalized, "source": "ia"}
    if {k.rsplit("-", 1)[-1] for k in output} != expected:
        raise ValueError("Certaines recettes manquent")
    if len({r["name"].lower() for r in output.values()}) != len(output):
        raise ValueError("Titres dupliqués")
    return output

def macros(rec, catalogue):
    p = c = f = 0.0
    for item in rec["items"]:
        arr = catalogue[item["id"]]["macros"]
        p += item["g"] * arr[0] / 100
        c += item["g"] * arr[1] / 100
        f += item["g"] * arr[2] / 100
    return (p, c, f, 4*p + 4*c + 9*f)

def rebalance_portions(recipes, catalogue):
    """Corrige les quantités d'une portion, sans inventer de valeurs nutritionnelles.

    Les modèles de langage surestiment parfois les portions. Avant de constituer
    les 7 jours, on ajuste chaque recette vers le budget énergétique de son repas.
    Les macros sont ensuite intégralement recalculées à partir du catalogue.
    """
    budgets = {"Petit-déjeuner": 450, "Déjeuner": 600,
               "Collation": 240, "Dîner": 625}
    for key, rec in recipes.items():
        kcal = macros(rec, catalogue)[3]
        if kcal < 100:
            raise ValueError(f"Apports énergétiques trop faibles pour {key} : {kcal:.0f} kcal")
        factor = budgets[rec["meal"]] / kcal
        # Un écart très important indique probablement une mauvaise recette,
        # pas simplement un besoin d'ajuster sa portion.
        if not 0.45 <= factor <= 2.2:
            raise ValueError(f"Portions incohérentes pour {key} : {kcal:.0f} kcal")
        for item in rec["items"]:
            item["g"] = max(2, min(400, round(item["g"] * factor)))
        adjusted_kcal = macros(rec, catalogue)[3]
        if abs(adjusted_kcal - budgets[rec["meal"]]) > 110:
            raise ValueError(f"Impossible de rééquilibrer {key} : {adjusted_kcal:.0f} kcal")
    return recipes


def build_plan(recipes, catalogue):
    groups = {}
    for key, rec in recipes.items():
        groups.setdefault(rec["meal"], []).append(key)
    import itertools
    options = []
    for picks in itertools.product(groups["Petit-déjeuner"], groups["Déjeuner"],
                                   groups["Collation"], groups["Dîner"]):
        ms = [macros(recipes[k], catalogue) for k in picks]
        p, c, f, kcal = [sum(row[i] for row in ms) for i in range(4)]
        score = ((kcal-1915)/40)**2 + ((p-130)/7)**2 + ((c-180)/12)**2 + ((f-75)/7)**2
        options.append((score, picks, kcal, p))
    used = set()
    result, summaries = [], []
    # Diversité : sept déjeuners et sept dîners différents.
    for day in range(7):
        candidates = [x for x in options if x[1][1] not in used and x[1][3] not in used]
        if not candidates:
            raise ValueError("Impossible de répartir sept déjeuners/dîners différents")
        ranked = sorted(candidates, key=lambda x:x[0] + ((day * 17 + sum(ord(c) for c in x[1][0])) % 13)*0.04)
        best = ranked[0]
        used.add(best[1][1]); used.add(best[1][3])
        if abs(best[2]-1915) > 230 or abs(best[3]-130) > 27:
            raise ValueError(f"Menu nutritionnel trop éloigné des objectifs : {best[2]:.0f} kcal P{best[3]:.0f}")
        result.append(list(best[1]))
        summaries.append({"kcal": round(best[2]), "proteines": round(best[3])})
    return result, summaries

def make_photo(rec, key, week):
    prompt = ("Photographie culinaire réaliste, vue de trois quarts, belle lumière naturelle, "
              "assiette individuelle appétissante, sans texte, sans logo, sans watermark : " +
              rec["name"] + ". Ingrédients principaux : " +
              ", ".join(x["id"] for x in rec["items"][:5]) + ".")
    payload = request("images/generations", {
        "model": IMAGE_MODEL, "size": "1024x1024", "quality": "low",
        "output_format": "webp", "prompt": prompt
    }, timeout=260)
    binary = base64.b64decode(payload["data"][0]["b64_json"])
    output = ROOT / "images" / "ia" / week / (key + ".webp")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(binary)
    return "https://raw.githubusercontent.com/jaycikomo/mon-panier/main/" + output.relative_to(ROOT).as_posix()

def main():
    if not API_KEY:
        raise SystemExit("OPENAI_API_KEY absent : ajouter un secret dans Settings > Secrets and variables > Actions.")
    week = current_monday()
    if LATEST.exists() and not os.getenv("FORCE", "").lower() in ("1", "true", "yes"):
        last = json.loads(LATEST.read_text(encoding="utf-8"))
        if last.get("week") == week:
            print("Recettes de cette semaine déjà disponibles : aucune nouvelle dépense.")
            return
    catalogue, retail_meta = retail_inventory(ingredients())
    # Un seul appel texte à l'IA par semaine : pas de deuxième facture en cas d'erreur.
    raw = generate_recipes(catalogue, week, retail_meta)
    recipes = validate(raw, catalogue, week)
    rebalance_portions(recipes, catalogue)
    plan, nutrition = build_plan(recipes, catalogue)
    images_limit = min(2, max(0, int(os.getenv("AI_IMAGE_COUNT", "0"))))
    if images_limit:
        # Une photo par dîner utilisé au menu, au plus 7 par semaine.
        for key in dict.fromkeys(day[3] for day in plan):
            if images_limit <= 0:
                break
            try:
                recipes[key]["photo"] = make_photo(recipes[key], key, week)
                images_limit -= 1
            except Exception as err:
                print("Photo facultative non créée pour", key, ":", str(err)[:400], file=sys.stderr)
    data = {"week": week, "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
            "model": MODEL, "target": TARGET, "retail": retail_meta, "plan": plan,
            "nutrition": nutrition, "recipes": recipes,
            "notice": "Macros estimées depuis une table générique d'ingrédients, à vérifier sur les emballages."}
    week_path = ROOT / "data/ai/weeks" / (week + ".json")
    week_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    week_path.write_text(serialized, encoding="utf-8")
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(serialized, encoding="utf-8")
    print("Semaine IA créée :", week, ", recettes :", len(recipes),
          ", fourchette kcal :", min(i["kcal"] for i in nutrition), max(i["kcal"] for i in nutrition))

if __name__ == "__main__":
    main()
