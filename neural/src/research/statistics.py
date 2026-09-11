"""Sparse physical-group moments with separate observed-bin occupancy.

No dense group-by-bin array is allocated. Only the artifact's required bin
covariance is dense. Instances belong to one call and one event population.
"""
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


class GroupBinStatistics:
    def __init__(self, groups, bins, weights, n_bins):
        self.groups, _ = pd.factorize(np.asarray(groups), sort=True)
        self.bins = np.asarray(bins, dtype=int)
        self.n_groups = int(self.groups.max()) + 1 if len(self.groups) else 0
        self.n_bins = n_bins
        self.reweight(weights)

    def reweight(self, weights):
        weights = np.asarray(weights, dtype=float)
        # pandas uses compensated summation; retain it for within-group sums.
        grouped = pd.DataFrame(dict(group=self.groups, bin=self.bins, w=weights)).groupby(['group','bin']).w.sum()
        row = grouped.index.get_level_values(0).to_numpy()
        col = grouped.index.get_level_values(1).to_numpy()
        shape = (self.n_groups, self.n_bins)
        self.matrix = csr_matrix((grouped.to_numpy(), (row,col)), shape=shape)
        self.occupancy = csr_matrix((np.ones(len(grouped), dtype=np.int64), (row,col)), shape=shape)
        self.row_sums = np.array([
            pd.Series(value).groupby(self.bins).sum().reindex(range(self.n_bins),fill_value=0).to_numpy()
            for value in (np.abs(weights), np.maximum(weights,0), np.minimum(weights,0))])

    def merge(self, projection):
        self.matrix = self.matrix @ projection
        self.occupancy = self.occupancy @ projection
        self.occupancy.data[:] = 1  # union, including groups whose signed sum is zero
        self.row_sums = self.row_sums @ projection
        self.n_bins = projection.shape[1]

    def moments(self):
        covariance = (self.matrix.T @ self.matrix).toarray()
        return (np.asarray(self.matrix.sum(axis=0)).ravel(), covariance,
                *self.row_sums, np.asarray(self.occupancy.sum(axis=0)).ravel())


def mass_merge_projection(n_mass, n_categories, left):
    """Category-major old-to-new map for one adjacent mass merge."""
    old = np.arange(n_mass*n_categories)
    mass = old % n_mass
    new = (old // n_mass)*(n_mass-1) + mass - (mass > left)
    return csr_matrix((np.ones(len(old),dtype=np.int64), (old,new)), shape=(len(old),(n_mass-1)*n_categories))
