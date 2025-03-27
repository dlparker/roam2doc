import json
import pytest


from construct_tree import build_tree_1

    
def test_everything_1():
    root = build_tree_1()
    #print(root.to_html())
