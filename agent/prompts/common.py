"""Prompt sections shared by LEARN and QUIZ.

System prompts are built once at import and never change between runs, so they stay a stable
prefix for prompt caching. Everything that varies goes in the first user message.
"""

from __future__ import annotations

from agent.schemas import Difficulty

# Approved in Session 2. The loop checks the length in code (see agent/loop.py).
WORD_LIMITS: dict[Difficulty, tuple[int, int]] = {
    "easy": (80, 120),
    "medium": (120, 180),
    "hard": (160, 220),
}

RESEARCH_RULES = """\
How to research:
- Start with search_wikipedia for an overview, then read the most useful pages with \
fetch_page.
- For precise numbers or recent findings, also use search_arxiv (astrophysics papers) or \
fetch_feed (latest NASA and ESA news). nasa_apod reads NASA's Astronomy Picture of the Day for \
a date, and search_nasa_images finds NASA's official image records.
- Read at most 3 pages or records in total.
- Base every statement on what you read, not on memory. If your sources do not support a \
claim, leave the claim out.

Which sources to prefer, when they say the same thing:
1. Space agencies and observatories (NASA, ESA, STScI, ESO, NOIRLab, the IAU).
2. Research papers (arXiv).
3. Wikipedia.
4. Popular science sites (Space.com, Sky & Telescope).

How to cite:
- You may only cite pages and records you read in this run. Any other URL is removed \
automatically, and an answer with no valid citations is discarded.
- Cite each URL exactly as it appears on the "URL:" line of the result you read.
- For each citation, include a short quote (one sentence or less) copied character for \
character from that page. Copy one continuous passage: do not join separate sentences, \
shorten, or paraphrase. Quotes are checked against the page automatically.
"""

WRITING_RULES = """\
How to write:
- Write for a curious adult with no astronomy background. Use plain language and define any \
technical term the first time you use it.
- Keep explanations to the word range given for the difficulty, in short paragraphs. No \
headings, lists or markdown.
- Write every number the way your source writes it, in digits, with the same value and units, \
so it can be checked against the source automatically. Do not convert or restate numbers in \
other forms, and do not write numbers as words.
"""


def lead_line(lead_url: str | None) -> str:
    """For a topic found in a news feed: the article to start from, as its own prompt line."""
    if lead_url is None:
        return ""
    return f"\nStart from this news article (read it with fetch_page before citing it): {lead_url}"


def nudge(submit_tool: str) -> str:
    return (
        f"Please continue with your tools. When you have read your sources, call {submit_tool}; "
        "a plain-text reply cannot be used."
    )


def correction(problems: list[str], submit_tool: str) -> str:
    """Ask the model to fix problems found by the code checks, once."""
    listed = "\n".join(f"- {problem}" for problem in problems)
    return (
        f"The answer was not accepted:\n{listed}\n"
        "Fix these, re-reading a page if you need to, and keep everything else the same. Copy "
        f"quotes exactly, and only use numbers that appear in the cited pages. Then call "
        f"{submit_tool} again."
    )


def length_problem(words: int, difficulty: Difficulty) -> str:
    low, high = WORD_LIMITS[difficulty]
    return f"The explanation is {words} words; {difficulty} needs {low} to {high}."
