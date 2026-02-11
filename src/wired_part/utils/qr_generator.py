"""Generate printable QR tag PDFs for parts.

Creates label-style PDF pages (Avery 5160 compatible) with QR codes
and human-readable part information.  Each label contains:
  - QR code (left) encoding ``WP:<identifier>``
  - Text block (right): Name, Part Number, Local PN, Location, Category

Usage::

    from wired_part.utils.qr_generator import generate_qr_tags

    parts = [
        {"part_id": 1, "name": "Duplex Outlet", "part_number": "OUT-001",
         "local_part_number": "LP-0001", "location": "Shelf A-3",
         "category_name": "Switches & Outlets"},
    ]
    pdf_path = generate_qr_tags(parts)
"""

import io
import os
import tempfile

import qrcode
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# ── Label grid constants (Avery 5160 compatible) ─────────────
PAGE_WIDTH, PAGE_HEIGHT = LETTER  # 8.5 × 11 inches
COLS = 3
ROWS_PER_PAGE = 10
LABEL_WIDTH = 2.625 * inch
LABEL_HEIGHT = 1.0 * inch
LEFT_MARGIN = 0.1875 * inch
TOP_MARGIN = 0.5 * inch
COL_GAP = 0.125 * inch
ROW_GAP = 0.0 * inch  # Avery 5160 has no vertical gap

QR_SIZE = 0.85 * inch
TEXT_LEFT_OFFSET = 0.95 * inch
FONT_NAME = "Helvetica"
FONT_SIZE_NAME = 7
FONT_SIZE_DETAIL = 5.5


def generate_qr_tags(
    parts: list[dict],
    output_path: str | None = None,
) -> str:
    """Generate a PDF with QR code labels for the given parts.

    Args:
        parts: List of dicts with keys:
            - part_id (int)
            - name (str)
            - part_number (str)
            - local_part_number (str)
            - location (str)
            - category_name (str)
        output_path: Optional output PDF path.  If *None*, creates a
            temp file in the system temp directory.

    Returns:
        Absolute path to the generated PDF file.
    """
    if not output_path:
        output_path = os.path.join(
            tempfile.gettempdir(), "wired_part_qr_tags.pdf"
        )

    c = canvas.Canvas(output_path, pagesize=LETTER)
    c.setTitle("Wired-Part QR Tags")

    for idx, part in enumerate(parts):
        col = idx % COLS
        row_on_page = (idx // COLS) % ROWS_PER_PAGE

        # New page if needed (except for the very first label)
        if idx > 0 and col == 0 and row_on_page == 0:
            c.showPage()

        # Calculate label position (top-left corner)
        x = LEFT_MARGIN + col * (LABEL_WIDTH + COL_GAP)
        y = (
            PAGE_HEIGHT
            - TOP_MARGIN
            - row_on_page * (LABEL_HEIGHT + ROW_GAP)
            - LABEL_HEIGHT
        )

        # Generate QR code
        qr_data = _build_qr_data(part)
        qr_img = _make_qr_image(qr_data)

        # Draw QR code
        c.drawImage(
            ImageReader(qr_img),
            x + 0.05 * inch,
            y + 0.075 * inch,
            width=QR_SIZE,
            height=QR_SIZE,
        )

        # Draw text info
        text_x = x + TEXT_LEFT_OFFSET
        text_y = y + LABEL_HEIGHT - 0.15 * inch

        # Name (bold, larger)
        c.setFont(FONT_NAME + "-Bold", FONT_SIZE_NAME)
        c.drawString(text_x, text_y, _truncate(part.get("name", ""), 22))

        # Part number
        text_y -= 0.12 * inch
        c.setFont(FONT_NAME, FONT_SIZE_DETAIL)
        pn = part.get("part_number", "") or part.get(
            "local_part_number", ""
        )
        if pn:
            c.drawString(text_x, text_y, f"PN: {_truncate(pn, 24)}")

        # Local PN (if different from above)
        lpn = part.get("local_part_number", "")
        if lpn and lpn != pn:
            text_y -= 0.1 * inch
            c.drawString(text_x, text_y, f"LPN: {_truncate(lpn, 22)}")

        # Location
        loc = part.get("location", "")
        if loc:
            text_y -= 0.1 * inch
            c.drawString(text_x, text_y, f"Loc: {_truncate(loc, 22)}")

        # Category
        cat = part.get("category_name", "")
        if cat:
            text_y -= 0.1 * inch
            c.drawString(text_x, text_y, f"Cat: {_truncate(cat, 22)}")

    c.save()
    return output_path


def _build_qr_data(part: dict) -> str:
    """Build the string to encode in the QR code.

    Format: ``WP:<identifier>`` where identifier is the local part
    number if available, otherwise part number, with part_id as fallback.
    """
    lpn = part.get("local_part_number", "")
    pn = part.get("part_number", "")
    pid = part.get("part_id", "")
    identifier = lpn or pn or str(pid)
    return f"WP:{identifier}"


def _make_qr_image(data: str) -> io.BytesIO:
    """Generate a QR code image and return as a BytesIO buffer."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) > max_len:
        return text[: max_len - 1] + "\u2026"
    return text
