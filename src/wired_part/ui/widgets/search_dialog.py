"""Global search dialog (Ctrl+K) — spotlight-style floating search."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from wired_part.database.repository import Repository

# Category icons (text-based) and colors
_CATEGORY_STYLE = {
    "job": ("[Job]", "#f9e2af"),
    "part": ("[Part]", "#89b4fa"),
    "user": ("[User]", "#a6e3a1"),
    "order": ("[PO]", "#cba6f7"),
    "page": ("[Note]", "#fab387"),
}


class SearchDialog(QDialog):
    """Spotlight-style global search accessible via Ctrl+K."""

    result_selected = Signal(str, int)  # (entity_type, entity_id)

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Search")
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.Popup
        )
        self.setMinimumSize(500, 400)
        self.setMaximumSize(600, 500)

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._do_search)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # All styling via QSS object names — no inline setStyleSheet
        self.setObjectName("SearchDialog")

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Search jobs, parts, users, orders, notes...")
        self.search_input.setMinimumHeight(36)
        self.search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_input)

        # Category counts row
        self.counts_label = QLabel("")
        self.counts_label.setObjectName("SearchCountsLabel")
        layout.addWidget(self.counts_label)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setObjectName("SearchResultsList")
        self.results_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.results_list, 1)

        # Hint
        hint = QLabel("Enter to select  |  Esc to close")
        hint.setObjectName("SearchHint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def _on_text_changed(self, text: str):
        self._debounce.start()

    def _do_search(self):
        query = self.search_input.text().strip()
        if len(query) < 2:
            self.results_list.clear()
            self.counts_label.setText("")
            return

        results = self.repo.search_all(query)
        self.results_list.clear()

        # Build counts label
        counts = []
        for cat_key in ("job", "part", "user", "order", "page"):
            cat_results = results.get(f"{cat_key}s", [])
            if cat_results:
                style_info = _CATEGORY_STYLE.get(cat_key, ("[?]", "#cdd6f4"))
                counts.append(
                    f'<span style="color:{style_info[1]}">'
                    f'{len(cat_results)} {cat_key}s</span>'
                )
        self.counts_label.setText("  ".join(counts) if counts else "No results")

        # Populate list in category order
        for cat_key in ("job", "part", "user", "order", "page"):
            cat_results = results.get(f"{cat_key}s", [])
            for r in cat_results:
                style_info = _CATEGORY_STYLE.get(r.get("type", ""), ("[?]", "#cdd6f4"))
                tag = style_info[0]
                color = style_info[1]

                item = QListWidgetItem(
                    f"{tag}  {r['label']}  —  {r.get('sublabel', '')}"
                )
                item.setData(Qt.UserRole, r.get("type", ""))
                item.setData(Qt.UserRole + 1, r.get("id", 0))
                self.results_list.addItem(item)

    def _on_item_activated(self, item: QListWidgetItem):
        entity_type = item.data(Qt.UserRole)
        entity_id = item.data(Qt.UserRole + 1)
        self.result_selected.emit(entity_type, entity_id)
        self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard navigation."""
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Down, Qt.Key_Up):
            # Forward arrow keys to the results list
            self.results_list.setFocus()
            self.results_list.keyPressEvent(event)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            current = self.results_list.currentItem()
            if current:
                self._on_item_activated(current)
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        """Focus the search input when shown."""
        super().showEvent(event)
        self.search_input.clear()
        self.results_list.clear()
        self.counts_label.setText("")
        self.search_input.setFocus()
