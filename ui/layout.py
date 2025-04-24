# layout_glass_static.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QApplication, QTreeWidget, QTreeWidgetItem, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Signal, Qt, QThread, QDateTime
from ui.compose_popup import ComposePopup
from ui.notify_popup import NotifyPopup
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation
from logic.api import create_temp_email, poll_inbox
from playsound import playsound
from ui.loading_popup import LoadingPopup


class EmailWorker(QThread):
    finished = Signal(tuple)

    def run(self):
        from logic.api import create_temp_email
        result = create_temp_email()
        self.finished.emit(result)


class PollThread(QThread):
    message_signal = Signal(str)

    def __init__(self, base, token):
        super().__init__()
        self.base = base
        self.token = token

    def run(self):
        poll_inbox(self.base, self.token, self.message_signal.emit)


class AppUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GlassMail Client")
        self.setMinimumSize(1280, 800)
        self.messages = []
        self.new_message_flag = False
        self.setup_ui()
        self.setStyleSheet(self.elegant_style())

    def open_compose_popup(self):
        self.popup = ComposePopup(self)
        self.popup.show()

    def setup_ui(self):
        layout = QHBoxLayout(self)

        # 👉 Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMaximumWidth(200)
        self.sidebar.itemClicked.connect(self.handle_sidebar_click)
        self.inbox_item = None
        for label in ["📥 Inbox", "⭐ Important", "📤 Sent"]:
            item = QListWidgetItem(label)
            if "Inbox" in label:
                self.inbox_item = item
            self.sidebar.addItem(item)
        layout.addWidget(self.sidebar)

        # 👉 Center Panel
        center_panel = QVBoxLayout()
        top = QHBoxLayout()

        # 👉 Email input + buttons
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Temporary Email Appears Here")
        top.addWidget(self.email_input)

        self.compose_button = QPushButton("compose")
        self.compose_button.clicked.connect(self.open_compose_popup)
        top.addWidget(self.compose_button)

        self.copy_button = QPushButton("📋 Copy")
        self.copy_button.clicked.connect(self.copy_email)
        top.addWidget(self.copy_button)

        self.gen_button = QPushButton("✉️New Mail")
        self.gen_button.clicked.connect(self.handle_generate)
        top.addWidget(self.gen_button)

        self.mark_btn = QPushButton("⭐ Mark Important")
        self.mark_btn.clicked.connect(self.mark_important)
        top.addWidget(self.mark_btn)

        center_panel.addLayout(top)

        # 👉 Message Table
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Subject", "Preview", "Time", "From"])
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 400)
        self.tree.setColumnWidth(2, 120)
        self.tree.setColumnWidth(3, 180)
        self.tree.itemClicked.connect(self.view_message)
        center_panel.addWidget(self.tree)

        # 👉 Instructions
        self.instruction = QTextEdit()
        self.instruction.setReadOnly(True)
        self.instruction.setHtml("""
        <b>Note:</b> This is a limited-use inbox. <br>
        You may receive only 1–2 emails before needing to regenerate.<br>
        Please click <b>✉️New Mail</b> again after ~2 minutes to refresh.
        """)
        self.instruction.setMaximumHeight(80)
        center_panel.addWidget(self.instruction)

        layout.addLayout(center_panel)

        # 👉 Message Preview Panel
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.preview)

    def fade_widget(self, widget, duration=300):
        effect = QGraphicsOpacityEffect()
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.start()

        # Keep reference alive
        self._current_fade = anim

    def handle_generate(self):
        self.preview.clear()
        self.tree.clear()

        # 🔄 Show the loading popup
        self.loader = LoadingPopup(self)
        self.loader.show()

        self.gen_button.setText("⏳ Generating...")
        self.gen_button.setEnabled(False)
        self.email_input.clear()

        # Start background thread
        self.email_worker = EmailWorker()
        self.email_worker.finished.connect(self.handle_email_result)
        self.email_worker.start()

    def handle_email_result(self, result):
        self.loader.close()

        if not result[1]:
            self.gen_button.setText("✉️ New Mail")
            self.gen_button.setEnabled(True)
            error_box = QMessageBox(self)
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle("Email Generation Failed")
            error_box.setText("❌ We couldn't generate your temp email.")
            error_box.setInformativeText("Please try again.")
            error_box.exec()
            return

        email, token, base, _ = result
        self.email_input.setText(email)
        self.gen_button.setText("✉️ New Mail")
        self.gen_button.setEnabled(True)

        from playsound import playsound
        playsound("assets/sounds/notify.wav")
        self.notifier = NotifyPopup("✅ Temp Email Created", email, self)
        self.notifier.show()

        self.poll_thread = PollThread(base, token)
        self.poll_thread.message_signal.connect(self.store_and_display)
        self.poll_thread.start()

    def store_and_display(self, message):
        subject = self.extract_subject(message)
        sender = self.extract_sender(message)
        snippet = self.summarize_message(message)
        date = self.extract_date(message)

        item = QTreeWidgetItem([subject, snippet, date, sender])
        item.setData(0, Qt.UserRole, message)
        self.tree.addTopLevelItem(item)

        # Save message data
        self.messages.append({
            "message": message,
            "time": date,
            "important": False
        })

        # Optional notification and red dot
        self.notifier = NotifyPopup(subject, snippet, self)
        self.notifier.show()
        if self.inbox_item:
            self.inbox_item.setText("📥 Inbox 🔴")
            self.new_message_flag = True

    def extract_subject(self, message):
        lines = message.splitlines()
        for line in lines:
            if "subject:" in line.lower():
                parts = line.split(":", 1)
                return parts[1].strip() if len(parts) > 1 else "No Subject"
        # If nothing matched, fallback to first line with text
        for line in lines:
            if line.strip():
                return line.strip()[:80]
        return "No Subject"
    def summarize_message(self, message):
        lines = message.splitlines()
        content = " ".join(line.strip() for line in lines if line.strip())
        if len(content) > 100:
            return content[:97] + "..."
        return content

    def extract_sender(self, message):
        lines = message.splitlines()
        for line in lines:
            if "from:" in line.lower():
                parts = line.split(":", 1)
                return parts[1].strip() if len(parts) > 1 else "Unknown Sender"
        return "Unknown Sender"

    def extract_date(self, message):
        lines = message.splitlines()
        for line in lines:
            if "date:" in line.lower():
                return line.split(":", 1)[1].strip()
        return QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm")


    def extract_snippet(self, message):
        return message.replace('\n', ' ')[:100]

    def view_message(self, item):
        self.preview.setPlainText(item.data(0, Qt.UserRole))

    def mark_important(self):
        item = self.tree.currentItem()
        if item:
            message_body = item.data(0, Qt.UserRole)
            for entry in self.messages:
                if entry["message"] == message_body:
                    entry["important"] = not entry["important"]

    def handle_sidebar_click(self, item):
        text = item.text().replace(" 🔴", "")
        self.tree.clear()
        self.preview.clear()

        if text == "📥 Inbox":
            # existing logic...
            if self.new_message_flag and self.inbox_item:
                self.inbox_item.setText("📥 Inbox")
                self.new_message_flag = False
            for entry in self.messages:
                subject = self.extract_subject(entry["message"])
                snippet = self.extract_snippet(entry["message"])
                sender = self.extract_sender(entry["message"])
                row = QTreeWidgetItem([subject, snippet, entry["time"], sender])
                row.setData(0, Qt.UserRole, entry["message"])
                self.tree.addTopLevelItem(row)

        elif text == "⭐ Important":
            # existing logic...
            for entry in self.messages:
                if entry["important"]:
                    subject = self.extract_subject(entry["message"])
                    snippet = self.extract_snippet(entry["message"])
                    sender = self.extract_sender(entry["message"])
                    row = QTreeWidgetItem([subject, snippet, entry["time"], sender])
                    row.setData(0, Qt.UserRole, entry["message"])
                    self.tree.addTopLevelItem(row)

        elif text == "📤 Sent":
            # NEW: Show saved messages from sent_emails folder
            import os
            sent_dir = "sent_emails"
            if not os.path.exists(sent_dir):
                return

            for filename in os.listdir(sent_dir):
                if filename.endswith(".txt"):
                    path = os.path.join(sent_dir, filename)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract fields
                    subject = filename.replace("_", " ").split("_")[0]
                    snippet = content.splitlines()[-1][:80] + "..."
                    time = filename[-10:-4]  # crude time from filename
                    sender = "You"

                    row = QTreeWidgetItem([subject, snippet, time, sender])
                    row.setData(0, Qt.UserRole, content)
                    self.tree.addTopLevelItem(row)

    def copy_email(self):
        email = self.email_input.text()
        if email:
            QApplication.clipboard().setText(email)
            self.preview.setPlainText(f"✅ Email copied to clipboard:{email}")

    def elegant_style(self):
        return '''
        QWidget {
            background-color: #0d1117;
            color: #e6edf3;
            font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            font-size: 15px;
        }
        QListWidget#sidebar {
            background-color: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 0.06),
                stop:1 rgba(255, 255, 255, 0.02)
            );
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            padding: 10px;
            border-radius: 16px;
        }
        QTreeWidget {
            background-color: rgba(255, 255, 255, 0.04);
            border-radius: 14px;
            font-size: 14px;
        }
        QTextEdit {
            background-color: rgba(255, 255, 255, 0.06);
            border-radius: 14px;
            padding: 12px;
            font-size: 14px;
        }
        '''
