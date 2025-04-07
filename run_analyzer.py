import sys
from src.analyzer_gui import VideoStreamAnalyzerApp
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoStreamAnalyzerApp()
    window.show()
    sys.exit(app.exec_())