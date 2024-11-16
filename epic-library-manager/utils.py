import os
import json
import shutil
from pathlib import Path

from tqdm import tqdm


def read_json_file(file_path):
    with open(file_path, 'r') as file:
        item_data = json.load(file)
    return item_data


def copytree_with_progress(source, destination):
    total_size = sum(os.path.getsize(f) for f in Path(source).rglob('*'))

    def copy_with_progress(src, dst):
        shutil.copy2(src, dst)
        progress_bar.update(os.path.getsize(src))

    try:
        with tqdm(total=total_size, unit='B', unit_scale=True) as progress_bar:
            shutil.copytree(source, destination, copy_function=copy_with_progress, ignore=shutil.ignore_patterns(''))
        return True

    except Exception as e:
        print(f"ERROR: Copy function failed. Exception: {e}")
        return False
