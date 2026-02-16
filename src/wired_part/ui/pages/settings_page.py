"""Settings page — user management, categories, LLM config, general."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository


class _LLMWorker(QThread):
    """Background thread for LLM server operations (test, fetch models)."""

    finished = Signal(str, list)   # status_text, model_names
    error = Signal(str)            # error_text

    def __init__(self, url: str, key: str, timeout: int,
                 action: str = "test"):
        super().__init__()
        self.url = url
        self.key = key
        self.timeout = timeout
        self.action = action  # "test" or "fetch"

    def run(self):
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=self.url, api_key=self.key,
                timeout=self.timeout,
            )
            models = client.models.list()
            model_names = sorted([m.id for m in models.data])
            count = len(model_names)

            if self.action == "test":
                preview = ", ".join(model_names[:5])
                if count > 5:
                    preview += f", ... ({count} total)"
                self.finished.emit(
                    f"Connected! {count} model(s): {preview}",
                    model_names,
                )
            else:
                self.finished.emit(
                    f"Found {count} model(s).",
                    model_names,
                )
        except Exception as e:
            self.error.emit(str(e))


class SettingsPage(QWidget):
    """Settings with sub-tabs: Users, Categories, LLM, General."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Section selector (QComboBox + QStackedWidget)
        section_row = QHBoxLayout()
        section_row.addWidget(QLabel("Section:"))
        self.section_combo = QComboBox()
        self.section_combo.setMinimumWidth(200)
        section_row.addWidget(self.section_combo)
        section_row.addStretch()
        layout.addLayout(section_row)

        self.section_stack = QStackedWidget()
        layout.addWidget(self.section_stack)

        # ── Section 0: App Settings ────────────────────────────
        self.app_settings_tabs = QTabWidget()

        self.general_widget = QWidget()
        self._setup_general_tab()
        self.app_settings_tabs.addTab(self.general_widget, "General")

        self.labor_widget = QWidget()
        self._setup_labor_tab()
        self.app_settings_tabs.addTab(self.labor_widget, "Labor")

        self.notebook_widget = QWidget()
        self._setup_job_customizations_tab()
        self.app_settings_tabs.addTab(self.notebook_widget, "Job Customizations")

        self.llm_widget = QWidget()
        self._setup_llm_tab()
        self.app_settings_tabs.addTab(self.llm_widget, "LLM Settings")

        self.agent_config_widget = QWidget()
        self._setup_agent_config_tab()
        self.app_settings_tabs.addTab(self.agent_config_widget, "Agent Config")

        self.section_stack.addWidget(self.app_settings_tabs)

        # ── Section 1: Team Settings ───────────────────────────
        self.team_settings_tabs = QTabWidget()

        self.users_widget = QWidget()
        self._setup_users_tab()
        self.team_settings_tabs.addTab(self.users_widget, "Users")

        self.hats_widget = QWidget()
        self._setup_hats_tab()
        self.team_settings_tabs.addTab(self.hats_widget, "Hats & Permissions")

        self.categories_widget = QWidget()
        self._setup_categories_tab()
        self.team_settings_tabs.addTab(self.categories_widget, "Categories")

        self.suppliers_widget = QWidget()
        self._setup_suppliers_tab()
        self.team_settings_tabs.addTab(self.suppliers_widget, "Suppliers")

        self.section_stack.addWidget(self.team_settings_tabs)

        # ── Section 2: My Settings ─────────────────────────────
        self.my_settings_widget = QWidget()
        self._setup_my_settings()
        self.section_stack.addWidget(self.my_settings_widget)

        # Wire section combo
        self.section_combo.currentIndexChanged.connect(
            self._on_section_changed
        )

        # Apply permission visibility — build combo entries
        p = self._perms
        self._section_indices: list[int] = []  # stack index per combo item

        # App Settings — visible if user has ANY app settings perm
        app_perms = {
            "settings_general", "settings_labor", "settings_notebook",
            "settings_llm", "settings_agent",
        }
        if p & app_perms:
            self.section_combo.addItem("App Settings")
            self._section_indices.append(0)
            # Hide individual tabs within App Settings based on perms
            _app_perm_map = {
                0: "settings_general",
                1: "settings_labor",
                2: "settings_notebook",
                3: "settings_llm",
                4: "settings_agent",
            }
            for idx, perm in _app_perm_map.items():
                if idx < self.app_settings_tabs.count():
                    self.app_settings_tabs.setTabVisible(idx, perm in p)

        # Team Settings — visible if user has ANY team settings perm
        team_perms = {
            "settings_users", "settings_hats",
            "settings_categories", "settings_suppliers",
        }
        if p & team_perms:
            self.section_combo.addItem("Team Settings")
            self._section_indices.append(1)
            _team_perm_map = {
                0: "settings_users",
                1: "settings_hats",
                2: "settings_categories",
                3: "settings_suppliers",
            }
            for idx, perm in _team_perm_map.items():
                if idx < self.team_settings_tabs.count():
                    self.team_settings_tabs.setTabVisible(idx, perm in p)

        # My Settings — ALWAYS visible to everyone
        self.section_combo.addItem("My Settings")
        self._section_indices.append(2)

        # Default to the first available section
        if self._section_indices:
            self.section_stack.setCurrentIndex(self._section_indices[0])

        # Backward-compat: expose sub_tabs for tests/permissions that reference it
        # Points to the currently visible inner QTabWidget
        self.sub_tabs = self.app_settings_tabs

        # Auto-fetch models when LLM tab is first opened
        self._llm_models_fetched = False
        self.app_settings_tabs.currentChanged.connect(
            self._on_settings_tab_changed
        )

    def _on_section_changed(self, combo_index: int):
        """Switch the settings section based on combo selection."""
        if combo_index < len(self._section_indices):
            stack_idx = self._section_indices[combo_index]
            self.section_stack.setCurrentIndex(stack_idx)

    def _on_settings_tab_changed(self, index: int):
        """Auto-fetch models when LLM tab is first opened."""
        if self.app_settings_tabs.widget(index) is self.llm_widget:
            if not self._llm_models_fetched:
                self._llm_models_fetched = True
                self._fetch_models()

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
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(
            ["ID", "Username", "Display Name", "Hats", "Role", "Active"]
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
            # Show hats
            hat_names = self.repo.get_user_hat_names(user.id)
            hats_text = ", ".join(hat_names) if hat_names else "(none)"
            self.users_table.setItem(row, 3, QTableWidgetItem(hats_text))
            self.users_table.setItem(row, 4, QTableWidgetItem(user.role))
            active_text = "Yes" if user.is_active else "No"
            self.users_table.setItem(row, 5, QTableWidgetItem(active_text))

    def _get_selected_user_id(self):
        row = self.users_table.currentRow()
        if row < 0:
            return None
        return int(self.users_table.item(row, 0).text())

    def _add_user(self):
        from wired_part.ui.dialogs.user_dialog import UserDialog
        dlg = UserDialog(
            self.repo, current_user=self.current_user, parent=self
        )
        if dlg.exec() == UserDialog.Accepted:
            self._refresh_users()

    def _edit_user(self):
        uid = self._get_selected_user_id()
        if not uid:
            QMessageBox.information(self, "Info", "Select a user to edit.")
            return
        user = self.repo.get_user_by_id(uid)
        from wired_part.ui.dialogs.user_dialog import UserDialog
        dlg = UserDialog(
            self.repo, user=user,
            current_user=self.current_user, parent=self,
        )
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

    # ── Hats & Permissions Tab ────────────────────────────────────

    def _setup_hats_tab(self):
        """Configure hat roles and their permissions."""
        layout = QVBoxLayout(self.hats_widget)

        from wired_part.utils.constants import (
            FULL_ACCESS_HATS,
            LOCKED_HAT_IDS,
            PERMISSION_GROUPS,
            PERMISSION_LABELS,
        )

        layout.addWidget(QLabel(
            "Hats define what each user can see and do in the application.\n"
            "Select a hat on the left to view and edit its permissions.\n"
            "Locked hats (\U0001f512) can be renamed but their permissions "
            "cannot be changed."
        ))

        # ── Hat selector and permission editor side by side ─────
        from PySide6.QtWidgets import QSplitter, QScrollArea

        splitter = QSplitter()

        # Left: Hat list + management buttons
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_header = QLabel("Hats")
        left_header.setStyleSheet("font-weight: bold; font-size: 12px;")
        left_layout.addWidget(left_header)

        self.hats_list = QListWidget()
        self.hats_list.currentRowChanged.connect(self._on_hat_selected)
        left_layout.addWidget(self.hats_list)

        # Hat management buttons
        hat_btn_row = QHBoxLayout()
        hat_btn_row.setSpacing(4)
        add_hat_btn = QPushButton("+ Add")
        add_hat_btn.setToolTip("Create a new custom hat")
        add_hat_btn.clicked.connect(self._add_hat)
        hat_btn_row.addWidget(add_hat_btn)

        rename_hat_btn = QPushButton("Rename")
        rename_hat_btn.setToolTip("Rename the selected hat")
        rename_hat_btn.clicked.connect(self._rename_hat)
        hat_btn_row.addWidget(rename_hat_btn)

        delete_hat_btn = QPushButton("Delete")
        delete_hat_btn.setToolTip("Delete the selected custom hat")
        delete_hat_btn.clicked.connect(self._delete_hat)
        hat_btn_row.addWidget(delete_hat_btn)

        left_layout.addLayout(hat_btn_row)

        splitter.addWidget(left)

        # Right: Permissions
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        self.hat_name_label = QLabel("Select a hat")
        self.hat_name_label.setStyleSheet(
            "font-weight: bold; font-size: 14px;"
        )
        right_layout.addWidget(self.hat_name_label)

        self.hat_info_label = QLabel("")
        self.hat_info_label.setStyleSheet("color: #a6adc8;")
        self.hat_info_label.setWordWrap(True)
        right_layout.addWidget(self.hat_info_label)

        # Scrollable permissions area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        perms_container = QWidget()
        self.perms_layout = QVBoxLayout(perms_container)
        self.perms_layout.setContentsMargins(0, 0, 0, 0)
        self._perm_checkboxes: dict[str, QCheckBox] = {}

        for group_name, keys in PERMISSION_GROUPS.items():
            group_box = QGroupBox(group_name)
            group_layout = QVBoxLayout()
            for key in keys:
                label = PERMISSION_LABELS.get(key, key)
                cb = QCheckBox(label)
                cb.setProperty("perm_key", key)
                self._perm_checkboxes[key] = cb
                group_layout.addWidget(cb)
            group_box.setLayout(group_layout)
            self.perms_layout.addWidget(group_box)

        self.perms_layout.addStretch()
        scroll.setWidget(perms_container)
        right_layout.addWidget(scroll)

        # Save permissions button
        self.save_perms_btn = QPushButton("Save Permissions")
        self.save_perms_btn.setMinimumHeight(34)
        self.save_perms_btn.clicked.connect(self._save_hat_permissions)
        self.save_perms_btn.setEnabled(False)
        right_layout.addWidget(self.save_perms_btn)

        self.hat_perm_status = QLabel("")
        self.hat_perm_status.setWordWrap(True)
        right_layout.addWidget(self.hat_perm_status)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

    def _refresh_hats(self):
        """Reload the hats list."""
        from wired_part.utils.constants import LOCKED_HAT_IDS
        self.hats_list.clear()
        hats = self.repo.get_all_hats()
        for hat in hats:
            label = hat.name
            if hat.id in LOCKED_HAT_IDS:
                label = f"\U0001f512 {hat.name}"
            self.hats_list.addItem(label)
            item = self.hats_list.item(self.hats_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, hat.id)

    def _on_hat_selected(self, row: int):
        """Load permissions for the selected hat."""
        from wired_part.utils.constants import FULL_ACCESS_HATS, LOCKED_HAT_IDS

        if row < 0:
            self.hat_name_label.setText("Select a hat")
            self.hat_info_label.setText("")
            self.save_perms_btn.setEnabled(False)
            return

        item = self.hats_list.item(row)
        hat_id = item.data(Qt.ItemDataRole.UserRole)
        hat = self.repo.get_hat_by_id(hat_id)
        if not hat:
            return

        is_locked = hat_id in LOCKED_HAT_IDS
        is_full = hat.name in FULL_ACCESS_HATS

        lock_icon = "\U0001f512 " if is_locked else ""
        self.hat_name_label.setText(f"{lock_icon}{hat.name}")

        if is_full:
            self.hat_info_label.setText(
                "Full access — all permissions granted automatically.\n"
                "This hat is locked. Permissions cannot be changed."
            )
            self.hat_info_label.setStyleSheet("color: #a6e3a1;")
        elif is_locked:
            self.hat_info_label.setText(
                "This hat is locked — permissions cannot be changed.\n"
                "You can still rename it."
            )
            self.hat_info_label.setStyleSheet("color: #fab387;")
        else:
            self.hat_info_label.setText(
                "Customize which permissions this hat grants."
            )
            self.hat_info_label.setStyleSheet("color: #a6adc8;")

        # Load current permissions
        current_perms = set(hat.permission_list)
        for key, cb in self._perm_checkboxes.items():
            cb.blockSignals(True)
            if is_full:
                cb.setChecked(True)
                cb.setEnabled(False)
            elif is_locked:
                cb.setChecked(key in current_perms)
                cb.setEnabled(False)
            else:
                cb.setChecked(key in current_perms)
                cb.setEnabled(True)
            cb.blockSignals(False)

        self.save_perms_btn.setEnabled(not is_locked and not is_full)

    def _add_hat(self):
        """Create a new custom hat."""
        from wired_part.database.models import Hat
        name, ok = QInputDialog.getText(
            self, "New Hat", "Hat name:"
        )
        if ok and name.strip():
            existing = self.repo.get_hat_by_name(name.strip())
            if existing:
                QMessageBox.warning(
                    self, "Duplicate",
                    f"A hat named '{name.strip()}' already exists.",
                )
                return
            self.repo.create_hat(Hat(
                name=name.strip(), permissions="[]", is_system=0,
            ))
            self._refresh_hats()
            self.hat_perm_status.setText(
                f"Hat '{name.strip()}' created. "
                "Select it to configure permissions."
            )
            self.hat_perm_status.setStyleSheet("color: #a6e3a1;")

    def _rename_hat(self):
        """Rename the selected hat (allowed even for locked hats)."""
        row = self.hats_list.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Info", "Select a hat to rename."
            )
            return
        item = self.hats_list.item(row)
        hat_id = item.data(Qt.ItemDataRole.UserRole)
        hat = self.repo.get_hat_by_id(hat_id)
        if not hat:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Hat", "New name:", text=hat.name,
        )
        if ok and new_name.strip() and new_name.strip() != hat.name:
            # Check for duplicate name
            existing = self.repo.get_hat_by_name(new_name.strip())
            if existing and existing.id != hat_id:
                QMessageBox.warning(
                    self, "Duplicate",
                    f"A hat named '{new_name.strip()}' already exists.",
                )
                return
            self.repo.rename_hat(hat_id, new_name.strip())
            self._refresh_hats()
            self.hat_perm_status.setText(
                f"Renamed to '{new_name.strip()}'."
            )
            self.hat_perm_status.setStyleSheet("color: #a6e3a1;")

    def _delete_hat(self):
        """Delete a custom hat. Locked hats cannot be deleted."""
        from wired_part.utils.constants import LOCKED_HAT_IDS
        row = self.hats_list.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Info", "Select a hat to delete."
            )
            return
        item = self.hats_list.item(row)
        hat_id = item.data(Qt.ItemDataRole.UserRole)

        if hat_id in LOCKED_HAT_IDS:
            QMessageBox.warning(
                self, "Locked Hat",
                "This hat is locked and cannot be deleted.\n"
                "Only custom hats can be deleted.",
            )
            return

        hat = self.repo.get_hat_by_id(hat_id)
        if not hat:
            return

        reply = QMessageBox.question(
            self, "Delete Hat",
            f"Delete '{hat.name}'?\n\n"
            "Users assigned this hat will lose its permissions.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.repo.delete_hat(hat_id)
                self._refresh_hats()
                self.hat_perm_status.setText(
                    f"Hat '{hat.name}' deleted."
                )
                self.hat_perm_status.setStyleSheet("color: #a6e3a1;")
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _save_hat_permissions(self):
        """Save the edited permissions for the selected hat."""
        from wired_part.utils.constants import LOCKED_HAT_IDS
        row = self.hats_list.currentRow()
        if row < 0:
            return

        item = self.hats_list.item(row)
        hat_id = item.data(Qt.ItemDataRole.UserRole)

        if hat_id in LOCKED_HAT_IDS:
            QMessageBox.warning(
                self, "Locked Hat",
                "This hat is locked. Permissions cannot be changed.",
            )
            return

        perms = [
            key for key, cb in self._perm_checkboxes.items()
            if cb.isChecked()
        ]

        try:
            self.repo.update_hat_permissions(hat_id, perms)
            hat = self.repo.get_hat_by_id(hat_id)
            self.hat_perm_status.setText(
                f"Permissions saved for {hat.name if hat else 'hat'} "
                f"({len(perms)} permissions granted)."
            )
            self.hat_perm_status.setStyleSheet("color: #a6e3a1;")
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))

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
            color_item.setBackground(QColor(cat.color))
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

    # ── Suppliers Tab ────────────────────────────────────────────

    def _setup_suppliers_tab(self):
        layout = QVBoxLayout(self.suppliers_widget)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add Supplier")
        add_btn.clicked.connect(self._add_supplier)
        edit_btn = QPushButton("Edit Supplier")
        edit_btn.clicked.connect(self._edit_supplier)
        delete_btn = QPushButton("Delete Supplier")
        delete_btn.clicked.connect(self._delete_supplier)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.suppliers_table = QTableWidget()
        self.suppliers_table.setColumnCount(9)
        self.suppliers_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Contact", "Email", "Phone",
             "Preference", "Supply House", "Hours", "Active"]
        )
        self.suppliers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.suppliers_table.setSelectionMode(QTableWidget.SingleSelection)
        self.suppliers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.suppliers_table.horizontalHeader().setStretchLastSection(True)
        self.suppliers_table.setColumnHidden(0, True)
        layout.addWidget(self.suppliers_table)

    def _refresh_suppliers(self):
        suppliers = self.repo.get_all_suppliers(active_only=False)
        self.suppliers_table.setRowCount(len(suppliers))
        for row, s in enumerate(suppliers):
            self.suppliers_table.setItem(
                row, 0, QTableWidgetItem(str(s.id))
            )
            self.suppliers_table.setItem(
                row, 1, QTableWidgetItem(s.name)
            )
            self.suppliers_table.setItem(
                row, 2, QTableWidgetItem(s.contact_name or "")
            )
            self.suppliers_table.setItem(
                row, 3, QTableWidgetItem(s.email or "")
            )
            self.suppliers_table.setItem(
                row, 4, QTableWidgetItem(s.phone or "")
            )
            self.suppliers_table.setItem(
                row, 5, QTableWidgetItem(str(s.preference_score))
            )
            self.suppliers_table.setItem(
                row, 6,
                QTableWidgetItem("Yes" if s.is_supply_house else ""),
            )
            self.suppliers_table.setItem(
                row, 7,
                QTableWidgetItem(s.operating_hours or ""),
            )
            self.suppliers_table.setItem(
                row, 8,
                QTableWidgetItem("Yes" if s.is_active else "No"),
            )

    def _get_selected_supplier_id(self):
        row = self.suppliers_table.currentRow()
        if row < 0:
            return None
        return int(self.suppliers_table.item(row, 0).text())

    def _add_supplier(self):
        from wired_part.ui.dialogs.supplier_dialog import SupplierDialog
        dlg = SupplierDialog(self.repo, parent=self)
        if dlg.exec() == SupplierDialog.Accepted:
            self._refresh_suppliers()

    def _edit_supplier(self):
        sid = self._get_selected_supplier_id()
        if not sid:
            QMessageBox.information(
                self, "Info", "Select a supplier to edit."
            )
            return
        supplier = self.repo.get_supplier_by_id(sid)
        from wired_part.ui.dialogs.supplier_dialog import SupplierDialog
        dlg = SupplierDialog(self.repo, supplier=supplier, parent=self)
        if dlg.exec() == SupplierDialog.Accepted:
            self._refresh_suppliers()

    def _delete_supplier(self):
        sid = self._get_selected_supplier_id()
        if not sid:
            QMessageBox.information(
                self, "Info", "Select a supplier to delete."
            )
            return
        reply = QMessageBox.question(
            self, "Confirm", "Delete this supplier?"
        )
        if reply == QMessageBox.Yes:
            self.repo.delete_supplier(sid)
            self._refresh_suppliers()

    # ── LLM Settings Tab ─────────────────────────────────────────

    def _setup_llm_tab(self):
        layout = QVBoxLayout(self.llm_widget)

        from wired_part.config import Config

        # Connection settings group
        conn_group = QGroupBox("LLM Connection")
        conn_layout = QFormLayout()

        self.llm_url_input = QLineEdit(Config.LM_STUDIO_BASE_URL)
        self.llm_url_input.setPlaceholderText("http://localhost:1234/v1")
        conn_layout.addRow("Base URL:", self.llm_url_input)

        self.llm_key_input = QLineEdit(Config.LM_STUDIO_API_KEY)
        self.llm_key_input.setPlaceholderText("lm-studio")
        conn_layout.addRow("API Key:", self.llm_key_input)

        # Model picker — dropdown with editable fallback for custom names
        model_row = QHBoxLayout()
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setEditable(True)
        self.llm_model_combo.setMinimumWidth(200)
        self.llm_model_combo.setMaxVisibleItems(20)
        self.llm_model_combo.lineEdit().setPlaceholderText(
            "Click Refresh or select from list"
        )
        self.llm_model_combo.setToolTip(
            "Select a model from the dropdown, or type a custom name.\n"
            "Click Refresh to fetch available models from the server."
        )
        self.llm_model_combo.addItem(Config.LM_STUDIO_MODEL)
        self.llm_model_combo.setCurrentText(Config.LM_STUDIO_MODEL)
        model_row.addWidget(self.llm_model_combo, 1)
        refresh_models_btn = QPushButton("Refresh")
        refresh_models_btn.setToolTip("Fetch available models from server")
        refresh_models_btn.clicked.connect(self._fetch_models)
        model_row.addWidget(refresh_models_btn)
        conn_layout.addRow("Model:", model_row)

        self.llm_timeout_spin = QSpinBox()
        self.llm_timeout_spin.setRange(5, 300)
        self.llm_timeout_spin.setValue(Config.LM_STUDIO_TIMEOUT)
        self.llm_timeout_spin.setSuffix(" seconds")
        conn_layout.addRow("Timeout:", self.llm_timeout_spin)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # Buttons
        btn_layout = QHBoxLayout()

        self.save_llm_btn = QPushButton("Save Settings")
        self.save_llm_btn.setMinimumHeight(34)
        self.save_llm_btn.clicked.connect(self._save_llm_settings)
        btn_layout.addWidget(self.save_llm_btn)

        self.test_conn_btn = QPushButton("Test Connection")
        self.test_conn_btn.setMinimumHeight(34)
        self.test_conn_btn.clicked.connect(self._test_llm_connection)
        btn_layout.addWidget(self.test_conn_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setMinimumHeight(34)
        reset_btn.clicked.connect(self._reset_llm_defaults)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Status
        self.llm_status = QLabel("")
        self.llm_status.setWordWrap(True)
        layout.addWidget(self.llm_status)

        # Help text
        help_group = QGroupBox("Help")
        help_layout = QVBoxLayout()
        help_layout.addWidget(QLabel(
            "Configure the connection to your local LLM server.\n\n"
            "LM Studio: Start LM Studio, load a model, and enable the "
            "server on port 1234.\nThe default URL http://localhost:1234/v1 "
            "should work out of the box.\n\n"
            "Ollama: Use http://localhost:11434/v1 as the Base URL.\n"
            "Set API Key to 'ollama' and Model to your model name "
            "(e.g., 'llama3.2').\n\n"
            "Any OpenAI-compatible server: Set the Base URL to your "
            "server's /v1 endpoint."
        ))
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)

        layout.addStretch()

    def _save_llm_settings(self):
        from wired_part.config import Config

        url = self.llm_url_input.text().strip()
        key = self.llm_key_input.text().strip()
        model = self.llm_model_combo.currentText().strip()
        timeout = self.llm_timeout_spin.value()

        if not url:
            self.llm_status.setText("Base URL cannot be empty.")
            self.llm_status.setStyleSheet("color: #f38ba8;")
            return

        if not model:
            self.llm_status.setText("Model name cannot be empty.")
            self.llm_status.setStyleSheet("color: #f38ba8;")
            return

        Config.update_llm_settings(url, key, model, timeout)
        self.llm_status.setText(
            "Settings saved. Reconnect in the Agent tab to apply."
        )
        self.llm_status.setStyleSheet("color: #a6e3a1;")

    def _set_llm_buttons_enabled(self, enabled: bool):
        """Enable/disable LLM action buttons during async operations."""
        self.save_llm_btn.setEnabled(enabled)
        self.test_conn_btn.setEnabled(enabled)

    def _test_llm_connection(self):
        """Test connection in background thread — doesn't freeze UI."""
        url = self.llm_url_input.text().strip()
        if not url:
            self.llm_status.setText("Enter a Base URL first.")
            self.llm_status.setStyleSheet("color: #f38ba8;")
            return

        key = self.llm_key_input.text().strip() or "lm-studio"
        timeout = self.llm_timeout_spin.value()

        self.llm_status.setText("Testing connection...")
        self.llm_status.setStyleSheet("color: #fab387;")
        self._set_llm_buttons_enabled(False)

        self._llm_worker = _LLMWorker(url, key, timeout, action="test")
        self._llm_worker.finished.connect(self._on_test_finished)
        self._llm_worker.error.connect(self._on_llm_error)
        self._llm_worker.start()

    def _on_test_finished(self, status: str, model_names: list):
        self._set_llm_buttons_enabled(True)
        self.llm_status.setText(status)
        self.llm_status.setStyleSheet("color: #a6e3a1;")
        # Also populate the model picker with discovered models
        if model_names:
            self._populate_model_combo(model_names)

    def _on_llm_error(self, error: str):
        self._set_llm_buttons_enabled(True)
        self.llm_status.setText(f"Connection failed: {error}")
        self.llm_status.setStyleSheet("color: #f38ba8;")

    def _fetch_models(self):
        """Fetch available models in background thread."""
        url = self.llm_url_input.text().strip()
        if not url:
            self.llm_status.setText("Enter a Base URL first.")
            self.llm_status.setStyleSheet("color: #f38ba8;")
            return

        key = self.llm_key_input.text().strip() or "lm-studio"
        timeout = self.llm_timeout_spin.value()

        self.llm_status.setText("Fetching models...")
        self.llm_status.setStyleSheet("color: #fab387;")
        self._set_llm_buttons_enabled(False)

        self._llm_worker = _LLMWorker(url, key, timeout, action="fetch")
        self._llm_worker.finished.connect(self._on_fetch_finished)
        self._llm_worker.error.connect(self._on_llm_error)
        self._llm_worker.start()

    def _on_fetch_finished(self, status: str, model_names: list):
        self._set_llm_buttons_enabled(True)
        if not model_names:
            self.llm_status.setText("No models found on server.")
            self.llm_status.setStyleSheet("color: #f38ba8;")
            return
        self._populate_model_combo(model_names)
        self.llm_status.setText(
            f"Found {len(model_names)} model(s). Select from dropdown."
        )
        self.llm_status.setStyleSheet("color: #a6e3a1;")

    def _populate_model_combo(self, model_names: list):
        """Fill the model combo box, preserving the current selection."""
        current = self.llm_model_combo.currentText()
        self.llm_model_combo.blockSignals(True)
        self.llm_model_combo.clear()
        for name in model_names:
            self.llm_model_combo.addItem(name)

        idx = self.llm_model_combo.findText(current)
        if idx >= 0:
            self.llm_model_combo.setCurrentIndex(idx)
        elif current:
            # Re-add the user's saved/custom model so it isn't lost
            self.llm_model_combo.insertItem(0, current)
            self.llm_model_combo.setCurrentIndex(0)
        elif len(model_names) == 1:
            self.llm_model_combo.setCurrentIndex(0)
        self.llm_model_combo.blockSignals(False)

    def _reset_llm_defaults(self):
        self.llm_url_input.setText("http://localhost:1234/v1")
        self.llm_key_input.setText("lm-studio")
        self.llm_model_combo.clear()
        self.llm_model_combo.addItem("local-model")
        self.llm_model_combo.setCurrentText("local-model")
        self.llm_timeout_spin.setValue(60)
        self.llm_status.setText("Defaults restored. Click Save to apply.")
        self.llm_status.setStyleSheet("color: #fab387;")

    # ── Agent Config Tab ─────────────────────────────────────────

    def _setup_agent_config_tab(self):
        layout = QVBoxLayout(self.agent_config_widget)

        from wired_part.config import Config

        intervals_group = QGroupBox("Background Agent Intervals")
        intervals_layout = QFormLayout()

        self.audit_interval_spin = QSpinBox()
        self.audit_interval_spin.setRange(1, 1440)
        self.audit_interval_spin.setValue(Config.AUDIT_AGENT_INTERVAL)
        self.audit_interval_spin.setSuffix(" minutes")
        self.audit_interval_spin.setToolTip(
            "How often the Audit Agent scans for inconsistencies"
        )
        intervals_layout.addRow(
            "Audit Agent:", self.audit_interval_spin
        )

        self.admin_interval_spin = QSpinBox()
        self.admin_interval_spin.setRange(1, 1440)
        self.admin_interval_spin.setValue(Config.ADMIN_AGENT_INTERVAL)
        self.admin_interval_spin.setSuffix(" minutes")
        self.admin_interval_spin.setToolTip(
            "How often the Admin Helper summarizes activity"
        )
        intervals_layout.addRow(
            "Admin Helper:", self.admin_interval_spin
        )

        self.reminder_interval_spin = QSpinBox()
        self.reminder_interval_spin.setRange(1, 1440)
        self.reminder_interval_spin.setValue(Config.REMINDER_AGENT_INTERVAL)
        self.reminder_interval_spin.setSuffix(" minutes")
        self.reminder_interval_spin.setToolTip(
            "How often the Reminder Agent checks for pending items"
        )
        intervals_layout.addRow(
            "Reminder Agent:", self.reminder_interval_spin
        )

        intervals_group.setLayout(intervals_layout)
        layout.addWidget(intervals_group)

        # Save button
        save_btn = QPushButton("Save Agent Config")
        save_btn.setMinimumHeight(34)
        save_btn.clicked.connect(self._save_agent_config)
        layout.addWidget(save_btn)

        self.agent_config_status = QLabel("")
        self.agent_config_status.setWordWrap(True)
        layout.addWidget(self.agent_config_status)

        # Description
        desc_group = QGroupBox("About Background Agents")
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel(
            "Background agents run periodically to assist with inventory "
            "management.\n\n"
            "Audit Agent: Scans for low stock, missing data, and "
            "inconsistencies. Creates warning notifications.\n\n"
            "Admin Helper: Generates daily activity summaries — new parts, "
            "completed jobs, pending transfers.\n\n"
            "Reminder Agent: Checks for stale transfers (>24h pending), "
            "jobs on hold for 7+ days, and inactive trucks.\n\n"
            "Agents require a running LLM server (configured in LLM Settings). "
            "Start/Stop agents from the Agent tab."
        ))
        desc_group.setLayout(desc_layout)
        layout.addWidget(desc_group)

        layout.addStretch()

    def _save_agent_config(self):
        from wired_part.config import Config
        audit = self.audit_interval_spin.value()
        admin = self.admin_interval_spin.value()
        reminder = self.reminder_interval_spin.value()
        Config.update_agent_intervals(audit, admin, reminder)
        self.agent_config_status.setText(
            "Agent intervals saved. Restart background agents to apply."
        )
        self.agent_config_status.setStyleSheet("color: #a6e3a1;")

    # ── Labor Tab ──────────────────────────────────────────────

    def _setup_labor_tab(self):
        layout = QVBoxLayout(self.labor_widget)

        from wired_part.config import Config

        settings_group = QGroupBox("Labor Tracking Settings")
        form = QFormLayout()

        self.geofence_spin = QDoubleSpinBox()
        self.geofence_spin.setRange(0.01, 50.0)
        self.geofence_spin.setDecimals(2)
        self.geofence_spin.setValue(Config.GEOFENCE_RADIUS)
        self.geofence_spin.setSuffix(" miles")
        self.geofence_spin.setToolTip(
            "Maximum distance from job site for clock-in/out "
            "before a warning is shown"
        )
        form.addRow("Geofence Radius:", self.geofence_spin)

        self.overtime_spin = QDoubleSpinBox()
        self.overtime_spin.setRange(1.0, 24.0)
        self.overtime_spin.setDecimals(1)
        self.overtime_spin.setValue(Config.OVERTIME_THRESHOLD)
        self.overtime_spin.setSuffix(" hours")
        self.overtime_spin.setToolTip(
            "Entries exceeding this many hours are flagged as overtime"
        )
        form.addRow("Overtime Threshold:", self.overtime_spin)

        # Photos directory with browse button
        photos_row = QHBoxLayout()
        self.photos_dir_input = QLineEdit(Config.PHOTOS_DIRECTORY)
        self.photos_dir_input.setPlaceholderText("Path to photos directory")
        self.photos_dir_input.setToolTip(
            "Directory where labor and notebook photos are stored"
        )
        photos_row.addWidget(self.photos_dir_input, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_photos_dir)
        photos_row.addWidget(browse_btn)

        form.addRow("Photos Directory:", photos_row)

        settings_group.setLayout(form)
        layout.addWidget(settings_group)

        # Save button
        save_btn = QPushButton("Save Labor Settings")
        save_btn.setMinimumHeight(34)
        save_btn.clicked.connect(self._save_labor_config)
        layout.addWidget(save_btn)

        self.labor_status = QLabel("")
        self.labor_status.setWordWrap(True)
        layout.addWidget(self.labor_status)

        # Description
        desc_group = QGroupBox("About Labor Tracking")
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel(
            "Configure defaults for the labor tracking system.\n\n"
            "Geofence Radius: When GPS coordinates are provided during "
            "clock-in/out, the system checks if the worker is within "
            "this radius of the job site. A warning is shown if outside "
            "the radius, but the action is still allowed.\n\n"
            "Overtime Threshold: Entries with hours exceeding this value "
            "are highlighted and flagged as overtime in reports.\n\n"
            "Photos Directory: Where photos attached to labor entries "
            "and notebook pages are stored on disk."
        ))
        desc_group.setLayout(desc_layout)
        layout.addWidget(desc_group)

        # ── Billing Settings ─────────────────────────────────
        billing_group = QGroupBox("Default Billing Cycle")
        billing_form = QFormLayout()

        self.billing_cycle_combo = QComboBox()
        self.billing_cycle_combo.addItem("Weekly", "weekly")
        self.billing_cycle_combo.addItem("Biweekly", "biweekly")
        self.billing_cycle_combo.addItem("Monthly", "monthly")
        self.billing_cycle_combo.addItem("Quarterly", "quarterly")
        idx = self.billing_cycle_combo.findData(Config.DEFAULT_BILLING_CYCLE)
        if idx >= 0:
            self.billing_cycle_combo.setCurrentIndex(idx)
        self.billing_cycle_combo.currentIndexChanged.connect(
            self._on_billing_cycle_changed
        )
        billing_form.addRow("Cycle Type:", self.billing_cycle_combo)

        # Day-of-week combo (shown for weekly/biweekly)
        self.billing_day_of_week = QComboBox()
        for i, day_name in enumerate(
            ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"], start=1
        ):
            self.billing_day_of_week.addItem(day_name, i)
        billing_form.addRow("Day of Week:", self.billing_day_of_week)

        # Day-of-month spin (shown for monthly/quarterly)
        self.billing_day_spin = QSpinBox()
        self.billing_day_spin.setRange(1, 31)
        self.billing_day_spin.setToolTip("Day of month for billing")
        billing_form.addRow("Billing Day:", self.billing_day_spin)

        # Set initial values and visibility
        self._set_billing_day_value(
            Config.DEFAULT_BILLING_CYCLE, Config.DEFAULT_BILLING_DAY,
        )
        self._on_billing_cycle_changed()

        billing_group.setLayout(billing_form)
        layout.addWidget(billing_group)

        billing_save_btn = QPushButton("Save Billing Settings")
        billing_save_btn.setMinimumHeight(34)
        billing_save_btn.clicked.connect(self._save_billing_config)
        layout.addWidget(billing_save_btn)

        self.billing_status = QLabel("")
        self.billing_status.setWordWrap(True)
        layout.addWidget(self.billing_status)

        # ── Timesheet Report Cycle ──────────────────────────────
        ts_group = QGroupBox("Timesheet Report Cycle")
        ts_form = QFormLayout()

        self.ts_cycle_combo = QComboBox()
        self.ts_cycle_combo.addItem("Weekly", "weekly")
        self.ts_cycle_combo.addItem("Biweekly", "biweekly")
        self.ts_cycle_combo.addItem("Monthly", "monthly")
        self.ts_cycle_combo.addItem("Quarterly", "quarterly")
        ts_idx = self.ts_cycle_combo.findData(Config.TIMESHEET_CYCLE)
        if ts_idx >= 0:
            self.ts_cycle_combo.setCurrentIndex(ts_idx)
        self.ts_cycle_combo.currentIndexChanged.connect(
            self._on_ts_cycle_changed
        )
        ts_form.addRow("Cycle Type:", self.ts_cycle_combo)

        # Day-of-week combo (shown for weekly/biweekly)
        self.ts_day_of_week = QComboBox()
        for i, day_name in enumerate(
            ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"], start=1
        ):
            self.ts_day_of_week.addItem(day_name, i)
        ts_form.addRow("Day of Week:", self.ts_day_of_week)

        # Day-of-month spin (shown for monthly/quarterly)
        self.ts_day_spin = QSpinBox()
        self.ts_day_spin.setRange(1, 31)
        self.ts_day_spin.setToolTip("Day of month for timesheet report")
        ts_form.addRow("Report Day:", self.ts_day_spin)

        # Set initial values and visibility
        self._set_ts_day_value(Config.TIMESHEET_CYCLE, Config.TIMESHEET_DAY)
        self._on_ts_cycle_changed()

        ts_group.setLayout(ts_form)
        layout.addWidget(ts_group)

        ts_save_btn = QPushButton("Save Timesheet Settings")
        ts_save_btn.setMinimumHeight(34)
        ts_save_btn.clicked.connect(self._save_timesheet_config)
        layout.addWidget(ts_save_btn)

        self.ts_status = QLabel("")
        self.ts_status.setWordWrap(True)
        layout.addWidget(self.ts_status)

        layout.addStretch()

    def _browse_photos_dir(self):
        """Open a directory picker for the photos directory."""
        current = self.photos_dir_input.text().strip()
        directory = QFileDialog.getExistingDirectory(
            self, "Select Photos Directory", current
        )
        if directory:
            self.photos_dir_input.setText(directory)

    def _save_labor_config(self):
        from wired_part.config import Config

        radius = self.geofence_spin.value()
        photos_dir = self.photos_dir_input.text().strip()
        overtime = self.overtime_spin.value()

        if not photos_dir:
            self.labor_status.setText("Photos directory cannot be empty.")
            self.labor_status.setStyleSheet("color: #f38ba8;")
            return

        Config.update_labor_settings(radius, photos_dir, overtime)
        self.labor_status.setText("Labor settings saved successfully.")
        self.labor_status.setStyleSheet("color: #a6e3a1;")

    def _on_billing_cycle_changed(self):
        """Toggle between day-of-week and day-of-month for billing."""
        cycle = self.billing_cycle_combo.currentData()
        is_weekly = cycle in ("weekly", "biweekly")
        self.billing_day_of_week.setVisible(is_weekly)
        self.billing_day_spin.setVisible(not is_weekly)

    def _set_billing_day_value(self, cycle: str, day: int):
        """Set the correct widget value based on cycle type."""
        if cycle in ("weekly", "biweekly"):
            idx = self.billing_day_of_week.findData(day)
            if idx >= 0:
                self.billing_day_of_week.setCurrentIndex(idx)
        else:
            self.billing_day_spin.setValue(day)

    def _on_ts_cycle_changed(self):
        """Toggle between day-of-week and day-of-month for timesheets."""
        cycle = self.ts_cycle_combo.currentData()
        is_weekly = cycle in ("weekly", "biweekly")
        self.ts_day_of_week.setVisible(is_weekly)
        self.ts_day_spin.setVisible(not is_weekly)

    def _set_ts_day_value(self, cycle: str, day: int):
        """Set the correct widget value based on cycle type."""
        if cycle in ("weekly", "biweekly"):
            idx = self.ts_day_of_week.findData(day)
            if idx >= 0:
                self.ts_day_of_week.setCurrentIndex(idx)
        else:
            self.ts_day_spin.setValue(day)

    def _save_billing_config(self):
        from wired_part.config import Config

        cycle = self.billing_cycle_combo.currentData()
        if cycle in ("weekly", "biweekly"):
            day = self.billing_day_of_week.currentData()
        else:
            day = self.billing_day_spin.value()
        Config.update_billing_settings(cycle, day)
        self.billing_status.setText("Billing settings saved successfully.")
        self.billing_status.setStyleSheet("color: #a6e3a1;")

    def _save_timesheet_config(self):
        from wired_part.config import Config

        cycle = self.ts_cycle_combo.currentData()
        if cycle in ("weekly", "biweekly"):
            day = self.ts_day_of_week.currentData()
        else:
            day = self.ts_day_spin.value()
        Config.update_timesheet_settings(cycle, day)
        self.ts_status.setText("Timesheet settings saved successfully.")
        self.ts_status.setStyleSheet("color: #a6e3a1;")

    # ── Notebook Tab ─────────────────────────────────────────────

    def _setup_job_customizations_tab(self):
        """Configure job defaults: BRO categories + notebook sections."""
        layout = QVBoxLayout(self.notebook_widget)

        from wired_part.config import Config

        # ── BRO Categories ────────────────────────────────────
        bro_group = QGroupBox("BRO (Bill Out Rate) Categories")
        bro_layout = QVBoxLayout()
        bro_layout.addWidget(QLabel(
            "Customize the BRO categories available on jobs.\n"
            "These are bookkeeper classification codes (e.g. C, T&M, SERVICE).\n"
            "Categories in use by active/on-hold jobs cannot be removed."
        ))

        self.bro_list = QListWidget()
        self.bro_list.setMaximumHeight(140)
        for cat in Config.get_bro_categories():
            self.bro_list.addItem(cat)
        bro_layout.addWidget(self.bro_list)

        bro_btns = QHBoxLayout()
        bro_add_btn = QPushButton("Add")
        bro_add_btn.clicked.connect(self._bro_add)
        bro_btns.addWidget(bro_add_btn)

        bro_edit_btn = QPushButton("Edit")
        bro_edit_btn.clicked.connect(self._bro_edit)
        bro_btns.addWidget(bro_edit_btn)

        bro_remove_btn = QPushButton("Remove")
        bro_remove_btn.clicked.connect(self._bro_remove)
        bro_btns.addWidget(bro_remove_btn)

        bro_save_btn = QPushButton("Save BRO List")
        bro_save_btn.setMinimumHeight(30)
        bro_save_btn.clicked.connect(self._save_bro_categories)
        bro_btns.addWidget(bro_save_btn)

        bro_layout.addLayout(bro_btns)

        self.bro_status = QLabel("")
        bro_layout.addWidget(self.bro_status)

        bro_group.setLayout(bro_layout)
        layout.addWidget(bro_group)

        # ── Notebook Sections Template ──────────────────────────
        template_group = QGroupBox("Default Sections for New Job Notebooks")
        tpl_layout = QVBoxLayout()

        tpl_layout.addWidget(QLabel(
            "Configure which sections are automatically created when\n"
            "a new job notebook is created. The 'Daily Logs' section\n"
            "is always locked and cannot be renamed or deleted."
        ))

        self.sections_list = QListWidget()
        self.sections_list.setMinimumHeight(140)
        self.sections_list.setToolTip(
            "Drag to reorder, or use Move Up/Down buttons"
        )
        tpl_layout.addWidget(self.sections_list)

        # Load current template
        for section in Config.get_notebook_sections():
            item = QListWidgetItem(section)
            self.sections_list.addItem(item)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        add_btn = QPushButton("+ Add Section")
        add_btn.setToolTip("Add a new section to the template")
        add_btn.clicked.connect(self._on_add_template_section)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setToolTip("Remove selected section from the template")
        remove_btn.clicked.connect(self._on_remove_template_section)
        btn_row.addWidget(remove_btn)

        up_btn = QPushButton("Move Up")
        up_btn.setToolTip("Move selected section up")
        up_btn.clicked.connect(self._on_move_section_up)
        btn_row.addWidget(up_btn)

        down_btn = QPushButton("Move Down")
        down_btn.setToolTip("Move selected section down")
        down_btn.clicked.connect(self._on_move_section_down)
        btn_row.addWidget(down_btn)

        btn_row.addStretch()
        tpl_layout.addLayout(btn_row)

        template_group.setLayout(tpl_layout)
        layout.addWidget(template_group)

        # Save / Reset
        action_row = QHBoxLayout()
        save_tpl_btn = QPushButton("Save Template")
        save_tpl_btn.setMinimumHeight(34)
        save_tpl_btn.clicked.connect(self._save_notebook_template)
        action_row.addWidget(save_tpl_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setToolTip("Restore the default sections template")
        reset_btn.clicked.connect(self._reset_notebook_template)
        action_row.addWidget(reset_btn)
        layout.addLayout(action_row)

        self.notebook_status = QLabel("")
        self.notebook_status.setWordWrap(True)
        layout.addWidget(self.notebook_status)

        layout.addStretch()

    def _on_add_template_section(self):
        """Add a new section to the notebook template."""
        name, ok = QInputDialog.getText(
            self, "New Section", "Section name:"
        )
        if ok and name.strip():
            self.sections_list.addItem(name.strip())

    def _on_remove_template_section(self):
        """Remove the selected section from the template."""
        row = self.sections_list.currentRow()
        if row < 0:
            return
        item = self.sections_list.item(row)
        if item.text() == "Daily Logs":
            QMessageBox.information(
                self, "Locked Section",
                "'Daily Logs' is locked and cannot be removed.",
            )
            return
        self.sections_list.takeItem(row)

    def _on_move_section_up(self):
        """Move the selected section up in the list."""
        row = self.sections_list.currentRow()
        if row > 0:
            item = self.sections_list.takeItem(row)
            self.sections_list.insertItem(row - 1, item)
            self.sections_list.setCurrentRow(row - 1)

    def _on_move_section_down(self):
        """Move the selected section down in the list."""
        row = self.sections_list.currentRow()
        if row < self.sections_list.count() - 1:
            item = self.sections_list.takeItem(row)
            self.sections_list.insertItem(row + 1, item)
            self.sections_list.setCurrentRow(row + 1)

    def _save_notebook_template(self):
        """Save the current section template to settings."""
        from wired_part.config import Config

        sections = []
        for i in range(self.sections_list.count()):
            sections.append(self.sections_list.item(i).text())

        if not sections:
            self.notebook_status.setText(
                "Template must have at least one section."
            )
            self.notebook_status.setStyleSheet("color: #f38ba8;")
            return

        # Ensure Daily Logs is always present
        if "Daily Logs" not in sections:
            sections.insert(0, "Daily Logs")
            self.sections_list.clear()
            for s in sections:
                self.sections_list.addItem(s)

        Config.update_notebook_template(sections)
        self.notebook_status.setText(
            f"Template saved with {len(sections)} sections. "
            "New jobs will use this template."
        )
        self.notebook_status.setStyleSheet("color: #a6e3a1;")

    def _reset_notebook_template(self):
        """Reset the template to default sections."""
        from wired_part.config import Config
        from wired_part.utils.constants import DEFAULT_NOTEBOOK_SECTIONS

        Config.update_notebook_template(list(DEFAULT_NOTEBOOK_SECTIONS))
        self.sections_list.clear()
        for s in DEFAULT_NOTEBOOK_SECTIONS:
            self.sections_list.addItem(s)
        self.notebook_status.setText("Template reset to defaults.")
        self.notebook_status.setStyleSheet("color: #a6e3a1;")

    # ── General Tab ─────────────────────────────────────────────

    def _setup_general_tab(self):
        layout = QVBoxLayout(self.general_widget)

        from wired_part.utils.constants import APP_VERSION
        from wired_part.config import Config

        info_group = QGroupBox("Application Info")
        info_layout = QFormLayout()
        info_layout.addRow("Version:", QLabel(APP_VERSION))
        info_layout.addRow("Database:", QLabel(str(Config.DATABASE_PATH)))

        # Theme selector
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Retro", "retro")
        idx = self.theme_combo.findData(Config.APP_THEME)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        info_layout.addRow("Theme:", self.theme_combo)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Theme save button
        theme_btn = QPushButton("Apply Theme (restart required)")
        theme_btn.clicked.connect(self._save_theme)
        layout.addWidget(theme_btn)

        self.general_status = QLabel("")
        layout.addWidget(self.general_status)

        # ── Order Settings ─────────────────────────────────────
        order_group = QGroupBox("Order & Return Settings")
        order_form = QFormLayout()

        self.po_prefix_input = QLineEdit(Config.ORDER_NUMBER_PREFIX)
        self.po_prefix_input.setMaxLength(10)
        self.po_prefix_input.setToolTip(
            "Prefix for purchase order numbers (e.g. PO → PO-2026-001)"
        )
        order_form.addRow("PO Number Prefix:", self.po_prefix_input)

        self.ra_prefix_input = QLineEdit(Config.RA_NUMBER_PREFIX)
        self.ra_prefix_input.setMaxLength(10)
        self.ra_prefix_input.setToolTip(
            "Prefix for return authorization numbers (e.g. RA → RA-2026-001)"
        )
        order_form.addRow("RA Number Prefix:", self.ra_prefix_input)

        self.auto_close_check = QCheckBox("Auto-close orders when fully received")
        self.auto_close_check.setChecked(bool(Config.AUTO_CLOSE_RECEIVED_ORDERS))
        self.auto_close_check.setToolTip(
            "When enabled, orders are automatically set to 'closed' "
            "when all items are received"
        )
        order_form.addRow("", self.auto_close_check)

        order_group.setLayout(order_form)
        layout.addWidget(order_group)

        order_save_btn = QPushButton("Save Order Settings")
        order_save_btn.setMinimumHeight(34)
        order_save_btn.clicked.connect(self._save_order_config)
        layout.addWidget(order_save_btn)

        self.order_status = QLabel("")
        self.order_status.setWordWrap(True)
        layout.addWidget(self.order_status)

        layout.addStretch()

    def _bro_add(self):
        text, ok = QInputDialog.getText(
            self, "Add BRO Category", "Category code:"
        )
        if ok and text.strip():
            val = text.strip().upper()
            # Check for duplicate
            existing = [
                self.bro_list.item(i).text()
                for i in range(self.bro_list.count())
            ]
            if val in existing:
                self.bro_status.setText(f"'{val}' already exists.")
                self.bro_status.setStyleSheet("color: #f38ba8;")
                return
            self.bro_list.addItem(val)
            self.bro_status.setText(f"Added '{val}'. Click Save to persist.")
            self.bro_status.setStyleSheet("color: #fab387;")

    def _bro_edit(self):
        item = self.bro_list.currentItem()
        if not item:
            return
        text, ok = QInputDialog.getText(
            self, "Edit BRO Category", "Category code:", text=item.text()
        )
        if ok and text.strip():
            item.setText(text.strip().upper())
            self.bro_status.setText("Updated. Click Save to persist.")
            self.bro_status.setStyleSheet("color: #fab387;")

    def _bro_remove(self):
        row = self.bro_list.currentRow()
        if row < 0:
            return
        cat_name = self.bro_list.item(row).text()

        # Protect: don't allow removal if active/on-hold jobs use this BRO
        active_jobs = [
            j for j in self.repo.get_all_jobs()
            if j.bill_out_rate == cat_name
            and j.status in ("active", "on_hold")
        ]
        if active_jobs:
            job_list = ", ".join(j.job_number for j in active_jobs[:5])
            extra = (
                f" and {len(active_jobs) - 5} more"
                if len(active_jobs) > 5 else ""
            )
            QMessageBox.warning(
                self, "Cannot Remove BRO",
                f"'{cat_name}' is used by active/on-hold jobs:\n"
                f"{job_list}{extra}\n\n"
                "Complete or change the BRO on those jobs first.",
            )
            return

        self.bro_list.takeItem(row)
        self.bro_status.setText(
            f"Removed '{cat_name}'. Click Save to persist."
        )
        self.bro_status.setStyleSheet("color: #fab387;")

    def _save_bro_categories(self):
        from wired_part.config import Config
        categories = [
            self.bro_list.item(i).text()
            for i in range(self.bro_list.count())
        ]
        if not categories:
            self.bro_status.setText("At least one BRO category is required.")
            self.bro_status.setStyleSheet("color: #f38ba8;")
            return
        Config.update_bro_categories(categories)
        self.bro_status.setText(
            f"Saved {len(categories)} BRO categories."
        )
        self.bro_status.setStyleSheet("color: #a6e3a1;")

    def _save_theme(self):
        from wired_part.config import Config
        theme = self.theme_combo.currentData()
        Config.update_theme(theme)
        self.general_status.setText(
            f"Theme set to '{theme}'. Restart the app to apply."
        )
        self.general_status.setStyleSheet("color: #a6e3a1;")

    def _save_order_config(self):
        from wired_part.config import Config

        po_prefix = self.po_prefix_input.text().strip()
        ra_prefix = self.ra_prefix_input.text().strip()
        auto_close = self.auto_close_check.isChecked()

        if not po_prefix:
            self.order_status.setText("PO prefix cannot be empty.")
            self.order_status.setStyleSheet("color: #f38ba8;")
            return
        if not ra_prefix:
            self.order_status.setText("RA prefix cannot be empty.")
            self.order_status.setStyleSheet("color: #f38ba8;")
            return

        Config.update_order_settings(po_prefix, ra_prefix, auto_close)
        self.order_status.setText("Order settings saved successfully.")
        self.order_status.setStyleSheet("color: #a6e3a1;")

    # ── My Settings ──────────────────────────────────────────────

    def _setup_my_settings(self):
        """Per-user preferences — visible to every user."""
        from wired_part.config import Config
        from pathlib import Path

        layout = QVBoxLayout(self.my_settings_widget)

        # Theme
        theme_group = QGroupBox("Appearance")
        theme_form = QFormLayout()

        self.my_theme_combo = QComboBox()
        self.my_theme_combo.addItem("Dark", "dark")
        self.my_theme_combo.addItem("Light", "light")
        self.my_theme_combo.addItem("Retro", "retro")

        # Load current user setting
        settings = self.repo.get_or_create_user_settings(
            self.current_user.id
        )
        idx = self.my_theme_combo.findData(settings.theme or "dark")
        if idx >= 0:
            self.my_theme_combo.setCurrentIndex(idx)

        theme_form.addRow("Theme:", self.my_theme_combo)

        # Font size
        self.my_font_spin = QSpinBox()
        self.my_font_spin.setRange(8, 16)
        self.my_font_spin.setValue(settings.font_size or 10)
        theme_form.addRow("Font Size:", self.my_font_spin)

        # Compact mode
        self.my_compact_check = QCheckBox("Compact mode (smaller spacing)")
        self.my_compact_check.setChecked(bool(settings.compact_mode))
        theme_form.addRow("", self.my_compact_check)

        theme_group.setLayout(theme_form)
        layout.addWidget(theme_group)

        # Defaults
        defaults_group = QGroupBox("Defaults")
        defaults_form = QFormLayout()

        self.my_truck_filter_combo = QComboBox()
        self.my_truck_filter_combo.addItem("My Truck", "mine")
        self.my_truck_filter_combo.addItem("All Trucks", "all")
        tf_idx = self.my_truck_filter_combo.findData(
            settings.default_truck_filter or "mine"
        )
        if tf_idx >= 0:
            self.my_truck_filter_combo.setCurrentIndex(tf_idx)
        defaults_form.addRow("Default Truck Filter:", self.my_truck_filter_combo)

        self.my_date_range_combo = QComboBox()
        for label in (
            "This Period", "Last 7 Days", "Last 30 Days",
            "This Month", "All Time",
        ):
            self.my_date_range_combo.addItem(label)
        dr_idx = self.my_date_range_combo.findText(
            settings.preferred_date_range or "This Period"
        )
        if dr_idx >= 0:
            self.my_date_range_combo.setCurrentIndex(dr_idx)
        defaults_form.addRow("Preferred Date Range:", self.my_date_range_combo)

        defaults_group.setLayout(defaults_form)
        layout.addWidget(defaults_group)

        # Account
        account_group = QGroupBox("Account")
        account_form = QFormLayout()

        self.my_display_name = QLineEdit(
            self.current_user.display_name or ""
        )
        account_form.addRow("Display Name:", self.my_display_name)

        self.my_pin_current = QLineEdit()
        self.my_pin_current.setEchoMode(QLineEdit.EchoMode.Password)
        self.my_pin_current.setPlaceholderText("Current PIN")
        account_form.addRow("Current PIN:", self.my_pin_current)

        self.my_pin_new = QLineEdit()
        self.my_pin_new.setEchoMode(QLineEdit.EchoMode.Password)
        self.my_pin_new.setPlaceholderText("New PIN (leave blank to keep)")
        account_form.addRow("New PIN:", self.my_pin_new)

        self.my_pin_confirm = QLineEdit()
        self.my_pin_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.my_pin_confirm.setPlaceholderText("Confirm new PIN")
        account_form.addRow("Confirm PIN:", self.my_pin_confirm)

        account_group.setLayout(account_form)
        layout.addWidget(account_group)

        # Save button
        save_btn = QPushButton("Save My Settings")
        save_btn.setMinimumHeight(34)
        save_btn.clicked.connect(self._save_my_settings)
        layout.addWidget(save_btn)

        self.my_settings_status = QLabel("")
        self.my_settings_status.setObjectName("SettingsStatusLabel")
        layout.addWidget(self.my_settings_status)

        layout.addStretch()

    def _save_my_settings(self):
        """Persist the user's personal preferences."""
        from wired_part.config import Config

        theme = self.my_theme_combo.currentData()
        font_size = self.my_font_spin.value()
        compact = 1 if self.my_compact_check.isChecked() else 0
        truck_filter = self.my_truck_filter_combo.currentData()
        date_range = self.my_date_range_combo.currentText()
        display_name = self.my_display_name.text().strip()

        # Validate display name
        if not display_name:
            self.my_settings_status.setText("Display name cannot be empty.")
            return

        # Handle PIN change
        new_pin = self.my_pin_new.text().strip()
        if new_pin:
            current = self.my_pin_current.text().strip()
            if not current:
                self.my_settings_status.setText(
                    "Enter current PIN to change it."
                )
                return
            if Repository.hash_pin(current) != self.current_user.pin_hash:
                self.my_settings_status.setText("Current PIN is incorrect.")
                return
            confirm = self.my_pin_confirm.text().strip()
            if new_pin != confirm:
                self.my_settings_status.setText("New PINs do not match.")
                return
            if len(new_pin) < 4:
                self.my_settings_status.setText(
                    "PIN must be at least 4 digits."
                )
                return
            self.current_user.pin_hash = Repository.hash_pin(new_pin)
            self.my_pin_current.clear()
            self.my_pin_new.clear()
            self.my_pin_confirm.clear()

        # Update display name and/or PIN via full User update
        user_changed = False
        if display_name != self.current_user.display_name:
            self.current_user.display_name = display_name
            user_changed = True
        if new_pin:
            user_changed = True  # pin_hash already updated above
        if user_changed:
            self.repo.update_user(self.current_user)

        # Save user_settings
        self.repo.update_user_settings(
            self.current_user.id,
            theme=theme,
            font_size=font_size,
            compact_mode=compact,
            default_truck_filter=truck_filter,
            preferred_date_range=date_range,
        )

        # Live-apply theme
        from pathlib import Path
        from wired_part.utils.platform import get_font_family
        qss_file = (
            Path(__file__).parent.parent / "styles" / f"{theme}.qss"
        )
        if qss_file.exists():
            from PySide6.QtWidgets import QApplication
            qss = qss_file.read_text(encoding="utf-8")
            qss = qss.replace("{{FONT_FAMILY}}", get_font_family())
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)

        # Also update global Config.APP_THEME so refresh() picks it up
        Config.update_theme(theme)

        self.my_settings_status.setText(
            "Settings saved. Theme applied."
        )

    # ── Refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._refresh_users()
        self._refresh_hats()
        self._refresh_categories()
        self._refresh_suppliers()
