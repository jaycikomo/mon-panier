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
    # Un 503 peut venir d'une limitation temporaire côté Open Food Facts.
    # Une seule nouvelle tentative, sans IA et sans marteler leur API.
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=35) as res:
                result = json.load(res)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt:
                raise
            print(f"{store}: API momentanément indisponible ({exc.code}), nouvelle tentative dans 22 s.")
            time.sleep(22)
    if not isinstance(result.get("products"), list):
        raise ValueError("Réponse de catalogue invalide")
    return result["products"]

OFFICIAL = ROOT / "data" / "retail" / "official-references.json"
ALLOWED_HOSTS = {
    "lidl": "https://www.lidl.fr/",
    "aldi": "https://www.aldi.fr/",
    "netto": "https://www.netto.fr/",
}

def official_evidence(catalogue):
    """Charge les références officielles vérifiées et traçables.
    Les promotions archivées sont signalées et peuvent ne plus exister.
    """
    if not OFFICIAL.is_file():
        return {}, 0
    source = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    by_store = {name: [] for name in STORES}
    seen = set()
    for item in source.get("items", []):
        if not isinstance(item, dict):
            continue
        store, ingredient = item.get("store"), item.get("id")
        name, url = item.get("name"), item.get("url")
        if (store not in STORES or ingredient not in ALIASES
                or not isinstance(name, str) or not 4 <= len(name) <= 110
                or not isinstance(url, str)
                or not url.startswith(ALLOWED_HOSTS[store])
                or (store, ingredient, url) in seen):
            continue
        seen.add((store, ingredient, url))
        by_store[store].append({
            "name": name, "ingredients": [ingredient], "url": url,
            "source": "Site officiel", "kind": item.get("kind", "listing"),
            "reviewed": source.get("checked_on", ""),
        })
    return by_store, len(seen)


def main():
    old = {}
    if OUTPUT.is_file():
        try:
            old = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    # Les sources officielles vérifiées forment une base même en cas de 503 OFF.
    by_store, official_count = official_evidence(ALIASES)
    errors = []
    community_count = 0
    for store in STORES:
        try:
            raw = fetch(store)
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
                by_store[store].append({
                    "name": name[:110], "brand": str(p.get("brands") or "")[:65],
                    "ean": code, "ingredients": hits[:3],
                    "url": SOURCE + "/product/" + code, "source": "Open Food Facts",
                })
                community_count += 1
            print(store, len(raw), "fiches participatives consultées,",
                  len(used_codes), "produits rapprochés.")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            errors.append(store + ": " + str(exc)[:160])
            print("Source communautaire indisponible, références officielles conservées :",
                  errors[-1])
        time.sleep(1)

    # Si les références officielles et communautaires sont indisponibles,
    # ne pas écraser un catalogue antérieur qui fonctionnait.
    if not official_count and not community_count:
        if old.get("evidence"):
            print("Réutilisation du dernier catalogue valide.")
            return
        raise RuntimeError("Aucune référence officielle ou communautaire exploitable.")

    evidence = {}
    for store in STORES:
        for p in by_store[store][:200]:
            for ingredient in p.get("ingredients", []):
                hits = evidence.setdefault(ingredient, {}).setdefault(store, [])
                if len(hits) < 4:
                    hits.append({k: p[k] for k in ("name", "brand", "ean", "url", "source", "kind", "reviewed") if k in p})

    data = {
        "source": "Sites officiels + Open Food Facts",
        "source_url": SOURCE,
        "license": "ODbL-1.0 pour les seules fiches Open Food Facts",
        "disclaimer": (
            "Références observées en ligne (dont offres anciennes). "
            "Aucun stock local ni prix actuel garanti."
        ),
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "official_reviewed": "2026-10-18",
        "priority": list(STORES),
        "official_count": official_count,
        "community_count": community_count,
        "stores": {name: values[:200] for name, values in by_store.items()},
        "evidence": evidence,
        "matched_ingredients": sorted(evidence),
        "errors": errors,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Catalogue enregistré :", official_count, "références officielles,",
          community_count, "fiches participatives ;",
          len(evidence), "ingrédients représentés.")

if __name__ == "__main__":
    main()
