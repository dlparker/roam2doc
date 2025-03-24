import re
import logging
import typing
from enum import Enum
from pprint import pformat
from roam2doc.tree import (Root, Branch, Section, Heading, Text, Paragraph, BlankLine, TargetText,
                         LinkTarget, BoldText, ItalicText,
                         UnderlinedText, LinethroughText, InlineCodeText,
                         VerbatimText, Blockquote, CodeBlock, List,
                         ListItem, OrderedList, OrderedListItem, UnorderedList,
                         UnorderedListItem, DefinitionList, DefinitionListItem,
                         DefinitionListItemTitle, DefinitionListItemDescription,
                         Table, TableRow, TableCell, Link, Image, InternalLink)

class DocParser:

    def __init__(self, text, source, root=None):
        self.text = text
        self.lines = text.split('\n')
        self.source = source
        if root is None:
            root = Root(source)
            self.branch = root.trunk
        else:
            self.branch = Branch(root.trunk, source)
        self.root = root
        self.doc_properties = None
        self.doc_title = None
        self.current_section = None
        self.sections = []
        self.match_log_format =    "%15s %12s matched line %s"
        self.no_match_log_format = "%15s %12s matched line %s"
        self.parser_stack = []
        self.parse_problems = []
        self.logger = logging.getLogger('roam2doc-parser')
        
    def get_parse_range(self):
        if self.current_section is None:
            return (0, len(self.lines))
        return (self.current_section.cursor, self.current_section.end)
    
    def push_parser(self, parser):
        self.parser_stack.append(parser)

    def current_parser(self):
        if len(self.parser_stack) > 0:
            return self.parser_stack[-1]
        return None

    def pop_parser(self, parser):
        index = self.parser_stack.index(parser)
        if index != len(self.parser_stack) - 1:
            raise ValueError('parser not last in stack')
        self.parser_stack.pop(-1)

    def get_parser_parent(self, parser):
        # let the exception propogate
        index = self.parser_stack.index(parser)
        if index == 0:
            return None
        return self.parser_stack[index - 1]

    def record_parse_problem(self, problem_dict):
        self.parse_problems.append(problem_dict)
    
    def find_first_section(self, offset=0, include_blank_start=False):
        """ Section parsing it done by finding the start and the end before parsing. This allows the section
        parser to be the parent of all other parsers, simplifying the logic in most of those."""
        lines = self.lines[offset:]
        pos = -1
        start_pos = -1
        # we have a section start, whether there is a heading or not
        # look for something that starts another section or end of file, skipping
        # the first line which may or may not be a heading
        end_pos = len(lines)  - 1
        pos  = 0
        if pos >= end_pos + 1:
            return None
        # single line file is possible
        subs = lines[pos:]
        tool_box = ToolBox()
        heading_matcher = tool_box.get_matcher(MatcherType.heading)
        for line in subs:
            if heading_matcher.match_line(line):
                end_pos = pos - 1
                break
            pos += 1
        return SectionParse(self, start_pos + offset, end_pos + offset)

    def parse_file_start(self):
        """ This method is broken out from the parse method to make it easier to build
        child classes for test, so that the test version can poke at the steps of the process """
        start_offset = 0
        properties = self.parse_properties(start_offset, len(self.lines))
        if properties:
            # need to skip some lines before searching for section
            self.doc_properties = properties
            # props wrapped in :PROPERTIES:\nprops\n:END:
            start_offset += len(properties) + 2
            self.logger.info("Found file level properies, setting offset to %s", start_offset)
            self.logger.debug("File level properies = %s", pformat(properties))
        # might have a #+title: next
        if self.lines[start_offset].startswith("#+title:"):
            title = ":".join(self.lines[start_offset].split(":")[1:])
            self.doc_title = title
            start_offset += 1
            self.logger.info("Found file title, setting offset to %s", start_offset)
            self.logger.debug("File title = %s", pformat(title))
        section = self.find_first_section(start_offset, include_blank_start=True)
        return section

    def find_top_sections(self):
        """ This method is broken out from the parse method to make it easier to build
        child classes for test, so that the test version can poke at the steps of the process """
        first_section = self.parse_file_start()
        start_offset = first_section.end
        self.sections.append(first_section)
        self.logger.info("found level 1 section %d lines %d to %s of %d",
                         0, 
                         first_section.start + 1,
                         first_section.end + 1,
                         len(self.lines))
        tool_box = ToolBox()
        pos = start_offset + 1
        starts = []
        while pos < len(self.lines):
            elem  = tool_box.next_greater_element(self, pos, len(self.lines))
            if elem is None:
                break
            pos = elem['match_line']
            pos += 1
            if elem['match_type'] != MatcherType.heading:
                continue
            stars =  elem['matched_contents']['stars']
            level = len(stars)
            if level > 1:
                continue
            starts.append(elem['match_line'])
        index = 0
        for start in starts:
            if index == len(starts) - 1:
                end = len(self.lines) - 1
            else:
                end = starts[index+1] -1
            index += 1
            section = SectionParse(self, start, end)
            self.logger.info("found level 1 section %d lines %d to %s of %d",
                        len(self.sections),
                        section.start + 1,
                        section.end + 1,
                        len(self.lines))
            self.sections.append(section)
        
    def parse(self):
        self.find_top_sections()
        index = 0
        for section in self.sections:
            self.current_section = section
            self.logger.info("running parser for level 1 section %d lines %d to %s of %d",
                             index,
                             section.start + 1,
                             section.end + 1,
                             len(self.lines))
            self.push_parser(section)
            section.parse()
            self.pop_parser(section)
            index += 1
        result = dict(sections=self.sections, title=self.doc_title, properties=self.doc_properties)
        return result

    def parse_properties(self, start, end):
        # :PROPERTIES:
        #  some number of property defs all starting with :
        # :END:
        start_line = self.lines[start].lstrip()
        if start_line.startswith(':PROPERTIES'):
            prop_lines = [start_line,]
            offset = start + 1
            while offset <= end:
                tmp = self.lines[offset]
                if not tmp.startswith(':'):
                    break
                prop_lines.append(tmp)
                offset += 1
            if prop_lines[-1].lower() == ":end:":
                self.logger.debug("processing properties in lines %d to %s", start, end)
                # first and last are start and end, only middle ones matter
                prop_dict = {}
                for prop_line in prop_lines[1:-1]:
                    tmp = prop_line.split(':')
                    name = tmp[1]
                    value = ":".join(tmp[2:])
                    prop_dict[name] = value
                self.logger.debug("parsed properties %s", pformat(prop_dict))
                return prop_dict
            else:
                self.logger.warning("failed to parse properties starting on line %d", offset)
        return None


