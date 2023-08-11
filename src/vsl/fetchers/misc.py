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
from . import web
from .. import items


@base.chain(base.FetcherTop)
@base.chain(base.FetcherMinScore)
@base.chain(base.FetcherScoreName)
class FetcherActions(base.FetcherLeaf):
    def __init__(self):
        super().__init__()
        self.append_item(items.ItemAction(name=_("Quit"), detail='quit', icon='face-devilish'))
        self.append_item(items.ItemAction(name=_("Close window"), detail='close', icon='face-devilish'))


@base.chain(base.FetcherPrefix, 'lo', _("Locate files"), 'system-search')
@base.chain(base.FetcherTop)
@base.chain(base.FetcherMinScore)
@base.chain(base.FetcherScoreName)
class FetcherLocate(base.FetcherLeaf):
    def __init__(self):
        super().__init__()
        self.future = None

    def do_request(self, request):
        if self.future is not None:
            self.future.cancel()

        self.future = asyncio.ensure_future(self.async_do_request(request))

    async def async_do_request(self, request):
        try:
            if len(request) < 3:
                self.reply.remove_all()
            else:
                process = await asyncio.create_subprocess_exec('plocate', '-biN', request, stdout=asyncio.subprocess.PIPE)
                filenames = await process.stdout.read()
                self.reply.remove_all()
                for filename in filenames.decode().split('\n')[:-1]:
                    content_type, encoding = mimetypes.guess_type(filename)
                    if content_type is not None:
                        icon = Gio.content_type_get_icon(content_type)
                        title = _("{{name}} ({description})").format(description=Gio.content_type_get_description(content_type))
                    else:
                        icon = None
                        title = None
                    score = 0.1 if filename.startswith(os.path.expanduser('~/')) else 0.0
                    item = items.ItemFile(name=os.path.basename(filename), detail=filename, title=title, icon=icon)
                    self.append_item(item, score)
        finally:
            self.future = None


class ItemDesktop(items.ItemBase):
    def activate(self):
        Gio.DesktopAppInfo.new_from_filename(self.detail).launch()


@base.chain(base.FetcherTop)
@base.chain(base.FetcherMinScore)
@base.chain(base.FetcherScoreName)
class _FetcherLaunchApp(base.FetcherLeaf):
    def __init__(self):
        super().__init__()
        for appinfo in Gio.app_info_get_all():
            item = ItemDesktop(name=appinfo.get_name(), detail=appinfo.get_filename(), title=_("Run application: {name}"), icon=appinfo.get_icon())
            self.append_item(item)


class FetcherLaunchApp(base.FetcherPrefix):
    def __init__(self):
        fetcher = _FetcherLaunchApp()
        super().__init__(fetcher, 'a', _("Applications"))
        asyncio.ensure_future(self.get_icon())

    async def get_icon(self):
        self.icon = await web.FirefoxInfo.get_favicon('https://specifications.freedesktop.org/favicon.ico')
