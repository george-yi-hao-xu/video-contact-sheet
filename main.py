from multiprocessing import freeze_support

from src.gen_video_sheet import main


if __name__ == "__main__":
    freeze_support()
    main()
