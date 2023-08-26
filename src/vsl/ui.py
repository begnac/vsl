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
from gi.repository import Gdk
from gi.repository import Gtk

import re
import weakref

from . import logger
from . import items
from . import __program_name__, __version__


class HeaderBar(Gtk.HeaderBar):
    def __init__(self):
        self.title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(css_classes=['title'], label=__program_name__)
        self.subtitle = Gtk.Label(css_classes=['subtitle'], label=__version__)
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
        box.title = Gtk.Label(halign=Gtk.Align.START, css_classes=['item-title'])
        box.detail = Gtk.Label(halign=Gtk.Align.START, css_classes=['item-detail'])
        box.score = Gtk.Label(halign=Gtk.Align.END, css_classes=['item-detail'])
        box2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        box3 = Gtk.Box()

        box.append(box.icon)
        box.append(box2)
        box2.append(box.title)
        box2.append(box3)
        box3.append(box.detail)
        box3.append(Gtk.Label(label=" ", hexpand=True))
        box3.append(box.score)

        listitem.set_child(box)

    @staticmethod
    def bind_cb(self, listitem):
        scored_item = listitem.get_item()
        item = scored_item.item
        box = listitem.get_child()
        box.title.set_label(item.format_title())
        box.detail.set_label(item.detail)
        box.score.set_label(f"({scored_item.score})")

        if item.icon is None:
            return
        elif isinstance(item.icon, str):
            icon = Gio.ThemedIcon(name=item.icon + '-symbolic')
        elif isinstance(item.icon, Gio.ThemedIcon):
            names = item.icon.get_names()
            icon = Gio.ThemedIcon.new_from_names([name + '-symbolic' for name in names] + names)
        else:
            icon = item.icon
        box.icon.set_from_gicon(icon)

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
        self.view = Gtk.ListView(model=self.selection, factory=Factory(), tab_behavior=Gtk.ListTabBehavior.CELL)
        self.append(self.view)

        self.entry.connect('activate', self.activate_entry_cb, self.selection)
        self.view.connect('activate', self.activate_view_cb, self.entry)

    def __del__(self):
        logger.debug(f'Deleting {self}')

    @staticmethod
    def activate_item(item, entry):
        if isinstance(item, items.ItemChangeRequest):
            old_request = entry.get_buffer().get_text()
            new_request = re.sub(item.pattern, item.repl, old_request)
            entry.get_buffer().set_text(new_request, -1)
            entry.grab_focus()
            entry.get_first_child().emit('move-cursor', Gtk.MovementStep.BUFFER_ENDS, 1, False)
        else:
            item.activate()
            Gio.Application.get_default().close_window()

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
        self.headerbar = HeaderBar()
        self.request_box = RequestBox(fetcher.reply)
        self.request_box.selection.connect('items-changed', self.items_changed_cb, weakref.ref(self))

        app.bind_property('request', self.request_box.entry.get_buffer(), 'text', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.focus_request()

        super().__init__(titlebar=self.headerbar, child=self.request_box, application=app)

        self.connect('close-request', lambda self_: self_.destroy() or True)

    def __del__(self):
        logger.debug(f'Deleting {self}')

    @staticmethod
    def items_changed_cb(model, position, removed, added, self):
        self = self()
        self.set_default_size(0, 0)
        self.request_box.view.scroll_to(0, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)

    def focus_request(self):
        self.request_box.entry.grab_focus()
