"""Tests gratuits du mécanisme de quatre semaines, sans connexion ni clé OpenAI."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_ai_week as menus


START = "2026-10-19"


def bank_fixture():
    meal = {"b": "Petit-déjeuner", "l": "Déjeuner", "s": "Collation", "d": "Dîner"}
    counts = {"b": 5, "l": 11, "s": 5, "d": 11}
    return {
        f"bank-{START}-{prefix}{i}": {
            "name": f"Recette {prefix}{i}",
            "meal": meal[prefix],
            "time": "15 min",
            "steps": "Préparer les ingrédients, les cuire puis servir.",
            "items": [{"id": prefix, "g": 100}],
            "source": "ia",
        }
        for prefix, total in counts.items()
        for i in range(1, total + 1)
    }


def nutrition_fixture():
    # Chaque repas contribue P/G/L à la cible 130/180/75.
    return {
        "b": {"macros": [30, 50, 14]},
        "l": {"macros": [45, 55, 18]},
        "s": {"macros": [20, 25, 8]},
        "d": {"macros": [35, 50, 35]},
    }


class MonthlyMenuTests(unittest.TestCase):
    def test_four_weeks_have_twenty_recipes_and_distinct_dates(self):
        bank = bank_fixture()
        batches = [menus.select_week(bank, START, i) for i in range(4)]
        self.assertEqual(
            [week for week, _ in batches],
            ["2026-10-19", "2026-10-26", "2026-11-02", "2026-11-09"],
        )
        self.assertTrue(all(len(recipes) == 20 for _, recipes in batches))
        self.assertEqual(len({tuple(sorted(x["name"] for x in recipes.values()))
                              for _, recipes in batches}), 4)
        for week, recipes in batches:
            for key in recipes:
                self.assertTrue(key.startswith(f"ia-{week}-"))

    def test_every_week_uses_balanced_day_plan(self):
        bank, catalogue = bank_fixture(), nutrition_fixture()
        for i in range(4):
            week, recipes = menus.select_week(bank, START, i)
            plan, summary = menus.build_plan(recipes, catalogue)
            self.assertEqual(len(plan), 7)
            self.assertEqual(len(summary), 7)
            self.assertEqual(len({day[1] for day in plan}), 7)
            self.assertEqual(len({day[3] for day in plan}), 7)
            self.assertTrue(all(d["kcal"] == 1915 and d["proteines"] == 130
                                for d in summary), week)

    def test_cached_monday_never_needs_openai(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            week = "2026-10-26"
            saved = root / "weeks"
            saved.mkdir()
            (saved / (week + ".json")).write_text(json.dumps({
                "week": week,
                "recipes": dict(list(menus.select_week(bank_fixture(), START, 1)[1].items())),
                "plan": [["b", "l", "s", "d"] for _ in range(7)],
            }), encoding="utf-8")
            with (patch.object(menus, "LATEST", root / "latest.json"),
                  patch.object(menus, "WEEKS_DIR", saved),
                  patch.object(menus, "current_monday", return_value=week),
                  patch.object(menus, "API_KEY", ""),
                  patch.object(menus, "request", side_effect=AssertionError("Aucun token !"))):
                menus.main()
                published = json.loads((root / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(published["week"], week)

    def test_existing_current_week_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "latest.json"
            target.write_text(json.dumps({"week": START}), encoding="utf-8")
            with (patch.object(menus, "LATEST", target),
                  patch.object(menus, "current_monday", return_value=START),
                  patch.object(menus, "API_KEY", ""),
                  patch.object(menus, "request", side_effect=AssertionError("Aucun token !"))):
                menus.main()
            self.assertEqual(json.loads(target.read_text())["week"], START)


if __name__ == "__main__":
    unittest.main()
