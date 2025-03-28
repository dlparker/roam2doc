import json
import logging

class Root:
    """ The base of the tree. The source designates the first source file or buffer parsed to
    produce the tree. Normally this should be a pathlike object, but
    other things are possible.
    """ 
    def __init__(self, source):
        self.source = source
        self.node_id = 0
        self.trunk = None
        self.link_targets = {}
        self.css_classes = {}

    def new_node_id(self):
        self.node_id += 1
        return self.node_id

    def add_link_target(self, node, target_id):
        self.link_targets[target_id] = LinkTarget(node, target_id)

    def get_link_target(self, target_id):
        if target_id in self.link_targets:
            return self.link_targets[target_id].target_node
        if target_id.startswith('id:'):
            new_target_id = target_id[3:]
            if new_target_id in self.link_targets:
                return self.link_targets[new_target_id].target_node
        # could be just a heading text
        return self.find_heading_match(target_id)
        
    def find_heading_match(self, text, level=None):
        if not level:
            level = self.trunk
        # breadth first
        for kid in level.children:
            if isinstance(kid, Section):
                if kid.heading.original_text == text:
                    return kid.heading
        for kid in level.children:
            if not hasattr(kid, 'children'):
                continue
            found = self.find_heading_match(text, kid)
            if found:
                return found
        return None
        
    def to_json_dict(self):
        res = dict(cls=str(self.__class__),
                   props=dict(source=self.source,
                   trunk=self.trunk.to_json_dict()))
        return res

    def add_css_class(self, class_spec):
        self.css_classes[class_spec['name']] = class_spec
        
    def to_html(self, wrap=True, make_pretty=True, include_json=False):
        self.css_classes = {}
        indent_level = 0
        lines = []
        lines.extend(self.trunk.to_html(indent_level))
        lines.append("</body>")
        if wrap:
            out_lines = []
            out_lines.append("<!DOCTYPE html>")
            out_lines.append("<html>")
            out_lines.append(" <head>")
            out_lines.append(f'<title>Roam2Doc Output from {str(self.source)}</title>')
            out_lines.append('  <link rel="stylesheet" type="text/css" href="https://gongzhitaao.org/orgcss/org.css"/>')
            out_lines.append("  <style>")
            for class_spec in self.css_classes.values():
                styles = class_spec['styles']
                out_lines.append(f".{class_spec['name']}" + " {")
                for style in styles:
                    out_lines.append(f"   {style['name']}: {style['value']} !important;")
                out_lines.append("}")
            out_lines.append("  </style>")
            if include_json:
                out_lines.append("  <script>")
                obj_tree = json.dumps(self, default=lambda o:o.to_json_dict(), indent=4)
                out_lines.append(f"      var obj_tree = {obj_tree};")
                out_lines.append("  </script>")
            out_lines.append(" </head>")
            out_lines.append("<body>")
            out_lines.extend(lines)
            lines = out_lines
        if make_pretty:
            return "\n".join(lines)
        stripped = []
        for line in lines:
            stripped.append(line.strip())
        return "".join(lines)
    
    def __str__(self):
        return f"root from source {self.source}"
    
