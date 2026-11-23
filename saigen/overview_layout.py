"""Validate and version positions for a particular collapsed Canvas view."""
from .records import Conflict, RecordError, coordinates


def edit_overview(flow, op, internal=False):
    layout = op.get("layout")
    if layout is None and internal:
        key = op["key"]
    else:
        if not isinstance(layout, dict) or set(layout) != {"scale", "cards"}:
            raise RecordError("Supply an overview scale and card positions")
        scale, cards = layout["scale"], layout["cards"]
        if type(scale) not in (int, float) or not .22 <= scale <= 1.8:
            raise RecordError("Invalid overview scale")
        if not isinstance(cards, list) or not cards:
            raise RecordError("Choose at least one overview card")
        known = {state["id"] for state in flow["states"]}
        known.update("group:" + group["id"] for group in flow.get("analysisGroups", []))
        ids = set()
        for card in cards:
            if not isinstance(card, dict) or set(card) != {"id", "x", "y"}:
                raise RecordError("Supply a position and ID for each overview card")
            ident = card["id"]
            if not isinstance(ident, str) or ident in ids or (not internal and ident not in known):
                raise RecordError("Choose distinct cards from this Canvas")
            ids.add(ident)
            coordinates(card)
        if not any(ident.startswith("group:") for ident in ids):
            raise RecordError("An overview layout requires a collapsed group")
        key = "|".join(sorted(ids))
        layout = {"scale": scale, "cards": sorted(cards, key=lambda card: card["id"])}
    layouts = flow.setdefault("overviewLayouts", {})
    previous = layouts.get(key)
    if "expected" in op and previous != op["expected"]:
        raise Conflict("This overview changed after the edit. Undo would overwrite newer positions.")
    if layout is None:
        layouts.pop(key, None)
    else:
        layouts[key] = layout
    if not layouts:
        flow.pop("overviewLayouts")
    return {"op": "edit_overview", "key": key, "layout": previous, "expected": layout}
