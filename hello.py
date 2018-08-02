#!/usr/bin/python
#
# hello.py

import argparse

def main(param1, param2):
    print("Hello. I'm here!")
    print("param1 is %s" % param1)
    print("param2 is %s" % param2)

parser = argparse.ArgumentParser()
parser.add_argument('--param1', default='')
parser.add_argument('--param2', default='')
args = parser.parse_args()

if __name__ == "__main__":
    main(args.param1, args.param2)

