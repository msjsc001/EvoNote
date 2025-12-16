
import os
import hashlib
import shutil
import time
from pathlib import Path
from PySide6.QtGui import QImage
from PySide6.QtCore import QMimeData

class ImagePasteHandler:
    """
    Handles logic for pasting images from clipboard/mime data.
    Saves image to vault assets and returns Markdown syntax.
    """
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.assets_dir = self.vault_path / "assets"

    def handle_mime_data(self, mime: QMimeData) -> str | None:
        """
        Checks if mime data contains an image. 
        If so, saves it and returns '![image](assets/xxx.png)'.
        Returns None if no image found.
        """
        if not mime.hasImage():
            return None
        
        image = QImage(mime.imageData())
        if image.isNull():
            return None

        # 1. Ensure assets directory exists with YearMonth subfolder (to avoid limit issues)
        # Using simple "assets/YYYYMM" structure
        timestamp = time.strftime("%Y%m")
        target_dir = self.assets_dir / timestamp
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"ERROR: Failed to create assets dir {target_dir}: {e}")
            return None

        # 2. Generate unique filename
        # We can hash the image data or just use precise timestamp
        raw_seed = f"{time.time_ns()}"
        file_hash = hashlib.md5(raw_seed.encode()).hexdigest()[:10]
        filename = f"paste_{file_hash}.png"
        
        file_path = target_dir / filename
        
        # 3. Save Image
        try:
            # Save as PNG for lossless quality
            success = image.save(str(file_path), "PNG")
            if not success:
                print(f"ERROR: Failed to save QImage to {file_path}")
                return None
        except Exception as e:
            print(f"ERROR: Exception saving image: {e}")
            return None

        # 4. Return Markdown Link
        # Path should be relative to vault root
        rel_path = f"assets/{timestamp}/{filename}"
        return f"![Image]({rel_path})"
