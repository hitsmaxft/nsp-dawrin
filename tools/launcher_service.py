"""Version-one JSON-lines desktop API over private child-process stdio."""
import argparse
import json
import sys
from launcher.service import Launcher
from launcher.store import data_directory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',default=str(data_directory()))
    args=parser.parse_args(); service=Launcher(args.data_dir)
    try:
        for line in sys.stdin:
            identity=None
            try:
                if len(line)>262144: raise ValueError('Request exceeds limit')
                request=json.loads(line); identity=request.get('id')
                if request.get('version')!=1 or not isinstance(request.get('params',{}),dict): raise ValueError('Invalid protocol request')
                result=service.dispatch(request['method'],request.get('params',{}))
                response=dict(id=identity,result=result)
            except Exception as error:
                response=dict(id=identity,error=dict(message=str(error)))
            print(json.dumps(response),flush=True)
    finally: service.close()


if __name__=='__main__': main()
