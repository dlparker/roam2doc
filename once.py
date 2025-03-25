#!/usr/bin/env python
from pathlib import Path
import sys
from pprint import pprint
sys.path.append(str(Path('./src').resolve()))
                
from roam2doc.parse import DocParser, ToolBox

def t1():
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

    doc_parser = DocParser(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())

def t2():
    lines = []
    lines.append('* Section 1 heading')
    lines.append('')
    lines.append('')
    lines.append('This will be a <<paragraph>>.')
    lines.append('This continues the paragraph.')
    lines.append('The next line (blank) will end the paragraph.')
    lines.append('')
    lines.append('')
    lines.append('This will be a second paragraph. ')
    lines.append('The following blank lines will end it.')
    lines.append('The following next two blank will also be part of the paragraph.')
    lines.append('They should be part of the section directly.')
    lines.append('')
    lines.append('a link [[arubop][link to last line of the definition list later in the page]]')
    lines.append('')
    lines.append('')
    lines.append('')
    lines.append('This will be a third paragraph.')
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
    lines.append('* new top')
    lines.append('| a | *1 bold item* |')
    lines.append('| b | /2 italian items/ |')
    lines.append('| c | +3 other items+ |')
    lines.append('')
    lines.append('')
    lines.append('* a section')
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
    lines.append('')
    lines.append(' */+bold italic strikethrough+/*')
    lines.append('')
    lines.append('a link [[paragraph][link to section 1 first line word paragraph]]')
    lines.append('')
    lines.append('a link [[Section 1 heading][link to section 1 *with some bold text!*]]')
    lines.append('')
    lines.append('a bad link [[flabist][link to **bad thing!*]]')
    lines.append('')
    lines.append('last para -1 line 1')
    lines.append('')
    lines.append('last para line 1')
    lines.append('')
    
    
    buff = '\n'.join(lines)

    doc_parser = DocParser(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())


def t3():
    lines = []
    lines.append('* section 1')
    lines.append('')
    lines.append('last-1 para line 1')
    lines.append('')
    lines.append('last para line 1')
    lines.append('')
    #lines.append("<<target>>")
    #lines.append("[[target][link with objects */+bold+/*]]")
    
    buff = '\n'.join(lines)

    doc_parser = DocParser(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())

t2()
