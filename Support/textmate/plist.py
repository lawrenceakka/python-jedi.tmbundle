# coding: utf-8
""" A wrapper around Pyton's plistlib to allow reading and writing of TM
format plist files.

"""
import os
import plistlib
import subprocess
from xml.parsers.expat import ExpatError

# This bundle must list the Property List Bundle as a requirement so that
# TM_PROPERTY_LIST_BUNDLE_SUPPORT is available.  i.e, its info.plist should
# contain:
# <array>
#     <dict>
#         <key>name</key>
#         <string>Property List</string>
#         <key>uuid</key>
#         <string>467A3CB0-6227-11D9-BFB1-000D93589AF6</string>
#     </dict>
# </array>

pretty_list = os.environ['TM_PROPERTY_LIST_BUNDLE_SUPPORT'] + '/bin/pretty_plist'


def to_string(data):
    return plistlib.writePlistToString(data)

def from_string(string):
    try:
        return plistlib.readPlistFromString(string)
    except ExpatError:
        # string must have contained a TM format plist, which cannot be
        # parsed. Try converting it using pretty_list
        proc = subprocess.Popen([pretty_list, '-a'],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE
                                )

        string, _ = proc.communicate(string)
        print string
        return plistlib.readPlistFromString(string)
