from PyQt6.QtWidgets import (
    QApplication, QListWidget, QMainWindow, QBoxLayout,
    QLineEdit, QPushButton, QWidget
)
from PyQt6.QtCore import QTimer
import json
import os

HISTORY_FILE = "history.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Clippy")

        # clipboard and clipboard history
        self.clipboard = QApplication.clipboard()
        self.history = self.load_history()

        # widget initialization
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search")
        self.input.textChanged.connect(self.search_list) # on text change
        self.list = QListWidget()
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_item)

        # layout for container
        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        layout.addWidget(self.input)
        layout.addWidget(self.list)
        layout.addWidget(self.delete_button)

        # main container for widgets
        container = QWidget()
        container.setLayout(layout)
        container.setFixedSize(500, 500)
        self.setCentralWidget(container)

        self.last_text = ""
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(1000)

        self.update_ui()

    # updates list based on filtered search, fuzzy
    def search_list(self, text):
        self.list.clear()
        filtered = [item for item in self.history if text.lower() in item.lower()]
        self.list.addItems(filtered)

    # read json history
    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        return []

    # connect to QTimer to check clipboard contents
    def check_clipboard(self):
        text = self.clipboard.text()
        if text and text != self.last_text:
            self.last_text = text
            if text not in self.history:
                self.history.insert(0, text)
                self.history = self.history[:50]
                self.save_history()
                self.update_ui()

    # write contents to json file
    def save_history(self):
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)

    def update_ui(self):
        self.list.clear()
        for item in self.history:
            self.list.addItem(item)

    def delete_item(self):
        selected_items = self.list.selectedItems()
        for item in selected_items:
            text = item.text()
            if text in self.history:
                self.history.remove(text)
                print(f"Deleted: {text}")
        self.save_history()
        self.update_ui()
