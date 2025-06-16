import argparse
import filecmp
import logging
import os
import shutil
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv
from vdf import parse

from utils import check_proc, term_proc, copytree_with_progress

load_dotenv()

STEAM_DIR = os.getenv('STEAM_DIR')
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


def get_games_by_base_dir():
    """Get Steam games organized by base install directory."""
    logger = logging.getLogger('steam_manager')
    logger.info("Getting Steam games organized by base directory")

    if not STEAM_DIR or not os.path.exists(STEAM_DIR):
        logger.error(f"Steam directory not found or not configured: {STEAM_DIR}")
        return defaultdict(list)

    games_by_base_dir = defaultdict(list)

    libraryfolders_path = os.path.join(STEAM_DIR, 'config', 'libraryfolders.vdf')

    if not os.path.exists(libraryfolders_path):
        logger.error(f"Steam libraryfolders.vdf not found at: {libraryfolders_path}")
        return defaultdict(list)

    try:
        with open(libraryfolders_path, 'r') as libraryfolders_file:
            libfolders_vdf = parse(libraryfolders_file)
        logger.debug("Successfully parsed libraryfolders.vdf")
    except Exception as e:
        logger.error(f"Failed to parse libraryfolders.vdf: {e}")
        return defaultdict(list)

    libfolders = libfolders_vdf.get('libraryfolders', {})
    logger.info(f"Found {len(libfolders)} Steam library folders")

    total_games = 0
    for folder_id, lib_data in libfolders.items():
        try:
            path = lib_data.get('path', '')
            steamapps_dir = os.path.join(path, 'steamapps')

            if not os.path.exists(steamapps_dir):
                logger.warning(f"Steamapps directory not found: {steamapps_dir}")
                continue

            logger.debug(f"Processing library folder {folder_id}: {steamapps_dir}")

            manifest_files = [
                f
                for f in os.listdir(steamapps_dir)
                if f.startswith('appmanifest_') and f.endswith('.acf')
            ]

            logger.debug(f"Found {len(manifest_files)} manifest files in {steamapps_dir}")

            for manifest_file in manifest_files:
                try:
                    manifest_path = os.path.join(steamapps_dir, manifest_file)

                    with open(manifest_path, encoding='utf-8') as manifest_file_handle:
                        app_vdf = parse(manifest_file_handle)

                    app_state = app_vdf.get('AppState', {})
                    game_id = app_state.get('appid')
                    game_name = app_state.get('name')
                    install_dir = os.path.join(steamapps_dir, 'common', app_state.get('installdir', ''))
                    base_install_dir = os.path.dirname(install_dir)

                    if game_id and game_name:
                        game_tuple = (game_id, game_name, install_dir)
                        games_by_base_dir[base_install_dir].append(game_tuple)
                        total_games += 1
                        logger.debug(f"Loaded game: {game_name} ({game_id}) from {manifest_file}")
                    else:
                        logger.warning(f"Incomplete game data in {manifest_file}: ID={game_id}, Name={game_name}")

                except Exception as e:
                    logger.error(f"Failed to process manifest {manifest_file}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to process library folder {folder_id}: {e}")
            continue

    logger.info(f"Loaded {total_games} games across {len(games_by_base_dir)} base directories")

    for root_location, game_tuple in games_by_base_dir.items():
        game_tuple.sort(key=lambda x: x[1].lower())
        logger.debug(f"Sorted {len(game_tuple)} games in {root_location}")

    global_game_index = 1
    for root_location, game_tuple in games_by_base_dir.items():
        for index, game in enumerate(game_tuple, start=1):
            game_tuple[index - 1] = (global_game_index,) + game
            global_game_index += 1

    logger.info(f"Assigned global indices to {global_game_index - 1} games")
    return games_by_base_dir


def list_games(games_by_base_dir):
    """List all games organized by root install location."""
    logger = logging.getLogger('steam_manager')
    logger.debug("Listing Steam games")

    print("GAMES BY ROOT INSTALL LOCATION:")
    for root_location, game_tuple in games_by_base_dir.items():
        print(f"\nRoot Install Location: {root_location}")
        for (index, game_id, game_name, install_dir) in game_tuple:
            print(f"  {index}. {game_id} - {game_name}")

    total_games = sum(len(games) for games in games_by_base_dir.values())
    logger.info(f"Listed {total_games} games across {len(games_by_base_dir)} locations")


