"""主页界面 - 使用 qfluentwidgets 组件 + QWidget 基类"""

import json
import os
import re
import threading
import webbrowser
from urllib.error import URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)
from PySide6.QtSvgWidgets import QSvgWidget
from qfluentwidgets import (
    TitleLabel,
    CaptionLabel,
    BodyLabel,
    StrongBodyLabel,
    CardWidget,
    IconWidget,
    FluentIcon,
    InfoBadge,
    PushButton,
    InfoBar,
    InfoBarPosition,
    SegmentedWidget,
)
from gui.i18n import get_locale, set_locale, subscribe_locale_changed, t


def _read_local_version() -> str:
    """从环境变量读取本地版本号。"""
    try:
        from app.core.config import settings

        return settings.APP_VERSION or ""
    except Exception:
        return os.environ.get("APP_VERSION") or ""


def _version_key(version: str) -> tuple[int, ...]:
    """把版本字符串转换为可比较的数字元组。"""
    normalized = version.strip()
    match = re.search(r"(\d+(?:\.\d+)*)", normalized)
    if not match:
        return tuple()
    return tuple(int(part) for part in match.group(1).split("."))


class _InfoCard(CardWidget):
    """功能信息卡片"""

    def __init__(self, icon: FluentIcon, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(112)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        icon_widget = IconWidget(icon, self)
        icon_widget.setFixedSize(20, 20)
        layout.addWidget(icon_widget, alignment=Qt.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self._title_label = StrongBodyLabel(title, self)
        self._desc_label = CaptionLabel(desc, self)
        self._desc_label.setTextColor(QColor("#888888"), QColor("#aaaaaa"))
        self._desc_label.setWordWrap(True)

        text_layout.addWidget(self._title_label)
        text_layout.addWidget(self._desc_label)
        layout.addLayout(text_layout, 1)

    def setTexts(self, title: str, desc: str):
        """Update card title and description (used on language change)."""
        self._title_label.setText(title)
        self._desc_label.setText(desc)


class HomeInterface(QWidget):
    """主页界面"""

    updateCheckFinished = Signal(dict)

    GITHUB_URL = "https://github.com/visresearch/WordAgent"
    GITHUB_RELEASE_API = "https://api.github.com/repos/visresearch/WordAgent/releases/latest"
    WEBSITE_URL = "https://visresearch.github.io/WordAgent/"
    RELEASE_URL = "https://github.com/visresearch/WordAgent/releases/latest"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeInterface")
        self._current_version = _read_local_version()
        self.updateCheckFinished.connect(self._on_update_check_finished)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 36)
        layout.setSpacing(0)

        # --- Logo + 标题 ---
        header = QHBoxLayout()
        header.setSpacing(20)

        icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icon", "robot.svg")
        icon_path = os.path.normpath(icon_path)
        if os.path.exists(icon_path):
            svg = QSvgWidget(icon_path, self)
            svg.setFixedSize(64, 64)
            header.addWidget(svg, alignment=Qt.AlignVCenter)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = TitleLabel(t("app.name"), self)
        self._subtitle_label = subtitle = CaptionLabel(t("home.subtitle"), self)
        subtitle.setTextColor(QColor("#888888"), QColor("#aaaaaa"))
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        github_button = PushButton(t("home.button.github"), self)
        github_icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icon", "github.svg")
        github_icon_path = os.path.normpath(github_icon_path)
        if os.path.exists(github_icon_path):
            github_button.setIcon(QIcon(github_icon_path))
        github_button.clicked.connect(lambda: self._open_url(self.GITHUB_URL))
        button_row.addWidget(github_button)

        self._website_button = website_button = PushButton(t("home.button.website"), self)
        website_icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icon", "Web.svg")
        website_icon_path = os.path.normpath(website_icon_path)
        if os.path.exists(website_icon_path):
            website_button.setIcon(QIcon(website_icon_path))
        website_button.clicked.connect(lambda: self._open_url(self.WEBSITE_URL))
        button_row.addWidget(website_button)
        button_row.addStretch(1)

        title_col.addSpacing(8)
        title_col.addLayout(button_row)
        header.addLayout(title_col, 1)

        layout.addLayout(header)
        layout.addSpacing(28)

        # --- 状态栏 ---
        status = CardWidget(self)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(16, 12, 16, 12)
        sl.setSpacing(10)

        self._dot = InfoBadge.success("", self)
        self._dot.setFixedSize(10, 10)
        sl.addWidget(self._dot, alignment=Qt.AlignVCenter)

        self._status_label = BodyLabel(t("home.status.runningChecking"), self)
        sl.addWidget(self._status_label, 1)

        self._version_label = CaptionLabel(t("home.version.current", version=self._current_version or t("home.version.unknown")), self)
        self._version_label.setTextColor(QColor("#888888"), QColor("#aaaaaa"))
        sl.addWidget(self._version_label, alignment=Qt.AlignVCenter)

        self._update_label = CaptionLabel(t("home.update.checking"), self)
        self._update_label.setTextColor(QColor("#888888"), QColor("#aaaaaa"))
        sl.addWidget(self._update_label, alignment=Qt.AlignVCenter)

        self._download_button = PushButton(t("home.button.downloadLatest"), self)
        self._download_button.clicked.connect(lambda: self._open_url(self.RELEASE_URL))
        self._download_button.hide()
        sl.addWidget(self._download_button, alignment=Qt.AlignVCenter)

        layout.addWidget(status)
        layout.addSpacing(20)
        # --- language picker ---
        lang_card = CardWidget(self)
        lang_layout = QHBoxLayout(lang_card)
        lang_layout.setContentsMargins(16, 12, 16, 12)
        self._lang_label = BodyLabel(t("language.label"), self)
        self._lang_label.setStyleSheet("font-weight: bold;")
        lang_layout.addWidget(self._lang_label, alignment=Qt.AlignVCenter)
        lang_layout.addSpacing(16)
        self._lang_picker = SegmentedWidget(self)
        self._lang_picker.addItem(routeKey="en-US", text="English")
        self._lang_picker.addItem(routeKey="zh-CN", text="简体中文")
        self._lang_picker.addItem(routeKey="id-ID", text="Bahasa Indonesia")
        self._lang_picker.setCurrentItem(get_locale())
        self._lang_picker.currentItemChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self._lang_picker, alignment=Qt.AlignVCenter)
        lang_layout.addStretch(1)
        layout.addWidget(lang_card)
        layout.addSpacing(20)

        # --- 功能卡片 ---
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        self._card_cross = _InfoCard(
            FluentIcon.APPLICATION,
            t("home.cards.crossPlatform.title"),
            t("home.cards.crossPlatform.desc"),
            self,
        )
        row1.addWidget(self._card_cross)
        self._card_rich = _InfoCard(
            FluentIcon.DOCUMENT,
            t("home.cards.richText.title"),
            t("home.cards.richText.desc"),
            self,
        )
        row1.addWidget(self._card_rich)
        layout.addLayout(row1)
        layout.addSpacing(16)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        self._card_workflow = _InfoCard(
            FluentIcon.CHAT,
            t("home.cards.workflow.title"),
            t("home.cards.workflow.desc"),
            self,
        )
        row2.addWidget(self._card_workflow)
        self._card_open = _InfoCard(
            FluentIcon.SETTING,
            t("home.cards.open.title"),
            t("home.cards.open.desc"),
            self,
        )
        row2.addWidget(self._card_open)
        layout.addLayout(row2)

        layout.addStretch(1)
        QTimer.singleShot(0, self._check_latest_release_async)

    def _on_language_changed(self, route_key: str):
        """Apply the selected interface language and refresh static texts."""
        if not route_key:
            return
        set_locale(route_key)
        self._retranslate()

    def _retranslate(self):
        """Update all translatable labels on this page."""
        self._lang_label.setText(t("language.label"))
        self._subtitle_label.setText(t("home.subtitle"))
        self._website_button.setText(t("home.button.website"))
        self._version_label.setText(t("home.version.current", version=self._current_version or t("home.version.unknown")))
        self._update_label.setText(t("home.update.checking"))
        self._download_button.setText(t("home.button.downloadLatest"))
        self._status_label.setText(t("home.status.runningChecking"))
        self._card_cross.setTexts(t("home.cards.crossPlatform.title"), t("home.cards.crossPlatform.desc"))
        self._card_rich.setTexts(t("home.cards.richText.title"), t("home.cards.richText.desc"))
        self._card_workflow.setTexts(t("home.cards.workflow.title"), t("home.cards.workflow.desc"))
        self._card_open.setTexts(t("home.cards.open.title"), t("home.cards.open.desc"))

    def _open_url(self, url: str):
        webbrowser.open(url)

    def _check_latest_release_async(self):
        worker = threading.Thread(target=self._check_latest_release_worker, daemon=True)
        worker.start()

    def _check_latest_release_worker(self):
        result = {
            "ok": False,
            "latest_tag": "",
            "latest_url": self.GITHUB_URL,
            "error": "",
        }
        try:
            req = Request(
                self.GITHUB_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "WenCeAI-VersionChecker",
                },
            )
            with urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            result["latest_tag"] = str(payload.get("tag_name") or "").strip()
            result["latest_url"] = str(payload.get("html_url") or self.GITHUB_URL).strip()
            result["ok"] = bool(result["latest_tag"])
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            result["error"] = str(exc)
        self.updateCheckFinished.emit(result)

    def _on_update_check_finished(self, result: dict):
        latest_tag = str(result.get("latest_tag", "")).strip()
        if not result.get("ok"):
            self._update_label.setText(t("home.update.failed"))
            self._update_label.setTextColor(QColor("#d97706"), QColor("#d97706"))
            self._status_label.setText(t("home.status.runningNoUpdateInfo"))
            return

        local_key = _version_key(self._current_version)
        latest_key = _version_key(latest_tag)
        has_new_version = bool(latest_key) and (not local_key or latest_key > local_key)

        if has_new_version:
            self._status_label.setText(t("home.status.newVersion", tag=latest_tag))
            self._update_label.setText(t("home.update.new", tag=latest_tag))
            self._update_label.setTextColor(QColor("#d97706"), QColor("#d97706"))
            self._download_button.show()
            InfoBar.warning(
                title=t("home.infobar.newVersion.title"),
                content=t("home.infobar.newVersion.content", tag=latest_tag),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=5000,
            )
            return

        self._status_label.setText(t("home.status.runningLatest"))
        self._update_label.setText(t("home.update.latest"))
        self._update_label.setTextColor(QColor("#16a34a"), QColor("#16a34a"))
