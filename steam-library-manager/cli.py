import argparse
import filecmp
import os
import shutil
from collections import defaultdict

from dotenv import load_dotenv
from vdf import parse

from utils import check_proc, term_proc, copytree_with_progress

load_dotenv()

STEAM_DIR = os.getenv('STEAM_DIR')
INSTALL_DIR_OPTIONS = os.getenv('INSTALL_DIR_OPTIONS').split(',')


def get_games_by_base_dir():
    games_by_base_dir = defaultdict(list)

    libraryfolders_path = os.path.join(STEAM_DIR, 'config', 'libraryfolders.vdf')
    with open(libraryfolders_path, 'r') as libraryfolders_file:
        libfolders_vdf = parse(libraryfolders_file)

    libfolders = libfolders_vdf.get('libraryfolders', {})
    for _, lib_data in libfolders.items():
        try:
            path = lib_data.get('path', '')
            steamapps_dir = os.path.join(path, 'steamapps')

            manifest_files = [
                f
                for f in os.listdir(steamapps_dir)
                if f.startswith('appmanifest_') and f.endswith('.acf')
            ]

            for manifest_file in manifest_files:
                manifest_path = os.path.join(steamapps_dir, manifest_file)
                with open(manifest_path, encoding='utf-8') as manifest_file:
                    app_vdf = parse(manifest_file)

                app_state = app_vdf.get('AppState', {})
                game_id = app_state.get('appid')
                game_name = app_state.get('name')
                install_dir = os.path.join(steamapps_dir, app_state.get('installdir', ''))
                base_install_dir = os.path.dirname(install_dir)
                game_tuple = (game_id, game_name, install_dir)
                games_by_base_dir[base_install_dir].append(game_tuple)

        except ValueError as e:
            print(f"ERROR: {e}")
            pass

    for root_location, game_tuple in games_by_base_dir.items():
        game_tuple.sort(key=lambda x: x[1].lower())

    global_game_index = 1
    for root_location, game_tuple in games_by_base_dir.items():
        for index, game in enumerate(game_tuple, start=1):
            game_tuple[index - 1] = (global_game_index,) + game
            global_game_index += 1

    return games_by_base_dir


def list_games(games_by_base_dir):
    print("GAMES BY ROOT INSTALL LOCATION:")
    for root_location, game_tuple in games_by_base_dir.items():
        print(f"\nRoot Install Location: {root_location}")
        for (index, game_id, game_name, install_dir) in game_tuple:
            print(f"  {index}. {game_id} - {game_name}")


def move_game(game_id, desired_base_dir):
    libraryfolders_path = os.path.join(STEAM_DIR, 'config', 'libraryfolders.vdf')
    with open(libraryfolders_path, 'r') as libraryfolders_file:
        libfolders_vdf = parse(libraryfolders_file)

    libfolders = libfolders_vdf.get('libraryfolders', {})
    for _, lib_data in libfolders.items():
        try:
            apps_vdf = lib_data.get('apps', {})
            steamapps_dir = os.path.join(lib_data.get('path', ''), 'steamapps')

            if game_id in apps_vdf:
                manifest_file = os.path.join(steamapps_dir, f"appmanifest_{game_id}.acf")

                with open(manifest_file) as manifest_file:
                    app_vdf = parse(manifest_file)

                app_state = app_vdf.get('AppState', {})
                install_folder = app_state.get('installdir', '')

        except ValueError:
            pass

    source_install_dir = os.path.join(steamapps_dir, "common", install_folder)
    source_manifest_path = os.path.join(steamapps_dir, f"appmanifest_{game_id}.acf")
    new_install_dir = os.path.join(desired_base_dir, "common", install_folder)
    new_manifest_path = os.path.join(desired_base_dir, f"appmanifest_{game_id}.acf")

    if not os.path.exists(source_install_dir) or not os.listdir(source_install_dir):
        print("Source install directory is empty. Aborting move operation.")
        return

    if os.path.abspath(source_install_dir) != os.path.abspath(new_install_dir):
        print(f"Copying from {source_install_dir} to {new_install_dir}")
        copytree_with_progress(source_install_dir, new_install_dir)
        dircmp = filecmp.dircmp(source_install_dir, new_install_dir, ignore=None)

        if not dircmp.left_only and not dircmp.right_only:
            print("\nCopy successful, updating manifest and removing old install location.")
            shutil.move(source_manifest_path, new_manifest_path)
            shutil.rmtree(source_install_dir)
        else:
            print("\nERROR: File comparison mismatch:")
            print("Left only: ", dircmp.left_only if dircmp.left_only else "None")
            print("Right only: ", dircmp.right_only if dircmp.right_only else "None")

            print("\nRemoving new install location.")
            if os.path.exists(new_install_dir):
                shutil.rmtree(new_install_dir)
    else:
        print("\nPreferred location is the same as the current location. No action required.")


