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
from gi.repository import Gio
from gi.repository import GdkPixbuf

import os
import json
import asyncio
import aiosqlite

from . import base
from .. import items


class ChromiumInfo:
    ROOT = os.path.join(GLib.get_user_config_dir(), 'chromium', 'Default')

    @classmethod
    async def db(cls, name):
        path = os.path.join(cls.ROOT, name)
        return await aiosqlite.connect(f'file:{path}?immutable=1', uri=True)

    @classmethod
    async def get_favicon_db(cls):
        return await cls.db('Favicons')

    @classmethod
    async def get_favicon_from_db(cls, favicon, db):
        icons = await db.execute('SELECT image_data '
                                 'FROM favicon_bitmaps '
                                 'JOIN icon_mapping on favicon_bitmaps.icon_id = icon_mapping.icon_id '
                                 'WHERE page_url = ? '
                                 'ORDER BY width DESC', (favicon,))
        async for data, in icons:
            stream = Gio.MemoryInputStream.new_from_data(data)
            return GdkPixbuf.Pixbuf.new_from_stream(stream)

    @classmethod
    async def get_favicon(cls, favicon):
        db = await cls.get_favicon_db()
        try:
            return await cls.get_favicon_from_db(favicon, db)
        finally:
            await db.close()


@base.score
class FetcherChromiumBookmarks(base.FetcherLeaf):
    def __init__(self):
        super().__init__(_("Chromium bookmarks"), 'chromium')
        asyncio.create_task(self.get_bookmarks())

    async def get_bookmarks(self):
        path = os.path.join(GLib.get_user_config_dir(), 'chromium', 'Default', 'Bookmarks')
        bookmarks = json.loads(open(path, 'rb').read().decode('utf-8'))
        favicons = await ChromiumInfo.get_favicon_db()
        try:
            await self.append_bookmarks(bookmarks['roots'].values(), favicons)
        finally:
            await favicons.close()

    async def append_bookmarks(self, bookmarks, favicons):
        for bookmark in bookmarks:
            if bookmark['type'] == 'folder':
                await self.append_bookmarks(bookmark['children'], favicons)
            elif bookmark['type'] == 'url':
                icon = (await ChromiumInfo.get_favicon_from_db(bookmark['url'], favicons)) or 'chromium'
                self.append_item(items.ItemUri(name=bookmark['name'], detail=bookmark['url'], title=bookmark['name'], icon=icon), score=0.1)
