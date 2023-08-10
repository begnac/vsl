# vsl - Very Simple Launcher

A launcher, similar to `albert` or `kupfer`, written in Python/Gtk4.

At this point this is merely a proof-of-concept.
- There are two kinds of objects:
  + An `Item` object represents an action that the launcher can perform.
  + A `Fetcher` object fetches `Item`s for a request (a string).
- A tree of fetchers is constructed in `src/vsl/root.py`.
- Requests are propagated from the root by calling the fetchers' `do_request` method.
- A fetcher's reply is represented is stored in its `reply` attribute, a `Gio.ListModel` of `Item`s.
  Replies flow down to the root using Gtk4's various `ListModel` implementations (`FilterListModel` etc.)


## Requirements

- Python 3
- PyGObject
- GLib and Gtk4 Python GObject Introspection
- Python packages:
  * gasyncio
  * aiosqlite
