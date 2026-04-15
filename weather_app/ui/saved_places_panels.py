from __future__ import annotations

import wx

from weather_app.domain.settings import Theme
from weather_app.services.storage import StorageRepo
from weather_app.ui.theme import get_palette
from weather_app.utils.formatters import format_d_m_hhmm


class ExpandRow(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        *,
        title: str,
        subtitle: str = "",
        theme: Theme,
        on_toggle=None,
    ):
        super().__init__(parent)

        self._expanded = False
        self._on_toggle = on_toggle
        self.palette = get_palette(theme)

        self.SetWindowStyle(wx.BORDER_NONE)

        root = wx.BoxSizer(wx.HORIZONTAL)

        self.btn = wx.Button(self, label="▶", style=wx.BORDER_NONE | wx.BU_LEFT)
        self.btn.SetMinSize((34, 34))

        text_col = wx.BoxSizer(wx.VERTICAL)

        self.title_lbl = wx.StaticText(self, label=title)
        title_font = self.title_lbl.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title_lbl.SetFont(title_font)

        self.subtitle_lbl = wx.StaticText(self, label=subtitle)
        sub_font = self.subtitle_lbl.GetFont()
        sub_font.SetPointSize(max(8, sub_font.GetPointSize() - 1))
        self.subtitle_lbl.SetFont(sub_font)

        text_col.Add(self.title_lbl, 0, wx.BOTTOM, 1)
        if subtitle:
            text_col.Add(self.subtitle_lbl, 0)

        root.Add(self.btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        root.Add(text_col, 1, wx.ALIGN_CENTER_VERTICAL)

        self.SetSizer(root)

        self.btn.Bind(wx.EVT_BUTTON, self._toggle)
        self.Bind(wx.EVT_LEFT_UP, self._toggle)
        self.title_lbl.Bind(wx.EVT_LEFT_UP, self._toggle)
        self.subtitle_lbl.Bind(wx.EVT_LEFT_UP, self._toggle)

        self.apply_theme(theme)

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.btn.SetLabel("▼" if expanded else "▶")
        self.Layout()
        self.Refresh()

    def _toggle(self, event=None) -> None:
        self.set_expanded(not self._expanded)
        if callable(self._on_toggle):
            self._on_toggle(self._expanded)

    def apply_theme(self, theme: Theme | None = None) -> None:
        if theme is not None:
            self.palette = get_palette(theme)

        p = self.palette
        self.SetBackgroundColour(p.dialog_bg)
        self.btn.SetBackgroundColour(p.dialog_bg)
        self.btn.SetForegroundColour(p.text_primary)
        self.title_lbl.SetForegroundColour(p.text_primary)
        self.subtitle_lbl.SetForegroundColour(p.hour_tile_text_muted)
        self.Refresh()


class _BaseSavedPanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        *,
        repo: StorageRepo,
        theme: Theme,
        on_load_city=None,
        on_changed=None,
    ):
        super().__init__(parent)

        self.repo = repo
        self.on_load_city = on_load_city
        self.on_changed = on_changed
        self.palette = get_palette(theme)
        self._selected_city: str | None = None

        self.root = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.root)

        self._build_ui()
        self.apply_theme(theme)

    def _build_ui(self) -> None:
        raise NotImplementedError

    def refresh_data(self) -> None:
        raise NotImplementedError

    def _notify_changed(self) -> None:
        if callable(self.on_changed):
            self.on_changed()

    def _do_load(self) -> None:
        if self._selected_city and callable(self.on_load_city):
            self.on_load_city(self._selected_city)

    def apply_theme(self, theme: Theme | None = None) -> None:
        if theme is not None:
            self.palette = get_palette(theme)

        self.SetBackgroundColour(self.palette.dialog_bg)
        self.Refresh()


