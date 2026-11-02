"""User-customizable shortcuts: registry, persistence, matching, apply."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent


def _press(key, modifiers=Qt.KeyboardModifier.NoModifier, auto=False):
    from PySide6.QtCore import QEvent

    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers, "", auto)


def test_registry_unique_and_parsable(qt_app):
    from app import shortcuts as S

    ids = S.action_ids()
    assert len(ids) == len(set(ids)) > 10
    from PySide6.QtGui import QKeySequence

    for aid in ids:
        default = S.default_keys(aid)
        if default:
            seq = QKeySequence(default)
            assert not seq.isEmpty() and seq.count() == 1, aid


def test_labels_cover_actions(qt_app):
    from app import shortcuts as S

    for aid in S.action_ids():
        assert S.action_label(aid) and S.action_label(aid) != aid


def test_roundtrip_and_validation(tmp_path):
    from app import shortcuts as S

    assert S.load_custom(tmp_path) == {}
    assert S.save_custom({"file_open": "Ctrl+Shift+O",
                          "nope": "Ctrl+X",
                          "edit_undo": "not a shortcut!!!"}, tmp_path)
    back = S.load_custom(tmp_path)
    assert back == {"file_open": "Ctrl+Shift+O"}
    # Invalid files and payloads fall back to {}.
    (tmp_path / "shortcuts.json").write_text("{oops", encoding="utf-8")
    assert S.load_custom(tmp_path) == {}
    (tmp_path / "shortcuts.json").write_text("[1,2]", encoding="utf-8")
    assert S.load_custom(tmp_path) == {}
    # Explicit unbind ("") beats the default.
    S.save_custom({"file_open": ""}, tmp_path)
    assert S.load_custom(tmp_path) == {"file_open": ""}
    assert S.effective_keys("file_open", {"file_open": ""}) == ""
    S.reset_custom(tmp_path)
    assert S.load_custom(tmp_path) == {}


def test_conflicts():
    from app import shortcuts as S

    assert S.find_conflicts({}) == {}
    dupes = S.find_conflicts({"file_open": "Ctrl+S", "file_quick_export": "Ctrl+S"})
    assert set(dupes) == {"Ctrl+S"}
    assert sorted(dupes["Ctrl+S"]) == ["file_open", "file_quick_export"]


def test_event_matches():
    from app import shortcuts as S

    assert S.event_matches(_press(Qt.Key_Space), "Space")
    assert not S.event_matches(_press(Qt.Key_Space), "Ctrl+Space")
    assert S.event_matches(_press(Qt.Key_O, Qt.ControlModifier), "Ctrl+O")
    assert not S.event_matches(_press(Qt.Key_O), "Ctrl+O")
    assert not S.event_matches(_press(Qt.Key_O, Qt.ControlModifier), "Ctrl+P")
    assert not S.event_matches(_press(Qt.Key_O, Qt.ControlModifier, auto=True), "Ctrl+O")
    assert not S.event_matches(_press(Qt.Key_O), "")
    assert not S.event_matches(_press(Qt.Key_O), "nope")
    assert S.event_matches(_press(Qt.Key_Left, Qt.AltModifier), "Alt+Left")


def test_event_to_text_roundtrip():
    from app import shortcuts as S

    assert S.event_to_text(_press(Qt.Key_E, Qt.ControlModifier)) == "Ctrl+E"
    assert S.event_to_text(_press(Qt.Key_Space)) == "Space"
    assert S.event_to_text(_press(Qt.Key_E, Qt.ControlModifier, auto=True)) == ""


def test_apply_shortcuts_stub(qt_app):
    from types import SimpleNamespace

    from app import shortcuts as S

    seen = {}

    class Fake:
        def setShortcut(self, keys):
            seen["keys"] = keys

    win = SimpleNamespace(_shortcut_actions={"file_open": [Fake()]},
                          _shortcuts_custom={"file_open": "Ctrl+Shift+O"})
    S.apply_shortcuts(win)
    assert seen["keys"] == "Ctrl+Shift+O"
    S.apply_shortcuts(win, {"file_open": "Ctrl+Alt+O"})
    assert seen["keys"] == "Ctrl+Alt+O"
    assert win._shortcuts_custom == {"file_open": "Ctrl+Alt+O"}
    S.apply_shortcuts(win, {"file_open": ""})
    assert seen["keys"] == ""


def test_shortcut_editor_assign_and_reset(window, qt_app):
    from app import shortcuts as S
    from app.ui import shortcuts_dialog as D

    dlg = D.build_shortcuts_dialog(window)
    assert dlg is not None
    ok, msg = D.assign_binding(window, "file_open", "Ctrl+Shift+O")
    assert ok, msg
    assert S.effective_for(window, "file_open") == "Ctrl+Shift+O"
    ok, msg = D.assign_binding(window, "edit_undo", "Ctrl+Shift+O")
    assert not ok and "already used" in msg
    assert S.effective_for(window, "edit_undo") == "Ctrl+Z"
    ok, msg = D.assign_binding(window, "file_open", "not a shortcut!!!")
    assert not ok
    ok, msg = D.assign_binding(window, "file_open", "")
    assert ok and S.effective_for(window, "file_open") == ""
    S.reset_custom()
    window._shortcuts_custom = {}
    S.apply_shortcuts(window)
    assert S.effective_for(window, "file_open") == "Ctrl+O"
    dlg.deleteLater()


def test_compare_key_follows_registry(window):
    from PIL import Image

    from app import shortcuts as S

    window.src = Image.new("RGB", (16, 16))
    ev = _press(Qt.Key_Space)
    window.keyPressEvent(ev)
    assert window._comparing is True
    window.keyReleaseEvent(_press(Qt.Key_Space))
    assert window._comparing is False
    # Rebind compare to H: space stops working, H works.
    window._shortcuts_custom = {"view_compare_hold": "H"}
    S.apply_shortcuts(window)
    window.keyPressEvent(_press(Qt.Key_Space))
    assert window._comparing is False
    window.keyPressEvent(_press(Qt.Key_H))
    assert window._comparing is True
    window.keyReleaseEvent(_press(Qt.Key_H))
    assert window._comparing is False
    window._shortcuts_custom = {}
    S.apply_shortcuts(window)
