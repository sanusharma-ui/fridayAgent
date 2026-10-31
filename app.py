import sys

from PyQt5.QtWidgets import QApplication

from ui.main_window import AssistantWindow


def main():
    app = QApplication(sys.argv)
    window = AssistantWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
