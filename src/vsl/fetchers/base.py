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

from .. import items
from .. import logger


def chain(ChainClass, *cargs, debug=None, **ckwargs):
    def decorator(OldClass):
        class NewClass(ChainClass):
            def __init__(self, *args, **kwargs):
                super().__init__(OldClass(*args, **kwargs), *cargs, **ckwargs)
                if debug is not None:
                    debug(self)
        NewClass.__name__ = f'{OldClass.__name__}->{ChainClass.__name__}'
        return NewClass
    return decorator


class FetcherBase:
    def __init__(self, *, reply):
        self.reply = reply

    def __del__(self):
        logger.debug(f'Deleting {self}')

    def do_request(self, request):
        raise NotImplementedError


class FetcherLeaf(FetcherBase):
    def __init__(self):
        super().__init__(reply=Gio.ListStore(item_type=items.ScoredItem))

    def do_request(self, request):
        pass

    def append_item(self, item, score=0.0):
        self.reply.append(items.ScoredItem(item, score))


class FetcherTransform(FetcherBase):
    def __init__(self, *, fetcher, **kwargs):
        self.fetcher = fetcher
        super().__init__(**kwargs)

    def do_request(self, request):
        self.fetcher.do_request(request)


class FetcherTop(FetcherTransform):
    def __init__(self, fetcher, *, size=10):
        sorter = Gtk.CustomSorter.new(lambda item1, item2, none: Gtk.Ordering.SMALLER if item1.score > item2.score else Gtk.Ordering.LARGER if item1.score < item2.score else Gtk.Ordering.EQUAL)
        reply = Gtk.SliceListModel(model=Gtk.SortListModel(model=fetcher.reply, sorter=sorter), size=size)
        super().__init__(fetcher=fetcher, reply=reply)


class FetcherMinScore(FetcherTransform):
    def __init__(self, fetcher, *, score=0.2):
        filter = Gtk.CustomFilter.new(lambda item, score_: item.score >= score_, score)
        super().__init__(fetcher=fetcher, reply=Gtk.FilterListModel(model=fetcher.reply, filter=filter))


class FetcherNonEmpty(FetcherTransform):
    def __init__(self, fetcher):
        self.nonempty = False
        filter = Gtk.CustomFilter.new(lambda item: False)
        super().__init__(fetcher=fetcher, reply=Gtk.FilterListModel(model=fetcher.reply, filter=filter))

    def do_request(self, request):
        if request:
            self.nonempty = True
            self.fetcher.do_request(request)
            self.reply.set_filter(Gtk.CustomFilter.new(lambda item: True))
        elif self.nonempty:
            self.nonempty = False
            self.reply.set_filter(Gtk.CustomFilter.new(lambda item: False))


class FetcherChangeScore(FetcherTransform):
    def __init__(self, fetcher):
        super().__init__(fetcher=fetcher, reply=Gtk.MapListModel(model=fetcher.reply))

    def set_score_delta(self, delta):
        self.reply.set_map_func(lambda i: i.apply_delta(delta))


class FetcherScoreItems(FetcherTransform):
    def __init__(self, fetcher):
        super().__init__(fetcher=fetcher, reply=Gtk.MapListModel(model=fetcher.reply))

    def do_request(self, request):
        self.reply.set_map_func(lambda i, r: i.apply_request(r), request)
        super().do_request(request)


class FetcherMux(FetcherBase):
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


class FetcherPrefix(FetcherBase):
    PREFIX_NONE = 0
    PREFIX_BAD = 1
    PREFIX_EXACT = 2
    PREFIX_OK = 3

    def __init__(self, fetcher, prefix, name, icon=None):
        self.fetcher = fetcher
        self.prefix = prefix
        self.name = name
        self.icon = icon

        self.score_fetcher = FetcherChangeScore(fetcher)
        self.nonempty_fetcher = FetcherNonEmpty(self.score_fetcher)
        self.prefix_fetcher = FetcherLeaf()

        self.replies = Gio.ListStore(item_type=Gio.ListModel)
        self.replies.append(self.nonempty_fetcher.reply)
        self.replies.append(self.prefix_fetcher.reply)

        self.prefix_status = self.PREFIX_NONE

        super().__init__(reply=Gtk.FlattenListModel(model=self.replies))

    def do_request(self, request):
        if not request.startswith('.'):
            if self.prefix_status != self.PREFIX_NONE:
                self.prefix_status = self.PREFIX_NONE
                self.prefix_fetcher.reply.remove_all()
                self.score_fetcher.set_score_delta(0.0)
            self.nonempty_fetcher.do_request(request)
        elif request[1:] in (self.prefix, ''):
            if self.prefix_status != self.PREFIX_EXACT:
                self.prefix_status = self.PREFIX_EXACT
                item = items.ItemChangeRequest(name=self.name, detail=f"Prefix is « {self.prefix} »", icon=self.icon, pattern='\\.$', repl='.' + self.prefix)
                self.prefix_fetcher.append_item(item, score=1.0)
                self.nonempty_fetcher.do_request('')
        elif not request[1:].startswith(self.prefix):
            if self.prefix_status != self.PREFIX_BAD:
                self.prefix_status = self.PREFIX_BAD
                self.prefix_fetcher.reply.remove_all()
                self.nonempty_fetcher.do_request('')
        else:
            if self.prefix_status != self.PREFIX_OK:
                self.prefix_status = self.PREFIX_OK
                self.prefix_fetcher.reply.remove_all()
                self.score_fetcher.set_score_delta(1.0)
            self.nonempty_fetcher.do_request(request[len(self.prefix) + 1:])
