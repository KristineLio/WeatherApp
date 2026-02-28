# weather_app/ui/favorites_dialog.py
from __future__ import annotations

import datetime as dt
import wx

from weather_app.services.storage import StorageRepo
from weather_app.utils.formatters import format_d_m_hhmm


class FavoritesDialog(wx.Dialog):
    """
    Simple modal dialog with:
      - Favorites list (click -> load)
      - History list (last 20) (click -> load)  [ListCtrl w/ City + Time columns]
    """

    def __init__(self, parent: wx.Window, repo: StorageRepo, on_changed=None):
        super().__init__(
            parent,
            title="Favorites & History",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.repo = repo
        self.on_changed = on_changed
        self._selected_city: str | None = None

        # keep row objects so we can delete history by id (cities can repeat)
        self._fav_rows = []
        self._hist_rows = []

        root = wx.BoxSizer(wx.VERTICAL)

        # --- Favorites ---
        fav_box = wx.StaticBoxSizer(wx.StaticBox(self, label="⭐ Favorites"), wx.VERTICAL)
        self.fav_list = wx.ListBox(self, choices=[])
        fav_box.Add(self.fav_list, 1, wx.EXPAND | wx.ALL, 8)

        fav_btns = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_remove_fav = wx.Button(self, label="Remove")
        fav_btns.Add(self.btn_remove_fav, 0)
        fav_btns.AddSpacer(8)

        self.btn_clear_fav = wx.Button(self, label="Clear")
        fav_btns.Add(self.btn_clear_fav, 0)

        fav_btns.AddStretchSpacer(1)
        fav_box.Add(fav_btns, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # --- History (ListCtrl) ---
        hist_box = wx.StaticBoxSizer(wx.StaticBox(self, label="🕘 Search history (last 20)"), wx.VERTICAL)

        self.hist_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self.hist_list.InsertColumn(0, "City", width=220)
        self.hist_list.InsertColumn(1, "Searched At", width=150)

        hist_box.Add(self.hist_list, 1, wx.EXPAND | wx.ALL, 8)

        hist_btns = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_remove_hist = wx.Button(self, label="Remove")
        hist_btns.Add(self.btn_remove_hist, 0)
        hist_btns.AddSpacer(8)

        self.btn_clear_hist = wx.Button(self, label="Clear history")
        hist_btns.Add(self.btn_clear_hist, 0)

        hist_btns.AddStretchSpacer(1)
        hist_box.Add(hist_btns, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # --- bottom buttons ---
        bottom = wx.StdDialogButtonSizer()
        self.btn_load = wx.Button(self, wx.ID_OK, label="Load")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL)
        bottom.AddButton(self.btn_load)
        bottom.AddButton(self.btn_cancel)
        bottom.Realize()

        root.Add(fav_box, 1, wx.EXPAND | wx.ALL, 10)
        root.Add(hist_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        root.Add(bottom, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(root)
        self.SetMinSize((420, 520))
        self.SetInitialSize((480, 580))

        # Make Enter trigger Load
        self.btn_load.SetDefault()
        self.SetAffirmativeId(wx.ID_OK)

        # -----------------
        # bindings
        # -----------------
        # favorites
        self.fav_list.Bind(wx.EVT_LISTBOX, self._on_select_fav)
        self.fav_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_dclick_load)

        # history (ListCtrl)
        self.hist_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_select_hist)
        self.hist_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_dclick_load)  # double-click / Enter on row

        # buttons
        self.btn_remove_fav.Bind(wx.EVT_BUTTON, self._on_remove_fav)
        self.btn_clear_fav.Bind(wx.EVT_BUTTON, self._on_clear_favorites)
        self.btn_remove_hist.Bind(wx.EVT_BUTTON, self._on_remove_hist)
        self.btn_clear_hist.Bind(wx.EVT_BUTTON, self._on_clear_history)

        # Optional: Enter/Delete handling even when focus is inside the list
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        # Right-click context menus
        self.fav_list.Bind(wx.EVT_CONTEXT_MENU, self._on_fav_context_menu)
        self.hist_list.Bind(wx.EVT_CONTEXT_MENU, self._on_hist_context_menu)
        # Windows fallback
        self.fav_list.Bind(wx.EVT_RIGHT_UP, self._on_fav_context_menu)
        self.hist_list.Bind(wx.EVT_RIGHT_UP, self._on_hist_context_menu)

        self._refresh_lists()
        self._update_buttons()

    # -----------------
    # Helpers
    # -----------------
    def _clear_hist_selection(self) -> None:
        """Unselect any selected row in the ListCtrl."""
        i = self.hist_list.GetFirstSelected()
        while i != -1:
            self.hist_list.Select(i, on=0)
            i = self.hist_list.GetFirstSelected()

    def _sync_selected_city_from_hist(self) -> None:
        idx = self.hist_list.GetFirstSelected()
        self._selected_city = self._hist_rows[idx].city if idx != -1 else None

    def _do_load(self) -> None:
        if self._selected_city:
            self.EndModal(wx.ID_OK)

    def _refresh_lists(self) -> None:
        self._fav_rows = self.repo.list_favorites()
        self._hist_rows = self.repo.list_history(limit=20)

        # favorites listbox
        self.fav_list.Set([f.city for f in self._fav_rows])

        # history listctrl
        self.hist_list.DeleteAllItems()
        for i, h in enumerate(self._hist_rows):
            row_idx = self.hist_list.InsertItem(i, h.city)
            self.hist_list.SetItem(row_idx, 1, format_d_m_hhmm(h.searched_at))

    def _update_buttons(self) -> None:
        fav_sel = (self.fav_list.GetSelection() != wx.NOT_FOUND)
        hist_sel = (self.hist_list.GetFirstSelected() != -1)

        self.btn_load.Enable(bool(self._selected_city))
        self.btn_remove_fav.Enable(fav_sel)
        self.btn_remove_hist.Enable(hist_sel)
        self.btn_clear_hist.Enable(True)
        self.btn_clear_fav.Enable(bool(self._fav_rows))

    # -----------------
    # Selection handlers
    # -----------------
    def _on_select_fav(self, event: wx.CommandEvent | None) -> None:
        idx = self.fav_list.GetSelection()
        self._selected_city = self.fav_list.GetString(idx) if idx != wx.NOT_FOUND else None
        self._clear_hist_selection()
        self._update_buttons()

    def _on_select_hist(self, event: wx.ListEvent) -> None:
        idx = event.GetIndex()
        self._selected_city = self._hist_rows[idx].city if idx != -1 else None
        self.fav_list.SetSelection(wx.NOT_FOUND)
        self._update_buttons()

    # -----------------
    # Load / keyboard
    # -----------------
    def _on_dclick_load(self, event) -> None:
        self._do_load()

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()

        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if self._selected_city:
                self.EndModal(wx.ID_OK)
                return

        if key == wx.WXK_DELETE:
            # Delete selected history row if any
            if self.hist_list.GetFirstSelected() != -1:
                self._on_remove_hist(None)
                return

        event.Skip()

    # -----------------
    # Favorites actions
    # -----------------
    def _on_remove_fav(self, event: wx.CommandEvent) -> None:
        idx = self.fav_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return

        city = self.fav_list.GetString(idx)
        self.repo.remove_favorite(city)

        self._selected_city = None
        self.fav_list.SetSelection(wx.NOT_FOUND)

        self._refresh_lists()
        if self.on_changed:
            self.on_changed()
        self._update_buttons()

    def _on_clear_favorites(self, event: wx.CommandEvent) -> None:
        res = wx.MessageBox(
            "Clear ALL favorites?",
            "Confirm clear",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            parent=self,
        )
        if res != wx.YES:
            return

        self.repo.clear_favorites()

        self._selected_city = None
        self.fav_list.SetSelection(wx.NOT_FOUND)

        self._refresh_lists()
        self._update_buttons()

        if self.on_changed:
            self.on_changed()

    # -----------------
    # History actions
    # -----------------
    def _on_remove_hist(self, event: wx.CommandEvent | None) -> None:
        idx = self.hist_list.GetFirstSelected()
        if idx == -1:
            return

        row = self._hist_rows[idx]
        self.repo.remove_history(row.id)

        self._selected_city = None
        self._clear_hist_selection()

        self._refresh_lists()
        self._update_buttons()

    def _on_clear_history(self, event: wx.CommandEvent) -> None:
        res = wx.MessageBox(
            "Clear ALL search history?",
            "Confirm clear",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            parent=self,
        )
        if res != wx.YES:
            return

        self.repo.clear_history()

        self._selected_city = None
        self._clear_hist_selection()

        self._refresh_lists()
        self._update_buttons()

    # -----------------
    # Context menus
    # -----------------
    def _select_item_from_context(self, lst, event) -> None:
        pos = event.GetPosition()

        if isinstance(pos, wx.Point):
            if lst.GetScreenRect().Contains(pos):
                pos = lst.ScreenToClient(pos)

        if isinstance(lst, wx.ListCtrl):
            item, _ = lst.HitTest(pos)
            if item != wx.NOT_FOUND:
                lst.Select(item)
        else:
            try:
                idx = lst.HitTest(pos)
                if idx != wx.NOT_FOUND:
                    lst.SetSelection(idx)
            except Exception:
                pass

    def _on_fav_context_menu(self, event) -> None:
        self._select_item_from_context(self.fav_list, event)
        self._on_select_fav(None)

        menu = wx.Menu()
        m_load = menu.Append(wx.ID_ANY, "Load")
        m_remove = menu.Append(wx.ID_ANY, "Remove")
        menu.AppendSeparator()
        m_clear = menu.Append(wx.ID_ANY, "Clear all favorites…")

        has_sel = self.fav_list.GetSelection() != wx.NOT_FOUND
        m_load.Enable(has_sel)
        m_remove.Enable(has_sel)
        m_clear.Enable(bool(self._fav_rows))

        self.Bind(wx.EVT_MENU, lambda e: self._do_load(), m_load)
        self.Bind(wx.EVT_MENU, self._on_remove_fav, m_remove)
        self.Bind(wx.EVT_MENU, self._on_clear_favorites, m_clear)

        self.PopupMenu(menu)
        menu.Destroy()

    def _on_hist_context_menu(self, event) -> None:
        self._select_item_from_context(self.hist_list, event)

        # sync selected city from ListCtrl selection (don't call _on_select_hist(None))
        self._sync_selected_city_from_hist()
        self.fav_list.SetSelection(wx.NOT_FOUND)
        self._update_buttons()

        menu = wx.Menu()
        m_load = menu.Append(wx.ID_ANY, "Load")
        m_remove = menu.Append(wx.ID_ANY, "Remove")
        menu.AppendSeparator()
        m_clear = menu.Append(wx.ID_ANY, "Clear all history…")

        has_sel = self.hist_list.GetFirstSelected() != -1
        m_load.Enable(has_sel)
        m_remove.Enable(has_sel)
        m_clear.Enable(bool(self._hist_rows))

        self.Bind(wx.EVT_MENU, lambda e: self._do_load(), m_load)
        self.Bind(wx.EVT_MENU, self._on_remove_hist, m_remove)
        self.Bind(wx.EVT_MENU, self._on_clear_history, m_clear)

        self.PopupMenu(menu)
        menu.Destroy()

    # -----------------
    # Public API
    # -----------------
    def get_selected_city(self) -> str | None:
        return self._selected_city