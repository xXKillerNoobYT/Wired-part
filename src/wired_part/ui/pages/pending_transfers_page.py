"""Pending Transfers page — outbound, in-transit, and returns tracking."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import TruckTransfer, User
from wired_part.database.repository import Repository


class PendingTransfersPage(QWidget):
    """Three-tab view for tracking transfers at every stage.

    Sub-tabs:
        1. Pending Outbound — warehouse → truck, not yet loaded
        2. In Transit — loaded on trucks, pending delivery confirmation
        3. Recent Returns — truck → warehouse (recently completed)
    """

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Pending Transfers")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addStretch()
        header.addWidget(self.summary_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Sub-tabs
        self.sub_tabs = QTabWidget()
        self.sub_tabs.currentChanged.connect(self._on_tab_changed)

        # Tab 1: Pending Outbound
        self._outbound_tab = _TransferTableTab(
            self.repo, "outbound", current_user=self.current_user,
        )
        self.sub_tabs.addTab(self._outbound_tab, "Pending Outbound")

        # Tab 2: In Transit (on trucks, outbound & pending)
        self._transit_tab = _TransferTableTab(
            self.repo, "transit", current_user=self.current_user,
        )
        self.sub_tabs.addTab(self._transit_tab, "In Transit")

        # Tab 3: Recent Returns
        self._returns_tab = _TransferTableTab(
            self.repo, "returns", current_user=self.current_user,
        )
        self.sub_tabs.addTab(self._returns_tab, "Recent Returns")

        layout.addWidget(self.sub_tabs, 1)

    def refresh(self):
        """Reload all three sub-tabs."""
        self._outbound_tab.refresh()
        self._transit_tab.refresh()
        self._returns_tab.refresh()
        self._update_summary()

    def _on_tab_changed(self, index: int):
        widget = self.sub_tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _update_summary(self):
        outbound = self._outbound_tab.row_count
        transit = self._transit_tab.row_count
        returns = self._returns_tab.row_count
        self.summary_label.setText(
            f"Outbound: {outbound}  |  In Transit: {transit}  |  "
            f"Returns: {returns}"
        )


class _TransferTableTab(QWidget):
    """Single table tab showing transfers of a particular type."""

    COLUMNS = [
        "ID", "Truck", "Part #", "Description", "Qty",
        "Direction", "Status", "Created By", "Date",
    ]

    def __init__(self, repo: Repository, mode: str,
                 current_user: User = None):
        super().__init__()
        self.repo = repo
        self.mode = mode  # "outbound", "transit", or "returns"
        self.current_user = current_user
        self._transfers: list[TruckTransfer] = []
        self._setup_ui()

    @property
    def row_count(self) -> int:
        return len(self._transfers)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch,
        )
        self.table.setColumnHidden(0, True)  # Hide ID column
        layout.addWidget(self.table, 1)

        # Action buttons
        btn_layout = QHBoxLayout()

        if self.mode == "outbound":
            self.receive_btn = QPushButton("Mark as Received")
            self.receive_btn.setToolTip(
                "Mark selected transfers as received on truck"
            )
            self.receive_btn.clicked.connect(self._on_receive)
            btn_layout.addWidget(self.receive_btn)

            self.cancel_btn = QPushButton("Cancel Transfer")
            self.cancel_btn.setToolTip(
                "Cancel selected transfers and return stock to warehouse"
            )
            self.cancel_btn.clicked.connect(self._on_cancel)
            btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch()

        # Item count
        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet("color: #a6adc8;")
        btn_layout.addWidget(self.count_label)

        layout.addLayout(btn_layout)

    def refresh(self):
        """Reload data for this tab."""
        all_transfers = self.repo.get_all_pending_transfers()

        if self.mode == "outbound":
            # Pending outbound: direction=outbound, status=pending
            self._transfers = [
                t for t in all_transfers
                if t.direction == "outbound" and t.status == "pending"
            ]
        elif self.mode == "transit":
            # In transit: these are the same as pending outbound but grouped
            # by truck — show all pending transfers as "in transit"
            self._transfers = [
                t for t in all_transfers
                if t.direction == "outbound" and t.status == "pending"
            ]
        elif self.mode == "returns":
            # Recent returns: use a different query for recent returns
            self._transfers = self.repo.get_recent_returns(limit=50)

        self._populate_table()
        self.count_label.setText(f"{len(self._transfers)} items")

    def _populate_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._transfers))

        for row, t in enumerate(self._transfers):
            date_str = ""
            if t.created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(t.created_at))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = str(t.created_at)[:16]

            cells = [
                QTableWidgetItem(str(t.id or "")),
                QTableWidgetItem(t.truck_number),
                QTableWidgetItem(t.part_number),
                QTableWidgetItem(t.part_description),
                QTableWidgetItem(str(t.quantity)),
                QTableWidgetItem(t.direction.title()),
                QTableWidgetItem(t.status.title()),
                QTableWidgetItem(t.created_by_name),
                QTableWidgetItem(date_str),
            ]

            # Color code by status
            if t.status == "pending":
                for cell in cells:
                    cell.setForeground(Qt.GlobalColor.yellow)
            elif t.status == "received":
                for cell in cells:
                    cell.setForeground(Qt.GlobalColor.green)

            for col, cell in enumerate(cells):
                if col == 4:  # Qty column — right align
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)

    def _get_selected_transfer_ids(self) -> list[int]:
        """Get IDs of all selected rows."""
        rows = set()
        for idx in self.table.selectionModel().selectedRows():
            rows.add(idx.row())
        ids = []
        for row in sorted(rows):
            item = self.table.item(row, 0)
            if item and item.text():
                ids.append(int(item.text()))
        return ids

    def _on_receive(self):
        """Mark selected outbound transfers as received."""
        ids = self._get_selected_transfer_ids()
        if not ids:
            QMessageBox.information(
                self, "No Selection",
                "Select one or more transfers to receive.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Receive",
            f"Mark {len(ids)} transfer(s) as received on truck?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        user_id = self.current_user.id if self.current_user else None
        errors = []
        for tid in ids:
            try:
                self.repo.receive_transfer(tid, received_by=user_id)
            except Exception as e:
                errors.append(f"Transfer {tid}: {e}")

        if errors:
            QMessageBox.warning(
                self, "Some Errors",
                "\n".join(errors),
            )

        self.refresh()

    def _on_cancel(self):
        """Cancel selected outbound transfers."""
        ids = self._get_selected_transfer_ids()
        if not ids:
            QMessageBox.information(
                self, "No Selection",
                "Select one or more transfers to cancel.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cancel",
            f"Cancel {len(ids)} transfer(s)?\n"
            "Stock will be returned to the warehouse.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        errors = []
        for tid in ids:
            try:
                self.repo.cancel_transfer(tid)
            except Exception as e:
                errors.append(f"Transfer {tid}: {e}")

        if errors:
            QMessageBox.warning(
                self, "Some Errors",
                "\n".join(errors),
            )

        self.refresh()
