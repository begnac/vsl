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
from gi.repository import Gdk

import os
import configparser
import asyncio
import aiosqlite

from . import base
from .. import items


class _FirefoxInfo:
    FIREFOX_ROOT = os.path.expanduser('~/.mozilla/firefox')
    profile_path = None

    @classmethod
    def get_profile_path(cls):
        if cls.profile_path is None:
            profiles = configparser.ConfigParser()
            profiles.read(os.path.join(cls.FIREFOX_ROOT, 'profiles.ini'))
            for section in profiles.sections():
                if section.startswith('Profile') and profiles.has_option(section, 'Default') and profiles.getboolean(section, 'Default'):
                    cls.profile_path = profiles.get(section, 'Path')
                    if profiles.getboolean(section, 'IsRelative'):
                        cls.profile_path = os.path.join(cls.FIREFOX_ROOT, cls.profile_path)
                    break
        return cls.profile_path

    @classmethod
    async def db_in_profile(cls, name):
        path = os.path.join(cls.get_profile_path(), name)
        return await aiosqlite.connect(f'file:{path}.sqlite?immutable=1', uri=True)

    @classmethod
    async def get_favicon(cls, favicon):
        db = await cls.db_in_profile('favicons')
        try:
            icons = await db.execute('SELECT data '
                                     'FROM moz_icons '
                                     'WHERE icon_url = ? '
                                     'ORDER BY moz_icons.width DESC', (favicon,))
            async for data, in icons:
                return Gdk.Texture.new_from_bytes(GLib.Bytes.new_take(data))
        finally:
            await db.close()


@base.score
class FetcherFirefoxBookmarks(base.FetcherLeaf):
    def __init__(self):
        super().__init__(_("Firefox bookmarks"), 'firefox')
        asyncio.ensure_future(self.setup())

    async def setup(self):
        db1 = await _FirefoxInfo.db_in_profile('places')
        db2 = await _FirefoxInfo.db_in_profile('favicons')
        bookmarks = await db1.execute('SELECT bookmarks.title, places.url '
                                      'FROM moz_bookmarks bookmarks '
                                      # 'JOIN moz_bookmarks parents ON bookmarks.parent = parents.id AND parents.parent <> 4 '
                                      'JOIN moz_places places ON bookmarks.fk = places.id')
        async for title, url in bookmarks:
            icons = await db2.execute('SELECT moz_icons.data '
                                      'FROM moz_pages_w_icons '
                                      'JOIN moz_icons_to_pages ON moz_pages_w_icons.id = moz_icons_to_pages.page_id '
                                      'JOIN moz_icons ON moz_icons_to_pages.icon_id = moz_icons.id '
                                      'WHERE moz_pages_w_icons.page_url = ? '
                                      'ORDER BY moz_icons.width DESC', (url,))
            async for data, in icons:
                icon = Gdk.Texture.new_from_bytes(GLib.Bytes.new_take(data))
                break
            else:
                icon = 'firefox'
            self.append_item(items.ItemUri(name=title, detail=url, title=_("{name} [Firefox]"), icon=icon), score=0.1)
        await db2.close()
        await db1.close()
