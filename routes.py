"""Editable demo geometry. These are sketches, NOT surveyed accessible paths.

Replace intermediate vertices with points collected during the team's walk.
Geisel reference: https://ezid.cdlib.org/id/doi:10.34946/D6V01X
Library Walk context: https://calendar.ucsd.edu/library-walk
"""

START = (32.87965, -117.23758)
END = (32.88072, -117.23763)
START_NAME = "Library Walk — Price Center vicinity"
END_NAME = "Library Walk — Geisel approach"

ROUTES = [
    {"id": "direct", "name": "Central candidate", "verified": False,
     "points": [START, (32.88000, -117.23759), (32.88035, -117.23761), END]},
    {"id": "west", "name": "West candidate", "verified": False,
     "points": [START, (32.87980, -117.23790), (32.88035, -117.23790), END]},
    {"id": "east", "name": "East candidate", "verified": False,
     "points": [START, (32.87985, -117.23725), (32.88035, -117.23725), END]},
]
