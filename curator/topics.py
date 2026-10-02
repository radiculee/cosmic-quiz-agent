"""The topics for the initial bank build, approved by Vedant on 2026-10-02.

Evergreen topics never retire. None repeats the eval set in `evals/topics.py`.
"""

from __future__ import annotations

BUILD_TOPICS: tuple[str, ...] = (
    # Solar system
    "The Sun and solar flares",
    "Mercury's extreme temperatures",
    "Venus's runaway greenhouse effect",
    "Auroras",
    "The asteroid belt",
    "Europa's hidden ocean",
    "Titan's lakes and atmosphere",
    "Uranus's tilted rotation",
    "Neptune and Triton",
    # Stars
    "The life cycle of a Sun-like star",
    "Cepheid variable stars",
    "Binary star systems",
    "Planetary nebulae",
    "Magnetars",
    "Open and globular star clusters",
    # Galaxies and cosmology
    "Types of galaxies",
    "Sagittarius A*",
    "Quasars",
    "Galaxy collisions",
    "Dark energy",
    "The Big Bang",
    "Gravitational lensing",
    # Observing and exploring
    "Gravitational waves and LIGO",
    "The Hubble Space Telescope",
    "The Apollo Moon landings",
    "The International Space Station",
    "Mars rovers",
    "The Voyager probes",
    "Radio telescopes",
    "Light-years and cosmic distances",
)

# News topics found by the daily run retire this many days after they are added (decided
# 2026-10-02). Retired items keep their rows, so history and analytics survive.
NEWS_RETIRE_DAYS = 90
