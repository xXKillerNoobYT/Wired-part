"""Tests for notebook attachment CRUD operations."""

import pytest

from wired_part.database.models import (
    Job,
    NotebookAttachment,
    NotebookPage,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def notebook_setup(repo):
    """Create user, job, notebook, section, and page for attachment tests."""
    user = User(
        username="attuser", display_name="Att User",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    job = Job(
        job_number="JOB-ATT-001", name="Attachment Test Job",
        status="active",
    )
    job_id = repo.create_job(job)

    notebook = repo.get_or_create_notebook(job_id)
    sections = repo.get_sections(notebook.id)
    section_id = sections[0].id

    page = NotebookPage(
        section_id=section_id,
        title="Test Page",
        created_by=user_id,
    )
    page_id = repo.create_page(page)

    return {
        "user_id": user_id,
        "job_id": job_id,
        "notebook_id": notebook.id,
        "section_id": section_id,
        "page_id": page_id,
    }


class TestCreateAttachment:
    def test_create_attachment(self, repo, notebook_setup):
        att = NotebookAttachment(
            page_id=notebook_setup["page_id"],
            filename="photo.jpg",
            file_path="/tmp/photo.jpg",
            file_type="jpg",
            file_size=102400,
            created_by=notebook_setup["user_id"],
        )
        att_id = repo.create_attachment(att)
        assert att_id > 0

    def test_create_multiple_attachments(self, repo, notebook_setup):
        page_id = notebook_setup["page_id"]
        for i in range(3):
            att = NotebookAttachment(
                page_id=page_id,
                filename=f"file_{i}.pdf",
                file_path=f"/tmp/file_{i}.pdf",
                file_type="pdf",
                file_size=1000 * (i + 1),
            )
            repo.create_attachment(att)

        attachments = repo.get_attachments(page_id)
        assert len(attachments) == 3


class TestGetAttachments:
    def test_get_attachments_for_page(self, repo, notebook_setup):
        page_id = notebook_setup["page_id"]
        att = NotebookAttachment(
            page_id=page_id,
            filename="doc.pdf",
            file_path="/tmp/doc.pdf",
            file_type="pdf",
            file_size=5000,
        )
        repo.create_attachment(att)

        attachments = repo.get_attachments(page_id)
        assert len(attachments) == 1
        assert attachments[0].filename == "doc.pdf"
        assert attachments[0].file_type == "pdf"
        assert attachments[0].file_size == 5000

    def test_get_attachments_empty_page(self, repo, notebook_setup):
        attachments = repo.get_attachments(notebook_setup["page_id"])
        assert len(attachments) == 0

    def test_get_attachments_does_not_cross_pages(self, repo, notebook_setup):
        page_id = notebook_setup["page_id"]

        # Create a second page
        page2 = NotebookPage(
            section_id=notebook_setup["section_id"],
            title="Other Page",
        )
        page2_id = repo.create_page(page2)

        # Attach to first page only
        att = NotebookAttachment(
            page_id=page_id,
            filename="first_page.txt",
            file_path="/tmp/first.txt",
            file_type="txt",
            file_size=100,
        )
        repo.create_attachment(att)

        # Second page should have no attachments
        assert len(repo.get_attachments(page2_id)) == 0
        assert len(repo.get_attachments(page_id)) == 1

    def test_get_attachment_by_id(self, repo, notebook_setup):
        att = NotebookAttachment(
            page_id=notebook_setup["page_id"],
            filename="specific.png",
            file_path="/tmp/specific.png",
            file_type="png",
            file_size=25000,
            created_by=notebook_setup["user_id"],
        )
        att_id = repo.create_attachment(att)

        fetched = repo.get_attachment_by_id(att_id)
        assert fetched is not None
        assert fetched.id == att_id
        assert fetched.filename == "specific.png"
        assert fetched.file_size == 25000

    def test_get_attachment_by_id_not_found(self, repo):
        assert repo.get_attachment_by_id(99999) is None


class TestDeleteAttachment:
    def test_delete_attachment(self, repo, notebook_setup):
        page_id = notebook_setup["page_id"]
        att = NotebookAttachment(
            page_id=page_id,
            filename="deleteme.txt",
            file_path="/tmp/deleteme.txt",
            file_type="txt",
            file_size=50,
        )
        att_id = repo.create_attachment(att)

        repo.delete_attachment(att_id)
        assert repo.get_attachment_by_id(att_id) is None
        assert len(repo.get_attachments(page_id)) == 0

    def test_delete_one_keeps_others(self, repo, notebook_setup):
        page_id = notebook_setup["page_id"]
        ids = []
        for i in range(3):
            att = NotebookAttachment(
                page_id=page_id,
                filename=f"keep_{i}.txt",
                file_path=f"/tmp/keep_{i}.txt",
                file_type="txt",
                file_size=100,
            )
            ids.append(repo.create_attachment(att))

        repo.delete_attachment(ids[1])  # Delete middle one

        remaining = repo.get_attachments(page_id)
        assert len(remaining) == 2
        remaining_ids = {a.id for a in remaining}
        assert ids[0] in remaining_ids
        assert ids[2] in remaining_ids

    def test_cascade_delete_on_page_delete(self, repo, notebook_setup):
        page_id = notebook_setup["page_id"]
        att = NotebookAttachment(
            page_id=page_id,
            filename="cascade.txt",
            file_path="/tmp/cascade.txt",
            file_type="txt",
            file_size=10,
        )
        att_id = repo.create_attachment(att)

        repo.delete_page(page_id)
        assert repo.get_attachment_by_id(att_id) is None


class TestAttachmentModel:
    def test_model_defaults(self):
        att = NotebookAttachment()
        assert att.id is None
        assert att.page_id == 0
        assert att.filename == ""
        assert att.file_path == ""
        assert att.file_type == ""
        assert att.file_size == 0
        assert att.created_by is None
        assert att.created_at is None

    def test_model_with_values(self):
        att = NotebookAttachment(
            page_id=5,
            filename="report.xlsx",
            file_path="/data/report.xlsx",
            file_type="xlsx",
            file_size=500000,
            created_by=3,
        )
        assert att.page_id == 5
        assert att.filename == "report.xlsx"
        assert att.file_type == "xlsx"
        assert att.file_size == 500000
