"""Point tree-sitter at a per-platform grammar build unless the caller already did.

The grammar in process_graphs/tree_sitter_codeviews/build/ is a macOS arm64 binary,
so on a fresh Linux clone every parsing test failed unless TREE_SITTER_LIB_DIR was
exported by hand (the old machine exported <repo>/build/linux-x86_64). An existing
value is never overridden.
"""
from scripts.graph_build.pipeline import use_platform_grammar

use_platform_grammar()
