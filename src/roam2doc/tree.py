import json

class Root:
    """ The base of the tree. The source designates the first source file or buffer parsed to
    produce the tree. Normally this should be a pathlike object, but
    other things are possible.
    """ 
    def __init__(self, source):
        self.source = source
        self.node_id = 0
        # Always exactly one branch as trunk, others attach to it or each other
        self.trunk = Branch(self, source)
        self.link_targets = {}

    def new_node_id(self):
        self.node_id += 1
        return self.node_id

    def add_link_target(self, node, target_id):
        self.link_targets[target_id] = LinkTarget(node, target_id)

    def get_link_target(self, target_id):
        if target_id in self.link_targets:
            return self.link_targets[target_id].target_node
        # could be just a heading text
        return self.find_heading_match(target_id)
        
    def find_heading_match(self, text, level=None):
        if not level:
            level = self.trunk
        # breadth first
        for kid in level.children:
            if isinstance(kid, Section):
                if kid.heading.text == text:
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
            out_lines.append("<html>")
            out_lines.append(" <head>")
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

    def __init__(self, root, source, parent=None):
        self.root = root
        self.node_id = root.new_node_id()
        self.source = source
        if parent is None:
            parent = root
        self.parent = parent # could be attatched to a trunk branch, not the root
        self.children = []

    def find_root(self):
        return self.root
    
    def add_node(self, node):
        if node not in self.children:
            self.children.append(node)

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
    
    def __init__(self, parent, auto_add=True):
        self.parent = parent
        self.root = self.find_root()
        self.node_id = self.root.new_node_id()
        self.link_targets = []
        if auto_add and self.parent != self.root:
            self.parent.add_node(self)

    def find_root(self):
        parent = self.parent
        while parent is not None and not isinstance(parent, Root):
            parent = parent.parent
        if isinstance(parent, Root):
            return parent
        raise Exception("cannot find root!")
    
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
        res = dict(cls=str(self.__class__),
                   props=dict(node_id=self.node_id,
                   link_targets=[lt.to_json_dict() for lt in self.link_targets]))
        return res
        
    def __str__(self):
        msg = f"({self.node_id}) {self.__class__.__name__} "
        index = self.parent.children.index(self)
        msg += f"{index} child of obj {self.parent.node_id}"
        return msg

    def get_css_styles(self):
        return []
    
    
class BlankLine(Node):
    """ This node records the presence of a blank line in the original text. This
    allows format converters to preserve the original vertical separation of text if
    so desired. They often also mark the end of other elements, such as tables, lists,
    etc.
    """
    def __init__(self, parent):
        super().__init__(parent)
    
    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        line1 = " " * indent_level  * 4
        line1 += "<br>"
        return [line1,]
    
class Container(Node):
    """ This node contains one or more other nodes but does not directly contain text."""
    def __init__(self, parent, content=None):
        super().__init__(parent)
        self.children = []
        if content:
            for item in content:
                item.move_to_parent(self)
        
    def add_node(self, node):
        if node not in self.children:
            self.children.append(node)
        
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
    def __init__(self, parent, heading_text):
        super().__init__(parent)
        par = self.parent
        wraps = 0
        while not isinstance(par, Branch):
            if isinstance(par, Section):
                wraps += 1
            par = par.parent
        level = wraps + 1
        self.heading = Heading(parent=self, text=heading_text, level=level)

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
    def __init__(self, parent):
        super().__init__(parent)
        
    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("p", indent_level, self)
        line1 += ">"
        lines.append(line1)
        for node in self.children:
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</p>')
        return lines
        
class Text(Node):
    """ A node that has actual content, meaning text."""

    def __init__(self, parent, text):
        super().__init__(parent)
        self.text = text

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
        
class Heading(Node):
    """ An org heading, meaning it starts with one or more asterisks. Always starts a new
    Section, but not all Sections start with a heading. May have a parent, may not.
    """
    def __init__(self, parent, text, level=1,):
        super().__init__(parent, auto_add=False)
        self.text = text
        self.level = level
        self.properties = {}

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open(f"h{self.level}", indent_level, self)
        line1 += f">{self.text}</h{self.level}>"
        return [line1,]
        
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
    def __init__(self, parent, text):
        super().__init__(parent, text)
        root = self.find_root()
        root.add_link_target(self, text)

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


class TextTag(Text):

    def get_css_styles(self):
        return [dict(name="font-weight", value="bold"),]

    def to_html(self, indent_level):
        indent_level += 1
        padding, line1 = setup_tag_open(f"{self.tag}", indent_level, self)
        line1 += f">{self.text}</{self.tag}>"
        return [line1,]
    
class BoldText(TextTag):
    tag = 'b'
    
class ItalicText(TextTag):
    tag = 'i'

class UnderlinedText(TextTag):
    tag = 'u'

class LinethroughText(TextTag):
    tag = 's'

class InlineCodeText(TextTag):
    tag = '<code>'

    def get_css_styles(self):
        return [dict(name="font-family", value="monospace"),]
    
class VerbatimText(TextTag):
    tag = '<code>'

    def get_css_styles(self):
        return [dict(name="font-family", value="monospace"),]

class Blockquote(Container):


    def __init__(self, parent, cite=None, content=None):
        super().__init__(parent)
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


class List(Container):

    def __init__(self, parent,  margin=None):
        super().__init__(parent)
        self.margin = margin

class ListItem(Container):

    def __init__(self, parent, level=1, line_contents=None):
        super().__init__(parent)
        self.line_contents = []  #index into children of the items on the line, other childen possible
        if line_contents:
            for item in line_contents:
                self.line_contents.append(len(self.line_contents))
                item.move_to_parent(self)
        self.level = level
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
            lines.extend(node.to_html(indent_level))
        lines.append(padding + '</li>')
        return lines

    def to_json_dict(self):
        ## fiddle the resluts around to make it easier to understand
        ## by getting the children last
        superres = super().to_json_dict()
        lres = dict(level=self.level, line_contents=self.line_contents)
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

    def __init__(self, parent, level=1, ordinal=None, line_contents=None):
        super().__init__(parent, level, line_contents)
        self.ordinal = ordinal

    pass

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

    def __init__(self, parent, title, description):
        super().__init__(parent)
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

class DefinitionListItemDescription(Container):

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
        res.append(dict(name="margin-left", value="10em"))
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

    def __init__(self, parent, target_text, display_text=None):
        super().__init__(parent)
        self.children = []
        self.target_text = target_text
        self.display_text = display_text

    def to_html(self, indent_level):
        lines = []
        indent_level += 1
        padding, line1 = setup_tag_open("a", indent_level, self)
        line1 += f' href="{self.target_text}">'
        lines.append(line1)
        if self.display_text:
            lines.append(padding + "   " + self.display_text)
        lines.append(padding + '</a>')
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
            line1 += f'>{self.display_text}</span>'
            line1 += '<span style="color: red; font-style: italic; font-weight: bold;">'
            line1 += " !!! link target not found !!!"
            line1 += "</span>"
            lines.append(line1)
            return lines
        padding, line1 = setup_tag_open("a", indent_level, self)
        if self.display_text:
            display_text = self.display_text
        else:
            display_text = target_text
        line1 += f' href="#obj-{target.node_id}">{display_text}</a>'
        lines.append(line1)
        return lines

    def to_json_dict(self):
        ## fiddle the resluts around to make it easier to understand
        ## by getting the children last
        res = super().to_json_dict()
        target = self.find_target()
        res['props']['target_node'] = str(target)
        return res
        
class Image(Node):
    
    def __init__(self, parent, src_text, alt_text=None):
        super().__init__(parent)
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
    



    
    
