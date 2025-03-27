import sys
import logging
from pathlib import Path
from glob import glob
from roam2doc.parse import DocParser
logger = logging.getLogger('roam2doc-io')

def parse_fileset(filepaths):
    root_parser = None
    parsers = []
    for path in filepaths:
        with open(path, "r", encoding="utf-8") as f:
            contents = f.read()
        if root_parser is None:
            root_parser = parser = DocParser(contents, str(path))
        else:
            parser = DocParser(contents, str(path), root=root_parser.root)
        parsers.append(parser)
        parser.parse()
    return parsers

def parse_one_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        contents = f.read()
    parser = DocParser(contents, str(filepath), root=root_parser.root)
    parser.parse()
    return parser

def parse_directory(dirpath):
    path = Path(dirpath)
    targets = []
    for filepath in path.glob('*.org'):
        targets.append(filepath)
    return parse_fileset(targets)

def parse_from_filelist(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        contents = f.read()
    targets = []
    for line in contents.split('\n'):
        if line.strip() != '':
            path = Path(line)
            targets.append(path)
    return parse_fileset(targets)
            
if __name__=="__main__":
    tdir = sys.argv[1]
    if Path(tdir).is_dir():
        res = parse_directory(tdir)
        print(res[0].root.to_html())
    elif tdir.endswith('.org'):
        res = parse_file(tdir)
        print(res.root.to_html())
    else:
        res = parse_from_filelist(tdir)
        print(res[0].root.to_html())
        

    
