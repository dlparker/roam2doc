import re
import logging
import typing
from pathlib import Path
from collections import defaultdict
import subprocess
from enum import Enum
from pprint import pformat
from roam2doc.tree import (Root, Branch, Section, Heading, Text, Paragraph, BlankLine, TargetText,
                           LinkTarget, BoldText, ItalicText,
                           UnderlinedText, LinethroughText, InlineCodeText,
                           VerbatimText, CenterBlock, QuoteBlock, CodeBlock,
                           ExampleBlock, CommentBlock, ExportBlock, List,
                           ListItem, OrderedList, OrderedListItem, UnorderedList,
                           UnorderedListItem, DefinitionList, DefinitionListItem,
                           DefinitionListItemTitle, DefinitionListItemDescription,
                           Table, TableRow, TableCell, Link, InternalLink, Image)

class DocParser:

    def __init__(self, text, source, root=None, included_files=None):
        self.text = text
        self.lines = text.split('\n')
        self.source = str(source)
        self.included_files = included_files
        if root is None:
            root = Root(self.source)
            self.branch = Branch(root, self.source, self)
            root.trunk = self.branch
        else:
            self.branch = Branch(root, self.source, self, root.trunk)
            root.trunk.add_node(self.branch)
        self.root = root
        self.doc_properties = None
        self.doc_title = None
        self.current_section = None
        self.sections = []
        self.match_log_format =    "%15s %12s matched line %s"
        self.no_match_log_format = "%15s %12s matched line %s"
        self.parser_stack = []
        self.parse_problems = []
        self.parse_start_callback = None
        self.parse_end_callback = None
        self.logger = logging.getLogger('roam2doc.parser')

    def set_parse_callbacks(self, start_cb, end_cb):
        # For support of whitebox testing, this will
        # cause each parser to have this callback set
        # on it when pushed on the stack
        self.parse_start_callback = start_cb
        self.parse_end_callback = end_cb
        
    def push_parser(self, parser):
        self.parser_stack.append(parser)
        if self.parse_start_callback or self.parse_end_callback:
            parser.set_callbacks(self.parse_start_callback, self.parse_end_callback)

    def current_parser(self):
        if len(self.parser_stack) > 0:
            return self.parser_stack[-1]
        return None

    def pop_parser(self, parser):
        index = self.parser_stack.index(parser)
        if index != len(self.parser_stack) - 1:
            # why doesn't covereage see this when I
            # definitely hit it during testing.
            # Cannot figure it out
            raise ValueError('parser not last in stack') # pragma: no cover
        self.parser_stack.pop(-1)
        parser.set_callbacks(None, None)

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
        # however, it the zeroth section is nothing but properties,
        # followed by a heading, then we will treat that heading
        # as starting the first section
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
            # while we are at it, just skip any blank lines
            while self.lines[start_offset].strip() == '':
                start_offset += 1
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

    def find_sections(self):
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
            elem  = tool_box.get_next_element(pos, len(self.lines))
            if elem is None:
                break
            pos = elem['match_line']
            pos += 1
            if elem['match_type'] != MatcherType.heading:
                continue
            stars =  elem['matched_contents']['stars']
            level = len(stars)
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
        self.find_sections()
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
            if index == 0:
                if self.doc_properties is not None:
                    if "ID" in self.doc_properties:
                        raw = self.doc_properties['ID']
                        self.logger.debug("adding link targeet for doc properties id %s", raw.lstrip())
                        self.root.add_link_target(section.tree_node, raw.lstrip())
            self.pop_parser(section)
            index += 1
        self.branch.note_parse_done()
        return self.branch

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
                    prop_dict[name] = value.lstrip()
                self.logger.debug("parsed properties %s", pformat(prop_dict))
                return prop_dict
            else:
                msg = f"failed to parse properties starting on line {start}"
                self.logger.warning(msg)
                self.record_parse_problem(msg)
        return None


