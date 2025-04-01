import sys
import logging
import json
from io import StringIO
from pathlib import Path
from pprint import pprint, pformat
import pytest
from unittest.mock import patch
from roam2doc.parse import (DocParser, MatchHeading, MatchTable, MatchList,
                            MatchQuote, MatchCenter, MatchExample,
                            ParagraphParse, MatcherType, ToolBox, SectionParse)
from roam2doc.tree import (OrderedList, OrderedListItem, BlankLine, Section)
from roam2doc.setup_logging import setup_logging
from roam2doc.cli import main

setup_logging(default_level="debug")

start_frag_files = ["file_start_with_heading.org",
                    "file_start_with_no_heading.org",
                    "file_start_with_props.org",
                    "file_start_with_only_title.org",
                    "file_start_with_props_and_title.org",]

def get_example_file_path_and_contents(name):
    this_dir = Path(__file__).resolve().parent
    fdir = Path(this_dir, "org_files", "examples")
    target = Path(fdir, name)
    with open(target) as f:
        buffer = f.read()
    return target, buffer
    
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
    doc_parser =  DocParser(contents, start_file)

    section_p = None

    def parse_start(parser):
        nonlocal section_p
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
        pass


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
        doc_parser.pop_parser(sp)
                
    res = doc_parser.parse()
    assert len(doc_parser.parse_problems) == 0


def test_latex_1():
    #path, contents =get_example_file_path_and_contents("min.org")
    path, contents =get_example_file_path_and_contents("all_nodes.org")
    doc_parser =  DocParser(contents, "")
    branch = doc_parser.parse()
    root = branch.root
    res = root.to_latex(title="Parse of all nodes")
    trunk = root.trunk
    # there is zeroth section in this file
    section3 = trunk.children[3]
    section2 = trunk.get_parent_section(section3)
    assert section2 == trunk.children[2]
    section1 = trunk.get_parent_section(section2)
    assert section1 == trunk.children[1]
    #print(res)
    
def test_latex_labels():
    lines = []
    lines.append('* Section 1 heading')
    lines.append('1. List 1')
    lines.append('    2. List 1 sub 1 <<target>>')
    lines.append('       + List 1 sub 1 sub list item 1')
    lines.append('       + List 1 sub 1 sub list item 2 [[target][link to target]]')
    lines.append('       + List 1 sub 1 sub list item 3 [[target][link to target]]')
    contents = "\n".join(lines)
    doc_parser =  DocParser(contents, "")
    branch = doc_parser.parse()
    root = branch.root
    res = root.to_latex(title="Parse of all nodes")
    trunk = root.trunk
    section_1 = trunk.children[0]
    list_1 = section_1.children[0]
    label = list_1.get_latex_label_text()
    print(label)

    
    list_item_1 = list_1.children[0]
    first_inner_list = list_item_1.children[1]
    inner_list_item_1 = first_inner_list.children[0]
    # first ones are text items
    unordered_list = inner_list_item_1.children[-1]
    unordered_list_item_1 = unordered_list.children[0]
    section_check = trunk.get_parent_section(unordered_list_item_1)
    assert section_check == section_1
    pprint(unordered_list.get_list_stack())
    label = unordered_list_item_1.get_latex_label_text()
    

    pprint(root.to_latex(grokify=True))
    
