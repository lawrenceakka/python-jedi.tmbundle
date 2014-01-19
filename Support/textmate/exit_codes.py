# coding = utf-8
""" Exit codes """
from sys import exit, stdout


def exit_discard():
    exit(200)


def exit_replace_text(out=None):
    if out is not None: stdout.write(out)
    exit(201)


def exit_replace_document(out=None):
    if out is not None: stdout.write(out)
    exit(202)


def exit_insert_text(out=None):
    if out is not None: stdout.write(out)
    exit(203)


def exit_insert_snippet(out=None):
    if out is not None: stdout.write(out)
    exit(204)


def exit_show_html(out=None):
    if out is not None: stdout.write(out)
    exit(205)


def exit_show_tool_tip(out=None):
    if out is not None: stdout.write(out)
    exit(206)


def exit_create_new_document(out=None):
    if out is not None: stdout.write(out)
    exit(207)
