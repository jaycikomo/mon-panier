#!/usr/bin/env python3
"""Référence des PRODUITS répertoriés chez Lidl, Aldi et Netto.

Source : Open Food Facts (ODbL 1.0), base participative, PAS stocks par magasin.
Les pages officielles présentent des gammes et promotions mais pas une API de
stock fiable. On garde le dernier fichier valide si l'API est indisponible.
"""
import datetime as dt
import json
import pathlib
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "retail" / "catalog.json"
SOURCE = "https://world.openfoodfacts.org"
STORES = ("lidl", "aldi", "netto")
UA = "MonPanier/1.0 (catalogue familial; https://github.com/jaycikomo/mon-panier)"
# Alias précis pour rapprocher les fiches produits des 43 ingrédients autorisés.
# Un résultat est une correspondance de libellé, jamais une preuve de stock.
ALIASES = {
    "poulet": ["filet de poulet", "blanc de poulet", "escalope de poulet"],
    "saumon": ["saumon"],
    "oeufs": ["oeufs", "oeuf"],
    "steak": ["steak hache 5", "steaks haches 5"],
    "sardines": ["sardines au naturel", "sardines nature"],
    "thon": ["thon au naturel", "thon nature"],
    "dinde": ["escalope de dinde", "filet de dinde"],
    "truite": ["truite"],
    "tofu": ["tofu nature", "tofu ferme"],
    "skyr": ["skyr nature", "skyr"],
    "fromageblanc": ["fromage blanc"],
    "yaourtgrec": ["yaourt a la grecque", "yaourt grec"],
    "cottage": ["cottage cheese", "fromage frais"],
    "feta": ["feta"],
    "avoine": ["flocons d avoine", "flocon d avoine"],
    "muesli": ["muesli"],
    "riz": ["riz basmati"],
    "pates": ["pates completes", "pates complete"],
    "pommesdeterre": ["pommes de terre"],
    "patatedouce": ["patate douce"],
    "quinoa": ["quinoa"],
    "pain": ["pain complet", "pain integral"],
    "banane": ["bananes", "banane"],
    "pomme": ["pommes", "pomme"],
    "poire": ["poires", "poire"],
    "fruitsrouges": ["fruits rouges"],
    "brocoli": ["brocoli"],
    "haricots": ["haricots verts"],
    "courgette": ["courgettes", "courgette"],
    "carotte": ["carottes", "carotte"],
    "tomate": ["tomates", "tomate"],
    "epinards": ["epinards"],
    "salade": ["salade verte", "laitue"],
    "concombre": ["concombre"],
    "amandes": ["amandes", "amande"],
    "noix": ["cerneaux de noix", "noix"],
    "cacahuetes": ["cacahuetes", "arachides"],
    "huile": ["huile d olive"],
    "huilecolza": ["huile de colza"],
    "avocat": ["avocats", "avocat"],
    "beurrecacahuete": ["beurre de cacahuete", "pate d arachide"],
    "citron": ["citrons", "citron"],
    "epices": ["herbes de provence", "melange d epices"],
}

def normalize(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

def is_match(name, aliases):
    text = " " + normalize(name) + " "
    return any(" " + normalize(alias) + " " in text for alias in aliases)

def fetch(store):
    params = urllib.parse.urlencode({
        "stores_tags": store,
        "countries_tags": "en:france",
        "page_size": 500,
        "fields": "code,product_name,product_name_fr,brands,stores_tags,countries_tags",
    })
    url = SOURCE + "/api/v2/search?" + params
    request = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(request, timeout=35) as res:
        result = json.load(res)
    if not isinstance(result.get("products"), list):
        raise ValueError("Réponse de catalogue invalide")
    return result["products"]

def main():
    old = {}
    if OUTPUT.exists():
        try:
            old = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    by_store = dict(old.get("stores", {}))
    errors = []
    successes = 0
    for store in STORES:
        try:
            raw = fetch(store)
            products = []
            used_codes = set()
            for p in raw:
                code = str(p.get("code", ""))
                name = str(p.get("product_name_fr") or p.get("product_name") or "").strip()
                if not re.fullmatch(r"\d{8,14}", code) or len(name) < 3 or code in used_codes:
                    continue
                hits = [key for key, names in ALIASES.items() if is_match(name, names)]
                if not hits:
                    continue
                used_codes.add(code)
                products.append({
                    "name": name[:110], "brand": str(p.get("brands") or "")[:65],
                    "ean": code, "ingredients": hits[:3],
                    "url": SOURCE + "/product/" + code,
                })
            # Conserver les références vérifiables même si peu nombreuses.
            by_store[store] = products[:180]
            successes += 1
            print(store, len(raw), "produits consultés,", len(by_store[store]), "correspondances")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            errors.append(store + ": " + str(exc)[:160])
            print("Catalogue indisponible, conservation du précédent :", errors[-1])
        time.sleep(1)
    if not successes and not old:
        print("Pas de catalogue fiable disponible, génération classique conservée.")
        return
    evidence = {}
    for store in STORES:
        for p in by_store.get(store, []):
            for ingredient in p.get("ingredients", []):
                hits = evidence.setdefault(ingredient, {}).setdefault(store, [])
                if len(hits) < 3:
                    hits.append({"name": p["name"], "brand": p["brand"],
                                 "ean": p["ean"], "url": p["url"]})
    data = {
        "source": "Open Food Facts", "source_url": SOURCE,
        "license": "ODbL-1.0", "disclaimer":
            "Fiches participatives historiques, pas de garantie de disponibilité ni de prix en rayon.",
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "priority": list(STORES), "stores": by_store, "evidence": evidence,
        "matched_ingredients": sorted(evidence), "errors": errors,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Catalogue enregistré :", len(evidence), "ingrédients rapprochés.")

if __name__ == "__main__":
    main()
