from .bootstrap import apply_pending_at_startup

apply_pending_at_startup()

from .app import main  # noqa: E402

if __name__ == "__main__":
    main()
