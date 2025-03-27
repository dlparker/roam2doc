import sys
import logging
import json
from pathlib import Path
from pprint import pprint, pformat
from bs4 import BeautifulSoup
import pytest
from roam2doc.parse import (DocParser, MatchHeading, MatchDoubleBlank, MatchTable, MatchList,
                            MatchSrc, MatchQuote, MatchCenter, MatchExample, MatchGreaterEnd,
                            ParagraphParse, MatcherType, ToolBox, SectionParse)
from roam2doc.tree import (OrderedList, OrderedListItem, BlankLine)
from setup_logging import setup_logging

setup_logging(default_level="warning")

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

def test_parser_stack():
    start_file = "file_start_with_props_and_title.org"
    start_contents = get_frag_file_contents(start_file)
    para1 = get_frag_file_contents("no_object_paragraph.org")
    contents = start_contents + para1
    doc_parser =  DocParser(contents, "combined1")

    section_p = None

    def parse_start(parser):
        nonlocal section_p
        print(f"parsing starting by {parser}")
        assert doc_parser.current_parser() == parser
        if isinstance(parser, SectionParse):
            assert doc_parser.get_parser_parent(parser) is None
            section_p = parser
            assert parser.get_section_parser() == section_p
        else:
            p1 = doc_parser.get_parser_parent(parser) 
            assert p1 is not None
            p2 = parser.get_parent_parser()
            assert p1 == p2
            assert parser.get_section_parser() == section_p
            
    def parse_end(parser):
        print(f"parsing finished by {parser}")

    doc_parser.set_parse_callbacks(parse_start, parse_end)

    # do some manual manipulation before running for real
    sp = SectionParse(doc_parser, 0, 3)
    assert len(doc_parser.parser_stack) == 0
    assert doc_parser.current_parser() is None
    doc_parser.push_parser(sp)
    assert len(doc_parser.parser_stack) == 1
    assert sp.start_callback is not None
    doc_parser.pop_parser(sp)
    assert len(doc_parser.parser_stack) == 0
    with pytest.raises(ValueError) as execinfo:
        # can't pop it twice
        print(execinfo)
        doc_parser.pop_parser(sp)
                
    res = doc_parser.parse()
    assert len(doc_parser.parse_problems) == 0

def test_flat_ordered_list():
    flat_list_inner()

def test_flat_ordered_list_with_objects():
    flat_list_inner()
    
def test_flat_ordered_list_with_objects():
    flat_list_inner(use_objects=True)
    
def test_flat_ordered_list_append_para():
    flat_list_inner(append_para=True)

def test_flat_ordered_list_append_table():
    flat_list_inner(append_table=True)

def test_flat_unordered_list():
    flat_list_inner(list_type="ordered")

def test_flat_unordered_list_with_objects():
    flat_list_inner(list_type="ordered")
    
def test_flat_unordered_list_with_objects():
    flat_list_inner(list_type="ordered", use_objects=True)
    
def test_flat_unordered_list_append_para():
    flat_list_inner(list_type="ordered", append_para=True)

def test_flat_unordered_list_append_table():
    flat_list_inner(list_type="ordered", append_table=True)

def flat_list_inner(list_type="ordered", use_objects=False, append_para=False, append_table=False):
    file_start =  "file_start_with_props_and_title.org"
    start = get_frag_file_contents(file_start)
    section_kid_count = 1
    if use_objects:
        if list_type == "ordered":
            list_part = get_frag_file_contents("ordered_flat_list_with_objects.org")
        elif list_type == "unordered":
            list_part = get_frag_file_contents("unordered_flat_list_with_objects.org")
    else:
        if list_type == "ordered":
            list_part = get_frag_file_contents("ordered_flat_list.org")
        elif list_type == "unordered":
            list_part = get_frag_file_contents("unordered_flat_list.org")
    if append_table:
        append_part = get_frag_file_contents("three_row_table.org")
    elif append_para:
        append_part = get_frag_file_contents("para_with_objects.org")
    else:
        append_part = None
    contents = start + list_part
    if append_part:
        contents += append_part
    parser =  DocParser(contents, "")
    res = parser.parse()
    section_parse_0 = parser.sections[0]
    section_0 = section_parse_0.tree_node
    assert section_0 in parser.branch.children
    # should have one ordered list and one blank line
    assert len(section_0.children) == section_kid_count
    ol = section_0.children[0]
    assert len(ol.children) == 3
    assert isinstance(ol, OrderedList)
    assert isinstance(ol.children[0], OrderedListItem)
    assert isinstance(ol.children[1], OrderedListItem)
    assert isinstance(ol.children[2], OrderedListItem)
    html_lines = ol.to_html(indent_level=1)
    pre = "<body>"
    post = "</body>"
    new_list = []
    new_list.append(pre)
    new_list.extend(html_lines)
    new_list.append(post)
    html = '\n'.join(new_list)
    print(html)
    soup = BeautifulSoup(html, 'html.parser')
    elements = soup.find_all('li', class_="org-auto-OrderedListItem")
    for elm in elements:
        for kid in elm.descendants:
            if kid.string == "\n":
                continue
            if kid.string is None:
                # if something is appended, it will be here
                break
            assert "(flat)" in kid.string

    
def test_bad_file_properties():
    frag_file =  "file_start_with_bad_props.org"
    contents = get_frag_file_contents(frag_file)
    parser =  DocParser(contents, frag_file)
    res = parser.parse()
    assert len(parser.parse_problems) > 0
    
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
        para1 = get_frag_file_contents("no_object_paragraph.org")
        more = contents + para1
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
        para1 = get_frag_file_contents("no_object_paragraph.org")
        f_section_start_with_drawer = get_frag_file_contents("f_section_start_with_drawer.org")
        # Need to handle carefully as some emacs files have \n\n ending can
        # get lost when combining file content strings and then splitting,
        # so split first and combine that way.
        s1_lines = contents.split('\n') + para1.split('\n')
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

        
def atest_file_all_nodes():
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


def gen_top_lists():
    lines = []
    lines.append('* Section 1 heading')
    lines.append('1. List 1')
    lines.append('    2. List 1 sub 1')

    buff = '\n'.join(lines)
    return buff

def gen_mixed_elems():
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
    return buff
    
    
def gen_no_elems():
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
    return buff
    

def gen_objects():

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
    return buff

    
    
def gen_def_list():
    lines = []
    lines.append('* a section')
    lines.append('+ foo :: a word ofen used by programmers')
    lines.append('+ bar :: another word ofen used by programmers')
    lines.append('   + foobar :: see a pattern?')
    lines.append('')
    lines.append('')
    buff = '\n'.join(lines)
    return buff


def gen_def_list_2():
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
    return buff

    
def gen_big_mix():
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
    return buff
    
