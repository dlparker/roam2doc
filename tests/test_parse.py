import sys
import logging
import json
from pathlib import Path
from pprint import pprint, pformat
import pytest
from roam2doc.parse import (DocParser, MatchHeading, MatchDoubleBlank, MatchTable, MatchList,
                            MatchSrc, MatchQuote, MatchCenter, MatchExample, MatchGreaterEnd,
                            ParagraphParse, MatcherType, ToolBox)
from setup_logging import setup_logging

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

class DocParserWrap(DocParser):

    pass

def do_list_matcher_test():
    """ Ensure that the matchers for the start and end of a list work"""
    lines = []
    lines.append('* Foo')
    lines.append('+ l1')
    # terminate the list with double blank line
    lines.append('')
    lines.append('')
    doc_parser, section_p = matcher_test_setup(lines)
    list_matcher = MatchList()
    double_matcher = MatchDoubleBlank()
    m1 = list_matcher.match_line(lines[section_p.cursor])
    assert m1 is not None
    m2 = double_matcher.match_line(lines[section_p.cursor + 1])
    assert m2 is not None
    end_matcher = MatchDoubleBlank()
    end  = end_matcher.match_line_range(lines, section_p.cursor + 2, len(lines))
    assert end is not None

    lines = []
    lines.append('* Foo')
    lines.append('+ l1')
    # terminate the list with a new section
    lines.append('* bar')
    doc_parser, section_p = matcher_test_setup(lines)
    end_matcher = MatchGreaterEnd()
    end  = end_matcher.match_line_range(doc_parser, lines, section_p.cursor + 2, len(lines))
    assert end is not None
    assert ToolBox.get_matcher(MatcherType.alist) is not None
    
def matcher_test_setup(lines):
    buff = '\n'.join(lines)
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.find_sections()
    assert len(doc_parser.sections) == 1
    section_p = doc_parser.sections[0]
    pos = 0

    heading_matcher = MatchHeading()
    hmatch = heading_matcher.match_line(lines[pos])
    assert hmatch is not None, "Heading matcher failed, direct position"
    hmatch = heading_matcher.match_line(lines[section_p.cursor])
    assert hmatch is not None, "Heading matcher failed, position from section cursor"
    with pytest.raises(Exception):
        section_parse_tool = heading_matcher.get_parse_tool(doc_parser)
    # pretend to start the section parser, but don't do it
    doc_parser.current_section = section_p
    doc_parser.push_parser(section_p)
    return doc_parser, section_p
    
def test_matchers():
    do_list_matcher_test()


def find_para_blocks(lines, start, end):
    # caller has stripped the data down to text that does not trigger any element matches.
    # also guarantees that the first line is not blank
    pos = start
    paras = []
    cur_para = dict(start=pos, end=-1, first_blank=-1, last_blank=-1)
    paras.append(cur_para)
    while pos < end:
        if lines[pos].strip() == '':
            if cur_para['first_blank'] == -1:
                cur_para['first_blank'] = pos
            cur_para['last_blank'] = pos
        else:
            if cur_para['first_blank'] != -1:
                cur_para['end'] = pos - 1
                cur_para = dict(start=pos, end=-1, first_blank=-1, last_blank=-1)
                paras.append(cur_para)
        pos += 1
    cur_para['end'] = pos - 1
    return paras

def test_top_lists():
    lines = []
    lines.append('* Section 1 heading')
    lines.append('1. List 1')
    lines.append('    2. List 1 sub 1')

    buff = '\n'.join(lines)

    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())
    
def test_mixed_elems():
    lines = []
    lines.append('* Section 1 heading')
    lines.append('')
    lines.append('')
    lines.append('This will be a paragraph.')
    lines.append('This continues the paragraph.')
    lines.append('The next line (blank) will end the paragraph.')
    lines.append('')
    lines.append('This will be a second paragraph. ')
    lines.append('The following blank lines will end it.')
    lines.append('The following next two blank will also be part of the paragraph.')
    lines.append('They should be part of the section directly')
    lines.append('')
    lines.append('')
    lines.append('')
    lines.append('This will be a second paragraph. ')
    lines.append('* Section 2 heading')
    lines.append('** Section 2-1 heading')
    lines.append('1. List 1')
    lines.append('    2. List 1 sub 1')
    lines.append('** Section 2-2 heading')
    lines.append('this first text should be in Section 2-2 before list' )
    lines.append('+ List 2')
    lines.append('    + List 2 sub 1')
    lines.append('        1. List 2 sub 1 sub list change type')
    lines.append('          this should be para 1 line 1 inside List 2 sub 1 sub 1')
    lines.append('          this should be para 1 line 2 inside List 2 sub 1 sub 1')
    lines.append('          this should be para 1 line 3 inside List 2 sub 1 sub 1')
    lines.append('')
    lines.append('          this should be para 2 line 1 inside List 2 sub 1 sub 1')
    lines.append('          this should be para 2 line 2 inside List 2 sub 1 sub 1')
    lines.append('          this should be para 2 line 3 inside List 2 sub 1 sub 1')
    lines.append('')
    lines.append('')
    lines.append('this other text should be in Section 2-2 after list')
    lines.append('* Section 3')
    lines.append('| a | 1 |')
    lines.append('| b | 2 |')
    
    buff = '\n'.join(lines)

    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())
    
    
    
def test_no_elems():
    lines = []
    lines.append('* Section 1 heading')
    lines.append('')
    lines.append('')

    lines.append('This will be a paragraph.')
    lines.append('This continues the paragraph.')
    lines.append('The next line (blank) will end the paragraph.')
    lines.append('')
    lines.append('This will be a second paragraph. ')
    lines.append('The following blank lines will end it.')
    lines.append('The following next two blank will also be part of the paragraph.')
    lines.append('They should be part of the section directly')
    lines.append('')
    lines.append('')
    lines.append('')
    lines.append('This will be a second paragraph. ')
    lines.append('* Section 2 heading')
    lines.append('** Section 3 heading')
    lines.append('* Section 4 heading')

    buff = '\n'.join(lines)

    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())
    

def test_objects():

    lines = []
    lines.append('* Section 1 heading')
    lines.append('')
    lines.append('Paragraph starts')
    lines.append("*bold_text* *more_bold_text* *even_more*")
    lines.append("/italic_text/ /more_italic_text/")
    lines.append("_underlined_text_ _more_underlined_text_")
    lines.append('')
    buff = '\n'.join(lines)
    
    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())
    
    
