"""Application entry point — sets up QApplication and launches the main window."""

import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.schema import initialize_database


def _load_theme(app: QApplication):
    """Load the configured QSS theme stylesheet."""
    theme = Config.APP_THEME.lower()
    styles_dir = Path(__file__).parent / "ui" / "styles"
    qss_file = styles_dir / f"{theme}.qss"
    if qss_file.exists():
        app.setStyleSheet(qss_file.read_text(encoding="utf-8"))


def main():
    """Launch the Wired-Part application."""
    # Initialize database
    db = DatabaseConnection(Config.DATABASE_PATH)
    initialize_database(db)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Wired-Part")
    app.setOrganizationName("WeirdToo LLC")

    # Set application font before theme to avoid -1 pointSize warnings
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Apply theme
    _load_theme(app)

    # Import here to avoid circular imports and let DB init first
    from wired_part.database.repository import Repository
    from wired_part.ui.login_dialog import FirstRunDialog, LoginDialog
    from wired_part.ui.main_window import MainWindow

    repo = Repository(db)

    # First-run setup: create admin if no users exist
    if repo.user_count() == 0:
        first_run = FirstRunDialog(repo)
        if first_run.exec() != FirstRunDialog.Accepted:
            sys.exit(0)
        current_user = first_run.created_user
    else:
        # Login screen
        login = LoginDialog(repo)
        if login.exec() != LoginDialog.Accepted:
            sys.exit(0)
        current_user = login.authenticated_user

    # Launch main window
    window = MainWindow(db, current_user)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
