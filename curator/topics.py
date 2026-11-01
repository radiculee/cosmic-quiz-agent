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

# The likely-topic fill, approved by Vedant on 2026-11-01: what visitors are likely to type before
# the launch, with `python -m curator fill`. Short plain names on purpose, because a search matches
# the bank only on the exact name, ignoring case. Unlike the build's list, some repeat or share a
# subject with the eval set (decided the same day): no code in `evals/` reads the bank, so eval
# results stay comparable. "Space oceans" was typed by a visitor and has a topic row already.
FILL_TOPICS: tuple[str, ...] = (
    # Solar system
    "Mars",
    "Jupiter",
    "Saturn",
    "The Moon",
    "Pluto",
    "Comets",
    "Meteor showers",
    "Enceladus",
    "Lunar eclipses",
    # Stars
    "Supernovae",
    "Neutron stars",
    "Betelgeuse",
    "Alpha Centauri",
    "Brown dwarfs",
    "Constellations",
    "Nebulae",
    # Galaxies and cosmology
    "Dark matter",
    "The Milky Way",
    "Andromeda Galaxy",
    "Exoplanets",
    "The Fermi paradox",
    "Time dilation",
    "Hawking radiation",
    "The observable universe",
    # Exploring
    "The Space Race",
    "Cassini-Huygens",
    "New Horizons",
    "Parker Solar Probe",
    "Space debris",
    # Typed by a visitor, with no published item
    "Space oceans",
)

# News topics found by the daily run retire this many days after they are added (decided
# 2026-10-02). Retired items keep their rows, so history and analytics survive.
NEWS_RETIRE_DAYS = 90
