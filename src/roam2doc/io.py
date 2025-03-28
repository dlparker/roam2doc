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
    if len(sys.argv) < 2:
        print("You must supply a file or directory name")
        raise SystemExit(1)
    target = sys.argv[1]
    if Path(target).is_dir():
        res = parse_directory(target)
        root = res[0].root
    elif target.endswith('.org'):
        res = parse_file(target)
        root = res.root
    else:
        res = parse_from_filelist(target)
        root = res[0].root
    if len(sys.argv) > 2:
        outfilepath = Path(sys.argv[2])
        if outfilepath.exists():
            print(f"refusing to overwrite file {outfilepath}")
            raise SystemExit(1)
        if not outfilepath.parent.exists():
            print(f"output directory {outfilepath.parent} does not exist")
            raise SystemExit(1)
        with open(outfilepath, 'w', encoding="utf-8") as f:
            f.write(root.to_html())
    else:
        print(root.to_html())
        

    
