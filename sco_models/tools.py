import numpy as np
import torch


class EarlyStopping:
    """Early stops the training if validation loss doesn't improve after a given patience."""
    def __init__(self, patience=7, verbose=False, delta=0, path='checkpoint.pt', trace_func=print):
        """
        Args:
            patience (int): How long to wait after last time validation loss improved.
                            Default: 7
            verbose (bool): If True, prints a message for each validation loss improvement. 
                            Default: False
            delta (float): Minimum change in the monitored quantity to qualify as an improvement.
                            Default: 0
            path (str): Path for the checkpoint to be saved to.
                            Default: 'checkpoint.pt'
            trace_func (function): trace print function.
                            Default: print            
        """
        self.patience = patience
        self.verbose = verbose
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        self.val_loss_min = np.Inf
        self.delta = delta
        self.path = path
        self.trace_func = trace_func
        # Best validation loss seen so far, and whether the most recent call was an
        # improvement. The caller reports these; printing them from here would fight
        # with the per-fold progress bar.
        self.best_val_loss = np.Inf
        self.improved = False

    # EARLY STOP FIX (2026-10-08): original threshold-only bookkeeping retained.
    # def __call__(self, val_loss, path=None):
    #     val_loss = float(val_loss)
    #     score = -val_loss
    #     if self.best_score is None:
    #         self.best_score = score
    #         self.best_val_loss = val_loss
    #         self.improved = True
    #     elif score < self.best_score + self.delta:
    #         self.improved = False
    #         self.counter += 1
    #         if self.counter >= self.patience:
    #             self.early_stop = True
    #     else:
    #         self.best_score = score
    #         self.best_val_loss = val_loss
    #         self.improved = True
    #         self.counter = 0
    # EARLY STOP FIX: save selection uses the absolute minimum; patience uses
    # a separate significant-improvement reference (best_score).
    def __call__(self, val_loss, path=None):
        val_loss = float(val_loss)
        if not np.isfinite(val_loss):
            raise ValueError('Early stopping requires a finite validation loss')
        self.improved = val_loss < self.best_val_loss
        if self.improved:
            self.best_val_loss = val_loss
        score = -val_loss
        if self.best_score is None or score > self.best_score + self.delta:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True

    def save_checkpoint(self, val_loss, model, path=None):
        # EARLY STOP FIX: original stop-time-only description retained below.
        # Original: Persist the current weights. Called once per fold at the
        # early-stopping point, not on every improvement; old inf -> x was misleading.
        '''Persist current weights as a raw state_dict.

        Graph/node trainers now call this immediately on each new minimum loss.
        The method still accepts explicit calls from existing loss-only clients.
        '''
        if path:
            self.path = path
        val_loss = float(val_loss)
        if self.verbose:
            self.trace_func(
                f'Saving checkpoint at val loss {val_loss:.6f} '
                f'(best seen {self.best_val_loss:.6f}) -> {self.path}'
            )
        torch.save(model.state_dict(), self.path)
        self.val_loss_min = val_loss