def move_game(game_id, desired_base_dir):
    """Move a Steam game to a different base directory."""
    logger = logging.getLogger('steam_manager')
    logger.info(f"Starting move operation for game ID {game_id} to {desired_base_dir}")

    if not STEAM_DIR or not os.path.exists(STEAM_DIR):
        logger.error(f"Steam directory not found: {STEAM_DIR}")
        return False

    libraryfolders_path = os.path.join(STEAM_DIR, 'config', 'libraryfolders.vdf')

    if not os.path.exists(libraryfolders_path):
        logger.error(f"Steam libraryfolders.vdf not found at: {libraryfolders_path}")
        return False

    try:
        with open(libraryfolders_path, 'r') as libraryfolders_file:
            libfolders_vdf = parse(libraryfolders_file)
        logger.debug("Successfully parsed libraryfolders.vdf for move operation")
    except Exception as e:
        logger.error(f"Failed to parse libraryfolders.vdf: {e}")
        return False

    libfolders = libfolders_vdf.get('libraryfolders', {})
    install_folder = None
    source_steamapps_dir = None

    for folder_id, lib_data in libfolders.items():
        try:
            apps_vdf = lib_data.get('apps', {})
            steamapps_dir = os.path.join(lib_data.get('path', ''), 'steamapps')

            if game_id in apps_vdf:
                logger.debug(f"Found game {game_id} in library folder {folder_id}")
                manifest_file_path = os.path.join(steamapps_dir, f"appmanifest_{game_id}.acf")

                if not os.path.exists(manifest_file_path):
                    logger.error(f"Manifest file not found: {manifest_file_path}")
                    continue

                with open(manifest_file_path, encoding='utf-8') as manifest_file:
                    app_vdf = parse(manifest_file)

                app_state = app_vdf.get('AppState', {})
                install_folder = app_state.get('installdir', '')
                source_steamapps_dir = steamapps_dir

                if install_folder:
                    logger.debug(f"Found install folder: {install_folder}")
                    break
                else:
                    logger.warning(f"No install directory found in manifest for game {game_id}")

        except Exception as e:
            logger.error(f"Error processing library folder {folder_id}: {e}")
            continue

    if not install_folder or not source_steamapps_dir:
        logger.error(f"Game {game_id} not found in any Steam library")
        return False

    source_install_dir = os.path.join(source_steamapps_dir, "common", install_folder)
    source_manifest_path = os.path.join(source_steamapps_dir, f"appmanifest_{game_id}.acf")
    new_install_dir = os.path.join(desired_base_dir, "steamapps", "common", install_folder)
    new_manifest_path = os.path.join(desired_base_dir, "steamapps", f"appmanifest_{game_id}.acf")

    logger.debug(f"Source install directory: {source_install_dir}")
    logger.debug(f"Source manifest: {source_manifest_path}")
    logger.debug(f"Target install directory: {new_install_dir}")
    logger.debug(f"Target manifest: {new_manifest_path}")

    if not os.path.exists(source_install_dir):
        logger.error(f"Source install directory does not exist: {source_install_dir}")
        print("Source install directory does not exist. Aborting move operation.")
        return False

    if not os.listdir(source_install_dir):
        logger.warning(f"Source install directory is empty: {source_install_dir}")
        print("Source install directory is empty. Aborting move operation.")
        return False

    if os.path.abspath(source_install_dir) != os.path.abspath(new_install_dir):
        try:
            logger.info(f"Copying from {source_install_dir} to {new_install_dir}")

            os.makedirs(os.path.dirname(new_install_dir), exist_ok=True)
            os.makedirs(os.path.dirname(new_manifest_path), exist_ok=True)

            copytree_with_progress(source_install_dir, new_install_dir)

            logger.info("Copy completed, verifying integrity...")
            dircmp = filecmp.dircmp(source_install_dir, new_install_dir, ignore=None)

            if not dircmp.left_only and not dircmp.right_only:
                logger.info("Copy verification successful, updating manifest and cleaning up")

                if os.path.exists(source_manifest_path):
                    shutil.move(source_manifest_path, new_manifest_path)
                    logger.debug(f"Moved manifest from {source_manifest_path} to {new_manifest_path}")
                else:
                    logger.warning(f"Source manifest not found: {source_manifest_path}")

                shutil.rmtree(source_install_dir)
                logger.info("Old install location removed successfully")

                print("\nCopy successful, updating manifest and removing old install location.")
                return True

            else:
                logger.error("File comparison mismatch detected:")
                logger.error(f"Left only: {dircmp.left_only if dircmp.left_only else 'None'}")
                logger.error(f"Right only: {dircmp.right_only if dircmp.right_only else 'None'}")

                logger.info("Removing new install location due to copy failure")
                if os.path.exists(new_install_dir):
                    shutil.rmtree(new_install_dir)
                if os.path.exists(new_manifest_path):
                    os.remove(new_manifest_path)

                print("\nERROR: File comparison mismatch:")
                print("Left only: ", dircmp.left_only if dircmp.left_only else "None")
                print("Right only: ", dircmp.right_only if dircmp.right_only else "None")
                print("\nRemoving new install location.")

                return False

        except Exception as e:
            logger.error(f"Failed to move game {game_id}: {e}")

            if os.path.exists(new_install_dir):
                try:
                    shutil.rmtree(new_install_dir)
                    logger.info("Cleaned up incomplete game directory")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up game directory: {cleanup_error}")

            if os.path.exists(new_manifest_path):
                try:
                    os.remove(new_manifest_path)
                    logger.info("Cleaned up incomplete manifest file")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up manifest file: {cleanup_error}")

            return False
    else:
        logger.info("Preferred location is the same as the current location. No action required.")
        print("\nPreferred location is the same as the current location. No action required.")
        return True


