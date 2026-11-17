# mando — the MANDO-LLM baseline

This package is the upstream MANDO-LLM code this project extends, kept close to the
published version: the HGT models and data utilities (`models/`, formerly `sco_models`),
the tree-sitter CFG/call-graph construction (`graphs/`, formerly `process_graphs`), the
contract- and line-level trainers and single-contract inference. Run them as modules from
the repository root:

```bash
python -m mando.graph_classifier --help    # contract-level (graph) detection
python -m mando.node_classifier --help     # line-level (node) detection
python -m mando.infer --help               # one Solidity file, pretrained assets
```

The rebuilt pipeline (`hcg` → `dfg` → `nodesem` → `edgesem`, see the repository README)
uses `graphs/` to build graphs and `models/` for the HGT; its G0 profile is this baseline
on the rebuilt graphs. The sections below are the upstream README and quickstart; paths
in their commands are relative to the repository root.

## Smart Contract Vulnerabilities
[![python](https://img.shields.io/badge/python-3.7.12-blue)](https://www.python.org/)
[![slither](https://img.shields.io/badge/slither-0.8.0-orange)](https://github.com/crytic/slither)
[![slither](https://img.shields.io/badge/dgl-0.6.1-green)](https://www.dgl.ai/)

## Multi-Level Graph Embeddings
[![GE-SC overview](../assets/MANDO-LLM-full.png)](https://github.com/MANDO-Project/ge-sc-llm)

This repository is an implementation of MANDO-LLM: Heterogeneous Graph Transformers with Large Language Models for Smart Contract Vulnerability Detection.
The source code is the next version of our two previous frameworks [MANDO](https://github.com/MANDO-Project/ge-sc) and [MANDO-HGT](https://github.com/MANDO-Project/ge-sc-transformer).



## How to run the models?

### Quickstart
- We provide a quickstart guide for the refactored direct classifier scripts in [Classifier quickstart](#classifier-quickstart) below.


### Dataset
- We prepared dataset for [experiments](../experiments/ge-sc-data/source_code).

### Pretrained checkpoints and compressed graphs
- We provide our trained weight checkpoints and compressed graphs for training and inference in the [Google Drive](https://drive.google.com/drive/folders/1Ne3ozncJK1Oqaf6hlF_NdQAiS4VgWulx?usp=sharing).
- For hands-on direct script usage after the classifier refactor, see [Classifier quickstart](#classifier-quickstart). The default assets live under `mando-assets/` and use `nodetype` node features.

### System Description

We run all experiments on 
- Ubuntu 20.04
- CUDA 11.1
- NVIDA 3080

### Install Environment

Install python required packages.
```bash
pip install -r requirements.txt
```

### Inspection scripts

We provide inspection scripts for Graph Classification and Node Classification tasks as well as their required data.

#### Graph Classification

Training Phase
```bash
python -m experiments.graph_classification --epochs 50 --repeat 20
```
To show the result table

```bash
python -m experiments.graph_classification --result
```

#### Node Classification

Training Phase
```bash
python -m experiments.node_classification --epochs 50 --repeat 20
```
To show the result table

```bash
python -m experiments.node_classification --result
```

- We currently supported 7 types of the bug: `access_control`, `arithmetic`, `denial_of_service`, `front_running`, `reentrancy`, `time_manipulation`, `unchecked_low_level_calls`.

- Run the inspection 


### Trainer

#### Graph Classification

##### Usage

```bash
usage: MANDO Graph Classifier [-h] [-s SEED] [-ld LOG_DIR]
                              [--output_models OUTPUT_MODELS]
                              [--compressed_graph COMPRESSED_GRAPH]
                              [--dataset DATASET] [--testset TESTSET]
                              [--label LABEL] [--checkpoint CHECKPOINT]
                              [--feature_extractor FEATURE_EXTRACTOR]
                              [--node_feature NODE_FEATURE]
                              [--k_folds K_FOLDS] [--test] [--non_visualize]

optional arguments:
  -h, --help            show this help message and exit
  -s SEED, --seed SEED  Random seed

Storage:
  Directories for util results

  -ld LOG_DIR, --log-dir LOG_DIR
                        Directory for saving training logs and visualization
  --output_models OUTPUT_MODELS
                        Where you want to save your models

Dataset:
  Dataset paths

  --compressed_graph COMPRESSED_GRAPH
                        Compressed graphs of dataset which was extracted by
                        graph helper tools
  --dataset DATASET     Dicrectory of all souce code files which were used to
                        extract the compressed graph
  --testset TESTSET     Dicrectory of all souce code files which is a
                        partition of the dataset for testing
  --label LABEL         Label of sources in source code storage
  --checkpoint CHECKPOINT
                        Checkpoint of trained models

Node feature:
  Define the way to get node features

  --feature_extractor FEATURE_EXTRACTOR
                        If "node_feature" is "GAE" or "LINE" or "Node2vec", we
                        need a extracted features from those models
  --node_feature NODE_FEATURE
                        Kind of node features we want to use, here is one of
                        "nodetype", "metapath2vec", "han", "gae", "line",
                        "node2vec"

Optional configures:
  Advanced options

  --k_folds K_FOLDS     Config for cross validate strategy
  --test                Set true if you only want to run test phase
  --non_visualize       Wheather you want to visualize the metrics
```

##### Examples

- We prepared some scripts for the custom MANDO structures below:

- Graph Classification for Heterogeneous Control Flow Graphs (HCFGs), which detect vulnerabilities at the contract level.
  - GAE as node features.
```bash
python -m mando.graph_classifier -ld ./logs/graph_classification/cfg/gae/access_control --output_models ./models/graph_classification/cfg/gae/access_control --dataset ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/ --compressed_graph ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/cfg_compressed_graphs.gpickle --label ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/graph_labels.json --node_feature gae --feature_extractor ./experiments/ge-sc-data/source_code/gesc_matrices_node_embedding/matrix_gae_dim128_of_core_graph_of_access_control_cfg_clean_57_0.pkl --seed 1
```

- Graph Classification for Heterogeneous Call Graphs (HCGs), which detect vulnerabilities at the contract level.
  - LINE as node features.
```bash
python -m mando.graph_classifier -ld ./logs/graph_classification/cg/line/access_control --output_models ./models/graph_classification/cg/line/access_control --dataset ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/ --compressed_graph ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/cg_compressed_graphs.gpickle --label ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/graph_labels.json --node_feature line --feature_extractor ./experiments/ge-sc-data/source_code/gesc_matrices_node_embedding/matrix_line_dim128_of_core_graph_of_access_control_cg_clean_57_0.pkl --seed 1
```

- Graph Classification for the combination of HCFGs and HCGs which detect vulnerabilities at the contract level.
  - node2vec as node features.
```bash
python -m mando.graph_classifier -ld ./logs/graph_classification/cfg_cg/node2vec/access_control --output_models ./models/graph_classification/cfg_cg/node2vec/access_control --dataset ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/ --compressed_graph ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/cfg_cg_compressed_graphs.gpickle --label ./experiments/ge-sc-data/source_code/access_control/clean_57_buggy_curated_0/graph_labels.json --node_feature node2vec --feature_extractor ./experiments/ge-sc-data/source_code/gesc_matrices_node_embedding/matrix_node2vec_dim128_of_core_graph_of_access_control_cfg_cg_clean_57_0.pkl --seed 1
```

#### Node Classification
- We used node classification tasks to detect vulnerabilities at the line and function levels for Heterogeneous Control-Flow Graphs (HCFGs) and Call Graphs (HCGs) in correspondence.

##### Usage
```bash
usage: MANDO Node Classifier [-h] [-s SEED] [-ld LOG_DIR]
                             [--output_models OUTPUT_MODELS]
                             [--compressed_graph COMPRESSED_GRAPH]
                             [--dataset DATASET] [--testset TESTSET]
                             [--label LABEL]
                             [--feature_compressed_graph FEATURE_COMPRESSED_GRAPH]
                             [--cfg_feature_extractor CFG_FEATURE_EXTRACTOR]
                             [--feature_extractor FEATURE_EXTRACTOR]
                             [--node_feature NODE_FEATURE] [--k_folds K_FOLDS]
                             [--test] [--non_visualize]

optional arguments:
  -h, --help            show this help message and exit
  -s SEED, --seed SEED  Random seed

Storage:
  Directories \for util results

  -ld LOG_DIR, --log-dir LOG_DIR
                        Directory for saving training logs and visualization
  --output_models OUTPUT_MODELS
                        Where you want to save your models

Dataset:
  Dataset paths

  --compressed_graph COMPRESSED_GRAPH
                        Compressed graphs of dataset which was extracted by
                        graph helper tools
  --dataset DATASET     Dicrectory of all souce code files which were used to
                        extract the compressed graph
  --testset TESTSET     Dicrectory of all souce code files which is a
                        partition of the dataset for testing
  --label LABEL

Node feature:
  Define the way to get node features

  --feature_compressed_graph FEATURE_COMPRESSED_GRAPH
                        If "node_feature" is han, you mean use 2 HAN layers.
                        The first one is HAN of CFGs as feature node for the
                        second HAN of call graph, This is the compressed
                        graphs were trained for the first HAN
  --cfg_feature_extractor CFG_FEATURE_EXTRACTOR
                        If "node_feature" is han, feature_extractor is a
                        checkpoint of the first HAN layer
  --feature_extractor FEATURE_EXTRACTOR
                        If "node_feature" is "GAE" or "LINE" or "Node2vec", we
                        need a extracted features from those models
  --node_feature NODE_FEATURE
                        Kind of node features we want to use, here is one of
                        "nodetype", "metapath2vec", "han", "gae", "line",
                        "node2vec"

Optional configures:
  Advanced options

  --k_folds K_FOLDS     Config cross validate strategy
  --test                If true you only want to run test phase
  --non_visualize       Wheather you want to visualize the metrics
```

##### Examples
We prepared some scripts for the custom MANDO structures bellow:

- Node Classification for Heterogeneous Control Flow Graphs (HCFGs), which detect vulnerabilities at the line level.
  - GAE is used as a node feature for detecting access_control bugs.
  ```bash
  python -m mando.node_classifier -ld ./logs/node_classification/cfg/gae/access_control --output_models ./models/node_classification/cfg/gae/access_control --dataset ./experiments/ge-sc-data/source_code/access_control/buggy_curated/ --compressed_graph ./experiments/ge-sc-data/source_code/access_control/buggy_curated/cfg_compressed_graphs.gpickle --node_feature gae --feature_extractor ./experiments/ge-sc-data/source_code/gesc_matrices_node_embedding/matrix_gae_dim128_of_core_graph_of_access_control_cfg_buggy_curated.pkl --testset ./experiments/ge-sc-data/source_code/access_control/curated --seed 1
    ```

- Node Classification for Heterogeneous Call Graphs (HCGs), which detect vulnerabilities at the function level.
- The command lines are the same as CFG except for the dataset. 
  - LINE as node features for detection access_control bugs.
  ```bash
  python -m mando.node_classifier -ld ./logs/node_classification/cg/line/access_control --output_models ./models/node_classification/cg/line/access_control --dataset ./experiments/ge-sc-data/source_code/access_control/buggy_curated --compressed_graph ./experiments/ge-sc-data/source_code/access_control/buggy_curated/cg_compressed_graphs.gpickle --node_feature line --feature_extractor ./experiments/ge-sc-data/source_code/gesc_matrices_node_embedding/matrix_line_dim128_of_core_graph_of_access_control_cg_buggy_curated.pkl --testset ./experiments/ge-sc-data/source_code/access_control/curated --seed 1
  ```

- Node Classification for the combination of HCFGs and HCGs, which detect vulnerabilities at the line level.
  - node2vec as node features.
  ```bash
  python -m mando.node_classifier -ld ./logs/node_classification/cfg_cg/node2vec/access_control --output_models ./models/node_classification/cfg_cg/node2vec/access_control --dataset ./experiments/ge-sc-data/source_code/access_control/buggy_curated --compressed_graph ./experiments/ge-sc-data/source_code/access_control/buggy_curated/cfg_cg_compressed_graphs.gpickle --node_feature node2vec --feature_extractor ./experiments/ge-sc-data/source_code/gesc_matrices_node_embedding/matrix_node2vec_dim128_of_core_graph_of_access_control_cfg_cg_buggy_curated.pkl --testset ./experiments/ge-sc-data/source_code/access_control/curated --seed 1
  ```


- We also stack 2 HAN layers for function-level detection. The first HAN layer is based on HCFGs used as a feature for the second HAN layer based on HCGs (It will be deprecated in a future version).
```bash
python -m mando.node_classifier -ld ./logs/node_classification/call_graph/node2vec_han/access_control --output_models ./models/node_classification/call_graph/node2vec_han/access_control --dataset ./ge-sc-data/node_classification/cg/access_control/buggy_curated --compressed_graph ./ge-sc-data/node_classification/cg/access_control/buggy_curated/compressed_graphs.gpickle --testset ./ge-sc-data/node_classification/cg/curated/access_control --seed 1  --node_feature han --feature_compressed_graph ./data/smartbugs_wild/binary_class_cfg/access_control/buggy_curated/compressed_graphs.gpickle --cfg_feature_extractor ./data/smartbugs_wild/embeddings_buggy_currated_mixed/cfg_mixed/gesc_matrices_node_embedding/matrix_node2vec_dim128_of_core_graph_of_access_control_compressed_graphs.pkl --feature_extractor ./models/node_classification/cfg/node2vec/access_control/han_fold_0.pth
```

### Testing
- We automatically run testing after the training phase for now.

### Visualization
- You also use Tensorboard and take a look at the trend of metrics for both the training phase and the testing phase.

```bash
tensorboard --logdir LOG_DIR
```

### Results

#### Combine HCFGs and HCGs in Form-A Fusion.

##### Coarse-Grained Contract-Level Detection

[![Coarse-Grained CFGs+CGs](../assets/coarse_grained_cfg_cg.png)](https://anonymous.4open.science/r/ge-sc-FE31)

##### Fine-Grained Line-Level Detection

[![Coarse-Grained CFGs+CGs](../assets/fine_grained_cfg_cg.png)](https://anonymous.4open.science/r/ge-sc-FE31)


#### HCFGs only
##### Coarse-Grained Contract-Level Detection

[![CFGs](../assets/coarse_grained_cfg.png)](https://anonymous.4open.science/r/ge-sc-FE31)

#### Combine CFGs and CGs in Form-B Fusion.
##### Fine-Grained Function-Level Detection

[![CGs](../assets/function_level_fusion_form_B.png)](https://anonymous.4open.science/r/ge-sc-FE31)

## Classifier quickstart

This guide is for the refactored direct classifier scripts:

- `python -m mando.graph_classifier ...` for contract-level graph detection.
- `python -m mando.node_classifier ...` for node, line, or function-level detection.


### 1. Prepare The Environment

Use Python 3.7 or later with the CUDA/PyTorch/DGL versions listed in the README.

```bash
pip install -r requirements.txt \
  -f https://download.pytorch.org/whl/lts/1.8/torch_lts.html \
  -f https://data.pyg.org/whl/torch-1.8.0+cu111.html \
  -f https://data.dgl.ai/wheels/repo.html
```

Verify the scripts are visible:

```bash
python -m mando.graph_classifier --help
python -m mando.node_classifier --help
```

### 2. Check The Default Asset Bundle

The default pretrained checkpoints and compressed graphs are expected under `mando-assets/` (link to [download](https://drive.google.com/drive/folders/1Ne3ozncJK1Oqaf6hlF_NdQAiS4VgWulx?usp=drive_link)). These assets use `nodetype` node features, so no external embedding feature file is required.

Expected layout:

```text
mando-assets/
  checkpoints/
    graph_detection/nodetype/
    node_detection/nodetype/
  graphs/
    graph_detection/
    node_detection/
```

Supported vulnerability names:

```text
access_control
arithmetic
denial_of_service
front_running
reentrancy
time_manipulation
unchecked_low_level_calls
```

### 3. Run Graph Classification Inference

#### Batch inference
Choose a vulnerability type and set the matching paths. This example uses `reentrancy`.

```bash
BUG=reentrancy

python -m mando.graph_classifier --test \
  --node_feature nodetype \
  --compressed_graph "mando-assets/graphs/graph_detection/${BUG}_tree_sitter_cfg_cg_compressed_graphs.gpickle" \
  --checkpoint "mando-assets/checkpoints/graph_detection/nodetype/${BUG}_tree_sitter_cfg_cg_hgt.pth" \
  --label "PATH/TO/graph_labels.json" \
  --testset "PATH/TO/test/source_files"
```
python -m mando.graph_classifier --test \
  --node_feature nodetype \
  --compressed_graph "mando-assets/graphs/graph_detection/${BUG}_tree_sitter_cfg_cg_compressed_graphs.gpickle" \
  --checkpoint "mando-assets/checkpoints/graph_detection/nodetype/${BUG}_tree_sitter_cfg_cg_hgt.pth" \
  --label "mando-assets/graphs/graph_detection/${BUG}_graph_labels.json" \
  --testset "experiments/ge-sc-data/source_code/${BUG}/curated"



`--label` should point to the graph label JSON for the contracts being evaluated. `--testset` should point to the Solidity files or split directory used to select the evaluation subset.

#### Expected output
The expected output is the predicted labels of the test set in JSON format.

```json
{
  "contract1.sol": 0,
  "contract2.sol": 1,
  ...
}
```

Where `0` indicates no vulnerability and `1` indicates a vulnerability.


### 4. Run Node Classification Inference

#### Batch inference
For node detection, use the matching node graph and node checkpoint. This example again uses `reentrancy`.

```bash
BUG=reentrancy

python -m mando.node_classifier --test \
  --node_feature nodetype \
  --compressed_graph "mando-assets/graphs/node_detection/${BUG}_tree_sitter_cfg_compressed_graphs.gpickle" \
  --checkpoint "mando-assets/checkpoints/node_detection/nodetype/${BUG}_tree_sitter_cfg_cg_hgt.pth" \
  --testset "PATH/TO/test/source_files"
```

#### Expected output
The expected output is the predicted labels of the test set in JSON format.

```json
{
  "contract1.sol": {
    {'nodeID': 'node1', 'label': 0, 'lines': [1, 2, 3]},
    {'nodeID': 'node2', 'label': 1, 'lines': [4, 5, 6]},
    ...
  },
  "contract2.sol": {
    {'nodeID': 'node1', 'label': 0, 'lines': [7, 8, 9]},
    {'nodeID': 'node2', 'label': 0, 'lines': [10, 11, 12]},
    ...
  },
  ...
}
```

and a summary of the test metrics included:

```text
Buggy nodes in test: 6572/11948 (55.005021760964176%)
Testing on 11948 nodes
Test Micro f1:   0.4746 | Test Macro f1:   0.4559 | Test Accuracy:   0.4746
Classification report
               precision    recall  f1-score   support

           0     0.4487    0.7334    0.5568      5376
           1     0.5467    0.2629    0.3551      6572

    accuracy                         0.4746     11948
   macro avg     0.4977    0.4982    0.4559     11948
weighted avg     0.5026    0.4746    0.4458     11948

Confusion matrix
 [[3943 1433]
 [4844 1728]]
```

Where `0` indicates no vulnerability and `1` indicates a vulnerability.


### 5. Single file inference

Use `python -m mando.infer` when you want to analyze one Solidity source file instead of an existing test split. This mode generates a tree-sitter CFG for the file, loads the tree-sitter node-detection checkpoint for the selected vulnerability type, and runs `HGTVulNodeClassifier.extend_forward` on the generated graph.

```bash
BUG=access_control
SOURCE=experiments/ge-sc-data/source_code/access_control/cleaned_buggy_curated/arbitrary_location_write_simple.sol

python -m mando.infer "$SOURCE" \
  --bug_type "$BUG" \
  --top_k 10 \
  --output_json mando/examples/access_control_inference.json
```

By default, the script resolves assets from:

```text
mando-assets/graphs/node_detection/${BUG}_tree_sitter_cfg_compressed_graphs.gpickle
mando-assets/checkpoints/node_detection/nodetype/${BUG}_tree_sitter_cfg_cg_hgt.pth
```

Override those paths with `--compressed_graph` and `--checkpoint` if you are testing a custom model. The output is node-level: `contract_prediction` is an aggregate that becomes `vulnerable` when at least one generated node is predicted vulnerable. Inspect the ranked `nodes` list for line numbers, node type, source snippet, and vulnerability probability.

Example output is attached at [`mando/examples/access_control_inference.json`](examples/access_control_inference.json).


### 6. Run Direct Training

Training uses the same direct scripts, but omit `--test` and set `--output_models`.

```bash
BUG=reentrancy

python -m mando.graph_classifier \
  --node_feature nodetype \
  --compressed_graph "mando-assets/graphs/graph_detection/${BUG}_cfg_cg_compressed_graphs.gpickle" \
  --label "PATH/TO/graph_labels.json" \
  --output_models "models/graph_detection/nodetype/${BUG}_hgt.pth" \
  --num_epochs 50 \
  --k_folds 5 \
  --seed 1
```

```bash
BUG=reentrancy

python -m mando.node_classifier \
  --node_feature nodetype \
  --compressed_graph "mando-assets/graphs/node_detection/${BUG}_cfg_cg_compressed_graphs.gpickle" \
  --output_models "models/node_detection/nodetype/${BUG}_hgt.pth" \
  --num_epochs 50 \
  --k_folds 5 \
  --seed 1
```

### 7. Common Checks

- Use `--node_feature nodetype` with `mando-assets` defaults.
