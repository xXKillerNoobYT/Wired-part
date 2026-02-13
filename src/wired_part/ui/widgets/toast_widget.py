"""Toast notification widget — non-intrusive slide-in alerts."""

from PySide6.QtCore import (
    QPropertyAnimation,
    QEasingCurve,
    QPoint,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout


_SEVERITY_COLORS = {
    "info": "#89b4fa",
    "success": "#a6e3a1",
    "warning": "#f9e2af",
    "error": "#f38ba8",
}


class Toast(QWidget):
    """A single toast notification that auto-dismisses."""

    def __init__(self, message: str, severity: str = "info",
                 duration_ms: int = 4000, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(320)

        border_color = _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["info"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            f"QLabel {{ background: #1e1e2e; color: #cdd6f4; "
            f"border: 2px solid {border_color}; border-radius: 8px; "
            f"padding: 10px 14px; font-size: 12px; }}"
        )
        layout.addWidget(self.label)
        self.adjustSize()

        # Auto-dismiss timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(duration_ms)
        self._timer.timeout.connect(self._fade_out)

    def show_toast(self, x: int, y: int):
        """Show the toast at the given screen position with slide-in."""
        self.move(x, y + 20)
        self.show()

        # Slide up animation
        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(200)
        self._slide_anim.setStartValue(QPoint(x, y + 20))
        self._slide_anim.setEndValue(QPoint(x, y))
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._slide_anim.start()

        self._timer.start()

    def _fade_out(self):
        """Slide down and close."""
        current = self.pos()
        self._close_anim = QPropertyAnimation(self, b"pos")
        self._close_anim.setDuration(200)
        self._close_anim.setStartValue(current)
        self._close_anim.setEndValue(QPoint(current.x(), current.y() + 20))
        self._close_anim.setEasingCurve(QEasingCurve.InCubic)
        self._close_anim.finished.connect(self.close)
        self._close_anim.finished.connect(self.deleteLater)
        self._close_anim.start()


class ToastManager:
    """Manages toast notifications for a parent window."""

    def __init__(self, parent_window: QWidget):
        self._parent = parent_window
        self._active_toasts: list[Toast] = []

    def show_toast(self, message: str, severity: str = "info",
                   duration_ms: int = 4000):
        """Show a toast notification in the bottom-right corner."""
        toast = Toast(message, severity, duration_ms)

        # Calculate position (bottom-right of parent)
        parent_geo = self._parent.geometry()
        x = parent_geo.right() - toast.width() - 20
        y = parent_geo.bottom() - toast.height() - 40

        # Stack above existing toasts
        for t in self._active_toasts:
            if t.isVisible():
                y -= t.height() + 8

        self._active_toasts.append(toast)
        toast.destroyed.connect(lambda: self._remove_toast(toast))
        toast.show_toast(x, y)

    def _remove_toast(self, toast: Toast):
        """Remove a toast from the active list."""
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
