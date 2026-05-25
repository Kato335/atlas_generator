from typing import Tuple, List, Optional
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFont


class ImageProcessor:
    
    def __init__(self, font_paths: Optional[List[str]] = None):

        self.font_paths = font_paths or [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:\\Windows\\Fonts\\Arial.ttf"
        ]
    
    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:

        for path in self.font_paths:
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
        return ImageFont.load_default()
    
    def enhance_for_printing(self, img: Image.Image) -> Image.Image:
 
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        gray = ImageOps.grayscale(img)
        
        enhancer = ImageEnhance.Contrast(gray)
        gray = enhancer.enhance(1.5)

        enhancer = ImageEnhance.Sharpness(gray)
        gray = enhancer.enhance(1.3)
        
        gray = ImageOps.autocontrast(gray, cutoff=2)
        
        return gray.convert('RGB')
    
    def crop_to_bounds(
        self,
        img: Image.Image,
        target_bounds: Tuple[float, float, float, float],
        img_bounds: Tuple[float, float, float, float],
        target_size: Tuple[int, int],
        margin_px: int = 10,
        label: Optional[str] = None
    ) -> Image.Image:
       
        min_lat_target, min_lon_target, max_lat_target, max_lon_target = target_bounds
        min_lat_img, min_lon_img, max_lat_img, max_lon_img = img_bounds
        
        # Рассчитываем отступ в градусах
        lat_range = max_lat_target - min_lat_target
        lon_range = max_lon_target - min_lon_target
        
        lat_margin_deg = lat_range * (margin_px / target_size[1]) if target_size[1] > 0 else 0
        lon_margin_deg = lon_range * (margin_px / target_size[0]) if target_size[0] > 0 else 0
        
        min_lat_with_margin = min_lat_target - lat_margin_deg
        max_lat_with_margin = max_lat_target + lat_margin_deg
        min_lon_with_margin = min_lon_target - lon_margin_deg
        max_lon_with_margin = max_lon_target + lon_margin_deg
        
        def geo_to_pixel(lat: float, lon: float) -> Tuple[int, int]:
            x = (lon - min_lon_img) / (max_lon_img - min_lon_img) * img.width
            y = (1 - (lat - min_lat_img) / (max_lat_img - min_lat_img)) * img.height
            return int(x), int(y)
        
        left, top = geo_to_pixel(max_lat_with_margin, min_lon_with_margin)
        right, bottom = geo_to_pixel(min_lat_with_margin, max_lon_with_margin)
        
        left = max(0, left)
        top = max(0, top)
        right = min(img.width, right)
        bottom = min(img.height, bottom)
        
        img_cropped = img.crop((left, top, right, bottom))
        img_resized = img_cropped.resize(target_size, Image.Resampling.LANCZOS)
        
        def target_geo_to_pixel(lat: float, lon: float) -> Tuple[int, int]:
            x = (lon - min_lon_with_margin) / (max_lon_with_margin - min_lon_with_margin) * img_resized.width
            y = (1 - (lat - min_lat_with_margin) / (max_lat_with_margin - min_lat_with_margin)) * img_resized.height
            return int(x), int(y)
        
        left_border, top_border = target_geo_to_pixel(max_lat_target, min_lon_target)
        right_border, bottom_border = target_geo_to_pixel(min_lat_target, max_lon_target)
        
        draw = ImageDraw.Draw(img_resized)
        draw.rectangle(
            [(left_border, top_border), (right_border, bottom_border)], 
            outline=(0, 0, 0), 
            width=2
        )
        
        if label:
            self._add_label(img_resized, label, draw)
        
        return img_resized
    
    def _add_label(self, img: Image.Image, label: str, draw: ImageDraw.Draw):
        font = self._get_font(24)
        
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        padding = 8
        rect_width = text_width + padding * 2
        rect_height = text_height + padding * 2

        x = (img.width - rect_width) // 2
        y = 10
        
        draw.rectangle([(x, y), (x + rect_width, y + rect_height)], fill=(0, 0, 0))

        draw.text((x + padding, y + padding), label, fill=(255, 255, 255), font=font)
    
    def add_grid(
        self,
        img: Image.Image,
        rows: int,
        cols: int,
        labels_top: Optional[List[str]] = None,
        labels_left: Optional[List[str]] = None
    ) -> Image.Image:
       
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        for col in range(1, cols):
            x = col * width / cols
            draw.line([(x, 0), (x, height)], fill=(0, 0, 0), width=3)

        for row in range(1, rows):
            y = row * height / rows
            draw.line([(0, y), (width, y)], fill=(0, 0, 0), width=3)

        if labels_top:
            self._add_top_labels(img, draw, labels_top, cols, width)

        if labels_left:
            self._add_left_labels(img, draw, labels_left, rows, height)
        
        return img
    
    def _add_top_labels(self, img: Image.Image, draw: ImageDraw.Draw, 
                        labels: List[str], cols: int, width: int):
        font = self._get_font(28)
        
        for i, label in enumerate(labels):
            col_center_x = (i + 0.5) * (width / cols)
            y_pos = 40
            
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            padding = 10
            rect_width = text_width + padding * 2
            rect_height = text_height + padding * 2
            
            x_rect = col_center_x - rect_width / 2
            y_rect = y_pos - rect_height / 2
            
            draw.rectangle([(x_rect, y_rect), (x_rect + rect_width, y_rect + rect_height)], fill=(0, 0, 0))
            draw.text((col_center_x - text_width / 2, y_pos - text_height / 2), 
                     label, fill=(255, 255, 255), font=font)
    
    def _add_left_labels(self, img: Image.Image, draw: ImageDraw.Draw,
                         labels: List[str], rows: int, height: int):
        font = self._get_font(28)
        
        for i, label in enumerate(labels):
            row_center_y = (i + 0.5) * (height / rows)
            x_pos = 40
            
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            padding = 10
            rect_width = text_width + padding * 2
            rect_height = text_height + padding * 2
            
            x_rect = x_pos - rect_width / 2
            y_rect = row_center_y - rect_height / 2
            
            draw.rectangle([(x_rect, y_rect), (x_rect + rect_width, y_rect + rect_height)], fill=(0, 0, 0))
            draw.text((x_pos - text_width / 2, row_center_y - text_height / 2),
                     label, fill=(255, 255, 255), font=font)
    
    def add_scale_bar(self, img: Image.Image, km_per_pixel: float) -> Image.Image:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        if km_per_pixel * 200 > 5:
            scale_km = 10.0
        elif km_per_pixel * 200 > 2:
            scale_km = 5.0
        elif km_per_pixel * 200 > 1:
            scale_km = 2.0
        else:
            scale_km = 1.0
        
        scale_pixels = int(scale_km / km_per_pixel)
        
        if scale_pixels > width - 60:
            scale_pixels = width - 60
        
        margin = 20
        x_start = width - margin - scale_pixels
        x_end = width - margin
        y = height - margin
        
        # Рисуем линейку
        draw.rectangle([(x_start, y - 3), (x_end, y + 3)], fill=(0, 0, 0))
        draw.line([(x_start, y), (x_start, y - 10)], fill=(0, 0, 0), width=1)
        draw.line([(x_end, y), (x_end, y - 10)], fill=(0, 0, 0), width=1)
        
        # Подпись
        font = self._get_font(10)
        draw.text((x_start - 15, y - 15), f"{scale_km} km", fill=(0, 0, 0), font=font)
        
        return img