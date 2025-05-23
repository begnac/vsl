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

from . import base


def fetcher_from_config(config, name='Root'):
    section = config[name]
    nameargs = f'{name}.args'
    if config.has_section(nameargs):
        args = dict(config[nameargs])
    else:
        args = {}
    for namesubarg in config.sections():
        if namesubarg.startswith(nameargs + '.'):
            args[namesubarg[len(nameargs) + 1:]] = dict(config[namesubarg])
    if section['type'] == 'mux':
        fetchers = (base.FetcherPrefix(fetcher_from_config(config, name), prefix) for prefix, name in config[f'{name}.mux'].items())
        return base.FetcherTop(base.FetcherMux(fetchers, **args))
    elif section['type'] == 'import':
        module_name, node_name = section['import'].rsplit('.', 1)
        module = importlib.import_module(module_name, __name__)
        return getattr(module, node_name)(**args)
