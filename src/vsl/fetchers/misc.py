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


from . import base
from .. import items

import os
import configparser
import asyncio
import aiosqlite
import urllib.parse


@base.chain(base.FetcherTop)
@base.chain(base.FetcherFilter)
@base.chain(base.FetcherScore)
class FetcherActions(base.FetcherFixed):
    def __init__(self):
        super().__init__(
            items.ItemAction(title=_("Quit"), subtitle='quit', icon='face-devilish'),
            items.ItemAction(title=_("Close window"), subtitle='close', icon='face-devilish'),
        )


@base.chain(base.FetcherNonEmpty)
class FetcherWeb(base.Fetcher):
    def __init__(self, url, title, icon=None):
        super().__init__()
        self.title = title
        self.url = url
        self.icon = icon

    def notify_request_cb(self):
        super().notify_request_cb()
        self.reply.splice(0, len(self.reply), [items.ItemUri(title=self.title, subtitle=self.url.replace('%s', self.request), icon=self.icon)])


@base.chain(base.FetcherPrefix, 'gg', title=_("Google search"))
class FetcherGoogle(FetcherWeb):
    def __init__(self, **kwargs):
        super().__init__('https://www.google.com/search?q=%s', **kwargs)


@base.chain(base.FetcherPrefix, 'p', title=_("Debian package search"), icon='emblem-debian')
class FetcherDebianPackage(FetcherWeb):
    def __init__(self, **kwargs):
        super().__init__('https://packages.debian.org/search?searchon=names&keywords=%s&suite=sid&arch=any', **kwargs)


@base.chain(base.FetcherPrefix, 'f', title=_("Debian file search"), icon='emblem-debian')
class FetcherDebianFile(FetcherWeb):
    def __init__(self, **kwargs):
        super().__init__('https://packages.debian.org/search?searchon=contents&keywords=%s&mode=filename&suite=sid&arch=any', **kwargs)


@base.chain(base.FetcherPrefix, 'p', title=_("Debian bugs by package"), icon='emblem-debian')
class FetcherDebianBugPackage(FetcherWeb):
    def __init__(self, **kwargs):
        super().__init__('https://bugs.debian.org/cgi-bin/pkgreport.cgi?dist=sid;package=%s', **kwargs)


@base.chain(base.FetcherPrefix, 'n', title=_("Debian bug by number"), icon='emblem-debian')
class FetcherDebianBugNumber(FetcherWeb):
    def __init__(self, **kwargs):
        super().__init__('https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=%s', **kwargs)


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


@base.chain(base.FetcherPrefix, 'ff', _("Firefox bookmarks"), 'firefox')
@base.chain(base.FetcherTop)
@base.chain(base.FetcherFilter)
@base.chain(base.FetcherScore)
class FetcherFirefox(base.Fetcher):
    FIREFOX_ROOT = os.path.expanduser('~/.mozilla/firefox')
    FIREFOX_PROFILES = os.path.join(FIREFOX_ROOT, 'profiles.ini')

    FIREFOX_PROFILE_DEFAULT = 'Default'
    FIREFOX_PROFILE_ISRELATIVE = 'IsRelative'
    FIREFOX_PROFILE_PATH = 'Path'

    FIREFOX_PLACES_FILE = 'places.sqlite'

    def __init__(self):
        super().__init__()
        asyncio.ensure_future(self.setup())

    async def setup(self):
        db = await aiosqlite.connect(f'file:{self.firefox_places()}?immutable=1', uri=True)
        bookmarks = await db.execute('SELECT bookmarks.title, places.url '
                                     'FROM moz_bookmarks bookmarks '
                                     # 'JOIN moz_bookmarks parents ON bookmarks.parent = parents.id AND parents.parent <> 4 '
                                     'JOIN moz_places places ON bookmarks.fk = places.id')
        async for title, url in bookmarks:
            self.reply.append(items.ItemUri(icon='firefox', title=title, subtitle=url))
        await db.close()

    def firefox_places(self):
        profiles = configparser.ConfigParser()
        profiles.read(self.FIREFOX_PROFILES)
        for section in profiles.sections():
            if section.startswith('Profile') and profiles.has_option(section, self.FIREFOX_PROFILE_DEFAULT) and profiles.getboolean(section, self.FIREFOX_PROFILE_DEFAULT):
                path = profiles.get(section, self.FIREFOX_PROFILE_PATH)
                if profiles.getboolean(section, self.FIREFOX_PROFILE_ISRELATIVE):
                    path = os.path.join(self.FIREFOX_ROOT, path)
                return os.path.join(path, self.FIREFOX_PLACES_FILE)


class FetcherUrl(base.Fetcher):
    def notify_request_cb(self):
        super().notify_request_cb()
        self.reply.remove_all()
        result = urllib.parse.urlsplit(self.request)
        if result.scheme in ('http', 'https'):
            uri = self.request
        elif result.scheme == '' and '.' in result.path and result.path == self.request:
            uri = urllib.parse.urlunsplit(('https', self.request, '', '', ''))
        else:
            return
        item = items.ItemUri(title=_("Open URL in browser"), subtitle=uri, icon='web-browser', score=1.0)
        self.reply.append(item)