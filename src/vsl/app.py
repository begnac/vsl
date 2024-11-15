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


import configparser
import signal
import os

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import gasyncio

from . import __application__, __program_name__, __version__, __copyright__, __license_type__
from . import ui
from . import tree
from . import logger


class Action(Gio.SimpleAction):
    def __init__(self, name, accels, activate_cb):
        self.name = name
        self.accels = accels
        self.activate_cb = lambda self_, param, app: activate_cb(app)
        super().__init__(name=name)

    def add_to_app(self, app):
        self.connect('activate', self.activate_cb, app)
        app.add_action(self)
        app.set_accels_for_action(f'app.{self.name}', self.accels)

    def remove_from_app(self, app):
        app.remove_action(self.name)
        self.disconnect_by_func(self.activate_cb)


class App(Gtk.Application):
    request = GObject.Property(type=str, default='')

    def __init__(self):
        super().__init__(application_id=f'begnac.{__application__}', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.ALLOW_REPLACEMENT)

        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Display version"), None)
        self.add_main_option('debug', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Debug messages"), None)
        self.add_main_option('request', ord('r'), GLib.OptionFlags.NONE, GLib.OptionArg.STRING, _("Request text"), None)
        self.add_main_option('clipboard', ord('c'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Request from clipboard"), None)

        self.connect('startup', self.startup_cb)
        self.connect('shutdown', self.shutdown_cb)
        self.connect('handle-local-options', self.handle_local_options_cb)
        self.connect('command-line', self.command_line_cb)
        self.connect('activate', self.activate_cb)

    def __del__(self):
        logger.debug(f'Deleting {self}')

    @staticmethod
    def startup_cb(self):
        ui.CssProvider().add_myself()

        self.sigint_source = GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: self.quit() or True)
        gasyncio.start_slave_loop()

        self.actions = (
            Action(name='quit', accels=['<Control>q'], activate_cb=lambda app: app.quit()),
            Action(name='close', accels=['Escape'], activate_cb=lambda app: app.close_window())
        )
        for action in self.actions:
            action.add_to_app(self)

        config_file = os.path.join(GLib.get_user_config_dir(), __application__)
        config = configparser.ConfigParser(interpolation=None)
        if os.path.exists(config_file):
            config.read_file(open(config_file), source=config_file)
        self.root_fetcher = tree.fetcher_from_config(config)

        self.connect('notify::request', lambda self_, param: self_.root_fetcher.do_request(self_.request))

        self.hold()

    @staticmethod
    def shutdown_cb(self):
        logger.debug("Shutting down")

        self.close_window()
        for action in self.actions:
            action.remove_from_app(self)
        self.release()
        gasyncio.stop_slave_loop()
        GLib.source_remove(self.sigint_source)

    @staticmethod
    def handle_local_options_cb(self, options):
        if options.contains('version'):
            print(_("{program} version {version}").format(program=__program_name__, version=__version__))
            print(__copyright__)
            print(__license_type__)
            return 0
        return -1

    @staticmethod
    def command_line_cb(self, command_line):
        options = command_line.get_options_dict().end().unpack()

        if 'debug' in options:
            logger.setLevelDebug()

        if 'request' in options:
            self.set_request(options['request'])
        elif 'clipboard' in options:
            Gdk.Display.get_default().get_primary_clipboard().read_text_async(None, self.clipboard_read_cb)
        self.activate()
        return 0

    def clipboard_read_cb(self, clipboard, result):
        try:
            self.set_request(clipboard.read_text_finish(result))
        except GLib.GError:
            pass

    @staticmethod
    def activate_cb(self):
        win = self.get_active_window() or ui.Window(self, self.root_fetcher)
        win.present()

    def set_request(self, request):
        self.request = request
        win = self.get_active_window()
        if win:
            win.focus_request()

    def close_window(self):
        win = self.get_active_window()
        if win:
            win.destroy()
