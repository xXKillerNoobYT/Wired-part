"""Settings page — user management, categories, agent config, general."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository


class SettingsPage(QWidget):
    """Settings with sub-tabs: Users, Categories, Agent Config, General."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)

        # Users tab
        self.users_widget = QWidget()
        self._setup_users_tab()
        self.sub_tabs.addTab(self.users_widget, "Users")

        # Categories tab
        self.categories_widget = QWidget()
        self._setup_categories_tab()
        self.sub_tabs.addTab(self.categories_widget, "Categories")

        # General tab
        self.general_widget = QWidget()
        self._setup_general_tab()
        self.sub_tabs.addTab(self.general_widget, "General")

    # ── Users Tab ───────────────────────────────────────────────

    def _setup_users_tab(self):
        layout = QVBoxLayout(self.users_widget)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add User")
        add_btn.clicked.connect(self._add_user)
        edit_btn = QPushButton("Edit User")
        edit_btn.clicked.connect(self._edit_user)
        deactivate_btn = QPushButton("Deactivate")
        deactivate_btn.clicked.connect(self._deactivate_user)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(deactivate_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.users_table = QTableWidget()
        self.users_table.setColumnCount(5)
        self.users_table.setHorizontalHeaderLabels(
            ["ID", "Username", "Display Name", "Role", "Active"]
        )
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.setSelectionMode(QTableWidget.SingleSelection)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.setColumnHidden(0, True)
        layout.addWidget(self.users_table)

    def _refresh_users(self):
        users = self.repo.get_all_users(active_only=False)
        self.users_table.setRowCount(len(users))
        for row, user in enumerate(users):
            self.users_table.setItem(row, 0, QTableWidgetItem(str(user.id)))
            self.users_table.setItem(row, 1, QTableWidgetItem(user.username))
            self.users_table.setItem(
                row, 2, QTableWidgetItem(user.display_name)
            )
            self.users_table.setItem(row, 3, QTableWidgetItem(user.role))
            active_text = "Yes" if user.is_active else "No"
            self.users_table.setItem(row, 4, QTableWidgetItem(active_text))

    def _get_selected_user_id(self):
        row = self.users_table.currentRow()
        if row < 0:
            return None
        return int(self.users_table.item(row, 0).text())

    def _add_user(self):
        from wired_part.ui.dialogs.user_dialog import UserDialog
        dlg = UserDialog(self.repo, parent=self)
        if dlg.exec() == UserDialog.Accepted:
            self._refresh_users()

    def _edit_user(self):
        uid = self._get_selected_user_id()
        if not uid:
            QMessageBox.information(self, "Info", "Select a user to edit.")
            return
        user = self.repo.get_user_by_id(uid)
        from wired_part.ui.dialogs.user_dialog import UserDialog
        dlg = UserDialog(self.repo, user=user, parent=self)
        if dlg.exec() == UserDialog.Accepted:
            self._refresh_users()

    def _deactivate_user(self):
        uid = self._get_selected_user_id()
        if not uid:
            QMessageBox.information(self, "Info", "Select a user first.")
            return
        if uid == self.current_user.id:
            QMessageBox.warning(
                self, "Error", "You cannot deactivate yourself."
            )
            return
        reply = QMessageBox.question(
            self, "Confirm", "Deactivate this user?"
        )
        if reply == QMessageBox.Yes:
            self.repo.deactivate_user(uid)
            self._refresh_users()

    # ── Categories Tab ──────────────────────────────────────────

    def _setup_categories_tab(self):
        layout = QVBoxLayout(self.categories_widget)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add Category")
        add_btn.clicked.connect(self._add_category)
        edit_btn = QPushButton("Edit Category")
        edit_btn.clicked.connect(self._edit_category)
        delete_btn = QPushButton("Delete Category")
        delete_btn.clicked.connect(self._delete_category)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.categories_table = QTableWidget()
        self.categories_table.setColumnCount(5)
        self.categories_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Description", "Parts", "Color"]
        )
        self.categories_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.categories_table.setSelectionMode(QTableWidget.SingleSelection)
        self.categories_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.categories_table.horizontalHeader().setStretchLastSection(True)
        self.categories_table.setColumnHidden(0, True)
        layout.addWidget(self.categories_table)

    def _refresh_categories(self):
        categories = self.repo.get_all_categories()
        self.categories_table.setRowCount(len(categories))
        for row, cat in enumerate(categories):
            self.categories_table.setItem(
                row, 0, QTableWidgetItem(str(cat.id))
            )
            self.categories_table.setItem(
                row, 1, QTableWidgetItem(cat.name)
            )
            self.categories_table.setItem(
                row, 2, QTableWidgetItem(cat.description)
            )
            count = self.repo.get_category_part_count(cat.id)
            self.categories_table.setItem(
                row, 3, QTableWidgetItem(str(count))
            )
            color_item = QTableWidgetItem(cat.color)
            color_item.setBackground(
                __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(
                    cat.color
                )
            )
            self.categories_table.setItem(row, 4, color_item)

    def _get_selected_category_id(self):
        row = self.categories_table.currentRow()
        if row < 0:
            return None
        return int(self.categories_table.item(row, 0).text())

    def _add_category(self):
        from wired_part.ui.dialogs.category_dialog import CategoryDialog
        dlg = CategoryDialog(self.repo, parent=self)
        if dlg.exec() == CategoryDialog.Accepted:
            self._refresh_categories()

    def _edit_category(self):
        cid = self._get_selected_category_id()
        if not cid:
            QMessageBox.information(
                self, "Info", "Select a category to edit."
            )
            return
        cat = self.repo.get_category_by_id(cid)
        from wired_part.ui.dialogs.category_dialog import CategoryDialog
        dlg = CategoryDialog(self.repo, category=cat, parent=self)
        if dlg.exec() == CategoryDialog.Accepted:
            self._refresh_categories()

    def _delete_category(self):
        cid = self._get_selected_category_id()
        if not cid:
            QMessageBox.information(
                self, "Info", "Select a category to delete."
            )
            return
        cat = self.repo.get_category_by_id(cid)
        if cat and cat.name == "Miscellaneous":
            QMessageBox.warning(
                self, "Error",
                "Cannot delete the Miscellaneous category."
            )
            return
        count = self.repo.get_category_part_count(cid)
        msg = f"Delete '{cat.name}'?"
        if count > 0:
            msg += f"\n{count} part(s) will be reassigned to Miscellaneous."
        reply = QMessageBox.question(self, "Confirm", msg)
        if reply == QMessageBox.Yes:
            self.repo.delete_category(cid)
            self._refresh_categories()

    # ── General Tab ─────────────────────────────────────────────

    def _setup_general_tab(self):
        layout = QVBoxLayout(self.general_widget)

        info_group = QGroupBox("Application Info")
        info_layout = QVBoxLayout(info_group)
        from wired_part.utils.constants import APP_VERSION
        from wired_part.config import Config
        info_layout.addWidget(QLabel(f"Version: {APP_VERSION}"))
        info_layout.addWidget(
            QLabel(f"Database: {Config.DATABASE_PATH}")
        )
        info_layout.addWidget(QLabel(f"Theme: {Config.APP_THEME}"))
        info_layout.addWidget(
            QLabel(f"LM Studio: {Config.LM_STUDIO_BASE_URL}")
        )
        layout.addWidget(info_group)

        layout.addStretch()

    # ── Refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._refresh_users()
        self._refresh_categories()
