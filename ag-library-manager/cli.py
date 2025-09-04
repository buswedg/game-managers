import argparse
import os

from dotenv import load_dotenv

from library import get_games_dict, get_game_from_dict, process_game
from utils import close_process
from logger import setup_logger

load_dotenv()

LIBRARY_SOURCE = os.getenv('LIBRARY_SOURCE', 'nile')
UPDATE_AG_MANIFEST = os.getenv('UPDATE_AG_MANIFEST', 'False').lower() == "true"
UPDATE_NILE_MANIFEST = os.getenv('UPDATE_NILE_MANIFEST', 'True').lower() == "true"
INSTALL_DIR_OPTIONS = os.getenv('INSTALL_DIR_OPTIONS').split(',')

logger = setup_logger(log_name='ag_library_manager')


def list_games(games_dict):
    """
    List all games organized by base install location.
    """
    logger.info("GAMES BY BASE INSTALL LOCATION:")
    for base_install_dir, games in games_dict.items():
        logger.info(f"\nBase Install Location: {base_install_dir}")
        for game in games:
            logger.info(f"  {game.index}. {game.game_id} - {game.name}")

    total_games = sum(len(games) for games in games_dict.values())
    logger.info(f"\nListed {total_games} games across {len(games_dict)} locations")


def interactive(games_dict):
    """
    Interactive mode for game selection and movement.
    """
    logger.info("Starting interactive mode")

    selected_index = input("\nEnter the index number of the game you want to update or 'all' to move all games: ")
    logger.debug(f"User selected: {selected_index}")

    if selected_index.lower() == "all":
        logger.info("User selected to move all games")

        for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
            print(f"{index}. Option {index}: {location}")

        try:
            desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
            logger.debug(f"User selected option: {desired_option}")

            if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                logger.info(f"Moving all games to: {desired_base_dir}")

                close_process('Amazon Games.exe')

                total_games = sum(len(games) for games in games_dict.values())
                current_game = 0
                for _, games in games_dict.items():
                    for game in games:
                        current_game += 1
                        logger.info(f"Moving game {current_game}/{total_games}: {game.name}")
                        process_game(game, desired_base_dir)
            else:
                logger.warning(f"Invalid choice: {desired_option}")

        except ValueError as e:
            logger.error(f"Invalid input in interactive mode: {e}")

    else:
        try:
            selected_index = int(selected_index)
            logger.debug(f"Looking for game with index: {selected_index}")

            game = get_game_from_dict(games_dict, selected_index, by_index=True)
            if game:
                logger.info(f"Selected game: {game.name}")

                logger.info(f"\nSelected Game:")
                logger.info(f"Game ID: {game.game_id}")
                logger.info(f"Game Name: {game.name}")
                logger.info(f"Current Install Location: {game.install_dir}")

                logger.info("\nChoose a preferred installation location option:")

                for index, location in enumerate(INSTALL_DIR_OPTIONS, start=1):
                    logger.info(f"{index}. Option {index}: {location}")

                try:
                    desired_option = int(input(f"\nEnter your choice (1-{len(INSTALL_DIR_OPTIONS)}): "))
                    logger.debug(f"User selected destination option: {desired_option}")

                    if 1 <= desired_option <= len(INSTALL_DIR_OPTIONS):
                        desired_base_dir = INSTALL_DIR_OPTIONS[desired_option - 1]
                        logger.info(f"Moving '{game.name}' to '{desired_base_dir}'")
                        close_process('Amazon Games.exe')
                        process_game(game, desired_base_dir)

                    else:
                        logger.warning(f"Invalid destination choice: {desired_option}")

                except ValueError as e:
                    logger.error(f"Invalid input for destination choice: {e}")

            else:
                logger.warning(f"Game with index '{selected_index}' not found")

        except ValueError as e:
            logger.error(f"Invalid input for game index: {e}")


def main():
    logger.info("=== Amazon Games Library Manager Started ===")
    logger.info(f"Library source: {LIBRARY_SOURCE}")
    logger.info(f"Update AG manifest: {UPDATE_AG_MANIFEST}")
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
            logger.info(f"Running in move mode, for game_id: {args.game_id}")

            games_dict = get_games_dict()

            game = get_game_from_dict(games_dict, args.game_id)
            if not game:
                logger.error(f"Game with ID '{args.game_id}' not found.")
                return

            close_process('Amazon Games.exe')
            process_game(game, args.desired_base_dir)

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
