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


import importlib

from .fetchers import base


class Node:
    def instantiate(self, args, nodes):
        raise NotImplementedError


class NodeImport(Node):
    def __init__(self, name):
        module_name, node_name = name.rsplit('.', 1)
        module = importlib.import_module(module_name, 'vsl.fetchers')
        self.class_ = getattr(module, node_name)

    def instantiate(self, nodes, *args):
        return self.class_(*args)


class NodePipeline(Node):
    def __init__(self, *segments):
        self.segments = segments

    def instantiate(self, nodes):
        name, *args = self.segments[0]
        pipeline = nodes[name].instantiate(nodes, *args)
        for name, *args in self.segments[1:]:
            pipeline = nodes[name].instantiate(nodes, pipeline, *args)
        return pipeline


class NodeSingle(NodePipeline):
    def __init__(self, *segment):
        super().__init__(segment)


class NodeMux(Node):
    def __init__(self, name, icon, *sources):
        self.name = name
        self.icon = icon
        self.sources = sources

    def instantiate(self, nodes):
        return base.FetcherTop(base.FetcherMux(self.name, self.icon, (base.FetcherPrefix(nodes[name].instantiate(nodes, *args), prefix) for prefix, name, *args in self.sources)))


class TreeData:
    def __init__(self):
        self.nodes = {
            'ChromiumBookmarks': NodeImport('.chromium.FetcherChromiumBookmarks'),
            'FirefoxBookmarks': NodeImport('.firefox.FetcherFirefoxBookmarks'),
            'WebSearch': NodeImport('.web.FetcherWebSearch'),
            'Url': NodeImport('.web.FetcherWebUrl'),
            'Actions': NodeImport('.misc.FetcherActions'),
            'Locate': NodeImport('.misc.FetcherLocate'),
            'LaunchApp': NodeImport('.misc.FetcherLaunchApp'),

            'Google': NodeSingle('WebSearch', 'https://www.google.com/search?q=%s', _("Google search"), None, 'https://www.google.com/favicon.ico'),
            'DebianPackage': NodeSingle('WebSearch', 'https://packages.debian.org/search?searchon=names&keywords=%s&suite=sid&arch=any', _("Debian package search"), 'emblem-debian'),
            'DebianFile': NodeSingle('WebSearch', 'https://packages.debian.org/search?searchon=contents&keywords=%s&mode=filename&suite=sid&arch=any', _("Debian file search"), 'emblem-debian'),
            'DebianBugNumber': NodeSingle('WebSearch', 'https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=%s', _("Debian bug by number"), 'emblem-debian'),
            'DebianBugPackage': NodeSingle('WebSearch', 'https://bugs.debian.org/cgi-bin/pkgreport.cgi?dist=sid;package=%s', _("Debian bugs by package"), 'emblem-debian'),

            'DebianBugs': NodeMux(_("Debian bugs"), 'emblem-debian',
                                  ['n', 'DebianBugNumber'],
                                  ['p', 'DebianBugPackage'],
                                  ),

            'Debian': NodeMux(_("Debian searchs"), 'emblem-debian',
                              ['p', 'DebianPackage'],
                              ['f', 'DebianFile'],
                              ['b', 'DebianBugs'],
                              ),

            'Root': NodeMux(None, None,
                            # ['cb', 'ChromiumBookmarks'],
                            ['fb', 'FirefoxBookmarks'],
                            ['gg', 'Google'],
                            ['d', 'Debian'],
                            ['u', 'Url'],
                            ['vsl', 'Actions'],
                            ['lo', 'Locate'],
                            ['a', 'LaunchApp'],
                            ),
        }

    def instantiate_root(self):
        return self.nodes['Root'].instantiate(self.nodes)


def Root():
    return TreeData().instantiate_root()
