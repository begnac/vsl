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


def chain(factory):
    def decorator(old_factory):
        def new_factory(*args, **kwargs):
            return factory(old_factory(*args, **kwargs))
        return new_factory
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

    # def cleanup(self):
    #     logger.debug(f'Cleaning up {self}')


class FetcherModifierMixin:
    def __init__(self, *, fetcher, **kwargs):
        super().__init__(**kwargs)
        self.fetcher = fetcher
        self.fetcher.request = self.request

    def notify_request_cb(self):
        super().notify_request_cb()
        self.fetcher.request = self.request

    # def cleanup(self):
    #     super().cleanup()
    #     self.fetcher.cleanup()


class FetcherTop(FetcherModifierMixin, Fetcher):
    def __init__(self, fetcher, *, size=5, **kwargs):
        sorter = Gtk.CustomSorter.new(lambda item1, item2, none: int((item2.score - item1.score) * 100))
        reply = Gtk.SliceListModel(model=Gtk.SortListModel(model=fetcher.reply, sorter=sorter), size=size)
        super().__init__(fetcher=fetcher, reply=reply, **kwargs)


class FetcherFilter(FetcherModifierMixin, Fetcher):
    def __init__(self, fetcher, *, score=0.2, **kwargs):
        filter = Gtk.CustomFilter.new(lambda item, score_: item.score >= score_, score)
        reply = Gtk.FilterListModel(model=fetcher.reply, filter=filter)
        super().__init__(fetcher=fetcher, reply=reply, **kwargs)


class FetcherNonEmpty(FetcherModifierMixin, Fetcher):
    def __init__(self, fetcher, **kwargs):
        self.filter = Gtk.CustomFilter.new(lambda item, fetcher_: fetcher_.request != '', fetcher)
        reply = Gtk.FilterListModel(model=fetcher.reply, filter=self.filter)
        super().__init__(fetcher=fetcher, reply=reply, **kwargs)

    def notify_request_cb(self):
        super().notify_request_cb()
        self.filter.changed(Gtk.FilterChange.LESS_STRICT if self.request == '' else Gtk.FilterChange.MORE_STRICT)


class _FetcherScore(FetcherModifierMixin, Fetcher):
    def __init__(self, fetcher, **kwargs):
        super().__init__(fetcher=fetcher, reply=Gtk.MapListModel(model=fetcher.reply), **kwargs)

    @staticmethod
    def change_score(item, score):
        new_item = item.copy()
        new_item.score += score
        return new_item


class FetcherChangeScore(_FetcherScore):
    def set_score(self, score):
        self.reply.set_map_func(self.change_score, score)


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


class FetcherMux(_FetcherMux):
    def __init__(self, *_fetchers, fetchers=()):
        super().__init__()

        for fetcher in _fetchers:
            self.append_fetcher(fetcher)
        for fetcher in fetchers:
            self.append_fetcher(fetcher)

    def append_fetcher(self, fetcher):
        if fetcher in self.fetchers:
            raise ValueError
        self.fetchers.append(fetcher)
        fetcher.request_binding = self.bind_property('request', fetcher, 'request', GObject.BindingFlags.SYNC_CREATE)

    def remove_fetcher(self, fetcher):
        has, pos = self.fetchers.find(fetcher)
        if not has:
            raise ValueError
        self.fetchers.remove(pos)
        fetcher.request_binding.unbind()


class FetcherPrefix(_FetcherMux):
    has_prefix = GObject.Property(type=bool, default=False)

    def __init__(self, prefix, fetcher):
        super().__init__()
        self.fetcher = fetcher
        self.score_fetcher = FetcherChangeScore(fetcher)
        self.fetcher2 = Fetcher()
        self.fetchers.append(self.score_fetcher)
        self.fetchers.append(self.fetcher2)

        self.prefix = prefix
        self.caught_reply = items.Item(title="Caught prefix", subtitle=f"Prefix is « {prefix} »", icon=None)

    def notify_request_cb(self):
        super().notify_request_cb()
        has_prefix = False
        if self.request.startswith('.'):
            if self.request[1:].startswith(self.prefix):
                request = self.request[len(self.prefix) + 1:]
                has_prefix = True
            else:
                request = ''
        else:
            request = self.request

        if has_prefix:
            if not self.has_prefix:
                self.has_prefix = True
                self.fetcher2.reply.append(self.caught_reply)
                self.score_fetcher.set_score(1.0)
        else:
            if self.has_prefix:
                self.has_prefix = False
                self.fetcher2.reply.remove(0)
                self.score_fetcher.set_score(0.0)

        self.fetcher.request = request
