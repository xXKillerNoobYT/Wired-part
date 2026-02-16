"""E2E tests for Session C (Loops 11-15): job chat, DMs, read receipts,
chat search and pagination.

Simulated user feedback driving each section:
  Loop 11 — "We need a way to communicate on job sites without switching apps"
  Loop 12 — "I sent messages but can't tell which are comments vs. chat"
  Loop 13 — "I need to DM the foreman privately within the job"
  Loop 14 — "I missed a DM because there was no indicator of unread messages"
  Loop 15 — "Can't find that message about the wire gauge from last week"
"""

from datetime import datetime

import pytest

from wired_part.database.models import (
    Job, JobAssignment, JobUpdate, User,
)
from wired_part.database.repository import Repository


# ── Shared fixture ────────────────────────────────────────────────


@pytest.fixture
def chat_data(repo):
    """Create users + job with assignments for chat tests."""
    boss = User(
        username="chatboss", display_name="Chat Boss",
        pin_hash=Repository.hash_pin("0000"), role="admin",
    )
    boss.id = repo.create_user(boss)

    worker = User(
        username="chatworker", display_name="Chat Worker",
        pin_hash=Repository.hash_pin("1111"), role="user",
    )
    worker.id = repo.create_user(worker)

    foreman = User(
        username="chatforeman", display_name="Chat Foreman",
        pin_hash=Repository.hash_pin("2222"), role="user",
    )
    foreman.id = repo.create_user(foreman)

    job = Job(
        job_number="JOB-CHAT-001", name="Chat Test Job",
        customer="ChatCorp", status="active",
    )
    job.id = repo.create_job(job)

    for u in (boss, worker, foreman):
        repo.assign_user_to_job(JobAssignment(
            job_id=job.id, user_id=u.id, role="worker",
        ))

    return {
        "boss": boss, "worker": worker, "foreman": foreman,
        "job": job,
    }


# =====================================================================
# Loop 11 — Chat schema works end-to-end
# =====================================================================


class TestChatSchema:
    """Verify the v15 schema additions work correctly."""

    def test_job_update_accepts_chat_type(self, repo, chat_data):
        """The CHECK constraint allows 'chat' type."""
        j, u = chat_data["job"], chat_data["boss"]
        uid = repo.create_job_update(
            j.id, u.id, "Hello team!", update_type="chat",
        )
        assert uid > 0

    def test_job_update_accepts_dm_type(self, repo, chat_data):
        """The CHECK constraint allows 'dm' type."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]
        uid = repo.create_job_update(
            j.id, boss.id, "Hey worker!", update_type="dm",
            recipient_id=worker.id,
        )
        assert uid > 0

    def test_edit_message_sets_edited_at(self, repo, chat_data):
        """Editing a message sets the edited_at timestamp."""
        j, u = chat_data["job"], chat_data["boss"]
        uid = repo.send_chat_message(j.id, u.id, "Original msg")
        repo.edit_job_update(uid, "Edited msg")

        msgs = repo.get_job_chat(j.id)
        edited = [m for m in msgs if m.id == uid][0]
        assert edited.message == "Edited msg"
        assert edited.edited_at is not None

    def test_old_update_types_still_work(self, repo, chat_data):
        """Legacy update types (comment, milestone, etc.) still work."""
        j, u = chat_data["job"], chat_data["boss"]
        for utype in ("comment", "status_change", "assignment", "milestone"):
            uid = repo.create_job_update(
                j.id, u.id, f"Test {utype}", update_type=utype,
            )
            assert uid > 0


# =====================================================================
# Loop 12 — Group chat CRUD
# =====================================================================


class TestGroupChat:
    """Group chat visible to all job members."""

    def test_send_and_retrieve_messages(self, repo, chat_data):
        """Messages sent via send_chat_message appear in get_job_chat."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]

        repo.send_chat_message(j.id, boss.id, "Morning team!")
        repo.send_chat_message(j.id, worker.id, "Good morning boss!")
        repo.send_chat_message(j.id, boss.id, "Let's wire panel B today.")

        msgs = repo.get_job_chat(j.id)
        assert len(msgs) == 3
        # Oldest first (chat order)
        assert msgs[0].message == "Morning team!"
        assert msgs[2].message == "Let's wire panel B today."

    def test_chat_visible_in_updates_but_dms_excluded(self, repo, chat_data):
        """Chat messages appear in get_job_updates, but DMs don't."""
        j = chat_data["job"]
        boss, worker = chat_data["boss"], chat_data["worker"]
        repo.create_job_update(j.id, boss.id, "Status update", update_type="comment")
        repo.send_chat_message(j.id, boss.id, "Chat message")
        repo.send_dm(j.id, boss.id, worker.id, "Secret DM")

        updates = repo.get_job_updates(j.id)
        assert any(up.message == "Status update" for up in updates)
        assert any(up.message == "Chat message" for up in updates)
        assert not any(up.message == "Secret DM" for up in updates)

    def test_chat_messages_excluded_from_dashboard(self, repo, chat_data):
        """Chat messages show on dashboard but DMs don't."""
        j, u = chat_data["job"], chat_data["boss"]
        repo.send_chat_message(j.id, u.id, "Group visible")

        latest = repo.get_latest_updates_across_jobs(limit=50)
        types = [up.update_type for up in latest]
        assert "chat" in types

    def test_chat_pagination(self, repo, chat_data):
        """Offset-based pagination works for chat history."""
        j, u = chat_data["job"], chat_data["boss"]
        for i in range(10):
            repo.send_chat_message(j.id, u.id, f"Msg-{i:02d}")

        page1 = repo.get_job_chat(j.id, limit=5, offset=0)
        page2 = repo.get_job_chat(j.id, limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].message == "Msg-00"
        assert page2[0].message == "Msg-05"

    def test_chat_with_photos(self, repo, chat_data):
        """Chat messages can include photo attachments."""
        j, u = chat_data["job"], chat_data["boss"]
        photos = '["img_001.jpg", "img_002.jpg"]'
        mid = repo.send_chat_message(j.id, u.id, "See these photos", photos=photos)

        msgs = repo.get_job_chat(j.id)
        msg = [m for m in msgs if m.id == mid][0]
        assert len(msg.photo_list) == 2
        assert "img_001.jpg" in msg.photo_list

    def test_delete_chat_message(self, repo, chat_data):
        """Chat messages can be deleted."""
        j, u = chat_data["job"], chat_data["boss"]
        mid = repo.send_chat_message(j.id, u.id, "Delete me")
        repo.delete_job_update(mid)

        msgs = repo.get_job_chat(j.id)
        assert not any(m.id == mid for m in msgs)


