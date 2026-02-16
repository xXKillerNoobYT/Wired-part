"""Full notifications page with filtering, dismiss, and click-to-navigate."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository


class NotificationsPage(QWidget):
    """Full notification centre with filters, table, dismiss, and navigation."""

    navigate_requested = Signal(str, int)  # (target_tab, entity_id)

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._notifications: list = []
        self._setup_ui()

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Notifications")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Filter bar
        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("Severity:"))
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["All", "info", "warning", "critical"])
        self.severity_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.severity_combo)

        filter_row.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(["All", "system", "agent", "sync", "user"])
        self.source_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.source_combo)

        filter_row.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "Unread", "Read"])
        self.status_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.status_combo)

        filter_row.addStretch()

        self.mark_all_btn = QPushButton("Mark All Read")
        self.mark_all_btn.clicked.connect(self._mark_all_read)
        filter_row.addWidget(self.mark_all_btn)

        layout.addLayout(filter_row)

        # Notification table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Severity", "Title", "Message", "Source", "Time", "Status",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMinimumHeight(3 * 30 + 30 + 2)  # 3 rows + header
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch,
        )
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table, 1)

        # Bottom controls
        bottom_row = QHBoxLayout()
        self.count_label = QLabel("0 notifications")
        bottom_row.addWidget(self.count_label)
        bottom_row.addStretch()

        self.dismiss_btn = QPushButton("Dismiss Selected")
        self.dismiss_btn.clicked.connect(self._dismiss_selected)
        bottom_row.addWidget(self.dismiss_btn)

        layout.addLayout(bottom_row)

    # ── Data ────────────────────────────────────────────────────

    def refresh(self):
        """Reload notifications with current filter settings."""
        self._apply_filters()

    def _apply_filters(self):
        severity = self.severity_combo.currentText()
        source = self.source_combo.currentText()
        status = self.status_combo.currentText()

        sev_val = None if severity == "All" else severity
        src_val = None if source == "All" else source
        read_val = None
        if status == "Unread":
            read_val = 0
        elif status == "Read":
            read_val = 1

        self._notifications = self.repo.get_user_notifications_filtered(
            self.current_user.id,
            severity=sev_val,
            source=src_val,
            is_read=read_val,
            limit=50,
        )
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self._notifications))
        for row, n in enumerate(self._notifications):
            # Severity icon
            icon_map = {
                "info": "\u2139\ufe0f",
                "warning": "\u26a0\ufe0f",
                "critical": "\u274c",
            }
            sev_item = QTableWidgetItem(
                icon_map.get(n.severity, "") + " " + n.severity
            )
            sev_item.setData(Qt.UserRole, n.id)
            self.table.setItem(row, 0, sev_item)

            self.table.setItem(row, 1, QTableWidgetItem(n.title or ""))
            self.table.setItem(row, 2, QTableWidgetItem(n.message or ""))
            self.table.setItem(row, 3, QTableWidgetItem(n.source or ""))

            time_str = ""
            if n.created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(n.created_at))
                    time_str = dt.strftime("%b %d %I:%M %p")
                except (ValueError, TypeError):
                    time_str = str(n.created_at)
            self.table.setItem(row, 4, QTableWidgetItem(time_str))

            status_text = "Read" if n.is_read else "Unread"
            status_item = QTableWidgetItem(status_text)
            if not n.is_read:
                font = status_item.font()
                font.setBold(True)
                status_item.setFont(font)
            self.table.setItem(row, 5, status_item)

        self.count_label.setText(f"{len(self._notifications)} notifications")

    # ── Actions ─────────────────────────────────────────────────

    def _on_cell_clicked(self, row: int, _col: int):
        """Mark notification read and navigate to its target."""
        if row >= len(self._notifications):
            return
        n = self._notifications[row]

        # Mark read
        if not n.is_read and n.id:
            self.repo.mark_notification_read(n.id)
            n.is_read = 1
            status_item = QTableWidgetItem("Read")
            self.table.setItem(row, 5, status_item)

        # Navigate if target set
        if n.target_tab:
            entity_id = 0
            if n.target_data:
                try:
                    entity_id = int(n.target_data)
                except (ValueError, TypeError):
                    pass
            self.navigate_requested.emit(n.target_tab, entity_id)

    def _dismiss_selected(self):
        """Mark selected notifications as read."""
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())
        for row in rows:
            if row < len(self._notifications):
                n = self._notifications[row]
                if not n.is_read and n.id:
                    self.repo.mark_notification_read(n.id)
        self._apply_filters()

    def _mark_all_read(self):
        """Mark all of this user's notifications as read."""
        self.repo.mark_all_notifications_read(self.current_user.id)
        self._apply_filters()
