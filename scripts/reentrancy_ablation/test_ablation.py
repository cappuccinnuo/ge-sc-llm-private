"""Meaningful checks for fold isolation, single-factor variants and gradient intervention."""
import unittest, tempfile, argparse
import numpy as np
import torch
import networkx as nx
from common import *
from run_experiment import StopMonitor, make_model, gradient_hook, initialize, settings

class AblationTests(unittest.TestCase):
    def test_monitor_matches_current_implementation(self):
        from sco_models.tools import EarlyStopping
        original=EarlyStopping(patience=3,delta=.001)
        isolated=StopMonitor(3,.001)
        for loss in [1.,.9,.8995,.8992,.898,.898,.898,.899]:
            original(loss);improved,done=isolated.step(loss)
            self.assertEqual((improved,done,isolated.counter),
                             (original.improved,original.early_stop,original.counter))
    def test_actual_folds_and_single_factor_variants(self):
        prepared=HERE/"artifacts/v1/prepared";m=read_json(prepared/"manifest.json")
        for task,count,k in [("node",71,10),("contract",142,5)]:
            f=read_json(prepared/(task+"_folds.json"));self.assertEqual(len(f["folds"]),k)
            seen=Counter()
            for split in f["folds"]:
                self.assertFalse(set(split["train_files"])&set(split["val_files"]))
                self.assertEqual(len(set(split["train_files"])|set(split["val_files"])),count)
                seen.update(split["val_files"])
            self.assertEqual(set(seen.values()),{1})
        a=m["variants"]["A_author"]["node_stats"]
        allowed={"B_local_labels":{"labels","positive_nodes"},"C_local_relations":{"typed_edges","edge_types"},
                 "D_local_features":{"features"}}
        for name,fields in allowed.items():
            b=m["variants"][name]["node_stats"]
            for key in a:
                if key not in fields:self.assertEqual(a[key],b[key],(name,key))
        self.assertEqual(m["variants"]["B_local_labels"]["node_stats"]["positive_nodes"],6976)
    def test_gradient_switch_changes_only_autograd(self):
        g=nx.MultiDiGraph()
        for n in range(4):
            g.add_node(n,node_type="expression_statement",source_file="a.sol" if n<2 else "b.sol",
                       code="x",token=np.arange(512,dtype=np.float32)/(n+1),
                       node_info_vulnerabilities=None)
        g.add_edge(0,1,edge_type="next");g.add_edge(2,3,edge_type="next")
        scratch=HERE/"artifacts/test_scratch";scratch.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(scratch)) as tmp:
            path=Path(tmp)/"tiny.gpickle";write_graph(g,path)
            model=make_model("contract",path,"cpu");model.eval()
            before=model(["a.sol","b.sol"])[0]
            hook=model.classify.register_forward_pre_hook(gradient_hook)
            detached=model(["a.sol","b.sol"])[0]
            self.assertTrue(torch.equal(before,detached))
            torch.nn.functional.cross_entropy(detached,torch.tensor([0,1])).backward()
            self.assertIsNone(model.adapt_ws[0].weight.grad)
            self.assertIsNotNone(model.classify.weight.grad)
            hook.remove();model.zero_grad()
            torch.nn.functional.cross_entropy(model(["a.sol","b.sol"])[0],torch.tensor([0,1])).backward()
            self.assertIsNotNone(model.adapt_ws[0].weight.grad)
    def test_initialization_shared_between_relation_schemas(self):
        prepared=HERE/"artifacts/v1/prepared"
        scratch=HERE/"artifacts/test_scratch";scratch.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(scratch)) as tmp:
            seed_all(10000);a=make_model("node",prepared/"A_author/node.gpickle","cpu")
            one=initialize(a,"node",prepared,Path(tmp),10000)
            seed_all(10000);b=make_model("node",prepared/"B_local_labels/node.gpickle","cpu")
            two=initialize(b,"node",prepared,Path(tmp),10000)
            seed_all(10000);c=make_model("node",prepared/"C_local_relations/node.gpickle","cpu")
            three=initialize(c,"node",prepared,Path(tmp),10000)
            self.assertEqual(one["actual_hash"],two["actual_hash"])
            self.assertEqual(one["shared_nonrelation_hash"],three["shared_nonrelation_hash"])
            self.assertTrue(three["new_canonical_relations"])

if __name__=="__main__":
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
