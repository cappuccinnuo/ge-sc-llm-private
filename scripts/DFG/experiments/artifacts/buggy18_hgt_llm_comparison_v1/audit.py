"""Read-only comparison of buggy_18 labels; outputs only to this audit folder."""
import ast, csv, hashlib, io, json, subprocess, sys
from pathlib import Path

ROOT = Path('/home/zhao/SmartContract')
LLM = ROOT / 'ge-sc-llm'
HGT = ROOT / 'ge-sc-transformer'
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(LLM))
from scripts.labeling_v2.safe_graph import read_graph
from scripts.line_mapping import build_line_map

def digest(data):
    return hashlib.sha256(data).hexdigest()

def git(*args):
    return subprocess.check_output(['git', '-C', str(HGT)] + list(args))

def literal(value):
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return value

def numbers(value):
    if isinstance(value, int):
        return {value}
    if isinstance(value, (list, tuple)):
        result = set()
        for item in value:
            result.update(numbers(item))
        return result
    raise ValueError('Unexpected coordinate representation: ' + repr(value))

def records(data):
    value = literal(data.get('node_info_vulnerabilities'))
    if value is None:
        return []
    assert isinstance(value, list), repr(value)
    return value

hashes = {
    'reentrancy': '6a9531542e8b053721ad20938bea5c548750153c0b6d8049aeb2cc454b47a483',
    'access_control': '6d40e6ffc59e8109813836229f7b5baa8cbf5f8542fc69f3a8d4a2b0e48980ad',
}
report = {'date': '2026-10-20', 'author': 'Codex',
          'hgt_head': git('rev-parse', 'HEAD').decode().strip(),
          'method': 'HGT original annotations mapped to LLM processed coordinates; same LLM HCG endpoints replay',
          'native_hgt_graph_evaluated': False, 'categories': {}}
inputs = {}
for category, expected_sha in hashes.items():
    base = HGT / 'data/solidifi_buggy_contracts' / category
    provenance = {}
    for name in ('buggy_18.sol', 'BugLog_18.csv', 'vulnerabilities.json'):
        path = base / name
        raw = path.read_bytes()
        tracked = git('show', 'HEAD:' + path.relative_to(HGT).as_posix())
        assert raw == tracked, 'HGT file differs from tracked HEAD: ' + str(path)
        provenance[name] = {'path': str(path), 'sha256': digest(raw), 'equals_head': True}
        inputs[str(path)] = digest(raw)
    raw_source = (base / 'buggy_18.sol').read_bytes()
    source_path = LLM / 'experiments/ge-sc-data/source_code' / category / 'source_files/buggy_18.sol'
    assert source_path.read_bytes() == raw_source
    inputs[str(source_path)] = digest(raw_source)
    solidifi = LLM / 'data/SolidiFI-benchmark/buggy_contracts' / (
        'Re-entrancy' if category == 'reentrancy' else 'tx.origin') / 'buggy_18.sol'
    assert solidifi.read_bytes() == raw_source
    inputs[str(solidifi)] = digest(raw_source)
    source = raw_source.decode('utf8')
    entries = [x for x in json.loads((base / 'vulnerabilities.json').read_text())
               if x['name'] == 'buggy_18.sol']
    assert len(entries) == 1
    hgt_lines = [line for rec in entries[0]['vulnerabilities']
                 if rec['category'] == category for line in rec['lines']]
    original_set = set(hgt_lines)
    rows = list(csv.DictReader(io.StringIO((base / 'BugLog_18.csv').read_text())))
    csv_lines = [line for row in rows for line in
                 range(int(row['loc']), int(row['loc']) + int(row['length']))]
    assert set(csv_lines) == original_set
    line_map = build_line_map(source)
    mapped = {i + 1 for i, origins in enumerate(line_map) if original_set.intersection(origins)}
    graph_path = LLM / 'data/upstream_mando_llm/graph_detection' / (
        category + '_tree_sitter_cfg_cg_compressed_graphs.gpickle')
    actual_sha = digest(graph_path.read_bytes())
    assert actual_sha == expected_sha
    inputs[str(graph_path)] = actual_sha
    graph = read_graph(graph_path)
    nodes = [(n, d) for n, d in graph.nodes(data=True) if d.get('source_file') == 'buggy_18.sol']
    embedded_records = {}
    for n, data in nodes:
        for rec in records(data):
            assert rec['category'] == category
            embedded_records[json.dumps(rec, sort_keys=True)] = rec
    embedded = {line for rec in embedded_records.values() for line in rec['lines']}
    disagreements, self_replay_errors = [], []
    author_positive = hgt_replay_positive = 0
    for n, data in nodes:
        endpoints = numbers(literal(data['node_source_code_lines']))
        author = bool(records(data))
        hgt_replay = bool(endpoints & mapped)
        author_positive += int(author)
        hgt_replay_positive += int(hgt_replay)
        if bool(endpoints & embedded) != author:
            self_replay_errors.append(n)
        if author != hgt_replay:
            disagreements.append({'node_id': n, 'node_type': data['node_type'],
                                  'endpoints': sorted(endpoints), 'author_label': int(author),
                                  'hgt_annotation_same_hcg_endpoint_label': int(hgt_replay)})
    assert not self_replay_errors, 'Author embedded annotation does not reproduce labels'
    out_of_bounds = {x for x in embedded if not 1 <= x <= len(line_map)}
    report['categories'][category] = {
        'hgt_provenance': provenance, 'llm_graph': str(graph_path), 'llm_graph_sha256': actual_sha,
        'source_sha256': digest(raw_source), 'hgt_llm_solidifi_sources_byte_identical': True,
        'original_line_slots_split_newline': len(source.split('\n')), 'processed_lines': len(line_map),
        'csv_records': len(rows), 'csv_expanded_entries': len(csv_lines), 'csv_unique_lines': len(set(csv_lines)),
        'hgt_raw_entries': len(hgt_lines), 'hgt_raw_unique': len(original_set),
        'hgt_equals_csv_set': True, 'hgt_mapped_unique': len(mapped), 'hgt_mapped_lines': sorted(mapped),
        'hgt_original_lines': sorted(original_set),
        'llm_unique_record_count': len(embedded_records), 'llm_embedded_records': list(embedded_records.values()),
        'llm_embedded_unique': len(embedded), 'llm_embedded_lines': sorted(embedded),
        'overlap': sorted(mapped & embedded), 'hgt_only': sorted(mapped - embedded),
        'llm_only': sorted(embedded - mapped), 'llm_out_of_bounds': sorted(out_of_bounds),
        'llm_max_annotation': max(embedded), 'file_graph_nodes': len(nodes),
        'author_positive_nodes': author_positive,
        'hgt_on_same_hcg_endpoint_positive_nodes': hgt_replay_positive,
        'different_node_labels': len(disagreements), 'disagreements': disagreements,
        'author_endpoint_self_replay_errors': self_replay_errors}
    print(category, 'raw/mapped/author:', len(original_set), len(mapped), len(embedded),
          'positive author/replay:', author_positive, hgt_replay_positive,
          'node disagreement:', len(disagreements), 'out_of_bounds:', len(out_of_bounds))
    del graph
assert all(digest(Path(p).read_bytes()) == sha for p, sha in inputs.items())
report['input_hashes_before_equal_after'] = True
report['inputs'] = inputs
report['script_sha256'] = digest(Path(__file__).read_bytes())
with (OUT / 'comparison.json').open('x') as handle:
    json.dump(report, handle, indent=2, ensure_ascii=True)
print('Saved', OUT / 'comparison.json')