def move_all_games(desired_base_dir, games_by_base_dir):
    for root_location, game_tuple in games_by_base_dir.items():
        for (global_game_index, game_id, game_name, install_dir) in game_tuple:
            move_game(game_id, desired_base_dir)


def interactive(games_by_base_dir):
    list_games(games_by_base_dir)

    selected_index = input("\nEnter the index number of the game you want to update or 'all' to move all games: ")

    if selected_index.lower() == 'all':
        for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
            print(f"{index}. Option {index}: {location}")

        try:
            desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
            if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                move_all_games(desired_base_dir, games_by_base_dir)
            else:
                print("ERROR: Invalid choice. Exiting.")
        except ValueError:
            print("ERROR: Invalid input. Please enter a valid choice.")
    else:
        try:
            selected_index = int(selected_index)
            selected_game_id, selected_game_name, selected_install_dir = None, None, None
            for root_location, game_tuple in games_by_base_dir.items():
                for (global_game_index, game_id, game_name, install_dir) in game_tuple:
                    if global_game_index == selected_index:
                        selected_game_id, selected_game_name, selected_install_dir = game_id, game_name, install_dir
                        break

            if selected_game_id:
                print(f"\nSelected Game:")
                print(f"Game ID: {selected_game_id}")
                print(f"Game Name: {selected_game_name}")
                print(f"Current Install Location: {selected_install_dir}")

                print("\nChoose a preferred installation location option:")

                for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
                    print(f"{index}. Option {index}: {location}")

                try:
                    desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
                    if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                        desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                        move_game(selected_game_id, desired_base_dir)
                    else:
                        print("ERROR: Invalid choice. Exiting.")
                except ValueError:
                    print("ERROR: Invalid input. Please enter a valid choice.")
            else:
                print("ERROR: Invalid Game ID.")
        except ValueError:
            print("ERROR: Invalid input. Please enter a valid index number or 'all'.")


def main():
    steam_pids = check_proc("steam")
    if steam_pids:
        close_steam = input("Close Steam to continue? (YES/no): ")
        if close_steam.lower() == "yes":
            term_proc(steam_pids)
            print()
        else:
            exit()

    parser = argparse.ArgumentParser(description="Steam Library Manager CLI")
    subparsers = parser.add_subparsers(title="subcommands", dest="command")

    subparsers.add_parser("list", help="List all games currently recognized by Steam.")

    move_parser = subparsers.add_parser("move", help="Move a game to a different location.")
    move_parser.add_argument("game_id", help="Game ID to move.")
    move_parser.add_argument("desired_base_dir", help="Desired base directory.")

    args = parser.parse_args()

    if args.command == "list":
        games_by_base_dir = get_games_by_base_dir()
        list_games(games_by_base_dir)
    elif args.command == "move":
        move_game(args.game_id, args.desired_base_dir)
    else:
        print("No command provided, running in interactive mode.")
        games_by_base_dir = get_games_by_base_dir()
        interactive(games_by_base_dir)


if __name__ == "__main__":
    main()
