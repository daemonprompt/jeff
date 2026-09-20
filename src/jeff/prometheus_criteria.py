"""
Prometheus Platform PR Approval Tier Classifier — Jeff Criteria
Bead: obsidian-vault-8fy Phase 2

These are the tuned question definitions for classifying Prometheus platform PRs
into approval tiers T0/T1/T2 using Jeff (GLiFormer).

Canonical tier spec: daemonprompt/prometheus-standards/docs/APPROVAL-TIERS.md

Usage:
    from typesafe_sdk import Choice, TypeSafeClient
    from jeff.prometheus_criteria import TIER_QUESTION, build_pr_state

    client = TypeSafeClient(api_key=..., base_url=...)
    result = client.system_one(
        state=build_pr_state(repo, title, files, author),
        questions={"tier": TIER_QUESTION},
    )
    tier = result.choices["tier"].choice  # "T0", "T1", or "T2"

NOTE (Phase 2 finding): GLiFormer has a strong T1 bias for PR classification tasks.
In benchmarking against 256 labeled Prometheus PRs, accuracy was ~40-55%.
The heuristic (tier_classifier.py) achieves 99.6% accuracy and is currently preferred
for production use. Jeff is recommended as a supplementary signal or for tasks
where the heuristic is absent, pending model tuning or fine-tuning on Prometheus data.
See: 40 Prometheus/Research/vault-8fy-benchmark-results.md
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Tier question definition (choice — tuned for GLiFormer)
# ---------------------------------------------------------------------------
# Phase 1 findings drove these three improvements:
#   1. P1 repo list embedded explicitly in T2 criteria (not just instructions)
#   2. T0 explicitly covers docs-only PRs even in P1 repos
#   3. T2 is the safe-fail / high-weight criteria

TIER_INSTRUCTIONS = (
    "Prometheus PR approval tier: what level of human review is required?"
)

TIER_CRITERIA = {
    "T0": (
        "safe routine documentation-only maintenance, "
        "README CHANGELOG markdown files, "
        "chore docs style title, "
        "no code scripts, "
        "automatic merge"
    ),
    "T1": (
        "human developer code change in safe non-critical non-P1 repository, "
        "normal code review needed, "
        "in-session approval"
    ),
    "T2": (
        "dangerous high-risk change: P1 critical service "
        "daemon-mm prom-memory rag-server cc-remote-control daemon-state lve, "
        "OR shared infrastructure prometheus-gitops kubernetes gitops, "
        "OR automated bot robot commit [bot], "
        "OR sensitive governance security configuration CLAUDE"
    ),
}

# For use with typesafe_sdk
TIER_QUESTION = {
    "type": "choice",
    "instructions": TIER_INSTRUCTIONS,
    "criteria": TIER_CRITERIA,
}

# ---------------------------------------------------------------------------
# Supplementary Noul questions (alternative decomposed approach)
# Better recall on specific T2 triggers than the 3-way choice
# ---------------------------------------------------------------------------
IS_CRITICAL_INSTRUCTIONS = (
    "Is this a critical change requiring Telegram approval? "
    "Yes if: P1 service code (daemon-mm cc-remote-control prom-memory rag-server daemon-state lve), "
    "OR prometheus-gitops repo, OR bot [bot] author, "
    "OR governance file (CLAUDE.md Skills Protocols ISA)."
)

IS_DOCS_ONLY_INSTRUCTIONS = (
    "Is this documentation-only? "
    "Yes if: only .md CHANGELOG log files changed, "
    "title starts chore: docs: style:, "
    "no code scripts Python Go shell YAML."
)

NOUL_QUESTIONS = {
    "is_critical": {"type": "noul", "instructions": IS_CRITICAL_INSTRUCTIONS},
    "is_docs_only": {"type": "noul", "instructions": IS_DOCS_ONLY_INSTRUCTIONS},
}


def classify_from_nouls(p_critical: float, p_docs: float) -> str:
    """Combine Noul probabilities into a tier string.

    Conservative thresholds derived from Phase 2 calibration:
    - T2 if p_critical > 0.5
    - T0 if p_docs > 0.6 and not critical
    - T1 otherwise
    """
    if p_critical > 0.5:
        return "T2"
    if p_docs > 0.6:
        return "T0"
    return "T1"


# ---------------------------------------------------------------------------
# State builder — formats PR metadata for Jeff's state field
# ---------------------------------------------------------------------------

def build_pr_state(
    repo: str,
    title: str,
    files: list[str],
    author: str,
    labels: list[str] | None = None,
) -> str:
    """Format PR metadata as a Jeff state string.

    Args:
        repo:    Short repo name (e.g. "daemon-mm")
        title:   PR title string
        files:   List of changed file paths
        author:  GitHub login of PR author
        labels:  Optional list of PR label names

    Returns:
        Formatted state string for /v1/systemone
    """
    files_str = ", ".join(files[:5]) if files else "none"
    if len(files) > 5:
        files_str += f" (+{len(files) - 5} more)"
    parts = [
        f"Repository: {repo}.",
        f"Title: {title}.",
        f"Files: {files_str}.",
        f"Author: {author}.",
    ]
    if labels:
        parts.append(f"Labels: {', '.join(labels)}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# P1 service constants (mirrors tier_classifier.py T2_P1_REPOS)
# ---------------------------------------------------------------------------
P1_REPOS = frozenset(
    ["daemon-mm", "cc-remote-control", "prom-memory", "rag-server", "daemon-state", "lve", "prometheus-lve-mm"]
)
T2_REPOS = frozenset(["prometheus-gitops"])
BOT_PATTERNS = ["[bot]", "-bot", "b0b", "daemonprompt-bot"]
GOVERNANCE_PATHS = [
    "CLAUDE.md", "CLAUDE.local.md",
    "00 System/Skills/", "00 System/Protocols/", "00 System/Agents/",
    "-ISA.md", "enforcement.md", "standards-frontmatter",
]