class ParseTool:

    def __init__(self, doc_parser, start, end, parent_tree_node):
        self.doc_parser = doc_parser
        self.tree_node = None
        self.start = start
        self.end = end
        self.parent_tree_node = parent_tree_node
        self.keywords = None
        self.keyword_name = None
        self.logger = logging.getLogger('roam2doc.parser')
        # these are only used to support whitebox testing techniques
        self.start_callback = None
        self.end_callback = None
        self.match_log_format =  doc_parser.match_log_format
        self.no_match_log_format = doc_parser.no_match_log_format

    def set_callbacks(self, start_cb, end_cb):
        self.start_callback = start_cb
        self.end_callback = end_cb
        
    def set_keywords(self, keywords):
        if len(keywords) == 0:
            return
        self.keywords = keywords
        for w in keywords:
            name_key_start = "#+NAME:"
            if w.upper().startswith(name_key_start):
                endpart = w[len(name_key_start):].strip()
                if endpart != '':
                    self.keyword_name = endpart
            
    def get_parent_parser(self):
        # can't do this during init, not added to doc parser yet
        return self.doc_parser.get_parser_parent(self)
    
    def get_section_parser(self):
        if isinstance(self, SectionParse):
            return self
        par = self.doc_parser.get_parser_parent(self)
        while par is not None and not isinstance(par, SectionParse):
            par = self.doc_parser.get_parser_parent(par)
        return par

class SectionParse(ParseTool):

    def __init__(self, doc_parser, start, end, parent_tree_node=None):
        self.start = start
        self.end = end
        self.level = 0
        self.heading_text = None
        self.properties = None
        if parent_tree_node is None:
            parent_tree_node = doc_parser.branch
        super().__init__(doc_parser, start, end, parent_tree_node)

    def calc_level(self):
        first_line = self.doc_parser.lines[self.start].lstrip()
        tool_box = ToolBox(self.doc_parser)
        matcher = tool_box.get_matcher(MatcherType.heading)
        heading_match = matcher.match_line(first_line)
        if heading_match:
            self.level = len(heading_match['groupdict']['stars'])
            self.heading_text = heading_match['groupdict']['heading']
            return True
        # We don't have an actual heading, just start of file.
        # We need to figure out some kind of text for a heading, cause
        # that is how we roll.
        # The doc_parser may have stored zeroth section
        # properties and or title, so check for that.
        if self.doc_parser.doc_title is not None:
            self.heading_text = self.doc_parser.doc_title
        else:
            self.heading_text = f"Start of {self.doc_parser.source}"
        self.level = 1
        return False

    def parse(self):
        if self.start_callback:
            self.start_callback(self)
        found_heading = self.calc_level()
        pos = self.start
        if found_heading:
            pos += 1
        self.tree_node = Section(self.parent_tree_node, self.start, self.end)
        heading = Heading(self.tree_node, self.start, self.start, self.level, self.heading_text)
        tool_box = ToolBox(self.doc_parser)
        objects = tool_box.get_text_and_object_nodes_in_line(heading, self.heading_text, pos-1)
        if self.end == self.start:
            self.logger.debug("Header %s has no following section contents", str(self))
            return self.end
        self.properties = self.doc_parser.parse_properties(pos, self.end)
        short_id = f"Section@{self.start}"
        if self.properties:
            self.logger.debug("%s has properties %s", short_id, pformat(self.properties))
            pos += len(self.properties) + 2
            if "ID" in self.properties:
                self.doc_parser.root.add_link_target(self.tree_node, self.properties['ID'])
        # now find all greater elements
        last_sub_start = pos - 1
        last_sub_end = pos - 1
        gep = GreaterElementParse(self.doc_parser, pos, self.end, self.tree_node)
        self.doc_parser.push_parser(gep)
        gep.parse()
        self.doc_parser.pop_parser(gep)
        if self.end_callback:
            self.end_callback(self)
        return self.end

    def __str__(self):
        msg = f"Level {self.level} "
        if self.heading_text:
            msg += self.heading_text
        return msg

