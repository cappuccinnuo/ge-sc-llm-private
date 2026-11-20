#!/usr/bin/env python3
"""Read-only audit of current Dataset A line G0 vs published author graph.

Run from the repository root *inside the project's Docker image*:
  bash docker/run.sh python /work/repo/audit_mando_line_discrepancy.py

Outputs a JSON report and a console summary in the current benchmark run.
Does not train, edit labels, modify models, or alter existing benchmark files.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from hcg.store.io import read_gpickle
from hcg.verify import is_positive

CATEGORIES = [
    'access_control', 'arithmetic', 'denial_of_service', 'front_running',
    'reentrancy', 'time_manipulation', 'unchecked_low_level_calls',
]


def group_nodes(graph):
    result = defaultdict(list)
    for nid, data in graph.nodes(data=True):
        result[data['source_file']].append(nid)
    return result


def graph_stats(path):
    if not path.exists():
        return {'status': 'missing', 'path': str(path)}
    g = read_gpickle(path)
    return {
        'status': 'present', 'path': str(path),
        'nodes': g.number_of_nodes(), 'edges': g.number_of_edges(),
        'positive_nodes': sum(is_positive(d.get('node_info_vulnerabilities'))
                              for _, d in g.nodes(data=True)),
        'files': len(group_nodes(g)),
        'token_nodes': sum(d.get('token') is not None for _, d in g.nodes(data=True)),
    }


def mean(vals):
    return sum(vals) / len(vals) if vals else None


def evaluate_a_category(run, category, protocols):
    current_root = run / 'hcg' / 'A' / category
    current_path = current_root / 'contract_level.gpickle'
    current_line = current_root / 'line_level.gpickle'
    nodes_path = current_root / 'line_node_ids.json'
    author_path = Path('data/upstream_mando_llm/graph_detection') / (category + '_tree_sitter_cfg_cg_compressed_graphs.gpickle')
    node_dir = Path('data/upstream_mando_llm/node_detection')
    output = {
        'category': category,
        'input_paths': {
            'current_contract': str(current_path), 'current_line': str(current_line),
            'author_contract': str(author_path),
        },
        'author_node_detection_assets': {
            'tree_sitter_cfg': graph_stats(node_dir / (category + '_tree_sitter_cfg_compressed_graphs.gpickle')),
            'cfg_cg': graph_stats(node_dir / (category + '_cfg_cg_compressed_graphs.gpickle')),
        },
        'protocols': {},
    }
    if not all(p.is_file() for p in (current_path, current_line, nodes_path, author_path)):
        output['status'] = 'missing_graph_or_mapping'
        output['missing'] = [str(p) for p in (current_path, current_line, nodes_path, author_path) if not p.is_file()]
        return output

    ours = read_gpickle(current_path)
    author = read_gpickle(author_path)
    line = read_gpickle(current_line)
    line_to_full = json.loads(nodes_path.read_text(encoding='utf8'))
    ours_by_file, author_by_file = group_nodes(ours), group_nodes(author)
    if set(ours_by_file) != set(author_by_file):
        raise AssertionError(f'{category}: current and published source-file populations differ')
    curr_to_author = {}
    current_different, positive_current, positive_author = 0, 0, 0
    token_same = token_different = token_missing = 0
    for filename in sorted(ours_by_file):
        curr_ids, aut_ids = ours_by_file[filename], author_by_file[filename]
        if len(curr_ids) != len(aut_ids):
            raise AssertionError(f'{category} {filename}: node populations differ')
        for a, b in zip(curr_ids, aut_ids):
            ca, cb = ours.nodes[a], author.nodes[b]
            if (ca.get('node_type'), ca.get('code'), ca.get('node_source_code_lines')) != (
                cb.get('node_type'), cb.get('code'), cb.get('node_source_code_lines')):
                raise AssertionError(f'{category} {filename}: node alignment differs')
            curr_to_author[a] = b
            na = is_positive(ca.get('node_info_vulnerabilities'))
            nb = is_positive(cb.get('node_info_vulnerabilities'))
            positive_current += int(na)
            positive_author += int(nb)
            current_different += na != nb
            if 'token' not in ca or 'token' not in cb:
                token_missing += 1
                continue
            tca, tcb = np.asarray(ca['token']), np.asarray(cb['token'])
            if tca.shape == tcb.shape and np.array_equal(tca, tcb):
                token_same += 1
            else:
                token_different += 1

    if len(line_to_full) != line.number_of_nodes() or set(int(n) for n in line) != set(range(len(line_to_full))):
        raise AssertionError(f'{category}: line node ordering is unexpected')
    current_true = {int(n): is_positive(line.nodes[n].get('node_info_vulnerabilities')) for n in line}
    author_true = {int(n): is_positive(author.nodes[curr_to_author[full]].get('node_info_vulnerabilities'))
                   for n, full in enumerate(line_to_full)}
    n_different = sum(current_true[n] != author_true[n] for n in current_true)
    output.update({
        'status': 'ok', 'contract_nodes_current': ours.number_of_nodes(),
        'contract_nodes_author': author.number_of_nodes(), 'line_nodes': line.number_of_nodes(),
        'positive_current': positive_current, 'positive_author': positive_author,
        'different_labels': current_different, 'different_labels_on_line_graph': n_different,
        'token_equal': token_same, 'token_different': token_different, 'token_unavailable': token_missing,
    })
    if len(curr_to_author) != ours.number_of_nodes():
        raise AssertionError('Lost author node matches')

    for protocol in protocols:
        fold_details = []
        for k in range(10):
            folder = run / protocol / f'{category}_line' / f'fold_{k}' / 'G0'
            pred_path, result_path = folder / 'predictions.json', folder / 'result.json'
            if not pred_path.exists() or not result_path.exists():
                fold_details.append({'fold': k, 'status': 'missing_local_predictions_or_result'})
                continue
            predictions = json.loads(pred_path.read_text())['outer_test']
            reference_result = json.loads(result_path.read_text())
            f = {'fold': k, 'status': 'ok', 'n': len(predictions)}
            by_y = [int(author_true[int(p['node'])]) for p in predictions]
            existing_y = [int(p['target']) for p in predictions]
            if any(int(current_true[int(p['node'])]) != t for p, t in zip(predictions, existing_y)):
                raise AssertionError(f'{category} {protocol} fold {k}: prediction truth and graph mismatch')
            f['changed_targets'] = sum(a != b for a, b in zip(by_y, existing_y))
            for checkpoint in ('best', 'last'):
                pred = [int(p[checkpoint]) for p in predictions]
                current_f1 = 100 * f1_score(existing_y, pred, zero_division=0)
                expected_current = reference_result['outer_test'][checkpoint]['buggy_f1']
                if abs(current_f1 - expected_current) > 1e-6:
                    raise AssertionError(f'{category} {protocol} fold{k} {checkpoint}: fold metrics mismatch')
                f[checkpoint] = {
                    'public_truth_f1': round(current_f1, 6),
                    'author_truth_f1': round(100 * f1_score(by_y, pred, zero_division=0), 6),
                }
            fold_details.append(f)
        valid = [f for f in fold_details if f['status'] == 'ok']
        record = {'folds_scored': len(valid), 'details': fold_details}
        if valid:
            for cp in ('best', 'last'):
                record[cp] = {
                    'public_truth_mean': mean([f[cp]['public_truth_f1'] for f in valid]),
                    'author_truth_mean': mean([f[cp]['author_truth_f1'] for f in valid]),
                }
                record[cp]['label_only_delta_author_minus_public'] = (
                    record[cp]['author_truth_mean'] - record[cp]['public_truth_mean'])
        output['protocols'][protocol] = record
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='runs/benchmark/full_20261119')
    parser.add_argument('--categories', nargs='+', default=CATEGORIES)
    parser.add_argument('--protocols', nargs='+', default=['paper', 'grouped'])
    parser.add_argument('--out', default=None, help='where to put diagnostic JSON; default run/audit_line_label_replay.json')
    args = parser.parse_args()
    run = Path(args.run)
    if not run.is_dir():
        raise SystemExit(f'Run directory not found: {run}')
    result = {
        'description': 'Re-score fixed G0 best/last predictions against author-published graph node labels; no retraining',
        'run': str(run),
        'caveat': 'This counterfactual changes only evaluation labels, not the labels used during model training.',
        'categories': [evaluate_a_category(run, c, args.protocols) for c in args.categories],
    }
    dest = Path(args.out) if args.out else run / 'audit_line_label_replay.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('category | labels changed | token mismatches (missing) | paper best public→author | grouped best public→author')
    for r in result['categories']:
        def scores(p):
            d = r.get('protocols', {}).get(p, {})
            cp = d.get('best') or {}
            if not cp:
                return '--'
            return f"{cp['public_truth_mean']:.2f}→{cp['author_truth_mean']:.2f} (Δ{cp['label_only_delta_author_minus_public']:+.2f})"
        print('%s | %s | %s (%s) | %s | %s' % (
            r['category'], r.get('different_labels_on_line_graph', '--'), r.get('token_different', '--'),
            r.get('token_unavailable', '--'), scores('paper'), scores('grouped')))
    print('Saved:', dest)


if __name__ == '__main__':
    main()