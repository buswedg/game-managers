import logging
import os
import sqlite3

from dotenv import load_dotenv

from utils import read_json, save_json, backup_file

load_dotenv()

AG_DB_PATH = os.getenv('AG_DB_PATH')
NILE_MANIFEST_PATH = os.getenv('NILE_MANIFEST_PATH')
UPDATE_AG_MANIFEST = os.getenv('UPDATE_AG_MANIFEST', 'False').lower() == "true"
UPDATE_NILE_MANIFEST = os.getenv('UPDATE_NILE_MANIFEST', 'False').lower() == "true"

logger = logging.getLogger(__name__)


def update_manifest(game):
    """
    Update manifest files with the new game location.
    """
    success = True

    if UPDATE_AG_MANIFEST:
        success &= _update_ag_asin(game)
        success &= _update_ag_manifest(game)

    if UPDATE_NILE_MANIFEST:
        success &= _update_nile_manifest(game)

    return success


def _update_ag_manifest(game):
    """
    Update EGL manifest with new install directory.
    """
    if not AG_DB_PATH or not os.path.exists(AG_DB_PATH):
        logger.error(f"EGL manifest directory not found: {AG_DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(AG_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE DbSet SET InstallDirectory = ? WHERE ProductAsin = ?",
            (game.install_dir, game.game_id)
        )
        rows_affected = cursor.rowcount
        conn.commit()

        if rows_affected == 0:
            logger.warning(f"Game '{game.name}' not found in AG database. No changes made.")
            return False
        else:
            logger.info(f"Successfully updated AG manifest for game '{game.name}'")
            return True

    except sqlite3.Error as e:
        logger.error(f"Failed to update AG manifest for {game.name}: {e}")
        return False


def _update_ag_asin(game):
    """
    Update ASIN in the Amazon Games database.
    """
    logger.info(f"Updating ASIN for {game.name} to {game.game_id}")

    if not AG_DB_PATH or not os.path.exists(AG_DB_PATH):
        logger.error(f"EGL manifest directory not found: {AG_DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(AG_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE DbSet SET ProductAsin = ? WHERE ProductTitle = ? AND InstallDirectory = ?",
            (game.game_id, game.name, game.install_dir)
        )
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()

        if rows_affected > 0:
            logger.info(f"Successfully updated ASIN for game {game.name}")
            return True
        else:
            logger.warning(f"No rows updated for {game.name} - game may not exist in database")
            return False

    except sqlite3.Error as e:
        logger.error(f"Failed to update ASIN for {game.name}: {e}")
        return False


def _update_nile_manifest(game):
    """
    Update Nile manifest with new install directory.
    """
    if not NILE_MANIFEST_PATH or not os.path.exists(NILE_MANIFEST_PATH):
        logger.error(f"Nile manifest directory not found: {NILE_MANIFEST_PATH}")
        return False

    if not os.path.exists(NILE_MANIFEST_PATH):
        logger.error(f"Nile manifest not found: {NILE_MANIFEST_PATH}")
        return False

    try:
        manifest_data = read_json(NILE_MANIFEST_PATH)

        for entry in manifest_data:
            if entry.get('id') == game.game_id:
                entry['path'] = game.install_dir

                backup_file(NILE_MANIFEST_PATH)
                save_json(manifest_data, NILE_MANIFEST_PATH)

                logger.info(f"Updated Nile manifest for game '{game.name}'")
                return True

        logger.warning(f"Game '{game.name}' not found in Nile manifest")
        return False

    except Exception as e:
        logger.error(f"Failed to update Nile manifest: {e}")
        return False
