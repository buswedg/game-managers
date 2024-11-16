import argparse
import filecmp
import json
import os
import shutil
from collections import defaultdict

from dotenv import load_dotenv

from utils import copytree_with_progress, read_json_file

load_dotenv()

LIBRARY_SOURCE = os.getenv('LIBRARY_SOURCE', 'legendary')

UPDATE_EGL_MANIFEST = os.getenv('UPDATE_EGL_MANIFEST', 'False').lower() == "true"
EGL_MANIFEST_DIR = os.getenv('EGL_MANIFEST_DIR')

UPDATE_LEGENDARY_MANIFEST = os.getenv('UPDATE_LEGENDARY_MANIFEST', 'False').lower() == "true"
LEGENDARY_MANIFEST_DIR = os.getenv('LEGENDARY_MANIFEST_DIR')

INSTALL_DIR_OPTIONS = os.getenv('INSTALL_DIR_OPTIONS').split(',')


def fetch_egl_games(game_id=None):
    game_tuples = []
    for manifest_file in os.listdir(EGL_MANIFEST_DIR):
        if manifest_file.endswith('.item'):
            manifest_path = os.path.join(EGL_MANIFEST_DIR, manifest_file)
            manifest_data = read_json_file(manifest_path)

            game_id = manifest_data['InstallationGuid']
            game_name = manifest_data['DisplayName']
            app_name = manifest_data['AppName']
            install_dir = manifest_data['InstallLocation']

            game_tuples.append((game_id, game_name, app_name, install_dir))

    return [
        game_tuple for game_tuple in game_tuples
        if not game_id or game_tuple[0] == game_id
    ] if game_tuples else []


def fetch_legendary_games(game_id=None):
    manifest_path = os.path.join(LEGENDARY_MANIFEST_DIR, 'installed.json')
    manifest_data = read_json_file(manifest_path)

    game_tuples = []
    for manifest_id, manifest_entry in manifest_data.items():
        game_id = manifest_entry['egl_guid']
        game_name = manifest_entry['title']
        app_name = manifest_entry['app_name']
        install_dir = manifest_entry['install_path']

        game_tuples.append((game_id, game_name, app_name, install_dir))

    return [
        game_tuple for game_tuple in game_tuples
        if not game_id or game_tuple[0] == game_id
    ] if game_tuples else []


def get_games_dict(game_id=None):
    if LIBRARY_SOURCE == "egl":
        fetched_games = fetch_egl_games(game_id)
    else:
        fetched_games = fetch_legendary_games(game_id)

    if not fetched_games:
        return {}

    # create games_dict from fetched game tuples, using base install dir as key
    games_dict = defaultdict(list)
    for game_id, game_name, app_name, install_dir in fetched_games:
        base_install_dir = os.path.dirname(install_dir)
        games_dict[base_install_dir].append((game_id, game_name, app_name, install_dir))

    # sort game_tuples within games_dict by game_name, over each base install dir key
    for _, game_tuples in games_dict.items():
        game_tuples.sort(key=lambda x: x[1].lower())

    # add unique index values to each tuple, over all base install dir keys
    game_index = 1
    for _, game_tuples in games_dict.items():
        for idx, game in enumerate(game_tuples, start=1):
            game_tuples[idx - 1] = (game_index,) + game
            game_index += 1

    return games_dict


def update_egl_manifest(game_id, new_install_dir):
    manifest_path = os.path.join(EGL_MANIFEST_DIR, game_id + ".item")
    shutil.copyfile(manifest_path, f'{manifest_path}.bak')

    manifest_data = read_json_file(manifest_path)

    manifest_data['InstallLocation'] = new_install_dir
    manifest_data['StagingLocation'] = os.path.join(new_install_dir, '.egstore/bps')
    manifest_data['ManifestLocation'] = os.path.join(new_install_dir, '.egstore')

    with open(manifest_path, 'w') as f:
        json.dump(manifest_data, f, indent=4)


def update_legendary_manifest(game_id, new_install_dir):
    manifest_path = os.path.join(LEGENDARY_MANIFEST_DIR, 'installed.json')
    shutil.copyfile(manifest_path, f'{manifest_path}.bak')

    manifest_data = read_json_file(manifest_path)

    found_game = False
    for manifest_id, manifest_entry in manifest_data.items():
        if manifest_entry.get('egl_guid') == game_id:
            manifest_entry['install_path'] = new_install_dir
            found_game = True
            break

    if found_game:
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=4)
    else:
        print(f"WARNING: {game_id} not found in the manifest. No changes made.")


