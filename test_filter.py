import sys
import os

# Add paths to sys.path
sys.path.append("/home/ahmed/programming-projects/python/rcn-core")
sys.path.append("/home/ahmed/programming-projects/python/pentest-utils")

from pentest_utils.viewers.emacs.match_groups import parse_rule_to_node
from pentest_utils.storage.shared import ComparisonNode

filter_str = "entry['id'].in_([924277511, 669653510, 593181651])"
node = parse_rule_to_node(filter_str)

print(f"Filter: {filter_str}")
print(f"Node type: {type(node)}")
if isinstance(node, ComparisonNode):
    print(f"Field: {node.field_name}")
    print(f"Operator: {node.operator}")
    print(f"Value: {node.value}")
