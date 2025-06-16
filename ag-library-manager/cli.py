import argparse
import filecmp
import json
import logging
import os
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv

from utils import copytree_with_progress, read_json_file, generate_random_asin

load_dotenv()

LIBRARY_SOURCE = os.getenv('LIBRARY_SOURCE', 'nile')

UPDATE_AG_MANIFEST = os.getenv('UPDATE_AG_MANIFEST', 'False').lower() == "true"
AG_MANIFEST_DB_PATH = os.getenv('AG_MANIFEST_DB_PATH')

UPDATE_NILE_MANIFEST = os.getenv('UPDATE_NILE_MANIFEST', 'True').lower() == "true"
NILE_MANIFEST_DIR = os.getenv('NILE_MANIFEST_DIR')

INSTALL_DIR_OPTIONS = os.getenv('INSTALL_DIR_OPTIONS').split(',')


def setup_logging():
    """Set up logging configuration with both file and console handlers."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"epic_games_manager_{timestamp}.log")

    logger = logging.getLogger('epic_games_manager')
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(message)s'
    )

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def update_asin(game_id, game_name, install_dir):
    """Update ASIN in the Amazon Games database."""
    logger = logging.getLogger('amazon_games_manager')
    logger.info(f"Updating ASIN for {game_name} to {game_id}")

    if not AG_MANIFEST_DB_PATH or not os.path.exists(AG_MANIFEST_DB_PATH):
        logger.error(f"Amazon Games database not found: {AG_MANIFEST_DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(AG_MANIFEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE DbSet SET ProductAsin = ? WHERE ProductTitle = ? AND InstallDirectory = ?",
            (game_id, game_name, install_dir)
        )
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()

        if rows_affected > 0:
            logger.info(f"Successfully updated ASIN for {game_name}")
            return True
        else:
            logger.warning(f"No rows updated for {game_name} - game may not exist in database")
            return False

    except sqlite3.Error as e:
        logger.error(f"Failed to update ASIN for {game_name}: {e}")
        return False


def fetch_ag_games(game_id=None):
    """Fetch games from Amazon Games database."""
    logger = logging.getLogger('amazon_games_manager')
    logger.debug(f"Fetching Amazon Games with filter game_id: {game_id}")

    if not AG_MANIFEST_DB_PATH or not os.path.exists(AG_MANIFEST_DB_PATH):
        logger.error(f"Amazon Games database not found: {AG_MANIFEST_DB_PATH}")
        return []

    rows = []
    try:
        conn = sqlite3.connect(AG_MANIFEST_DB_PATH)
        cursor = conn.cursor()

        if game_id:
            cursor.execute(
                "SELECT ProductAsin, ProductTitle, InstallDirectory FROM DbSet WHERE ProductAsin = ?",
                (game_id,)
            )
            logger.debug(f"Querying database for specific game_id: {game_id}")
        else:
            cursor.execute(
                "SELECT ProductAsin, ProductTitle, InstallDirectory FROM DbSet"
            )
            logger.debug("Querying database for all games")

        rows = cursor.fetchall()
        conn.close()

        logger.info(f"Fetched {len(rows)} games from Amazon Games database")

    except sqlite3.Error as e:
        logger.error(f"Failed to query Amazon Games database: {e}")
        return []

    result = [
        (game_id, game_name, install_dir)
        for game_id, game_name, install_dir in rows
    ] if rows else []

    logger.debug(f"Returning {len(result)} game tuples")
    return result


def fetch_nile_games(game_id=None):
    """Fetch games from Nile manifest file."""
    logger = logging.getLogger('amazon_games_manager')
    logger.debug(f"Fetching Nile games with filter game_id: {game_id}")

    if not NILE_MANIFEST_DIR or not os.path.exists(NILE_MANIFEST_DIR):
        logger.error(f"Nile manifest directory not found: {NILE_MANIFEST_DIR}")
        return []

    manifest_path = os.path.join(NILE_MANIFEST_DIR, 'installed.json')

    if not os.path.exists(manifest_path):
        logger.error(f"Nile installed.json not found at: {manifest_path}")
        return []

    try:
        manifest_data = read_json_file(manifest_path)
        logger.debug(f"Loaded Nile manifest with {len(manifest_data)} entries")
    except Exception as e:
        logger.error(f"Failed to read Nile manifest: {e}")
        return []

    game_tuples = []
    for manifest_entry in manifest_data:
        try:
            entry_game_id = manifest_entry['id']
            game_name = os.path.basename(manifest_entry['path'])
            install_dir = manifest_entry['path']

            game_tuples.append((entry_game_id, game_name, install_dir))
            logger.debug(f"Loaded game: {game_name} ({entry_game_id}) from Nile manifest")

        except KeyError as e:
            logger.warning(f"Incomplete Nile manifest entry: missing {e}")
            continue
        except Exception as e:
            logger.error(f"Failed to process Nile manifest entry: {e}")
            continue

    filtered_games = [
        game_tuple for game_tuple in game_tuples
        if not game_id or game_tuple[0] == game_id
    ] if game_tuples else []

    logger.info(f"Fetched {len(filtered_games)} Nile games (filtered from {len(game_tuples)} total)")
    return filtered_games


def get_games_dict(game_id=None):
    """Get games dictionary organized by base install directory."""
    logger = logging.getLogger('amazon_games_manager')
    logger.info(f"Getting games dictionary using {LIBRARY_SOURCE} as source")

    if LIBRARY_SOURCE == "ag":
        fetched_games = fetch_ag_games(game_id)
    else:
        fetched_games = fetch_nile_games(game_id)

    if not fetched_games:
        logger.warning("No games found")
        return {}

    # create games_dict from fetched game tuples, using base install dir as key
    games_dict = defaultdict(list)
    for game_id, game_name, install_dir in fetched_games:
        if not game_id:
            logger.info(f"Generating random ASIN for {game_name}")
            game_id = generate_random_asin()
            update_asin(game_id, game_name, install_dir)

        base_install_dir = os.path.dirname(install_dir)
        games_dict[base_install_dir].append((game_id, game_name, install_dir))

    logger.debug(f"Games organized into {len(games_dict)} base directories")

    # sort game_tuples within games_dict by game_name, over each base install dir key
    for base_dir, game_tuples in games_dict.items():
        game_tuples.sort(key=lambda x: x[1].lower())
        logger.debug(f"Sorted {len(game_tuples)} games in {base_dir}")

    # add unique index values to each tuple, over all base install dir keys
    game_index = 1
    for _, game_tuples in games_dict.items():
        for idx, game in enumerate(game_tuples, start=1):
            game_tuples[idx - 1] = (game_index,) + game
            game_index += 1

    logger.info(f"Created games dictionary with {game_index - 1} total games")
    return games_dict


def update_ag_manifest(game_id, new_install_dir):
    """Update Amazon Games database with new install directory."""
    logger = logging.getLogger('amazon_games_manager')
    logger.info(f"Updating Amazon Games manifest for {game_id} to {new_install_dir}")

    if not AG_MANIFEST_DB_PATH or not os.path.exists(AG_MANIFEST_DB_PATH):
        logger.error(f"Amazon Games database not found: {AG_MANIFEST_DB_PATH}")
        return False

    try:
        # Create backup
        backup_path = f'{AG_MANIFEST_DB_PATH}.bak'
        shutil.copyfile(AG_MANIFEST_DB_PATH, backup_path)
        logger.debug(f"Created backup at {backup_path}")

        conn = sqlite3.connect(AG_MANIFEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE DbSet SET InstallDirectory = ? WHERE ProductAsin = ?",
            (new_install_dir, game_id)
        )
        conn.commit()

        if cursor.rowcount == 0:
            logger.warning(f"{game_id} not found in the database. No changes made.")
            conn.close()
            return False
        else:
            logger.info(f"Successfully updated Amazon Games manifest for {game_id}")
            conn.close()
            return True

    except sqlite3.Error as e:
        logger.error(f"Failed to update Amazon Games database for {game_id}: {e}")
        return False


def update_nile_manifest(game_id, new_install_dir):
    """Update Nile manifest file with new install directory."""
    logger = logging.getLogger('amazon_games_manager')
    logger.info(f"Updating Nile manifest for {game_id} to {new_install_dir}")

    if not NILE_MANIFEST_DIR or not os.path.exists(NILE_MANIFEST_DIR):
        logger.error(f"Nile manifest directory not found: {NILE_MANIFEST_DIR}")
        return False

    manifest_path = os.path.join(NILE_MANIFEST_DIR, 'installed.json')

    if not os.path.exists(manifest_path):
        logger.error(f"Nile manifest file not found: {manifest_path}")
        return False

    try:
        backup_path = f'{manifest_path}.bak'
        shutil.copyfile(manifest_path, backup_path)
        logger.debug(f"Created backup at {backup_path}")

        manifest_data = read_json_file(manifest_path)

        found_game = False
        for manifest_entry in manifest_data:
            if manifest_entry.get('id') == game_id:
                manifest_entry['path'] = new_install_dir
                found_game = True
                logger.debug(f"Updated manifest entry for {game_id}")
                break

        if found_game:
            with open(manifest_path, 'w') as f:
                json.dump(manifest_data, f, indent=4)
            logger.info(f"Successfully updated Nile manifest for {game_id}")
            return True
        else:
            logger.warning(f"{game_id} not found in the Nile manifest. No changes made.")
            return False

    except Exception as e:
        logger.error(f"Failed to update Nile manifest for {game_id}: {e}")
        return False


def move_game(game_tuple, desired_base_dir):
    """Move a game to a different base directory."""
    logger = logging.getLogger('amazon_games_manager')

    game_id = game_tuple[1]
    game_name = game_tuple[2]
    source_install_game_dir = game_tuple[3]

    logger.info(f"Starting move operation for {game_name} ({game_id})")
    logger.info(f"Source: {source_install_game_dir}")
    logger.info(f"Target base directory: {desired_base_dir}")

    base_game_dir_name = os.path.basename(source_install_game_dir)
    new_install_game_dir = os.path.join(desired_base_dir, base_game_dir_name)

    source_install_data_dir = os.path.join(
        os.path.dirname(source_install_game_dir), "__InstallData__", base_game_dir_name
    )
    new_install_data_dir = os.path.join(
        os.path.dirname(new_install_game_dir), "__InstallData__", base_game_dir_name
    )

    logger.debug(f"Target game directory: {new_install_game_dir}")
    logger.debug(f"Source install data directory: {source_install_data_dir}")
    logger.debug(f"Target install data directory: {new_install_data_dir}")

    if os.path.abspath(source_install_game_dir) != os.path.abspath(new_install_game_dir):
        try:
            logger.info(f"Copying from {source_install_game_dir} to {new_install_game_dir}")
            copytree_with_progress(source_install_game_dir, new_install_game_dir)

            logger.info("Game directory copy completed, verifying integrity...")
            game_dircmp = filecmp.dircmp(source_install_game_dir, new_install_game_dir, ignore=None)

            if os.path.exists(source_install_data_dir):
                logger.info(f"Copying install data from {source_install_data_dir} to {new_install_data_dir}")
                copytree_with_progress(source_install_data_dir, new_install_data_dir)
            else:
                logger.debug("No install data directory found to copy")

            if not game_dircmp.left_only and not game_dircmp.right_only:
                logger.info("Copy verification successful, updating manifests and cleaning up")

                manifest_updated = True
                if UPDATE_AG_MANIFEST:
                    if not update_ag_manifest(game_id, new_install_game_dir):
                        manifest_updated = False

                if UPDATE_NILE_MANIFEST:
                    if not update_nile_manifest(game_id, new_install_game_dir):
                        manifest_updated = False

                if manifest_updated:
                    directories_to_remove = [source_install_game_dir]
                    if os.path.exists(source_install_data_dir):
                        directories_to_remove.append(source_install_data_dir)

                    for directory in directories_to_remove:
                        if os.path.exists(directory):
                            logger.debug(f"Removing old directory: {directory}")
                            shutil.rmtree(directory)

                    logger.info("Old install locations removed successfully")
                else:
                    logger.warning("Manifest update failed, keeping old install location")

            else:
                logger.error("File comparison mismatch detected:")
                logger.error(f"Left only: {game_dircmp.left_only if game_dircmp.left_only else 'None'}")
                logger.error(f"Right only: {game_dircmp.right_only if game_dircmp.right_only else 'None'}")

                logger.info("Removing new install locations due to copy failure")
                directories_to_cleanup = [new_install_game_dir, new_install_data_dir]
                for directory in directories_to_cleanup:
                    if os.path.exists(directory):
                        logger.debug(f"Cleaning up: {directory}")
                        shutil.rmtree(directory)

        except Exception as e:
            logger.error(f"Failed to move game {game_name}: {e}")

            directories_to_cleanup = [new_install_game_dir, new_install_data_dir]
            for directory in directories_to_cleanup:
                if os.path.exists(directory):
                    try:
                        shutil.rmtree(directory)
                        logger.info(f"Cleaned up incomplete copy: {directory}")
                    except Exception as cleanup_error:
                        logger.error(f"Failed to clean up {directory}: {cleanup_error}")
    else:
        logger.info("Preferred location is the same as the current location. No action required.")


def list_games(games_dict):
    """List all games organized by base install location."""
    logger = logging.getLogger('amazon_games_manager')
    logger.debug("Listing games")

    print("GAMES BY BASE INSTALL LOCATION:")
    for base_install_dir, game_tuples in games_dict.items():
        print(f"\nBase Install Location: {base_install_dir}")
        for (index, game_id, game_name, install_dir) in game_tuples:
            print(f"  {index}. {game_id} - {game_name}")

    logger.info(f"Listed {sum(len(games) for games in games_dict.values())} games across {len(games_dict)} locations")


def interactive(games_dict):
    """Interactive mode for game selection and movement."""
    logger = logging.getLogger('amazon_games_manager')
    logger.info("Starting interactive mode")

    selected_index = input("\nEnter the index number of the game you want to update or 'all' to move all games: ")
    logger.debug(f"User selected: {selected_index}")

    if selected_index.lower() == 'all':
        logger.info("User selected to move all games")

        for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
            print(f"{index}. Option {index}: {location}")

        try:
            desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
            logger.debug(f"User selected option: {desired_option}")

            if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                logger.info(f"Moving all games to: {desired_base_dir}")

                total_games = sum(len(games) for games in games_dict.values())
                current_game = 0

                for _, game_tuples in games_dict.items():
                    for game_tuple in game_tuples:
                        current_game += 1
                        logger.info(f"Moving game {current_game}/{total_games}: {game_tuple[2]}")
                        move_game(game_tuple, desired_base_dir)
            else:
                logger.warning(f"Invalid choice: {desired_option}")
                print("ERROR: Invalid choice. Exiting.")

        except ValueError as e:
            logger.error(f"Invalid input in interactive mode: {e}")
            print("ERROR: Invalid input. Please enter a valid choice.")

    else:
        try:
            selected_tuple = None
            selected_index = int(selected_index)
            logger.debug(f"Looking for game with index: {selected_index}")

            for _, game_tuples in games_dict.items():
                for game_tuple in game_tuples:
                    game_index = game_tuple[0]
                    if game_index == selected_index:
                        selected_tuple = game_tuple
                        break

            if selected_tuple:
                logger.info(f"Selected game: {selected_tuple[2]} ({selected_tuple[1]})")

                print(f"\nSelected Game:")
                print(f"Game ID: {selected_tuple[1]}")
                print(f"Game Name: {selected_tuple[2]}")
                print(f"Current Install Location: {selected_tuple[3]}")

                print("\nChoose a preferred installation location option:")

                for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
                    print(f"{index}. Option {index}: {location}")

                try:
                    desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
                    logger.debug(f"User selected destination option: {desired_option}")

                    if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                        desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                        logger.info(f"Moving {selected_tuple[2]} to: {desired_base_dir}")
                        move_game(selected_tuple, desired_base_dir)
                    else:
                        logger.warning(f"Invalid destination choice: {desired_option}")
                        print("ERROR: Invalid choice. Exiting.")
                except ValueError as e:
                    logger.error(f"Invalid input for destination choice: {e}")
                    print("ERROR: Invalid input. Please enter a valid choice.")
            else:
                logger.warning(f"Game with index {selected_index} not found")
                print("ERROR: Invalid Game ID.")

        except ValueError as e:
            logger.error(f"Invalid game index input: {e}")
            print("ERROR: Invalid input. Please enter a valid game index.")


def main():
    logger = setup_logging()
    logger.info("=== Amazon Games Library Manager Started ===")
    logger.info(f"Library source: {LIBRARY_SOURCE}")
    logger.info(f"Update Amazon Games manifest: {UPDATE_AG_MANIFEST}")
    logger.info(f"Update Nile manifest: {UPDATE_NILE_MANIFEST}")

    parser = argparse.ArgumentParser(description="Amazon Games Library Manager CLI")
    subparsers = parser.add_subparsers(title="subcommands", dest="command")

    subparsers.add_parser("list", help="List all games currently recognized by Amazon Games.")

    move_parser = subparsers.add_parser("move", help="Move a game to a different location.")
    move_parser.add_argument("game_id", help="Game ID to move.")
    move_parser.add_argument("desired_base_dir", help="Desired base directory.")

    args = parser.parse_args()
    logger.debug(f"Command line arguments: {args}")

    try:
        if args.command == "list":
            logger.info("Running in list mode")
            games_dict = get_games_dict()
            list_games(games_dict)
        elif args.command == "move":
            logger.info(f"Running in move mode for game_id: {args.game_id}")
            # Note: This part needs to be updated to work with the new tuple structure
            logger.warning("Direct move command not fully implemented with new tuple structure")
            # move_game(args.game_id, args.desired_base_dir)
        else:
            logger.info("Running in interactive mode")
            games_dict = get_games_dict()
            list_games(games_dict)
            interactive(games_dict)

    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        raise
    finally:
        logger.info("=== Amazon Games Library Manager Finished ===")


if __name__ == "__main__":
    main()
