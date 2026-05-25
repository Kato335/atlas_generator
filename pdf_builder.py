import os
import tempfile
from typing import List, Dict, Tuple, Optional
from PIL import Image
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


class PDFBuilder:
    
    def __init__(self):
        self.temp_files = [] 
    
    def _create_image_reader(self, img: Image.Image) -> ImageReader:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            temp_path = tmp.name
            img.save(temp_path, format='PNG', optimize=True)
            self.temp_files.append(temp_path)
            return ImageReader(temp_path)
    
    def _cleanup(self):
        for temp_path in self.temp_files:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        self.temp_files.clear()
    
    def create_print_pdf(
        self,
        pages_data: List[Dict],
        output_file: str,
        orientation: str = "vertical"
    ):
       
        if orientation == "horizontal":
            page_size = landscape(A4)
        else:
            page_size = portrait(A4)
        
        page_width, page_height = page_size
        quarter_width = page_width / 2
        quarter_height = page_height / 2
        
        c = canvas.Canvas(output_file, pagesize=page_size)
        
        for page_idx, page in enumerate(pages_data):
            if 'full_page' in page and page['full_page']:
                img = page['full_page']
                img_reader = self._create_image_reader(img)
                c.drawImage(img_reader, 0, 0, page_width, page_height, 
                           preserveAspectRatio=False)
            else:
                positions = ['top_left', 'top_right', 'bottom_left', 'bottom_right']
                coords = {
                    'top_left': (0, quarter_height),
                    'top_right': (quarter_width, quarter_height),
                    'bottom_left': (0, 0),
                    'bottom_right': (quarter_width, 0)
                }
                
                for pos in positions:
                    if pos in page and page[pos]:
                        img, rotate = page[pos]
                        
                        if rotate == 180:
                            img = img.rotate(180, expand=True)
                        
                        img_reader = self._create_image_reader(img)
                        x, y = coords[pos]
                        c.drawImage(img_reader, x, y, quarter_width, quarter_height,
                                   preserveAspectRatio=False)
            
            c.showPage()
        
        c.save()
        self._cleanup()
    
    def create_full_pdf(
        self,
        images: List[Image.Image],
        output_file: str,
        orientation: str = "vertical"
    ):
        if orientation == "horizontal":
            page_size = landscape(A4)
        else:
            page_size = portrait(A4)
        
        page_width, page_height = page_size
        c = canvas.Canvas(output_file, pagesize=page_size)
        
        for img in images:
            img_reader = self._create_image_reader(img)
            c.drawImage(img_reader, 0, 0, page_width, page_height,
                       preserveAspectRatio=False)
            c.showPage()
        
        c.save()
        self._cleanup()