class ParseTool:

    def __init__(self, doc_parser, start, end):
        self.doc_parser = doc_parser
        range = doc_parser.get_parse_range()
        self.tree_node = None
        self.start = start
        self.end = end
        self.logger = logging.getLogger('roam2doc-parser')
        self.match_log_format =  doc_parser.match_log_format
        self.no_match_log_format = doc_parser.no_match_log_format
    
    def get_parent_parser(self):
        # can't do this during init, not added to doc parser yet
        return self.doc_parser.get_parser_parent(self)
    
    def get_section_parser(self):
        if isinstance(self, SectionParse):
            return self
        p = self.doc_parser.get_parser_parent(self)
        while p is not None and not isinstance(p, SectionParse):
            p.doc_parser.get_parser_parent(p)
        return p


class SectionParse(ParseTool):

    def __init__(self, doc_parser, start, end):
        self.start = start
        self.end = end
        self.cursor = start
        self.level = 0
        self.heading_text = None
        self.properties = None
        super().__init__(doc_parser, start, end)

    def calc_level(self):
        first_line = self.doc_parser.lines[self.start].lstrip()
        if first_line.startswith('*'):
            last_star = first_line.lstrip().rfind('*', re.M) 
            self.level = last_star + 1
            self.heading_text = first_line[last_star + 1:].strip()
            if self.end == self.start:
                return True
            return True
        # We don't have an actual heading, just start of file.
        # We need to figure out some kind of text for a heading, cause
        # that is how we roll.
        # The doc_parser may have stored zeroth section
        # properties and or title, so check for that.
        if self.doc_parser.doc_title is not None:
            self.heading_text = f"Start of {self.doc_parser.doc_title}"
        else:
            self.heading_text = f"Start of {self.doc_parser.source}"
        self.level = 1
        return False

    def parse(self):
        found_heading = self.calc_level()
        if found_heading:
            self.cursor = self.start + 1
        parent = self.get_parent_parser()
        if parent:
            tree_parent = parent.tree_node
        else:
            tree_parent = self.doc_parser.branch
        self.tree_node = Section(tree_parent, self.heading_text)
        if self.end == self.start:
            self.logger.debug("Header %s has no following section contents", str(self))
            return self.end
        self.properties = self.doc_parser.parse_properties(self.cursor, self.end)
        short_id = f"Section@{self.start}"
        if self.properties:
            self.logger.debug("%s has properties %s", short_id, pformat(self.properties))
            self.cursor += len(self.properties) + 2
        tool_box = ToolBox()
        # now find all greater elements
        pos = self.cursor
        last_sub_start = pos - 1
        last_sub_end = pos - 1
        gaps = []
        while pos < self.end + 1:
            elem  = tool_box.next_greater_element(self.doc_parser, pos, self.end)
            if elem:
                self.logger.debug('%s found inner element %s at %d', str(self),
                                  elem['match_type'],
                                  elem['match_line'])
                parse_tool = elem['parse_tool']
                match_pos = elem['match_line']
                if match_pos > last_sub_end:
                    para = ParagraphParse(self.doc_parser, last_sub_end + 1, match_pos - 1)
                    self.doc_parser.push_parser(para)
                    para.parse() + 1
                    self.doc_parser.pop_parser(para)
                parser = parse_tool(self.doc_parser, match_pos, self.end)
                self.doc_parser.push_parser(parser)
                sub_start = match_pos
                sub_end = parser.parse()
                self.doc_parser.pop_parser(parser)
                pos = sub_end + 1
                last_sub_start = match_pos
                last_sub_end = sub_end
            else:
                # no more elements in range, so make a para
                if last_sub_end < self.end + 1:
                    para = ParagraphParse(self.doc_parser, last_sub_end + 1, self.end)
                    self.doc_parser.push_parser(para)
                    para.parse()
                    self.doc_parser.pop_parser(para)
                    pos = self.end + 1
        return self.end

    def __str__(self):
        msg = f"Level {self.level} "
        if self.heading_text:
            msg += self.heading_text
        return msg

