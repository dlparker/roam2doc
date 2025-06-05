import sys
import logging
from pathlib import Path
from glob import glob
import re
from roam2doc.parse import DocParser
logger = logging.getLogger('roam2doc.io')

heading_pattern = re.compile(r'^(?P<stars>\*+)[ \t]*(?P<heading>.*)?')


class FilesToParsers:

    def __init__(self, file_list):
        self.file_list = [] 
        self.skip_files = []
        self.parsers = []
        for filepath in file_list:
            self.file_list.append(Path(filepath).resolve())

    def do_file_includes(self, content_lines, path):
        include_paths = []
        bad_include_paths = []
        skip_counter = 0
        new_lines = []
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
                first_line = None
                tmp = rline.strip().split()
                check_path = tmp[0]
                if len(tmp) > 1:
                    first_line = ' '.join(tmp[1:])
                check_paths.append(dict(fpath=check_path, first_line=first_line))
                rpos += 1
                if rpos == len(rest):
                    raise Exception(f'End of file reached before include file section in {path} terminated')
                rline = rest[rpos]
                skip_counter += 1
            skip_counter += 1
            for check_spec in check_paths:
                check_path = check_spec['fpath']
                if check_path == "":
                    continue
                if check_path.startswith('/'):
                    check_path = Path(check_path)
                else:
                    # assume it is realtive to including path
                    dirname = path.parent
                    check_path = Path(dirname, check_path)
                if not check_path.exists():
                    bad_include_paths.append(check_path)
                    continue
                include_paths.append(check_path)
                self.skip_files.append(check_path)
                logger.warn("including %s", str(check_path))
                level = None
                if check_spec['first_line']:
                    new_lines.append(check_spec['first_line'])
                    res = heading_pattern.match(check_spec['first_line'])
                    if res:
                        level = len(res.groupdict()['stars'])
                with open(check_path, "r", encoding="utf-8") as f:
                    include_contents = f.read()
                if level:
                    extra = "*" * level
                    for line in include_contents.split('\n'):
                        if line.startswith('*'):
                            new_lines.append(f'{extra}{line}')
                        else:
                            new_lines.append(line)
                else:
                    # Without a level spec on the include, the doc properties
                    # will get ignored. With the level spec the property
                    # drawer looks like it belongs to the heading.
                    new_lines.extend(include_contents.split('\n'))
            contents = '\n'.join(new_lines)
        count = len(include_paths)
        if count:
            # do it again
            new_lines, sub_files,sub_bads = self.do_file_includes(new_lines, path)
            if sub_files:
                include_paths.extend(sub_files)
            if sub_bads:
                bad_include_paths.extend(sub_bads)
            return new_lines, include_paths, bad_include_paths
        else:
            return content_lines, None, None
        
    def run_parsers(self):
        root_parser = None
        parsers = []
        contents_by_path = {}
        includes_by_path = {}
        bad_paths_by_path = {}
        for path in self.file_list:
            if path in self.skip_files:
                continue
            with open(path, "r", encoding="utf-8") as f:
                contents = f.read()
            with_includes,included,bad_paths = self.do_file_includes(contents.split('\n'), path)
            contents_by_path[path] = '\n'.join(with_includes)
            includes_by_path[path] = included
            if bad_paths:
                bad_paths_by_path[path] = bad_includes
        for path in self.file_list:
            if path not in self.skip_files:
                contents = contents_by_path[path]
                if root_parser is None:
                    root_parser = parser = DocParser(contents, str(path.parts[-1]), included_files=includes_by_path[path])
                else:
                    parser = DocParser(contents, str(path.parts[-1]), root=root_parser.root,
                                       included_files=includes_by_path[path])
                parsers.append(parser)
                parser.parse()
        if len(bad_paths_by_path) > 0:
            with open('bad_includes.list', 'w') as f:
                for path,bads in bad_paths_by_path.items():
                    f.write(f"included_from {path}\n")
                    for bad in bads:
                        f.write(f"{bad}\n")
                    f.write(f"\n")
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
            
    
