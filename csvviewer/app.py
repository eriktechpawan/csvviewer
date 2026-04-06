"""CSV Viewer application entry point.

Initializes the Qt application and shows the main window.
"""

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from csvviewer.utils.constants import APP_NAME, APP_VERSION


def setup_dark_mode(app: QApplication):
    """Apply a dark color palette for dark-mode-friendly UI."""
    palette = QPalette()

    # Base colors
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))

    # Disabled colors
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,
        QColor(127, 127, 127)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
        QColor(127, 127, 127)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
        QColor(127, 127, 127)
    )

    app.setPalette(palette)
    app.setStyleSheet(
        "QToolTip { color: #ffffff; background-color: #2a82da; "
        "border: 1px solid white; }"
    )


def main():
    """Main entry point for the CSV Viewer application."""
    # Enable High DPI scaling for Retina / Apple Silicon displays
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("CSVViewer")

    # Apply dark mode
    setup_dark_mode(app)

    # Import here to avoid circular imports
    from csvviewer.ui.main_window import MainWindow

    window = MainWindow()

    # Handle file argument (open CSV directly)
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            window._load_file(file_path)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
