# -*- coding: utf-8 -*-

# Author: Vendula Poncova <poncovka@gmail.com>
# File: gui.py
#
# Description: 
# Widget for PDF Notes plugin.
#

# TODO :
# * application exits when I try to unload the plugin, similar with other plugins

from __future__ import with_statement

import gtk
import logging
import cairo
import time
import os
import re

from zim.plugins import extends, WindowExtension
from zim.gui.widgets import WindowSidePaneWidget, ScrolledWindow, InputEntry, IconButton, FileDialog, gtk_combobox_set_active_text
from zim.gui.pageview import SCROLL_TO_MARK_MARGIN
from zim.fs import File

from .model import PDFDocument

logger = logging.getLogger(__name__)

def get_keys(value):
    
    keys = ''.join(value.split()).split('+')
    
    for key in keys :        
        if gtk.gdk.keyval_from_name(key) == 0 :
            return False
        
    return set(keys)

@extends('MainWindow')
class MainWindowExtension(WindowExtension):

    TAB_NAME = _('Notes from PDF')

    def __init__(self, plugin, window):     
        # initialize
        WindowExtension.__init__(self, plugin, window)
        self.preferences = plugin.preferences
        self.uistate = plugin.uistate
        
        # widget initialize
        self.widget = None
        self.connect_widget()
        
        # signals
        self.connectto(plugin, 'preferences-changed')
        
    def connect_widget(self):  
        logger.debug('PDF Notes: connect_widget')   
        
        # create widget
        if self.widget == None :    
            self.widget = PDFNotesWidget(self, 
                                         self.window.ui,
                                         self.preferences)
        else:
            self.window.remove(self.widget)
                   
        # connect widget as tab    
        self.window.add_tab(self.TAB_NAME, self.widget, self.preferences['pane_position'])        
        # show widget
        self.widget.show_all()
                
    def disconnect_widget(self):
        logger.debug('PDF Notes: disconnect_widget')
        
        if self.widget != None :
            self.window.remove(self.widget)
            self.widget.destroy()
            self.widget = None
    
    def on_preferences_changed(self, plugin):
        logger.debug('PDF Notes: on_preferences_changed')
        self.connect_widget()
            
    def destroy(self):
        logger.debug('PDF Notes: destroy')
        
        self.disconnect_widget()
        WindowExtension.destroy(self)
        