# =====================================================================
# Loop 13 — DM support
# =====================================================================


class TestDirectMessages:
    """Private DMs between job team members."""

    def test_send_and_receive_dm(self, repo, chat_data):
        """DMs appear in get_job_dms between the two participants."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]

        repo.send_dm(j.id, boss.id, worker.id, "Hey, bring wire strippers")
        repo.send_dm(j.id, worker.id, boss.id, "On it, boss!")

        convo = repo.get_job_dms(j.id, boss.id, worker.id)
        assert len(convo) == 2
        assert convo[0].message == "Hey, bring wire strippers"
        assert convo[0].recipient_name == "Chat Worker"
        assert convo[1].message == "On it, boss!"

    def test_dm_not_visible_in_group_chat(self, repo, chat_data):
        """DMs don't appear in group chat or updates."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]

        repo.send_dm(j.id, boss.id, worker.id, "Secret message")

        chat = repo.get_job_chat(j.id)
        assert not any(m.message == "Secret message" for m in chat)

        updates = repo.get_job_updates(j.id)
        assert not any(u.message == "Secret message" for u in updates)

    def test_dm_not_visible_to_third_party(self, repo, chat_data):
        """Third user can't see DMs between other two."""
        j = chat_data["job"]
        boss, worker, foreman = (
            chat_data["boss"], chat_data["worker"], chat_data["foreman"]
        )

        repo.send_dm(j.id, boss.id, worker.id, "Private convo")

        # Foreman queries for DMs between self and boss — should be empty
        convo = repo.get_job_dms(j.id, foreman.id, boss.id)
        assert len(convo) == 0

    def test_dm_self_blocked(self, repo, chat_data):
        """Can't DM yourself."""
        j, boss = chat_data["job"], chat_data["boss"]
        with pytest.raises(ValueError, match="Cannot send a DM to yourself"):
            repo.send_dm(j.id, boss.id, boss.id, "Talking to myself")

    def test_dm_contacts(self, repo, chat_data):
        """get_dm_contacts shows who you've been chatting with."""
        j = chat_data["job"]
        boss, worker, foreman = (
            chat_data["boss"], chat_data["worker"], chat_data["foreman"]
        )

        repo.send_dm(j.id, boss.id, worker.id, "Hey worker")
        repo.send_dm(j.id, boss.id, foreman.id, "Hey foreman")

        contacts = repo.get_dm_contacts(j.id, boss.id)
        assert len(contacts) == 2
        names = [c["display_name"] for c in contacts]
        assert "Chat Worker" in names
        assert "Chat Foreman" in names

    def test_dm_pagination(self, repo, chat_data):
        """DM conversations support offset pagination."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]
        for i in range(8):
            repo.send_dm(j.id, boss.id, worker.id, f"DM-{i:02d}")

        page1 = repo.get_job_dms(j.id, boss.id, worker.id, limit=4, offset=0)
        page2 = repo.get_job_dms(j.id, boss.id, worker.id, limit=4, offset=4)
        assert len(page1) == 4
        assert len(page2) == 4
        assert page1[0].message == "DM-00"
        assert page2[0].message == "DM-04"

    def test_dm_not_on_dashboard(self, repo, chat_data):
        """DMs are excluded from the dashboard feed."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]
        repo.send_dm(j.id, boss.id, worker.id, "Private stuff")

        latest = repo.get_latest_updates_across_jobs(limit=50)
        assert not any(up.update_type == "dm" for up in latest)


# =====================================================================
# Loop 14 — Read receipts and unread counts
# =====================================================================


