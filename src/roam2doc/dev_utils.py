from roam2doc.tree import (Root, Branch, Section, Heading, Text, Paragraph, BlankLine, TargetText,
                         LinkTarget, BoldText, ItalicText,
                         UnderlinedText, LinethroughText, InlineCodeText,
                         MonospaceText, Blockquote, CodeBlock, List,
                         ListItem, OrderedList, OrderedListItem, UnorderedList,
                         UnorderedListItem, DefinitionList, DefinitionListItem,
                         DefinitionListItemTitle, DefinitionListItemDescription,
                         Table, TableRow, TableCell, Link, Image, InternalLink)


def build_tree_1():
    root = Root('foo')
    heading_text = None
    heading_text = "Top Heading"
    top = Section(root.trunk, heading_text=heading_text)
    top_para = Paragraph(top)
    top_text = Text(top_para, "Some beautiful Text")
    target_text = TargetText(top_para, "Target 1") 
    first_blank = BlankLine(top)

    mid = Section(root.trunk, heading_text="Middle Section")
    mid_para_1 = Paragraph(mid)
    mid_text_1 = Text(mid_para_1, "In the meat now.")
    mid_text_2 = Text(mid_para_1, "And cookin.")
    mid_para_2 = Paragraph(mid)
    mid_text_3 = Text(mid_para_2, "Lot to say.")
    mid_text_4 = Text(mid_para_2, "Running on.")
    mid_2 = Section(mid, heading_text="Middle Section Subsection")
    mid_2_para_1 = Paragraph(mid_2)
    mid_2_text_1 = Text(mid_2_para_1, "In Deep!.")
    
    text_section = Section(root.trunk, heading_text="Text Section")
    text_para = Paragraph(text_section)
    btext1 = BoldText(text_para, "Should be bold!")
    BlankLine(text_para)
    itext1 = ItalicText(text_para, "Should be italics!")
    BlankLine(text_para)
    utext1 = UnderlinedText(text_para, "Should be underlined!")
    BlankLine(text_para)
    lttext1 = LinethroughText(text_para, "Should be strike through!")
    BlankLine(text_para)
    monottext1 = MonospaceText(text_para, "Should be monospace!")
    BlankLine(text_para)
    
    incode = InlineCodeText(text_para, "Should be inline code.")
    BlankLine(text_para)
    text_text_1 = Text(text_para, "That's all folks.")

    blocks_section = Section(root.trunk, heading_text="Blocks Section")
    code = "Should be code monospace with pre-format preserved\n\n"
    code += "def perfect_function():\n"
    code += "    return 'perfect\n"
    codeblock = CodeBlock(blocks_section, code)

    block_quote = Blockquote(blocks_section, cite="https://foo.org")
    bq_text = Text(block_quote, 'Should be in block quote')

    olist_section = Section(root.trunk, heading_text="OrderedList Section")
    olist1 = OrderedList(olist_section)
    bits = [Text(root, "List 1 item o-1"),]
    oli1 = OrderedListItem(olist1, 1, bits)
    bits = [Text(root, "List 1 item o-2"),]
    oli2 = OrderedListItem(olist1, 1, bits)
    olist2 = List(oli2)
    bits = [Text(root, "List 1 item o-2-a"),]
    oli2a = OrderedListItem(olist2, 2, bits)
    olist3 = List(oli2a)
    bits = [Text(root, "List 1 item o-2-a-1"),]
    oli2a1 = OrderedListItem(olist3, 3, bits)

    ulist_section = Section(root.trunk, heading_text="UnorderedList Section")
    ulist1 = UnorderedList(ulist_section)
    bits = [Text(root, "List 1 item u-1"),]
    uli1 = UnorderedListItem(ulist1, 1, bits)
    bits = [Text(root, "List 1 item u-2"),]
    uli2 = UnorderedListItem(ulist1, 1, bits)
    ulist2 = UnorderedList(uli2)
    bits = [Text(root, "List 1 item u-2-a"),]
    uli2a = UnorderedListItem(ulist2, 2, bits)
    ulist2a = UnorderedList(uli2a)
    bits = [Text(root, "List 1 item u-2-a-1"),]
    uli2a1 = UnorderedListItem(ulist2a, 3, bits)

    dlist_section = Section(root.trunk, heading_text="DictionaryList Section")
    dlist1 = DefinitionList(dlist_section)
    dli1_title = DefinitionListItemTitle(dlist1, "DicTitle1")
    # make a descripion with multiple text items and a TargetText
    # because that could happen!
    bits = [Text(root, "DictDesc1 start "),  TargetText(root, "Target 2"), Text(root, "DictDescEnd")]
    dli1_desc = DefinitionListItemDescription(dlist1, bits)
    dli1_item = DefinitionListItem(dlist1, dli1_title, dli1_desc)

    dli2_title = DefinitionListItemTitle(dlist1, "DicTitleTheSecond")
    # make a descripion with multiple text items and a TargetText
    # because that could happen!
    bits = [Text(root, "What a boring definition."),
            Text(root, "It just goes on and on.")]
    dli2_desc = DefinitionListItemDescription(dlist1, bits)
    dli2_item = DefinitionListItem(dlist1, dli2_title, dli2_desc)
    
    table_section = Section(root.trunk, heading_text="Table Section")
    table1 = Table(table_section)
    t1r1 = TableRow(table1)
    t1r1c1 = TableCell(t1r1, [Text(root, "col 1"),])
    t1r1c2 = TableCell(t1r1, [Text(root, "col 2"),])
    t1r2 = TableRow(table1)
    t1r2c1 = TableCell(t1r2, [Text(root, "value 1"),])
    bits2 = [Text(root, "Value"),  TargetText(root, "Target 3"), Text(root, "2")]
    t1r2c2 = TableCell(t1r2, bits2)

    image_section = Section(root.trunk, heading_text="Image Section")
    image_1 = Image(image_section,
                    "https://fastly.picsum.photos/id/965/200/300.jpg?hmac=16gh0rrQrvUF3RJa52nRdq8hylkBd-pL4Ff9kqsNRDQ",
                    "a pretty picture")
    
    link_section = Section(root.trunk, heading_text="Link Section")
    link_1 = Link(link_section, "https://x.com", "Link to X")
    BlankLine(link_section)
    BlankLine(link_section)
    link_2 = InternalLink(link_section, "Target 1", "Internal link to Target 1")
    BlankLine(link_section)
    BlankLine(link_section)
    link_3 = InternalLink(link_section, "bad target", "Internal link that does not resolve")
    BlankLine(link_section)
    BlankLine(link_section)
    link_4 = InternalLink(link_section, "Text Section", "Internal link to section heading text")
    
    return root
