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


def fetcher_from_config(config, name='Root'):
    section = config[name]
    extra = get_section_extra(section)
    if section['type'] == 'mux':
        return base.FetcherTop(base.FetcherMux(section.get('name'), section.get('icon'), (base.FetcherPrefix(fetcher_from_config(config, name), prefix) for prefix, name in extra)))
    elif section['type'] == 'import':
        module_name, node_name = section['name'].rsplit('.', 1)
        module = importlib.import_module(module_name, 'vsl.fetchers')
        return getattr(module, node_name)(**dict(extra))


def get_section_extra(section):
    for name, value in section.items():
        if name.startswith('_'):
            yield name[1:], value