def test_latex_depth():
    lines = []
    lines.append('* H1')
    lines.append('  This document is created to improve my ability to get help from')
    lines.append('  Grok on developing the ideas in this project. It can perform')
    lines.append('  research for me in the way that only modern LLMs can, drastically')
    lines.append('  the difficulty of playing "what if".')
    lines.append('** H2')
    lines.append('  This document is created to improve my ability to get help from')
    lines.append('  Grok on developing the ideas in this project. It can perform')
    lines.append('  research for me in the way that only modern LLMs can, drastically')
    lines.append('  the difficulty of playing "what if".')
    lines.append('*** H3')
    lines.append('  This document is created to improve my ability to get help from')
    lines.append('  Grok on developing the ideas in this project. It can perform')
    lines.append('  research for me in the way that only modern LLMs can, drastically')
    lines.append('  the difficulty of playing "what if".')
    lines.append('**** H4')
    lines.append('  This document is created to improve my ability to get help from')
    lines.append('  Grok on developing the ideas in this project. It can perform')
    lines.append('  research for me in the way that only modern LLMs can, drastically')
    lines.append('  the difficulty of playing "what if".')
    lines.append('***** H5')
    lines.append('  This document is created to improve my ability to get help from')
    lines.append('  Grok on developing the ideas in this project. It can perform')
    lines.append('  research for me in the way that only modern LLMs can, drastically')
    lines.append('  the difficulty of playing "what if".')
    lines.append('****** H6')
    lines.append('  This document is created to improve my ability to get help from')
    lines.append('  Grok on developing the ideas in this project. It can perform')
    lines.append('  research for me in the way that only modern LLMs can, drastically')
    lines.append('  the difficulty of playing "what if".')
    lines.append('******* H7')
    contents = "\n".join(lines)
    doc_parser =  DocParser(contents, "")
    branch = doc_parser.parse()
    root = branch.root
    

    pprint(root.to_latex(grokify=True))
    

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
    doc_parser =  DocParser(contents, "")
    res = doc_parser.parse()
    section_parse_0 = doc_parser.sections[0]
    section_0 = section_parse_0.tree_node
    assert section_0 in doc_parser.branch.children
    # should have one ordered list and one blank line
    assert len(section_0.children) == section_kid_count
    the_l = section_0.children[0]
    assert len(the_l.children) == 3
    if list_type == "ordered":
        assert isinstance(the_l, OrderedList)
        assert isinstance(the_l.children[0], OrderedListItem)
        assert isinstance(the_l.children[1], OrderedListItem)
        assert isinstance(the_l.children[2], OrderedListItem)
    elif list_type == "unordered":
        assert isinstance(the_l, UnorderedList)
        assert isinstance(the_l.children[0], UnorderedListItem)
        assert isinstance(the_l.children[1], UnorderedListItem)
        assert isinstance(the_l.children[2], UnorderedListItem)
    # make sure output is produced without blowing up
    doc_parser.root.to_html()

def test_bad_file_properties():
    frag_file =  "file_start_with_bad_props.org"
    contents = get_frag_file_contents(frag_file)
    doc_parser =  DocParser(contents, frag_file)
    res = doc_parser.parse()
    assert len(doc_parser.parse_problems) > 0
    
def test_file_starts_no_content():
    logger = logging.getLogger('test_code')

    for name in start_frag_files:
        logger.debug('doing find section with file %s', name)
        contents = get_frag_file_contents(name)
        # All these have a non-empty first line, so the
        # should start on line index 0. They also
        # have exactly empty line at the end, so
        # the end index should, well, you do the math.
        doc_parser = DocParser(contents, name)
        res = doc_parser.find_first_section()
        assert res.start == 0, f"{name} should start section at 0"
        lines = contents.split('\n')
        x = len(lines) - 1
        assert res.end == x, f"{name} should end section at {x}"

        # make sure output is produced without blowing up
        doc_parser.root.to_html()
    
def test_file_starts_with_content():
    logger = logging.getLogger('test_code')
    
    for name in start_frag_files:
        logger.debug('doing find section with content append on file %s', name)
        contents = get_frag_file_contents(name)
        para1 = get_frag_file_contents("no_object_paragraph.org")
        more = contents + para1
        doc_parser =  DocParser(more, name)
        res = doc_parser.find_first_section()
        assert res.start == 0, f"{name} should start section at 0"
        lines = more.split('\n')
        x = len(lines) - 1
        assert res.end == x, f"{name} should end section at {x}"
        # make sure output is produced without blowing up
        doc_parser.root.to_html()

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
        doc_parser =  DocParser(text, name)
        branch = doc_parser.parse()
        root = branch.root
        sections = []
        for child in branch.children:
            assert isinstance(child, Section)
            sections.append(child)
            
        assert len(sections) == 2, f"{name} section 1 should have two sections"
        section_1 = sections[0]
        section_2 = sections[1]
        target = 0
        if name == "file_start_with_props.org":
            target = 3
        elif name == "file_start_with_props_and_title.org":
            target = 4
        elif name == "file_start_with_only_title.org":
            target = 1
        assert section_1.start_line == target, f"{name} section 1 should start section at {target}"
        s1_end = len(s1_lines) - 1
        assert section_1.end_line == s1_end, f"{name} section 1 should end section at {s1_end}"
        s2_start = s1_end + 1
        s2_end = s2_start + len(s2_lines)  - 1
        assert section_2.start_line == s2_start, f"{name} section 2 should start section at {s2_start}"
        assert section_2.end_line == s2_end, f"{name} section 2 should end section at {s2_end}"
        # make sure output is produced without blowing up
        doc_parser.root.to_html()

        
