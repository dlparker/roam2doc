import sys
import logging
from pathlib import Path
from glob import glob
from roam2doc.parse import DocParser
logger = logging.getLogger('roam2doc-io')


class FilesToParsers:

    def __init__(self, file_list):
        self.file_list = [] 
        self.skip_files = []
        self.parsers = []
        for filepath in file_list:
            self.file_list.append(Path(filepath).resolve())

    def run_parsers(self):
        root_parser = None
        contents_by_path = {}
        include_paths = []
        parsers = []
        for path in self.file_list:
            with open(path, "r", encoding="utf-8") as f:
                contents = f.read()
            new_lines = []
            skip_counter = 0
            content_lines = contents.split('\n')
            for pos, line in enumerate(content_lines):
                if skip_counter > 0:
                    skip_counter -= 1
                    continue
                if not line.upper().startswith("#+BEGIN_FILE_INCLUDE"):
                    new_lines.append(line)
                    continue
                check_paths = []
                rpos = 0
                rest = content_lines[pos+1:]
                rline = rest[rpos]
                while not rline.upper().startswith("#+END_FILE_INCLUDE"):
                    check_paths.append(rline.strip())
                    rpos += 1
                    if rpos == len(rest):
                        raise Exception(f'End of file reached before include file section in {path} terminated')
                    rline = rest[rpos]
                    skip_counter += 1
                skip_counter += 1
                for check_path in check_paths:
                    if check_path == "":
                        continue
                    if check_path.startswith('/'):
                        check_path = Path(check_path)
                    else:
                        # assume it is realtive to including path
                        dirname = path.parent
                        check_path = Path(dirname, check_path)
                    if not check_path.exists():
                        raise ValueError(f"File {path} tried to include non-existant file {check_path}")
                    include_paths.append(check_path)
                    with open(check_path, "r", encoding="utf-8") as f:
                        include_contents = f.read()
                    new_lines.extend(include_contents.split('\n'))
            contents = '\n'.join(new_lines)
            contents_by_path[path] = contents

        for path in self.file_list:
            if path not in include_paths:
                contents = contents_by_path[path]
                if root_parser is None:
                    root_parser = parser = DocParser(contents, str(path))
                else:
                    parser = DocParser(contents, str(path), root=root_parser.root)
                parsers.append(parser)
                parser.parse()
        return parsers

def parse_fileset(filepaths):
    ftp = FilesToParsers(filepaths)
    return ftp.run_parsers()

def parse_one_file(filepath):
    filepaths = [filepath,]
    ftp = FilesToParsers(filepaths)
    return ftp.run_parsers()[0]

def parse_directory(dirpath):
    path = Path(dirpath)
    targets = []
    for filepath in path.glob('*.org'):
        targets.append(filepath)
    ftp = FilesToParsers(targets)
    return ftp.run_parsers()

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
    ftp = FilesToParsers(targets)
    return ftp.run_parsers()
            
    
