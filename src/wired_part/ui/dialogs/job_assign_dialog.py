"""Dialog for assigning users to a job."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from wired_part.database.models import JobAssignment
from wired_part.database.repository import Repository
from wired_part.utils.constants import JOB_ASSIGNMENT_ROLES


class JobAssignDialog(QDialog):
    """Assign a user to a job with a role."""

    def __init__(self, repo: Repository, job_id: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id

        self.setWindowTitle("Assign User to Job")
        self.setMinimumSize(350, 200)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Select a user and role:"))

        # User dropdown
        layout.addWidget(QLabel("User:"))
        self.user_combo = QComboBox()
        self.user_combo.setMinimumHeight(30)

        # Get already-assigned user IDs to exclude them
        existing = self.repo.get_job_assignments(self.job_id)
        assigned_ids = {a.user_id for a in existing}

        users = self.repo.get_all_users(active_only=True)
        for user in users:
            if user.id not in assigned_ids:
                self.user_combo.addItem(user.display_name, user.id)
        layout.addWidget(self.user_combo)

        # Role dropdown
        layout.addWidget(QLabel("Role:"))
        self.role_combo = QComboBox()
        self.role_combo.setMinimumHeight(30)
        for role in JOB_ASSIGNMENT_ROLES:
            self.role_combo.addItem(role.title(), role)
        layout.addWidget(self.role_combo)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        assign_btn = QPushButton("Assign")
        assign_btn.setMinimumHeight(34)
        assign_btn.clicked.connect(self._assign)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(assign_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _assign(self):
        if self.user_combo.count() == 0:
            self.error_label.setText("No available users to assign")
            return

        user_id = self.user_combo.currentData()
        role = self.role_combo.currentData()

        try:
            assignment = JobAssignment(
                job_id=self.job_id,
                user_id=user_id,
                role=role,
            )
            self.repo.assign_user_to_job(assignment)
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
