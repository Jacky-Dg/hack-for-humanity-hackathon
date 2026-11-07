"""Run `python test_ai.py` for the offline checks.
Run `python test_ai.py --live` to also call Gemini (needs GEMINI_API_KEY).

The scenario uses made-up reports on the sketch routes from routes.py. To keep
the profiles visibly different, the real reports need the same shape: every
route needs an obstacle for at least one profile, or both profiles will pick
the route that has none.
"""

import json
import sys
from types import SimpleNamespace

from ai import pick_route

START, END = (32.87965, -117.23758), (32.88072, -117.23763)
GEOMETRY = {
    "direct": ("Central candidate", [START, (32.88000, -117.23759), (32.88035, -117.23761), END]),
    "west": ("West candidate", [START, (32.87980, -117.23790), (32.88035, -117.23790), END]),
    "east": ("East candidate", [START, (32.87985, -117.23725), (32.88035, -117.23725), END]),
}


def report(id, type, severity, explanation):
    return {"id": id, "type": type, "severity": severity, "explanation": explanation}


STEPS = report("r1", "stairs", "impassable", "Three steps with a handrail and no ramp.")
SLIPPERY = report("r2", "other", "difficult", "Sprinklers left the tile walkway wet and slippery.")
UNEVEN = report("r3", "debris", "difficult", "Long stretch of broken, uneven pavement with raised slabs.")

# Steps with a handrail are manageable on a walking aid, so r1 doesn't affect that profile.
NEARBY = {
    "wheelchair": {"direct": [STEPS], "west": [], "east": []},
    "walking_aid": {"direct": [], "west": [SLIPPERY], "east": [UNEVEN]},
}


def contexts(nearby):
    return [
        {"id": id, "name": name, "points": points, "verified": False, "nearby_reports": nearby.get(id, [])}
        for id, (name, points) in GEOMETRY.items()
    ]


class FakeClient:
    """Stands in for the Gemini client and returns a canned reply."""

    def __init__(self, text=None, error=None):
        def generate_content(**_):
            if error:
                raise error
            return SimpleNamespace(text=text)

        self.models = SimpleNamespace(generate_content=generate_content)


def reply(route_id):
    return json.dumps({"route_id": route_id, "explanation": "Canned reason."})


DOWN = FakeClient(error=RuntimeError("API down"))


def ids(reports):
    return [r["id"] for r in reports]


def test_offline():
    wheelchair = contexts(NEARBY["wheelchair"])
    walking_aid = contexts(NEARBY["walking_aid"])

    # Valid answers pass through, with obstacle lists computed by code.
    result = pick_route(wheelchair, [], "wheelchair", FakeClient(reply("west")))
    assert result["route_id"] == "west" and result["source"] == "gemini"
    assert result["explanation"] == "Canned reason."
    assert ids(result["avoided"]) == ["r1"] and result["on_route"] == []

    result = pick_route(walking_aid, [], "walking_aid", FakeClient(reply("direct")))
    assert result["route_id"] == "direct" and sorted(ids(result["avoided"])) == ["r2", "r3"]

    # A blocked pick from Gemini gets overruled.
    result = pick_route(wheelchair, [], "wheelchair", FakeClient(reply("direct")))
    assert result["route_id"] != "direct" and result["source"] == "rules"

    # A failure, bad JSON or unknown route falls back to rules, and the profiles still differ.
    for client in (DOWN, FakeClient("not json"), FakeClient(reply("nope"))):
        assert pick_route(wheelchair, [], "wheelchair", client)["route_id"] != "direct"
        result = pick_route(walking_aid, [], "walking_aid", client)
        assert result["route_id"] == "direct" and result["source"] == "rules"
        assert "No obstacles have been reported" in result["explanation"]
        assert ".." not in result["explanation"]

    # Every candidate blocked gives None, without calling Gemini.
    blocked = contexts({id: [STEPS] for id in GEOMETRY})
    result = pick_route(blocked, [], "wheelchair", FakeClient(reply("west")))
    assert result["route_id"] is None and "impassable" in result["explanation"]

    # A shared obstacle isn't counted as avoided.
    shared = contexts({"direct": [UNEVEN], "west": [UNEVEN]})
    assert pick_route(shared, [], "walking_aid", FakeClient(reply("west")))["avoided"] == []

    # No reports picks the shortest, and rules never call a route safe.
    result = pick_route(contexts({}), [], "wheelchair", FakeClient(reply("east")))
    assert result["route_id"] == "direct" and result["source"] == "rules"
    assert "No obstacles have been reported" in result["explanation"]
    assert "safe" not in result["explanation"].lower()

    print("Offline checks passed.")


def test_live():
    for profile in NEARBY:
        result = pick_route(contexts(NEARBY[profile]), [], profile)
        print(f"\n{profile}: {result['route_id']} ({result['source']})")
        print(f"  {result['explanation']}")
        print(f"  avoided: {ids(result['avoided'])}  on route: {ids(result['on_route'])}")


if __name__ == "__main__":
    test_offline()
    if "--live" in sys.argv:
        test_live()
