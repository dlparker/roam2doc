import re
import logging
import typing
from collections import defaultdict
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
    
    def find_first_section(self, offset=0):
        pos = offset
        start_pos = pos
        end_pos = 0
        level = 1
        heading_text = None
        # if the first line is not a heading, then we don't have one,
        # we have a zeroth section with no heading
        tool_box = ToolBox(self)
        heading_matcher = tool_box.get_matcher(MatcherType.heading)
        elem = heading_matcher.match_line(self.lines[pos])
        if elem:
            stars =  elem['groupdict']['stars']
            level = len(stars)
            heading_text = elem['groupdict']['heading']
            pos += 1
        while pos < len(self.lines):
            if heading_matcher.match_line(self.lines[pos]):
                break
            pos += 1
        end_pos = pos - 1
        return SectionParse(self, offset, end_pos)

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
        section = self.find_first_section(start_offset)
        return section

    def find_top_sections(self):
        """ This method is broken out from the parse method to make it easier to build
        child classes for test, so that the test version can poke at the steps of the process """
        first_section = self.parse_file_start()
        start_offset = first_section.end
        self.sections.append(first_section)
        self.logger.info("found level 1 section %d lines %d to %s of %d",
                         0, 
                         first_section.start,
                         first_section.end,
                         len(self.lines))
        tool_box = ToolBox(self)
        pos = start_offset + 1
        starts = []
        while pos < len(self.lines):
            elem  = tool_box.next_greater_element(pos, len(self.lines))
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
                        section.start,
                        section.end,
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
        self.level = 0
        self.heading_text = None
        self.properties = None
        super().__init__(doc_parser, start, end)

    def calc_level(self):
        first_line = self.doc_parser.lines[self.start].lstrip()
        if first_line.startswith('*'):
            last_star = first_line.lstrip().rfind('*')
            self.level = last_star + 1
            self.heading_text = first_line[last_star + 1:].strip()
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
        pos = self.start
        if found_heading:
            pos += 1
        parent = self.get_parent_parser()
        if parent:
            tree_parent = parent.tree_node
        else:
            tree_parent = self.doc_parser.branch
        self.tree_node = Section(tree_parent, self.heading_text)
        if self.end == self.start:
            self.logger.debug("Header %s has no following section contents", str(self))
            return self.end
        self.properties = self.doc_parser.parse_properties(pos, self.end)
        short_id = f"Section@{self.start}"
        if self.properties:
            self.logger.debug("%s has properties %s", short_id, pformat(self.properties))
            pos += len(self.properties) + 2
        tool_box = ToolBox(self.doc_parser)
        # now find all greater elements
        last_sub_start = pos - 1
        last_sub_end = pos - 1
        gaps = []
        while pos < self.end + 1:
            elem  = tool_box.next_greater_element(pos, self.end)
            if elem:
                self.logger.debug('%s found inner element %s at %d', str(self),
                                  elem['match_type'],
                                  elem['match_line'])
                parse_tool = elem['parse_tool']
                match_pos = elem['match_line']
                if match_pos > last_sub_end:
                    para = ParagraphParse(self.doc_parser, last_sub_end + 1, match_pos - 1)
                    self.doc_parser.push_parser(para)
                    para.parse()
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
                if last_sub_end < self.end:
                    self.logger.debug('%s found inner element making new paragraph for %d to %d', str(self),
                                      last_sub_end + 1, self.end)
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
        self.tree_node = table = Table(parent_tree_node)
        tool_box = ToolBox(self.doc_parser)
        matcher = tool_box.get_matcher(MatcherType.table)
        pos = start_pos = self.start
        short_id = f"Table@{start_pos}"
        while pos < self.end + 1:
            for line in self.doc_parser.lines[pos:self.end + 1]:
                next_elem = tool_box.next_greater_element(pos, self.end)
                if not next_elem:
                    return pos - 1
                if next_elem['match_type'] != MatcherType.table:
                    return pos - 1
                self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                tr = TableRow(table)
                for item in line.split('|')[1:-1]:
                    cell = TableCell(tr)
                    content_list = tool_box.get_text_and_object_nodes_in_line(self.tree_node, item)
                    for citem in content_list:
                        citem.move_to_parent(cell)
                pos += 1
        return self.end

