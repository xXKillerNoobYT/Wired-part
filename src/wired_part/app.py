"""Application entry point — sets up QApplication and launches the main window."""

import sys
from pathlib import Path

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

    # Apply theme
    _load_theme(app)

    # Import here to avoid circular imports and let DB init first
    from wired_part.ui.main_window import MainWindow

    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
