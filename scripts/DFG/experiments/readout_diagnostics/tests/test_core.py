import unittest
import torch
from torch import nn
from scripts.DFG.experiments.readout_diagnostics.core import capture_forward,decompose,validate_export,author_node_target

class Layer(nn.Module):
    def forward(self):
        return {"A":torch.tensor([[8.,9.],[1.,2.]]),"B":torch.tensor([[3.,4.]])}

class Model(nn.Module):
    def __init__(self):
        super().__init__();self.gcs=nn.ModuleList([Layer()]);self.classify=nn.Linear(2,2)
        self.total_nodes=3;self.hidden_size=2;self.node_ids_dict={"A":[2,0],"B":[1]}
        self.node_ids_by_filename={"val.sol":[0,1],"train.sol":[2]};self.fail=False
    def forward(self,files):
        by=self.gcs[-1]();h=torch.empty((3,2))
        h[[2,0]]=by["A"];h[[1]]=by["B"]
        if self.fail:raise RuntimeError("synthetic forward failure")
        pool=torch.stack([h[self.node_ids_by_filename[f]].mean(0) for f in files])
        return self.classify(pool),pool

class CoreTests(unittest.TestCase):
    def test_exact_decomposition_and_bias(self):
        h=torch.tensor([[1.,2.],[-3.,4.],[2.,-1.]],dtype=torch.float64)
        w=torch.tensor([[2.,-1.],[1.,3.]],dtype=torch.float64);b=torch.tensor([3.,-2.],dtype=torch.float64)
        z=w.mv(h.mean(0))+b;s,c,local,stats=decompose(h,w,b,z)
        self.assertAlmostEqual(float(c.sum())+stats['bias_margin'],float(z[1]-z[0]),places=12)
        self.assertTrue(torch.equal(c,s/3));self.assertTrue(torch.equal(local,s-5))
    def test_positive_local_evidence_can_coexist_with_negative_graph(self):
        h=torch.tensor([[4.],[-10.],[-10.]])
        w=torch.tensor([[0.],[1.]]);b=torch.zeros(2);z=w.mv(h.mean(0))
        _,_,_,stats=decompose(h,w,b,z)
        self.assertLess(stats['margin'],0);self.assertEqual(stats['positive_local_margin_nodes'],1)
    def test_bad_head_rejected(self):
        with self.assertRaisesRegex(ValueError,'dimensions'):decompose(torch.ones(2,3),torch.ones(3,3),torch.zeros(3),torch.zeros(3))
    def test_nonfinite_rejected(self):
        with self.assertRaisesRegex(ValueError,'Nonfinite'):decompose(torch.tensor([[float('nan')]]),torch.ones(2,1),torch.zeros(2),torch.zeros(2))
    def test_wrong_logits_rejected(self):
        with self.assertRaisesRegex(ValueError,'reconstruction'):decompose(torch.ones(2,1),torch.ones(2,1),torch.zeros(2),torch.tensor([1.,5.]))
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):decompose(torch.ones(0,1),torch.ones(2,1),torch.zeros(2),torch.zeros(2))
    def test_node_order_and_heldout_capture(self):
        m=Model().eval();before={k:v.clone() for k,v in m.state_dict().items()}
        h,p,z,e,replay=capture_forward(m,['val.sol'])
        self.assertTrue(torch.equal(h,torch.tensor([[1.,2.],[3.,4.],[8.,9.]])))
        self.assertTrue(torch.equal(p,torch.tensor([[2.,3.]])));self.assertEqual(z.shape,(1,2));self.assertEqual(e,0)
        self.assertTrue(all(torch.equal(v,before[k]) for k,v in m.state_dict().items()))
        self.assertTrue(all(p.grad is None for p in m.parameters()))
        self.assertEqual(len(m.gcs[-1]._forward_hooks),0);self.assertEqual(len(m.classify._forward_pre_hooks),0)
    def test_hooks_removed_on_exception(self):
        m=Model().eval();m.fail=True
        with self.assertRaisesRegex(RuntimeError,'synthetic'):capture_forward(m,['val.sol'])
        self.assertEqual(len(m.gcs[-1]._forward_hooks),0);self.assertEqual(len(m.classify._forward_pre_hooks),0)
    def test_training_mode_rejected(self):
        with self.assertRaisesRegex(ValueError,'eval'):capture_forward(Model(),['val.sol'])
    def test_bad_node_dictionary_rejected(self):
        m=Model().eval();m.node_ids_dict['A']=[1,0]
        with self.assertRaisesRegex(ValueError,'Duplicate'):capture_forward(m,['val.sol'])
    def test_duplicate_files_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):capture_forward(Model().eval(),['val.sol','val.sol'])
    def test_export_identity_and_label(self):
        row=dict(file='a.sol',target=1,score_role='cv_validation',best=1,last=0,best_positive_probability=.9,last_positive_probability=.4);sources={'a.sol':{'sha256':'123'}}
        self.assertEqual(validate_export(['a.sol'],[row],sources,{'a.sol':1})['a.sol'],row)
        for bad in [[row,row],[dict(row,score_role='test')]]:
            with self.assertRaises(ValueError):validate_export(['a.sol'],bad,sources,{'a.sol':1})
        with self.assertRaises(ValueError):validate_export(['a.sol'],[row],sources,{'a.sol':0})
        with self.assertRaises(ValueError):validate_export(['a.sol'],[row],{}, {'a.sol':1})
    def test_same_backend_head_replay_rejects_changed_logits(self):
        m=Model().eval();original=m.forward
        def corrupt(files):
            z,p=original(files)
            return z+torch.tensor([[0.,1.]]),p
        m.forward=corrupt
        with self.assertRaisesRegex(ValueError,'head replay'):capture_forward(m,['val.sol'])
    def test_roundoff_is_separate_not_assigned_to_nodes(self):
        h=torch.tensor([[.1],[.2]]);w=torch.tensor([[1.],[2.]]);b=torch.tensor([10000.,10000.]);pool=h.mean(0)
        z=torch.nn.functional.linear(pool,w,b)
        _,c,_,stats=decompose(h,w,b,z,pool,z.clone())
        self.assertAlmostEqual(float(c.sum())+stats['bias_margin'],stats['reference_margin'],places=10)
        self.assertGreater(abs(stats['actual_minus_reference_margin']),1e-4)
        self.assertAlmostEqual(stats['pooling_margin_residual']+stats['head_margin_residual'],stats['actual_minus_reference_margin'],places=10)
        self.assertEqual(stats['margin'],float(z.double()[1]-z.double()[0]))
    def test_replay_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'head replay'):
            decompose(torch.ones(2,1),torch.ones(2,1),torch.zeros(2),torch.ones(2),torch.ones(1),torch.zeros(2))
    def test_bad_pool_rejected_even_with_replay(self):
        with self.assertRaisesRegex(ValueError,'mean mismatch'):
            decompose(torch.ones(2,1),torch.ones(2,1),torch.zeros(2),torch.ones(2),torch.zeros(1),torch.ones(2))
    def test_nonfinite_historical_probability_rejected(self):
        row=dict(file='a.sol',target=1,score_role='cv_validation',best=1,last=1,best_positive_probability=.9,last_positive_probability=.8)
        for value in [float('nan'),float('inf'),-0.1,1.1]:
            with self.assertRaisesRegex(ValueError,'probability'):
                validate_export(['a.sol'],[dict(row,best_positive_probability=value)],{'a.sol':{'sha256':'1'}},{'a.sol':1})
    def test_original_author_label_semantics(self):
        self.assertEqual(author_node_target({'node_info_vulnerabilities':None}),0)
        self.assertEqual(author_node_target({'node_info_vulnerabilities':[]}),1)
        self.assertEqual(author_node_target({'node_info_vulnerabilities':[1]}),1)
if __name__=='__main__':unittest.main()
