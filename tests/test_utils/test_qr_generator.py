"""Tests for QR tag PDF generation."""

import os
import tempfile

import pytest

from wired_part.utils.qr_generator import (
    _build_qr_data,
    _make_qr_image,
    _truncate,
    generate_qr_tags,
)


def _sample_parts(count: int = 1) -> list[dict]:
    """Build a list of sample part dicts for testing."""
    parts = []
    for i in range(1, count + 1):
        parts.append({
            "part_id": i,
            "name": f"Test Part {i}",
            "part_number": f"TP-{i:04d}",
            "local_part_number": f"LP-{i:04d}",
            "location": f"Shelf A-{i}",
            "category_name": "Switches & Outlets",
        })
    return parts


class TestQRDataBuilder:
    """Test the QR data string builder."""

    def test_prefers_local_part_number(self):
        data = _build_qr_data({
            "part_id": 1,
            "part_number": "TP-001",
            "local_part_number": "LP-001",
        })
        assert data == "WP:LP-001"

    def test_falls_back_to_part_number(self):
        data = _build_qr_data({
            "part_id": 1,
            "part_number": "TP-001",
            "local_part_number": "",
        })
        assert data == "WP:TP-001"

    def test_falls_back_to_part_id(self):
        data = _build_qr_data({
            "part_id": 42,
            "part_number": "",
            "local_part_number": "",
        })
        assert data == "WP:42"

    def test_missing_keys_uses_part_id(self):
        data = _build_qr_data({"part_id": 7})
        assert data == "WP:7"


class TestQRImage:
    """Test QR code image generation."""

    def test_returns_png_buffer(self):
        buf = _make_qr_image("WP:TEST-001")
        header = buf.read(8)
        # PNG magic bytes
        assert header[:4] == b"\x89PNG"

    def test_buffer_is_seekable(self):
        buf = _make_qr_image("WP:LP-001")
        buf.seek(0)
        assert buf.tell() == 0


class TestTruncate:
    """Test the text truncation helper."""

    def test_short_text_unchanged(self):
        assert _truncate("Hello", 10) == "Hello"

    def test_exact_length_unchanged(self):
        assert _truncate("Hello", 5) == "Hello"

    def test_long_text_truncated(self):
        result = _truncate("Hello World", 8)
        assert len(result) == 8
        assert result.endswith("\u2026")

    def test_one_over_truncated(self):
        result = _truncate("ABCDEF", 5)
        assert result == "ABCD\u2026"


class TestGenerateQRTags:
    """Test PDF generation end-to-end."""

    def test_generates_pdf_file(self, tmp_path):
        out = str(tmp_path / "tags.pdf")
        result = generate_qr_tags(_sample_parts(3), output_path=out)
        assert result == out
        assert os.path.isfile(out)
        # PDF should start with %PDF
        with open(out, "rb") as f:
            assert f.read(4) == b"%PDF"

    def test_default_output_path(self):
        """Without explicit path, uses temp dir."""
        result = generate_qr_tags(_sample_parts(1))
        assert os.path.isfile(result)
        assert result.endswith(".pdf")
        # Clean up
        os.remove(result)

    def test_custom_output_path(self, tmp_path):
        out = str(tmp_path / "custom_tags.pdf")
        result = generate_qr_tags(_sample_parts(2), output_path=out)
        assert result == out
        assert os.path.isfile(out)
        # Non-trivial file size
        assert os.path.getsize(out) > 500

    def test_single_part(self, tmp_path):
        out = str(tmp_path / "single.pdf")
        generate_qr_tags(_sample_parts(1), output_path=out)
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 500

    def test_multiple_pages(self, tmp_path):
        """35 parts = 2 pages (30 per page)."""
        out = str(tmp_path / "multi.pdf")
        generate_qr_tags(_sample_parts(35), output_path=out)
        assert os.path.isfile(out)
        # Multi-page PDF should be larger than single-page
        multi_size = os.path.getsize(out)

        single_out = str(tmp_path / "single_page.pdf")
        generate_qr_tags(_sample_parts(5), output_path=single_out)
        single_size = os.path.getsize(single_out)

        assert multi_size > single_size

    def test_empty_fields_handled(self, tmp_path):
        """Parts with missing optional fields shouldn't crash."""
        out = str(tmp_path / "sparse.pdf")
        parts = [{
            "part_id": 1,
            "name": "Bare Part",
            "part_number": "",
            "local_part_number": "",
            "location": "",
            "category_name": "",
        }]
        generate_qr_tags(parts, output_path=out)
        assert os.path.isfile(out)

    def test_long_names_truncated(self, tmp_path):
        """Parts with very long names should still generate successfully."""
        out = str(tmp_path / "long.pdf")
        parts = [{
            "part_id": 1,
            "name": "A" * 100,
            "part_number": "B" * 100,
            "local_part_number": "C" * 100,
            "location": "D" * 100,
            "category_name": "E" * 100,
        }]
        generate_qr_tags(parts, output_path=out)
        assert os.path.isfile(out)

    def test_exact_page_boundary(self, tmp_path):
        """Exactly 30 parts = 1 full page, no second page started."""
        out = str(tmp_path / "exact30.pdf")
        generate_qr_tags(_sample_parts(30), output_path=out)
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 500