class Branch:
    """ For single file parsing, having a root to the tree is enough, but when combining
    files it is useful to be able to completely parse each file and then combine them into
    a bigger tree. So we use the branch concept to make that work. The source designates the
    first file or buffer parsed to produce the tree. Normally this should be a pathlike object.
    """

    def __init__(self, root, source, parser, parent=None):
        self.root = root
        self.parser = parser
        self.source = source
        if parent is None:
            parent = root
        self.parent = parent # could be attatched to a trunk branch, not just the root
        self.node_id = root.new_node_id()
        self.children = []
        self.last_node_id = None
        self.logger = logging.getLogger('roam2doc.tree')

    def find_root(self):
        return self.root
    
    def add_node(self, node):
        if node not in self.children:
            self.children.append(node)
        
    def note_parse_done(self):
        max_id = self.node_id
        if self.children:
            max_id = self.level_max_node_id(self, max_id)
        self.last_node_id = max_id
        self.logger.info("%s node id range is %d to %d",  str(self), self.node_id, max_id)

    def level_max_node_id(self, node, max_id):
        max_id = max(node.node_id, max_id)
        if hasattr(node, "children"):
            for child in node.children:
                max_id = self.level_max_node_id(child, max_id)
        return max_id
    
    def get_css_styles(self): 
        return []
    
    def to_json_dict(self):
        # don't include back links, up the tree
        res = dict(cls=str(self.__class__),
                   props=dict(node_id=self.node_id,
                   source=self.source, nodes=[n.to_json_dict() for n in self.children]))
        return res

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("div", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</div>')
        return lines
    
    def __str__(self):
        return f"(self.node_id) branch from source {self.source}"
    
class Node:
    
    def __init__(self, parent, start_line, end_line):
        self.parent = parent
        self.root = self.find_root()
        self.node_id = self.root.new_node_id()
        assert isinstance(start_line, int)
        self.start_line = start_line
        self.end_line = end_line
        self.link_targets = []
        if self.parent != self.root:
            self.parent.add_node(self)

    def find_root(self):
        parent = self.parent
        while parent is not None and not isinstance(parent, Root):
            parent = parent.parent
        if isinstance(parent, Root):
            return parent
        raise Exception("cannot find root!")
    
    def find_branch(self):
        parent = self.parent
        while parent is not None and not isinstance(parent, Branch):
            parent = parent.parent
        if isinstance(parent, Branch):
            return parent
        raise Exception("cannot find branch!")
    
    def add_link_target(self, target):
        self.link_targets.append(target)

    def move_to_parent(self, parent):
        if self.parent == parent:
            return
        if not isinstance(self.parent, Root):
            try:
                self.parent.children.remove(self)
            except ValueError:
                pass
        self.parent = parent
        self.parent.add_node(self)
        
    def to_json_dict(self):
        # don't include back links, up the tree
        props = dict(node_id=self.node_id,
                     parent_object=self.parent.node_id,
                     start_line=self.start_line, end_line=self.end_line,
                     start_pos=getattr(self, 'start_pos', None),
                     end_pos=getattr(self, 'end_pos', None),
                     link_targets=[lt.to_json_dict() for lt in self.link_targets])
        res = dict(cls=str(self.__class__), props=props)
        return res

    def get_source_data(self):
        data = dict(doc_source=self.find_root().source,
                     start_line=self.start_line, end_line=self.end_line,
                     start_pos=getattr(self, 'start_pos', None),
                     end_pos=getattr(self, 'end_pos', None))

        lines = self.find_branch().parser.lines
        if self.start_line == self.end_line:
            source = lines[self.start_line]
            start_pos = getattr(self, 'start_pos', None)
            end_pos = getattr(self, 'end_pos', None)
            if start_pos is not None and end_pos is not None:
                source = source[start_pos:end_pos+1]
        else:
            source = []
            for line_index in range(self.start_line, self.end_line-1):
                source.append(lines[line_index])
        data['source'] = source
        return data
        
    def __str__(self):
        msg = f"({self.node_id}) {self.__class__.__name__} "
        index = self.parent.children.index(self)
        msg += f"{index}th child of obj {self.parent.node_id}"
        return msg

    def get_css_styles(self):
        return []
    
class BlankLine(Node):
    """ This node records the presence of a blank line in the original text. This
    allows format converters to preserve the original vertical separation of text if
    so desired. They often also mark the end of other elements, such as tables, lists,
    etc.
    """
    def __init__(self, parent, start_line, end_line):
        super().__init__(parent, start_line, end_line)
    
    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        line1 = " " * indent_level  * 4
        #line1 += '<span style="margin-bottom: 1em;"> </span>'
        line1 += '<br>'
        return [line1,]
    
class Container(Node):
    """ This node contains one or more other nodes but does not directly contain text."""

    def __init__(self, parent, start_line, end_line):
        super().__init__(parent, start_line, end_line)
        self.children = []
        
    def add_node(self, node):
        if node not in self.children:
            self.children.append(node)
            node.move_to_parent(self)
        
    def remove_node(self, node):
        try:
            index = self.children.index(node)
            self.children.pop(index)
        except ValueError:
            pass
        
    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("div", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for child in self.children:
            lines.extend(child.to_html(indent_level))
        lines.append(padding + '</div>')
        return lines
    
    def to_json_dict(self):
        # don't include back links, up the tree
        res = super().to_json_dict()
        res['props']['children']  = [c.to_json_dict() for c in self.children]
        return res
    
class Section(Container):
    """ This type of Container starts with a heading, or at the beginning of the file.
    It may have a set of properties from a "drawer". 
    """
    def __init__(self, parent, start, end):
        super().__init__(parent, start, end)
        self.heading = None
        
    def add_node(self, node):
        if isinstance(node, Heading):
            self.heading = node
            return
        super().add_node(node)
            
    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("div", indent_level, self)
        line1 += ">"
        lines.append(line1)
        if self.heading:
            lines.extend(self.heading.to_html(indent_level))
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</div>')
        return lines
    
    def to_json_dict(self):
        if self.heading:
            res = dict(cls=str(self.__class__),
                   props=dict(heading=self.heading.to_json_dict()))
            res['props'].update(super().to_json_dict()['props'])
        else:
            res = super().to_json_dict()
        return res

        
class Paragraph(Container):
    """ A content container that is visually separated from the surrounding content
    but does not start with a header. Cannot be the top level container, so it
    must have a parent.
    """
    def __init__(self, parent, start, end):
        super().__init__(parent, start, end)
        
    def to_html(self, indent_level, zero_top_margin=False):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("p", indent_level, self)
        if zero_top_margin:
            line1 += ' style="margin-top: 0 !important" '
        line1 += ">"
        lines.append(line1)
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</p>')
        return lines
        
class Text(Node):
    """ A node that has actual content, meaning text."""

    def __init__(self, parent, start_line, end_line, text, start_pos=None, end_pos=None):
        super().__init__(parent, start_line, end_line)
        self.text = text
        self.start_pos = start_pos
        self.end_pos = end_pos
        if self.start_line == self.end_line:
            # Sometimes that caller didn't tell us position on line
            # because the parsing code gets pretty contorted when
            # handing nested objects like <<*/foo/*>>
            # but we can work it out
            if self.start_pos is None or self.end_pos is None:
                parser = self.find_branch().parser
                line = parser.lines[self.start_line]
                if text in line: # sanity check
                    self.start_pos = line.index(text)
                    self.end_pos = self.start_pos + len(text)

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("span", indent_level, self)
        line1 += f">{self.text}</span>"
        return [line1,]
    
    def to_json_dict(self):
        res = super().to_json_dict()
        res['props']['text'] = self.text
        return res
        
class Heading(Container):
    """ An org heading, meaning it starts with one or more asterisks. Always starts a new
    Section, but not all Sections start with a heading. May have a parent, may not.
    """
    def __init__(self, parent, start_line, end_line, level, original_text):
        super().__init__(parent, start_line, end_line)
        self.level = level
        # this allows heading to be a link target by text match
        self.original_text = original_text
        self.text = None
        self.properties = {}

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        level = self.level
        if self.level > 6:
            level = 6
        
        padding, line1 = setup_tag_open(f"h{level}", indent_level, self)
        if self.text:
            line1 += f">{self.text}</h{level}>"
            lines.append(line1)
            return lines
        line1 += ">"
        lines.append(line1)
        for child in self.children:
            lines.extend(child.to_html(indent_level))
        lines.append(padding + f"</h{level}>")
        return lines
        
    def to_json_dict(self):
        res = super().to_json_dict()
        res['props']['text'] = self.text
        res['props']['properties'] = self.properties
        res['props']['level'] = self.level
        return res

    def __str__(self):
        msg = f"({self.node_id}) {self.__class__.__name__} "
        msg += f"heading for section {self.parent.node_id}"
        return msg
    
        
class TargetText(Text):
    """ A node that has actual text content, but with special significance because
    it can be the target of a link. This is for the <<link-to-text>> form which
    needs special processing on conversion to other formats. 
    """
    def __init__(self, parent, start_line, start_pos, end_pos, text):
        super().__init__(parent, start_line, start_line, text)
        root = self.find_root()
        root.add_link_target(self, text)
        self.start_pos = start_pos
        self.end_pos = end_pos

class LinkTarget():
    """
    This is used to record the fact that a node has a link-to-text associated with it so that
    it can be the target of a link. It is not a node, but has a reference to the node that
    is the actual target. This is for the various target forms including explicit, including
    the named element form which is implemented in the TargetText class.

    The supported linkable forms include the explicit name form when can proceed
    any element:

    <<link-to-text>>

    Named:

    #+Name: link-to-text
    | col1 | col2 |
    | a    | b    |

    and the custom id form:
    
    * Section Header
    :PROPERTIES:
    :CUSTOM_ID: link-to-text
    :END:
    """
    def __init__(self, target_node, target_text):
        self.target_node = target_node
        self.target_text = target_text
        self.target_node.add_link_target(self)
        
    def to_json_dict(self):
        res = dict(target_node=str(self.target_node), target_text=self.target_text)
        return res


class TextTag(Container):

    def __init__(self, parent, start_line, start_pos, end_pos, simple_text):
        super().__init__(parent, start_line, start_line)
        self.simple_text = simple_text
        self.start_pos = start_pos
        self.end_pos = end_pos
    
    def get_css_styles(self):
        return [dict(name="font-weight", value="bold"),]

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open(f"{self.tag}", indent_level, self)
        if self.simple_text:
            line1 += f">{self.simple_text}</{self.tag}>"
            lines.append(line1)
        else:
            line1 += ">"
            lines.append(line1)
            for node in self.children:
                lines.extend(node.to_html(indent_level))
            lines.append(padding + f'</{self.tag}>')
            
        return lines
    
class BoldText(TextTag):
    tag = 'b'
    
class ItalicText(TextTag):
    tag = 'i'

class UnderlinedText(TextTag):
    tag = 'u'

class LinethroughText(TextTag):
    tag = 's'

class InlineCodeText(TextTag):
    tag = 'code'

    def get_css_styles(self):
        return [dict(name="font-family", value="monospace"),]
    
class VerbatimText(TextTag):
    tag = 'code'

    def get_css_styles(self):
        return [dict(name="font-family", value="monospace"),]

class CenterBlock(Container):
    
    def get_css_styles(self):
        return [dict(name="text-align", value="center"),]
    
class QuoteBlock(Container):

    def __init__(self, parent, start_line, end_line, cite=None, content=None):
        super().__init__(parent, start_line, end_line)
        self.cite = cite
        self.children = []
        if content:
            for item in content:
                item.move_to_parent(self)
        
    
    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("blockquote", indent_level, self)
        if self.cite:
            line1 += f' cite="{self.cite}">'
        else:
            line1 += '>'
            
        lines.append(line1)
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</blockquote>')
        return lines

class CodeBlock(Text):

    def get_css_styles(self):
        return [dict(name="white-space", value="pre-wrap"),
                dict(name="font-family", value="monospace"),]

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("code", indent_level, self)
        line1 += ">"
        lines.append(line1)
        lines.append(self.text)
        lines.append(padding + '</code>')
        return lines

class ExampleBlock(CodeBlock):
    pass


class CommentBlock(CodeBlock):
    pass

class ExportBlock(CodeBlock):
    pass


class List(Container):

    def __init__(self, parent, start_line, end_line,  margin=None):
        super().__init__(parent, start_line, end_line)
        self.margin = margin

class ListItem(Container):

    def __init__(self, parent, start_line, end_line, line_contents=None):
        super().__init__(parent, start_line, end_line)
        self.line_contents = []  #index into children of the items on the line, other childen possible
        if line_contents:
            for item in line_contents:
                self.line_contents.append(len(self.line_contents))
                item.move_to_parent(self)
        # while parsing it is helpful to be able to collect lines that will
        # be processed as paragraph data until the moment for parsing arrives
        self.para_lines = []

    def to_html(self, indent_level):

        add_this = """<ol>
        <li seq="1">Item one</li>
        <li seq="20">Item twenty</li>
        <li seq="300">Item three hundred</li>
        </ol>
        """
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("li", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for node in self.children:
            if isinstance(node, Paragraph):
                lines.extend(node.to_html(indent_level, zero_top_margin=True))
            else:
                lines.extend(node.to_html(indent_level))
        lines.append(padding + '</li>')
        return lines

    def to_json_dict(self):
        ## fiddle the resluts around to make it easier to understand
        ## by getting the children last
        superres = super().to_json_dict()
        lres = dict(line_contents=self.line_contents)
        lres.update(superres['props'])
        res = dict(cls=superres['cls'], props=lres)
        return res
    
class OrderedList(List):

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("ol", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</ol>')
        return lines


class OrderedListItem(ListItem):

    def __init__(self, parent, start_line, end_line, ordinal=None, line_contents=None):
        super().__init__(parent, start_line, end_line, line_contents)
        self.ordinal = ordinal


class UnorderedList(List):

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("ul", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</ul>')
        return lines


class UnorderedListItem(ListItem):
    pass

class DefinitionList(List):

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("dl", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</dl>')
        return lines


class DefinitionListItem(ListItem):

    def __init__(self, parent, start_line, end_line, title, description):
        super().__init__(parent, start_line, end_line)
        # This is pretty ugly, but it is that way
        # because the stuff it is manipulating is optimized
        # for the common case. This is not the common case.
        # Let this be ugly instead of spreading it far and wide
        title.move_to_parent(self)
        description.move_to_parent(self)
        self.children = []
        self.title = title
        self.description = description

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        lines.extend(self.title.to_html(indent_level))
        lines.extend(self.description.to_html(indent_level))
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        return lines

    def to_json_dict(self):
        ## fiddle the resluts around to make it easier to understand
        ## by getting the children last
        superres = super().to_json_dict()
        lres = dict(title=self.title.to_json_dict(),
                    description=self.description.to_json_dict())
        lres.update(superres['props'])
        res = dict(cls=superres['cls'], props=lres)
        return res
    
class DefinitionListItemTitle(Text):

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("dt", indent_level, self)
        line1 += f">{self.text}</dt>"
        lines.append(line1)
        return lines

class DefinitionListItemDescription(ListItem): # use to get contents support

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("dd", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for child in self.children:
            lines.extend(child.to_html(indent_level))
        lines.append(padding + '</dd>')
        return lines

class Table(Container):

    def get_css_styles(self):
        res = []
        res.append(dict(name="table-layout", value="fixed"))
        res.append(dict(name="display", value="inline-block"))
        res.append(dict(name="border", value="1px solid black"))
        return res
    
    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("table", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for child in self.children:
            lines.extend(child.to_html(indent_level))
        lines.append(padding + '</table>')
        return lines

class TableRow(Container):

    def get_css_styles(self):
        res = []
        res.append(dict(name="border", value="1px solid black"))
        return res

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("tr", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for child in self.children:
            lines.extend(child.to_html(indent_level))
        lines.append(padding + '</tr>')
        return lines

class TableCell(Container):

    def get_css_styles(self):
        res = []
        res.append(dict(name="border", value="1px solid black"))
        return res

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("td", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for child in self.children:
            lines.extend(child.to_html(indent_level))
        lines.append(padding + '</td>')
        return lines


class Link(Container):

    def __init__(self, parent, start_line, start_pos, end_pos, target_text, display_text=None):
        super().__init__(parent, start_line, start_line)
        self.children = []
        self.target_text = target_text
        self.display_text = display_text
        self.start_pos = start_pos
        self.end_pos = end_pos

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("a", indent_level, self)
        line1 += f' href="{self.target_text}">'
        if self.display_text:
            line1 += f'{self.display_text}'
        elif len(self.children) > 0:
            for child in self.children:
                for sub in child.to_html(0):
                    line1 += sub
        else:
            line1 += f'{self.target_text}'
        line1 += '</a>'
        lines.append(line1)
        return lines

    def to_json_dict(self):
        ## fiddle the resluts around to make it easier to understand
        ## by getting the children last
        superres = super().to_json_dict()
        lres = dict(target_text=self.target_text, display_text=self.display_text)
        lres.update(superres['props'])
        res = dict(cls=superres['cls'], props=lres)
        return res

class InternalLink(Link):

    def __init__(self, *args, **argv):
        super().__init__(*args, **argv)
        self.target_node = None

    def find_target(self):
        if not self.target_node:
            self.target_node =self.find_root().get_link_target(self.target_text)
        return self.target_node

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        target = self.find_target()
        if not target:
            padding, line1 = setup_tag_open("span", indent_level, self)
            line1 += 'style="color: red; font-style: italic; font-weight: bold;">'
            line1 += f' !!! link target "{self.target_text}" not found !!!'
            line1 += "</span>"
            lines.append(line1)
            return lines
        padding, line1 = setup_tag_open("a", indent_level, self)
        line1 += f' href="#obj-{target.node_id}">'
        if self.display_text:
            display_text = self.display_text
            line1 += f'{display_text}</a>'
        lines.append(line1)
        if len(self.children) > 0:
            for child in self.children:
                lines.extend(child.to_html(indent_level))
            lines.append(padding + '</a>')
        return lines

    def to_json_dict(self):
        ## fiddle the resluts around to make it easier to understand
        ## by getting the children last
        res = super().to_json_dict()
        target = self.find_target()
        res['props']['target_node'] = str(target)
        return res
        
"""
I can't figure out how to deal with image references. They look just like
links to regexp, unless you use the format [[file:./foo.jpg][altvalue]]
and that doesn't work very well if you are converting to html, so I am just
not going to support them unless I can figure out some clever way to
tell the difference.
"""
class Image(Node):
    
    def __init__(self, parent, start_line, end_line, src_text, alt_text=None):
        super().__init__(parent, start_line, end_line)
        self.src_text = src_text
        self.alt_text = alt_text

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("img", indent_level, self)
        line1 += f' src="{self.src_text}"'
        if self.alt_text:
            line1 += f' alt="{self.alt_text}>"'
        line1 += '</img>'
        return [line1,]

    def to_json_dict(self):
        ## fiddle the resluts around to make it easier to understand
        ## by getting the children last
        superres = super().to_json_dict()
        lres = dict(src_text=self.src_text, alt_text=self.alt_text)
        lres.update(superres['props'])
        res = dict(cls=superres['cls'], props=lres)
        return res


def setup_tag_open(tag, indent_level, obj):
    root = obj.find_root()
    padding = " " * indent_level  * 4
    line1 = padding
    line1 += f'<{tag} id="obj-{obj.node_id}" '
    classname = f"org-auto-{obj.__class__.__name__}"
    styles = obj.get_css_styles()
    selector = classname
    if len(styles) > 0:
        root.add_css_class(dict(name=selector, styles=obj.get_css_styles()))
    line1 += f'class="{selector}"'
    return padding, line1
    



    
    
