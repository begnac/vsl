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


from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import signal
import logging

import gasyncio

from . import __application__, __program_name__, __version__, __copyright__, __license_type__
from . import ui
from . import root
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


class ActionQuit(Action):
    def __init__(self):
        super().__init__(name='quit', accels=['<Control>q'], activate_cb=lambda app: app.quit())


class ActionClose(Action):
    def __init__(self):
        super().__init__(name='close', accels=['Escape'], activate_cb=lambda app: app.close_window())


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=f'begnac.{__application__}', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Display version"), None)
        self.add_main_option('copyright', ord('C'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Display copyright"), None)
        self.add_main_option('debug', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Debug messages"), None)
        self.add_main_option('request', ord('r'), GLib.OptionFlags.NONE, GLib.OptionArg.STRING, _("Request text"), None)
        self.add_main_option('clipboard', ord('c'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Request from clipboard"), None)

    def __del__(self):
        logger.debug('Deleting {}'.format(self))

    def do_startup(self):
        Gtk.Application.do_startup(self)

        ui.CssProvider().add_myself()

        self.sigint_source = GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)
        self.event_loop = gasyncio.GAsyncIOEventLoop()
        self.event_loop.start_slave_loop()

        self.actions = (ActionQuit(), ActionClose())
        for action in self.actions:
            action.add_to_app(self)

        self.root_fetcher = root.FetcherRoot()
        self.hold()

    def do_shutdown(self):
        logger.debug("Shutting down")

        self.close_window()
        for action in self.actions:
            action.remove_from_app(self)
        self.release()
        self.event_loop.stop_slave_loop()
        self.event_loop.close()
        GLib.source_remove(self.sigint_source)
        Gtk.Application.do_shutdown(self)

    def do_handle_local_options(self, options):
        if options.contains('version'):
            print(_("{program} version {version}").format(program=__program_name__, version=__version__))
            return 0

        if options.contains('copyright'):
            print(__copyright__)
            print(__license_type__)
            return 0

        return Gtk.Application.do_handle_local_options(self, options)

    def do_command_line(self, command_line):
        options = command_line.get_options_dict().end().unpack()

        if 'debug' in options:
            logger.setLevel(logging.DEBUG)

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

    def do_activate(self):
        Gtk.Application.do_activate(self)
        win = self.get_active_window() or ui.Window(self, self.root_fetcher)
        win.present()

    def set_request(self, request):
        self.root_fetcher.request = request
        win = self.get_active_window()
        if win:
            win.select_entry()

    def close_window(self):
        win = self.get_active_window()
        if win:
            win.destroy()

    def quit(self, *args):
        logger.debug("Quit")
        super().quit()
        return True
