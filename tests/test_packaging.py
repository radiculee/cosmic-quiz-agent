"""Deployment packaging: the two dependency lists must not drift apart, every response carries
the security headers (docs/SECURITY_AUDIT.md S5), and the scene images are small, real WebP
files that the app names and Vercel caches for good."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_and_requirements_pin_the_same_runtime_dependencies() -> None:
    # Vercel installs from pyproject.toml; pip (the Curator workflow, local setup) from
    # requirements.txt. A dependency added to one only would break the other at runtime.
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    assert sorted(project["dependencies"]) == sorted(requirements)
    assert all("==" in pin for pin in requirements), "runtime dependencies must be pinned"


def test_vercel_runs_the_python_version_we_test_on() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def _headers() -> dict[str, str]:
    """The headers vercel.json sends with every path."""
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    every_path = [rule for rule in config["headers"] if rule["source"] == "/(.*)"]
    assert len(every_path) == 1, "one header rule covers every path, pages and API alike"
    return {header["key"]: header["value"] for header in every_path[0]["headers"]}


def _csp() -> dict[str, list[str]]:
    """The Content-Security-Policy as directive -> sources."""
    directives = (part.split() for part in _headers()["Content-Security-Policy"].split(";"))
    return {words[0]: words[1:] for words in directives if words}


def test_every_response_carries_the_security_headers() -> None:
    headers = _headers()

    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    for feature in ("camera", "microphone", "geolocation", "payment", "usb"):
        assert f"{feature}=()" in headers["Permissions-Policy"]


def test_the_content_security_policy_allows_only_this_site() -> None:
    policy = _csp()

    assert policy["default-src"] == ["'self'"]
    assert policy["script-src"] == ["'self'"]  # no inline or outside scripts
    # The fonts are served from the site itself, so no visit reaches Google.
    assert policy["style-src"] == ["'self'"]
    assert policy["font-src"] == ["'self'"]
    assert policy["connect-src"] == ["'self'"]  # the UI only calls its own /api
    assert policy["frame-ancestors"] == ["'none'"]  # no other site may frame the game
    assert policy["object-src"] == ["'none'"] and policy["base-uri"] == ["'none'"]
    assert "upgrade-insecure-requests" in policy
    assert not any("unsafe" in source for sources in policy.values() for source in sources)


def test_the_page_has_no_inline_script_the_policy_would_block() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", html, flags=re.DOTALL)

    assert scripts, "the page loads its bundle with a script tag"
    for attributes, body in scripts:
        assert 'src="' in attributes and not body.strip()


# --- Scenes (public/scenes, src/slideshow.ts) -------------------------------------------------

SCENES = ROOT / "public" / "scenes"
SCENE_BUDGET = 350 * 1024
# The masters are 2720 x 1536; every web size keeps that shape.
MASTER_WIDTH, MASTER_HEIGHT = 2720, 1536
SCENE_PATH = re.compile(r"/scenes/[a-z0-9-]+[.](?:webp|jpg)")
SCENE_NAME = re.compile(r"(?P<scene>[a-z]+)-v(?P<version>[0-9]+)-(?P<width>[0-9]+)[.](?:webp|jpg)")
JPEG_START = bytes([0xFF, 0xD8, 0xFF])


def _webp_size(data: bytes) -> tuple[int, int]:
    """Width and height from a WebP file's header, for each of its three encodings."""
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", "not a WebP file"
    chunk = data[12:16]
    if chunk == b"VP8 ":  # lossy
        return (
            int.from_bytes(data[26:28], "little") & 0x3FFF,
            int.from_bytes(data[28:30], "little") & 0x3FFF,
        )
    if chunk == b"VP8L":  # lossless
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":  # extended
        return (
            int.from_bytes(data[24:27], "little") + 1,
            int.from_bytes(data[27:30], "little") + 1,
        )
    raise AssertionError(f"unknown WebP chunk {chunk!r}")


def _scene_files() -> list[Path]:
    files = sorted(SCENES.iterdir())
    assert files, "public/scenes has no images"
    return files


