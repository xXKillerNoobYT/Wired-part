"""Tests for notebook system — notebooks, sections, pages."""

import pytest

from wired_part.database.models import (
    Job,
    NotebookPage,
    NotebookSection,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def notebook_data(repo):
    """Create user and job for notebook tests."""
    user = User(
        username="noteuser", display_name="Note User",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    job = Job(
        job_number="JOB-NOTE-001", name="Notebook Test Job",
        status="active",
    )
    job_id = repo.create_job(job)

    return {"user_id": user_id, "job_id": job_id}


class TestNotebookAutoCreate:
    """Test notebook auto-creation for jobs."""

    def test_get_or_create_notebook(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        assert nb is not None
        assert nb.job_id == notebook_data["job_id"]
        assert "JOB-NOTE-001" in nb.title

    def test_default_sections_created(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        assert len(sections) == 5
        names = [s.name for s in sections]
        assert "Daily Logs" in names
        assert "Safety Notes" in names
        assert "Change Orders" in names
        assert "Punch List" in names
        assert "General" in names

    def test_idempotent_get_or_create(self, repo, notebook_data):
        nb1 = repo.get_or_create_notebook(notebook_data["job_id"])
        nb2 = repo.get_or_create_notebook(notebook_data["job_id"])
        assert nb1.id == nb2.id

    def test_get_notebook_for_job_not_found(self, repo):
        nb = repo.get_notebook_for_job(9999)
        assert nb is None


class TestSectionCRUD:
    """Test notebook section operations."""

    def test_create_section(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        section = NotebookSection(
            notebook_id=nb.id, name="Custom Section",
        )
        sid = repo.create_section(section)
        assert sid > 0

    def test_update_section(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sid = repo.create_section(NotebookSection(
            notebook_id=nb.id, name="Original",
        ))
        sections = repo.get_sections(nb.id)
        custom = [s for s in sections if s.name == "Original"][0]
        custom.name = "Renamed"
        repo.update_section(custom)

        sections = repo.get_sections(nb.id)
        names = [s.name for s in sections]
        assert "Renamed" in names
        assert "Original" not in names

    def test_delete_section(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sid = repo.create_section(NotebookSection(
            notebook_id=nb.id, name="To Delete",
        ))
        initial_count = len(repo.get_sections(nb.id))
        repo.delete_section(sid)
        assert len(repo.get_sections(nb.id)) == initial_count - 1

    def test_reorder_sections(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        # Reverse the order
        reversed_ids = [s.id for s in reversed(sections)]
        repo.reorder_sections(nb.id, reversed_ids)

        reordered = repo.get_sections(nb.id)
        assert reordered[0].id == reversed_ids[0]


class TestPageCRUD:
    """Test notebook page operations."""

    def test_create_page(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        page = NotebookPage(
            section_id=sections[0].id,
            title="Day 1 Log",
            content="<p>Started rough-in wiring today.</p>",
            created_by=notebook_data["user_id"],
        )
        pid = repo.create_page(page)
        assert pid > 0

    def test_get_page_by_id(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        pid = repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Test Page",
            content="<b>Bold content</b>",
            created_by=notebook_data["user_id"],
        ))
        page = repo.get_page_by_id(pid)
        assert page.title == "Test Page"
        assert "<b>Bold content</b>" in page.content
        assert page.created_by_name == "Note User"
        assert page.section_name == sections[0].name

    def test_update_page(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        pid = repo.create_page(NotebookPage(
            section_id=sections[0].id, title="Original",
        ))
        page = repo.get_page_by_id(pid)
        page.title = "Updated Title"
        page.content = "<p>Updated content</p>"
        repo.update_page(page)

        updated = repo.get_page_by_id(pid)
        assert updated.title == "Updated Title"
        assert "Updated content" in updated.content

    def test_delete_page(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        pid = repo.create_page(NotebookPage(
            section_id=sections[0].id, title="To Delete",
        ))
        assert repo.get_page_by_id(pid) is not None
        repo.delete_page(pid)
        assert repo.get_page_by_id(pid) is None

    def test_get_pages_for_section(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        sid = sections[0].id

        repo.create_page(NotebookPage(
            section_id=sid, title="Page 1",
        ))
        repo.create_page(NotebookPage(
            section_id=sid, title="Page 2",
        ))
        pages = repo.get_pages(sid)
        assert len(pages) == 2

    def test_page_with_photos_json(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        import json
        photos = json.dumps(["photo1.jpg", "photo2.jpg"])
        pid = repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Photo Page",
            photos=photos,
        ))
        page = repo.get_page_by_id(pid)
        assert page.photo_list == ["photo1.jpg", "photo2.jpg"]

    def test_page_with_part_references(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        import json
        refs = json.dumps([1, 5, 10])
        pid = repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Parts Page",
            part_references=refs,
        ))
        page = repo.get_page_by_id(pid)
        assert page.part_reference_list == [1, 5, 10]


class TestNotebookSearch:
    """Test searching across notebook pages."""

    def test_search_by_title(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Electrical rough-in notes",
            content="Nothing special",
        ))
        repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Safety meeting",
            content="Discussed PPE",
        ))

        results = repo.search_notebook_pages("rough-in")
        assert len(results) == 1
        assert "rough-in" in results[0].title.lower()

    def test_search_by_content(self, repo, notebook_data):
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Page A",
            content="Installed GFCI outlets in the kitchen",
        ))
        results = repo.search_notebook_pages("GFCI")
        assert len(results) == 1

    def test_search_scoped_to_job(self, repo, notebook_data):
        # Create notebook and page for main job
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        repo.create_page(NotebookPage(
            section_id=sections[0].id,
            title="Main job wire",
            content="Wire installed",
        ))

        # Create a second job with notebook
        job2_id = repo.create_job(Job(
            job_number="JOB-NOTE-002", name="Other Job",
            status="active",
        ))
        nb2 = repo.get_or_create_notebook(job2_id)
        sections2 = repo.get_sections(nb2.id)
        repo.create_page(NotebookPage(
            section_id=sections2[0].id,
            title="Other wire",
            content="Wire in other job",
        ))

        # Search all
        all_results = repo.search_notebook_pages("wire")
        assert len(all_results) == 2

        # Search scoped to job 1
        scoped = repo.search_notebook_pages(
            "wire", job_id=notebook_data["job_id"]
        )
        assert len(scoped) == 1
        assert scoped[0].title == "Main job wire"

    def test_empty_search_returns_nothing(self, repo):
        results = repo.search_notebook_pages("")
        assert results == []

    def test_cascade_delete_job_removes_notebook(self, repo, notebook_data):
        """Deleting a job should cascade-delete its notebook."""
        nb = repo.get_or_create_notebook(notebook_data["job_id"])
        sections = repo.get_sections(nb.id)
        repo.create_page(NotebookPage(
            section_id=sections[0].id, title="Will be deleted",
        ))

        repo.delete_job(notebook_data["job_id"])
        assert repo.get_notebook_for_job(notebook_data["job_id"]) is None