class TableParse(ParseTool):

    def __init__(self, doc_parser, start, end):
        super().__init__(doc_parser, start, end)
        
    def parse(self):
        parent_parser = self.doc_parser.get_parser_parent(self)
        parent_tree_node = parent_parser.tree_node
        table = Table(parent_tree_node)
        tool_box = ToolBox()
        matcher = tool_box.get_matcher(MatcherType.table)
        pos = start_pos = self.start
        short_id = f"Table@{start_pos}"
        while pos < self.end + 1:
            for line in self.doc_parser.lines[pos:self.end + 1]:
                next_elem = tool_box.next_greater_element(self.doc_parser, pos, self.end)
                if not next_elem:
                    return pos - 1
                if next_elem['match_type'] != MatcherType.table:
                    return pos - 1
                self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                tr = TableRow(table)
                for item in line.split('|')[1:-1]:
                    cell = TableCell(tr)
                    text = Text(cell, item)

                pos += 1
        return self.end

class ListParse(ParseTool):

    def __init__(self, doc_parser, start, end):
        super().__init__(doc_parser, start, end)
        self.list_type = None
        self.margin = 0
        self.start_value = None
        tool_box = ToolBox()
        list_matcher = tool_box.get_matcher(MatcherType.alist)
        self.regexps = {
            ListType.unordered_list: list_matcher.get_compiled_regex(ListType.unordered_list),
            ListType.ordered_list:  list_matcher.get_compiled_regex(ListType.ordered_list),
            ListType.def_list:  list_matcher.get_compiled_regex(ListType.def_list),
        }


    def parse(self):
        parent_parser = self.doc_parser.get_parser_parent(self)
        pos = self.start
        end = self.end
        short_id = f"List@{pos}"
        # we know we are on the first line of a list, so
        # figure out wnat kind and initialize it.
        line = self.doc_parser.lines[pos]
        matcher = MatchList()
        match_res = self.list_line_get_type(line)
        if match_res is None:
            # we are going to follow the rule of ignoring text that confuses
            # use, just recoring the problem
            problem = dict(description="List parser called with first line that is not a list item",
                           problem_line_pos=pos, problem_line=line)
            self.doc_parser.record_parse_problem(problem)
            return
        # This will be the margin for all list items, so the
        # depth calculation needs to subtract this first
        margin = match_res['lindent']
        self.list_type = list_type = match_res['list_type']
        level = 1
        parent = self.get_parent_parser()
        tree_parent = parent_parser.tree_node
        if isinstance(parent, ListParse):
            parent_list = parent_parser.tree_node
            parent_last_item = parent_list.children[-1]
            tree_parent = parent_last_item
        if list_type == ListType.ordered_list:
            the_list = OrderedList(parent=tree_parent, margin=margin)
            content_list = [Text(the_list, match_res['contents']),]
            ordinal = match_res['bullet'].rstrip(".").rstrip(')')
            item = OrderedListItem(the_list, level, ordinal, content_list)
        elif list_type == ListType.unordered_list:
            the_list = UnorderedList(parent=tree_parent, margin=margin)
            content_list = [Text(the_list, match_res['contents']),]
            item = UnorderedListItem(the_list, level, content_list)
        elif list_type == ListType.def_list:
            the_list = DictionaryList(parent=tree_parent, margin=margin)
            title = DictionaryListItemTitle(the_list, match_res['tag'])
            content_list = [Text(the_list, match_res['contents']),]
            desc = DictionaryListItemDescription(the_list, content_list)
            item = DefinitionListItem(the_list, title, desc)
        else:
            desc = "List parser code is buggy, detected a list type but has no code for it"
            problem = dict(description=desc, problem_line_pos=pos, problem_line=line)
            self.doc_parser.record_parse_problem(problem)
            return self.start
        self.tree_node = the_list
        self.logger.debug(self.match_log_format, short_id, "List", line)
        self.logger.debug("%15s %12s created item %s", short_id, '', item)
        tool_box = ToolBox()
        heading_matcher = tool_box.get_matcher(MatcherType.heading)
        blank_count = 0
        spaces_per_level = 0
        para_lines = []
        pos += 1
        current_item = item
        while pos < end + 1:
            for line in self.doc_parser.lines[pos:end + 1]:
                if heading_matcher.match_line(line):
                    self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                    if len(item.para_lines) > 0:
                        self.handle_item_para(item)
                    return pos - 1
                if line.strip() == '':
                    blank_count += 1
                    if blank_count == 2:
                        if len(item.para_lines) > 0:
                            self.handle_item_para(item)
                        if isinstance(parent, ListParse):
                            return pos - 2
                        BlankLine(item)
                        BlankLine(item)
                        return pos
                    pos += 1
                    break
                elif blank_count:
                    blank_count -= 1
                match_res = self.list_line_get_type(line)
                if match_res is None:
                    current_item.para_lines.append(pos)
                    pos += 1
                    break
                if match_res['list_type'] != list_type:
                    if len(item.para_lines) > 0:
                        self.handle_item_para(item)
                    if isinstance(parent, ListParse):
                        if match_res['list_type'] == parent.list_type:
                            return pos - 1
                    parser = ListParse(self.doc_parser, pos, self.end)
                    self.doc_parser.push_parser(parser)
                    pos = parser.parse() + 1
                    self.doc_parser.pop_parser(parser)
                    break
                level = 1
                if spaces_per_level != 0:
                    level = int(match_res['lindent'] / spaces_per_level) + 1
                else:
                    if match_res['lindent'] > margin:
                        # this line is indented beyond first so we can calc the
                        # indent to level ratio
                        spaces_per_level = match_res['lindent'] - self.margin
                        level = int(match_res['lindent'] / spaces_per_level) + 1
                self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                if list_type == ListType.ordered_list:
                    content_list = [Text(the_list, match_res['contents']),]
                    ordinal = match_res['bullet'].rstrip(".").rstrip(')')
                    item = OrderedListItem(the_list, level, ordinal, content_list)
                elif list_type == ListType.unordered_list:
                    content_list = [Text(the_list, match_res['contents']),]
                    item = UnorderedListItem(the_list, level, content_list)
                elif list_type == ListType.def_list:
                    title = DictionaryListItemTitle(the_list, match_res['tag'])
                    content_list = [Text(the_list, match_res['contents']),]
                    desc = DictionaryListItemDescription(the_list, content_list)
                    item = DefinitionListItem(the_list, title, desc)
                current_item = item
                self.logger.debug("%15s %12s created item %s", short_id, '', item)
                pos += 1
        if len(item.para_lines) > 0:
            self.handle_item_para(item)
        return pos 
                
    def list_line_get_type(self, line):
        for bullettype in [ListType.ordered_list, ListType.unordered_list, ListType.def_list]:
            match_res = self.parse_list_item(line, bullettype)
            if match_res:
                return match_res
        return None

    def handle_item_para(self, item):
        if len(item.para_lines) < 1:
            return
        para = ParagraphParse(self.doc_parser, item.para_lines[0], item.para_lines[-1])
        self.doc_parser.push_parser(para)
        para.parse()
        self.doc_parser.pop_parser(para)
        item.para_lines = []

    def parse_list_item(self, line, list_type):
        """Parse a single list item line and return its components."""
        if list_type == "def":
            pattern = self.regexps[ListType.def_list]
        elif list_type == ListType.ordered_list:
            pattern = self.regexps[ListType.ordered_list]
        else:  # unordered
            pattern = self.regexps[ListType.unordered_list]
        match = pattern.match(line)
        if not match:
            return None

        parts = match.groupdict()
        return {
            'list_type': list_type,
            'lindent': len(parts['lindent']),
            'bullet': parts['bullet'],
            'counter_set': parts['counter_set'],  # e.g., [@5], None if absent
            'checkbox': parts['checkbox'],        # e.g., [X], None if absent
            'tag': parts.get('tag'),             # For def lists, None otherwise
            'contents': parts['contents'] or ''  # Rest of line, empty if None
        }
    
        