class ListParse(ParseTool):

    def __init__(self, doc_parser, start, end):
        super().__init__(doc_parser, start, end)
        self.list_type = None
        self.start_value = None
        self.margin = 0
        self.spaces_per_level = 0
        list_matcher = ToolBox.get_matcher(MatcherType.alist)
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
            # us, just record the problem
            problem = dict(description="List parser called with first line that is not a list item",
                           problem_line_pos=pos, problem_line=line)
            self.doc_parser.record_parse_problem(problem)
            return
        # This will be the margin for all list items, so the
        # depth calculation needs to subtract this first
        parent = self.get_parent_parser()
        tree_parent = parent_parser.tree_node
        if isinstance(parent, ListParse):
            self.margin = parent.margin
            self.spaces_per_level = parent.spaces_per_level
            my_start_level = 1
            tmp = parent
            while tmp and isinstance(tmp, ListParse):
                my_start_level += 1
                tmp = tmp.get_parent_parser()
        else:
            self.margin = margin = match_res['lindent']
            my_start_level = 1
        self.list_type = list_type = match_res['list_type']
        if isinstance(parent, ListParse):
            parent_list = parent_parser.tree_node
            parent_last_item = parent_list.children[-1]
            tree_parent = parent_last_item
        if list_type == ListType.ordered_list:
            the_list = OrderedList(parent=tree_parent, margin=self.margin)
            content_list = [Text(the_list, match_res['contents']),]
            ordinal = match_res['bullet'].rstrip(".").rstrip(')')
            item = OrderedListItem(the_list, ordinal, content_list)
        elif list_type == ListType.unordered_list:
            the_list = UnorderedList(parent=tree_parent, margin=self.margin)
            content_list = [Text(the_list, match_res['contents']),]
            item = UnorderedListItem(the_list, content_list)
        elif list_type == ListType.def_list:
            the_list = DefinitionList(parent=tree_parent, margin=self.margin)
            title = DefinitionListItemTitle(the_list, match_res['tag'])
            content_list = [Text(the_list, match_res['contents']),]
            desc = DefinitionListItemDescription(the_list, content_list)
            item = DefinitionListItem(the_list, title, desc)
        # unless self.list_line_get_type(line) is broken, one of the above MUST match
        self.tree_node = the_list
        self.logger.info(self.match_log_format, short_id, "List", line)
        self.logger.info("%15s %12s created item %s at level %d", short_id, '', the_list, my_start_level)
        self.logger.info("%15s %12s created item %s", short_id, '', item)
        tool_box = ToolBox(self.doc_parser)
        heading_matcher = tool_box.get_matcher(MatcherType.heading)
        blank_count = 0
        para_lines = []
        pos += 1
        current_item = item
        level = my_start_level
        while pos < end + 1:
            for line in self.doc_parser.lines[pos:end + 1]:
                if heading_matcher.match_line(line):
                    self.logger.info(self.match_log_format, short_id, str(matcher), line)
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
                self.logger.info(self.match_log_format, short_id, str(matcher), line)
                if self.spaces_per_level != 0:
                    level = int(match_res['lindent'] / self.spaces_per_level) + 1
                    self.logger.debug("List left indent spaces %d gives level %d", match_res['lindent'], level) 
                else:
                    if match_res['lindent'] > self.margin:
                        # this line is indented beyond first so we can calc the
                        # indent to level ratio
                        self.spaces_per_level = match_res['lindent'] - self.margin
                        level = 2
                        self.logger.debug("List indent spaces per level calculated to be %d", self.spaces_per_level)
                if level < my_start_level:
                    self.logger.debug("List parser returning at pos %d", pos - 1)
                    return pos - 1
                if match_res['list_type'] != list_type or level > my_start_level:
                    self.logger.debug("Processing sub list of type %s at pos  %d", match_res['list_type'], pos)
                    if len(item.para_lines) > 0:
                        self.handle_item_para(item)
                    parser = ListParse(self.doc_parser, pos, self.end)
                    self.doc_parser.push_parser(parser)
                    pos = parser.parse() + 1
                    self.doc_parser.pop_parser(parser)
                    break

                content_list = tool_box.get_text_and_object_nodes_in_line(self.tree_node, match_res['contents'])
                if list_type == ListType.ordered_list:
                    ordinal = match_res['bullet'].rstrip(".").rstrip(')')
                    item = OrderedListItem(the_list, ordinal, content_list)
                elif list_type == ListType.unordered_list:
                    item = UnorderedListItem(the_list, content_list)
                elif list_type == ListType.def_list:
                    title = DefinitionListItemTitle(the_list, match_res['tag'])
                    desc = DefinitionListItemDescription(the_list, content_list)
                    item = DefinitionListItem(the_list, title, desc)
                current_item = item
                self.logger.debug("%15s %12s created item %s", short_id, '', item)
                pos += 1
        if len(item.para_lines) > 0:
            self.handle_item_para(item)
        return pos 
                
    def list_line_get_type(self, line):
        # check def_list first, looks like unordered too
        for bullettype in [ListType.def_list, ListType.ordered_list, ListType.unordered_list]:
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
        if list_type == ListType.def_list:
            pattern = self.regexps[ListType.def_list]
        elif list_type == ListType.ordered_list:
            pattern = self.regexps[ListType.ordered_list]
        else:  # unordered
            pattern = self.regexps[ListType.unordered_list]
        match_res = pattern.match(line)
        if not match_res:
            return None
        parts = match_res.groupdict()
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
        pos = self.start
        end = self.end
        any = False
        breaking = False
        # skip past any leading blank lines
        while pos < self.end + 1 and not any:
            for line in self.doc_parser.lines[pos:end + 1]:
                if line.strip() == "":
                    BlankLine(parent.tree_node)
                    pos += 1
                else:
                    any = True
                    break
        if pos > self.end:
            return
        self.tree_node = para = Paragraph(parent.tree_node)
        self.logger.debug('Adding paragraph to parser %s', parent)
        # find all the paragraphs first
        ranges = []
        start_pos =  pos
        prev_end = start_pos - 1 
        last_was_blank = False
        while pos < self.end + 1:
            for line in self.doc_parser.lines[pos:end + 1]:
                if breaking and "a link" in line:
                    breakpoint()
                if line.strip() != "":
                    if last_was_blank:
                        ranges.append([prev_end + 1, pos - 1])
                        prev_end = pos - 1
                    last_was_blank = False
                else:
                    last_was_blank = True
                pos += 1
        if len(ranges) == 0:
            # must be a single paragraph
            ranges.append([start_pos, self.end])
        elif prev_end < self.end + 1:
            ranges.append([prev_end, self.end])

        if breaking:
            for line_sub in self.doc_parser.lines[self.start:self.end]:
                print(line_sub)
            for r in ranges:
                print(r, '---------')
                for line_sub in self.doc_parser.lines[r[0]: r[1]+1]:
                    print(line_sub)
            breakpoint()

        tool_box = ToolBox(self.doc_parser)
        index = 0
        for r_spec in ranges:
            if index > 0:
                para = Paragraph(parent.tree_node)
            index += 1
            line_index = r_spec[0]
            for line in self.doc_parser.lines[r_spec[0]:r_spec[1] + 1]:
                if line_index == r_spec[1] and line.strip() == '':
                    # we do not include blank that ends a paragraph
                    pass
                elif line_index < r_spec[1] and line.strip() == '':
                    # must be more than one blank after paragraph, we honor that
                    BlankLine(para)
                else:
                    items = tool_box.get_text_and_object_nodes_in_line(para, line)
                line_index += 1
        return self.end 

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
        
class TargetObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'<<(?P<text>.+?)>>'),]

    def __init__(self):
        super().__init__(self.patterns)
        
class InternalLinkObjectMatcher(ObjectRegexMatch):
    patterns = [re.compile(r'\[\[(?P<pathreg>.+?)?\]\[(?P<description>.+?)?\]\]'),]
    
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
        
    def match_line(self, line):
        if line.strip() == '':
            return None
        self.patterns = [self.ordered_re,]
        res = super().match_line(line)
        if res:
            res['list_type'] = ListType.ordered_list
            return res
        # need to do def first, to prevent unordered from matching it
        self.patterns = [self.def_re,]
        res = super().match_line(line)
        if res:
            res['list_type'] = ListType.def_list
            return res
        self.patterns = [self.unordered_re,]
        res = super().match_line(line)
        if res:
            res['list_type'] = ListType.unordered_list
            return res
        
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
        tool_box = ToolBox(self.doc_parser)
        next_elem = tool_box.next_greater_element(pos, end)
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
    target_object = "TARGET_OBJECT"
    internal_link_object = "INTERNAL_LINK_OBJECT"

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
                       MatcherType.target_object:TargetObjectMatcher(),
                       MatcherType.internal_link_object:InternalLinkObjectMatcher(),
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

    def __init__(self, doc_parser):
        self.doc_parser = doc_parser
        
    def next_greater_element(self, start, end):
        """ See https://orgmode.org/worg/org-syntax.html#Elements. Some
        things covered elsewhere such as the zeroth section, which is detected by the initial parser."""
        pos = start
        logger = logging.getLogger('roam2doc-parser')
        for line in self.doc_parser.lines[start:end+1]:
            # greater elements
            for match_type, matcher in self.greater_matchers.items():
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

    def get_text_and_object_nodes_in_line(self, tree_node, line):
        blocks_by_offset = {}

        matches_per_type = {}
        for match_type, matcher in self.object_matchers.items():
            mres = matcher.match_text(line)
            matches_per_type[match_type] = mres

        for match_type in self.object_matchers:
            for mitem in matches_per_type[match_type]:
                mitem['matcher_type'] = match_type
                blocks_by_offset[mitem['start']] = mitem

        # find overlaps. objects can contain other objects, e.g. <<*bold*>>
        items = []
        tmp = list(blocks_by_offset.keys())
        if len(tmp) == 0:
            items.append(Text(tree_node, line))
            return items
        tmp.sort()
        pos = tmp[0]
        by_start = {}
        block_id_pos = 0
        last_block = None
        while block_id_pos < len(tmp):
            pos = tmp[block_id_pos]
            block = blocks_by_offset[pos]
            if last_block and last_block['end'] > block['end']:
                block_id_pos += 1
                continue
            self.fold_inner(pos, blocks_by_offset)
            by_start[pos] = block
            block_id_pos += 1
            last_block = block
        order = sorted(by_start.keys())
        last_end = -1
        for pos,item in by_start.items():
            if pos > last_end + 1:
                text_chunk = line[last_end + 1:pos].strip()
                if text_chunk:
                    items.append(Text(tree_node, text_chunk))
            items.append(self.do_object_parts(item, tree_node))
            last_end = item['end']
        if last_end + 1 < len(line):
            text_chunk = line[last_end + 1:].strip()
            if text_chunk:
                Text(tree_node, text_chunk)
        return items

    def fold_inner(self, pos, blocks_by_offset):
        block = blocks_by_offset[pos]
        start = block['start']
        inner = []
        next_pos = start + 1
        inner_block = blocks_by_offset.get(next_pos, None)
        if inner_block:
            inner.append(inner_block)
            self.fold_inner(next_pos, blocks_by_offset)
            block['inner_objects'] = inner
        
    def do_object_parts(self, item, tree_node):
        simple_text = None
        if "inner_objects" not in item:
            if item['matcher_type'] != MatcherType.internal_link_object:
                simple_text = item['matched'].groupdict()['text']
        tree_item = self.add_object_item(tree_node, item, simple_text)
        if "inner_objects" not in item:
            return tree_item
        if "inner_objects" in item:
            for in_item in item['inner_objects']:
                self.do_object_parts(in_item, tree_item)
        return tree_item
        
    def add_object_item(self, tree_node, item, simple_text=None):
        if item['matcher_type'] == MatcherType.bold_object:
            tree_item = BoldText(tree_node, simple_text)
        elif item['matcher_type'] == MatcherType.italic_object:
            tree_item = ItalicText(tree_node, simple_text)
        elif item['matcher_type'] == MatcherType.underlined_object:
            tree_item = UnderlinedText(tree_node, simple_text)
        elif item['matcher_type'] == MatcherType.linethrough_object:
            tree_item = LinethroughText(tree_node, simple_text)
        elif item['matcher_type'] == MatcherType.inlinecode_object:
            tree_item = InlineCodeText(tree_node, simple_text)
        elif item['matcher_type'] == MatcherType.verbatim_object:
            tree_item = VerbatimText(tree_node, simple_text)
        elif item['matcher_type'] == MatcherType.target_object:
            tree_item = TargetText(tree_node, simple_text)
        elif item['matcher_type'] == MatcherType.internal_link_object:
            target_text = item['matched'].groupdict()['pathreg']
            desc = item['matched'].groupdict()['description']
            tree_item = InternalLink(tree_node, target_text, None)
            items = self.get_text_and_object_nodes_in_line(tree_item, desc)
            if len(items) == 1:
                tree_item.display_text = desc
                tree_item.remove_node(items[0])
        return tree_item
        
