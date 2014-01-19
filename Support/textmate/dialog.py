#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import subprocess
from textmate import plist

dialog = os.environ["DIALOG"]


def _call_dialog(command, *args):
    """ Call the Textmate Dialog process

    command is the command to invoke.
    args are the strings to pass as arguments
    a dict representing the plist returned from DIALOG is returned

    """
    popen_args = [dialog, command]
    popen_args.extend(args)
    result = subprocess.check_output(popen_args)
    return plist.from_string(result) if result else {}


def popup(suggestions, already_typed="", static_prefix="", extra_chars="",
            case_insensitive=False, return_choice=False):
    """ Popup an autocomplete menu.

    suggestions is a list strings or 2-tuples to display. A string, if matched
    will be inserted as-is. If the first element of a 2-tuple is matched, the
    second element will be inserted.
    """

   # --returnChoice
    def item(val):
        if isinstance(s, tuple):
            return {'display': val[0], 'insert': val[1]}
        return {'display': val}
    d = [item(s) for s in suggestions]
    p = plist.to_string(d)
    return _call_dialog('popup', '--suggestions', p,
                 '--alreadyTyped', already_typed,
                 '--staticPrefix', static_prefix,
                 '--additionalWordCharacters', extra_chars,
                 '--returnChoice' if return_choice else ''
                 '--caseInsensitive' if case_insensitive else '')


def insert(text, snippet=False):
    """Tries to insert text into the frontmost text view. If snippet is True,
    insert text as a snippet and set the key focus to the current document.

    """
    # This is not part of the public API, but is useful in conjunction with popup:
    # http://lists.macromates.com/textmate-dev/2012-September/014803.html
    # and
    # https://github.com/textmate/dialog/pull/4
    _call_dialog('x-insert', '--snippet' if snippet else '--text', text)


def alert(style='warning', title='Alert', message='', buttons=()):
    """ Present an alert.

    style is one of 'warning', 'information', or 'critical'
    title and message are strings
    buttons is a tuple of button names. If no buttons are specified,
    an OK button will be dislayed, and will have index -1000

    return the index of the button clicked

    """
    if not style in ('warning', 'information', 'critical'):
        raise KeyError(
            "style must be one of 'warning', 'information' or 'critical'")
    button_args = []
    for b in enumerate(buttons, start=1):
        button_args.extend(['--button{}'.format(b[0]), b[1]])
    args = ['--alertStyle', style,
            '--title',      title,
            '--body',       message]
    args.extend(button_args)
    result = _call_dialog('alert', *args)
    return result.get('buttonClicked')


def tooltip(text='', format='text',  transparent=False):
    """Display a tooltip containing text

    format may be 'text' or 'html'
    transparent is True or False
    """
    if not format in ('text, html'):
        raise KeyError("format must be 'text' or 'html'")
    _call_dialog('tooltip', '--{}'.format(format), text,
        '--transparent' if transparent else '')


def menu(options):
    """ Accept a list and causes TextMate to show an inline menu.

    The members of the list are interpreted and shown as follows:

    string: a menu item
    None: a separator
    list with a single string member: a header (eg ['header'])

    Return the title of the menu item chosen by the user (or None)
    """
    # Adapted from https://github.com/textmate/bundle-support.tmbundle/blob/master/Support/shared/lib/dialog.py

    def item(val):
        if isinstance(val, basestring):
            return {"title": val}
        if isinstance(val, list):
            return {"header": 1, 'title': val[0]}
        elif val is None:
            return {"separator": 1}

    if not options:
        return None
    menu = [item(thing) for thing in options]
    p = plist.to_string(menu)
    result = _call_dialog('menu', '--items', p)
    return result.get('title')


# IMAGES:
# "$DIALOG" images --register "{ macro = '/path to file.png'; }"
#
# "$DIALOG" popup --suggestions '( { image = macro; display = foo; }, { display
# = bar; } )'

# see: https://github.com/textmate/dialog/commit/8998009b