class ParagraphParse(ParseTool):

    def __init__(self, doc_parser, start, end):
        super().__init__(doc_parser, start, end)
        self.start = start
        self.end = end
        self.logger = logging.getLogger('roam2doc-parser')
        
    def parse(self):
        parent = self.get_parent_parser()
        self.tree_node = para = Paragraph(parent.tree_node)
        last_was_blank = False
        self.logger.debug('Adding paragraph to parser %s', parent)
        tool_box = ToolBox()
        start = pos = self.start
        end = self.end
        # skip past any leading blank lines
        any = False
        while pos < self.end + 1 and not any:
            for line in self.doc_parser.lines[pos:end + 1]:
                if line.strip() == "":
                    BlankLine(parent.tree_node)
                    pos += 1
                else:
                    any = True
                    break
            
        # find all the paragraphs first
        ranges = []
        prev = pos
        while pos < self.end + 1:
            for line in self.doc_parser.lines[pos:end + 1]:
                if line.strip() == "":
                    ranges.append([prev, pos-1])
                    prev = pos
                pos += 1

        for r_spec in ranges:
            tool_box.get_text_and_object_nodes(self.doc_parser, self, r_spec[0], r_spec[1])
            
        return pos 

class LineRegexMatch:
    """ The structure of this class and its children might look a bit funny,
    but i am  trying to ensure that the re patterns are compiled just once,
    not every time a class is instantiated"""
    
    def __init__(self, patterns):
        self.patterns = patterns

    def match_line(self, line):
        for re in self.patterns:
            sr = re.match(line)
            if sr:
                return dict(start=sr.start(), end=sr.end(),
                            groupdict=sr.groupdict(),
                            matched=sr)
        return False

    def match_line_range(self, lines, start, end):
        matches = []
        for line in lines[start, end+1]:
            m = self.match_line(line)
            if m:
                matches.append(m)
        return matches
    
    def get_parse_tool(self):
        raise NotImplementedError
    
    def __str__(self):
        return self.__class__.__name__

