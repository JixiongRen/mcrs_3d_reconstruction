"""Run after installing the project with pip install -e ."""
from guidewire.workflows.offline import main


if __name__ == "__main__":
    raise SystemExit(main())