class TableParse(ParseTool):

    def __init__(self, doc_parser, start, end, parent_tree_node):
        super().__init__(doc_parser, start, end, parent_tree_node)
        
    def parse(self):
        if self.start_callback:
            self.start_callback(self)
        self.tree_node = table = Table(self.parent_tree_node, self.start, self.end)
        if self.keyword_name:
            self.doc_parser.root.add_link_target(table, self.keyword_name)
        tool_box = ToolBox(self.doc_parser)
        matcher = tool_box.get_matcher(MatcherType.table)
        pos = start_pos = self.start
        short_id = f"Table@{start_pos}"
        while pos < self.end + 1:
            for line in self.doc_parser.lines[pos:self.end + 1]:
                next_elem = tool_box.get_next_element(pos, self.end)
                if not next_elem:
                    return pos - 1
                if next_elem['match_type'] != MatcherType.table:
                    return pos - 1
                self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                tr = TableRow(table, pos, pos)
                for item in line.split('|')[1:-1]:
                    cell = TableCell(tr, pos, pos)
                    content_list = tool_box.get_text_and_object_nodes_in_line(self.tree_node,
                                                                              item, pos)
                    self.logger.debug("cell %s", item)
                    for citem in content_list:
                        citem.move_to_parent(cell)
                pos += 1
        if self.end_callback:
            self.end_callback(self)
        return self.end

class GreaterElementParse(ParseTool):
    
    def __init__(self, doc_parser, start, end, parent_tree_node):
        super().__init__(doc_parser, start, end, parent_tree_node)

    def parse(self):
        if self.start_callback:
            self.start_callback(self)
        pos = self.start
        end = self.end
        self.short_id = fr"GenELem\@{pos}"
        self.logger.info(self.match_log_format, self.short_id, "", "parsing starting")
        last_sub_start = pos - 1
        last_sub_end = pos - 1
        tool_box = ToolBox(self.doc_parser)
        self.tree_node = self.parent_tree_node
        while pos < end + 1:
            elem  = tool_box.get_next_element(pos, end)
            if elem:
                self.logger.debug('%s found inner element %s at %d', str(self),
                                  elem['match_type'],
                                  elem['match_line'])
                parse_tool = elem['parse_tool']
                match_pos = elem['match_line']
                if match_pos > last_sub_end:
                    para = ParagraphParse(self.doc_parser, last_sub_end + 1, match_pos - 1, self.tree_node)
                    self.doc_parser.push_parser(para)
                    para.parse()
                    self.doc_parser.pop_parser(para)
                if "end_match" in elem:
                    sub_end = elem['end_match']['pos']
                else:
                    sub_end = end
                parser = parse_tool(self.doc_parser, match_pos, sub_end, self.tree_node)
                parser.set_keywords(elem['keywords'])
                self.doc_parser.push_parser(parser)
                sub_start = match_pos
                sub_end = parser.parse()
                self.doc_parser.pop_parser(parser)
                pos = sub_end + 1
                last_sub_start = match_pos
                last_sub_end = sub_end
            else:
                if last_sub_end < self.end:
                    # when we are past
                    self.logger.debug('%s found inner element making new paragraph for %d to %d', str(self),
                                      last_sub_end + 1, self.end)
                    para = ParagraphParse(self.doc_parser, last_sub_end + 1, end, self.tree_node)
                    self.doc_parser.push_parser(para)
                    para.parse()
                    self.doc_parser.pop_parser(para)
                    pos = end + 1
        if self.end_callback:
            self.end_callback(self)
        return end

class WrappedGEParse(GreaterElementParse):
    tree_class = None

    def parse(self):
        if self.start_callback:
            self.start_callback(self)
        # want to strip the wrapper lines
        wrap_start = self.start
        wrap_end = self.end
        elem_start = wrap_start + 1
        elem_end = wrap_end - 1
        self.start = elem_start
        self.end = elem_end
        parent_node = self.parent_tree_node
        self.parent_tree_node = self.tree_class(parent_node, elem_start, elem_end)
        res = super().parse()
        self.parent_tree_node = parent_node 
        self.start = wrap_start
        self.end = wrap_end
        if self.end_callback:
            self.end_callback(self)
        return self.end

class QuoteParse(WrappedGEParse):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree_class = QuoteBlock

class CenterParse(WrappedGEParse):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree_class = CenterBlock

