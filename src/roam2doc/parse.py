import re
import logging
from pprint import pformat
from roam2doc.tree import (Root, Branch, Section, Heading, Text, Paragraph, BlankLine, TargetText,
                         LinkTarget, BoldText, ItalicText,
                         UnderlinedText, LinethroughText, InlineCodeText,
                         MonospaceText, Blockquote, CodeBlock, List,
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
        self.parser_stack = []
        self.current_section = None
        self.match_log_format =    "%15s %12s matched line %s"
        self.no_match_log_format = "%15s %12s matched line %s"
        self.parse_problems = []

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
        
    def find_section(self, offset=0, include_blank_start=False):
        # look for a non blank line
        lines = self.lines[offset:]
        pos = -1
        start_pos = -1
        # skip any blank lines
        for line in lines:
            pos += 1
            if line.strip() == "":
                if not include_blank_start:
                    # If the first section has not been found yet,
                    # we want to include all the text. This condition
                    # is likely to occur when there are file level
                    # properties or a title and a blank line got
                    # added right after those. It is legal, if meaningless.
                    continue
            start_pos = pos
            break
        if start_pos == - 1:
            return None
        # we have a section start, whether there is a heading or not
        # look for something that starts another section or end of file, skipping
        # the first line which may or may not be a heading
        end_pos = len(lines)  - 1
        pos += 1
        if pos < end_pos + 1:
            # single line file is possible
            subs = lines[pos:]
            for line in subs:
                if MatchHeading().match_line(line):
                    end_pos = pos - 1
                    break
                pos += 1
        return SectionParse(self, start_pos + offset, end_pos + offset)

    def parse(self):
        logger = logging.getLogger('roam2doc-parser')
        sections = []
        result = dict(sections=sections)
        # it is possible that the file starts with a properties block
        lines = self.lines
        start_offset = 0
        properties = self.parse_properties(0, len(lines))
        if properties:
            # need to skip some lines before searching for section
            result['file_properties'] = properties
            self.doc_properties = properties
            # props wrapped in :PROPERTIES:\nprops\n:END:
            start_offset += len(properties) + 2
            logger.info("Found file level properies, setting offset to %s", start_offset)
            logger.debug("File level properies = %s", pformat(properties))
        # might have a #+title: next
        if lines[start_offset].startswith("#+title:"):
            title = ":".join(lines[start_offset].split(":")[1:])
            result['title'] = title
            self.doc_title = title
            start_offset += 1
            logger.info("Found file title, setting offset to %s", start_offset)
            logger.debug("File title = %s", pformat(title))
        section = self.find_section(start_offset, include_blank_start=True)
        logger.info("found section 0 starting lines %d to %d of %d",
                    section.start,
                    section.end,
                    len(lines))
        sections.append(section)
        while section.end < len(lines) - 1:
            section = self.find_section(section.end + 1)
            logger.info("found section %d starting lines %d to %d of %d",
                        len(sections),
                        section.start,
                        section.end,
                        len(lines))
            sections.append(section)

        for section in sections:
            self.current_section = section
            self.push_parser(section)
            section.parse()
            self.pop_parser(section)
        return result

    def parse_properties(self, start, end):
        # :PROPERTIES:
        #  some number of property defs all starting with :
        # :END:
        logger = logging.getLogger('roam2doc-parser')
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
                logger.debug("processing properties in lines %d to %s", start, end)
                # first and last are start and end, only middle ones matter
                prop_dict = {}
                for prop_line in prop_lines[1:-1]:
                    tmp = prop_line.split(':')
                    name = tmp[1]
                    value = ":".join(tmp[2:])
                    prop_dict[name] = value
                logger.debug("parsed properties %s", pformat(prop_dict))
                return prop_dict
            else:
                logger.warning("failed to parse properties starting on line %d", offset)
        return None

class ParseTool:

    def __init__(self, doc_parser, name=None):
        self.doc_parser = doc_parser
        range = doc_parser.get_parse_range()
        self.tree_node = None
        self.start_line = range[0]
        self.end_line = range[1]
        self.name = name
        self.logger = logging.getLogger('roam2doc-parser')
        self.match_log_format =  doc_parser.match_log_format
        self.no_match_log_format = doc_parser.no_match_log_format
    
    def get_section_parser(self):
        if isinstance(self, SectionParse):
            return self
        p = self.doc_parser.get_parser_parent(self)
        while p is not None and not isinstance(p, SectionParse):
            p.self.doc_parser.get_parser_parent(p)
        return p
        

class SectionParse(ParseTool):

    def __init__(self, doc_parser, start, end):
        self.start = start
        self.end = end
        self.cursor = start
        self.level = 0
        self.heading_text = None
        self.properties = None
        super().__init__(doc_parser)

    def calc_level(self):
        first_line = self.doc_parser.lines[self.start].lstrip()
        if first_line.startswith('*'):
            last_star = first_line.lstrip().rfind('*') 
            self.level = last_star + 1
            self.heading_text = first_line[self.level:]
            if self.end == self.start:
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
        self.tree_node = Section(self.doc_parser.branch, self.heading_text)
        self.properties = self.doc_parser.parse_properties(self.cursor, self.end)
        short_id = f"Section@{self.start}"
        if self.properties:
            self.logger.debug("%s has properties %s", short_id, pformat(self.properties))
            self.cursor += len(self.properties) + 2
        line_matchers = [MatchTable(), MatchList()]
        start_pos = self.cursor
        while start_pos < self.end:
            for line in self.doc_parser.lines[start_pos:self.end]:
                # check for simple line start matches first
                matched = False
                for matcher in line_matchers:
                    if matcher.match_line(line):
                        self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                        parse_tool = matcher.get_parse_tool(self.doc_parser)
                        self.doc_parser.push_parser(parse_tool)
                        parse_tool.parse()
                        self.doc_parser.pop_parser(parse_tool)
                        matched = True
                        break
                if matched:
                    break
                else:
                    self.cursor += 1
                    self.logger.debug(self.no_match_log_format, short_id, "nothing", line)
                    # this needs to add content to current paragraph, creating as needed
            start_pos = self.cursor
                    

    def __str__(self):
        msg = f"Level {self.level} "
        if self.heading_text:
            msg += self.heading_text
        return msg

class TableParse(ParseTool):

    def __init__(self, doc_parser, name=None):
        super().__init__(doc_parser, name)
        
    def parse(self):
        matcher = MatchTable()
        sec_p = self.get_section_parser()
        start_pos = sec_p.cursor
        end = sec_p.end
        short_id = f"Table@{start_pos}"
        while start_pos < end:
            for line in self.doc_parser.lines[start_pos:end]:
                if len(line) == 0:
                    continue
                if matcher.match_line(line):
                    self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                    sec_p.cursor += 1
                else:
                    return
            

class ListParse(ParseTool):

    def __init__(self, doc_parser, name=None):
        super().__init__(doc_parser, name)
        self.margin = 0
        self.start_value = None

        UNORDERED_LIST_regex = r'(?P<lindent>\s*)(?P<bullet>[-+*])\s+(?P<counter_set>\[@[a-z\d]+\])?(?:\s*(?P<checkbox>\[(?: |X|x|\+|-)\]))?(?:\s*(?P<contents>.*))?$'
        ORDERED_LIST_regex = r'(?P<lindent>\s*)(?P<bullet>\d+[.)])\s+(?P<counter_set>\[@[a-z\d]+\])?(?:\s*(?P<checkbox>\[(?: |X|x|\+|-)\]))?(?:\s*(?P<contents>.*))?$'
        DEF_LIST_regex = r'(?P<lindent>\s*)(?P<bullet>[-+*])\s+(?P<counter_set>\[@[a-z\d]+\])?(?:\s*(?P<checkbox>\[(?: |X|x|\+|-)\]))?(?:\s*(?P<tag>.*?)(?<!\s)\s*::\s*(?P<contents>.*))?$'

        self.regexps = {
            # Existing regexps...
            'unorderedlist': re.compile(UNORDERED_LIST_regex),
            'orderedlist': re.compile(ORDERED_LIST_regex),
            'deflist': re.compile(DEF_LIST_regex), # definitionlist, but shorter name
        }


    def old_parse(self):
        matcher = MatchList()
        heading_matcher = MatchHeading()
        table_matcher = MatchTable()
        sec_p = self.get_section_parser()
        start_pos = sec_p.cursor
        end = sec_p.end
        short_id = f"List@{start_pos}"
        blank_count = 0
        spaces_per_level = 0
        while start_pos < end:
            for line in self.doc_parser.lines[start_pos:end]:
                # look for end conditions
                if (heading_matcher.match_line(line) 
                    or table_matcher.match_line(line)):
                    return
                if matcher.match_line(line):
                    res = self.old_list_line_get_type(line)
                    if self.list_type != res['list_type']:
                        raise Exception('nested other type lists not done yet')
                    ordinal = res['ordinal']
                    if self.list_type != "def":
                        # calculate level
                        indent = len(line) - len(line.lstrip())
                        if indent == self.margin:
                            level = 1
                        elif spaces_per_level == 0:
                            # this must be the first indent
                            spaces_per_level = indent - self.margin
                            level = 2
                        else:
                            level = int(indent / spaces_per_level) + 1
                    # now figure out what parts are what
                    tmp = line.lstrip().split()
                    bullet = tmp.pop(0)
                    content = None
                    made_sense = True
                    if len(tmp) == 0:
                        content = ""
                    else:
                        while len(tmp) > 0 and made_sense:
                            token = tmp[0]
                            if token.startswith('[@'):
                                # is counter
                                discard = tmp.pop(0)
                                continue
                            if token in ('[ ]', '[X]', '[x]', '[+]'):
                                # is checkbox, maybe we shouldn't skip?
                                discard = tmp.pop(0)
                                continue
                            if self.list_type != "def":
                                content = ' '.join(tmp)
                                break
                            elif len(tmp) >= 2:
                                tag = tmp.pop(0)
                                if tmp[0] != "::":
                                    made_sense = False
                                    break
                                if len(tmp) > 0:
                                    content = ' '.join(tmp)
                                    break
                        if not made_sense:
                            self.logger.warning("could not parse list line %s", line)
                        elif self.list_type == "ordered":
                            content_list = [Text(the_list, content),]
                            item = OrderedListItem(the_list, level, ordinal, content_list)
                        elif self.list_type == "unordered":
                            content_list = [Text(the_list, content),]
                            item = UnorderedListItem(the_list, level, content_list)
                        else:
                            raise Exception('no code for dict lists yet')
                    self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                    sec_p.cursor += 1
                else:
                    if len(line) == 0:
                        sec_p.cursor += 1
                        blank_count += 1
                        BlankLine(self.the_list.children[-1])
                        if blank_count == 2:
                            return
                        continue
                    return


    def parse(self):
        sec_p = self.get_section_parser()
        parent_parser = self.doc_parser.get_parser_parent(self)
        end = sec_p.end
        # we know we are on the first line of a list, so
        # figure out wnat kind and initialize it.
        pos = sec_p.cursor
        short_id = f"List@{pos}"
        line = self.doc_parser.lines[pos]
        matcher = MatchList()
        match_res = self.list_line_get_type(line)
        if match_res is None:
            # we are going to follow the rule of ignoring text that confuses
            # use, just recoring the problem
            problem = dict(description="List parser called with first line that is not a list item",
                           problem_line_pos=pos, problem_line=line)
            self.doc_parser.record_parse_problem(problem)
            breakpoint()
            return
        # This will be the margin for all list items, so the
        # depth calculation needs to subtract this first
        margin = match_res['lindent']
        list_type = match_res['list_type']
        level = 1
        if list_type == 'ordered':
            the_list = OrderedList(parent=parent_parser.tree_node, margin=margin)
            content_list = [Text(the_list, match_res['contents']),]
            ordinal = match_res['bullet'].rstrip(".").rstrip(')')
            item = OrderedListItem(the_list, level, ordinal, content_list)
        elif list_type == 'unordered':
            the_list = UnorderedList(parent=parent_parser.tree_node, margin=margin)
            content_list = [Text(the_list, match_res['contents']),]
            item = UnorderedListItem(the_list, level, content_list)
        elif list_type == 'def':
            the_list = DictionaryList(parent=parent_parser.tree_node, margin=margin)
            title = DictionaryListItemTitle(the_list, match_res['tag'])
            content_list = [Text(the_list, match_res['contents']),]
            desc = DictionaryListItemDescription(the_list, content_list)
            item = DefinitionListItem(the_list, title, desc)
        else:
            desc = "List parser code is buggy, detected a list type but has no code for it"
            problem = dict(description=desc, problem_line_pos=pos, problem_line=line)
            self.doc_parser.record_parse_problem(problem)
            breakpoint()
            return
        self.logger.debug(self.match_log_format, short_id, str(matcher), line)
        self.logger.debug("%15s %12s created item %s", short_id, '', item)
        heading_matcher = MatchHeading()
        table_matcher = MatchTable()
        blank_count = 0
        spaces_per_level = 0
        para_lines = []
        while pos < end:
            for line in self.doc_parser.lines[pos:end]:
                pos += 1
                if (heading_matcher.match_line(line) 
                    or table_matcher.match_line(line)):
                    self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                    if len(para_lines) > 0:
                        self.append_lines_to_item(item, para_lines)
                    return
                if line.strip() == '':
                    sec_p.cursor += 1
                    blank_count += 1
                    if blank_count == 2:
                        if len(para_lines) > 2:
                            self.append_lines_to_item(item, para_lines[:2])
                        BlankLine(item)
                        BlankLine(item)
                        return
                match_res = self.list_line_get_type(line)
                if match_res is None:
                    sec_p.cursor += 1
                    para_lines.append(line)
                    continue
                level = 1
                if spaces_per_level != 0:
                    level = int(match_res['lindent'] / spaces_per_level) + 1
                else:
                    if match_res['lindent'] > margin:
                        # this line is indented beyond first so we can calc the
                        # indent to level ratio
                        spaces_per_level = match_res['lindent'] - self.margin
                        level = int(match_res['lindent'] / spaces_per_level) + 1
                if match_res['list_type'] != list_type:
                    raise Exception('not yet dealing with other list type as content of list item')
                self.logger.debug(self.match_log_format, short_id, str(matcher), line)
                if list_type == 'ordered':
                    content_list = [Text(the_list, match_res['contents']),]
                    ordinal = match_res['bullet'].rstrip(".").rstrip(')')
                    item = OrderedListItem(the_list, level, ordinal, content_list)
                elif list_type == 'unordered':
                    content_list = [Text(the_list, match_res['contents']),]
                    item = UnorderedListItem(the_list, level, content_list)
                elif list_type == 'def':
                    title = DictionaryListItemTitle(the_list, match_res['tag'])
                    content_list = [Text(the_list, match_res['contents']),]
                    desc = DictionaryListItemDescription(the_list, content_list)
                    item = DefinitionListItem(the_list, title, desc)
                last_item = item
                sec_p.cursor += 1
                self.logger.debug("%15s %12s created item %s", short_id, '', item)
        if len(para_lines) > 0:
            self.append_lines_to_item(item, para_lines)
        return
                
    def list_line_get_type(self, line):
        sec_p = self.get_section_parser()
        for bullettype in ['ordered', 'unordered', 'def']:
            match_res = self.parse_list_item(line, bullettype)
            if match_res:
                return match_res
        return None

    def append_lines_to_item(self, item, lines):
        raise Exception('not yet dealing with list item content paragraphs')

    def parse_list_item(self, line, list_type='unordered'):
        """Parse a single list item line and return its components."""
        if list_type == "def":
            pattern = self.regexps['deflist']
        elif list_type == 'ordered':
            pattern = self.regexps['orderedlist']
        else:  # unordered
            pattern = self.regexps['unorderedlist']
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
    
        
class LineRegexMatch:

    def __init__(self, patterns):
        self.patterns = patterns

    def match_line(self, line):
        for re in self.patterns:
            sr = re.match(line)
            if sr:
                return dict(start=sr.start(), end=sr.end(), matched=sr)
        return False

    def get_parse_tool(self, doc_parser, name=None):
        raise NotImplementedError
    
    def __str__(self):
        return self.__class__.__name__

class MatchHeading(LineRegexMatch):
    patterns = [re.compile(r"^\*.*[ \t].*[\s].*$"),]

    def __init__(self):
        super().__init__(self.patterns)

    
class MatchTable(LineRegexMatch):
    patterns = [re.compile(r"^\|[ \t]*"),
                re.compile(r"^\+-.*")]

    def __init__(self):
        super().__init__(self.patterns)

    def get_parse_tool(self, doc_parser, name=None):
        return TableParse(doc_parser, name)
        
class MatchList(LineRegexMatch):
    patterns = [
        # - followed by whitespace
        re.compile(r"[ ]*\-[ \t].*"),
        # + followed by whitespace
        re.compile(r"[ ]*\+[ \t].*"),
        # * not at first char, followed by whitespace
        re.compile(r"^[ ].*\*[ \t]*"),
        # number followed by dot, followed by whitespace
        re.compile(r"^[ ]*\d+\.[ \t].*"),
        # number followed by close paren, followed by whitespace
        re.compile(r"[ ]*\d+\)[ \t].*"),
        ]
    def __init__(self):
        super().__init__(self.patterns)

    def get_parse_tool(self, doc_parser, name=None):
        return ListParse(doc_parser, name)
