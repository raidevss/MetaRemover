import sys

from PySide6.QtWidgets import QApplication

from metaremover.gui import MainWindow
from metaremover import theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MetaRemover")
    app.setOrganizationName("MetaRemover")
    theme.apply(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
