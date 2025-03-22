#!/usr/bin/env python
from roam2doc.parse import DocParser

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

t1()