def test_every_scene_is_a_small_webp_at_the_width_its_name_says() -> None:
    for file in _scene_files():
        name = SCENE_NAME.fullmatch(file.name)
        assert name, f"{file.name} does not follow <scene>-v<version>-<width>.<ext>"
        data = file.read_bytes()
        assert len(data) <= SCENE_BUDGET, f"{file.name} is {len(data) // 1024} KB"
        if file.suffix == ".jpg":
            assert data.startswith(JPEG_START), f"{file.name} is not a JPEG"
            continue
        width, height = _webp_size(data)
        assert width == int(name["width"]), f"{file.name} is {width} px wide"
        assert abs(height - round(width * MASTER_HEIGHT / MASTER_WIDTH)) <= 1, file.name


def test_every_scene_the_app_names_exists_and_no_file_is_left_unused() -> None:
    sources = [ROOT / "index.html", *(ROOT / "src").rglob("*.ts"), *(ROOT / "src").rglob("*.tsx")]
    sources.append(ROOT / "src" / "index.css")
    named = {match for source in sources for match in SCENE_PATH.findall(source.read_text("utf-8"))}

    assert named, "nothing names a scene"
    for scene in sorted(named):
        assert (ROOT / "public" / scene.lstrip("/")).is_file(), f"{scene} is named but missing"
    shipped = {f"/scenes/{file.name}" for file in _scene_files()}
    assert shipped == named, f"in public/scenes but never used: {sorted(shipped - named)}"


def test_scenes_are_cached_for_good_and_keep_the_security_headers() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    rules = {rule["source"]: rule["headers"] for rule in config["headers"]}
    cache = {header["key"]: header["value"] for header in rules["/scenes/(.*)"]}

    # Safe because a changed image gets a new name (the -v1- in each file name).
    assert cache["Cache-Control"] == "public, max-age=31536000, immutable"
    assert "/(.*)" in rules  # the security headers still cover the scenes too


def test_the_css_fades_and_switches_layout_as_the_slideshow_expects() -> None:
    # Vitest reads CSS files as empty, so this cross-check lives here.
    css = (ROOT / "src" / "index.css").read_text(encoding="utf-8")
    slideshow = (ROOT / "src" / "slideshow.ts").read_text(encoding="utf-8")
    fade = re.search(r"export const FADE_MS = ([0-9_]+);", slideshow)
    sizes = re.search(r'export const SCENE_SIZES = "([^"]+)";', slideshow)

    assert fade and sizes
    assert f"transition: opacity {int(fade[1].replace('_', ''))}ms" in css
    # The CSS switches to the whole scene at 4:3, where the sizes pick the full-width file.
    assert "@media (max-aspect-ratio: 4/3)" in css
    assert sizes[1].startswith("(max-aspect-ratio: 4/3) 100vw")


# --- Fonts (public/fonts, src/index.css) ------------------------------------------------------

FONTS = ROOT / "public" / "fonts"
FONT_PATH = re.compile(r"/fonts/[a-z0-9-]+[.]woff2")


def test_every_font_is_a_named_woff2_with_its_licence_and_none_is_unused() -> None:
    css = (ROOT / "src" / "index.css").read_text(encoding="utf-8")
    named = set(FONT_PATH.findall(css))
    shipped = {f"/fonts/{file.name}" for file in FONTS.glob("*.woff2")}

    assert named and named == shipped, f"unused: {shipped - named}, missing: {named - shipped}"
    for file in FONTS.glob("*.woff2"):
        assert file.read_bytes()[:4] == b"wOF2", f"{file.name} is not WOFF2"
        family = file.name.split("-v1-")[0]
        licence = FONTS / f"OFL-{family}.txt"
        assert "SIL OPEN FONT LICENSE" in licence.read_text(encoding="utf-8").upper(), licence.name


def test_the_page_loads_nothing_from_another_site() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    loads = re.findall(r'<(?:link|script)[^>]*(?:href|src)="(https?:[^"]+)"', html)

    assert loads == [], f"third-party loads: {loads}"
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    sources = {rule["source"]: rule["headers"] for rule in config["headers"]}
    assert sources["/fonts/(.*)"] == sources["/scenes/(.*)"]  # cached for good: names carry -v1-
