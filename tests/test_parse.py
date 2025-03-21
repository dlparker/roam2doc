import sys
print(sys.path)
import logging
import json
from logging.config import dictConfig
from pathlib import Path
from pprint import pprint, pformat
import pytest
from roam2doc.parse import DocParser

def setup_logging(default_level="error"):
    lfstring = '[%(levelname)s] %(name)s: %(message)s'
    log_formaters = dict(standard=dict(format=lfstring))
    logfile_path = Path('.', "test.log")
    if False:
        file_handler = dict(level="DEBUG",
                            formatter="standard",
                            encoding='utf-8',
                            mode='w',
                            filename=str(logfile_path))
        file_handler['class'] = "logging.FileHandler"
    stdout_handler =  dict(level="DEBUG",
                           formatter="standard",
                           stream="ext://sys.stdout")
    # can't us "class" in above form
    stdout_handler['class'] = "logging.StreamHandler"
    log_handlers = dict(stdout=stdout_handler)
    handler_names = ['stdout']
    if False:
        log_handlers = dict(file=file_handler, stdout=stdout_handler)
        handler_names = ['file', 'stdout']
    log_loggers = set_levels(handler_names, default_level=default_level)
    log_config = dict(version=1, disable_existing_loggers=False,
                      formatters=log_formaters,
                      handlers=log_handlers,
                      loggers=log_loggers)
        # apply the caller's modifications to the level specs
    try:
        dictConfig(log_config)
    except:
        from pprint import pprint
        pprint(log_config)
        raise
    return log_config

def set_levels(handler_names, default_level='error'):
    log_loggers = dict()
    err_log = dict(handlers=handler_names, level="ERROR", propagate=False)
    warn_log = dict(handlers=handler_names, level="WARNING", propagate=False)
    root_log = dict(handlers=handler_names, level="ERROR", propagate=False)
    info_log = dict(handlers=handler_names, level="INFO", propagate=False)
    debug_log = dict(handlers=handler_names, level="DEBUG", propagate=False)
    log_loggers[''] = root_log
    default_log = err_log
    if default_level == "warn":
        default_log =  warn_log
    elif default_level == "info":
        default_log =  info_log
    elif default_level == "debug":
        default_log =  debug_log
    log_loggers['pyorg2-parser'] = default_log
    log_loggers['test_code'] = default_log
    return log_loggers

setup_logging(default_level="debug")

start_frag_files = ["file_start_with_heading.org",
                    "file_start_with_no_heading.org",
                    "file_start_with_props.org",
                    "file_start_with_only_title.org",
                    "file_start_with_props_and_title.org",]

def get_example_file_contents(name):
    this_dir = Path(__file__).resolve().parent
    fdir = Path(this_dir, "org_files", "examples")
    target = Path(fdir, name)
    with open(target) as f:
        buffer = f.read()
    return buffer
    
def get_frag_file_contents(name):
    this_dir = Path(__file__).resolve().parent
    fdir = Path(this_dir, "org_files", "fragments")
    target = Path(fdir, name)
    with open(target) as f:
        buffer = f.read()
    return buffer

def test_file_starts_no_content():
    logger = logging.getLogger('test_code')

    for name in start_frag_files:
        logger.debug('doing find section with file %s', name)
        contents = get_frag_file_contents(name)
        # All these have a non-empty first line, so the
        # should start on line index 0. They also
        # have exactly empty line at the end, so
        # the end index should, well, you do the math.
        parser = DocParser(contents, name)
        res = parser.find_section()
        assert res.start == 0, f"{name} should start section at 0"
        lines = contents.split('\n')
        x = len(lines) - 1
        assert res.end == x, f"{name} should end section at {x}"

def test_file_starts_with_content():
    logger = logging.getLogger('test_code')
    
    for name in start_frag_files:
        logger.debug('doing find section with content append on file %s', name)
        contents = get_frag_file_contents(name)
        section_contents_1 = get_frag_file_contents("section_contents_1.org")
        more = contents + section_contents_1
        parser =  DocParser(more, name)
        res = parser.find_section()
        assert res.start == 0, f"{name} should start section at 0"
        lines = more.split('\n')
        x = len(lines) - 1
        assert res.end == x, f"{name} should end section at {x}"

def test_file_starts_with_second_section():
    logger = logging.getLogger('test_code')

    for name in start_frag_files:
        logger.debug('doing parse on second section append with file %s', name)
        contents = get_frag_file_contents(name)
        section_contents_1 = get_frag_file_contents("section_contents_1.org")
        f_section_start_with_drawer = get_frag_file_contents("f_section_start_with_drawer.org")
        # Need to handle carefully as some emacs files have \n\n ending can
        # get lost when combining file content strings and then splitting,
        # so split first and combine that way.
        s1_lines = contents.split('\n') + section_contents_1.split('\n')
        s2_lines = f_section_start_with_drawer.format(section_number=2).split('\n')
        all_lines = s1_lines + s2_lines
        text = '\n'.join(all_lines)
        parser =  DocParser(text, name)
        res = parser.parse()
        assert len(res['sections']) == 2, f"{name} section 1 should have two sections"
        section_1 = res['sections'][0]
        section_2 = res['sections'][1]
        target = 0
        if name == "file_start_with_props.org":
            target = 3
        elif name == "file_start_with_props_and_title.org":
            target = 4
        elif name == "file_start_with_only_title.org":
            target = 1
        assert section_1.start == target, f"{name} section 1 should start section at {target}"
        s1_end = len(s1_lines) - 1
        assert section_1.end == s1_end, f"{name} section 1 should end section at {s1_end}"
        s2_start = s1_end + 1
        s2_end = s2_start + len(s2_lines)  - 1
        assert section_2.start == s2_start, f"{name} section 2 should start section at {s2_start}"
        assert section_2.end == s2_end, f"{name} section 2 should end section at {s2_end}"

        
def test_file_all_nodes():
    name = "all_nodes.org"
    name = "only_title_and_list.org"
    name = "only_props_and_list.org"
    name = "props_title_and_list.org"
    contents = get_example_file_contents(name)
    parser =  DocParser(contents, name)
    res = parser.parse()
    #obj_tree = json.dumps(parser.root, default=lambda o:o.to_json_dict(), indent=4)
    #print(obj_tree)
    print(parser.root.to_html())


def test_foo():
    from roam2doc.parse import DocParser, SectionParse, Detector
    lines = []
    lines.append('* Foo')
    lines.append('#+BEGIN_CENTER')
    lines.append('Stuff in the middle')
    lines.append('More Stuff in the middle')
    lines.append('#+END_CenTer')
    buff = '\n'.join(lines)
    doc_parser = DocParser(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())
    
    
    
