"""Settings page — user management, categories, LLM config, general."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
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

        # Suppliers tab
        self.suppliers_widget = QWidget()
        self._setup_suppliers_tab()
        self.sub_tabs.addTab(self.suppliers_widget, "Suppliers")

        # LLM Settings tab
        self.llm_widget = QWidget()
        self._setup_llm_tab()
        self.sub_tabs.addTab(self.llm_widget, "LLM Settings")

        # Agent Config tab
        self.agent_config_widget = QWidget()
        self._setup_agent_config_tab()
        self.sub_tabs.addTab(self.agent_config_widget, "Agent Config")

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
        self.suppliers_table.setColumnCount(7)
        self.suppliers_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Contact", "Email", "Phone",
             "Preference", "Active"]
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

        # Model picker — editable combo box
        model_row = QHBoxLayout()
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setEditable(True)
        self.llm_model_combo.setMinimumWidth(200)
        self.llm_model_combo.lineEdit().setPlaceholderText("local-model")
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
        self.llm_model_combo.clear()
        for name in model_names:
            self.llm_model_combo.addItem(name)

        idx = self.llm_model_combo.findText(current)
        if idx >= 0:
            self.llm_model_combo.setCurrentIndex(idx)
        elif len(model_names) == 1:
            self.llm_model_combo.setCurrentIndex(0)

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

        layout.addStretch()

    def _save_theme(self):
        from wired_part.config import Config
        theme = self.theme_combo.currentData()
        Config.update_theme(theme)
        self.general_status.setText(
            f"Theme set to '{theme}'. Restart the app to apply."
        )
        self.general_status.setStyleSheet("color: #a6e3a1;")

    # ── Refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._refresh_users()
        self._refresh_categories()
        self._refresh_suppliers()
