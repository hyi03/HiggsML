"""Ordered research inputs; mass conditioning is local to this protocol."""
from itertools import combinations

from .errors import ResearchError

GROUPS = {
    "A": tuple(f"lep{i}_pt" for i in range(1, 5)) + tuple(f"lep{i}_eta" for i in range(1, 5)),
    "B": ("mZ1", "mZ2", "deltaR_Z1", "deltaR_Z2"),
    "C": ("pt4l", "deltaPhi_ZZ"),
    "D": ("cos_theta_star", "cos_theta_1", "cos_theta_2", "phi_decay_planes", "phi_production_plane"),
}
ENGINEERED19 = sum(GROUPS.values(), ())
DECAY7 = ("mZ1", "mZ2") + GROUPS["D"]
B_MASS = ("mZ1", "mZ2")
B_GEOMETRY = ("deltaR_Z1", "deltaR_Z2")


def representation_features(name, groups=None):
    if groups is not None:
        chosen = tuple(groups)
        if len(set(chosen)) != len(chosen) or set(chosen) - set(GROUPS):
            raise ResearchError("unknown or repeated feature group")
        if name != "engineered19":
            raise ResearchError("groups require engineered19 representation")
        return sum((GROUPS[g] for g in GROUPS if g in chosen), ()) + ("m4l",)
    options = {"mass-only": ("m4l",), "decay7": DECAY7 + ("m4l",),
               "engineered19": ENGINEERED19 + ("m4l",),
               "lab-extension": DECAY7 + ("pt4l", "y4l", "m4l"),
               "B_mass": B_MASS + ("m4l",), "B_geometry": B_GEOMETRY + ("m4l",)}
    if name not in options:
        raise ResearchError("unsupported research representation")
    return options[name]


def ordered_group_subsets(include_empty=False):
    return tuple(c for size in range(0 if include_empty else 1, 5)
                 for c in combinations(GROUPS, size))


get_feature_names = representation_features