class PDFNotesWidget(gtk.VBox, WindowSidePaneWidget):

    SELECT_TEXT  = _('Select paragraph')
    SELECT_LINE  = _('Select text')
    SELECT_IMAGE = _('Select image')
    ZOOM_SETTING = _('Zoom')
    ZOOM_FIT     = _('Fit width')

    def __init__(self, extension, ui, preferences):
        gtk.VBox.__init__(self)

        # state
        self.extension = extension # XXX
        self.ui = ui
        self.uistate = extension.uistate
        self.preferences = preferences
        
        self.drag = False
        self.whitespace = False
        self.zoom = None
        
        # position, size, scale, ...
        self.boundary = gtk.gdk.Rectangle(0,0,0,0)
        self.width, self.height = 0, 0
        self.x, self.y = 0, 0
        self.scale = 1
        self.img_scale = None
        
        # document to view
        self.document = PDFDocument()
        
        # colors
        self.color_sea = (0.31, 0.61, 0.71, 1.0)
        self.color_sea_light = (0.31, 0.61, 0.71, 0.4)
        self.color_blue = (0.15, 0.68, 0.9, 1.0)
        
        # pressed keys
        self.keys = set()
        
        # selection
        self.selection_style = self.SELECT_LINE
        self.unselect()
        
        # cursor
        self.cursor_in = gtk.gdk.Cursor(gtk.gdk.HAND1)
        
        # user interface
        self.set_ui()
        
        
    def set_ui(self):
        
        # widget pane
        pane = gtk.VBox(False, 2)
        
        # toolbar
        toolbar = gtk.HBox()

        # toolbar - buttons
        open_button = IconButton(gtk.STOCK_OPEN, False)
        open_button.connect('clicked', self.on_open_file)
        
        up_button = IconButton(gtk.STOCK_GO_UP, False)
        up_button.connect('clicked', self.on_page_up)
        
        down_button = IconButton(gtk.STOCK_GO_DOWN, False)
        down_button.connect('clicked', self.on_page_down)
        
        # toolbar - page number
        self.page_entry =  InputEntry()
        self.page_entry.set_text('0')
        self.page_entry.set_width_chars(4)
        self.page_entry.connect('activate', self.on_page_number_change)
        self.page_label = gtk.Label(' out of 0')
        
        # toolbar - separator
        separator = gtk.VSeparator()
        
        # toolbar - zoom setting
        self.zoom_button = gtk.combo_box_new_text()
        self.zoom_button.connect('changed', self.on_zoom)
        
        # toolbar - zoom options
        self.zoom_options = {}
 
        for item in (self.ZOOM_SETTING, self.ZOOM_FIT) :
            self.zoom_button.append_text(item)
        
        for item in range(20, 100, 20) + range(100, 450, 100) :
            self.zoom_options[str(item) + '%'] = item
            self.zoom_button.append_text(str(item) + '%')
            
        gtk_combobox_set_active_text(self.zoom_button, self.ZOOM_FIT)
        
        # toolbar - separator
        separator_2 = gtk.VSeparator()
        
        # toolbar - selection menu
        self.selection_button = gtk.combo_box_new_text()
        self.selection_button.connect('changed', self.on_selection_changed)
        
        # toolbar / selection options
        for option in (self.SELECT_LINE, self.SELECT_IMAGE) :
            self.selection_button.append_text(option)
            
        gtk_combobox_set_active_text(self.selection_button, self.selection_style)
        
        self.switch_button = gtk.Button()
        self.switch_button.connect('clicked', self.on_selection_switch)
        
        icon = gtk.Image()
        icon.set_from_file('./plugins/pdfnotes/image.png')
        self.switch_button.set_image(icon)
        self.switch_button.set_label('switch')
        
        # toolbar - button for scaling pictures
        img_button = IconButton(gtk.STOCK_ZOOM_FIT, False)
        img_button.connect('clicked', self.on_image_scale)

        # toolbar - pack all
        
        toolbar.pack_start(open_button, False, False, 0)
        toolbar.pack_start(up_button, False, False, 0)
        toolbar.pack_start(down_button, False, False, 0)
        toolbar.pack_start(self.page_entry, False, False, 0)
        toolbar.pack_start(self.page_label, False, False, 0)
        toolbar.pack_start(separator, False, False, 8)
        toolbar.pack_start(self.zoom_button, False, False, 0)
        toolbar.pack_start(separator_2, False, False, 8)
        toolbar.pack_start(self.selection_button, False, False, 0)
        #toolbar.pack_start(self.switch_button, False, False, 0)
        toolbar.pack_start(img_button, False, False, 0)
        
        pane.pack_start(toolbar, False, False, 0)

        # drawing area
         
        self.drawing_area = gtk.DrawingArea()
        
        self.drawing_area.connect("expose-event", self.on_expose)
        self.drawing_area.connect("motion-notify-event", self.on_motion)
        self.drawing_area.connect("button_press_event", self.on_button_press)
        self.drawing_area.connect("button_release_event", self.on_button_release)
        
        self.drawing_area.add_events(  gtk.gdk.LEAVE_NOTIFY_MASK
                                     | gtk.gdk.BUTTON_PRESS_MASK
                                     | gtk.gdk.BUTTON_RELEASE_MASK
                                     | gtk.gdk.POINTER_MOTION_MASK
                                     | gtk.gdk.POINTER_MOTION_HINT_MASK
                                     | gtk.gdk.KEY_PRESS_MASK
                                     | gtk.gdk.SCROLL_MASK)
        
        alignment = gtk.Alignment(xalign=0.5, yalign=0.5, xscale=0.0, yscale=0.0)
        alignment.add(self.drawing_area)
                
        self.viewport = gtk.Viewport()
        self.viewport.add(alignment)
         
        self.scrolled_w = ScrolledWindow(self.viewport)
        self.scrolled_w.connect("size-allocate", self.on_resize)
        self.scrolled_w.connect("scroll-event", self.on_scroll)
        
        # widget pane - pack all        
        self.ui.mainwindow.connect('key-press-event', self.on_key_press)
        self.ui.mainwindow.connect('key-release-event', self.on_key_release)
        
        pane.pack_start(self.scrolled_w, True, True, 0)
        
        self.add(pane)
        self.show_all()
    
    def unselect(self):
        logger.debug('PDF Notes: unselect')
  
        # forget the selection
        self.selected_text = None
        self.selected_area = list()
        
        # set the default text selection style
        if self.selection_style == self.SELECT_TEXT:
            self.selection_style = self.SELECT_LINE
       
    def point_in_area(self, x, y, area):
        
        # for all areas
        for x1, y1, x2, y2 in area:
            # check boundaries
            if  x1 <= x and y1 <= y and x2 >= x and y2 >= y :
                return True
            
        # point is not in the area
        return False
       
    def on_open_file(self, *e):
        logger.debug('PDF Notes: open file')
        
        # open dialog for choosing pdf file
        dialog = FileDialog(self.window, _('Select PDF file'))
        # set filter
        filter = dialog.add_filter( '*.pdf', '*.pdf')
        # run dialog and get file
        file = dialog.run()
        # proceed file
        if file :
            # set document
            self.document.set_file(file)
            # update widget
            self.unselect()
            self.update()

    def on_page_down(self, *e):
        logger.debug('PDF Notes: show next page')
        
        # try to set page
        if self.document.next_page() :    
            # update widget
            self.unselect()
            self.update()
            return True
        
        return False
    
    def on_page_up(self, *e):
        logger.debug('PDF Notes: show previous page')
        
        # try to set page
        if self.document.prev_page() :
            # widget update
            self.unselect()
            self.update()
            return True
        
        return False
      
    def on_expose(self, widget, event, *e):
        self.draw(widget, event)

    def on_page_number_change(self, *e):
        logger.info('PDF Notes: change of page entry')
        
        # get new number of current page
        try:
            page_number = int(self.page_entry.get_text()) - 1 
        except ValueError:
            logger.exception('PDF Notes: cannot convert page number to int')
            return
        
        # try to set page
        if self.document.set_page(page_number) :
            # update widget
            self.unselect() 
            self.update()

    def on_resize(self, widget, allocation, *e):
        
        if allocation != self.boundary :
            
            logger.debug('PDF Notes: resize')
            self.boundary = allocation
            self.update()
        
    def on_zoom(self, *e):
        logger.debug('PDF Notes: zoom changed')
        
        # get zoom from toolbar
        key = self.zoom_button.get_active_text()
        
        # nothing
        if key == self.ZOOM_SETTING :
            return
        
        # fit width
        elif key == self.ZOOM_FIT :
            self.zoom = None
            
        # zoom
        elif key in self.zoom_options :
            self.zoom = self.zoom_options[key]
        
        # update widget
        self.update()

    def on_selection_switch(self, *e):
        pass
        
    def on_selection_changed(self, *e):
        logger.debug('PDF Notes: selection changed')
        
        # get selection type from toolbar
        
        style = self.selection_button.get_active_text()
        if style != self.selection_style :
        
            self.selection_style = style
            self.unselect()
            self.redraw()
    
    def on_image_scale(self, *e) :       
        self.img_scale = self.scale
        
    def on_motion(self, widget, event, *e):
        logger.debug('PDF Notes: motion x=%s y=%s', event.x, event.y)
        
        # get point
        x = event.x / self.scale
        y = event.y / self.scale
                
        # no file
        if not self.document.exists() :
            return      

        # setting cursor
        cursor = self.cursor_in if self.point_in_area(x, y, self.selected_area) else None
        self.drawing_area.window.set_cursor(cursor)
        
        # uniting select line and select text modes
        if self.selection_style == self.SELECT_LINE and self.drag :
            self.selection_style = self.SELECT_TEXT
                
        logger.debug('PDF Notes: %s', self.selection_style)
                
        # find line
        if self.selection_style == self.SELECT_LINE and not self.drag :
            
            text, area = self.document.find_line(x, y, x, y)
            
            self.selected_text = text
            self.selected_area = area
            self.redraw()

        # find text            
        elif self.selection_style == self.SELECT_TEXT and self.drag :
            
            text, area = self.document.find_text(min(self.x, x), min(self.y, y), 
                                                 max(self.x, x), max(self.y, y))
                                                 
            text = re.sub("[\n\r\f\v]", " ", text)
            
            if area :
                self.selected_text = text
                self.selected_area = area
                self.redraw()
        
        # find image
        elif self.selection_style == self.SELECT_IMAGE and self.drag:
            
            self.selected_text = None
            self.selected_area = [(min(self.x, x), min(self.y, y), max(self.x, x), max(self.y, y))]
            self.redraw()
    
    def on_button_press(self, widget, event, *e):
        logger.debug('PDF Notes: button press at x=%s y=%s', event.x, event.y)
        
        self.drag = True
        self.x = event.x / self.scale
        self.y = event.y / self.scale
            
    def on_button_release(self, widget, event, *e):
        logger.debug('PDF Notes: button release at x=%s y=%s', event.x, event.y)

        no_motion = (event.x / self.scale) == self.x and (event.y / self.scale) == self.y  
        
        # choose style
        style = self.selection_style

        if no_motion and style == self.SELECT_IMAGE:
            
            # if clicked on selected area, insert image
            if self.point_in_area(self.x, self.y, self.selected_area) :
                
                # insert image
                self.insert_image_into_notebook()
                self.insert_text_into_notebook('\n')
            
            # unselect area
            self.unselect()
        
        elif no_motion and style == self.SELECT_TEXT:
            
            # if clicked on selected area, insert text
            if self.point_in_area(self.x, self.y, self.selected_area) :
                self.insert_text_into_notebook(self.selected_text)
            
            # unselect area
            self.unselect()
            
        elif no_motion and style == self.SELECT_LINE:
            
            # if clicked on selected area, insert line
            if self.point_in_area(self.x, self.y, self.selected_area) :
                self.insert_text_into_notebook(self.selected_text)
                
            # unselect area
            else : self.unselect()
        
        self.redraw()          
                
        self.drag = False
        self.x = 0
        self.y = 0
        
    def on_scroll(self, widget, event, *e):
        logger.debug('PDF Notes: scroll')
        
        # ZOOMING
        zoom = self.scale * 100  
  
        if self.is_pressed_key('Control_L', 'Control_R' ) :
            logger.debug('PDF Notes: scroll %s ', str(event.direction))
            
            # zoom in
            if event.direction == gtk.gdk.SCROLL_UP and zoom < 400 : 
                self.zoom = zoom + 20
                 
            # zoom out
            elif event.direction == gtk.gdk.SCROLL_DOWN and zoom >= 40 :
                self.zoom = zoom - 20
            
            # nothing
            else:
                return False

            # set gui            
            gtk_combobox_set_active_text(self.zoom_button, self.ZOOM_SETTING)

            # update widget
            self.update()
            return True
            
        # NEXT PAGE
        vertical = self.scrolled_w.get_vadjustment()
        
        # top of page, move to previous
        if event.direction == gtk.gdk.SCROLL_UP and vertical.value == vertical.lower :
            
            if self.on_page_up() :
                # set scrollbar to bottom
                vertical.value = vertical.upper - vertical.page_size
            
            return True
        
        # bottom of page, move to next
        elif event.direction == gtk.gdk.SCROLL_DOWN and vertical.value == vertical.upper - vertical.page_size :
            
            if self.on_page_down() :
                # set scrollbar to top
                vertical.value = vertical.lower
            
            return True
                
    def on_key_press(self, widget, event, *e):

        # TODO - umožnit kopírovat vybrané položky
        
        # set keyname
        keyname = gtk.gdk.keyval_name(event.keyval)
        logger.debug('PDF Notes: key pressed %s + %s', str(keyname), str(self.keys))
        
        # ERROR - shortcut for more keys doesnt work
        self.keys = set()
        self.keys.add(keyname)

        # set style and unselect
        if self.change_style_on_key() :
            self.unselect()
            self.update()

    def on_key_release(self, widget, event, *e):
        
        # remove keyname
        keyname = gtk.gdk.keyval_name(event.keyval)
        logger.debug('PDF Notes: key released %s', str(keyname))
        
        if keyname in self.keys :
            self.keys.remove(keyname)
            
    def is_pressed_key(self, *keys):
        
        for key in keys :
            if key in self.keys:
                return key
            
        return None 
    
    def change_style_on_key(self):
        
        # get shortcut
        shortcut = self.preferences['switch_mode']
        
        # check shortcut
        if shortcut and get_keys(shortcut) == self.keys:
            
            # switch style
            self.switch_style()    
            return True
                   
        return False
    
    def switch_style(self):

        if self.selection_style == self.SELECT_IMAGE :
          self.selection_style = self.SELECT_LINE 
        else :
          self.selection_style = self.SELECT_IMAGE
      
    
    def insert_image_into_notebook(self):
        logger.debug('PDF Notes: insert image into notebook')
        
        # for all areas get and insert image
        for x1, y1, x2, y2 in self.selected_area:
            
            # get scale, width and height of image           
            
            width  = abs(x2 - x1)
            height = abs(y2 - y1)
            
            if width > height : scale = self.preferences['image_width'] / float(width); logger.debug('PDF Notes: W')
            else:               scale = self.preferences['image_height'] / float(height); logger.debug('PDF Notes: H')
            
            dx = -x1 * scale
            dy = -y1 * scale
            
            # set surface
            image = cairo.ImageSurface(cairo.FORMAT_RGB24, 
                                       int(width * scale),
                                       int(height * scale)
                                       )
            
            context = cairo.Context(image)
            
            # set transition and scale
            context.translate(dx, dy)
            context.scale(scale, scale)
            
            # render page at surface
            self.document.render_page(context)
            
            # create filename
            basename = os.path.basename(self.document.file.path)
            title = os.path.splitext(basename)[0]
            imgname = time.strftime( title + '_%Y-%m-%d-%H%M%S.png')
            
            # create path
            page = self.ui.page
            dir = self.ui.notebook.get_attachments_dir(page).path
            path = dir + os.path.sep + imgname
                
            # create dirs if necessary                
            if not os.path.exists(dir):
                os.makedirs(dir)
                
            # write surface to file
            with open(path, 'w') as f:
                image.write_to_png(f)
            
            # insert image into notebook            
            f = File(path)
            src = self.ui.notebook.relative_filepath(f, page)
            
            # TODO - umožnit nastavit scale vkládaných obrázků
            
            if not self.img_scale:
              attr_scale = min(scale, 700.0 / self.document.width)      
            else:  
              attr_scale = self.img_scale

            attr = {'width'  : abs(int(width * attr_scale )), 
                    'height' : abs(int(height * attr_scale ))
                    }
            
            view = self.ui.mainwindow.pageview.view
            buffer = view.get_buffer()
            buffer.insert_image_at_cursor(f, src, **attr)
            
            # scroll to cursor
            mark = buffer.get_insert()
            view.scroll_mark_onscreen(mark)
            
            # set focus
            view.grab_focus()
            
            logger.debug('PDF Notes: image inserted at %s', path)
    
    def edit_text(self, text):
        
        result = text.strip()
        
        if self.whitespace:
            result = ' '.join(text.split())

        return result
    
    def insert_text_into_notebook(self, text):
        
        logger.debug('PDF Notes: insert text into notebook')
        
        ## MAGIC, DON'T TOUCH !!!
        
        # get text buffer        
        view = self.ui.mainwindow.pageview.view
        buffer = view.get_buffer()

        # get current line
        line = buffer.get_insert_iter().get_line()
        
        # get iter at the start of the line
        iter = buffer.get_iter_at_line(line)

        # put iter behind the bullet
        if not iter.ends_line():
          buffer.iter_forward_past_bullet(iter)
                  
        # if iter doesn't end the line, create new one
        if not iter.ends_line():
        
          # add line
          iter.forward_to_line_end()
          buffer.do_insert_text(iter, "\n", len("\n"))
          line = line + 1
          
          # save position as cursor
          buffer.place_cursor(iter)
     
        # create bullet and new iter
        bullet = buffer.get_bullet(line - 1)
        
        if bullet:
          buffer.set_bullet(line, bullet)
          iter = buffer.get_iter_at_mark(buffer.get_insert())

        # add text
        string = self.edit_text(text)
        buffer.do_insert_text(iter, string, len(string))

        # scroll to cursor        
        buffer.place_cursor(iter)
        view.scroll_to_mark(buffer.get_insert(),SCROLL_TO_MARK_MARGIN)
		    
        # set focus
        view.grab_focus()

        logger.debug('PDF Notes: text inserted: %s', self.selected_text)

                
    def update(self):
        logger.debug('PDF Notes: update')
        
        # no file is open
        if not self.document.exists():
            return
        
        # get size of document
        self.width, self.height = self.document.page.get_size()
        
        # set scale
        if self.zoom :            
            self.scale = self.zoom / 100.0
        else :
            self.scale = self.scrolled_w.get_hadjustment().page_size / float(self.width)
            
        # set drawing area
        self.drawing_area.set_size_request( int(self.width * self.scale),
                                            int(self.height * self.scale))  
        
        # ui - set number of current page
        self.page_entry.set_text(str(self.document.page_number + 1))
        
        # ui - set label
        self.page_label.set_text(' out of ' + str(self.document.pages_count))
        
        # ui - selection style
        gtk_combobox_set_active_text(self.selection_button, self.selection_style)
        logger.debug('PDF Notes: update style %s', self.selection_style)
        
        # ui - redraw widget
        self.predraw()
        self.redraw()

    def predraw(self):
        logger.debug('PDF Notes: predraw')
        
        # create surface
        self.surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 
                                          int(self.width * self.scale),
                                          int(self.height * self.scale))
        # create context
        context = cairo.Context(self.surface)

        # scaling
        if self.scale != 1:
            context.scale(self.scale, self.scale)
            
        # rendering
        self.document.render_page(context)

    def redraw(self):
        
        if self.document.exists() :
            logger.debug('PDF Notes: redraw')
            self.drawing_area.queue_draw()

    def draw(self, widget, event):
        logger.debug('PDF Notes: draw')
        
        # no file is open
        if not self.document.exists() :
            return
        
        # create context
        context = widget.window.cairo_create()
        
        # draw page
        context.set_source_surface(self.surface)
        context.paint()
        
        # highlight selected areas
        if self.selected_area:
            self.draw_highlighting(context)
    
    def draw_highlighting(self, context):
            
        # scaling
        context.scale(self.scale, self.scale)
        
        # choose style
        style = self.selection_style
         
        # highlight selected areas
        if style == self.SELECT_IMAGE:            
            
            # draw rectangle
            for x1, y1, x2, y2 in self.selected_area:
            
                context.save()
            
                # set color for highlighting
                color = self.color_sea
                context.set_source_rgba(*color)

                w = int( 2.0 / self.scale )
                context.rectangle(x1 - w/2, y1 - w/2, x2 - x1 + w , y2 - y1 + w)
                context.set_line_width(w)
                #context.set_dash([10.0, 10.0])
                context.stroke()

                context.restore()
                context.save()

                color = self.color_sea_light
                context.set_source_rgba(*color)
                
                w = int( 20.0 / self.scale )
                context.rectangle(x1 - w/2, y1 - w/2, x2 - x1 + w , y2 - y1 + w)
                context.set_line_width(w)
                context.stroke()
                
                context.restore()
                
        elif style == self.SELECT_LINE or style == self.SELECT_TEXT :
            # set color
            color = self.color_sea
            # render selected text
            for area in self.selected_area:
                self.document.render_selection(context, color, *area)
            
# end of file gui.py    
