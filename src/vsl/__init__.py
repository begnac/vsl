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


import gi
import gettext


gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')


from gi.repository import Gtk  # noqa: E402


__application__ = __name__
__author__ = "Itaï BEN YAACOV"
__copyright__ = "© " + __author__
__website__ = f'https://github.com/begnac/{__application__}'

__license_type__ = Gtk.License.GPL_3_0
__program_name__ = "Very Simple Launcher"
__version__ = '0.0.1'

gettext.install(__application__)