class TestReadReceipts:
    """Unread DM tracking and mark-as-read."""

    def test_new_dm_is_unread(self, repo, chat_data):
        """Freshly sent DMs have is_read = 0."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]
        repo.send_dm(j.id, boss.id, worker.id, "Read this!")

        count = repo.get_unread_dm_count(j.id, worker.id)
        assert count == 1

    def test_mark_dms_read(self, repo, chat_data):
        """mark_dms_read clears unread count for a specific sender."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]
        repo.send_dm(j.id, boss.id, worker.id, "Msg 1")
        repo.send_dm(j.id, boss.id, worker.id, "Msg 2")

        assert repo.get_unread_dm_count(j.id, worker.id) == 2
        repo.mark_dms_read(j.id, reader_id=worker.id, sender_id=boss.id)
        assert repo.get_unread_dm_count(j.id, worker.id) == 0

    def test_mark_read_only_from_sender(self, repo, chat_data):
        """Marking read from one sender doesn't affect another sender's DMs."""
        j = chat_data["job"]
        boss, worker, foreman = (
            chat_data["boss"], chat_data["worker"], chat_data["foreman"]
        )
        repo.send_dm(j.id, boss.id, worker.id, "From boss")
        repo.send_dm(j.id, foreman.id, worker.id, "From foreman")

        repo.mark_dms_read(j.id, reader_id=worker.id, sender_id=boss.id)
        assert repo.get_unread_dm_count(j.id, worker.id) == 1  # foreman's still

    def test_total_unread_across_jobs(self, repo, chat_data):
        """get_total_unread_dm_count counts DMs across all jobs."""
        boss, worker = chat_data["boss"], chat_data["worker"]
        j1 = chat_data["job"]

        j2 = Job(job_number="JOB-CHAT-002", name="Second Job", status="active")
        j2.id = repo.create_job(j2)
        repo.assign_user_to_job(JobAssignment(
            job_id=j2.id, user_id=worker.id, role="worker",
        ))
        repo.assign_user_to_job(JobAssignment(
            job_id=j2.id, user_id=boss.id, role="worker",
        ))

        repo.send_dm(j1.id, boss.id, worker.id, "Job 1 DM")
        repo.send_dm(j2.id, boss.id, worker.id, "Job 2 DM")

        total = repo.get_total_unread_dm_count(worker.id)
        assert total == 2

    def test_read_dms_not_double_counted(self, repo, chat_data):
        """Already-read DMs aren't counted again."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]
        repo.send_dm(j.id, boss.id, worker.id, "Already read")
        repo.mark_dms_read(j.id, reader_id=worker.id, sender_id=boss.id)

        # Send a new one
        repo.send_dm(j.id, boss.id, worker.id, "New message")
        assert repo.get_unread_dm_count(j.id, worker.id) == 1


# =====================================================================
# Loop 15 — Chat search
# =====================================================================


class TestChatSearch:
    """Searching chat and update messages by keyword."""

    def test_search_finds_matching(self, repo, chat_data):
        """search_job_chat returns messages matching the query."""
        j, u = chat_data["job"], chat_data["boss"]
        repo.send_chat_message(j.id, u.id, "Use 12 AWG wire for panel A")
        repo.send_chat_message(j.id, u.id, "Panel B needs conduit")
        repo.send_chat_message(j.id, u.id, "Lunch at noon")

        results = repo.search_job_chat(j.id, "panel")
        assert len(results) == 2
        assert all("panel" in r.message.lower() for r in results)

    def test_search_excludes_dms(self, repo, chat_data):
        """Search doesn't return DM content (privacy)."""
        j, boss, worker = chat_data["job"], chat_data["boss"], chat_data["worker"]
        repo.send_dm(j.id, boss.id, worker.id, "Secret panel info")
        repo.send_chat_message(j.id, boss.id, "Panel update for all")

        results = repo.search_job_chat(j.id, "panel")
        assert len(results) == 1
        assert results[0].update_type != "dm"

    def test_search_with_special_chars(self, repo, chat_data):
        """LIKE special chars are escaped in search."""
        j, u = chat_data["job"], chat_data["boss"]
        repo.send_chat_message(j.id, u.id, "Use 50% more wire")
        repo.send_chat_message(j.id, u.id, "Something else")

        results = repo.search_job_chat(j.id, "50%")
        assert len(results) == 1
        assert "50%" in results[0].message

    def test_search_empty_returns_nothing(self, repo, chat_data):
        """No matches returns empty list."""
        j, u = chat_data["job"], chat_data["boss"]
        repo.send_chat_message(j.id, u.id, "Hello world")
        results = repo.search_job_chat(j.id, "xyznonexistent")
        assert len(results) == 0

    def test_search_includes_comments(self, repo, chat_data):
        """Search also finds legacy comments, not just chat."""
        j, u = chat_data["job"], chat_data["boss"]
        repo.create_job_update(j.id, u.id, "Wire gauge comment", update_type="comment")
        repo.send_chat_message(j.id, u.id, "Wire gauge discussion")

        results = repo.search_job_chat(j.id, "wire gauge")
        assert len(results) == 2
