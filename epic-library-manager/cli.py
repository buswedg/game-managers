import argparse
import filecmp
import json
import logging
import os
import shutil
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv

from utils import copytree_with_progress, read_json_file

load_dotenv()

LIBRARY_SOURCE = os.getenv('LIBRARY_SOURCE', 'legendary')

UPDATE_EGL_MANIFEST = os.getenv('UPDATE_EGL_MANIFEST', 'False').lower() == "true"
EGL_MANIFEST_DIR = os.getenv('EGL_MANIFEST_DIR')

UPDATE_LEGENDARY_MANIFEST = os.getenv('UPDATE_LEGENDARY_MANIFEST', 'False').lower() == "true"
LEGENDARY_MANIFEST_DIR = os.getenv('LEGENDARY_MANIFEST_DIR')

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


def fetch_egl_games(game_id=None):
    """Fetch games from EGL manifest files."""
    logger = logging.getLogger('epic_games_manager')
    logger.debug(f"Fetching EGL games with filter game_id: {game_id}")

    if not EGL_MANIFEST_DIR or not os.path.exists(EGL_MANIFEST_DIR):
        logger.error(f"EGL manifest directory not found or not configured: {EGL_MANIFEST_DIR}")
        return []

    game_tuples = []
    manifest_files = [f for f in os.listdir(EGL_MANIFEST_DIR) if f.endswith('.item')]
    logger.info(f"Found {len(manifest_files)} EGL manifest files")

    for manifest_file in manifest_files:
        try:
            manifest_path = os.path.join(EGL_MANIFEST_DIR, manifest_file)
            manifest_data = read_json_file(manifest_path)

            game_id_from_manifest = manifest_data['InstallationGuid']
            game_name = manifest_data['DisplayName']
            app_name = manifest_data['AppName']
            install_dir = manifest_data['InstallLocation']

            game_tuples.append((game_id_from_manifest, game_name, app_name, install_dir))
            logger.debug(f"Loaded game: {game_name} ({app_name}) from {manifest_file}")

        except Exception as e:
            logger.error(f"Failed to process manifest file {manifest_file}: {e}")
            continue

    filtered_games = [
        game_tuple for game_tuple in game_tuples
        if not game_id or game_tuple[0] == game_id
    ] if game_tuples else []

    logger.info(f"Fetched {len(filtered_games)} EGL games (filtered from {len(game_tuples)} total)")
    return filtered_games


def fetch_legendary_games(filter_game_id=None):
    """Fetch games from Legendary manifest file."""
    logger = logging.getLogger('epic_games_manager')
    logger.debug(f"Fetching Legendary games with filter game_id: {filter_game_id}")

    if not LEGENDARY_MANIFEST_DIR or not os.path.exists(LEGENDARY_MANIFEST_DIR):
        logger.error(f"Legendary manifest directory not found or not configured: {LEGENDARY_MANIFEST_DIR}")
        return []

    manifest_path = os.path.join(LEGENDARY_MANIFEST_DIR, 'installed.json')

    if not os.path.exists(manifest_path):
        logger.error(f"Legendary installed.json not found at: {manifest_path}")
        return []

    try:
        manifest_data = read_json_file(manifest_path)
        logger.debug(f"Loaded Legendary manifest with {len(manifest_data)} entries")
    except Exception as e:
        logger.error(f"Failed to read Legendary manifest: {e}")
        return []

    game_tuples = []
    for manifest_id, manifest_entry in manifest_data.items():
        try:
            game_id = manifest_entry.get('egl_guid', None) or manifest_id
            game_name = manifest_entry['title']
            app_name = manifest_entry['app_name']
            install_dir = manifest_entry['install_path']

            game_tuples.append((game_id, game_name, app_name, install_dir))
            logger.debug(f"Loaded game: {game_name} ({app_name}) from Legendary manifest")

        except KeyError as e:
            logger.warning(f"Incomplete manifest entry for {manifest_id}: missing {e}")
            continue
        except Exception as e:
            logger.error(f"Failed to process manifest entry {manifest_id}: {e}")
            continue

    filtered_games = [
        game_tuple for game_tuple in game_tuples
        if not filter_game_id or game_tuple[0] == filter_game_id
    ] if game_tuples else []

    logger.info(f"Fetched {len(filtered_games)} Legendary games (filtered from {len(game_tuples)} total)")
    return filtered_games


