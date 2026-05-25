import os
import time
import math
from typing import Tuple, List, Dict
from dataclasses import dataclass
from PIL import Image

from geometry import (
    get_bbox_from_half_diagonal, 
    get_zoom_for_size_km,
    calculate_km_per_pixel_at_latitude
)
from tile_downloader import TileDownloader
from image_processor import ImageProcessor
from pdf_builder import PDFBuilder


@dataclass
class Sector:
    row: int
    col: int
    bounds: Tuple[float, float, float, float]
    
    @property
    def name(self) -> str:
        return f"{chr(65 + self.row)}{self.col + 1}"
    
    @property
    def center(self) -> Tuple[float, float]:
        min_lat, min_lon, max_lat, max_lon = self.bounds
        return ((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)
    
    @property
    def size_km(self) -> Tuple[float, float]:
        min_lat, min_lon, max_lat, max_lon = self.bounds
        width_km = (max_lon - min_lon) * 111.0 * math.cos(math.radians(self.center[0]))
        height_km = (max_lat - min_lat) * 111.0
        return (width_km, height_km)
    
    def __repr__(self) -> str:
        return f"Sector {self.name}: {self.size_km[0]:.2f}x{self.size_km[1]:.2f} km"


class FieldAtlasGenerator:
    
    def __init__(
        self,
        cache_dir: str = "./tile_cache",
        a4_mm: Tuple[int, int] = (210, 297),
        dpi: int = 300
    ):

        self.a4_mm = a4_mm
        self.dpi = dpi
        
        self.a4_px = (
            int(a4_mm[0] / 25.4 * dpi),
            int(a4_mm[1] / 25.4 * dpi)
        )
        self.quarter_px = (
            self.a4_px[0] // 2,
            self.a4_px[1] // 2
        )
        
        self.tile_downloader = TileDownloader(cache_dir=cache_dir)
        self.image_processor = ImageProcessor()
        self.pdf_builder = PDFBuilder()
    
    def generate(
        self,
        center: Tuple[float, float],
        half_diagonal_km: float,
        orientation: str = "vertical",
        quality: str = "high",
        zoom_boost: float = 1.0,
        margin_mm: float = 5,
        output_dir: str = "./atlas_output"
    ) -> str:

        os.makedirs(output_dir, exist_ok=True)
        margin_px = int(margin_mm / 25.4 * self.dpi)
        
        print(f"Center: {center[0]:.5f}, {center[1]:.5f}")
        print(f"Half-diagonal: {half_diagonal_km} km")
        print(f"Orientation: {orientation}")
        print(f"Quality: {quality}")
        print(f"Zoom boost: {zoom_boost}")
        print(f"A4 size: {self.a4_px[0]}x{self.a4_px[1]} px")
        
        bounds = get_bbox_from_half_diagonal(center, half_diagonal_km, orientation)
        
        overview_img, overview_bounds = self._generate_overview(
            bounds, orientation, quality
        )
        
        sectors = self._calculate_sectors(overview_bounds)
        for sector in sectors:
            print(f"  {sector}")
        
        sector_images = self._generate_sectors(
            sectors, quality, zoom_boost, margin_px
        )
        
        self._build_pdfs(sector_images, overview_img, orientation, output_dir)
        
        print(f"Done. Results: {output_dir}")
        
        return output_dir
    
    def _generate_overview(
        self,
        bounds: Tuple[float, float, float, float],
        orientation: str,
        quality: str
    ) -> Tuple[Image.Image, Tuple[float, float, float, float]]:
        print("Generating overview map...")
        
        min_lat, min_lon, max_lat, max_lon = bounds
        
        max_dim_km = max(
            (max_lon - min_lon) * 111.0 * math.cos(math.radians((min_lat+max_lat)/2)),
            (max_lat - min_lat) * 111.0
        )
        zoom = get_zoom_for_size_km(max_dim_km, quality)
        print(f"  Zoom: {zoom}")
        
        # Скачиваем карту
        print("  Downloading tiles...")
        img, img_bounds = self.tile_downloader.download_area(bounds, zoom, margin_deg=0)
        
        # Обрабатываем
        print("  Processing image...")
        img = self.image_processor.enhance_for_printing(img)

        target_ratio = self.a4_px[0] / self.a4_px[1]
        current_ratio = img.width / img.height
        
        if current_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            crop_region = (left, 0, left + new_width, img.height)
        else:
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            crop_region = (0, top, img.width, top + new_height)
        
        img_cropped = img.crop(crop_region)
        img_resized = img_cropped.resize(self.a4_px, Image.Resampling.LANCZOS)
        
        print("  Drawing grid...")
        labels_top = ["1", "2", "3", "4"]
        labels_left = ["A", "B", "C", "D"]
        img_with_grid = self.image_processor.add_grid(
            img_resized, 4, 4, labels_top, labels_left
        )
        
        def pixel_to_geo(x, y):
            lon = img_bounds[1] + (x / img.width) * (img_bounds[3] - img_bounds[1])
            lat = img_bounds[2] - (y / img.height) * (img_bounds[2] - img_bounds[0])
            return lat, lon
        
        left, top, right, bottom = crop_region
        overview_bounds = (
            pixel_to_geo(left, bottom)[0],  
            pixel_to_geo(left, top)[1],    
            pixel_to_geo(left, top)[0],     
            pixel_to_geo(right, top)[1]   
        )
        
        return img_with_grid, overview_bounds
    
    def _calculate_sectors(
        self,
        overview_bounds: Tuple[float, float, float, float]
    ) -> List[Sector]:
        min_lat, min_lon, max_lat, max_lon = overview_bounds
        
        lat_step = (max_lat - min_lat) / 4
        lon_step = (max_lon - min_lon) / 4
        
        sectors = []
        for row in range(4):
            for col in range(4):
                sector_min_lat = max_lat - (row + 1) * lat_step
                sector_max_lat = max_lat - row * lat_step
                sector_min_lon = min_lon + col * lon_step
                sector_max_lon = min_lon + (col + 1) * lon_step
                
                bounds = (sector_min_lat, sector_min_lon, sector_max_lat, sector_max_lon)
                sectors.append(Sector(row, col, bounds))
        
        return sectors
    
    def _generate_sectors(
        self,
        sectors: List[Sector],
        quality: str,
        zoom_boost: float,
        margin_px: int
    ) -> Dict[str, Image.Image]:
        print("Generating sectors...")
        
        sector_images = {}
        total = len(sectors)
        
        for i, sector in enumerate(sectors, 1):
            print(f"[{i}/{total}] Sector {sector.name}...", end=' ')
            start_time = time.time()
            
            img = self._generate_sector_image(sector, quality, zoom_boost, margin_px)
            sector_images[sector.name] = img
            
            elapsed = time.time() - start_time
            print(f"done ({elapsed:.1f}s)")
        
        return sector_images
    
    def _generate_sector_image(
        self,
        sector: Sector,
        quality: str,
        zoom_boost: float,
        margin_px: int
    ) -> Image.Image:
        min_lat, min_lon, max_lat, max_lon = sector.bounds
        
        max_dim_km = max(sector.size_km)
        zoom = get_zoom_for_size_km(max_dim_km, quality, zoom_boost)
        
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon
        lat_margin_deg = lat_range * (margin_px / self.quarter_px[1]) if self.quarter_px[1] > 0 else 0
        lon_margin_deg = lon_range * (margin_px / self.quarter_px[0]) if self.quarter_px[0] > 0 else 0
        margin_deg = max(lat_margin_deg, lon_margin_deg)

        img, img_bounds = self.tile_downloader.download_area(
            sector.bounds, zoom, margin_deg
        )
        img = self.image_processor.enhance_for_printing(img)

        img_final = self.image_processor.crop_to_bounds(
            img, sector.bounds, img_bounds, self.quarter_px, margin_px, sector.name
        )

        km_per_pixel = sector.size_km[0] / img_final.width
        img_final = self.image_processor.add_scale_bar(img_final, km_per_pixel)
        
        return img_final
    
    def _build_pdfs(
        self,
        sector_images: Dict[str, Image.Image],
        overview_img: Image.Image,
        orientation: str,
        output_dir: str
    ):
        print("Building PDF files...")
        
        file_a_pages = [
            {
                'top_left': (sector_images['A2'], 0),
                'top_right': (sector_images['D3'], 0),
                'bottom_left': (sector_images['A4'], 0),
                'bottom_right': (sector_images['D1'], 0)
            },
            {'full_page': overview_img},
            {
                'top_left': (sector_images['B2'], 0),
                'top_right': (sector_images['C3'], 0),
                'bottom_left': None,
                'bottom_right': None
            }
        ]
        
        file_b_pages = [
            {
                'top_left': (sector_images['D4'], 0),
                'top_right': (sector_images['A1'], 0),
                'bottom_left': (sector_images['D2'], 0),
                'bottom_right': (sector_images['A3'], 0)
            },
            {
                'top_left': (sector_images['C2'], 0),
                'top_right': (sector_images['B3'], 0),
                'bottom_left': (sector_images['C1'], 180),
                'bottom_right': (sector_images['B4'], 180)
            },
            {
                'top_left': (sector_images['C4'], 0),
                'top_right': (sector_images['B1'], 0),
                'bottom_left': None,
                'bottom_right': None
            }
        ]
        
        print("  Creating file A...")
        self.pdf_builder.create_print_pdf(
            file_a_pages,
            os.path.join(output_dir, "print_file_A.pdf"),
            orientation
        )
        
        print("  Creating file B...")
        self.pdf_builder.create_print_pdf(
            file_b_pages,
            os.path.join(output_dir, "print_file_B.pdf"),
            orientation
        )
        
        print("PDF files created")


if __name__ == "__main__":
    generator = FieldAtlasGenerator(cache_dir="./tile_cache")
    
    generator.generate(
        center=(59.933086, 30.388149),
        half_diagonal_km=15.0,
        orientation="vertical",
        quality="high",
        zoom_boost=1.5,
        margin_mm=5,
        output_dir="./field_atlas"
    )