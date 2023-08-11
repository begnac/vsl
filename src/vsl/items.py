# coding: utf-8
#
# Very Simple Launcher
#
# Copyright (C) Itaï BEN YAACOV
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gtk


class ScoredItem(GObject.Object):
    def __init__(self, item, score=0.0):
        super().__init__()
        self.item = item
        self.score = score

    def copy_change_score(self, delta):
        return ScoredItem(self.item, self.score + delta)


class ItemBase:
    def __init__(self, *, name, detail, title=None, icon=None):
        self.name = name
        self.detail = detail
        self.title = title or "{name}"
        self.icon = icon

    def activate(self):
        raise NotImplementedError

    def format_title(self):
        return self.title.format_map(vars(self))

    def __repr__(self):
        return f'Item({self.format_title()})'


class ItemChangeRequest(ItemBase):
    "Special item type, will not need to activate."
    def __init__(self, *, pattern, repl, **kwargs):
        super().__init__(**kwargs)
        self.pattern = pattern
        self.repl = repl


class ItemNoop(ItemBase):
    def activate(self):
        pass


class ItemUri(ItemBase):
    def activate(self):
        Gtk.UriLauncher(uri=self.detail).launch(Gio.Application.get_default().get_active_window(), None, lambda launcher, result: launcher.launch_finish(result))


class ItemFile(ItemBase):
    def activate(self):
        Gtk.FileLauncher(file=Gio.File.new_for_path(self.detail)).launch(Gio.Application.get_default().get_active_window(), None, lambda launcher, result: launcher.launch_finish(result))


class ItemFolder(ItemBase):
    def activate(self):
        Gtk.FileLauncher(file=Gio.File.new_for_path(self.detail)).open_containing_folder(Gio.Application.get_default().get_active_window(), None, lambda launcher, result: launcher.open_containing_folder_finish(result))


class ItemAction(ItemBase):
    def activate(self):
        Gio.Application.get_default().activate_action(self.detail)
