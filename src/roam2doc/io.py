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
    parser = DocParser(contents, str(filepath))
    parser.parse()
    return parser

def parse_directory(dirpath):
    path = Path(dirpath)
    targets = []
    for filepath in path.glob('*.org'):
        targets.append(filepath)
    return parse_fileset(targets)

def parse_from_filelist(listfile):
    filepath = Path(listfile)
    with open(filepath, "r", encoding="utf-8") as f:
        contents = f.read()
    targets = []
    for line in contents.split('\n'):
        if line.strip() != '':
            if not line.startswith('/'):
                path = Path(filepath.parent, line)
            else:
                path = Path(line)
            targets.append(path)
    return parse_fileset(targets)
            
    