def test_file_all_nodes():
    name = "all_nodes.org"
    path, contents = get_example_file_path_and_contents(name)
    # need the path to make image tag work
    doc_parser =  DocParser(contents, path)
    section_p = None
    def parse_start(parser):
        nonlocal section_p
        assert doc_parser.current_parser() == parser
        if isinstance(parser, SectionParse):
            section_p = parser
            
    def parse_end(parser):
        pass

    doc_parser.set_parse_callbacks(parse_start, parse_end)
    res = doc_parser.parse()
    # make sure output is produced without blowing up
    doc_parser.root.to_html()
    doc_parser.root.to_html(make_pretty=False, include_json=True)

def test_file_all_nodes_cli():
    this_dir = Path(__file__).resolve().parent
    org_file = Path(this_dir, 'org_files', 'examples', 'all_nodes.org')
    with patch('sys.argv', ['tester', str(org_file), '--output', '/tmp/foo.pdf', '--doc_type', 'latex', '--grokify', '--overwrite']):
        parsers = main()
    
def test_cli():
    this_dir = Path(__file__).resolve().parent
    org_file = Path(this_dir, 'org_files', 'examples', 'objects.org')

    with patch('sys.stdout', new=StringIO()) as fake_out:
        with patch('sys.argv', ['tester', "--doc_type", "json", str(org_file)]):
            parsers = main()
            outvalue = fake_out.getvalue()
    reload_data = json.loads(outvalue)
    jdata = parsers[0].root.to_json_dict()

    # just check some of the structure to do a sanity check on reloading from file
    assert jdata['cls'] == reload_data['cls']
    o_sec_1 = jdata['props']['trunk']['props']['nodes'][0]
    r_sec_1 = jdata['props']['trunk']['props']['nodes'][0]
    assert o_sec_1['cls'] == "<class 'roam2doc.tree.Section'>"
    assert r_sec_1['cls'] == "<class 'roam2doc.tree.Section'>"

    # blank line, should be literally the same
    assert o_sec_1['props']['children'][0] == r_sec_1['props']['children'][0]
    o_head_1 = o_sec_1['props']['heading']
    r_head_1 = r_sec_1['props']['heading']
    assert o_head_1['cls'] == "<class 'roam2doc.tree.Heading'>"
    assert r_head_1['cls'] == "<class 'roam2doc.tree.Heading'>"
    assert o_head_1['props']['node_id'] == r_head_1['props']['node_id']
            
    with patch('sys.stdout', new=StringIO()) as fake_out:
        with patch('sys.argv', ['tester', str(org_file)]):
            parsers = main()
            assert "bold_text</b>" in fake_out.getvalue()
        b1 = parsers[0].branch
        sec = b1.children[0]
        blank = sec.children[0]
        para = sec.children[1]
        first_bold = para.children[1]
        assert first_bold.simple_text == "bold_text"
        assert(first_bold.get_source_data()['source']) == "*bold_text*"
        
    with patch('sys.argv', ['tester', str(org_file), '--output', '/tmp/foo', '--overwrite']):
        parsers = main()
        b1 = parsers[0].branch
        sec = b1.children[0]
        blank = sec.children[0]
        para = sec.children[1]
        first_bold = para.children[1]
        assert first_bold.simple_text == "bold_text"

        
    with patch('sys.argv', ['tester', "--doc_type", "json", str(org_file), '--output', '/tmp/foo', '--overwrite']):
        parsers = main()
    with open('/tmp/foo', 'r', encoding='utf-8') as f:
        outvalue = f.read()
        
            
    reload_data = json.loads(outvalue)
    jdata = parsers[0].root.to_json_dict()

    # just check some of the structure to do a sanity check on reloading from file
    assert jdata['cls'] == reload_data['cls']
    o_sec_1 = jdata['props']['trunk']['props']['nodes'][0]
    r_sec_1 = jdata['props']['trunk']['props']['nodes'][0]
    o_head_1 = o_sec_1['props']['heading']
    r_head_1 = r_sec_1['props']['heading']
    assert o_head_1['cls'] == "<class 'roam2doc.tree.Heading'>"
    assert r_head_1['cls'] == "<class 'roam2doc.tree.Heading'>"
    assert o_head_1['props']['node_id'] == r_head_1['props']['node_id']
    
    with patch('sys.argv', ['tester', str(org_file), '--output', '/tmp/foo']):
        with pytest.raises(SystemExit):
                parsers = main()
    with patch('sys.argv', ['tester', str(org_file), '--output', '/directory_that_does_not_exist/foo']):
        with pytest.raises(SystemExit):
            parsers = main()
        
        
