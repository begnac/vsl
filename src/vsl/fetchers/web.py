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
from gi.repository import GdkPixbuf

import os
import configparser
import asyncio
import aiosqlite
import urllib.parse

from . import base
from .. import items


class FirefoxInfo:
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
            # icons = await db.execute('SELECT icon_url '
            #                          'FROM moz_icons '
            #                          'WHERE icon_url LIKE "%freedesktop%" ')
            # async for x in icons: print(x)
            icons = await db.execute('SELECT data '
                                     'FROM moz_icons '
                                     'WHERE icon_url = ? '
                                     'ORDER BY moz_icons.width DESC', (favicon,))
            async for data, in icons:
                stream = Gio.MemoryInputStream.new_from_data(data)
                return GdkPixbuf.Pixbuf.new_from_stream(stream)
        finally:
            await db.close()

    @classmethod
    async def _DEBUG_find_favicon(cls, pattern):
        db = await cls.db_in_profile('favicons')
        try:
            icons = await db.execute('SELECT icon_url '
                                     'FROM moz_icons '
                                     'WHERE icon_url LIKE ? ', (pattern,))
            async for url, in icons:
                print(url)
        finally:
            await db.close()


@base.chain(base.FetcherPrefix, 'fb', _("Firefox bookmarks"), 'firefox')
@base.chain(base.FetcherTop)
@base.chain(base.FetcherMinScore)
@base.chain(base.FetcherScoreName)
@base.chain(base.FetcherNonEmpty)
class FetcherFirefoxBookmarks(base.Fetcher):
    def __init__(self):
        super().__init__()
        asyncio.ensure_future(self.setup())

    async def setup(self):
        db = await FirefoxInfo.db_in_profile('places')
        bookmarks = await db.execute('SELECT bookmarks.title, places.url '
                                     'FROM moz_bookmarks bookmarks '
                                     # 'JOIN moz_bookmarks parents ON bookmarks.parent = parents.id AND parents.parent <> 4 '
                                     'JOIN moz_places places ON bookmarks.fk = places.id')
        async for title, url in bookmarks:
            self.reply.append(items.ItemUri(name=title, detail=url, title=_("Open bookmark: {name}"), icon='firefox'))
        await db.close()

        db = await FirefoxInfo.db_in_profile('favicons')
        for item in self.reply:
            icons = await db.execute('SELECT moz_icons.data '
                                     'FROM moz_pages_w_icons '
                                     'JOIN moz_icons_to_pages ON moz_pages_w_icons.id = moz_icons_to_pages.page_id '
                                     'JOIN moz_icons ON moz_icons_to_pages.icon_id = moz_icons.id '
                                     'WHERE moz_pages_w_icons.page_url = ? '
                                     'ORDER BY moz_icons.width DESC', (item.detail,))
            async for data, in icons:
                stream = Gio.MemoryInputStream.new_from_data(data)
                item.icon = GdkPixbuf.Pixbuf.new_from_stream(stream)
                break
        await db.close()


class FetcherWeb(base.Fetcher):
    def __init__(self, url, name, icon=None, favicon=None):
        super().__init__()
        self.url = url
        self.name = name
        self.icon = icon

        if favicon:
            asyncio.ensure_future(self.get_icon(favicon))

    async def get_icon(self, favicon):
        self.icon = await FirefoxInfo.get_favicon(favicon)

    def do_request(self, request):
        self.base_reply.remove_all()
        if request:
            self.base_reply.append(items.ItemUri(name=self.name, detail=self.url.replace('%s', request), icon=self.icon))


class FetcherWebPrefix(base.FetcherPrefix):
    def __init__(self, prefix, url, name, icon=None, favicon=None):
        fetcher = FetcherWeb(url, name, icon)
        super().__init__(fetcher, prefix, name, icon)
        if favicon:
            asyncio.ensure_future(self.get_icon(favicon))

    async def get_icon(self, favicon):
        self.icon = self.fetcher.icon = await FirefoxInfo.get_favicon(favicon)


class FetcherGoogle(FetcherWebPrefix):
    def __init__(self):
        super().__init__(prefix='gg', url='https://www.google.com/search?q=%s', name=_("Google search"), favicon='https://www.google.com/favicon.ico')


class FetcherDebianPackage(FetcherWebPrefix):
    def __init__(self):
        super().__init__(prefix='p', url='https://packages.debian.org/search?searchon=names&keywords=%s&suite=sid&arch=any', name=_("Debian package search"), icon='emblem-debian')


class FetcherDebianFile(FetcherWebPrefix):
    def __init__(self):
        super().__init__(prefix='f', url='https://packages.debian.org/search?searchon=contents&keywords=%s&mode=filename&suite=sid&arch=any', name=_("Debian file search"), icon='emblem-debian')


class FetcherDebianBugPackage(FetcherWebPrefix):
    def __init__(self):
        super().__init__(prefix='p', url='https://bugs.debian.org/cgi-bin/pkgreport.cgi?dist=sid;package=%s', name=_("Debian bugs by package"), icon='emblem-debian')


class FetcherDebianBugNumber(FetcherWebPrefix):
    def __init__(self):
        super().__init__(prefix='n', url='https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=%s', name=_("Debian bug by number"), icon='emblem-debian')


@base.chain(base.FetcherPrefix, 'b', _("Debian bugs"), 'emblem-debian')
class FetcherDebianBugs(base.FetcherMux):
    classes = [
        FetcherDebianBugPackage,
        FetcherDebianBugNumber,
    ]


@base.chain(base.FetcherPrefix, 'd', _("Debian searches"), 'emblem-debian')
class FetcherDebian(base.FetcherMux):
    classes = [
        FetcherDebianPackage,
        FetcherDebianFile,
        FetcherDebianBugs,
    ]


class FetcherUrl(base.Fetcher):
    def do_request(self, request):
        self.reply.remove_all()
        result = urllib.parse.urlsplit(request)
        if result.scheme in ('http', 'https'):
            uri = self.request
        elif result.scheme == '' and '.' in result.path and all(result.path.split('.')) and result.path == request:
            uri = urllib.parse.urlunsplit(('https', request, '', '', ''))
        else:
            return
        item = items.ItemUri(name=_("Open URL in browser"), detail=uri, icon='web-browser', score=1.0)
        self.reply.append(item)
