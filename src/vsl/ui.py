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
from gi.repository import GdkPixbuf
from gi.repository import Gdk
from gi.repository import Gtk

import re

from . import logger
from . import items


class HeaderBar(Gtk.HeaderBar):
    def __init__(self):
        self.title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(css_classes=['title'], label='Title')
        self.subtitle = Gtk.Label(css_classes=['subtitle'], label='Subtitle')
        self.title_box.append(self.title)
        self.title_box.append(self.subtitle)
        super().__init__(title_widget=self.title_box)

    def __del__(self):
        logger.debug(f'Deleting {self}')


class Factory(Gtk.SignalListItemFactory):
    def __init__(self):
        super().__init__()

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        # self.connect('unbind', self.unbind_cb)
        self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        box = Gtk.Box(css_name='item-box')
        box.icon = Gtk.Image(icon_size=Gtk.IconSize.LARGE)
        box2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        box.title = Gtk.Label(halign=Gtk.Align.START, css_classes=['item-title'])
        box.detail = Gtk.Label(halign=Gtk.Align.START, css_classes=['item-detail'])

        box.append(box.icon)
        box.append(box2)
        box2.append(box.title)
        box2.append(box.detail)

        listitem.set_child(box)

    @staticmethod
    def bind_cb(self, listitem):
        scored_item = listitem.get_item()
        item = scored_item.item
        box = listitem.get_child()
        if item.icon is None:
            pass
        elif isinstance(item.icon, str):
            box.icon.set_from_icon_name(item.icon)
        elif isinstance(item.icon, Gio.Icon):
            box.icon.set_from_gicon(item.icon)
        elif isinstance(item.icon, GdkPixbuf.Pixbuf):
            box.icon.set_from_pixbuf(item.icon)
        else:
            raise ValueError
        box.title.set_label(f'{item.format_title()} ({scored_item.score})')
        box.detail.set_label(item.detail)

    # @staticmethod
    # def unbind_cb(self, item):
    #     pass

    @staticmethod
    def teardown_cb(self, item):
        item.set_child(None)


class RequestBox(Gtk.Box):
    def __init__(self, model):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.entry = Gtk.Entry(css_classes=['request'])
        self.append(self.entry)

        self.selection = Gtk.SingleSelection(model=model)
        self.view = Gtk.ListView(model=self.selection, factory=Factory())
        self.append(self.view)

        self.entry.connect('activate', self.activate_entry_cb, self.selection)
        self.view.connect('activate', self.activate_view_cb, self.entry)
        self.selection.connect('items-changed', lambda model, position, removed, added: model.set_selected(0))

    def __del__(self):
        logger.debug(f'Deleting {self}')

    @staticmethod
    def activate_item(item, entry):
        if isinstance(item, items.ItemChangeRequest):
            old_request = entry.get_buffer().get_text()
            new_request = re.sub(item.pattern, item.repl, old_request)
            entry.get_buffer().set_text(new_request, -1)
        else:
            item.activate()
        entry.grab_focus()

    @staticmethod
    def activate_entry_cb(entry, model):
        for i in range(len(model)):
            if model.is_selected(i):
                RequestBox.activate_item(model[i].item, entry)
                break

    @staticmethod
    def activate_view_cb(view, position, entry):
        RequestBox.activate_item(view.get_model()[position].item, entry)


class CssProvider(Gtk.CssProvider):
    CSS = '''
    label.item-title {
      font-size: larger;
    }
    label.item-detail {
      font-size: smaller;
      color: rgba(0.5,0.5,0.5,0.5);
    }
    entry.request {
      font-size: 250%;
    }
    '''

    def __init__(self):
        super().__init__()
        self.load_from_data(self.CSS, -1)

    def add_myself(self):
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class Window(Gtk.ApplicationWindow):
    def __init__(self, app, fetcher):
        self.fetcher = fetcher
        fetcher.reply.connect('items-changed', self.items_changed_cb)

        self.headerbar = HeaderBar()
        self.request_box = RequestBox(fetcher.reply)
        app.bind_property('request', self.request_box.entry.get_buffer(), 'text', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.focus_request()

        super().__init__(titlebar=self.headerbar, child=self.request_box, application=app)

        self.connect('close-request', lambda self_: self_.destroy() or True)

    def __del__(self):
        logger.debug(f'Deleting {self}')

    def destroy(self):
        self.fetcher.reply.disconnect_by_func(self.items_changed_cb)
        super().destroy()

    def items_changed_cb(self, model, position, removed, added):
        self.set_default_size(0, 0)

    def focus_request(self):
        self.request_box.entry.grab_focus()
