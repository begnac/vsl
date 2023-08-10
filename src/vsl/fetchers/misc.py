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


@base.chain(base.FetcherTop)
@base.chain(base.FetcherMinScore)
@base.chain(base.FetcherScoreTitle)
class FetcherActions(base.FetcherFixed):
    def __init__(self):
        super().__init__(
            items.ItemAction(title=_("Quit"), subtitle='quit', icon='face-devilish'),
            items.ItemAction(title=_("Close window"), subtitle='close', icon='face-devilish'),
        )