class FavoritesPanel(_BaseSavedPanel):
    def __init__(
        self,
        parent: wx.Window,
        *,
        repo: StorageRepo,
        theme: Theme,
        on_load_city=None,
        on_changed=None,
    ):
        self._rows = []
        super().__init__(
            parent,
            repo=repo,
            theme=theme,
            on_load_city=on_load_city,
            on_changed=on_changed,
        )
        self.refresh_data()

    def _build_ui(self) -> None:
        self.list_box = wx.ListBox(self, choices=[])
        self.list_box.SetMinSize((-1, 220))

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_load = wx.Button(self, label="Load")
        self.btn_remove = wx.Button(self, label="Remove")
        self.btn_clear = wx.Button(self, label="Clear all")

        btns.Add(self.btn_load, 0)
        btns.AddSpacer(8)
        btns.Add(self.btn_remove, 0)
        btns.AddSpacer(8)
        btns.Add(self.btn_clear, 0)
        btns.AddStretchSpacer(1)

        self.root.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 8)
        self.root.Add(btns, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.list_box.Bind(wx.EVT_LISTBOX, self._on_select)
        self.list_box.Bind(wx.EVT_LISTBOX_DCLICK, self._on_load)

        self.btn_load.Bind(wx.EVT_BUTTON, self._on_load)
        self.btn_remove.Bind(wx.EVT_BUTTON, self._on_remove)
        self.btn_clear.Bind(wx.EVT_BUTTON, self._on_clear)

        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def refresh_data(self) -> None:
        self._rows = self.repo.list_favorites()
        self.list_box.Set([row.city for row in self._rows])
        self._selected_city = None
        self.list_box.SetSelection(wx.NOT_FOUND)
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_sel = self.list_box.GetSelection() != wx.NOT_FOUND
        self.btn_load.Enable(has_sel)
        self.btn_remove.Enable(has_sel)
        self.btn_clear.Enable(bool(self._rows))

    def _on_select(self, event=None) -> None:
        idx = self.list_box.GetSelection()
        self._selected_city = self.list_box.GetString(idx) if idx != wx.NOT_FOUND else None
        self._update_buttons()

    def _on_load(self, event=None) -> None:
        self._do_load()

    def _on_remove(self, event=None) -> None:
        idx = self.list_box.GetSelection()
        if idx == wx.NOT_FOUND:
            return

        city = self.list_box.GetString(idx)
        self.repo.remove_favorite(city)
        self.refresh_data()
        self._notify_changed()

    def _on_clear(self, event=None) -> None:
        res = wx.MessageBox(
            "Clear ALL favorites?",
            "Confirm clear",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            parent=self,
        )
        if res != wx.YES:
            return

        self.repo.clear_favorites()
        self.refresh_data()
        self._notify_changed()

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and self._selected_city:
            self._do_load()
            return
        if key == wx.WXK_DELETE and self.list_box.GetSelection() != wx.NOT_FOUND:
            self._on_remove()
            return
        event.Skip()

    def apply_theme(self, theme: Theme | None = None) -> None:
        super().apply_theme(theme)
        p = self.palette
        self.list_box.SetBackgroundColour(p.input_bg)
        self.list_box.SetForegroundColour(p.input_text)


class HistoryPanel(_BaseSavedPanel):
    def __init__(
        self,
        parent: wx.Window,
        *,
        repo: StorageRepo,
        theme: Theme,
        on_load_city=None,
        on_changed=None,
    ):
        self._rows = []
        super().__init__(
            parent,
            repo=repo,
            theme=theme,
            on_load_city=on_load_city,
            on_changed=on_changed,
        )
        self.refresh_data()

    def _build_ui(self) -> None:
        self.list_ctrl = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self.list_ctrl.InsertColumn(0, "City", width=270)
        self.list_ctrl.InsertColumn(1, "Searched At", width=190)
        self.list_ctrl.SetMinSize((-1, 260))

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_load = wx.Button(self, label="Load")
        self.btn_remove = wx.Button(self, label="Remove")
        self.btn_clear = wx.Button(self, label="Clear history")

        btns.Add(self.btn_load, 0)
        btns.AddSpacer(8)
        btns.Add(self.btn_remove, 0)
        btns.AddSpacer(8)
        btns.Add(self.btn_clear, 0)
        btns.AddStretchSpacer(1)

        self.root.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 8)
        self.root.Add(btns, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_select)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_load)

        self.btn_load.Bind(wx.EVT_BUTTON, self._on_load)
        self.btn_remove.Bind(wx.EVT_BUTTON, self._on_remove)
        self.btn_clear.Bind(wx.EVT_BUTTON, self._on_clear)

        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def refresh_data(self) -> None:
        self._rows = self.repo.list_history(limit=20)
        self.list_ctrl.DeleteAllItems()

        for i, row in enumerate(self._rows):
            idx = self.list_ctrl.InsertItem(i, row.city)
            self.list_ctrl.SetItem(idx, 1, format_d_m_hhmm(row.searched_at))

        self._selected_city = None
        self._clear_selection()
        self._update_buttons()

    def _clear_selection(self) -> None:
        i = self.list_ctrl.GetFirstSelected()
        while i != -1:
            self.list_ctrl.Select(i, on=0)
            i = self.list_ctrl.GetFirstSelected()

    def _update_buttons(self) -> None:
        has_sel = self.list_ctrl.GetFirstSelected() != -1
        self.btn_load.Enable(has_sel)
        self.btn_remove.Enable(has_sel)
        self.btn_clear.Enable(bool(self._rows))

    def _on_select(self, event: wx.ListEvent) -> None:
        idx = event.GetIndex()
        self._selected_city = self._rows[idx].city if idx != -1 else None
        self._update_buttons()

    def _on_load(self, event=None) -> None:
        self._do_load()

    def _on_remove(self, event=None) -> None:
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1:
            return

        row = self._rows[idx]
        self.repo.remove_history(row.id)
        self.refresh_data()

    def _on_clear(self, event=None) -> None:
        res = wx.MessageBox(
            "Clear ALL search history?",
            "Confirm clear",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            parent=self,
        )
        if res != wx.YES:
            return

        self.repo.clear_history()
        self.refresh_data()

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and self._selected_city:
            self._do_load()
            return
        if key == wx.WXK_DELETE and self.list_ctrl.GetFirstSelected() != -1:
            self._on_remove()
            return
        event.Skip()

    def apply_theme(self, theme: Theme | None = None) -> None:
        super().apply_theme(theme)
        p = self.palette
        self.list_ctrl.SetBackgroundColour(p.input_bg)
        self.list_ctrl.SetForegroundColour(p.input_text)