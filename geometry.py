import math 
from typing import Tuple


def lon2tile(lon: float, zoom: int) -> int:
    return int((lon + 180.0) / 360.0 * (1 << zoom))


def lat2tile(lat: float, zoom: int) -> int:
    lat_rad = math.radians(lat)
    return int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (1 << zoom))


def tile2lon(x: int, zoom: int) -> float:
    return x / (1 << zoom) * 360.0 - 180.0


def tile2lat(y: int, zoom: int) -> float:

    n = math.pi - 2.0 * math.pi * y / (1 << zoom)
    return math.degrees(math.atan(math.sinh(n)))


def get_bbox_from_half_diagonal(
    center: Tuple[float, float], 
    half_diagonal_km: float, 
    orientation: str
) -> Tuple[float, float, float, float]:
    if orientation == "horizontal":
        width_ratio = 297 / math.sqrt(297**2 + 210**2)
        height_ratio = 210 / math.sqrt(297**2 + 210**2)
    else:
        width_ratio = 210 / math.sqrt(297**2 + 210**2)
        height_ratio = 297 / math.sqrt(297**2 + 210**2)
    
    width_km = half_diagonal_km * width_ratio * 2
    height_km = half_diagonal_km * height_ratio * 2
    
    lat, lon = center
    delta_lat = (height_km / 2) / 111.0
    delta_lon = (width_km / 2) / (111.0 * math.cos(math.radians(lat)))
    
    return (lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


def get_zoom_for_size_km(size_km: float, quality: str, zoom_boost: float = 1.0) -> int:
    effective_size = size_km / 2.0 / zoom_boost

    thresholds = [
        (19, 0.3), (18, 0.5), (17, 0.8), (16, 1.2),
        (15, 2.0), (14, 3.0), (13, 5.0), (12, 8.0), (11, 12.0)
    ]
    
    quality_multiplier = {
        "ultra": 1.0,
        "high": 1.3,
        "normal": 1.6,
        "draft": 2.0
    }.get(quality, 1.6)
    
    for zoom, threshold in thresholds:
        if effective_size <= threshold * quality_multiplier:
            return zoom
    
    return 10


def calculate_km_per_pixel_at_latitude(lat: float, zoom: int) -> float:
    meters_per_pixel = 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)
    return meters_per_pixel / 1000