"""E2E tests for Session D (Loops 16-20): @mentions, job timeline,
notebook search improvements, edit history, and message reactions.

Simulated user feedback driving each section:
  Loop 16 — "I @mentioned the foreman but he never got a notification"
  Loop 17 — "I need to see everything that happened on a job in one place"
  Loop 18 — "Search can't find my note even though I know which section it's in"
  Loop 19 — "Someone edited a message and I can't see what the original said"
  Loop 20 — "I just want to thumbs-up a message instead of typing 'ok'"
"""

import json
from datetime import datetime

import pytest

from wired_part.database.models import (
    Job, JobAssignment, LaborEntry, NotebookPage, User,
)
from wired_part.database.repository import Repository


# ── Shared fixture ────────────────────────────────────────────────


@pytest.fixture
def polish_data(repo):
    """Create users + job + notebook for Session D tests."""
    boss = User(
        username="polishboss", display_name="Polish Boss",
        pin_hash=Repository.hash_pin("0000"), role="admin",
    )
    boss.id = repo.create_user(boss)

    worker = User(
        username="polishworker", display_name="Polish Worker",
        pin_hash=Repository.hash_pin("1111"), role="user",
    )
    worker.id = repo.create_user(worker)

    foreman = User(
        username="polishforeman", display_name="Polish Foreman",
        pin_hash=Repository.hash_pin("2222"), role="user",
    )
    foreman.id = repo.create_user(foreman)

    job = Job(
        job_number="JOB-POLISH-001", name="Polish Test Job",
        customer="PolishCorp", status="active",
    )
    job.id = repo.create_job(job)

    for u in (boss, worker, foreman):
        repo.assign_user_to_job(JobAssignment(
            job_id=job.id, user_id=u.id, role="worker",
        ))

    # Create notebook with a page
    nb = repo.get_or_create_notebook(job.id)
    sections = repo.get_sections(nb.id)
    page = NotebookPage(
        section_id=sections[0].id,
        title="Wire Gauge Reference",
        content="Use 12 AWG for 20A circuits and 10 AWG for 30A circuits.",
        created_by=boss.id,
    )
    page.id = repo.create_page(page)

    return {
        "boss": boss, "worker": worker, "foreman": foreman,
        "job": job, "notebook": nb, "sections": sections,
        "page": page,
    }


# =====================================================================
# Loop 16 — @mentions
# =====================================================================


class TestMentions:
    """@username mentions should create targeted notifications."""

    def test_mention_creates_notification(self, repo, polish_data):
        """@mentioning a user creates a notification for them."""
        j, boss, worker = (
            polish_data["job"], polish_data["boss"], polish_data["worker"]
        )
        repo.send_chat_message(
            j.id, boss.id,
            "Hey @polishworker, bring the wire strippers",
        )

        notifs = repo.get_user_notifications(worker.id, unread_only=True)
        mention_notifs = [n for n in notifs if n.title == "Mentioned"]
        assert len(mention_notifs) >= 1
        assert "Polish Boss" in mention_notifs[0].message
        assert "wire strippers" in mention_notifs[0].message

    def test_mention_does_not_notify_sender(self, repo, polish_data):
        """Mentioning yourself doesn't create a notification."""
        j, boss = polish_data["job"], polish_data["boss"]
        repo.send_chat_message(j.id, boss.id, "Reminder to @polishboss self")

        notifs = repo.get_user_notifications(boss.id, unread_only=True)
        mention_notifs = [n for n in notifs if n.title == "Mentioned"]
        assert len(mention_notifs) == 0

    def test_mention_nonexistent_user_ignored(self, repo, polish_data):
        """@mentioning a non-existent username is silently ignored."""
        j, boss = polish_data["job"], polish_data["boss"]
        # Should not raise
        repo.send_chat_message(j.id, boss.id, "Hey @nobody_exists, do stuff")

    def test_multiple_mentions(self, repo, polish_data):
        """Multiple @mentions in one message create separate notifications."""
        j, boss, worker, foreman = (
            polish_data["job"], polish_data["boss"],
            polish_data["worker"], polish_data["foreman"],
        )
        repo.send_chat_message(
            j.id, boss.id,
            "@polishworker and @polishforeman — meeting at 3pm",
        )

        worker_notifs = [
            n for n in repo.get_user_notifications(worker.id, unread_only=True)
            if n.title == "Mentioned"
        ]
        foreman_notifs = [
            n for n in repo.get_user_notifications(foreman.id, unread_only=True)
            if n.title == "Mentioned"
        ]
        assert len(worker_notifs) >= 1
        assert len(foreman_notifs) >= 1

    def test_duplicate_mentions_deduped(self, repo, polish_data):
        """@user @user in the same message only sends one notification."""
        j, boss, worker = (
            polish_data["job"], polish_data["boss"], polish_data["worker"]
        )
        repo.send_chat_message(
            j.id, boss.id,
            "@polishworker hey @polishworker pay attention",
        )

        notifs = [
            n for n in repo.get_user_notifications(worker.id, unread_only=True)
            if n.title == "Mentioned"
        ]
        assert len(notifs) == 1  # Deduplicated


