"""
Image combination utility for batch OCR processing.
Combines multiple screenshots into a single image to reduce API calls.
"""

from pathlib import Path
from typing import List, Literal, Tuple

import structlog
from PIL import Image

logger = structlog.get_logger()

CombineStrategy = Literal['vertical_stack', 'horizontal_stack', 'grid']


def combine_screenshots(
    images: List[Image.Image],
    strategy: CombineStrategy = 'vertical_stack',
    max_width: int = 4096,
    max_height: int = 4096,
    spacing: int = 10
) -> Image.Image:
    """
    Combine multiple screenshots into a single image.

    Args:
        images: List of PIL Image objects to combine
        strategy: How to arrange images ('vertical_stack', 'horizontal_stack', or 'grid')
        max_width: Maximum width of combined image
        max_height: Maximum height of combined image
        spacing: Pixels of spacing between images

    Returns:
        Combined PIL Image
    """
    if not images:
        raise ValueError("No images provided to combine")

    if len(images) == 1:
        return images[0]

    if strategy == 'vertical_stack':
        return _vertical_stack(images, max_width, max_height, spacing)
    elif strategy == 'horizontal_stack':
        return _horizontal_stack(images, max_width, max_height, spacing)
    elif strategy == 'grid':
        return _grid_layout(images, max_width, max_height, spacing)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def _vertical_stack(
    images: List[Image.Image],
    max_width: int,
    max_height: int,
    spacing: int
) -> Image.Image:
    """Stack images vertically."""
    # Calculate dimensions
    widths = [img.width for img in images]
    heights = [img.height for img in images]

    # Target width is the maximum width among images
    target_width = max(widths)

    # Scale images if needed
    scaled_images = []
    for img in images:
        if img.width > max_width:
            # Scale down proportionally
            scale = max_width / img.width
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        scaled_images.append(img)

    # Recalculate after scaling
    widths = [img.width for img in scaled_images]
    heights = [img.height for img in scaled_images]
    target_width = min(max(widths), max_width)

    # Calculate total height with spacing
    total_height = sum(heights) + spacing * (len(images) - 1)

    # If total height exceeds max, we need to scale down all images
    if total_height > max_height:
        scale = max_height / total_height
        scaled_images = [
            img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS
            )
            for img in scaled_images
        ]
        heights = [img.height for img in scaled_images]
        total_height = sum(heights) + spacing * (len(images) - 1)

    # Create combined image with white background
    combined = Image.new('RGB', (target_width, total_height), 'white')

    # Paste images
    y_offset = 0
    for img in scaled_images:
        # Center horizontally if image is narrower
        x_offset = (target_width - img.width) // 2
        combined.paste(img, (x_offset, y_offset))
        y_offset += img.height + spacing

    logger.debug(
        "images_combined_vertical",
        count=len(images),
        width=target_width,
        height=total_height
    )

    return combined


def _horizontal_stack(
    images: List[Image.Image],
    max_width: int,
    max_height: int,
    spacing: int
) -> Image.Image:
    """Stack images horizontally."""
    # Calculate dimensions
    widths = [img.width for img in images]
    heights = [img.height for img in images]

    # Target height is the maximum height among images
    target_height = max(heights)

    # Scale images if needed
    scaled_images = []
    for img in images:
        if img.height > max_height:
            # Scale down proportionally
            scale = max_height / img.height
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        scaled_images.append(img)

    # Recalculate after scaling
    widths = [img.width for img in scaled_images]
    heights = [img.height for img in scaled_images]
    target_height = min(max(heights), max_height)

    # Calculate total width with spacing
    total_width = sum(widths) + spacing * (len(images) - 1)

    # If total width exceeds max, we need to scale down all images
    if total_width > max_width:
        scale = max_width / total_width
        scaled_images = [
            img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS
            )
            for img in scaled_images
        ]
        widths = [img.width for img in scaled_images]
        total_width = sum(widths) + spacing * (len(images) - 1)

    # Create combined image with white background
    combined = Image.new('RGB', (total_width, target_height), 'white')

    # Paste images
    x_offset = 0
    for img in scaled_images:
        # Center vertically if image is shorter
        y_offset = (target_height - img.height) // 2
        combined.paste(img, (x_offset, y_offset))
        x_offset += img.width + spacing

    logger.debug(
        "images_combined_horizontal",
        count=len(images),
        width=total_width,
        height=target_height
    )

    return combined


def _grid_layout(
    images: List[Image.Image],
    max_width: int,
    max_height: int,
    spacing: int
) -> Image.Image:
    """Arrange images in a grid layout."""
    import math

    num_images = len(images)

    # Calculate grid dimensions (try to make it roughly square)
    cols = math.ceil(math.sqrt(num_images))
    rows = math.ceil(num_images / cols)

    # Calculate cell size
    cell_width = (max_width - spacing * (cols - 1)) // cols
    cell_height = (max_height - spacing * (rows - 1)) // rows

    # Scale images to fit cells
    scaled_images = []
    for img in images:
        # Scale to fit cell while maintaining aspect ratio
        width_scale = cell_width / img.width
        height_scale = cell_height / img.height
        scale = min(width_scale, height_scale)

        new_width = int(img.width * scale)
        new_height = int(img.height * scale)
        scaled_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        scaled_images.append(scaled_img)

    # Calculate actual dimensions
    total_width = cols * cell_width + spacing * (cols - 1)
    total_height = rows * cell_height + spacing * (rows - 1)

    # Create combined image with white background
    combined = Image.new('RGB', (total_width, total_height), 'white')

    # Paste images in grid
    for idx, img in enumerate(scaled_images):
        row = idx // cols
        col = idx % cols

        x = col * (cell_width + spacing) + (cell_width - img.width) // 2
        y = row * (cell_height + spacing) + (cell_height - img.height) // 2

        combined.paste(img, (x, y))

    logger.debug(
        "images_combined_grid",
        count=len(images),
        rows=rows,
        cols=cols,
        width=total_width,
        height=total_height
    )

    return combined


def combine_screenshot_files(
    file_paths: List[Path],
    strategy: CombineStrategy = 'vertical_stack',
    max_width: int = 4096,
    max_height: int = 4096,
    spacing: int = 10
) -> Image.Image:
    """
    Combine multiple screenshot files into a single image.

    Args:
        file_paths: List of paths to screenshot files
        strategy: How to arrange images
        max_width: Maximum width of combined image
        max_height: Maximum height of combined image
        spacing: Pixels of spacing between images

    Returns:
        Combined PIL Image
    """
    images = []
    for path in file_paths:
        try:
            img = Image.open(path)
            images.append(img)
        except Exception as e:
            logger.error("failed_to_load_image", path=str(path), error=str(e))

    if not images:
        raise ValueError("No valid images to combine")

    return combine_screenshots(images, strategy, max_width, max_height, spacing)
