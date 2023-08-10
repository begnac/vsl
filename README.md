# vsl - Very Simple Launcher

A launcher, similar to `albert` or `kupfer`, written in Python/Gtk4.

At this point this is merely a proof-of-concept.
- A pipeline of fetchers is constructed (see `src/vsl/root.py` for an example that can be modified).
- A `Fetcher` is a `GObject.Object` with the following properties:
  + `request` of type `str` is what the user is looking for.
  + `reply` of a type implementing `Gio.ListModel` contains a list of `Item`s found.
- Requests are sent down the pipeline by setting the `request` property.
- Replies are sent up using Gtk4's various `ListModel` implementations (`FilterListModel` etc.)

## Requirements

- Python 3
- PyGObject
- GLib and Gtk4 Python GObject Introspection
- Python packages:
  * gasyncio
  * aiosqlite