class ObjectRegexMatch:
    """ Base class for Matchers that look for org 'objects' withing text,
    rather than whole line patters. Things such as *bold*.
    """
    
    def __init__(self, patterns):
        self.patterns = patterns

    def match_text(self, text, first_only=False):
        matches = []
        for re in self.patterns:
            for m in re.finditer(text):
                matched = dict(start=m.start(),
                               end=m.end(),
                               groupdict=m.groupdict(),
                               matched=m)
                matches.append(matched)
        return matches

    def __str__(self):
        return self.__class__.__name__

class BoldObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'\*(?P<text>.+?)\*'),]

    def __init__(self):
        super().__init__(self.patterns)


class ItalicObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'/(?P<text>.+?)/'),]

    def __init__(self):
        super().__init__(self.patterns)

class UnderlinedObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'\b_(?P<text>\w*)_\b', re.M),
                re.compile(r'\b_(?P<text>[a-zA-Z0-9[ ]*)_\b')]
    def __init__(self):
        super().__init__(self.patterns)
        
class LineThroughObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'\+(?P<text>.+?)\+'),]
    
    def __init__(self):
        super().__init__(self.patterns)
        
class InlineCodeObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'=(?P<text>.+?)='),
                re.compile(r'~(?P<text>.+?)~')]

    def __init__(self):
        super().__init__(self.patterns)
        
class VerbatimObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'=(?P<text>.+?)='),]

    def __init__(self):
        super().__init__(self.patterns)
        
class MatchHeading(LineRegexMatch):
    patterns = [re.compile(r'^(?P<stars>\*+)[ \t]*(?P<heading>.*)?'),]

    def __init__(self):
        super().__init__(self.patterns)

    def match_line(self, line):
        res = super().match_line(line)
        if res:
            tmp = line.lstrip('*')
            rest = line.lstrip()[len(line) - len(tmp):]
            if '*' in rest:
                # treat it as a regular line containing bold text
                return None
        return res
            
    def get_parse_tool(self):
        return SectionParse

class MatchDoubleBlank(LineRegexMatch):
    patterns = [re.compile(r"^[ \t].*$"),]

    def __init__(self):
        super().__init__(self.patterns)

    def match_line_range(self, lines, start, end):
        first = -2
        pos = start
        for line in lines[start:end+1]:
            m = self.match_line(line)
            if first == pos - 1:
                return dict(start=first, end=pos)
            first = pos
            pos += 1
        return None
    
class MatchTable(LineRegexMatch):
    patterns = [re.compile(r"^[ \t]*\|[ \t]*"),
                re.compile(r"^[ \t]*\+-.*")]

    def __init__(self):
        super().__init__(self.patterns)

    def get_parse_tool(self):
        return TableParse
        

class MatchList(LineRegexMatch):

    UNORDERED_LIST_regex = r'(?P<lindent>\s*)(?P<bullet>[-+*])'\
        r'\s+(?P<counter_set>\[@[a-z\d]+\])?(?:\s*'\
        r'(?P<checkbox>\[(?: |X|x|\+|-)\]))?(?:\s*(?P<contents>.*))?$'
    ORDERED_LIST_regex = r'(?P<lindent>\s*)(?P<bullet>\d+[.)])'\
        r'\s+(?P<counter_set>\[@[a-z\d]+\])?(?:\s*'\
        r'(?P<checkbox>\[(?: |X|x|\+|-)\]))?(?:\s*(?P<contents>.*))?$'
    DEF_LIST_regex = r'(?P<lindent>\s*)(?P<bullet>[-+*])'\
        r'\s+(?P<counter_set>\[@[a-z\d]+\])?(?:\s*'\
        r'(?P<checkbox>\[(?: |X|x|\+|-)\]))?(?:\s*(?P<tag>.*?)'\
        r'(?<!\s)\s*::\s*(?P<contents>.*))?$'

    unordered_re = re.compile(UNORDERED_LIST_regex)
    ordered_re =  re.compile(ORDERED_LIST_regex)
    def_re =  re.compile(DEF_LIST_regex)
    all_patterns = [
        unordered_re,
        ordered_re,
        def_re,
        ]
    def __init__(self):
        super().__init__(self.all_patterns)

    def get_compiled_regex(self, list_type):
        if list_type == ListType.unordered_list:
            return self.unordered_re
        if list_type == ListType.ordered_list:
            return self.ordered_re
        if list_type == ListType.def_list:
            return self.def_re
        
    def match_line(self, line, require_type=None, ignore_type=None):
        if require_type is None and ignore_type is None:
            return super().match_line(line)
        # Instead of the usual initize time list of patterns,
        # we manipulated it for each pattern and call the super,
        # that way we know which pattern matched. Most (all?)
        # other children of regex match don't care.
        if require_type:
            if require_type == ListType.ordered_list:
                self.patterns = [ordered_re,]
            if require_type == ListType.unordered_list:
                self.patterns = [unordered_re,]
            if require_type == ListType.def_list:
                self.patterns = [def_re,]
        else:
            self.patterns = list(self.all_patterns)
            if ignore_type == ListType.ordered_list:
                self.patterns.remove(ordered_re)
            if ignore_type == ListType.unordered_list:
                self.patterns.remove(unordered_re)
            if ignore_type == ListType.def_list:
                self.patterns.remove(def_re)
        return super.match_line(line)
        
    def get_parse_tool(self):
        return ListParse


