import filecmp
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from tqdm import tqdm

logger = logging.getLogger(__name__)


def close_process(process_name):
    try:
        result = subprocess.run(
            ["taskkill", "/f", "/im", process_name],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            logger.info(f"{process_name} closed successfully")
            return True
        elif "not found" in result.stderr.lower():
            logger.info(f"{process_name} is not running")
            return True
        else:
            logger.warning(f"taskkill returned: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error using taskkill to close {process_name}: {e}")
        return False


def read_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read JSON file {file_path}: {e}")
        raise


def save_json(data, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save JSON to {file_path}: {e}")
        raise


def copy_directory(source_dir, target_dir):
    logger.info(f"Copying files from '{source_dir}' to '{target_dir}'...")

    try:
        _copytree_with_progress(source_dir, target_dir)
    except Exception as e:
        logger.error(f"Failed to copy directory: {e}")
        remove_dir_if_exists(target_dir)
        return False

    if not _verify_directory_copy(source_dir, target_dir):
        logger.warning("Copy verification failed. Cleaning up.")
        remove_dir_if_exists(target_dir)
        return False

    logger.info("Successfully copied directory")
    return True


def copy_file(source_file_path, target_file_path):
    logger.info(f"Copying file from '{source_file_path}' to '{target_file_path}'...")

    try:
        shutil.copy2(source_file_path, target_file_path)
    except Exception as e:
        logger.error(f"Failed to copy file: {e}")
        remove_file_if_exists(target_file_path)
        return False

    logger.info("Successfully copied file")
    return True


def remove_dir_if_exists(dir):
    try:
        if os.path.exists(dir):
            shutil.rmtree(dir)
        logger.info(f"Successfully removed directory: {dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove directory: {e}")
        return False


def remove_file_if_exists(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.info(f"Successfully removed file: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove file: {e}")
        return False


def backup_file(file_path):
    try:
        backup_path = f'{file_path}.bak'
        shutil.copyfile(file_path, backup_path)
        logger.info(f"Successfully created backup: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to backup file: {e}")
        return False


def _copytree_with_progress(source, destination):
    def copy_with_progress(src, dst):
        shutil.copy2(src, dst)
        progress_bar.update(os.path.getsize(src))

    total_size = sum(os.path.getsize(f) for f in Path(source).rglob('*'))

    try:
        with tqdm(total=total_size, unit='B', unit_scale=True) as progress_bar:
            shutil.copytree(source, destination, copy_function=copy_with_progress, ignore=shutil.ignore_patterns(''))
        return True

    except Exception as e:
        logger.error(f"Copy function failed: {e}")
        return False


def _verify_directory_copy(source_dir, target_dir):
    def compare_directories(dcmp):
        if dcmp.left_only or dcmp.right_only or dcmp.diff_files:
            logger.info(f"Differences found: {dcmp.diff_files}")
            return False

        for sub_dcmp in dcmp.subdirs.values():
            if not compare_directories(sub_dcmp):
                return False

        return True

    try:
        dircmp = filecmp.dircmp(source_dir, target_dir, ignore=None)
        if compare_directories(dircmp):
            return True

        return False

    except Exception as e:
        logger.error(f"Copy verification failed: {e}")
        return False