def test_roam_combine_1():
   
    def do_checks(b2):
        sec = b2.children[0]
        para = sec.children[1]
        link1 = para.children[0]
        link2 = para.children[1]
        in_text = link2.children[0]
        sd = in_text.get_source_data()
        source = sd['source']
        assert "ID style" in source and "section 2 by property" in source
        t2 = para.children[2]

    this_dir = Path(__file__).resolve().parent
    target_dir = Path(this_dir, 'org_files', 'roam1')
    list_file = Path(target_dir, 'roam_combine1.list')
    with patch('sys.argv', ['tester', str(list_file), '--output', '/tmp/foo', '--overwrite']):
        parsers = main()
    do_checks(parsers[1].branch)
    # just to make sure --overwrite works
    with patch('sys.argv', ['tester', str(target_dir), '--output', '/tmp/foo', '--overwrite']):
        parsers = main()
    do_checks(parsers[1].branch)
            
def test_roam_combine_2():
   
    def do_checks(b2):
        sec = b2.children[0]
        have_three = False
        have_two = False
        for pos, kid in enumerate(sec.children):
            if "file three" in ' '.join(kid.to_latex()):
                have_three = True
                assert not have_two, "File three found after file two, wrong order"
            if "stuff after the include" in ' '.join(kid.to_latex()):
                have_two = True
                assert have_two, "File two before after file three, wrong order"

    this_dir = Path(__file__).resolve().parent
    target_dir = Path(this_dir, 'org_files', 'roam2')
    list_file = Path(target_dir, 'roam_combine2.list')
    with patch('sys.argv', ['tester', str(list_file), '--output', '/tmp/foo', '--overwrite']):
        parsers = main()
    do_checks(parsers[1].branch)
    #  print(parsers[0].root.to_latex())

    
            
def test_objects_para():
   
    this_dir = Path(__file__).resolve().parent
    org_file = Path(this_dir, 'org_files', 'examples', 'objects.org')
    with patch('sys.argv', ['tester', str(org_file), '--output', '/tmp/foo', '--overwrite']):
        parsers = main()

    b1 = parsers[0].branch
    sec = b1.children[0]
    blank = sec.children[0]
    para = sec.children[1]
    sd = para.get_source_data()
    pos = 0
    if False:
        for obj in para.children:
            print(pos)
            sd = obj.get_source_data()
            pprint(sd)
            pos += 1

    first_bold = para.children[1]
    assert first_bold.simple_text == "bold_text"
    assert(first_bold.get_source_data()['source']) == "*bold_text*"

    first_italic = para.children[4]
    assert first_italic.simple_text == "italic_text"
    assert(first_italic.get_source_data()['source']) == "/italic_text/"

    first_uline = para.children[7]
    assert first_uline.simple_text == "underlined_text"
    assert(first_uline.get_source_data()['source']) == "_underlined_text_"

    first_struck = para.children[10]
    assert first_struck.simple_text == "linethrough_text"
    assert(first_struck.get_source_data()['source']) == "+linethrough_text+"

    first_verbatim = para.children[13]
    assert first_verbatim.simple_text == "verbatim_text"
    assert(first_verbatim.get_source_data()['source']) == "=verbatim_text="

    last_code = para.children[17]
    assert last_code.simple_text == "code containing = sign "
    assert(last_code.get_source_data()['source']) == "~code containing = sign ~"


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
    
