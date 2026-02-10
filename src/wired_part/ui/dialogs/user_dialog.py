"""Dialog for adding and editing users with hat (role) assignment."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.utils.constants import FULL_ACCESS_HATS


class UserDialog(QDialog):
    """Add or edit a user with hat (role) assignments."""

    def __init__(self, repo: Repository, user: User = None,
                 current_user: User = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.user = user
        self.current_user = current_user
        self.editing = user is not None
        self._hat_checkboxes: dict[int, QCheckBox] = {}

        self.setWindowTitle("Edit User" if self.editing else "Add User")
        self.setMinimumWidth(440)
        self.setMinimumHeight(500)

        self._setup_ui()
        if self.editing:
            self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. jsmith")
        self.username_input.setMinimumHeight(30)
        form.addRow("Username:", self.username_input)

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("e.g. John Smith")
        self.display_name_input.setMinimumHeight(30)
        form.addRow("Display Name:", self.display_name_input)

        # Legacy role (kept for DB compatibility)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["admin", "user"])
        self.role_combo.setMinimumHeight(30)
        self.role_combo.setToolTip(
            "Base role (admin users can manage the system). "
            "Hats below control fine-grained permissions."
        )
        form.addRow("Base Role:", self.role_combo)

        # PIN fields (optional when editing)
        pin_label = "New PIN:" if self.editing else "PIN:"
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText(
            "Leave blank to keep current" if self.editing else "4-6 digit PIN"
        )
        self.pin_input.setMaxLength(6)
        self.pin_input.setMinimumHeight(30)
        form.addRow(pin_label, self.pin_input)

        self.pin_confirm = QLineEdit()
        self.pin_confirm.setEchoMode(QLineEdit.Password)
        self.pin_confirm.setPlaceholderText("Confirm PIN")
        self.pin_confirm.setMaxLength(6)
        self.pin_confirm.setMinimumHeight(30)
        form.addRow("Confirm:", self.pin_confirm)

        layout.addLayout(form)

        # ── Hats Assignment ─────────────────────────────────────
        hats_group = QGroupBox("Hats (Roles)")
        hats_layout = QVBoxLayout()

        # Check if current user can assign hats
        can_assign_hats = self._can_assign_hats()

        if not can_assign_hats:
            hats_layout.addWidget(QLabel(
                "Only Admin and IT users can assign hats."
            ))

        hats_layout.addWidget(QLabel(
            "Select one or more hats to define this user's permissions:"
        ))

        all_hats = self.repo.get_all_hats()
        for hat in all_hats:
            cb = QCheckBox(hat.name)
            cb.setToolTip(
                f"{'Full access' if hat.name in FULL_ACCESS_HATS else 'Custom permissions'}"
            )
            cb.setEnabled(can_assign_hats)
            self._hat_checkboxes[hat.id] = cb
            hats_layout.addWidget(cb)

        hats_group.setLayout(hats_layout)
        layout.addWidget(hats_group)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setMinimumHeight(34)
        save_btn.clicked.connect(self._save)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _can_assign_hats(self) -> bool:
        """Check if the current user can assign hats to other users."""
        if not self.current_user:
            return True  # No restriction if no current user context
        return self.repo.user_has_any_full_access_hat(self.current_user.id)

    def _populate(self):
        self.username_input.setText(self.user.username)
        self.display_name_input.setText(self.user.display_name)
        idx = self.role_combo.findText(self.user.role)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)

        # Load current hats
        user_hats = self.repo.get_user_hats(self.user.id)
        assigned_hat_ids = {uh.hat_id for uh in user_hats}
        for hat_id, cb in self._hat_checkboxes.items():
            cb.setChecked(hat_id in assigned_hat_ids)

    def _save(self):
        username = self.username_input.text().strip()
        display_name = self.display_name_input.text().strip()
        role = self.role_combo.currentText()
        pin = self.pin_input.text().strip()
        pin_confirm = self.pin_confirm.text().strip()

        if not username:
            self.error_label.setText("Username is required")
            return
        if not display_name:
            self.error_label.setText("Display name is required")
            return

        # PIN validation
        if not self.editing and not pin:
            self.error_label.setText("PIN is required for new users")
            return
        if pin:
            if len(pin) < 4:
                self.error_label.setText("PIN must be at least 4 digits")
                return
            if not pin.isdigit():
                self.error_label.setText("PIN must contain only digits")
                return
            if pin != pin_confirm:
                self.error_label.setText("PINs do not match")
                return

        # Check username uniqueness
        existing = self.repo.get_user_by_username(username)
        if existing and (not self.editing or existing.id != self.user.id):
            self.error_label.setText("Username already taken")
            return

        # Collect selected hats
        selected_hat_ids = [
            hat_id for hat_id, cb in self._hat_checkboxes.items()
            if cb.isChecked()
        ]

        # Must have at least one hat
        if not selected_hat_ids:
            self.error_label.setText("User must have at least one hat")
            return

        try:
            if self.editing:
                self.user.username = username
                self.user.display_name = display_name
                self.user.role = role
                if pin:
                    self.user.pin_hash = Repository.hash_pin(pin)
                self.repo.update_user(self.user)
                # Update hats if allowed
                if self._can_assign_hats():
                    assigner_id = (
                        self.current_user.id if self.current_user else None
                    )
                    self.repo.set_user_hats(
                        self.user.id, selected_hat_ids,
                        assigned_by=assigner_id,
                    )
            else:
                user = User(
                    username=username,
                    display_name=display_name,
                    pin_hash=Repository.hash_pin(pin),
                    role=role,
                    is_active=1,
                )
                user.id = self.repo.create_user(user)
                self.user = user
                # Assign hats
                if self._can_assign_hats():
                    assigner_id = (
                        self.current_user.id if self.current_user else None
                    )
                    self.repo.set_user_hats(
                        user.id, selected_hat_ids,
                        assigned_by=assigner_id,
                    )
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
