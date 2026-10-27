"""Config files point at each other by id. A typo would silently fall back to a default, so every
link is checked here: adding a product, offer or method that names something missing fails CI."""

from pathlib import Path

import pytest

from core.infra.loader import load_yaml

CONFIG = Path(__file__).resolve().parent.parent / "config"
BUYER = load_yaml("buyer.yaml")
PRODUCTS = load_yaml("buyer_products.yaml")["products"]
ENGINE = load_yaml("script/engine.yaml")
GROUPED = [p for ids in BUYER["product_groups"].values() for p in ids]


@pytest.mark.parametrize("product", GROUPED)
def test_every_product_in_the_picker_has_knowledge_and_personas(product):
    assert product in PRODUCTS, f"buyer.yaml product_groups names '{product}', missing in buyer_products.yaml"
    assert product in BUYER["personas"], f"'{product}' has no personas in buyer.yaml, so the picker hides it"


def test_no_product_is_listed_in_two_groups():
    assert len(GROUPED) == len(set(GROUPED))


def test_every_persona_set_belongs_to_a_product():
    stray = set(BUYER["personas"]) - set(GROUPED) - {"general"}
    assert not stray, f"personas for unknown products: {sorted(stray)}"


@pytest.mark.parametrize("product, entry", ENGINE["products"].items())
def test_every_buy_mode_product_has_its_offer_and_method(product, entry):
    assert (CONFIG / "offers" / f"{entry['offer']}.yaml").exists(), f"{product}: no offers/{entry['offer']}.yaml"
    assert (CONFIG / "methods" / f"{entry.get('method', ENGINE['method'])}.yaml").exists(), f"{product}: no method file"


def test_the_default_buy_mode_product_is_listed():
    assert ENGINE["default_product"] in ENGINE["products"]
