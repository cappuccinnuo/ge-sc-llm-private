"""Offline CPU acceptance, executable without importing mando modules."""
from collections import OrderedDict
import json
from pathlib import Path
import tempfile
import unittest
from ctx_budget import truncate, render
from encode_ctx import load_fields
from asset_registry import reference, write

class CharacterTokenizer:
    def encode(self,text,add_special_tokens=True):
        return list(text)+([1,2] if add_special_tokens else [])


class BudgetTests(unittest.TestCase):
    def test_unchanged_short_input(self):
        fields=OrderedDict(STMT=["x=1;"],DEF=["x:local:@+0"],USE=["-"])
        text,info=truncate(fields,CharacterTokenizer(),256)
        self.assertEqual(text,render(fields));self.assertEqual(info["stage"],0)

    def test_each_priority_stage_can_complete_budget(self):
        # Oversized components target each stage independently.
        cases=[
            (1,OrderedDict(STMT=["x"],DEF=["-"],USE=["-"],FROM=["a","b"*400])),
            (2,OrderedDict(STMT=["x"],STATE_DECL=["a","b","c","d","e"*400])),
            (3,OrderedDict(STMT=["x"],GUARD=["kind:require","eq:env_state","detail:"+"a"*400])),
            (4,OrderedDict(STMT=["x"],PRE_EXT_CALL=["@-1: "+"a"*400])),
            (5,OrderedDict(STMT=["x"],DEF=["a:local","b:local","c:local","d"+"a"*400+":local"])),
            (6,OrderedDict(STMT=["x"],FUNC=["signature"+"a"*400,"visibility:public","guards:none"])),
            (7,OrderedDict(STMT=["a"*400],DEF=["-"],USE=["-"]))]
        for stage,fields in cases:
            with self.subTest(stage=stage):
                text,info=truncate(fields,CharacterTokenizer(),256)
                self.assertEqual(info["stage"],stage)
                self.assertLessEqual(info["final_tokens"],256)
                for key in fields:self.assertIn("["+key+"]",text)

    def test_single_long_neighbor_triggers_explicit_fallback(self):
        fields=OrderedDict(STMT=["short"],DEF=["-"],USE=["-"],FROM=["@-1: "+"a"*1000])
        text,info=truncate(fields,CharacterTokenizer(),256)
        self.assertEqual(info["stage"],8)
        self.assertIn("FROM",info["fallback_fields"])
        for key in fields:self.assertIn("["+key+"]",text)

    def test_empty_invalid_fields_and_impossible_label_budget(self):
        with self.assertRaises(ValueError):truncate({"STMT":[]},CharacterTokenizer())
        with self.assertRaises(ValueError):truncate({"STMT":["x"],"DEF":["-"],"USE":["-"]},CharacterTokenizer(),1)

    def test_unicode_remains_valid(self):
        text,info=truncate(OrderedDict(STMT=["文字🙂"*300],DEF=["-"],USE=["-"]),CharacterTokenizer(),256)
        self.assertEqual(text.encode().decode(),text)
        self.assertLessEqual(info["final_tokens"],256)

    def test_missing_or_changed_seal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/"ctx_fields.jsonl";path.write_text("{}\n")
            manifest=root/"ctx_fields.manifest.json"
            write(manifest,{"version":"nodesem-ctx-fields-v1"})
            write(root/"ctx_fields.manifest.seal.json",{"manifest":{"path":str(manifest),"sha256":"0"*64}})
            with self.assertRaisesRegex(ValueError,"seal"):load_fields(path)


if __name__=="__main__":unittest.main()
