# coding: utf-8
""" A wrapper around tm_query

Query tm settings

"""
import os
import subprocess

tm_query = os.environ['TM_QUERY']


def query(key=''):
    """Return the tm setting represented by 'key', or all settings """
    return subprocess.check_output([tm_query, '--setting' if key else '', key])
