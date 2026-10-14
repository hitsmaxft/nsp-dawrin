"""Compatibility facade for a single base NSP/XCI content set."""
import argparse
import json
from content import ContentSet, ContentError, Container, KeyStore, Nca, decrypt


class Package(ContentSet):
    def __init__(self,path,keys):
        super().__init__([path],keys)
        self.path=self.containers[0].path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package');parser.add_argument('keys');parser.add_argument('output')
    args=parser.parse_args()
    package=Package(args.package,args.keys)
    try:
        package.prepare(args.output)
        print(json.dumps(package.describe()))
    finally:package.close()
