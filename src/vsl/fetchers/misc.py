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
import sqlite3


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
class FetcherGoogle(base.Fetcher):
    def notify_request_cb(self):
        super().notify_request_cb()
        self.reply.splice(0, len(self.reply), [items.ItemUri(title=_("Google search"), subtitle=f'https://www.google.com/search?q={self.request}')])


@base.chain(base.FetcherTop)
@base.chain(base.FetcherFilter)
@base.chain(base.FetcherScore)
class FetcherFirefox(base.FetcherFixed):
    FIREFOX_ROOT = os.path.expanduser('~/.mozilla/firefox')
    FIREFOX_PROFILES = os.path.join(FIREFOX_ROOT, 'profiles.ini')

    FIREFOX_PROFILE_DEFAULT = 'Default'
    FIREFOX_PROFILE_ISRELATIVE = 'IsRelative'
    FIREFOX_PROFILE_PATH = 'Path'

    FIREFOX_PLACES_FILE = 'places.sqlite'

    def __init__(self):
        con = sqlite3.connect(f'file:{self.firefox_places()}?immutable=1', uri=True)
        bookmarks = list(con.execute('SELECT bookmarks.title, places.url '
                                     'FROM moz_bookmarks bookmarks '
                                     'JOIN moz_bookmarks parents ON bookmarks.parent = parents.id AND parents.parent <> 4 '
                                     'JOIN moz_places places ON bookmarks.fk = places.id'))
        super().__init__(items=(items.ItemUri(icon='firefox', title=title, subtitle=url) for title, url in bookmarks))

    def firefox_places(self):
        profiles = configparser.ConfigParser()
        profiles.read(self.FIREFOX_PROFILES)
        for section in profiles.sections():
            if section.startswith('Profile') and profiles.has_option(section, self.FIREFOX_PROFILE_DEFAULT) and profiles.getboolean(section, self.FIREFOX_PROFILE_DEFAULT):
                path = profiles.get(section, self.FIREFOX_PROFILE_PATH)
                if profiles.getboolean(section, self.FIREFOX_PROFILE_ISRELATIVE):
                    path = os.path.join(self.FIREFOX_ROOT, path)
                return os.path.join(path, self.FIREFOX_PLACES_FILE)
