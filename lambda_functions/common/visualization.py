import io

import numpy as np
import rasterio
from cmap import Colormap
from PIL import Image

GLOBAL_MIN = 273.15  # Kelvin
GLOBAL_MAX = 308.15  # Kelvin


def normalize(data):
    data = np.where(np.isfinite(data), data, np.nan)
    min_val, max_val = np.nanmin(data), np.nanmax(data)
    if np.isnan(min_val) or np.isnan(max_val) or max_val == min_val:
        return np.zeros_like(data, dtype=np.uint8), np.zeros_like(data, dtype=np.uint8)
    norm_data = np.nan_to_num(
        (data - min_val) / (max_val - min_val) * 255, nan=0
    ).astype(np.uint8)
    alpha_mask = np.where(np.isnan(data) | (data < -1000), 0, 255).astype(np.uint8)
    return norm_data, alpha_mask


def tif_to_png(tif_path, color_scale="relative"):
    with rasterio.open(tif_path) as dataset:
        num_bands = dataset.count

        if color_scale == "fixed":
            band = dataset.read(1).astype(np.float32)
            band[np.isnan(band)] = 0
            band = np.clip(band, GLOBAL_MIN, GLOBAL_MAX)
            norm_band = ((band - GLOBAL_MIN) / (GLOBAL_MAX - GLOBAL_MIN) * 255).astype(
                np.uint8
            )
            alpha_mask = np.where(band <= GLOBAL_MIN, 0, 255).astype(np.uint8)
            cmap = Colormap("jet")
            rgba_img = cmap(norm_band / 255.0)
            rgba_img = (rgba_img * 255).astype(np.uint8)
            rgba_img[..., 3] = alpha_mask
        elif color_scale == "relative":
            bands = [dataset.read(band) for band in range(1, num_bands + 1)]
            norm_bands, alpha_mask = zip(*[normalize(band) for band in bands])
            norm_band = norm_bands[0]
            cmap = Colormap("jet")
            rgba_img = cmap(norm_band / 255.0)
            rgba_img = (rgba_img * 255).astype(np.uint8)
            rgba_img[..., 3] = alpha_mask[0]
        elif color_scale == "gray":
            bands = [dataset.read(band) for band in range(1, num_bands + 1)]
            norm_bands, alpha_mask = zip(*[normalize(band) for band in bands])
            img_array = np.stack([norm_bands[0], norm_bands[0], norm_bands[0]], axis=-1)
            img_array = np.dstack((img_array, alpha_mask[0]))
            rgba_img = img_array
        else:
            raise ValueError(f"Invalid color_scale: {color_scale}")

        img = Image.fromarray(rgba_img, mode="RGBA")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
    return img_bytes