class LesserElementParse(ParseTool):
    
    def __init__(self, doc_parser, start, end, parent_tree_node):
        super().__init__(doc_parser, start, end, parent_tree_node)

    def parse(self):
        if self.start_callback:
            self.start_callback(self)
        # all the supported lesser elements
        # are "wrapped' with #+begin_xxx #+end_xxx
        start = self.start + 1
        end = self.end -1
        my_lines = []
        for line in self.doc_parser.lines[start:end + 1]:
            my_lines.append(line.lstrip().lstrip(','))
        buff = '\n'.join(my_lines)
        tree_node = self.tree_class(self.parent_tree_node, start, end, buff)
        if self.end_callback:
            self.end_callback(self)
        return self.end
    
class ExampleParse(LesserElementParse):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_inside = False
        self.tree_class = ExampleBlock
    
class CodeParse(LesserElementParse):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_inside = True
        self.tree_class = CodeBlock
    
class CommentParse(LesserElementParse):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_inside = False
        self.tree_class = CommentBlock

        
class ExportParse(LesserElementParse):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_inside = False
        self.tree_class = ExportBlock
    
class ListParse(ParseTool):

    def __init__(self, doc_parser, start, end, parent_tree_node):
        super().__init__(doc_parser, start, end, parent_tree_node)
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
        if self.start_callback:
            self.start_callback(self)
        pos = self.start
        end = self.end
        self.short_id = fr"List\@{pos}"
        self.logger.info(self.match_log_format, self.short_id, "List", "parsing starting")
        # To begin, iterate over the lines looking for the end of the outer list
        # that means two blanks, a heading, or end of section
        tool_box = ToolBox(self.doc_parser)
        heading_matcher = tool_box.get_matcher(MatcherType.heading)
        blank_count = 0
        pos += 1
        list_end = self.end
        ends_on_blanks = False
        for line in self.doc_parser.lines[pos:self.end]:
            if heading_matcher.match_line(line):
                list_end = pos
                break
            if line.strip() == '':
                blank_count += 1
                if blank_count >= 2:
                    list_end = pos
                    ends_on_blanks = True
                    break
            else:
                blank_count = 0
            pos += 1
        self.list_start = self.start
        self.list_end = list_end
        self.logger.info(self.match_log_format, self.short_id, "List", f"found end of list at {list_end}")
        # We know we are on the first line of a list, so
        # figure out wnat kind and get our margin
        line = self.doc_parser.lines[self.start]
        first_match_res = self.list_line_get_type(line)
        self.margin = margin = first_match_res['lindent']
        # now look at them all again and see if there are any list items that have
        # an indent greater than ours, that will give us the spaces_per_level value
        spaces_per_level = None
        # a dict of the line matches indexed by line number
        match_records = {}
        
        pos = self.start
        last_match_pos = None
        for line in self.doc_parser.lines[pos:self.list_end + 1]:
            match_res = self.list_line_get_type(line)
            if match_res:
                self.logger.info(self.match_log_format, self.short_id, "List", line)
                match_res['extra_lines'] = []
                match_res['line_index'] = pos
                match_records[pos] = match_res
                if pos == self.start:
                    match_res['prev_input_line'] = -1
                else:
                    match_res['prev_input_line'] = last_match_pos
                match_res['extra_lines'] = []
                last_match_pos = pos
                if match_res['lindent'] > self.margin and spaces_per_level is None:
                    # this line is indented beyond first so we can calc the
                    # indent to level ratio
                    spaces_per_level = match_res['lindent'] - self.margin
            else:
                if last_match_pos is not None:
                    # These lines will be parsed to collect whatever is contained by
                    # the item, since it is a greater element. Fence post issues
                    # here reading the code, self.list_end - 1 skips the last
                    # two blank lines
                    if ends_on_blanks and pos == self.list_end - 1:
                        # don't add the blanks to the cotent of the last item
                        continue
                    match_records[last_match_pos]['extra_lines'].append(pos)
            pos += 1
        if spaces_per_level is not None:
            self.spaces_per_level = spaces_per_level
            self.list_is_flat = False
        else:
            self.list_is_flat = False

        # Now fix the levels
        for line_index,record in match_records.items():
            if self.spaces_per_level is not None and record['lindent'] > self.margin:
                strict = int((record['lindent'] - self.margin) / self.spaces_per_level)
                record['level'] = strict  + 1
                if strict * self.spaces_per_level < record['lindent'] - self.margin:
                    self.logger.warning("improper formatting of list at line %d of %d, moving up to previous level",
                                        record['line_index'], len(self.doc_parser.lines))
            else:
                record['level'] = 1
                             
        # Now that we know everyone's indent level, we can latch the child matches onto the
        # parents so there is no confusion about which item each attaches to
        match_order = list(match_records.keys())
        match_order.sort()
        top_level_records = []
        level_lasts = {}
        list_type = None
        for line_index in match_order:
            rec = match_records[line_index]
            if list_type is None:
                list_type = rec['list_type']
            level = rec['level']
            level_lasts[level] = rec
            if level == 1:
                top_level_records.append(rec)
            else:
                # Be definsive, someone might have skipped a level
                # if the file is bogus. It is to fuzzy a problem
                # to fix, so just shift it left until there is
                # something there
                t_level = level-1
                while t_level > 0 and t_level not in level_lasts:
                    t_level -= 1
                parent_rec = level_lasts[t_level]
                if 'children' not in parent_rec:
                    parent_rec['children'] = []
                if rec not in parent_rec['children']:
                    parent_rec['children'].append(rec)

        the_list = self.do_one_level(self.parent_tree_node, top_level_records)
        if self.keyword_name:
            self.doc_parser.root.add_link_target(the_list, self.keyword_name)
        if ends_on_blanks:
            BlankLine(the_list, self.list_end-1, self.list_end-1)
            BlankLine(the_list, self.list_end, self.list_end)
        if self.end_callback:
            self.end_callback(self)
        return self.list_end

    def do_one_level(self, parent_tree_node, level_records):
        first_rec = level_records[0]
        cur_list = self.to_tree_list(parent_tree_node, first_rec)
        self.logger.debug("%15s @ level %d created %s from '%s'", self.short_id,
                          first_rec['level'], cur_list,
                          first_rec['contents'])
        first_rec['tree_list'] = cur_list
        list_type = first_rec['list_type']
            
        for index, record in enumerate(level_records):
            tree_node = self.to_tree_node(cur_list, record)
            record['tree_node'] = tree_node
            self.logger.debug("%15s @ level %d created %s from '%s'", self.short_id,
                              record['level'], tree_node,
                              record['contents'])
            # for any children, recurse
            if "children" in record and len(record['children']) > 0:
                self.do_one_level(tree_node, record['children'])
        return cur_list

    def to_tree_list(self, parent_tree_item, record):
        list_type = record['list_type']
        margin = record['lindent']
        line = record['line_index']
        # gonna use this for both start and end, and fix end later
        if list_type == ListType.ordered_list:
            the_list = OrderedList(parent_tree_item, line, line, margin=margin)
        elif list_type == ListType.unordered_list:
            the_list = UnorderedList(parent_tree_item, line, line, margin=margin)
        elif list_type == ListType.def_list:
            the_list = DefinitionList(parent_tree_item, line, line, margin=margin)
        return the_list
    
    def to_tree_node(self, the_list, record):
        self.logger.debug('Called to_tree_node with %s, from record %s', str(the_list),
                          record['contents'])
        list_type = record['list_type']
        line = record['line_index']
        tool_box = ToolBox(self.doc_parser)
        if list_type == ListType.ordered_list:
            ordinal = record['bullet'].rstrip(".").rstrip(')')
            item = OrderedListItem(the_list, line, line, ordinal)
            self.parse_item_contents(item, record)
        elif list_type == ListType.unordered_list:
            item = UnorderedListItem(the_list, line, line, None)
            self.parse_item_contents(item, record)
        elif list_type == ListType.def_list:
            title = DefinitionListItemTitle(the_list, line, line, record['tag'])
            desc = DefinitionListItemDescription(the_list, line, line)
            self.parse_item_contents(desc, record)
            item = DefinitionListItem(the_list, line, line, title, desc)
        return item

    def parse_item_contents(self, item, record):
        tool_box = ToolBox(self.doc_parser)
        # this will become bigger once I add parsing for other content such as elements
        content_list = tool_box.get_text_and_object_nodes_in_line(item, record['contents'],
                                                                  record['line_index'])
        if len(record['extra_lines']) > 0:
            xtra = record['extra_lines'] 
            start = xtra[0]
            end = xtra[-1]
            pos = start
            gep = GreaterElementParse(self.doc_parser, start, end, item)
            self.doc_parser.push_parser(gep)
            gep.parse()
            self.doc_parser.pop_parser(gep)
        
    def list_line_get_type(self, line):
        # check def_list first, looks like unordered too
        for bullettype in [ListType.def_list, ListType.ordered_list, ListType.unordered_list]:
            match_res = self.parse_list_item(line, bullettype)
            if match_res:
                return match_res
        return None

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

    def __init__(self, doc_parser, start, end, parent_tree_node):
        super().__init__(doc_parser, start, end, parent_tree_node)
        self.start = start
        self.end = end
        self.logger = logging.getLogger('roam2doc.parser')
        
    def parse(self):
        if self.start_callback:
            self.start_callback(self)
        pos = self.start
        end = self.end
        any = False
        breaking = False
        # skip past any leading blank lines
        while pos < self.end + 1 and not any:
            for line in self.doc_parser.lines[pos:end + 1]:
                if line.strip() == "":
                    BlankLine(self.parent_tree_node, pos, pos)
                    pos += 1
                else:
                    any = True
                    break
        if pos > self.end:
            return
        # find all the paragraphs first
        ranges = []
        start_pos =  pos
        prev_end = start_pos - 1 
        last_was_blank = False
        while pos < self.end + 1:
            for line in self.doc_parser.lines[pos:end + 1]:
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
        tool_box = ToolBox(self.doc_parser)
        index = 0
        self.logger.debug('Adding paragraph to parser %s', self)
        for r_spec in ranges:
            para = Paragraph(self.parent_tree_node, r_spec[0], r_spec[1])
            index += 1
            line_index = r_spec[0]
            for line in self.doc_parser.lines[r_spec[0]:r_spec[1] + 1]:
                if line.startswith("#+"):
                    line_index += 1
                    continue
                if line.startswith(":"):
                    tmp = line.split(':')
                    if len(tmp) > 2:
                        if line.split()[0].endswith(':'):
                            line_index += 1
                            continue
                if line_index == r_spec[1] and line.strip() == '':
                    # we do not include blank that ends a paragraph
                    pass
                elif line_index < r_spec[1] and line.strip() == '':
                    # must be more than one blank after paragraph, we honor that
                    BlankLine(para, line_index, line_index)
                else:
                    items = tool_box.get_text_and_object_nodes_in_line(para, line, line_index)
                line_index += 1
        if self.end_callback:
            self.end_callback(self)
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
    patterns = [re.compile(r'\[\[(?P<pathreg>.+?)?\](?:\[(?P<description>.+?)\])?\]'),]
    
    def __init__(self):
        super().__init__(self.patterns)

