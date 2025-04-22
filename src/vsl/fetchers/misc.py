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
import os
import re

from gi.repository import Gio

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
    def __init__(self, *, min_length='4', exclude='', max_paths=10000, bonus={}):
        super().__init__(_("Locate files"), 'system-search')
        self.min_length = int(min_length)
        self.exclude = [pattern for pattern in exclude.split() if pattern]
        self.max_paths = max_paths
        if bonus:
            print("Bonus not implemented yet")

        self.task = None
        self.last_async_request = None

    def do_request(self, request):
        if self.last_async_request is not None and request.startswith(self.last_async_request):
            return
        self.reply.remove_all()
        self.last_async_request = None
        if len(request) < self.min_length:
            self.append_item(items.ItemNoop(name=_("Type at least {min_length} characters to locate files").format(min_length=self.min_length), detail='', icon=self.icon), 0.2)
            self.task = None
        else:
            self.task = asyncio.create_task(self.async_do_request(request))

    async def async_do_request(self, request):
        task = asyncio.current_task()
        if task != self.task:
            return

        process = None
        try:
            process = await asyncio.create_subprocess_exec('plocate', '-iN', request, stdout=asyncio.subprocess.PIPE)
            if task != self.task:
                return

            data = b''
            counter = 0
            while True:
                new_data = await process.stdout.read(1024)
                if task != self.task:
                    return
                elif not new_data:
                    self.task = None
                    self.last_async_request = request
                    return
                *paths, data = (data + new_data).split(b'\n')
                for path in paths:
                    self.add_path(path.decode())
                    counter += 1
                    if counter == self.max_paths:
                        self.task = None
                        return
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                await process.communicate()

    def add_path(self, path):
        for pattern in self.exclude:
            if re.search(pattern, path):
                return
        score = 0.0
        if not path.startswith(os.path.expanduser('~/')):
            score -= 0.1
        if '/.git/' in path or '/.cache/' in path:
            score -= 0.3
        if os.path.isfile(path) and os.access(path, os.X_OK):
            item = items.ItemExecutable(path)
            score += 0.1
        elif os.path.isdir(path):
            item = items.ItemFolder(path)
        else:
            item = items.ItemFile(path)
        self.append_item(item, score)


@base.score
class FetcherLaunchApp(base.FetcherLeaf):
    def __init__(self):
        super().__init__(_("Applications"), 'applications-utilities')
        for appinfo in Gio.app_info_get_all():
            item = items.ItemDesktop(name=appinfo.get_name(), detail=appinfo.get_filename(), title=_("{name} [application]"), icon=appinfo.get_icon())
            self.append_item(item)
