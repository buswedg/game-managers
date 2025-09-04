import logging
import os
from collections import defaultdict

from fetch import fetch_games
from manifest import update_manifest
from utils import copy_directory, remove_dir_if_exists

logger = logging.getLogger(__name__)


def get_games_dict():
    """
    Get all games as a dictionary grouped by base directory.
    """
    games_dict = defaultdict(list)

    games = fetch_games()

    for game in games:
        games_dict[game.base_dir].append(game)

    for game_list in games_dict.values():
        game_list.sort(key=lambda x: x.name.lower())

    index = 1
    for game_list in games_dict.values():
        for game in game_list:
            game.index = index
            index += 1

    logger.info(f"Organized {index - 1} games into {len(games_dict)} directories")
    return games_dict


def get_game_from_dict(games_dict, lookup_value, by_index=False):
    """
    Get game from the dictionary by its index or game_id.
    """
    for game_list in games_dict.values():
        for game in game_list:
            if by_index and game.index == lookup_value:
                return game
            elif game.game_id == lookup_value:
                return game

    return None


def process_game(game, target_base_dir):
    """
    Process the game, including copying files, updating the manifest, and cleaning up old files.
    """
    if not os.path.exists(game.install_dir):
        logger.error(f"Source game directory does not exist: {game.install_dir}")
        return False

    target_dir = os.path.join(target_base_dir, os.path.basename(game.install_dir))

    if os.path.exists(target_dir):
        logger.error(f"Target game directory already exists: {target_dir}")
        return False

    original_install_dir, original_base_dir = game.get_dirs()

    def rollback():
        game.set_dirs(original_install_dir, original_base_dir)
        remove_dir_if_exists(target_dir)

    try:
        if not copy_directory(game.install_dir, target_dir):
            logger.error(f"Failed to copy directory for game '{game.name}'")
            rollback()
            return False

        logger.info(f"Successfully copied directory for game '{game.name}'")

        game.set_dirs(target_dir, target_base_dir)

        if not update_manifest(game):
            logger.error(f"Failed to update manifest for game '{game.name}'")
            rollback()
            return False

        logger.info(f"Successfully updated manifest for game '{game.name}'")

        remove_dir_if_exists(original_install_dir)
        return True

    except Exception as e:
        logger.error(f"Unexpected error processing game '{game.name}': {e}")
        rollback()
        return False
