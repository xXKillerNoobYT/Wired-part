"""AI-powered order suggestion engine.

Analyzes historical purchase order patterns to suggest
parts that are commonly ordered together.
"""

import logging

from wired_part.database.repository import Repository

logger = logging.getLogger(__name__)


def rebuild_suggestions(repo: Repository):
    """Rebuild the full co-occurrence matrix from PO history.

    Called periodically by the background agent or manually
    from the settings page.
    """
    try:
        repo.rebuild_order_patterns()
        logger.info("Order patterns rebuilt successfully")
    except Exception as e:
        logger.error(f"Failed to rebuild order patterns: {e}")
        raise


def get_suggestions(repo: Repository, part_ids: list[int],
                    limit: int = 5) -> list[dict]:
    """Get suggestions for a list of parts being ordered.

    Returns a merged, deduplicated list of suggested parts
    ranked by total score across all trigger parts.
    """
    scores: dict[int, dict] = {}

    for pid in part_ids:
        suggestions = repo.get_suggestions_for_part(pid, limit=limit * 2)
        for s in suggestions:
            sid = s["suggested_part_id"]
            # Don't suggest parts already in the order
            if sid in part_ids:
                continue
            if sid in scores:
                scores[sid]["score"] += s["score"]
            else:
                scores[sid] = dict(s)

    # Sort by total score descending and return top N
    ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:limit]
