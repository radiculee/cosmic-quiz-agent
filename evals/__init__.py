"""Evaluation of the agent and its verifiers on a fixed topic set and a planted-error set.

    python -m evals run [--quick] [--workers N] [--yes]
    python -m evals seed RUN_DIR [--yes]
    python -m evals verify-seeded RUN_DIR [--yes]
    python -m evals report RUN_DIR

Results are written to evals/results/<run>/ (gitignored): the scored items, the planted-error
set and its verification, report.md, summary.json and hand_review.md.
"""
