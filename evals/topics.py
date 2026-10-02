"""The fixed eval topics, approved by Vedant on 2026-10-01. Change only with his approval: results
are only comparable across runs while the set stays the same."""

from __future__ import annotations

from agent.schemas import Difficulty

TOPICS: tuple[str, ...] = (
    "The phases of the Moon",
    "Why Mars is red",
    "Jupiter's Great Red Spot",
    "Saturn's rings",
    "Comets and their tails",
    "The Kuiper Belt and Pluto",
    "How stars form in nebulae",
    "Red giant stars",
    "White dwarfs",
    "Neutron stars and pulsars",
    "Supernovae",
    "Black holes and event horizons",
    "The structure of the Milky Way",
    "The Andromeda Galaxy",
    "The cosmic microwave background",
    "Dark matter",
    "The expanding universe and Hubble's law",
    "Finding exoplanets with the transit method",
    "The James Webb Space Telescope",
    "Fast radio bursts",
)

# The quick set for checks while tuning: one topic from each area.
QUICK_TOPICS: tuple[str, ...] = (
    "Why Mars is red",
    "White dwarfs",
    "The Andromeda Galaxy",
    "Dark matter",
    "Fast radio bursts",
)

DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