# =====================================================================
# Loop 17 — Job timeline
# =====================================================================


class TestJobTimeline:
    """Unified timeline of labor + chat + updates."""

    def test_timeline_includes_labor(self, repo, polish_data):
        """Timeline includes labor clock-in entries."""
        j, boss = polish_data["job"], polish_data["boss"]
        repo.create_labor_entry(LaborEntry(
            user_id=boss.id, job_id=j.id,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            hours=3.5, sub_task_category="Rough-in",
            description="Panel A wiring",
        ))

        timeline = repo.get_job_timeline(j.id)
        labor_items = [t for t in timeline if t["type"] == "labor"]
        assert len(labor_items) >= 1
        assert "Rough-in" in labor_items[0]["message"]
        assert "3.5h" in labor_items[0]["message"]

    def test_timeline_includes_chat(self, repo, polish_data):
        """Timeline includes chat messages."""
        j, boss = polish_data["job"], polish_data["boss"]
        repo.send_chat_message(j.id, boss.id, "Starting panel B")

        timeline = repo.get_job_timeline(j.id)
        chat_items = [t for t in timeline if t["type"] == "chat"]
        assert len(chat_items) >= 1
        assert "Starting panel B" in chat_items[0]["message"]

    def test_timeline_includes_updates(self, repo, polish_data):
        """Timeline includes regular updates/comments."""
        j, boss = polish_data["job"], polish_data["boss"]
        repo.create_job_update(j.id, boss.id, "Status: 50% complete",
                               update_type="milestone")

        timeline = repo.get_job_timeline(j.id)
        update_items = [t for t in timeline if t["type"] == "update"]
        assert len(update_items) >= 1

    def test_timeline_excludes_dms(self, repo, polish_data):
        """Timeline never shows DMs."""
        j, boss, worker = (
            polish_data["job"], polish_data["boss"], polish_data["worker"]
        )
        repo.send_dm(j.id, boss.id, worker.id, "Secret timeline test")

        timeline = repo.get_job_timeline(j.id)
        assert not any(t.get("type") == "dm" for t in timeline)
        assert not any("Secret timeline" in t["message"] for t in timeline)

    def test_timeline_sorted_by_date(self, repo, polish_data):
        """Timeline items are sorted most-recent first."""
        j, boss = polish_data["job"], polish_data["boss"]
        repo.send_chat_message(j.id, boss.id, "First msg")
        repo.send_chat_message(j.id, boss.id, "Second msg")

        timeline = repo.get_job_timeline(j.id)
        if len(timeline) >= 2:
            # Most recent first
            assert timeline[0]["created_at"] >= timeline[-1]["created_at"]

    def test_timeline_pagination(self, repo, polish_data):
        """Timeline respects limit and offset."""
        j, boss = polish_data["job"], polish_data["boss"]
        for i in range(10):
            repo.send_chat_message(j.id, boss.id, f"Timeline-{i:02d}")

        page1 = repo.get_job_timeline(j.id, limit=5, offset=0)
        page2 = repo.get_job_timeline(j.id, limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        # No overlap
        ids1 = {t["id"] for t in page1}
        ids2 = {t["id"] for t in page2}
        assert ids1.isdisjoint(ids2)


# =====================================================================
# Loop 18 — Notebook search improvements
# =====================================================================


class TestNotebookSearchImprovements:
    """Enhanced notebook search with section filter and snippets."""

    def test_search_with_section_filter(self, repo, polish_data):
        """Search can be narrowed to a specific section."""
        sections = polish_data["sections"]
        page = polish_data["page"]

        # Create a second page in a different section (if available)
        if len(sections) > 1:
            repo.create_page(NotebookPage(
                section_id=sections[1].id,
                title="Other Section Page",
                content="This also mentions wire gauge info.",
                created_by=polish_data["boss"].id,
            ))

        # Search with section filter
        results = repo.search_notebook_pages(
            "wire", section_id=sections[0].id,
        )
        assert all(r.section_id == sections[0].id for r in results)

    def test_search_snippets(self, repo, polish_data):
        """search_notebook_with_snippets returns context around the match."""
        j = polish_data["job"]

        results = repo.search_notebook_with_snippets("12 AWG", job_id=j.id)
        assert len(results) >= 1
        assert "12 AWG" in results[0]["snippet"]
        assert results[0]["title"] == "Wire Gauge Reference"

    def test_search_snippets_truncation(self, repo, polish_data):
        """Long content gets truncated in snippets."""
        sections = polish_data["sections"]
        long_content = "A" * 500 + " target_keyword " + "B" * 500
        repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Long Page",
            content=long_content,
            created_by=polish_data["boss"].id,
        ))

        results = repo.search_notebook_with_snippets("target_keyword")
        assert len(results) >= 1
        snippet = results[0]["snippet"]
        assert "target_keyword" in snippet
        assert len(snippet) < len(long_content)  # Truncated

    def test_search_no_match_returns_empty(self, repo, polish_data):
        results = repo.search_notebook_with_snippets("xyznonexistent")
        assert len(results) == 0