class LineRegexAndEndMatch(LineRegexMatch):

    def __init__(self, patterns, end_pattern):
        super().__init__(self.patterns)
        self.end_pattern = end_pattern
        
    def match_end_line(self, line):
        sr = self.end_pattern.match(line)
        if sr:
            return dict(start=sr.start(), end=sr.end(),
                        groupdict=sr.groupdict(),
                        matched=sr)
        return False
    
class MatchSrc(LineRegexAndEndMatch):
    patterns = [re.compile(r'^[ \t]*\#\+BEGIN_SRc\s*(?P<language>\w+.)?', re.IGNORECASE),]
    end_pattern = re.compile(r'^[ \t]*\#\+END_SRC', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

    
class MatchQuote(LineRegexAndEndMatch):
    patterns = [re.compile(r'^[ \t]*\#\+BEGIN_QUOTE\s*(?P<cite>\w+.*)?', re.IGNORECASE),]
    end_pattern = re.compile(r'^[ \t]*\#\+END_QUOTE', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

    def get_parse_tool(self):
        return ParagraphParse
        
class MatchCenter(LineRegexAndEndMatch):
    patterns = [re.compile(r'^[ \t]*\#\+BEGIN_CENTER', re.IGNORECASE),]
    end_pattern = re.compile(r'[ \t]*^\#\+END_CENTER', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)
    
    def get_parse_tool(self):
        return ParagraphParse
    
class MatchExample(LineRegexAndEndMatch):
    patterns = [re.compile(r'^[ \t]*\#\+BEGIN_EXAMPLE', re.IGNORECASE),]
    end_pattern = re.compile(r'^[ \t]*\#\+END_EXAMPLE', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

class MatchGreaterEnd:
    
    def match_line_range(self, doc_parser, lines, start, end):
        pos = start
        tool_box = ToolBox()
        next_elem = tool_box.next_greater_element(doc_parser, pos, end)
        return next_elem


class ListType(str, Enum):

    ordered_list = "ORDERED_LIST"
    unordered_list = "UNORDERED_LIST"
    def_list = "DEF_LIST"
    
    def __str__(self):
        return self.value
    
class MatcherType(str, Enum):

    heading = "HEADING"
    table = "TABLE"
    alist = "LIST"
    quote_block = "QUOTE_BLOCK"
    center_block = "CENTER_BLOCK"
    # end of greater elements
    # special cases
    greater_end = "GREATER_END"
    # lesser elements
    example_block = "EXAMPLE_BLOCK"

    # special cases
    double_blank_line = "DOUBLE_BLANK_LINE"

    # objects
    bold_object = "BOLD_OBJECT"
    italic_object = "ITALIC_OBJECT"
    underlined_object = "UNDERLINED_OBJECT"
    linethrough_object = "LINETHROUGH_OBJECT"
    inlinecode_object = "INLINECODE_OBJECT"
    verbatim_object = "VERBATIM_OBJECT"

    def __str__(self):
        return self.value
    
class ToolBox:
    greater_matchers = {MatcherType.heading: MatchHeading(),
                        MatcherType.table:MatchTable(),
                        MatcherType.alist:MatchList(),
                        MatcherType.quote_block:MatchQuote(),
                        MatcherType.center_block:MatchCenter(),
                        }
    
    greater_end_matchers = {MatcherType.greater_end: MatchGreaterEnd(),
                            }
    # lesser elements
    lesser_matchers = {MatcherType.example_block:MatchExample(),
                        }
    # objects
    object_matchers = {MatcherType.bold_object:BoldObjectMatcher(),
                       MatcherType.italic_object:ItalicObjectMatcher(),
                       MatcherType.underlined_object:UnderlinedObjectMatcher(),
                       MatcherType.linethrough_object:LineThroughObjectMatcher(),
                       MatcherType.inlinecode_object:InlineCodeObjectMatcher(),
                       MatcherType.verbatim_object:VerbatimObjectMatcher(),
                        }
    @classmethod
    def get_matcher_dict(cls):
        res = dict(cls.greater_matchers)
        res.update(cls.greater_end_matchers)
        res.update(cls.lesser_matchers)
        res.update(cls.object_matchers)
        return res

    @classmethod
    def get_matcher(cls, typename):
        d = cls.get_matcher_dict()
        return d.get(typename, None)

    def next_greater_element(cls, doc_parser, start, end):
        """ See https://orgmode.org/worg/org-syntax.html#Elements. Some
        things covered elsewhere such as the zeroth section, which is detected by the initial parser."""
        pos = start
        logger = logging.getLogger('roam2doc-parser')
        for line in doc_parser.lines[start:end+1]:
            # greater elements
            for match_type, matcher in cls.greater_matchers.items():
                match_res = matcher.match_line(line)
                if match_res:
                    logger.debug("matched %s at line %d", match_type, pos)
                    parse_tool = matcher.get_parse_tool()
                    matched = match_res['matched']
                    res = dict(match_type=match_type, pos=pos,
                               parse_tool=parse_tool,
                               string=matched.string,
                               match_line=pos,
                               start_char=match_res['start'],
                               end_char=match_res['end'],
                               matched_contents=matched.groupdict())
                    return res
                # lesser elements
            pos += 1
        return None

    def get_text_and_object_nodes(cls, doc_parser, container, start, end):
        buffer = '\n'.join(doc_parser.lines[start:end + 1])
        matches_per_type = {}
        for match_type, matcher in cls.object_matchers.items():
            mres = matcher.match_text(buffer)
            matches_per_type[match_type] = mres

        by_start = {}
        for match_type in cls.object_matchers:
            for mitem in matches_per_type[match_type]:
                mitem['matcher_type'] = match_type
                by_start[mitem['start']] = mitem

        order = sorted(by_start.keys())
        last_end = -1
        for start_pos in order:
            item = by_start[start_pos]
            if start_pos > last_end + 1:  # Ensure no overlap
                text_chunk = buffer[last_end + 1:start_pos].strip()
                if text_chunk:
                    Text(container.tree_node, text_chunk)
            if item['matcher_type'] == MatcherType.bold_object:
                BoldText(container.tree_node, item['matched'].groupdict()['text'])
            elif item['matcher_type'] == MatcherType.italic_object:
                ItalicText(container.tree_node, item['matched'].groupdict()['text'])
            elif item['matcher_type'] == MatcherType.underlined_object:
                UnderlinedText(container.tree_node, item['matched'].groupdict()['text'])
            elif item['matcher_type'] == MatcherType.linethrough_object:
                LinethroughText(container.tree_node, item['matched'].groupdict()['text'])
            elif item['matcher_type'] == MatcherType.inlinecode_object:
                InlineCodeText(container.tree_node, item['matched'].groupdict()['text'])
            elif item['matcher_type'] == MatcherType.verbatim_object:
                VerbatimText(container.tree_node, item['matched'].groupdict()['text'])
            last_end = item['end']
            # Catch trailing text
        if last_end + 1 < len(buffer):
            text_chunk = buffer[last_end + 1:].strip()
            if text_chunk:
                Text(container.tree_node, text_chunk)