class MatchHeading(LineRegexMatch):
    patterns = [re.compile(r'^(?P<stars>\*+)[ \t]*(?P<heading>.*)?'),]

    def __init__(self):
        super().__init__(self.patterns)

    def get_parse_tool(self):
        return SectionParse

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
    
class MatchQuote(LineRegexAndEndMatch):
    patterns = [re.compile(r'^\#\+BEGIN_QUOTE', re.IGNORECASE),]
    end_pattern = re.compile(r'^\#\+END_QUOTE', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

    def get_parse_tool(self):
        return QuoteParse
        
class MatchCenter(LineRegexAndEndMatch):
    patterns = [re.compile(r'^\#\+BEGIN_CENTER', re.IGNORECASE),]
    end_pattern = re.compile(r'^\#\+END_CENTER', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)
    
    def get_parse_tool(self):
        return CenterParse
    
class MatchExample(LineRegexAndEndMatch):
    patterns = [re.compile(r'^\#\+BEGIN_EXAMPLE', re.IGNORECASE),]
    end_pattern = re.compile(r'^\#\+END_EXAMPLE', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

    def get_parse_tool(self):
        return ExampleParse
    

class MatchCode(LineRegexAndEndMatch):
    patterns = [re.compile(r'^\#\+BEGIN_SRC', re.IGNORECASE),]
    end_pattern = re.compile(r'^\#\+END_SRC', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

    def get_parse_tool(self):
        return CodeParse
    
class MatchComment(LineRegexAndEndMatch):
    patterns = [re.compile(r'^\#\+BEGIN_COMMENT', re.IGNORECASE),]
    end_pattern = re.compile(r'^\#\+END_COMMENT', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

    def get_parse_tool(self):
        return CommentParse
    
class MatchExport(LineRegexAndEndMatch):
    patterns = [re.compile(r'^\#\+BEGIN_EXPORT', re.IGNORECASE),]
    end_pattern = re.compile(r'^\#\+END_EXPORT', re.IGNORECASE)

    def __init__(self):
        super().__init__(self.patterns, self.end_pattern)

    def get_parse_tool(self):
        return ExportParse
    

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
    code_block = "CODE_BLOCK"
    comment_block = "COMMENT_BLOCK"
    export_block = "EXPORT_BLOCK"

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
    #image_object = "IMAGE_OBJECT"

    def __str__(self):
        return self.value
    
class ToolBox:
    greater_matchers = {MatcherType.heading: MatchHeading(),
                        MatcherType.table:MatchTable(),
                        MatcherType.alist:MatchList(),
                        MatcherType.quote_block:MatchQuote(),
                        MatcherType.center_block:MatchCenter(),
                        }
    
    # lesser elements
    lesser_matchers = {MatcherType.example_block:MatchExample(),
                       MatcherType.code_block:MatchCode(),
                       MatcherType.comment_block:MatchComment(),
                       MatcherType.export_block:MatchExport(),
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
                       #MatcherType.image_object:ImageObjectMatcher(),
                       }
    @classmethod
    def get_matcher_dict(cls):
        res = dict(cls.greater_matchers)
        res.update(cls.lesser_matchers)
        res.update(cls.object_matchers)
        return res

    @classmethod
    def get_matcher(cls, typename):
        d = cls.get_matcher_dict()
        return d.get(typename, None)

    def __init__(self, doc_parser):
        self.doc_parser = doc_parser
        
    def get_next_element(self, start, end):
        """ See https://orgmode.org/worg/org-syntax.html#Elements. Some
        things covered elsewhere such as the zeroth section, which is detected by the initial parser."""

        
        element_matchers = dict(self.greater_matchers)
        element_matchers.update(self.lesser_matchers)
        pos = start
        logger = logging.getLogger('roam2doc.parser')
        pending_keywords = []
        for line in self.doc_parser.lines[start:end+1]:
            # greater elements
            for match_type, matcher in element_matchers.items():
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
                               end_char=match_res['end'] - 1,
                               keywords=pending_keywords,
                               matched_contents=matched.groupdict())
                    if hasattr(matcher, 'match_end_line') and callable(getattr(matcher, 'match_end_line')):
                        subpos = pos + 1
                        for subline in self.doc_parser.lines[subpos:end+1]:
                            end_matched = matcher.match_end_line(subline)
                            if end_matched:
                                ressub = dict(match_type=match_type,
                                              pos=subpos,
                                              parse_tool=parse_tool,
                                              match_line=subpos,
                                              start_char=end_matched['start'],
                                              end_char=end_matched['end'] - 1,
                                              end_matched_contents=end_matched['groupdict'])
                                res['end_match'] = ressub
                                break
                            subpos += 1
                    return res
            # line unmatched, see if it right format for a keyword
            if line.strip() == '':
                # keywords only apply if no blank lines before element
                pending_keywords = []
            elif line.startswith("#+"):
                pending_keywords.append(line)
            pos += 1
        return None

    def get_text_and_object_nodes_in_line(self, tree_node, line, line_index):
        blocks_by_offset = {}

        matches_per_type = {}
        for match_type, matcher in self.object_matchers.items():
            mres = matcher.match_text(line)
            for m in mres:
                m['source_line'] = line
                m['line_index'] = line_index
            matches_per_type[match_type] = mres

        for match_type in self.object_matchers:
            for mitem in matches_per_type[match_type]:
                mitem['matcher_type'] = match_type
                blocks_by_offset[mitem['start']] = mitem

        # find overlaps. objects can contain other objects, e.g. <<*bold*>>
        items = []
        tmp = list(blocks_by_offset.keys())
        if len(tmp) == 0:
            items.append(Text(tree_node, line_index, line_index, line))
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
                    items.append(Text(tree_node, line_index, line_index, text_chunk,
                                      last_end + 1, pos))
            items.append(self.do_object_parts(item, tree_node, line_index))
            last_end = item['end']

        if last_end  < len(line):
            text_chunk = line[last_end:].strip()
            if text_chunk:
                Text(tree_node, line_index, line_index, text_chunk, last_end, len(line))
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
        
    def do_object_parts(self, item, tree_node, line_index):
        simple_text = None
        if "inner_objects" not in item:
            rejects = [MatcherType.internal_link_object,]
            if item['matcher_type'] not in rejects :
                simple_text = item['matched'].groupdict()['text']
        tree_item = self.add_object_item(tree_node, item, line_index,
                                         item['matched'].start(),
                                         item['matched'].end() -1,
                                         simple_text)
        if "inner_objects" not in item:
            return tree_item
        for in_item in item['inner_objects']:
            self.do_object_parts(in_item, tree_item, line_index)
        return tree_item
        
    def add_object_item(self, tree_node, item, line_index, start_pos, end_pos, simple_text):
        if item['matcher_type'] == MatcherType.bold_object:
            tree_item = BoldText(tree_node, line_index, start_pos, end_pos, simple_text)
        elif item['matcher_type'] == MatcherType.italic_object:
            tree_item = ItalicText(tree_node, line_index, start_pos, end_pos, simple_text)
        elif item['matcher_type'] == MatcherType.underlined_object:
            tree_item = UnderlinedText(tree_node, line_index, start_pos, end_pos, simple_text)
        elif item['matcher_type'] == MatcherType.linethrough_object:
            tree_item = LinethroughText(tree_node, line_index, start_pos, end_pos, simple_text)
        elif item['matcher_type'] == MatcherType.inlinecode_object:
            tree_item = InlineCodeText(tree_node, line_index, start_pos, end_pos, simple_text)
        elif item['matcher_type'] == MatcherType.verbatim_object:
            tree_item = VerbatimText(tree_node, line_index, start_pos, end_pos, simple_text)
        elif item['matcher_type'] == MatcherType.target_object:
            tree_item = TargetText(tree_node, line_index, start_pos, end_pos, simple_text)
        elif item['matcher_type'] == MatcherType.internal_link_object:
            target_text = item['matched'].groupdict()['pathreg']
            desc = item['matched'].groupdict()['description']
            if desc is None:
                desc = target_text
            # have to figure out what kind of link it is
            if "//" in target_text:
                # some kind of uri
                tree_item = Link(tree_node, line_index, start_pos, end_pos, target_text, None)
                items = self.get_text_and_object_nodes_in_line(tree_item, desc, line_index)
            else:
                # Try to make a file path from it and
                # see if there is a file there, which means
                # that it is an image file. If it is not
                # an image file then the user is out of luck
                tree_item = None
                prefix = 'file:'
                if target_text.lower().startswith(prefix):
                    file_part = target_text[len(prefix):]
                else:
                    file_part = target_text
                doc_path = Path(self.doc_parser.root.source).parent
                if file_part.startswith('./'):
                    path = Path(doc_path, file_part[2:])
                else:
                    path = Path(doc_path, file_part)
                path.resolve()
                is_image = False
                if path.exists():
                    proc = subprocess.Popen(['file', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    result,error = proc.communicate()
                    if "image" in str(result):
                        is_image = True
                if is_image:
                    tree_item = Image(tree_node, line_index, line_index, str(path), desc)
                else:
                    # If we can't make it into an image, just assume
                    # it is an internal link, give special treatment
                    tree_item = InternalLink(tree_node, line_index, start_pos, end_pos,
                                             target_text, None)
                    items = self.get_text_and_object_nodes_in_line(tree_item, desc, line_index)
        return tree_item
        
