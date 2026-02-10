"""Settings page — user management, categories, LLM config, general."""

from PySide6.QtCore import Qt
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

        # LLM Settings tab
        self.llm_widget = QWidget()
        self._setup_llm_tab()
        self.sub_tabs.addTab(self.llm_widget, "LLM Settings")

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

        save_btn = QPushButton("Save Settings")
        save_btn.setMinimumHeight(34)
        save_btn.clicked.connect(self._save_llm_settings)
        btn_layout.addWidget(save_btn)

        test_btn = QPushButton("Test Connection")
        test_btn.setMinimumHeight(34)
        test_btn.clicked.connect(self._test_llm_connection)
        btn_layout.addWidget(test_btn)

        fetch_btn = QPushButton("Fetch Models")
        fetch_btn.setMinimumHeight(34)
        fetch_btn.clicked.connect(self._fetch_models)
        btn_layout.addWidget(fetch_btn)

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

        Config.update_llm_settings(url, key, model, timeout)
        self.llm_status.setText(
            "Settings saved. Reconnect in the Agent tab to apply."
        )
        self.llm_status.setStyleSheet("color: #a6e3a1;")

    def _test_llm_connection(self):
        """Test the connection to the LLM server with current form values."""
        url = self.llm_url_input.text().strip()
        key = self.llm_key_input.text().strip() or "lm-studio"
        timeout = self.llm_timeout_spin.value()

        self.llm_status.setText("Testing connection...")
        self.llm_status.setStyleSheet("color: #fab387;")
        # Force UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=url, api_key=key, timeout=timeout,
            )
            models = client.models.list()
            model_names = [m.id for m in models.data]
            count = len(model_names)
            preview = ", ".join(model_names[:5])
            if count > 5:
                preview += f", ... ({count} total)"

            self.llm_status.setText(
                f"Connected! Found {count} model(s): {preview}"
            )
            self.llm_status.setStyleSheet("color: #a6e3a1;")
        except Exception as e:
            self.llm_status.setText(f"Connection failed: {e}")
            self.llm_status.setStyleSheet("color: #f38ba8;")

    def _fetch_models(self):
        """Fetch available models and populate the model picker combo box."""
        url = self.llm_url_input.text().strip()
        key = self.llm_key_input.text().strip() or "lm-studio"
        timeout = self.llm_timeout_spin.value()

        self.llm_status.setText("Fetching models...")
        self.llm_status.setStyleSheet("color: #fab387;")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=url, api_key=key, timeout=timeout,
            )
            models = client.models.list()
            model_names = sorted([m.id for m in models.data])

            if not model_names:
                self.llm_status.setText("No models found on server.")
                self.llm_status.setStyleSheet("color: #f38ba8;")
                return

            # Populate the combo box
            current = self.llm_model_combo.currentText()
            self.llm_model_combo.clear()
            for name in model_names:
                self.llm_model_combo.addItem(name)

            # Restore previous selection if it still exists
            idx = self.llm_model_combo.findText(current)
            if idx >= 0:
                self.llm_model_combo.setCurrentIndex(idx)
            elif len(model_names) == 1:
                self.llm_model_combo.setCurrentIndex(0)

            self.llm_status.setText(
                f"Found {len(model_names)} model(s). "
                "Select one from the dropdown."
            )
            self.llm_status.setStyleSheet("color: #a6e3a1;")
        except Exception as e:
            self.llm_status.setText(f"Failed to fetch models: {e}")
            self.llm_status.setStyleSheet("color: #f38ba8;")

    def _reset_llm_defaults(self):
        self.llm_url_input.setText("http://localhost:1234/v1")
        self.llm_key_input.setText("lm-studio")
        self.llm_model_combo.clear()
        self.llm_model_combo.addItem("local-model")
        self.llm_model_combo.setCurrentText("local-model")
        self.llm_timeout_spin.setValue(60)
        self.llm_status.setText("Defaults restored. Click Save to apply.")
        self.llm_status.setStyleSheet("color: #fab387;")

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
