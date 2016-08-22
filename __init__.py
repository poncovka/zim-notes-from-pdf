# -*- coding: utf-8 -*-

# Author: Vendula Poncova <poncovka@gmail.com>
# File: __init__.py
#
# Description: 
# This plugin for Zim allows to make quick notes from PDF files.
#

from zim.plugins import PluginClass
from zim.gui.widgets import RIGHT_PANE, PANE_POSITIONS

from .gui import MainWindowExtension, get_keys

# depends on python-poppler package
import poppler

def check_keys(value, default):
    
    klass = default.__class__
    if issubclass(klass, basestring):
        klass = basestring

    if value in ('', None):
        return value
    if isinstance(value, klass) and get_keys(value) :
        return value
    elif klass is tuple and isinstance(value, list):
        return tuple(value)
    else:
        raise AssertionError, 'should be a shortcut'

class PDFNotesPlugin(PluginClass):

    plugin_info = {
        'name': _('Notes from PDF'),
        'description': _('''Enables to open PDF files and copy lines and blocks of texts to Zim pages. It is also possible to select a part of the PDF file and insert it to the Zim page as a picture. Requred python-poppler. Warning: PDF is messy, so the text you get might be too.'''),
        'author': 'Vendula Poncova',
        'help': 'Plugins:pdfnotes',
    }
    
    plugin_preferences = (
        # key, type, label, default
        ('pane_position', 'choice', _('Position in the window'), RIGHT_PANE, PANE_POSITIONS),
        ( 'image_width', 'int', _('Max image width in px'), 1024, (1, 10000)),
        ( 'image_height', 'int', _('Max image height in px'), 1024, (1, 10000)),
        ( 'switch_mode', 'string', _('Shortcut for switching selecting modes'), 'Control_R', check_keys),
    )
# 
#     @classmethod
#     def check_dependencies(klass):
#         # TODO
#         '''Checks what dependencies are met and gives details
# 
#         @returns: a boolean telling overall dependencies are met,
#         followed by a list with details.
# 
#         This list consists of 3-tuples consisting of a (short)
#         description of the dependency, a boolean for dependency being
#         met, and a boolean for this dependency being optional or not.
# 
#         @implementation: must be implemented in sub-classes that have
#         one or more (external) dependencies.
#         '''
#         return (True, [])
        
# end of file __init__.py
