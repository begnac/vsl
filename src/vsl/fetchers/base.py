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


from .. import items
from .. import logger


def chain(pipe, *cargs, **ckwargs):
    def decorator(old):
        def init(self, *args, **kwargs):
            pipe.__init__(self, old(*args, **kwargs), *cargs, **ckwargs)
        return type(f'{old.__name__}->{pipe.__name__}', (pipe,), dict(__init__=init))
    return decorator


def score(old):
    old = chain(FetcherScoreItems)(old)
    old = chain(FetcherMinScore)(old)
    old = chain(FetcherTop)(old)
    old = chain(FetcherScoreDecay, factor=0.8)(old)
    return old


def nonempty(old):
    old = chain(FetcherNonEmpty)(old)
    return old


class FetcherBase:
    def __init__(self):
        self.hooks = []
        self.freeze_count = 0
        self.changed_while_frozen = False

    def __del__(self):
        logger.debug(f'Deleting fetcher {self}')

    def freeze(self):
        self.freeze_count += 1

    def thaw(self):
        if self.freeze_count == 0:
            raise RuntimeError
        self.freeze_count -= 1
        if self.freeze_count == 0 and self.changed_while_frozen:
            self.changed_while_frozen = False
            self._changed()

    def cleanup(self):
        pass

    def changed(self):
        if self.freeze_count == 0:
            self._changed()
        else:
            self.changed_while_frozen = True

    def _changed(self):
        for hook in self.hooks:
            hook()

    def __iter_(self):
        raise NotImplementedError

    def do_request(self, request):
        raise NotImplementedError


class FetcherSource(FetcherBase):
    def __init__(self, name, icon):
        super().__init__()
        self.name = name
        self.icon = icon


class FetcherLeaf(FetcherSource):
    def __init__(self, name=None, icon=None):
        super().__init__(name, icon)
        self.data = []

    def do_request(self, request):
        pass

    def append_item(self, item, score=0.0):
        self.data.append((item, score))
        self.changed()

    def __iter__(self):
        yield from self.data


class FetcherPipe(FetcherBase):
    def __init__(self, fetcher):
        self.fetcher = fetcher
        super().__init__()
        fetcher.hooks.append(self.changed)

    def cleanup(self):
        self.fetcher.hooks.remove(self.changed)
        self.fetcher.cleanup()

    @property
    def name(self):
        return self.fetcher.name

    @property
    def icon(self):
        return self.fetcher.icon

    def do_request(self, request):
        self.fetcher.do_request(request)


class FetcherTop(FetcherPipe):
    def __init__(self, fetcher, size=10):
        self.size = size
        self.top = []
        super().__init__(fetcher)

    def changed(self):
        self.top = sorted(self.fetcher, key=lambda item: item[1], reverse=True)
        if len(self.top) > self.size:
            self.top = self.top[:self.size]
        super().changed()

    def __iter__(self):
        yield from self.top


class FetcherMinScore(FetcherPipe):
    def __init__(self, fetcher, *, score=0.2):
        self.score = score
        super().__init__(fetcher)

    def __iter__(self):
        return filter(lambda item: item[1] >= self.score, self.fetcher)


class FetcherNonEmpty(FetcherPipe):
    def __init__(self, fetcher):
        self.nonempty = False
        super().__init__(fetcher)

    def do_request(self, request):
        if request:
            self.freeze()
            if not self.nonempty:
                self.nonempty = True
                self.changed()
            self.fetcher.do_request(request)
            self.thaw()
        else:
            if self.nonempty:
                self.nonempty = False
                self.changed()

    def __iter__(self):
        if self.nonempty:
            yield from self.fetcher


class FetcherScoreDecay(FetcherPipe):
    def __init__(self, fetcher, *, factor):
        self.factor = factor
        super().__init__(fetcher)

    def __iter__(self):
        f = 1.0
        for item, score in self.fetcher:
            yield item, score * f
            f *= self.factor


class FetcherScoreItems(FetcherPipe):
    def __init__(self, fetcher):
        self.request = ''
        super().__init__(fetcher)

    def do_request(self, request):
        self.freeze()
        super().do_request(request)
        self.request = request
        self.changed()
        self.thaw()

    def __iter__(self):
        for item, score in self.fetcher:
            yield item, score + item.score(self.request)


class FetcherPrefix(FetcherPipe):
    PREFIX_NONE = 0
    PREFIX_PREFIX = 1
    PREFIX_OK = 2
    PREFIX_BAD = 3

    def __init__(self, fetcher, prefix):
        self.prefix = prefix
        self.prefix_status = self.PREFIX_NONE
        self.score_delta = 0.0
        super().__init__(fetcher)

    def do_request(self, request):
        self.freeze()
        if not request.startswith('.'):
            if self.prefix_status != self.PREFIX_NONE:
                self.prefix_status = self.PREFIX_NONE
                self.score_delta = 0.0
                self.changed()
            self.fetcher.do_request(request)
        elif self.prefix.startswith(request[1:]):
            self.prefix_status = self.PREFIX_PREFIX
            self.item_prefix = items.ItemChangeRequest(name=self.fetcher.name, detail=f"Prefix is « {self.prefix} »", icon=self.fetcher.icon, pattern=f'\\{request}$', repl='.' + self.prefix)
            self.changed()
        elif request[1:].startswith(self.prefix):
            if self.prefix_status != self.PREFIX_OK:
                self.prefix_status = self.PREFIX_OK
                self.changed()
            self.fetcher.do_request(request[len(self.prefix) + 1:])
        else:
            if self.prefix_status != self.PREFIX_BAD:
                self.prefix_status = self.PREFIX_BAD
                self.changed()
        self.thaw()

    def __iter__(self):
        if self.prefix_status == self.PREFIX_NONE:
            yield from self.fetcher
        elif self.prefix_status == self.PREFIX_PREFIX:
            yield self.item_prefix, 1.0
        elif self.prefix_status == self.PREFIX_OK:
            for item, score in self.fetcher:
                yield item, score + 1.0


@nonempty
class FetcherMux(FetcherSource):
    def __init__(self, fetchers, name=None, icon=None):
        super().__init__(name, icon)
        self.fetchers = list(fetchers)
        for fetcher in self.fetchers:
            fetcher.hooks.append(self.changed)

    def cleanup(self):
        for fetcher in self.fetchers:
            fetcher.hooks.remove(self.changed)
            fetcher.cleanup()

    def __iter__(self):
        for fetcher in self.fetchers:
            yield from fetcher

    def do_request(self, request):
        self.freeze()
        for fetcher in self.fetchers:
            fetcher.do_request(request)
        self.thaw()
