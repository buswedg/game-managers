import logging
import os

from dotenv import load_dotenv
from vdf import parse

load_dotenv()

STEAM_LIBFOLDERS_PATH = os.getenv('STEAM_LIBFOLDERS_PATH')

logger = logging.getLogger(__name__)


class Game:
    def __init__(self, game_id, name, install_dir, base_dir, index=None):
        self.index = index
        self.game_id = game_id
        self.name = name
        self.install_dir = install_dir
        self.base_dir = base_dir

    def __repr__(self):
        return f"Game({self.name}, {self.install_dir})"

    def get_dirs(self):
        return self.install_dir, self.base_dir

    def set_dirs(self, install_dir, base_dir):
        self.install_dir, self.base_dir = install_dir, base_dir


def fetch_steam_games():
    """
    Fetch games from Steam manifest files.
    """
    if not STEAM_LIBFOLDERS_PATH or not os.path.exists(STEAM_LIBFOLDERS_PATH):
        logger.error(f"Steam libraryfolders.vdf not found: {STEAM_LIBFOLDERS_PATH}")
        return []

    try:
        with open(STEAM_LIBFOLDERS_PATH, 'r', encoding='utf-8') as libfolders_raw_vdf:
            libfolders_parsed_vdf = parse(libfolders_raw_vdf)
        logging.debug("Successfully parsed libraryfolders.vdf")
    except Exception as e:
        logging.error(f"Failed to parse libraryfolders.vdf: {e}")
        return []

    libfolders = libfolders_parsed_vdf.get('libraryfolders', {})

    games = []
    for folder_id, lib_data in libfolders.items():
        try:
            apps_vdf = lib_data.get('apps', {})
            steamapps_dir = os.path.join(lib_data.get('path', ''), 'steamapps')

            if not os.path.isdir(steamapps_dir):
                logging.error(f"Steamapps directory not found for library: {steamapps_dir}")
                continue

            for game_id in apps_vdf:
                app_manifest_path = os.path.join(steamapps_dir, f"appmanifest_{game_id}.acf")
                if not os.path.exists(app_manifest_path):
                    logger.error(f"Manifest file not found: {app_manifest_path}")
                    continue

                try:
                    with open(app_manifest_path, encoding='utf-8') as appmanifest_raw_vdf:
                        appmanifest_parsed_vdf = parse(appmanifest_raw_vdf)
                    logging.debug(f"Successfully parsed appmanifest_{game_id}.acf")
                except Exception as e:
                    logging.error(f"Failed to parse appmanifest_{game_id}.acf: {e}")
                    continue

                app_state = appmanifest_parsed_vdf.get('AppState', {})
                install_folder = app_state.get('installdir', '')
                install_dir = os.path.join(steamapps_dir, 'common', install_folder)

                game = Game(
                    game_id=app_state.get('appid'),
                    name=app_state.get('name'),
                    install_dir=install_dir,
                    base_dir=steamapps_dir
                )
                games.append(game)

        except Exception as e:
            logger.error(f"Failed to process app manifest file: {e}")
            continue

    logger.info(f"Loaded {len(games)} Steam games")
    return games