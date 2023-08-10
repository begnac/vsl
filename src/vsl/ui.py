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
from gi.repository import GdkPixbuf
from gi.repository import Gdk
from gi.repository import Gtk

from . import logger


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
        box.titlebox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        box.title = Gtk.Label(halign=Gtk.Align.START, css_classes=['item-title'])
        box.subtitle = Gtk.Label(halign=Gtk.Align.START, css_classes=['item-subtitle'])

        box.append(box.icon)
        box.append(box.titlebox)
        box.titlebox.append(box.title)
        box.titlebox.append(box.subtitle)

        listitem.set_child(box)

    @staticmethod
    def bind_cb(self, listitem):
        item = listitem.get_item()
        box = listitem.get_child()
        if item.icon is None:
            pass
        elif isinstance(item.icon, str):
            box.icon.set_from_icon_name(item.icon)
        elif isinstance(item.icon, GdkPixbuf.Pixbuf):
            box.icon.set_from_pixbuf(item.icon)
        else:
            raise ValueError
        box.title.set_label(f'{item.title} ({item.score})')
        # box.title.set_label(item.title)
        box.subtitle.set_label(item.subtitle)

    # @staticmethod
    # def unbind_cb(self, item):
    #     pass

    @staticmethod
    def teardown_cb(self, item):
        item.set_child(None)


class RequestBox(Gtk.Box):
    def __init__(self, fetcher_):
        self.fetcher = fetcher_

        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.entry = Gtk.Entry(css_classes=['request'])
        self.append(self.entry)

        self.fetcher.bind_property('request', self.entry.get_buffer(), 'text', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)

        self.selection = Gtk.SingleSelection(model=self.fetcher.reply)
        self.view = Gtk.ListView(model=self.selection, factory=Factory())
        self.append(self.view)

        self.entry.connect('activate', self.activate_entry_cb, self.view)
        self.view.connect('activate', self.activate_view_cb)
        self.selection.connect('items-changed', lambda model, position, removed, added: model.set_selected(0))

    def __del__(self):
        logger.debug(f'Deleting {self}')

    @staticmethod
    def activate_entry_cb(entry, view):
        model = view.get_model()
        for i in range(len(model)):
            if model.is_selected(i):
                model[i].activate()
                break

    @staticmethod
    def activate_view_cb(view, position):
        view.get_model()[position].activate()


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


class CssProvider(Gtk.CssProvider):
    CSS = '''
    label.item-title {
      font-size: larger;
    }
    label.item-subtitle {
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
        self.request_box = RequestBox(fetcher)
        self.select_entry()

        super().__init__(titlebar=self.headerbar, child=self.request_box, application=app)

        self.connect('close-request', lambda self_: self_.destroy() or True)

    def __del__(self):
        logger.debug(f'Deleting {self}')

    def destroy(self):
        self.fetcher.reply.disconnect_by_func(self.items_changed_cb)
        super().destroy()

    def items_changed_cb(self, model, position, removed, added):
        self.set_default_size(0, 0)

    def select_entry(self):
        self.request_box.entry.select_region(0, -1)
