"""
EXIF GPS extraction utility.

Extracts GPS coordinates and capture datetime from JPEG EXIF metadata.
Uses Pillow (already in requirements).
"""

import logging
from datetime import datetime

logger = logging.getLogger("documents")


def extract_exif_gps(image_path):
    """
    Extract GPS lat/lng and datetime from image EXIF data.

    Args:
        image_path: absolute path to image file

    Returns:
        dict: {'lat': float|None, 'lng': float|None, 'datetime': datetime|None}
    """
    result = {"lat": None, "lng": None, "datetime": None}
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS

        img = Image.open(image_path)
        exif_data = img._getexif()
        if not exif_data:
            return result

        # DateTime
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "DateTimeOriginal":
                try:
                    result["datetime"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass
                break

        # GPS
        gps_info = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value
                break

        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = _dms_to_decimal(
                gps_info["GPSLatitude"],
                gps_info.get("GPSLatitudeRef", "N"),
            )
            lng = _dms_to_decimal(
                gps_info["GPSLongitude"],
                gps_info.get("GPSLongitudeRef", "E"),
            )
            if lat is not None and lng is not None:
                result["lat"] = lat
                result["lng"] = lng

    except Exception:
        logger.debug("EXIF extraction failed for %s", image_path, exc_info=True)

    return result


def _dms_to_decimal(dms_coords, ref):
    """Convert EXIF DMS (degrees, minutes, seconds) to decimal degrees."""
    try:
        d = float(dms_coords[0])
        m = float(dms_coords[1])
        s = float(dms_coords[2])
        decimal = d + m / 60.0 + s / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)
    except (TypeError, IndexError, ValueError, ZeroDivisionError):
        return None
