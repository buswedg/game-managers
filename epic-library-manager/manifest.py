import logging
import os

from dotenv import load_dotenv

from utils import read_json, save_json, backup_file

load_dotenv()

EGS_MANIFEST_DIR = os.getenv('EGS_MANIFEST_DIR')
EGS_LAUNCHER_DATA_PATH = os.getenv('EGS_LAUNCHER_DATA_PATH')
LEGENDARY_MANIFEST_PATH = os.getenv('LEGENDARY_MANIFEST_PATH')
UPDATE_EGS_MANIFEST = os.getenv('UPDATE_EGS_MANIFEST', 'False').lower() == "true"
UPDATE_LEGENDARY_MANIFEST = os.getenv('UPDATE_LEGENDARY_MANIFEST', 'False').lower() == "true"

logger = logging.getLogger(__name__)


def update_manifest(game):
    """
    Update manifest files with the new game location.
    """
    success = True

    if UPDATE_EGS_MANIFEST:
        success &= _update_egl_manifest(game)
        success &= _update_egl_launcher_data(game)

    if UPDATE_LEGENDARY_MANIFEST:
        success &= _update_legendary_manifest(game)

    return success


def _update_egl_manifest(game):
    """
    Update EGS manifest with new install directory.
    """
    if not EGS_MANIFEST_DIR or not os.path.exists(EGS_MANIFEST_DIR):
        logger.error(f"EGS manifest directory not found: {EGS_MANIFEST_DIR}")
        return False

    manifest_files = [f for f in os.listdir(EGS_MANIFEST_DIR) if f.endswith('.item')]

    logger.info(f"Found {len(manifest_files)} manifest files in {EGS_MANIFEST_DIR}")

    for manifest_file in manifest_files:
        try:
            manifest_path = os.path.join(EGS_MANIFEST_DIR, manifest_file)
            manifest_data = read_json(manifest_path)

            if manifest_data.get('InstallationGuid') == game.game_id:
                manifest_data['InstallLocation'] = game.install_dir
                manifest_data['StagingLocation'] = os.path.join(game.install_dir, '.egstore/bps')
                manifest_data['ManifestLocation'] = os.path.join(game.install_dir, '.egstore')

                backup_file(manifest_path)
                save_json(manifest_data, manifest_path)

                logger.info(f"Updated EGS manifest for game '{game.name}'")
                return True

        except Exception as e:
            logger.error(f"Failed to update EGS manifest '{manifest_file}': {e}")
            return False

    logger.error(f"EGS manifest not found for game '{game.name}'")
    return False


def _update_egl_launcher_data(game):
    """
    Update EGS launcher data with new install directory.
    """
    if not EGS_LAUNCHER_DATA_PATH or not os.path.exists(EGS_LAUNCHER_DATA_PATH):
        logger.error(f"EGS launcher data file not found: {EGS_LAUNCHER_DATA_PATH}")
        return False

    try:
        launcher_data = read_json(EGS_LAUNCHER_DATA_PATH)

        installation_list = launcher_data.get("InstallationList", [])
        for entry in installation_list:
            if entry.get('AppName') == game.app_name:
                entry['InstallLocation'] = game.install_dir

                backup_file(EGS_LAUNCHER_DATA_PATH)
                save_json(launcher_data, EGS_LAUNCHER_DATA_PATH)

                logger.info(f"Updated EGS launcher data for game '{game.name}'")
                return True

    except Exception as e:
        logger.error(f"Failed to update EGS launcher data: {e}")

    logger.error(f"EGS launcher data not found for game '{game.name}'")
    return False


def _update_legendary_manifest(game):
    """
    Update Legendary manifest with new install directory.
    """
    if not LEGENDARY_MANIFEST_PATH or not os.path.exists(LEGENDARY_MANIFEST_PATH):
        logger.error(f"Legendary manifest directory not found: {LEGENDARY_MANIFEST_PATH}")
        return False

    if not os.path.exists(LEGENDARY_MANIFEST_PATH):
        logger.error(f"Legendary manifest not found: {LEGENDARY_MANIFEST_PATH}")
        return False

    try:
        manifest_data = read_json(LEGENDARY_MANIFEST_PATH)

        for entry in manifest_data.values():
            if entry.get('app_name') == game.app_name:
                entry['install_path'] = game.install_dir

                backup_file(LEGENDARY_MANIFEST_PATH)
                save_json(manifest_data, LEGENDARY_MANIFEST_PATH)

                logger.info(f"Updated Legendary manifest for game '{game.name}'")
                return True

        logger.warning(f"Game '{game.name}' not found in Legendary manifest")
        return False

    except Exception as e:
        logger.error(f"Failed to update Legendary manifest: {e}")
        return False
