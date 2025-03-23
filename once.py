#!/usr/bin/env python
from pathlib import Path
import sys
sys.path.append(str(Path('./src').resolve()))
                
from roam2doc.parse import DocParser

def t2():
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
    lines.append('')
    lines.append('')
    lines.append('this other text should be in Section 2-2 after list')
    
    buff = '\n'.join(lines)
    lines.append('          this should be para 2 line 1 inside List 2 sub 1 sub 1')
    lines.append('          this should be para 2 line 2 inside List 2 sub 1 sub 1')
    lines.append('          this should be para 2 line 3 inside List 2 sub 1 sub 1')

    doc_parser = DocParser(buff, "inline")
    doc_parser.parse()
    print(doc_parser.root.to_html())

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

t2()
