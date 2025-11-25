import sys

from .cli import app

def main():
    if len(sys.argv) == 1:
        app(["--help"])
    else:
        app()

if __name__ == "__main__":
    main()
