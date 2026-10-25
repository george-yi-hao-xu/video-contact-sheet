from multiprocessing import freeze_support

from src.gui import launch_app


if __name__ == "__main__":
    freeze_support()
    launch_app()