def move_all_games(desired_base_dir, games_by_base_dir):
    """Move all Steam games to the desired base directory."""
    logger = logging.getLogger('steam_manager')
    logger.info(f"Moving all games to: {desired_base_dir}")

    total_games = sum(len(games) for games in games_by_base_dir.values())
    current_game = 0
    successful_moves = 0
    failed_moves = 0

    for root_location, game_tuple in games_by_base_dir.items():
        for (global_game_index, game_id, game_name, install_dir) in game_tuple:
            current_game += 1
            logger.info(f"Moving game {current_game}/{total_games}: {game_name} ({game_id})")

            if move_game(game_id, desired_base_dir):
                successful_moves += 1
            else:
                failed_moves += 1

    logger.info(f"Completed moving all games. Success: {successful_moves}, Failed: {failed_moves}")


def interactive(games_by_base_dir):
    """Interactive mode for game selection and movement."""
    logger = logging.getLogger('steam_manager')
    logger.info("Starting interactive mode")

    list_games(games_by_base_dir)

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
                move_all_games(desired_base_dir, games_by_base_dir)
            else:
                logger.warning(f"Invalid choice: {desired_option}")
                print("ERROR: Invalid choice. Exiting.")
        except ValueError as e:
            logger.error(f"Invalid input in interactive mode: {e}")
            print("ERROR: Invalid input. Please enter a valid choice.")
    else:
        try:
            selected_index = int(selected_index)
            logger.debug(f"Looking for game with index: {selected_index}")

            selected_game_id, selected_game_name, selected_install_dir = None, None, None
            for root_location, game_tuple in games_by_base_dir.items():
                for (global_game_index, game_id, game_name, install_dir) in game_tuple:
                    if global_game_index == selected_index:
                        selected_game_id, selected_game_name, selected_install_dir = game_id, game_name, install_dir
                        break

            if selected_game_id:
                logger.info(f"Selected game: {selected_game_name} ({selected_game_id})")

                print(f"\nSelected Game:")
                print(f"Game ID: {selected_game_id}")
                print(f"Game Name: {selected_game_name}")
                print(f"Current Install Location: {selected_install_dir}")

                print("\nChoose a preferred installation location option:")

                for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
                    print(f"{index}. Option {index}: {location}")

                try:
                    desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
                    logger.debug(f"User selected destination option: {desired_option}")

                    if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                        desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                        logger.info(f"Moving {selected_game_name} to: {desired_base_dir}")
                        move_game(selected_game_id, desired_base_dir)
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
            print("ERROR: Invalid input. Please enter a valid index number or 'all'.")


def main():
    logger = setup_logging()
    logger.info("=== Steam Library Manager Started ===")
    logger.info(f"Steam directory: {STEAM_DIR}")
    logger.info(f"Install directory options: {INSTALL_DIR_OPTIONS}")

    logger.debug("Checking if Steam processes are running")
    steam_pids = check_proc("steam")
    if steam_pids:
        logger.warning(f"Steam is running (PIDs: {steam_pids})")
        close_steam = input("Close Steam to continue? (YES/no): ")
        logger.debug(f"User response to close Steam: {close_steam}")

        if close_steam.lower() == "yes":
            logger.info("Terminating Steam processes")
            term_proc(steam_pids)
            print()
        else:
            logger.info("User chose not to close Steam, exiting")
            exit()
    else:
        logger.info("Steam is not running, proceeding")

    parser = argparse.ArgumentParser(description="Steam Library Manager CLI")
    subparsers = parser.add_subparsers(title="subcommands", dest="command")

    subparsers.add_parser("list", help="List all games currently recognized by Steam.")

    move_parser = subparsers.add_parser("move", help="Move a game to a different location.")
    move_parser.add_argument("game_id", help="Game ID to move.")
    move_parser.add_argument("desired_base_dir", help="Desired base directory.")

    args = parser.parse_args()
    logger.debug(f"Command line arguments: {args}")

    try:
        if args.command == "list":
            logger.info("Running in list mode")
            games_by_base_dir = get_games_by_base_dir()
            list_games(games_by_base_dir)
        elif args.command == "move":
            logger.info(f"Running in move mode for game_id: {args.game_id}")
            move_game(args.game_id, args.desired_base_dir)
        else:
            logger.info("Running in interactive mode")
            games_by_base_dir = get_games_by_base_dir()
            interactive(games_by_base_dir)

    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        raise
    finally:
        logger.info("=== Steam Library Manager Finished ===")


if __name__ == "__main__":
    main()
