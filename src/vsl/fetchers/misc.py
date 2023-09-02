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


from gi.repository import Gio

import asyncio
import os
import mimetypes

from . import base
from .. import items


@base.score
class FetcherActions(base.FetcherLeaf):
    def __init__(self):
        super().__init__(_("VSL actions"), icon='face-devilish')
        self.append_item(items.ItemAction(name=_("Quit"), detail='quit', icon='application-exit'))
        self.append_item(items.ItemAction(name=_("Close window"), detail='close', icon='window-close'))


@base.score
class FetcherLocate(base.FetcherLeaf):
    def __init__(self):
        super().__init__(_("Locate files"), 'system-search')
        self.future = None
        self.last_async_request = None

    def do_request(self, request):
        if self.last_async_request is not None and request.startswith(self.last_async_request):
            return
        self.reply.remove_all()
        if len(request) < 3:
            self.append_item(items.ItemNoop(name=_("Type at least three characters to locate files"), detail='', icon=self.icon), 0.2)
            self.future = None
        else:
            self.future = asyncio.ensure_future(self.async_do_request(request))
            self.last_async_request = None

    async def async_do_request(self, request):
        future = asyncio.current_task()
        if future != self.future:
            return

        process = None
        process = await asyncio.create_subprocess_exec('plocate', '-iN', request, stdout=asyncio.subprocess.PIPE)
        if future != self.future:
            return

        data = b''
        while True:
            new_data = await process.stdout.read(1024)
            if future != self.future:
                return
            elif not new_data:
                self.future = None
                self.last_async_request = request
                return
            *filenames, data = (data + new_data).split(b'\n')
            for filename in filenames:
                filename = filename.decode()
                content_type, encoding = mimetypes.guess_type(filename)
                name = os.path.basename(filename)
                if os.path.isfile(filename) and os.access(filename, os.X_OK):
                    icon = 'application-x-executable'
                    title = _("{name} [Executable]")
                    item = items.ItemExecutable(name=name, detail=filename, title=title, icon=icon)
                    self.append_item(item, 0.1)
                    continue
                elif content_type is not None:
                    icon = Gio.content_type_get_icon(content_type)
                    title = _("{{name}} [{description}]").format(description=Gio.content_type_get_description(content_type))
                elif os.path.isdir(filename):
                    icon = 'folder'
                    name += '/'
                    title = None
                else:
                    icon = None
                    title = None
                score = 0.0 if filename.startswith(os.path.expanduser('~/')) else -0.1
                item = items.ItemFile(name=name, detail=filename, title=title, icon=icon)
                self.append_item(item, score)


class ItemDesktop(items.ItemBase):
    def activate(self):
        Gio.DesktopAppInfo.new_from_filename(self.detail).launch()

    def score(self, request):
        return super().score(request) + 0.1


@base.score
class FetcherLaunchApp(base.FetcherLeaf):
    def __init__(self):
        super().__init__(_("Applications"), 'applications-utilities')
        for appinfo in Gio.app_info_get_all():
            item = ItemDesktop(name=appinfo.get_name(), detail=appinfo.get_filename(), title=_("{name} [application]"), icon=appinfo.get_icon())
            self.append_item(item)
