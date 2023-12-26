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


from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gtk

import os
import difflib
import subprocess

from . import logger


class ScoredItem(GObject.Object):
    def __init__(self, item, score=0.0):
        super().__init__()
        self.item = item
        self.score = score

    def apply_delta(self, delta):
        return ScoredItem(self.item, self.score + delta)

    def apply_request(self, request):
        return self.apply_delta(self.item.score(request))

    def __repr__(self):
        return f'{self.item} ({self.score})'


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

    @staticmethod
    def _score(request, something):
        if not request or not something:
            return 0.0
        opcodes = difflib.SequenceMatcher(None, request, something).get_opcodes()
        n1 = [i2 - i1 for opcode, i1, i2, j1, j2 in opcodes if opcode in ('replace', 'delete')]
        n2 = [j2 - j1 for opcode, i1, i2, j1, j2 in opcodes if opcode in ('replace', 'insert')]
        score = 1.2
        score -= 2 * sum(n1) / len(request) + len(n1) / 10
        score -= sum(n2) / len(something) / len(request) + len(n2) / 20
        return score

    def score(self, request):
        return max(self._score(request.lower(), self.name.lower()), self._score(request.lower(), self.detail.lower()) - 0.05)

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

    def score(self, request):
        return 0.2


class ItemDesktop(ItemBase):
    def activate(self):
        Gio.DesktopAppInfo.new_from_filename(self.detail).launch()

    def score(self, request):
        return super().score(request) + 0.1


class ItemLauncher(ItemBase):
    @staticmethod
    def async_callback(launcher, result):
        try:
            launcher.launch_finish(result)
        except GLib.GError as error:
            logger.error(error.message)


class ItemUri(ItemLauncher):
    def activate(self):
        Gtk.UriLauncher(uri=self.detail).launch(None, None, self.async_callback)


class ItemFolder(ItemLauncher):
    def __init__(self, path):
        super().__init__(name=os.path.basename(path) + '/', detail=path, icon='folder')

    def activate(self):
        Gtk.FileLauncher(file=Gio.File.new_for_path(self.detail)).launch(None, None, self.async_callback)


class ItemFile(ItemBase):
    def __init__(self, path):
        self.content_type, self.content_type_certain = Gio.content_type_guess(path)
        if self.content_type is not None:
            icon = Gio.content_type_get_icon(self.content_type)
            title = _("{{name}} [{description}]").format(description=Gio.content_type_get_description(self.content_type))
        else:
            icon = None
            title = None
        super().__init__(name=os.path.basename(path), detail=path, title=title, icon=icon)

    def activate(self):
        if self.content_type is None:
            return
        app_info = Gio.AppInfo.get_default_for_type(self.content_type, False)
        if app_info is None:
            return
        app_info.launch([Gio.File.new_for_path(self.detail)])


class ItemExecutable(ItemBase):
    def __init__(self, path):
        super().__init__(name=os.path.basename(path), detail=path, title=_("{name} [Executable]"), icon='application-x-executable')

    def activate(self):
        subprocess.Popen([self.detail])


class ItemAction(ItemBase):
    def activate(self):
        Gio.Application.get_default().activate_action(self.detail)
