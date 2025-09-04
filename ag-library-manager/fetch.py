import logging
import os
import sqlite3

from dotenv import load_dotenv

from utils import read_json

load_dotenv()

AG_DB_PATH = os.getenv('AG_DB_PATH')
NILE_MANIFEST_PATH = os.getenv('NILE_MANIFEST_PATH')
LIBRARY_SOURCE = os.getenv('LIBRARY_SOURCE', 'nile')

logger = logging.getLogger(__name__)


class Game:
    def __init__(self, game_id, name, install_dir, index=None):
        self.index = index
        self.game_id = game_id
        self.name = name
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
    if LIBRARY_SOURCE == "ag":
        return _fetch_ag_games()

    return _fetch_nile_games()


def _fetch_ag_games():
    """
    Fetch games from Amazon Games database.
    """
    if not AG_DB_PATH or not os.path.exists(AG_DB_PATH):
        logger.error(f"AG database not found: {AG_DB_PATH}")
        return []

    try:
        conn = sqlite3.connect(AG_DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT ProductAsin, ProductTitle, InstallDirectory FROM DbSet"
        )

        rows = cursor.fetchall()
        conn.close()

        logger.info(f"Fetched {len(rows)} games from AG database")

    except sqlite3.Error as e:
        logger.error(f"Failed to query AG database: {e}")
        return []

    games = []
    for product_asin, product_title, install_directory in rows:
        game = Game(
            game_id=product_asin,
            name=product_title,
            install_dir=install_directory
        )
        games.append(game)

    logger.info(f"Loaded {len(games)} AG games")
    return games


def _fetch_nile_games():
    """
    Fetch games from the Nile manifest file.
    """
    if not NILE_MANIFEST_PATH or not os.path.exists(NILE_MANIFEST_PATH):
        logger.error(f"Nile manifest library.json not found: {NILE_MANIFEST_PATH}")
        return []

    data = read_json(NILE_MANIFEST_PATH)

    games = []
    for entry in data:
        try:
            game = Game(
                game_id=entry['id'],
                name=os.path.basename(entry['path']),
                install_dir=entry['path']
            )
            games.append(game)

        except KeyError as e:
            logger.warning(f"Incomplete entry: {e}")

    logger.info(f"Loaded {len(games)} Nile games")
    return games
