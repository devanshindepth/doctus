"""Ingredient edges live in their own table; small helper kept on RightsGraph."""
from __future__ import annotations

from doctus.graph.store import RightsGraph
from doctus.graph.store import IngredientEdge as _IE  # re-export convenience


def add_edge_ingredient(self: RightsGraph, asset_id: str, ingredient_id: str) -> None:
    self.add_edge(_IE(asset_id=asset_id, ingredient_id=ingredient_id))


RightsGraph.add_edge_ingredient = add_edge_ingredient  # type: ignore[attr-defined]
