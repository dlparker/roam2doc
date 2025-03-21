#!/usr/bin/env python

from roam2doc.dev_utils import build_tree_1

def big_1():
    root = build_tree_1()
    #print(json.dumps(root, default=lambda o:o.to_json_dict(), indent=4))
    
    print(root.to_html())

big_1()
