"""GUI i18n — en-US / zh-CN / id-ID / ja-JP / ko-KR / vi-VN with persistence via user_settings.json + QSettings."""

from __future__ import annotations

import json
import locale as py_locale
from pathlib import Path

from PySide6.QtCore import QObject, Signal

SUPPORTED = ("en-US", "zh-CN", "id-ID", "ja-JP", "ko-KR", "vi-VN")
DEFAULT = "en-US"
STORAGE_KEY = "wence/interface-language"

# Import locale dicts (Python modules, PyInstaller-safe)
try:
    from gui.locales.en_US import STRINGS as EN_US
except ImportError:
    EN_US = {}
try:
    from gui.locales.zh_CN import STRINGS as ZH_CN
except ImportError:
    ZH_CN = {}
try:
    from gui.locales.id_ID import STRINGS as ID_ID
except ImportError:
    ID_ID = {}
try:
    from gui.locales.ja_JP import STRINGS as JA_JP
except ImportError:
    JA_JP = {}
try:
    from gui.locales.ko_KR import STRINGS as KO_KR
except ImportError:
    KO_KR = {}
try:
    from gui.locales.vi_VN import STRINGS as VI_VN
except ImportError:
    VI_VN = {}
MESSAGES = {
    "en-US": EN_US,
    "zh-CN": ZH_CN,
    "id-ID": ID_ID,
    "ja-JP": JA_JP,
    "ko-KR": KO_KR,
    "vi-VN": VI_VN,
}


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT
    v = str(value).strip().lower()
    if v in ("en-us", "en"):
        return "en-US"
    if v.startswith("en"):
        return "en-US"
    if v in ("id-id", "id"):
        return "id-ID"
    if v.startswith("id"):
        return "id-ID"
    if v in ("zh-cn", "zh", "zh_cn"):
        return "zh-CN"
    if v.startswith("zh"):
        return "zh-CN"
    if v in ("ja-jp", "ja", "ja_jp"):
        return "ja-JP"
    if v.startswith("ja"):
        return "ja-JP"
    if v in ("ko-kr", "ko", "ko_kr"):
        return "ko-KR"
    if v.startswith("ko"):
        return "ko-KR"
    if v in ("vi-vn", "vi", "vi_vn"):
        return "vi-VN"
    if v.startswith("vi"):
        return "vi-VN"
    return DEFAULT


def _read_from_user_settings() -> str | None:
    try:
        from app.core.config import get_user_settings_file

        p = get_user_settings_file()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            lang = data.get("language")
            if lang:
                return normalize_locale(lang)
    except Exception:
        pass
    return None


def _write_to_user_settings(locale: str) -> None:
    try:
        from app.core.config import get_user_settings_file

        p = get_user_settings_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["language"] = locale
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _read_from_qsettings() -> str | None:
    try:
        from PySide6.QtCore import QSettings

        s = QSettings("WenCeAI", "WenCeAI")
        v = s.value(STORAGE_KEY, "")
        if v:
            return normalize_locale(str(v))
    except Exception:
        pass
    return None


def _write_to_qsettings(locale: str) -> None:
    try:
        from PySide6.QtCore import QSettings

        s = QSettings("WenCeAI", "WenCeAI")
        s.setValue(STORAGE_KEY, locale)
    except Exception:
        pass


def _detect_system_locale() -> str:
    # Try Qt locale first if QApplication exists
    try:
        from PySide6.QtCore import QLocale

        qloc = QLocale.system().name()  # e.g. "en_US", "zh_CN", "id_ID"
        qloc = qloc.replace("_", "-")
        norm = normalize_locale(qloc)
        # Only trust supported-locale detection; otherwise default to en-US
        if qloc.lower().startswith("zh"):
            return "zh-CN"
        if qloc.lower().startswith("id"):
            return "id-ID"
        if qloc.lower().startswith("ja"):
            return "ja-JP"
        if qloc.lower().startswith("ko"):
            return "ko-KR"
        if qloc.lower().startswith("vi"):
            return "vi-VN"
    except Exception:
        pass
    try:
        loc, _ = py_locale.getdefaultlocale()
        if loc:
            loc = loc.replace("_", "-")
            if loc.lower().startswith("zh"):
                return "zh-CN"
            if loc.lower().startswith("id"):
                return "id-ID"
            if loc.lower().startswith("ja"):
                return "ja-JP"
            if loc.lower().startswith("ko"):
                return "ko-KR"
            if loc.lower().startswith("vi"):
                return "vi-VN"
    except Exception:
        pass
    return DEFAULT


class _I18nBus(QObject):
    localeChanged = Signal(str)


_bus = _I18nBus()
_current: str = DEFAULT
_initialized = False


def _init() -> None:
    global _current, _initialized
    if _initialized:
        return
    _initialized = True
    # Priority: QSettings > user_settings.json > system > default
    for getter in (_read_from_qsettings, _read_from_user_settings, _detect_system_locale):
        try:
            v = getter()
            if v and v in SUPPORTED:
                _current = v
                return
        except Exception:
            continue
    _current = DEFAULT


def get_locale() -> str:
    _init()
    return _current


def set_locale(value: str) -> str:
    _init()
    global _current
    nxt = normalize_locale(value)
    if nxt not in SUPPORTED:
        nxt = DEFAULT
    if nxt == _current:
        return _current
    _current = nxt
    _write_to_qsettings(nxt)
    _write_to_user_settings(nxt)
    try:
        _bus.localeChanged.emit(nxt)
    except Exception:
        pass
    return _current


def set_locale_silent(value: str) -> str:
    """Set without emitting signal (for init)."""
    global _current
    nxt = normalize_locale(value)
    if nxt not in SUPPORTED:
        nxt = DEFAULT
    _current = nxt
    return _current


def subscribe_locale_changed(callback) -> None:
    try:
        _bus.localeChanged.connect(callback)
    except Exception:
        pass


def unsubscribe_locale_changed(callback) -> None:
    try:
        _bus.localeChanged.disconnect(callback)
    except Exception:
        pass


def _resolve(messages: dict, key: str):
    cur = messages
    for part in key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def t(key: str, **params) -> str:
    _init()
    # Try current locale, fallback to en-US, then key
    for loc in (_current, DEFAULT, "zh-CN"):
        msgs = MESSAGES.get(loc, {})
        val = _resolve(msgs, key)
        if val is not None:
            s = str(val)
            if params:
                for k, v in params.items():
                    s = s.replace(f"{{{k}}}", str(v))
            return s
    # Fallback: return key
    s = str(key)
    if params:
        for k, v in params.items():
            s = s.replace(f"{{{k}}}", str(v))
    return s


def get_bus() -> _I18nBus:
    return _bus