def move_game(game_tuple, desired_base_dir):
    source_install_game_dir = game_tuple[4]

    base_game_dir_name = os.path.basename(source_install_game_dir)
    new_install_game_dir = os.path.join(desired_base_dir, base_game_dir_name)

    if os.path.abspath(source_install_game_dir) != os.path.abspath(new_install_game_dir):
        print(f"Copying from {source_install_game_dir} to {new_install_game_dir}")
        copytree_with_progress(source_install_game_dir, new_install_game_dir)
        game_dircmp = filecmp.dircmp(source_install_game_dir, new_install_game_dir, ignore=None)

        if not game_dircmp.left_only and not game_dircmp.right_only:
            print("\nCopy successful, updating manifest and removing old install location.")
            if UPDATE_EGL_MANIFEST:
                update_egl_manifest(game_tuple[1], new_install_game_dir)
            if UPDATE_LEGENDARY_MANIFEST:
                update_legendary_manifest(game_tuple[1], new_install_game_dir)
            if os.path.exists(source_install_game_dir):
                shutil.rmtree(source_install_game_dir)
        else:
            print("\nERROR: File comparison mismatch:")
            print("Left only: " if game_dircmp.left_only else "None")
            print("Right only: " if game_dircmp.right_only else "None")

            print("\nRemoving new install location.")
            if os.path.exists(new_install_game_dir):
                shutil.rmtree(new_install_game_dir)
    else:
        print("\nPreferred location is the same as the current location. No action required.")


def list_games(games_dict):
    print("GAMES BY BASE INSTALL LOCATION:")
    for base_install_dir, game_tuples in games_dict.items():
        print(f"\nBase Install Location: {base_install_dir}")
        for (index, game_id, game_name, app_name, install_dir) in game_tuples:
            print(f"  {index}. {game_id} - {game_name}")


def interactive(games_dict):
    selected_index = input("\nEnter the index number of the game you want to update or 'all' to move all games: ")

    if selected_index.lower() == 'all':
        for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
            print(f"{index}. Option {index}: {location}")

        try:
            desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
            if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                for _, game_tuples in games_dict.items():
                    for game_tuple in game_tuples:
                        move_game(game_tuple, desired_base_dir)
            else:
                print("ERROR: Invalid choice. Exiting.")

        except ValueError:
            print("ERROR: Invalid input. Please enter a valid choice.")

    else:
        selected_tuple = None
        selected_index = int(selected_index)
        for _, game_tuples in games_dict.items():
            for game_tuple in game_tuples:
                game_index = game_tuple[0]
                if game_index == selected_index:
                    selected_tuple = game_tuple
                    break

        if selected_tuple:
            print(f"\nSelected Game:")
            print(f"Game ID: {selected_tuple[1]}")
            print(f"Game Name: {selected_tuple[2]}")
            print(f"Current Install Location: {selected_tuple[4]}")

            print("\nChoose a preferred installation location option:")

            for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
                print(f"{index}. Option {index}: {location}")

            try:
                desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
                if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                    desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                    move_game(selected_tuple, desired_base_dir)
                else:
                    print("ERROR: Invalid choice. Exiting.")
            except ValueError:
                print("ERROR: Invalid input. Please enter a valid choice.")
        else:
            print("ERROR: Invalid Game ID.")


def main():
    parser = argparse.ArgumentParser(description="Epic Games Library Manager CLI")
    subparsers = parser.add_subparsers(title="subcommands", dest="command")

    subparsers.add_parser("list", help="List all games currently recognized by Epic Games.")

    move_parser = subparsers.add_parser("move", help="Move a game to a different location.")
    move_parser.add_argument("game_id", help="Game ID to move.")
    move_parser.add_argument("desired_base_dir", help="Desired base directory.")

    args = parser.parse_args()

    if args.command == "list":
        games_dict = get_games_dict()
        list_games(games_dict)
    elif args.command == "move":
        move_game(args.game_id, args.desired_base_dir)
    else:
        print("No command provided, running in interactive mode.")
        games_dict = get_games_dict()
        list_games(games_dict)
        interactive(games_dict)


if __name__ == "__main__":
    main()