"""Application entry point — sets up QApplication and launches the main window."""

import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.schema import initialize_database
from wired_part.utils.platform import get_font_family, get_primary_font_name


def _load_theme(app: QApplication, theme: str | None = None):
    """Load a QSS theme stylesheet.

    Injects the platform-appropriate font-family into the QSS before
    applying it, so the stylesheet always references the correct native
    font for the current OS.

    Parameters
    ----------
    app:
        The running QApplication.
    theme:
        Theme name (``"dark"``, ``"light"``, ``"retro"``).
        Falls back to ``Config.APP_THEME`` when *None*.
    """
    theme = (theme or Config.APP_THEME).lower()
    styles_dir = Path(__file__).parent / "ui" / "styles"
    qss_file = styles_dir / f"{theme}.qss"
    if qss_file.exists():
        qss = qss_file.read_text(encoding="utf-8")
        # Replace the placeholder with platform-specific font stack
        qss = qss.replace("{{FONT_FAMILY}}", get_font_family())
        app.setStyleSheet(qss)


def _login(repo) -> "User | None":
    """Show the login dialog (or first-run setup) and return the user.

    Returns ``None`` if the user cancels the dialog.
    """
    from wired_part.ui.login_dialog import FirstRunDialog, LoginDialog

    if repo.user_count() == 0:
        first_run = FirstRunDialog(repo)
        if first_run.exec() != FirstRunDialog.Accepted:
            return None
        return first_run.created_user

    login = LoginDialog(repo)
    if login.exec() != LoginDialog.Accepted:
        return None
    return login.authenticated_user


def main():
    """Launch the Wired-Part application."""
    # Initialize database
    db = DatabaseConnection(Config.DATABASE_PATH)
    initialize_database(db)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Wired-Part")
    app.setOrganizationName("WeirdToo LLC")

    # Set application font (platform-aware) before theme to avoid
    # -1 pointSize warnings
    font = QFont(get_primary_font_name(), 10)
    app.setFont(font)

    # Apply theme
    _load_theme(app)

    # Import here to avoid circular imports and let DB init first
    from wired_part.database.repository import Repository
    from wired_part.ui.main_window import MainWindow

    repo = Repository(db)

    # Login loop — re-shows the login dialog after logout
    while True:
        current_user = _login(repo)
        if current_user is None:
            # User cancelled the login dialog
            sys.exit(0)

        # Apply the user's preferred theme (falls back to Config.APP_THEME)
        settings = repo.get_or_create_user_settings(current_user.id)
        _load_theme(app, settings.theme)

        window = MainWindow(db, current_user)

        # Track whether the user logged out (vs. closed the window)
        logout_flag = {"triggered": False}

        def _handle_logout():
            logout_flag["triggered"] = True

        window.logout_requested.connect(_handle_logout)
        window.show()

        app.exec()

        if not logout_flag["triggered"]:
            # User closed the window normally — exit the app
            break

    sys.exit(0)


if __name__ == "__main__":
    main()
