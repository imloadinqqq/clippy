from PyQt6.QtGui import QPixmap, QIcon, QImage
from PyQt6.QtWidgets import (
    QApplication, QListWidget, QMainWindow, QBoxLayout,
    QLineEdit, QPushButton, QWidget, QListWidgetItem
)
from PyQt6.QtCore import QTimer
import sqlite3
import os
import hashlib

IMAGE_DIR = "clipboard_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Database setup
conn = sqlite3.connect('history.db')
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        data TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()


def save_to_db(item_type, data):
    c.execute("INSERT INTO history (type, data) VALUES (?, ?)",
              (item_type, data))
    conn.commit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Clippy")

        # clipboard and clipboard history
        self.clipboard = QApplication.clipboard()
        self.history = []
        self.filtered_history = None

        # widgets
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search")
        self.input.textChanged.connect(self.search_list)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.selection_to_clipboard)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_item)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.manual_refresh)

        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_all)

        # layout
        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        layout.addWidget(self.input)
        layout.addWidget(self.list)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.clear_button)

        container = QWidget()
        container.setLayout(layout)
        container.setFixedSize(500, 500)
        self.setCentralWidget(container)

        # clipboard timer
        self.last_text = ""
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(1000)

        self.update_ui()

    def check_clipboard(self):
        mime = self.clipboard.mimeData()

        if mime.hasText():
            text = self.clipboard.text()
            if text and text != self.last_text:
                self.last_text = text
                c.execute(
                    "SELECT COUNT(*) FROM history WHERE type = 'text' AND data = ?", (text,))
                if c.fetchone()[0] == 0:
                    save_to_db("text", text)
                    self.update_ui()

        elif mime.hasImage():
            image = self.clipboard.image()
            if not image.isNull():
                image_hash = self.hash_qimage(image)
                filename = f"{image_hash}.png"  # filename using hash, unique
                filepath = os.path.join(IMAGE_DIR, filename)

                # Only save if not already in DB
                c.execute(
                    "SELECT COUNT(*) FROM history WHERE type = 'image' AND data = ?", (filepath,))
                if c.fetchone()[0] == 0:
                    image.save(filepath)
                    save_to_db("image", filepath)
                    self.update_ui()

    def selection_to_clipboard(self, item):
        row = self.list.row(item)
        source = self.filtered_history if self.filtered_history is not None else self.history

        if row < 0 or row >= len(source):
            return

        entry = source[row]
        print(f"Copied item: {entry['data']}")

        if entry["type"] == "text":
            self.clipboard.setText(entry["data"])
        elif entry["type"] == "image":
            pixmap = QPixmap(entry["data"])
            if not pixmap.isNull():
                self.clipboard.setPixmap(pixmap)

    def load_history(self, limit=50):
        c.execute(
            "SELECT type, data FROM history ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        return [{"type": row[0], "data": row[1]} for row in rows]

    # avoid having same image being added to list multiple times, using its hash
    def hash_qimage(self, image: QImage) -> str:
        buffer = image.bits().asstring(image.sizeInBytes())
        return hashlib.sha256(buffer).hexdigest()

    def update_ui(self):
        self.history = self.load_history()
        current_count = self.list.count()
        history_count = len(self.history)

        # Update existing items
        for i in range(min(current_count, history_count)):
            hist_item = self.history[i]
            list_item = self.list.item(i)

            if hist_item["type"] == "text":
                if list_item.text() != hist_item["data"]:
                    list_item.setText(hist_item["data"])
                    list_item.setIcon(QIcon())
            elif hist_item["type"] == "image":
                expected_label = f"Image #{i+1}"
                if list_item.text() != expected_label:
                    list_item.setText(expected_label)
                if list_item.icon().isNull():
                    pixmap = QPixmap()
                    pixmap.load(hist_item["data"])
                    pixmap = pixmap.scaled(64, 64)
                    list_item.setIcon(QIcon(pixmap))

        # Add new items
        for i in range(current_count, history_count):
            hist_item = self.history[i]
            if hist_item["type"] == "text":
                self.list.addItem(hist_item["data"])
            elif hist_item["type"] == "image":
                pixmap = QPixmap(hist_item["data"]).scaled(64, 64)
                icon = QIcon(pixmap)
                list_item = QListWidgetItem(f"Image #{i+1}")
                list_item.setIcon(icon)
                self.list.addItem(list_item)

        # Remove excess
        while self.list.count() > history_count:
            self.list.takeItem(self.list.count() - 1)

    def search_list(self, text):
        self.list.clear()

        if not text:
            self.filtered_history = None
            self.update_ui()
            return

        filtered = [
            item for item in self.history
            if item["type"] == "text" and text.lower() in item["data"].lower()
        ]
        self.filtered_history = filtered
        for item in filtered:
            self.list.addItem(item["data"])

    def delete_item(self):
        selected_items = self.list.selectedItems()
        for item in selected_items:
            row = self.list.row(item)
            entry = self.history[row]

            # Remove from DB
            c.execute("DELETE FROM history WHERE type = ? AND data = ?",
                      (entry["type"], entry["data"]))
            conn.commit()

            # Remove image file if needed
            if entry["type"] == "image" and os.path.exists(entry["data"]):
                os.remove(entry["data"])

        self.filtered_history = None
        self.update_ui()

    def clear_all(self):
        # Remove image files
        for entry in self.history:
            if entry["type"] == "image" and os.path.exists(entry["data"]):
                os.remove(entry["data"])

        # Clear DB
        c.execute("DELETE FROM history")
        conn.commit()

        self.update_ui()
        print("Cleared all clipboard history.")

    def manual_refresh(self):
        self.check_clipboard()
        self.update_ui()
