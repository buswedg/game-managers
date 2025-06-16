# Steam Library Manager

Allows users to move their Steam games between different drives/ locations, by offering routines to move the game files
and update Steam's game manifest files accordingly.

## Getting Started

### Prerequisites

- Python 3.x and virtualenv installed, e.g.:

    ```bash
    pip install virtualenv
    ```

### Installation

1. Clone this repository to your local machine.

2. Set up a virtual environment, activate it, and install requirements via Command Prompt:

    ```bash
    python -m venv env
    call env/Scripts/activate
    pip install -r requirements.txt
    ```

## Usage

Close Epic Game Store, then either start run.bat from windows directly, or run the following via Command Prompt:

	```bash
	call env/Scripts/activate
	python cli.py
	deactivate
	```

Follow the on-screen instructions to manage your game collection.