def get_games_dict(game_id=None):
    """Get games dictionary organized by base install directory."""
    logger = logging.getLogger('epic_games_manager')
    logger.info(f"Getting games dictionary using {LIBRARY_SOURCE} as source")

    if LIBRARY_SOURCE == "egl":
        fetched_games = fetch_egl_games(game_id)
    else:
        fetched_games = fetch_legendary_games(game_id)

    if not fetched_games:
        logger.warning("No games found")
        return {}

    # create games_dict from fetched game tuples, using base install dir as key
    games_dict = defaultdict(list)
    for game_id, game_name, app_name, install_dir in fetched_games:
        base_install_dir = os.path.dirname(install_dir)
        games_dict[base_install_dir].append((game_id, game_name, app_name, install_dir))

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


def update_egl_manifest(game_id, new_install_dir):
    """Update EGL manifest file with new install directory."""
    logger = logging.getLogger('epic_games_manager')
    logger.info(f"Updating EGL manifest for game_id {game_id} to {new_install_dir}")

    # Find the manifest file by searching for the one with matching InstallationGuid
    if not EGL_MANIFEST_DIR or not os.path.exists(EGL_MANIFEST_DIR):
        logger.error(f"EGL manifest directory not found or not configured: {EGL_MANIFEST_DIR}")
        return False

    manifest_files = [f for f in os.listdir(EGL_MANIFEST_DIR) if f.endswith('.item')]
    manifest_path = None

    for manifest_file in manifest_files:
        try:
            temp_manifest_path = os.path.join(EGL_MANIFEST_DIR, manifest_file)
            manifest_data = read_json_file(temp_manifest_path)

            if manifest_data.get('InstallationGuid') == game_id:
                manifest_path = temp_manifest_path
                logger.debug(f"Found matching manifest file: {manifest_file}")
                break

        except Exception as e:
            logger.warning(f"Failed to read manifest file {manifest_file}: {e}")
            continue

    if not manifest_path:
        logger.error(f"EGL manifest file not found for game_id: {game_id}")
        return False

    try:
        backup_path = f'{manifest_path}.bak'
        shutil.copyfile(manifest_path, backup_path)
        logger.debug(f"Created backup at {backup_path}")

        manifest_data = read_json_file(manifest_path)

        manifest_data['InstallLocation'] = new_install_dir
        manifest_data['StagingLocation'] = os.path.join(new_install_dir, '.egstore/bps')
        manifest_data['ManifestLocation'] = os.path.join(new_install_dir, '.egstore')

        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=4)

        logger.info(f"Successfully updated EGL manifest for game_id {game_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update EGL manifest for game_id {game_id}: {e}")
        return False


def update_legendary_manifest(app_name, new_install_dir):
    """Update Legendary manifest file with new install directory."""
    logger = logging.getLogger('epic_games_manager')
    logger.info(f"Updating Legendary manifest for {app_name} to {new_install_dir}")

    manifest_path = os.path.join(LEGENDARY_MANIFEST_DIR, 'installed.json')

    if not os.path.exists(manifest_path):
        logger.error(f"Legendary manifest file not found: {manifest_path}")
        return False

    try:
        # Create backup
        backup_path = f'{manifest_path}.bak'
        shutil.copyfile(manifest_path, backup_path)
        logger.debug(f"Created backup at {backup_path}")

        manifest_data = read_json_file(manifest_path)

        found_game = False
        for manifest_id, manifest_entry in manifest_data.items():
            if manifest_entry.get('app_name') == app_name:
                manifest_entry['install_path'] = new_install_dir
                found_game = True
                logger.debug(f"Updated manifest entry {manifest_id}")
                break

        if found_game:
            with open(manifest_path, 'w') as f:
                json.dump(manifest_data, f, indent=4)
            logger.info(f"Successfully updated Legendary manifest for {app_name}")
            return True
        else:
            logger.warning(f"{app_name} not found in the Legendary manifest. No changes made.")
            return False

    except Exception as e:
        logger.error(f"Failed to update Legendary manifest for {app_name}: {e}")
        return False


