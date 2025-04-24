import sys
from PySide6.QtWidgets import QApplication
from ui.layout import AppUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppUI()
    window.setWindowTitle("Temp Email Client")
    window.show()
    sys.exit(app.exec())
