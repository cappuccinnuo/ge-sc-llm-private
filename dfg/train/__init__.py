"""Training of HGT profiles on DFG-augmented graphs (grouped nested cross-validation).

    splits    duplicate groups and group-disjoint nested folds
    features  anonymized node features (identifier spellings replaced)
    init      family initialization of profiles from one G0 anchor
    trainer   supervision, epoch engine and scoring of one fit
    runner    fold x profile loop of one task, resumable
    report    fold means, paired comparisons with G0, profile selection
"""