# =====================================================================
# Loop 19 — Edit history
# =====================================================================


class TestEditHistory:
    """Message edits tracked in activity_log for history."""

    def test_edit_logs_history(self, repo, polish_data):
        """Editing a message creates an activity_log entry."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "Original text")

        repo.edit_job_update(mid, "Edited text", editor_id=boss.id)

        history = repo.get_edit_history(mid)
        assert len(history) == 1
        assert history[0]["old_message"] == "Original text"
        assert history[0]["new_message"] == "Edited text"
        assert history[0]["editor"] == "Polish Boss"

    def test_multiple_edits_tracked(self, repo, polish_data):
        """Multiple edits create separate history entries."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "Version 1")

        repo.edit_job_update(mid, "Version 2", editor_id=boss.id)
        repo.edit_job_update(mid, "Version 3", editor_id=boss.id)

        history = repo.get_edit_history(mid)
        assert len(history) == 2
        # Most recent first
        assert history[0]["new_message"] == "Version 3"
        assert history[1]["new_message"] == "Version 2"

    def test_edit_without_editor(self, repo, polish_data):
        """Edit without editor_id still works (system edit)."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "Auto-edited")
        repo.edit_job_update(mid, "System fixed")

        history = repo.get_edit_history(mid)
        assert len(history) == 1

    def test_no_history_for_unedited(self, repo, polish_data):
        """Unedited messages have empty history."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "Never edited")

        history = repo.get_edit_history(mid)
        assert len(history) == 0


# =====================================================================
# Loop 20 — Message reactions
# =====================================================================


class TestMessageReactions:
    """Lightweight emoji reactions on messages."""

    def test_add_reaction(self, repo, polish_data):
        """Adding a reaction stores it in the reactions JSON."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "Great work!")

        repo.add_reaction(mid, boss.id, "thumbs_up")
        reactions = repo.get_reactions(mid)
        assert "thumbs_up" in reactions
        assert boss.id in reactions["thumbs_up"]

    def test_multiple_users_same_reaction(self, repo, polish_data):
        """Multiple users can add the same reaction."""
        j, boss, worker = (
            polish_data["job"], polish_data["boss"], polish_data["worker"]
        )
        mid = repo.send_chat_message(j.id, boss.id, "Team lunch?")

        repo.add_reaction(mid, boss.id, "thumbs_up")
        repo.add_reaction(mid, worker.id, "thumbs_up")

        reactions = repo.get_reactions(mid)
        assert len(reactions["thumbs_up"]) == 2

    def test_multiple_different_reactions(self, repo, polish_data):
        """Different emojis coexist."""
        j, boss, worker = (
            polish_data["job"], polish_data["boss"], polish_data["worker"]
        )
        mid = repo.send_chat_message(j.id, boss.id, "Panel A done!")

        repo.add_reaction(mid, boss.id, "thumbs_up")
        repo.add_reaction(mid, worker.id, "fire")

        reactions = repo.get_reactions(mid)
        assert "thumbs_up" in reactions
        assert "fire" in reactions

    def test_remove_reaction(self, repo, polish_data):
        """Removing a reaction takes the user out of the list."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "Meh")

        repo.add_reaction(mid, boss.id, "thumbs_up")
        repo.remove_reaction(mid, boss.id, "thumbs_up")

        reactions = repo.get_reactions(mid)
        assert "thumbs_up" not in reactions

    def test_remove_last_user_removes_emoji_key(self, repo, polish_data):
        """When the last user removes a reaction, the emoji key disappears."""
        j, boss, worker = (
            polish_data["job"], polish_data["boss"], polish_data["worker"]
        )
        mid = repo.send_chat_message(j.id, boss.id, "Test")

        repo.add_reaction(mid, boss.id, "heart")
        repo.add_reaction(mid, worker.id, "heart")
        repo.remove_reaction(mid, boss.id, "heart")

        reactions = repo.get_reactions(mid)
        assert "heart" in reactions
        assert len(reactions["heart"]) == 1

        repo.remove_reaction(mid, worker.id, "heart")
        reactions = repo.get_reactions(mid)
        assert "heart" not in reactions

    def test_double_add_idempotent(self, repo, polish_data):
        """Adding the same reaction twice doesn't duplicate."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "Idempotent test")

        repo.add_reaction(mid, boss.id, "check")
        repo.add_reaction(mid, boss.id, "check")

        reactions = repo.get_reactions(mid)
        assert len(reactions["check"]) == 1

    def test_reactions_on_nonexistent_raises(self, repo, polish_data):
        """Reacting to nonexistent message raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            repo.add_reaction(99999, polish_data["boss"].id, "thumbs_up")

    def test_get_reactions_empty(self, repo, polish_data):
        """Fresh message has no reactions."""
        j, boss = polish_data["job"], polish_data["boss"]
        mid = repo.send_chat_message(j.id, boss.id, "No reactions yet")
        reactions = repo.get_reactions(mid)
        assert reactions == {}
