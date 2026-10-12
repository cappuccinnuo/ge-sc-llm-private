"""Additional source-projection and category isolation regressions."""
import sys,tempfile,unittest
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import networkx as nx
from build_dataset import node_targets,projection_tokens,token_subsequence

class ProjectionGuardTests(unittest.TestCase):
    def test_projection_keeps_string_spaces_and_identifier_boundaries(self):
        self.assertNotEqual(projection_tokens('return "a b";'),projection_tokens('return "ab";'))
        self.assertFalse(token_subsequence(projection_tokens('call(x);'),projection_tokens('recall(x);')))
        self.assertEqual(projection_tokens(r'return "\x19hello\nworld";'),
                         projection_tokens('return "\x19hello\nworld";'))

    def test_foreign_category_cannot_create_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.sol';p.write_text('uint x;\n')
            with self.assertRaises(ValueError):
                node_targets(nx.MultiDiGraph(),{'a.sol':[{'category':'arithmetic','lines':[1]}]},
                             {'a.sol':p},'reentrancy','author-endpoints')

    def test_pragma_word_in_string_cannot_bypass_source_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.sol';p.write_text('uint x;\n')
            g=nx.MultiDiGraph()
            g.add_node(0,source_file='a.sol',node_type='expression_statement',
                       code='emit Event("pragmasolidity");',
                       label='0_ emit Event\n1-expression_statement-1-1',node_source_code_lines=[1])
            result=node_targets(g,{'a.sol':[{'category':'reentrancy','lines':[1]}]},
                                {'a.sol':p},'reentrancy','author-endpoints')
            self.assertEqual(result[3]['source_projection']['source_projection_mismatches'],1)

if __name__=='__main__':unittest.main()
