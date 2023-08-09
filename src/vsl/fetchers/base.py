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


from gi.repository import GObject
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


class Fetcher(GObject.Object):
    request = GObject.Property(type=str, default='')
    reply = GObject.Property(type=Gio.ListModel)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('notify::request', lambda self_, param: self_.notify_request_cb())
        if self.reply is None:
            self.reply = Gio.ListStore(item_type=items.Item)

    def __del__(self):
        logger.debug(f'Deleting {self}')

    def notify_request_cb(self):
        pass


class FetcherModifierMixin:
    def __init__(self, *, fetcher, **kwargs):
        super().__init__(**kwargs)
        self.fetcher = fetcher
        self.fetcher.request = self.request

    def notify_request_cb(self):
        super().notify_request_cb()
        self.fetcher.request = self.request


class FetcherTop(FetcherModifierMixin, Fetcher):
    def __init__(self, fetcher, *, size=5, **kwargs):
        sorter = Gtk.CustomSorter.new(lambda item1, item2, none: int((item2.score - item1.score) * 100))
        reply = Gtk.SliceListModel(model=Gtk.SortListModel(model=fetcher.reply, sorter=sorter), size=size)
        super().__init__(fetcher=fetcher, reply=reply, **kwargs)


class _FetcherFilter(FetcherModifierMixin, Fetcher):
    def __init__(self, *, fetcher, filter=None, **kwargs):
        super().__init__(fetcher=fetcher, reply=Gtk.FilterListModel(model=fetcher.reply, filter=filter), **kwargs)


class FetcherFilter(_FetcherFilter):
    def __init__(self, fetcher, *, score=0.2, **kwargs):
        super().__init__(fetcher=fetcher, filter=Gtk.CustomFilter.new(lambda item, score_: item.score >= score_, score), **kwargs)


class FetcherNonEmpty(_FetcherFilter):
    def __init__(self, fetcher, **kwargs):
        self.filter = Gtk.CustomFilter.new(lambda item, fetcher_: fetcher_.request != '', fetcher)
        super().__init__(fetcher=fetcher, filter=self.filter, **kwargs)

    def notify_request_cb(self):
        super().notify_request_cb()
        self.filter.changed(Gtk.FilterChange.LESS_STRICT if self.request == '' else Gtk.FilterChange.MORE_STRICT)


class _FetcherScore(FetcherModifierMixin, Fetcher):
    def __init__(self, fetcher, **kwargs):
        super().__init__(fetcher=fetcher, reply=Gtk.MapListModel(model=fetcher.reply), **kwargs)

    @staticmethod
    def change_score(item, delta):
        new_item = item.copy()
        new_item.score += delta
        return new_item


class FetcherChangeScore(_FetcherScore):
    def set_score(self, delta):
        self.reply.set_map_func(self.change_score, delta)


class FetcherScore(_FetcherScore):
    def notify_request_cb(self):
        super().notify_request_cb()
        self.reply.set_map_func(self.scorer, self.fetcher)

    @staticmethod
    def scorer(item, fetcher):
        rlen = len(fetcher.request)
        if not rlen:
            score = 0.0
        else:
            opcodes = difflib.SequenceMatcher(None, fetcher.request.lower(), item.title.lower()).get_opcodes()
            d = sum(i2 - i1 for opcode, i1, i2, j1, j2 in opcodes if opcode in ('replace', 'delete'))
            score = (1 - 2 * d / rlen) / len(opcodes)
        return _FetcherScore.change_score(item, score)


class FetcherFixed(Fetcher):
    def __init__(self, *_items, items=()):
        super().__init__()
        for item in _items:
            self.reply.append(item)
        for item in items:
            self.reply.append(item)


class _FetcherMux(Fetcher):
    fetchers = GObject.Property(type=Gio.ListModel)

    def __init__(self):
        fetchers = Gio.ListStore(item_type=Fetcher)
        self.reply_map = Gtk.MapListModel(model=fetchers)
        self.reply_map.set_map_func(lambda fetcher: fetcher.reply)
        super().__init__(fetchers=fetchers, reply=Gtk.FlattenListModel(model=self.reply_map))

    def notify_request_cb(self):
        super().notify_request_cb()


class FetcherMux(_FetcherMux):
    def __init__(self, *_fetchers, fetchers=()):
        super().__init__()

        for fetcher_class in self.classes:
            fetcher = fetcher_class()
            self.fetchers.append(fetcher)

    def notify_request_cb(self):
        for fetcher in self.fetchers:
            fetcher.request = self.request
        super().notify_request_cb()


class FetcherPrefix(_FetcherMux):
    PREFIX_NONE = 0
    PREFIX_BAD = 1
    PREFIX_EXACT = 2
    PREFIX_OK = 3

    def __init__(self, fetcher, prefix, title, icon=None):
        super().__init__()
        self.fetcher = fetcher
        self.score_fetcher = FetcherChangeScore(self.fetcher)
        self.fetcher2 = Fetcher()
        self.fetchers.append(self.score_fetcher)
        self.fetchers.append(self.fetcher2)

        self.prefix = prefix
        self.caught_reply = items.Item(title=title, subtitle=f"Prefix is « {prefix} »", icon=icon, score=1.0)

        self.status = self.PREFIX_NONE

    def notify_request_cb(self):
        if not self.request.startswith('.'):
            if self.status != self.PREFIX_NONE:
                self.status = self.PREFIX_NONE
                self.fetcher2.reply.remove_all()
            self.score_fetcher.set_score(0.0)
            self.fetcher.request = self.request
        elif self.request[1:] in (self.prefix, '?'):
            if self.status != self.PREFIX_EXACT:
                self.status = self.PREFIX_EXACT
                self.fetcher2.reply.append(self.caught_reply)
                self.fetcher.request = ''
        elif not self.request[1:].startswith(self.prefix):
            if self.status != self.PREFIX_BAD:
                self.status = self.PREFIX_BAD
                self.fetcher2.reply.remove_all()
                self.fetcher.request = ''
        else:
            if self.status != self.PREFIX_OK:
                self.status = self.PREFIX_OK
                self.fetcher2.reply.remove_all()
            self.score_fetcher.set_score(1.0)
            self.fetcher.request = self.request[len(self.prefix) + 1:]