def move_game(game_tuple, desired_base_dir):
    """Move a game to a different base directory."""
    logger = logging.getLogger('epic_games_manager')

    game_id = game_tuple[1]
    app_name = game_tuple[3]
    source_install_game_dir = game_tuple[4]

    logger.info(f"Starting move operation for {app_name}")
    logger.info(f"Source: {source_install_game_dir}")
    logger.info(f"Target base directory: {desired_base_dir}")

    base_game_dir_name = os.path.basename(source_install_game_dir)
    new_install_game_dir = os.path.join(desired_base_dir, base_game_dir_name)

    logger.debug(f"Target full path: {new_install_game_dir}")

    if os.path.abspath(source_install_game_dir) != os.path.abspath(new_install_game_dir):
        def compare_directories(dcmp):
            if dcmp.left_only or dcmp.right_only or dcmp.diff_files:
                return False
            for sub_dcmp in dcmp.subdirs.values():
                if not compare_directories(sub_dcmp):
                    return False
            return True

        try:
            logger.info(f"Copying from {source_install_game_dir} to {new_install_game_dir}")
            copytree_with_progress(source_install_game_dir, new_install_game_dir)

            logger.info("Copy completed, verifying integrity...")
            game_dircmp = filecmp.dircmp(source_install_game_dir, new_install_game_dir, ignore=None)

            if compare_directories(game_dircmp):
                logger.info("Copy verification successful, updating manifests and cleaning up")

                manifest_updated = True
                if UPDATE_EGL_MANIFEST:
                    if not update_egl_manifest(game_id, new_install_game_dir):
                        manifest_updated = False

                if UPDATE_LEGENDARY_MANIFEST:
                    if not update_legendary_manifest(app_name, new_install_game_dir):
                        manifest_updated = False

                if manifest_updated and os.path.exists(source_install_game_dir):
                    shutil.rmtree(source_install_game_dir)
                    logger.info("Old install location removed successfully")
                elif not manifest_updated:
                    logger.warning("Manifest update failed, keeping old install location")

            else:
                logger.error("File comparison mismatch detected in recursive check:")
                logger.error(f"Left only: {game_dircmp.left_only}")
                logger.error(f"Right only: {game_dircmp.right_only}")
                logger.error(f"Different files: {game_dircmp.diff_files}")

                logger.info("Removing new install location due to copy failure")
                if os.path.exists(new_install_game_dir):
                    shutil.rmtree(new_install_game_dir)

        except Exception as e:
            logger.error(f"Failed to move game {app_name}: {e}")
            if os.path.exists(new_install_game_dir):
                try:
                    shutil.rmtree(new_install_game_dir)
                    logger.info("Cleaned up incomplete copy due to error")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up incomplete copy: {cleanup_error}")
    else:
        logger.info("Preferred location is the same as the current location. No action required.")


def list_games(games_dict):
    """List all games organized by base install location."""
    logger = logging.getLogger('epic_games_manager')
    logger.debug("Listing games")

    print("GAMES BY BASE INSTALL LOCATION:")
    for base_install_dir, game_tuples in games_dict.items():
        print(f"\nBase Install Location: {base_install_dir}")
        for (index, game_id, game_name, app_name, install_dir) in game_tuples:
            print(f"  {index}. {game_id} - {game_name}")

    logger.info(f"Listed {sum(len(games) for games in games_dict.values())} games across {len(games_dict)} locations")


def interactive(games_dict):
    """Interactive mode for game selection and movement."""
    logger = logging.getLogger('epic_games_manager')
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
                logger.info(f"Selected game: {selected_tuple[2]} ({selected_tuple[3]})")

                print(f"\nSelected Game:")
                print(f"Game ID: {selected_tuple[1]}")
                print(f"Game Name: {selected_tuple[2]}")
                print(f"Current Install Location: {selected_tuple[4]}")

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
    logger.info("=== Epic Games Library Manager Started ===")
    logger.info(f"Library source: {LIBRARY_SOURCE}")
    logger.info(f"Update EGL manifest: {UPDATE_EGL_MANIFEST}")
    logger.info(f"Update Legendary manifest: {UPDATE_LEGENDARY_MANIFEST}")

    parser = argparse.ArgumentParser(description="Epic Games Library Manager CLI")
    subparsers = parser.add_subparsers(title="subcommands", dest="command")

    subparsers.add_parser("list", help="List all games currently recognized by Epic Games.")

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
        logger.info("=== Epic Games Library Manager Finished ===")


if __name__ == "__main__":
    main()
