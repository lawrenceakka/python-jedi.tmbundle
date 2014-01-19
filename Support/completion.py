# coding: utf-8
# TODO:scope could be meta.function-call.python when just after (


import os
import sys
import subprocess
import re
import io

env = os.environ
support_path = env['TM_BUNDLE_SUPPORT']
sys.path.insert(0, support_path)
from textmate import dialog, tm_query, plist, exit_codes

sys.path.insert(0, support_path + b'/jedi')
import jedi
jedi.settings.case_insensitive_completion = False
jedi.settings.add_bracket_after_function = True


def get_script():
    """ Get the Jedi script object from the source passed on stdin, or none"""
    source = ''.join(sys.stdin.readlines()) or None
    script = None
    try:
        line = int(env['TM_LINE_NUMBER'])
        col = int(env['TM_COLUMN_NUMBER']) - 1
        encoding = tm_query.query('encoding')
        path = env('TM_FILE_PATH') if not source else None
        script = jedi.Script(source, line, col, path, encoding=encoding)
    except (AttributeError, KeyError):
        pass
    return script


def get_completions():
    """ Retrieve completions from Jedi, or return an empty list """
    script = get_script()
    if script is None:
        return []
    return [s.name for s in script.completions()]


def show_completions():
    """ Show completions in a popup. """
    completions = get_completions()
    typed = env.get('TM_CURRENT_WORD', '').lstrip('.')
    if len(completions) == 1:
        # There is only one completion. Insert it.
        sys.stdout.write(completions[0][len(typed):])
    elif completions is not []:
        # Python identifiers can contain _, so completions may contain it
        dialog.popup(completions, already_typed=typed, extra_chars="_")


def show_signature():
    """ Retrieve relevant function signatures and show them in a tooltip. """
    script = get_script()
    if script is None:
        return
    signatures = script.call_signatures()
    text = []
    if signatures is not None:
        for s in signatures:
            args = [p.get_code().replace('\n', '') for p in
                        getattr(s, 'params', None) if p]
            args = ", ".join(args)
            text.append("{call_name}({args})".format(
                call_name=s.call_name, args=args))
    dialog.tooltip("\n".join(text))


def goto_definition():
    """ Jump to the first defintion of the term under the cursor. """
    script = get_script()
    if script is None:
        return
    try:
        definitions = script.goto_definitions()
    except jedi.NotFoundError:
        exit_codes.exit_show_tool_tip('No definition found')
    if definitions:
        definition = definitions[0]
        path = definition.module_path
        if definition.in_builtin_module:
            exit_codes.exit_show_tool_tip('Cannot jump to builtin module')
        line = str(definition.line or 1)
        column = str(definition.column)
        #mate = env['TM_SUPPORT_PATH'] + b"/bin/mate"
        url = b"txmt://open/?url=file://{path}&line={line}&column={column}".format(
            path=path, line=line, column=column)
        subprocess.call(['open', url])


def show_docstrings():
    script = get_script()
    if script is None:
        return
    try:

        def hex_to_rgba(value):
            value = value.lstrip('#')
            lv = len(value)
            if lv == 3:
                result = tuple(int(value[i:i+1], 16)*17 for i in (0, 1, 2)) + (1,)
            if lv == 6:
                result = tuple(int(value[i:i+2], 16) for i in (0, 2, 4)) + (1,)
            if lv == 8:
                result = tuple(int(value[i:i+2], 16) for i in (0, 2, 4)) + (int(
                    value[6:], 16) / 255.0,)
            return "rgba({0}, {1}, {2}, {3:.1f})".format(*result)

        definitions = script.goto_definitions()
        docs = ['<b>Docstring for %s</b></br>%s</br>%s' % (d.desc_with_module,
            '='*40, d.doc) if d.doc else '|No Docstring for %s|' % d
                 for d in definitions]
        contents = ('\n' + '-' * 79 + '\n').join(docs)

        # Provides CSS-friendly variations of common Mac fonts that you
        # may use in TextMate. Feel free to edit these to your liking...
        # Adapted from https://github.com/textmate/textmate.tmbundle/blob/master/Support/lib/doctohtml.rb
        FONT_MAP = [
            (r'\bcourier\b', 'Courier, "MS Courier New"'),
            (r'\bbitstream.*mono\b', '"Bitstream Vera Sans Mono"'),
            (r'\bandale\b', '"Andale Mono"'),
            (r'\bDejaVuSansMono\b', '"DejaVu Sans Mono"')
            ]

        theme_path = os.environ['TM_CURRENT_THEME_PATH']
        tm_query = os.environ['TM_QUERY']
        font_name = subprocess.check_output([tm_query, '--setting', 'fontName']).rstrip() or "Menlo-Regular"
        font_size = subprocess.check_output([tm_query, '--setting', 'fontSize']).rstrip() or "12"
        # remove any digits at the end
        font_name = re.sub('\.\d+$', '', font_name, re.I)
        #font_name = "'" + font_name + "'" if font_name.include?(' ') &amp;&amp;
        #        !font_name.include?('"')

        for fonts in FONT_MAP:
            if re.match(fonts[0], font_name):
                font_name = fonts[1]
                break

        with io.open(theme_path, 'r', encoding='utf-8') as f:
            theme_plist = f.read()
        body_bg = '#fff'
        body_fg = '#000'
        theme_plist = plist.from_string(theme_plist)
        for setting in theme_plist['settings']:
            # The general settings dict has no 'name' key
            if (not 'name' in setting and 'settings' in setting):
                body_bg = setting['settings'].get('background', '#ffffff')
                body_fg = setting['settings'].get('foreground', '#000000')
                break
        if body_fg[0] == '#': body_fg = hex_to_rgba(body_fg)
        if body_bg[0] == '#': body_bg = hex_to_rgba(body_bg)

        html = """
        <style type="text/css" media="screen">
            body {{
                padding-top: 10px;
                padding-left: 0;
            }}
            .tip {{
                font-family: {font_name}, monospace;
                font-size: {font_size}px;
                background-color: {body_bg};
                color: {body_fg};
                border: 1px solid {body_fg};
                position: relative;
                margin: 0;
                padding: 12px;
                text-align: left;
                border-radius: 5px 10px 10px 10px;
                box-shadow: 0px 5px 10px rgba(0,0,0,0.25);
            }}
            .tip:before {{
                position: absolute;
                display: inline-block;
                content: "";
                border-color: transparent transparent {body_fg} transparent;
                border-style: solid;
                border-width: 10px;
                height:0;
                width:0;
                top:-20px;
                left:2px;
            }}
            .tip:after {{
                position: absolute;
                display: inline-block;
                content: "";
                border-color: transparent transparent {body_bg} transparent;
                border-style: solid;
                border-width: 10px;
                height:0;
                width:0;
                top:-18px;
                left:2px;
            }}

        </style>
        <div class="tip">
        {contents}
        </div>
        """
        html = html.format(font_name=font_name, font_size=font_size,
                body_bg=body_bg, body_fg=body_fg, contents=contents)

        dialog.tooltip(html, format='html', transparent=True)
        exit_codes.exit_discard()

    except jedi.NotFoundError:
        dialog.tooltip('No documentation found')
