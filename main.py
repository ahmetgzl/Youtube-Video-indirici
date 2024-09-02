import logging
import sys
import traceback
import os
from PyQt6.QtWidgets import QApplication
from gui import YouTubeDownloaderGUI

def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.critical("Uncaught exception:\n%s", tb)
    print("Critical error message:\n", tb)
    QApplication.quit()

sys.excepthook = excepthook

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='youtube_downloader.log',
        filemode='w'
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def load_styles(app, ex):
    style_file = os.path.join(os.path.dirname(__file__), 'style.qss')
    if os.path.exists(style_file):
        with open(style_file, 'r') as f:
            style_sheet = f.read()
            app.setStyleSheet(style_sheet)  # Uygulamaya stil uygula
            ex.setStyleSheet(style_sheet)  # Ana pencereye de aynı stili uygula
        logging.info(f"Styles loaded from {style_file}")
    else:
        logging.warning(f"Style file {style_file} not found!")

def main():
    setup_logging()
    logging.info("Application starting...")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    ex = YouTubeDownloaderGUI()
    load_styles(app, ex)

    ex.show()

    exit_code = app.exec()
    logging.info("Application closing...")
    sys.exit(exit_code)

if __name__ == '__main__':
    main()