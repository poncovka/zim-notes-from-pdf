# -*- coding: utf-8 -*-

# Author: Vendula Poncova <poncovka@gmail.com>
# File: model.py
#
# Description: 
# Model of PDF document.
#

import poppler
import logging

logger = logging.getLogger(__name__)

class PDFDocument(object):
    '''
    classdocs
    '''
    def __init__(self):
        '''
        Constructor
        '''
        self.file = None
        self.document = None
        self.page = None
        self.page_number = 0
        self.pages_count = 0
        self.width = 0
        self.height = 0
     
    def exists(self):
        return self.document != None 
    
    def next_page(self):
        return self.set_page(self.page_number + 1)
    
    def prev_page(self):
        return self.set_page(self.page_number - 1)                  
    
    def set_page(self, page_number):
        
        # check range
        if 0 <= page_number and page_number < self.pages_count :
            
            logger.debug('PDF Notes: set page to number %s', page_number)
            
            # set number and update widget
            self.page_number = page_number
            
            # get current page
            self.page = self.document.get_page(self.page_number)
            
            # set size
            self.width, self.height = self.page.get_size()
            
            self.walk()
                                  
            return True
        
        # no change
        return False  
     
    def set_file(self, file): 
        logger.info('PDF Notes: opening file %s', file)
        
        # open file with poppler
        try:      
            document = poppler.document_new_from_file ("file://" + file.path, None)
        except Exception:
            logger.exception("PDF Notes: cannot open file")
            return
        
        # update state
        self.file = file
        self.document = document
        self.pages_count = self.document.get_n_pages()
        
        self.set_page(0) 
      
    def to_rect(self, x1, y1, x2, y2):
        
        rect = poppler.Rectangle()
        
        rect.x1 = x1
        rect.y1 = y1
        rect.x2 = x2
        rect.y2 = y2
        
        return rect
     
    def to_tuple(self, rect):
        
        return (rect.x1, rect.y1, rect.x2, rect.y2)
   
    def to_color(self, r, g, b, a = None):
        
        color = poppler.Color()
        
        max = 65535.0
        color.red =   int(r * max)
        color.green = int (g * max)
        color.blue =  int(b * max)
        
        return color
                
    def point_in_rect(self, x, y, rect):     
        
        return rect.x1 <= x and rect.y1 <= y and rect.x2 >= x and rect.y2 >= y 
    
    def rect_intersection(self, rect_A, rect_B):
        
        x1 = max(rect_A.x1, rect_B.x1)
        y1 = max(rect_A.y1, rect_B.y1)
        x2 = min(rect_A.x2, rect_B.x2)
        y2 = min(rect_A.y2, rect_B.y2)
        
        if not (x1 <= x2 and y1 <= y2) :
            return None
        
        return (x1, y1, x2, y2) 

    def find_text(self, x1, y1, x2, y2):  
        logger.debug('PDF Notes: finding line')     
             
        # set style and area
        style = poppler.SELECTION_WORD
        selection = self.to_rect(x1, y1, x2, y2)
        areas = list()
        
        # find text in selected area
        text = self.page.get_selected_text(style,selection)
        logger.debug('PDF Notes: FOUND TEXT %s ', text )

        # nothing found
        if not text :
            return None, areas
        
        # find positions of lines
        lines = text.splitlines()
        
        for line in lines:
            area = self.find_area(line, selection=selection)
            areas.extend(area)            
            
        return text, areas
            
    def find_line(self, x1, y1, x2, y2):  
        logger.debug('PDF Notes: finding line')     
             
        # set style and area
        style = poppler.SELECTION_LINE
        selection = self.to_rect(x1, y1, x2, y2)
        
        # find text in selected area
        text = self.page.get_selected_text(style,selection)
        
        # nothing rect
        if not text :
            return None, list()
        
        # get first line
        line = text.splitlines()[0]
        
        # get area
        area = self.find_area(line, x=selection.x1, y=selection.y1)
        
        # return line and area
        return line, area
      
    def find_area(self, line, x=None, y=None, selection=None):
                 
        areas = list()
        found_rects = self.page.find_text(line)
        
        # find areas
        for rect in found_rects:
            
            # correction
            rect.y1, rect.y2 = self.height - rect.y2, self.height - rect.y1
                                   
            # check boundaries
            if (selection and self.rect_intersection(rect, selection)) or self.point_in_rect(x, y, rect) :

                # found to tuple
                area = self.to_tuple(rect)
                                
                # save area
                logger.debug('PDF Notes: FOUND %s AT %s', line, [int(point) for point in area] )
                areas.append(area)
                #break     
                
        return areas
    
    def render_page(self, cairo):
 
        # white background       
        cairo.set_source_rgb(1, 1, 1)
        cairo.rectangle(0, 0, self.width, self.height)
        cairo.fill()
        
        # rendering
        self.page.render(cairo)
            
    def render_selection(self, cairo, color, *area):
        logger.debug('PDF Notes: rendering selection')

        rect = self.to_rect(*area) 
        
        style = poppler.SELECTION_WORD
        old_selection = self.to_rect(0, 0, 0, 0)
        glyph_color = self.to_color(1.0, 1.0, 1.0)
        background_color = self.to_color(*color) 

        self.page.render_selection(cairo, 
                                   rect,
                                   old_selection,
                                   style,
                                   glyph_color,
                                   background_color
                                   )            

    def walk(self):
        pass

# end of file model.py       