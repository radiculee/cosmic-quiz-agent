"""arXiv astrophysics papers (astro-ph), via the public arXiv API (no key needed).

Search results are for choosing what to read. An abstract becomes citable once fetch_page reads its
https://arxiv.org/abs/<id> page, which this module serves from the API as clean text.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.llm import JsonObject, ToolSpec
from agent.tools.base import Tool, ToolContext, ToolError, http_get

API_URL = "https://export.arxiv.org/api/query"
MAX_RESULTS = 5
MAX_QUERY_TERMS = 8
_SNIPPET_CHARS = 300

_NS = {"atom": "http://www.w3.org/2005/Atom"}
_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*")
# New-style ids (2203.04890) and old-style ids (astro-ph/0601001), with an optional version.
_ABS_PATH = re.compile(
    r"^/abs/(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}))(?:v\d+)?/?$"
)
_VERSION = re.compile(r"v\d+$")
# Longest commands first, so a longer command is not split by a shorter one.
_LATEX_SYMBOLS: tuple[tuple[str, str], ...] = (
    (r"\lesssim", "≲"),
    (r"\gtrsim", "≳"),
    (r"\approx", "≈"),
    (r"\times", "\u00d7"),  # multiplication sign
    (r"\odot", "☉"),
    (r"\sun", "☉"),
    (r"\sim", "\u223c"),  # tilde operator: LaTeX uses a plain "~" as a space
    (r"\pm", "±"),
    (r"\leq", "≤"),
    (r"\geq", "≥"),
    (r"\le", "≤"),
    (r"\ge", "≥"),
    (r"\deg", "°"),
    (r"\uas", "μas"),
    (r"\mu", "μ"),
    (r"\alpha", "\u03b1"),
    (r"\beta", "\u03b2"),
    (r"\gamma", "\u03b3"),
    (r"\Omega", "Ω"),
    (r"\Lambda", "Λ"),
    (r"\%", "%"),
    (r"\&", "&"),
    (r"\rm", ""),
    (r"\mathrm", ""),
)
_LATEX_SPACING = re.compile(r"\\[,;!: ]|~")


class _SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200)


class Paper(BaseModel):
    model_config = ConfigDict(frozen=True)

    arxiv_id: str
    title: str
    authors: tuple[str, ...]
    published: str
    abstract: str

    @property
    def url(self) -> str:
        return f"https://arxiv.org/abs/{self.arxiv_id}"


def build_search_query(query: str) -> str:
    """Every word must match (the API treats bare words as OR), within astro-ph categories."""
    terms = _TERM.findall(query)[:MAX_QUERY_TERMS]
    if not terms:
        raise ToolError("The query needs at least one word or number.")
    return "cat:astro-ph* AND " + " AND ".join(f"all:{term}" for term in terms)


def parse_abs_url(url: str) -> str | None:
    """Return the version-less arXiv id for an abstract page URL, or None."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host not in ("arxiv.org", "www.arxiv.org"):
        return None
    match = _ABS_PATH.match(parts.path)
    return match.group("id") if match else None


def latex_to_text(text: str) -> str:
    """Turn the common LaTeX in arXiv abstracts into plain text, so the model reads (and quotes)
    the same characters the page check compares against: "$51.8 \\pm 2.3$" becomes "51.8 ± 2.3"."""
    for command, replacement in _LATEX_SYMBOLS:
        text = text.replace(command, replacement)
    text = _LATEX_SPACING.sub(" ", text)
    text = text.replace("$", "").replace("{", "").replace("}", "")
    return " ".join(text.split())


def _text(element: ET.Element, path: str) -> str:
    found = element.find(path, _NS)
    return latex_to_text(found.text or "") if found is not None else ""


def parse_feed(xml_text: str) -> list[Paper]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise ToolError("arXiv returned a response that was not valid XML.") from error

    papers: list[Paper] = []
    for entry in root.findall("atom:entry", _NS):
        raw_id = _text(entry, "atom:id")
        if "/abs/" not in raw_id:
            continue  # the API reports errors as an entry without an abstract id
        arxiv_id = _VERSION.sub("", raw_id.split("/abs/", 1)[1])
        authors = tuple(_text(author, "atom:name") for author in entry.findall("atom:author", _NS))
        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=_text(entry, "atom:title"),
                authors=authors,
                published=_text(entry, "atom:published")[:10],
                abstract=_text(entry, "atom:summary"),
            )
        )
    return papers


def _author_line(authors: tuple[str, ...]) -> str:
    if len(authors) > 3:
        return ", ".join(authors[:3]) + " et al."
    return ", ".join(authors) or "unknown"


def search_arxiv(arguments: JsonObject, ctx: ToolContext) -> str:
    try:
        args = _SearchArgs.model_validate(arguments)
    except ValidationError as error:
        raise ToolError(f"Invalid arguments: {error}") from error

    response = http_get(
        ctx,
        API_URL,
        {
            "search_query": build_search_query(args.query),
            "max_results": str(MAX_RESULTS),
            "sortBy": "relevance",
        },
    )
    papers = parse_feed(response.text)
    if not papers:
        return f"No astro-ph papers found for {args.query!r}. Try fewer or broader words."

    lines = [f"arXiv astro-ph results for {args.query!r}:"]
    for index, paper in enumerate(papers, start=1):
        snippet = paper.abstract[:_SNIPPET_CHARS] + (
            "..." if len(paper.abstract) > _SNIPPET_CHARS else ""
        )
        lines.append(
            f"{index}. {paper.title} ({paper.published}, {_author_line(paper.authors)})\n"
            f"   URL: {paper.url}\n   {snippet}"
        )
    lines.append("Use fetch_page on a URL to read the abstract. Search results cannot be cited.")
    return "\n".join(lines)


def fetch_abstract(arxiv_id: str, ctx: ToolContext) -> tuple[str, str, str]:
    """Fetch one paper's abstract as text. Returns (canonical_url, title, text)."""
    response = http_get(ctx, API_URL, {"id_list": arxiv_id})
    papers = parse_feed(response.text)
    if not papers:
        raise ToolError(f"arXiv has no paper with id {arxiv_id!r}.")
    paper = papers[0]
    text = (
        f"{paper.title}\n"
        f"Authors: {_author_line(paper.authors)}\n"
        f"Published: {paper.published}\n\n"
        f"Abstract: {paper.abstract}"
    )
    return paper.url, paper.title, text


SEARCH_ARXIV = Tool(
    spec=ToolSpec(
        name="search_arxiv",
        description=(
            "Search astrophysics research papers on arXiv (astro-ph). Use it for precise "
            "numbers and recent findings. Returns up to 5 papers with abstract URLs and short "
            "snippets; all words in the query must match, so keep it to a few key terms. "
            "Snippets cannot be cited: call fetch_page on a result URL to read the abstract."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A few key terms, for example 'fast radio burst magnetar'.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    run=search_arxiv,
)
