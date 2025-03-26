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
        res = parser.find_first_section()
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
        res = parser.find_first_section()
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

    lines.append('+ foo :: a word ofen used by programmers')
    lines.append('+ bar :: another word ofen used by programmers')
    lines.append('   + foobar :: see a pattern?')
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
    lines.append("*bold_text* *more_bold_text* *even more but with spaces*")
    lines.append("/italic_text/ /more_italic_text/ /spaced italic text/")
    lines.append("_underlined_text_ _more_underlined_text_ _underlined and spaces_")
    lines.append("+linethrough_text+ +more_linethrough_text+ +spaces in line through+")
    lines.append("=verbatim_text= =more verbatim text=")
    lines.append("~code_text~ ~more code text~ ~code containing = sign ~")
    lines.append('')
    buff = '\n'.join(lines)
    
    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())
    
    
def test_def_list():
    lines = []
    lines.append('* a section')
    lines.append('+ foo :: a word ofen used by programmers')
    lines.append('+ bar :: another word ofen used by programmers')
    lines.append('   + foobar :: see a pattern?')
    lines.append('')
    lines.append('')
    buff = '\n'.join(lines)
    
    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())


def test_def_list_2():
    lines = []
    lines.append('* a section')
    lines.append('- unordered list starts')
    lines.append('  - unordered sub 1')
    lines.append('    - unordered sub 1 subsub 1')
    lines.append('  - unordered sub 2')
    lines.append('- unordered second ')
    lines.append('  + foo :: a word ofen used by programmers')
    lines.append('  + bar :: another word ofen used by programmers')
    lines.append('    + foobar :: see a pattern?')
    lines.append('    + beebop :: arubop')
    lines.append('')
    lines.append('')
    buff = '\n'.join(lines)
    
    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())
    
def test_nest_list():
    lines = []
    lines.append('+ level 1 item 1')
    lines.append('+ level 1 item 2')
    lines.append('  + level 2 item 1')
    lines.append('    + level 3 item 1')
    lines.append('      + level 4 item 1')
    lines.append('    + level 3 item 2')
    lines.append('  + level 2 item 2')
    lines.append('+ level 1 item 3')
    lines.append('')
    lines.append('')
    lines.append('+ second list level 1 item 1')
    lines.append('    + level 2 item 1')
    lines.append('        1. switched to ordered')
    lines.append('            + def1 :: a thing')
    lines.append('            + def2 :: other thing')
    lines.append('')
    lines.append('')
    lines = []
    lines.append('* a section 2')
    lines.append('- unordered list starts')
    lines.append('  - unordered sub 1')
    lines.append('    - unordered sub 1 subsub 1')
    lines.append('  - unordered sub 2 *bold text*')
    lines.append('- unordered second ')
    lines.append('  + foo :: a word ofen used by programmers')
    lines.append('  + bar :: another word ofen used by programmers')
    lines.append('    + foobar :: see a pattern?')
    lines.append('    + beebop :: <<arubop>>')
    lines.append('')
    lines = []
    lines.append('* a section 3')
    lines.append(':PROPERTIES:')
    lines.append(':ID: foo_bar_section')
    lines.append(':END:')
    lines.append('- unordered list starts')
    lines.append('  - unordered sub 1')
    lines.append('    - unordered sub 1 subsub 1')
    lines.append('  - unordered sub 2 *bold text*')
    lines.append('- unordered second ')
    lines.append('    + foobar :: see a pattern?')
    lines.append('    + beebop :: <<arubop>>')
    lines.append('  Some text as a paragraph in an item!!!')
    lines.append('  and a link [[Section 1 heading][*/back to the top!/*]]')
    lines.append('  and an embedded table!!')
    lines.append('    | xx | *this item is bold* |')
    lines.append('    | yy | /this item is italian/ |')
    lines.append('')
    lines.append('')
    lines.append('paragraph after table')
    lines.append('#+BEGIN_CENTER center1')
    lines.append('A center block')
    lines.append('    | ww | Checking inside center block *this item is bold* |')
    lines.append('    | zz | /this item is italian/ |')
    lines.append('#+END_CENTER')
    lines.append('#+BEGIN_EXAMPLE python')
    lines.append(' This is an example')
    lines.append(" of what don't know")
    lines.append('#+END_EXAMPLE')
    lines.append('#+BEGIN_SRC python')
    lines.append('def foo():')
    lines.append('    return goodness')
    lines.append('#+END_SRC')
    lines.append('#+BEGIN_COMMENT ')
    lines.append(' I have things to say')
    lines.append(' and they should be heard!')
    lines.append('#+END_COMMENT')
    lines.append('#+BEGIN_EXPORT ')
    lines.append(' export blocks make little sense after conversion ')
    lines.append('#+END_EXPORT')
    lines.append('#+BEGIN_QUOTE quote1')
    lines.append('A quote block')
    lines.append('#+NAME: table_1')
    lines.append('    | ww | Checking inside quote *this item is bold* |')
    lines.append('    | zz | /this item is italian/ |')
    lines.append('#+END_QUOTE')
    lines.append('')
    lines.append('[[table_1][Link to table 1]]')
    lines.append('[[foo_bar_section][Link to section via id property]]')
    lines.append('')
    
    buff = '\n'.join(lines)
    
    logger = logging.getLogger("test_code")
    logger.info("starting test_no_elems")
    doc_parser = DocParserWrap(buff, "inline")
    doc_parser.parse()
    #print(json.dumps(doc_parser.root.to_json_dict(), indent=2))
    print(doc_parser.root.to_html())
    
