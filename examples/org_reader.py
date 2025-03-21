#!/usr/bin/env python
import sys
from pathlib import Path
try:
    import pyorg2 as test_import
except ModuleNotFoundError:
    parent = str(Path(__file__).resolve().parent.parent)
    sys.path.append(parent)
#from pyorg2.file_parser import parse_org_file, parse_org_directory, parse_org_files, OrgFileParser
from pyorg2.org_orig import Org

def xmain(filepath):
    parser = OrgFileParser()
    parser.parse_file(filepath)

def main(file_path):
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"{file_path} is not a valid file")
    with file_path.open('r', encoding='utf-8') as f:
        text = f.read()
    org = Org(text)
    print(org.html())

if __name__=="__main__":
    if len(sys.argv) != 2:
        raise Exception('You must supply an input file')
    filepath = Path(sys.argv[1]).resolve()
    main(filepath)
