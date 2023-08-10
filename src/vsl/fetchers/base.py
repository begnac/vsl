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
from gi.repository import Gtk

import difflib

from .. import items
from .. import logger


def chain(ChainClass, *cargs, **ckwargs):
    def decorator(OldClass):
        class NewClass(ChainClass):
            def __init__(self, *args, **kwargs):
                super().__init__(OldClass(*args, **kwargs, **ckwargs), *cargs, **ckwargs)
        NewClass.__name__ = f'{OldClass.__name__}->{ChainClass.__name__}'
        return NewClass
    return decorator


class Fetcher:
    def __init__(self, reply=None):
        self.reply = self.base_reply = Gio.ListStore(item_type=items.Item) if reply is None else reply

    def __del__(self):
        logger.debug(f'Deleting {self}')

    def do_request(self, request):
        pass


class FetcherTransform(Fetcher):
    def __init__(self, *, fetcher, **kwargs):
        self.fetcher = fetcher
        super().__init__(**kwargs)

    def do_request(self, request):
        self.fetcher.do_request(request)


class FetcherTop(FetcherTransform):
    def __init__(self, fetcher, *, size=5):
        sorter = Gtk.CustomSorter.new(lambda item1, item2, none: int((item2.score - item1.score) * 100))
        reply = Gtk.SliceListModel(model=Gtk.SortListModel(model=fetcher.reply, sorter=sorter), size=size)
        super().__init__(fetcher=fetcher, reply=reply)


class FetcherMinScore(FetcherTransform):
    def __init__(self, fetcher, *, score=0.2, **kwargs):
        filter = Gtk.CustomFilter.new(lambda item, score_: item.score >= score_, score)
        super().__init__(fetcher=fetcher, reply=Gtk.FilterListModel(model=fetcher.reply, filter=filter), **kwargs)


class FetcherNonEmpty(FetcherTransform):
    def __init__(self, fetcher):
        self.nonempty = False
        super().__init__(fetcher=fetcher, reply=Gtk.SliceListModel(model=fetcher.reply, size=0))

    def do_request(self, request):
        if request:
            self.nonempty = True
            self.fetcher.do_request(request)
            self.reply.set_size(len(self.fetcher.reply))
        elif self.nonempty:
            self.nonempty = False
            self.reply.set_size(0)


class FetcherChangeScore(FetcherTransform):
    def __init__(self, fetcher):
        super().__init__(fetcher=fetcher, reply=Gtk.MapListModel(model=fetcher.reply))

    def set_score_delta(self, delta):
        self.reply.set_map_func(lambda item: item.copy_change_score(delta))


class FetcherScoreTitle(FetcherTransform):
    def __init__(self, fetcher):
        super().__init__(fetcher=fetcher, reply=Gtk.MapListModel(model=fetcher.reply))

    def do_request(self, request):
        self.reply.set_map_func(self.scorer, request)
        super().do_request(request)

    @staticmethod
    def scorer(item, request):
        rlen = len(request)
        if not rlen:
            score = 0.0
        else:
            opcodes = difflib.SequenceMatcher(None, request.lower(), item.title.lower()).get_opcodes()
            d = sum(i2 - i1 for opcode, i1, i2, j1, j2 in opcodes if opcode in ('replace', 'delete'))
            score = (1 - 2 * d / rlen) / len(opcodes)
        return item.copy_change_score(score)


class FetcherFixed(Fetcher):
    def __init__(self, *_items, items=()):
        super().__init__()
        for item in _items:
            self.reply.append(item)
        for item in items:
            self.reply.append(item)


class FetcherMux(Fetcher):
    def __init__(self):
        self.fetchers = []
        self.replies = Gio.ListStore(item_type=Gio.ListModel)
        for fetcher_class in self.classes:
            fetcher = fetcher_class()
            self.fetchers.append(fetcher)
            self.replies.append(fetcher.reply)
        super().__init__(reply=Gtk.FlattenListModel(model=self.replies))

    def do_request(self, request):
        for fetcher in self.fetchers:
            fetcher.do_request(request)


class FetcherPrefix(Fetcher):
    PREFIX_NONE = 0
    PREFIX_BAD = 1
    PREFIX_EXACT = 2
    PREFIX_OK = 3

    def __init__(self, fetcher, prefix, title, icon=None):
        self.fetcher = fetcher
        self.prefix = prefix
        self.title = title
        self.icon = icon

        self.score_fetcher = FetcherChangeScore(fetcher)
        self.prefix_fetcher = Fetcher()

        self.replies = Gio.ListStore(item_type=Gio.ListModel)
        self.replies.append(self.score_fetcher.reply)
        self.replies.append(self.prefix_fetcher.reply)

        self.prefix_status = self.PREFIX_NONE

        super().__init__(reply=Gtk.FlattenListModel(model=self.replies))

    def do_request(self, request):
        if not request.startswith('.'):
            if self.prefix_status != self.PREFIX_NONE:
                self.prefix_status = self.PREFIX_NONE
                self.prefix_fetcher.reply.remove_all()
                self.score_fetcher.set_score_delta(0.0)
            self.fetcher.do_request(request)
        elif request[1:] in (self.prefix, '?'):
            if self.prefix_status != self.PREFIX_EXACT:
                self.prefix_status = self.PREFIX_EXACT
                item = items.Item(title=self.title, subtitle=f"Prefix is « {self.prefix} »", icon=self.icon, score=1.0)
                self.prefix_fetcher.reply.append(item)
                self.fetcher.do_request('')
        elif not request[1:].startswith(self.prefix):
            if self.prefix_status != self.PREFIX_BAD:
                self.prefix_status = self.PREFIX_BAD
                self.prefix_fetcher.reply.remove_all()
                self.fetcher.do_request('')
        else:
            if self.prefix_status != self.PREFIX_OK:
                self.prefix_status = self.PREFIX_OK
                self.prefix_fetcher.reply.remove_all()
                self.score_fetcher.set_score_delta(1.0)
            self.fetcher.do_request(request[len(self.prefix) + 1:])
