"""Language changes preserve the startup update check and its result."""

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gui import i18n
from gui.views import home_interface


@pytest.fixture
def home(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(i18n, "_initialized", True)
    monkeypatch.setattr(i18n, "_current", "en-US")
    monkeypatch.setattr(i18n, "_write_to_user_settings", lambda _: None)
    monkeypatch.setattr(i18n, "_write_to_qsettings", lambda _: None)
    monkeypatch.setattr(home_interface, "_read_local_version", lambda: "v1.0.0")
    start_check = Mock()
    notification = Mock()
    monkeypatch.setattr(home_interface.HomeInterface, "_check_latest_release_async", start_check)
    monkeypatch.setattr(home_interface.InfoBar, "warning", notification)
    widget = home_interface.HomeInterface()
    app.processEvents()
    start_check.assert_called_once_with()
    yield widget, app, start_check, notification
    widget.close()
    widget.deleteLater()
    app.processEvents()


@pytest.mark.parametrize(
    "result, status_key, update_key, download_visible, notification_count",
    [
        (None, "runningChecking", "checking", False, 0),
        ({"ok": False}, "runningNoUpdateInfo", "failed", False, 0),
        ({"ok": True, "latest_tag": "v1.0.0"}, "runningLatest", "latest", False, 0),
        ({"ok": True, "latest_tag": "v1.1.0"}, "newVersion", "new", True, 1),
    ],
)
def test_language_switch_preserves_update_status(
    home, result, status_key, update_key, download_visible, notification_count
):
    widget, app, start_check, notification = home
    if result is not None:
        widget.updateCheckFinished.emit(result)
    for index in [1, 2, 3, 4, 5, 0]:
        widget._lang_picker.setCurrentIndex(index)
        app.processEvents()
        tag = (result or {}).get("latest_tag", "")
        assert i18n.get_locale() == widget._lang_items[index][0]
        assert widget._status_label.text() == i18n.t(f"home.status.{status_key}", tag=tag)
        assert widget._update_label.text() == i18n.t(f"home.update.{update_key}", tag=tag)
        assert (not widget._download_button.isHidden()) == download_visible
        assert notification.call_count == notification_count
        start_check.assert_called_once_with()


def test_pending_check_finishes_in_selected_language(home):
    widget, app, start_check, notification = home
    widget._lang_picker.setCurrentIndex(1)
    app.processEvents()
    assert widget._update_label.text() == i18n.t("home.update.checking")

    widget.updateCheckFinished.emit({"ok": True, "latest_tag": "v1.1.0"})
    assert widget._status_label.text() == i18n.t("home.status.newVersion", tag="v1.1.0")
    assert widget._update_label.text() == i18n.t("home.update.new", tag="v1.1.0")
    assert not widget._download_button.isHidden()
    notification.assert_called_once()
    assert notification.call_args.kwargs["title"] == i18n.t("home.infobar.newVersion.title")
    start_check.assert_called_once_with()
