"""Node semantic features for HCG/DFG graphs (NodeSem).

    inputs     task context from hcg + dfg outputs
    text       CODE text per node            facts/   statement facts (AST + DFG evidence)
    context    CTX fields                    static   245-d STATIC vectors
    pipeline   analysis stage and stage functions writing the store (store)
    encode     CodeT5+ CODE/CTX, BGE teacher vectors
    llm/       prompts, cached Qwen2.5-Coder generation, response checks, teacher text
    student    per-fold teacher-vector students
    features   S-series specifications and the carrier; model, init: adapters and initialization
    train      grouped nested CV of configurations on dfg.train
"""
