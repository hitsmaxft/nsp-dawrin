"""Print the current conversion chain identity for the native launcher."""
import argparse
from pathlib import Path
from nsp_runtime.cache import chain_version

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(chain_version(args.directory))
