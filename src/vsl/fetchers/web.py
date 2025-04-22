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


import asyncio
import urllib.parse

from . import base
from . import firefox
from .. import items


class FetcherWeb(base.FetcherLeaf):
    def __init__(self, url, name, icon=None, favicon=None, favicon_source=firefox._FirefoxInfo):
        super().__init__(name, icon)
        self.url = url

        if favicon:
            asyncio.create_task(self.get_icon(favicon, favicon_source))

    async def get_icon(self, favicon, favicon_source):
        self.icon = await favicon_source.get_favicon(favicon)

    def do_request(self, request):
        self.reply.remove_all()
        self.append_item(items.ItemUri(name=self.name, detail=self.url.replace('%s', request), icon=self.icon), score=0.7)


class FetcherWebUrl(base.FetcherLeaf):
    def __init__(self):
        super().__init__(_("Open URL in browser"), 'web-browser')

    def do_request(self, request):
        self.reply.remove_all()
        url = urllib.parse.urlsplit(request)
        if url.scheme in ('http', 'https'):
            score = 1.0
        elif url.scheme != '':
            return
        else:
            url = urllib.parse.urlsplit('https://' + request)
            if '.' in url.netloc and all(url.netloc.split('.')) and url.netloc == request:
                score = 0.9
            else:
                return
        item = items.ItemUri(name=self.name, detail=urllib.parse.urlunsplit(url), icon=self.icon)
        self.append_item(item, score)
