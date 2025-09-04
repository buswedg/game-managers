import logging
import os

from dotenv import load_dotenv

from utils import read_json

load_dotenv()

EGS_MANIFEST_DIR = os.getenv('EGS_MANIFEST_DIR')
LEGENDARY_MANIFEST_PATH = os.getenv('LEGENDARY_MANIFEST_PATH')
LIBRARY_SOURCE = os.getenv('LIBRARY_SOURCE', 'legendary')

logger = logging.getLogger(__name__)


class Game:
    def __init__(self, game_id, name, app_name, install_dir, index=None):
        self.index = index
        self.game_id = game_id
        self.name = name
        self.app_name = app_name
        self.install_dir = install_dir
        self.base_dir = os.path.dirname(install_dir)

    def __repr__(self):
        return f"Game({self.name}, {self.install_dir})"

    def get_dirs(self):
        return self.install_dir, self.base_dir

    def set_dirs(self, install_dir, base_dir):
        self.install_dir, self.base_dir = install_dir, base_dir


def fetch_games():
    """
    Fetch games from the configured source.
    """
    if LIBRARY_SOURCE == "egs":
        return _fetch_egl_games()

    return _fetch_legendary_games()


def _fetch_egl_games():
    """
    Fetch games from EGS manifest files.
    """
    if not EGS_MANIFEST_DIR or not os.path.exists(EGS_MANIFEST_DIR):
        logger.error(f"EGS manifest directory not found: {EGS_MANIFEST_DIR}")
        return []

    games = []
    manifest_files = [f for f in os.listdir(EGS_MANIFEST_DIR) if f.endswith('.item')]

    for manifest_file in manifest_files:
        try:
            manifest_path = os.path.join(EGS_MANIFEST_DIR, manifest_file)
            manifest_data = read_json(manifest_path)

            game = Game(
                game_id=manifest_data['InstallationGuid'],
                name=manifest_data['DisplayName'],
                app_name=manifest_data['AppName'],
                install_dir=manifest_data['InstallLocation']
            )
            games.append(game)

        except Exception as e:
            logger.error(f"Failed to process manifest file: {e}")

    logger.info(f"Loaded {len(games)} EGS games")
    return games


def _fetch_legendary_games():
    """
    Fetch games from the Legendary manifest file.
    """
    if not LEGENDARY_MANIFEST_PATH or not os.path.exists(LEGENDARY_MANIFEST_PATH):
        logger.error(f"Legendary manifest installed.json not found: {LEGENDARY_MANIFEST_PATH}")
        return []

    data = read_json(LEGENDARY_MANIFEST_PATH)

    games = []
    for manifest_id, entry in data.items():
        try:
            game = Game(
                game_id=entry.get('egl_guid', manifest_id),
                name=entry['title'],
                app_name=entry['app_name'],
                install_dir=entry['install_path']
            )
            games.append(game)

        except KeyError as e:
            logger.warning(f"Incomplete entry for {manifest_id}: {e}")

    logger.info(f"Loaded {len(games)} Legendary games")
    return games
