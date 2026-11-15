# Upstream MANDO-LLM graph assets

Imported from the user-provided archive
mando-assets-20261115T115052Z-1-001.zip.

The contents of mando-assets/graphs/ are stored directly here:

- graph_detection/: 14 graph files and 7 contract-label JSON files.
- node_detection/: 14 graph files.
- ASSET_MANIFEST.json: the archive SHA-256 and each extracted file's size and SHA-256.

All 35 asset files retain their original archive bytes. Both legacy and
tree_sitter-named graph variants are preserved. This import does not regenerate
graphs, relabel nodes, convert pickle protocols, or change training configuration.
Model checkpoints from the archive remain outside this graph-asset import.

The files are committed as ordinary Git blobs, so a normal clone or pull obtains
the extracted directories directly. Binary .gpickle files are downloaded and
read locally; GitHub does not render their graph contents.
