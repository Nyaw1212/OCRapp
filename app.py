"""Leave Card OCR Extractor — Phase 1.

The selected source is opened read-only.  This program never writes to, renames,
uploads, or otherwise changes that source file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

SUPPORTED_FILTER = "Leave cards (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    """Create a Qt pixmap without saving a temporary image file."""
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Leave Card OCR Extractor — Phase 1 (Local / Read-only)")
        self.resize(1180, 760)

        self.path: Path | None = None
        self.document: fitz.Document | None = None
        self.page_number = 0
        self.source_image: Image.Image | None = None
        self.zoom = 100

        self._build_ui()
        self._create_menu()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        controls = QHBoxLayout()
        open_button = QPushButton("Open File")
        open_button.clicked.connect(self.open_file)
        controls.addWidget(open_button)

        self.previous_button = QPushButton("← Previous Page")
        self.previous_button.clicked.connect(lambda: self.change_page(-1))
        controls.addWidget(self.previous_button)
        self.page_label = QLabel("No file open")
        controls.addWidget(self.page_label)
        self.next_button = QPushButton("Next Page →")
        self.next_button.clicked.connect(lambda: self.change_page(1))
        controls.addWidget(self.next_button)
        controls.addSpacing(18)

        controls.addWidget(QLabel("Zoom:"))
        self.zoom_box = QSpinBox()
        self.zoom_box.setRange(25, 300)
        self.zoom_box.setSingleStep(25)
        self.zoom_box.setSuffix("%")
        self.zoom_box.setValue(100)
        self.zoom_box.valueChanged.connect(self.set_zoom)
        controls.addWidget(self.zoom_box)

        controls.addStretch()
        self.ocr_button = QPushButton("Run Local OCR")
        self.ocr_button.clicked.connect(self.run_ocr)
        controls.addWidget(self.ocr_button)
        main_layout.addLayout(controls)

        self.image_label = QLabel("Open a leave-card image or PDF to begin.")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(500, 450)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidget(self.image_label)
        self.image_scroll.setWidgetResizable(False)

        self.raw_text = QPlainTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setPlaceholderText("Raw OCR text will appear here. Review it before using any result.")
        self.copy_button = QPushButton("Copy Raw Text")
        self.copy_button.clicked.connect(self.copy_raw_text)

        text_panel = QVBoxLayout()
        text_panel.addWidget(QLabel("Raw OCR output — unconfirmed; not leave records"))
        text_panel.addWidget(self.raw_text)
        text_panel.addWidget(self.copy_button)
        text_container = QWidget()
        text_container.setLayout(text_panel)

        content = QHBoxLayout()
        content.addWidget(self.image_scroll, 3)
        content.addWidget(text_container, 2)
        main_layout.addLayout(content, 1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Local / read-only. No source file changes or uploads.")
        self._update_controls()

    def _create_menu(self) -> None:
        open_action = QAction("Open File…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        self.menuBar().addMenu("File").addAction(open_action)

    def _update_controls(self) -> None:
        has_image = self.source_image is not None
        is_pdf = self.document is not None
        page_count = len(self.document) if self.document else 1
        self.previous_button.setEnabled(is_pdf and self.page_number > 0)
        self.next_button.setEnabled(is_pdf and self.page_number < page_count - 1)
        self.ocr_button.setEnabled(has_image)
        self.copy_button.setEnabled(bool(self.raw_text.toPlainText()))
        if has_image:
            self.page_label.setText(f"Page {self.page_number + 1} of {page_count}")
        else:
            self.page_label.setText("No file open")

    def open_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Open leave card (read-only)", "", SUPPORTED_FILTER)
        if not filename:
            return
        new_path = Path(filename)
        try:
            self.document = None
            self.path = new_path
            self.page_number = 0
            if new_path.suffix.lower() == ".pdf":
                self.document = fitz.open(new_path)
                if len(self.document) == 0:
                    raise ValueError("The PDF has no pages.")
                self._render_pdf_page()
            elif new_path.suffix.lower() in IMAGE_SUFFIXES:
                with Image.open(new_path) as opened:
                    self.source_image = ImageOps.exif_transpose(opened).convert("RGB")
            else:
                raise ValueError("Unsupported file type.")
            self.raw_text.clear()
            self._show_image()
            self.statusBar().showMessage(f"Opened read-only: {new_path.name}")
        except Exception as error:
            self.path = None
            self.document = None
            self.source_image = None
            QMessageBox.critical(self, "Could not open file", str(error))
        self._update_controls()

    def _render_pdf_page(self) -> None:
        assert self.document is not None
        page = self.document.load_page(self.page_number)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        self.source_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def change_page(self, delta: int) -> None:
        if not self.document:
            return
        self.page_number = max(0, min(self.page_number + delta, len(self.document) - 1))
        self._render_pdf_page()
        self.raw_text.clear()
        self._show_image()
        self._update_controls()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = zoom
        self._show_image()

    def _show_image(self) -> None:
        if not self.source_image:
            return
        pixmap = pil_to_pixmap(self.source_image)
        scaled = pixmap.scaled(
            int(pixmap.width() * self.zoom / 100),
            int(pixmap.height() * self.zoom / 100),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def run_ocr(self) -> None:
        if not self.source_image:
            return
        try:
            configured = os.environ.get("TESSERACT_CMD")
            if configured:
                pytesseract.pytesseract.tesseract_cmd = configured
            # Gentle preparation only in Phase 1; source_image itself is not changed.
            working = ImageOps.grayscale(self.source_image)
            working = ImageEnhance.Contrast(working).enhance(1.4)
            text = pytesseract.image_to_string(working, config="--psm 6")
            self.raw_text.setPlainText(text)
            self.statusBar().showMessage("Local OCR completed. Raw text still needs human review.")
        except pytesseract.TesseractNotFoundError:
            QMessageBox.warning(
                self,
                "Tesseract not found",
                "Install Tesseract OCR, then restart the app. See README.md for setup instructions.",
            )
        except Exception as error:
            QMessageBox.critical(self, "OCR failed", str(error))
        self._update_controls()

    def copy_raw_text(self) -> None:
        QApplication.clipboard().setText(self.raw_text.toPlainText())
        self.statusBar().showMessage("Raw OCR text copied. It has not been saved as leave records.")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.document:
            self.document.close()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Leave Card OCR Extractor")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
