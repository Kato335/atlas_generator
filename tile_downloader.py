import os
import time
import requests
from io import BytesIO
from typing import Tuple, Optional
from PIL import Image

from geometry import lon2tile, lat2tile, tile2lon, tile2lat


class TileDownloader:
    
    def __init__(
        self, 
        cache_dir: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 15,
        user_agent: str = "FieldAtlasGenerator/1.0"
    ):
        self.cache_dir = cache_dir
        self.max_retries = max_retries
        self.timeout = timeout
        self.user_agent = user_agent
        self.tile_size = 256
        
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, x: int, y: int, zoom: int) -> str:
        return os.path.join(self.cache_dir, f"{zoom}_{x}_{y}.png")
    
    def download_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        if self.cache_dir:
            cache_path = self._get_cache_path(x, y, zoom)
            if os.path.exists(cache_path):
                try:
                    return Image.open(cache_path)
                except Exception:
                    pass 
        
        url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
        
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url, 
                    headers={"User-Agent": self.user_agent}, 
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Сохраняем в кэш
                    if self.cache_dir:
                        img.save(cache_path, "PNG")
                    
                    return img
                
                time.sleep(1)
                
            except Exception as e:
                print(f"    Error downloading tile {x},{y}: {e}")
                time.sleep(2)
        
        return Image.new('RGB', (self.tile_size, self.tile_size), color=(220, 220, 220))
    
    def download_area(
        self, 
        bounds: Tuple[float, float, float, float], 
        zoom: int, 
        margin_deg: float = 0
    ) -> Tuple[Image.Image, Tuple[float, float, float, float]]:
       
        min_lat, min_lon, max_lat, max_lon = bounds
        
        min_lat -= margin_deg
        max_lat += margin_deg
        min_lon -= margin_deg
        max_lon += margin_deg
        
        min_x = lon2tile(min_lon, zoom)
        max_x = lon2tile(max_lon, zoom)
        min_y = lat2tile(max_lat, zoom)
        max_y = lat2tile(min_lat, zoom)
        
        total_tiles = (max_x - min_x + 1) * (max_y - min_y + 1)
        print(f"    Tiles: {total_tiles} at zoom={zoom}")

        width = (max_x - min_x + 1) * self.tile_size
        height = (max_y - min_y + 1) * self.tile_size
        result = Image.new('RGB', (width, height))
    
        downloaded = 0
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                downloaded += 1
                print(f"    [{downloaded}/{total_tiles}] Tile {x},{y}...", end=' ')
                
                tile = self.download_tile(x, y, zoom)
                x_offset = (x - min_x) * self.tile_size
                y_offset = (y - min_y) * self.tile_size
                result.paste(tile, (x_offset, y_offset))
                
                print("ok")
                time.sleep(0.05)
        
        real_min_lon = tile2lon(min_x, zoom)
        real_max_lon = tile2lon(max_x + 1, zoom)
        real_max_lat = tile2lat(min_y, zoom)
        real_min_lat = tile2lat(max_y + 1, zoom)
        
        return result, (real_min_lat, real_min_lon, real_max_lat, real_max_lon)
    
    def clear_cache(self):
        """Очистить кэш"""
        if self.cache_dir and os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.png'):
                    os.remove(os.path.join(self.cache_dir, filename))