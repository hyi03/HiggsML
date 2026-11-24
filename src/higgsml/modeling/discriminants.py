"""Variable-input, CPU-only research discriminants; historical models are untouched."""
from __future__ import annotations

import hashlib
import json
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.metrics import roc_auc_score

from higgsml.errors import ResearchError, ResearchStateError
from higgsml.modeling.representations import representation_features
from higgsml.protocol import protocol_dict
from higgsml.adversary import Adversary

TRAINING = dict(max_epochs=200, patience=20, minimum_improvement=1e-4,
                batch_size=1024, learning_rate=1e-3, weight_decay=1e-4,
                warmup_epochs=5, ramp_epochs=10, adversary_bins=11)
CANDIDATES = {'M0c': 'mass-only', 'M2': 'decay7', 'M3': 'engineered19',
              'M3-fixed200': 'engineered19', 'M6': 'engineered19', 'L1': 'lab-extension'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class ResearchClassifier(nn.Module):
    def __init__(self, input_count, first_width=64):
        super().__init__()
        if type(first_width) is not int or first_width < 1:
            raise ResearchError('invalid registered classifier width')
        self.layers = nn.Sequential(
            nn.Linear(input_count, first_width), nn.LayerNorm(first_width, eps=1e-5), nn.SiLU(), nn.Dropout(.1),
            nn.Linear(first_width, 64), nn.LayerNorm(64, eps=1e-5), nn.SiLU(), nn.Dropout(.1),
            nn.Linear(64, 32), nn.LayerNorm(32, eps=1e-5), nn.SiLU(), nn.Linear(32, 1))

    def forward(self, x):
        return self.layers(x).squeeze(-1)


def effective_lambda(epoch, target):
    if not 1 <= epoch <= 200 or not np.isfinite(target) or target < 0:
        raise ResearchError('invalid epoch or lambda')
    return target * min(1., max(0., (epoch - 5) / 10))


def _validate_frame(frame, roles, columns):
    required = {'role', 'event_group_id', 'dataset', 'label', 'physical_weight', *columns}
    if not required <= set(frame):
        raise ResearchError('research frame missing required columns')
    if frame.empty or not set(frame.role) <= set(roles):
        raise ResearchError('forbidden or empty role input')
    if frame.dataset.nunique() != 1 or not set(frame.label) <= {0, 1}:
        raise ResearchError('dataset or class identity invalid')
    if frame.groupby('event_group_id').role.nunique().max() != 1:
        raise ResearchError('event group crosses roles')
    if frame.groupby('event_group_id').label.nunique().max() != 1:
        raise ResearchError('event group has inconsistent labels')
    if not np.isfinite(frame[list(columns) + ['physical_weight']].to_numpy(dtype=float)).all():
        raise ResearchError('nonfinite research input')


def _quantile(values, weights, q):
    order = np.argsort(values, kind='stable')
    v, w = np.asarray(values)[order], np.asarray(weights)[order]
    if w.sum() <= 0:
        raise ResearchStateError('no effective weight', status='insufficient_statistics')
    return v[np.searchsorted(np.cumsum(w), np.asarray(q) * w.sum(), side='left')]


def _diagnostics(mass, score, weight, edges, threshold, *, layout=None):
    selected = score >= threshold
    order, bins = layout if layout is not None else (np.argsort(mass, kind='stable'), np.searchsorted(edges, mass, side='left'))
    w, selected_w = weight[order], (weight * selected)[order]
    ks = None if selected_w.sum() == 0 else float(np.max(np.abs(np.cumsum(w) / w.sum() - np.cumsum(selected_w) / selected_w.sum())))
    totals = np.bincount(bins, weights=weight, minlength=len(edges)+1)
    accepted = np.bincount(bins[selected], weights=weight[selected], minlength=len(edges)+1)
    rates = [float(a/w) if w else None for a,w in zip(accepted,totals)]
    return dict(absolute_weight_mass_ks=ks, mass_bin_acceptance=rates, threshold=float(threshold), absolute_weight_working_point=.5,
                threshold_source='train_background_absolute_weight_median', bin_source='train_background_absolute_weight_quantiles', evaluation_source='validation_background')


def mass_slice_auc(frame, scores, mass_edges):
    """Validation absolute-weight AUC on fixed, common mass slices."""
    edges = np.asarray(mass_edges, dtype=float)
    scores = np.asarray(scores, dtype=float)
    if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or not np.all(np.diff(edges) > 0):
        raise ResearchError('invalid mass-slice AUC edges')
    required = {'m4l', 'label', 'physical_weight'}
    if (not required <= set(frame) or len(frame) != len(scores) or not np.isfinite(scores).all()
            or not np.isfinite(frame[['m4l', 'physical_weight']].to_numpy(float)).all()
            or not set(frame.label) <= {0, 1}):
        raise ResearchError('invalid mass-slice AUC scores')
    result = []
    mass = frame.m4l.to_numpy(float)
    labels = frame.label.to_numpy(int)
    weights = np.abs(frame.physical_weight.to_numpy(float))
    for index, (low, high) in enumerate(zip(edges[:-1], edges[1:])):
        selected = (mass >= low) & (mass < high)
        support = {}
        valid = True
        for label in (0, 1):
            chosen = selected & (labels == label)
            chosen_weights = weights[chosen]
            total = float(chosen_weights.sum())
            sumw2 = float(np.square(chosen_weights).sum())
            support[str(label)] = {'row_count': int(chosen.sum()), 'sum_absolute_weight': total,
                                   'effective_count': total * total / sumw2 if sumw2 > 0 else 0.0}
            valid &= bool(chosen.any() and total > 0)
        auc = float(roc_auc_score(labels[selected], scores[selected], sample_weight=weights[selected])) if valid else None
        result.append({'slice_index': index, 'mass_low': float(low), 'mass_high': float(high),
                       'status': 'valid' if valid else 'insufficient_class_support',
                       'auc': auc, 'class_support': support})
    return result


def train_discriminant(frame, protocol, candidate='M3', seed=42, target_lambda=0., groups=None,
                       mass_input='on', *, _registered_first_width=64):
    """Fit only train/validation roles. Serialize tensor lists, never pickle."""
    protocol = protocol_dict(protocol)
    if candidate not in CANDIDATES:
        raise ResearchError('candidate is not trainable; CDF candidates derive from frozen models')
    cfg = protocol.get('training', TRAINING)
    if any(cfg.get(k) != v for k, v in TRAINING.items()):
        raise ResearchError('training rules differ from the sealed research schedule')
    if seed not in range(42, 47) or (candidate == 'L1' and seed != 42):
        raise ResearchError('seed outside registered candidate budget')
    if not np.isfinite(target_lambda) or target_lambda < 0 or (candidate != 'M6' and target_lambda != 0):
        raise ResearchError('invalid candidate lambda')
    if candidate == 'M6' and target_lambda not in (.05, .1, .2, .5):
        raise ResearchError('M6 strength outside registered matrix; zero uses M3-fixed200')
    if type(_registered_first_width) is not int or _registered_first_width < 1:
        raise ResearchError('invalid registered classifier width')
    if mass_input == 'off' and (candidate != 'M3' or groups is None):
        raise ResearchError('m4l-off is registered only for grouped M3 models')
    names = list(representation_features(CANDIDATES[candidate], groups=groups, mass_input=mass_input))
    _validate_frame(frame, ['train', 'validation'], names)
    if protocol.get('dataset', frame.dataset.iloc[0]) != frame.dataset.iloc[0]:
        raise ResearchError('training protocol dataset mismatch')
    train, valid = frame[frame.role == 'train'], frame[frame.role == 'validation']
    for part in (train, valid):
        if any(np.abs(part.loc[part.label == label, 'physical_weight']).sum() <= 0 for label in (0, 1)):
            raise ResearchStateError('missing effective class', status='insufficient_statistics')
    x = train[names].to_numpy(float)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1
    x = torch.tensor((x - mean) / scale, dtype=torch.float32)
    xv = torch.tensor((valid[names].to_numpy(float) - mean) / scale, dtype=torch.float32)
    y = torch.tensor(train.label.to_numpy(), dtype=torch.float32)
    w = np.abs(train.physical_weight.to_numpy(float))
    class_means = [float(w[train.label.to_numpy() == label].mean()) for label in (0, 1)]
    opt_w = torch.tensor(w / np.asarray(class_means)[train.label.to_numpy(int)], dtype=torch.float32)
    bg = train.label.to_numpy() == 0
    edges = _quantile(train.m4l.to_numpy()[bg], w[bg], np.arange(1, 11) / 11)
    bins = np.searchsorted(edges, train.m4l.to_numpy(), side='left')
    fixed = candidate in {'M6', 'M3-fixed200'}
    detailed = 'diagnostics' in protocol
    vb = valid.label.to_numpy() == 0
    bin_tensor = torch.tensor(bins, dtype=torch.long)
    background_tensor = y == 0
    valid_labels = valid.label.to_numpy()
    valid_weights = np.abs(valid.physical_weight.to_numpy())
    valid_mass = valid.m4l.to_numpy()[vb]
    diagnostic_layout = (np.argsort(valid_mass, kind='stable'), np.searchsorted(edges, valid_mass, side='left'))
    if fixed and (len(np.unique(edges)) != 10 or any(w[bg & (bins == k)].sum() <= 0 for k in range(11))):
        raise ResearchStateError('ineffective adversarial diagnostic mass bins', status='insufficient_statistics')
    # Both fixed candidates construct the adversary, sharing initialization and RNG consumption.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = ResearchClassifier(len(names), _registered_first_width)
        adversary = Adversary() if fixed else None
        parameters = list(model.parameters()) + ([] if adversary is None else list(adversary.parameters()))
        optimizer = torch.optim.AdamW(parameters, lr=1e-3, weight_decay=1e-4)
        generator = torch.Generator().manual_seed(seed)
        history, best, best_epoch, best_state = [], -np.inf, 0, None
        for epoch in range(1, 201):
            model.train()
            if adversary is not None:
                adversary.train()
            lam = effective_lambda(epoch, target_lambda)
            losses = []
            classification_sum = adversary_sum = adversary_weight = 0.
            for indices in torch.randperm(len(train), generator=generator).split(1024):
                optimizer.zero_grad()
                logits = model(x[indices])
                classification = nn.functional.binary_cross_entropy_with_logits(logits, y[indices], reduction='none') * opt_w[indices]
                loss = classification.mean()
                classification_sum += float(classification.detach().sum())
                mask = background_tensor[indices]
                if adversary is not None and mask.any():
                    adv = adversary(logits[mask], lambda_effective=lam)
                    bw = opt_w[indices][mask]
                    ce = nn.functional.cross_entropy(adv, bin_tensor[indices][mask], reduction='none')
                    loss = loss + (ce * bw).sum() / bw.sum()
                    adversary_sum += float((ce * bw).detach().sum())
                    adversary_weight += float(bw.sum())
                if not torch.isfinite(loss):
                    raise ResearchStateError('nonfinite training loss', status='training_failed')
                loss.backward()
                optimizer.step()
                losses.append(float(loss.detach()))
            model.eval()
            with torch.no_grad():
                scores = torch.sigmoid(model(xv)).numpy()
            if not np.isfinite(scores).all():
                raise ResearchStateError('nonfinite validation scores', status='training_failed')
            auc = float(roc_auc_score(valid_labels, scores, sample_weight=valid_weights))
            history.append(dict(epoch=epoch, effective_lambda=lam, validation_absolute_weight_auc=auc, loss=float(np.mean(losses))))
            if detailed:
                # Evaluation mode consumes no dropout RNG and cannot change training.
                with torch.no_grad():
                    epoch_train_scores = torch.sigmoid(model(x)).numpy()
                threshold = _quantile(epoch_train_scores[bg], w[bg], [.5])[0]
                history[-1].update(
                    classification_loss=classification_sum / len(train),
                    adversary_loss=adversary_sum / adversary_weight if adversary_weight else None,
                    classification_denominator=len(train), adversary_denominator=adversary_weight,
                    diagnostics=_diagnostics(valid_mass, scores[vb],
                        valid_weights[vb], edges, threshold, layout=diagnostic_layout))
            if auc > best + 1e-4:
                best, best_epoch = auc, epoch
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            if not fixed and epoch - best_epoch >= 20:
                break
        selected = 200 if fixed else best_epoch
        if not fixed:
            model.load_state_dict(best_state)
        with torch.no_grad():
            train_scores, scores = torch.sigmoid(model(x)).numpy(), torch.sigmoid(model(xv)).numpy()
        threshold = _quantile(train_scores[bg], w[bg], [.5])[0]
        vb = valid.label.to_numpy() == 0
        result = dict(schema_version='research-discriminant-v1', candidate=candidate, representation=CANDIDATES[candidate],
            groups=groups, mass_input=mass_input, ordered_inputs=names, dataset=str(frame.dataset.iloc[0]), protocol_id=digest(protocol), seed=seed,
            architecture=[len(names),_registered_first_width,64,32,1], scaler=dict(mean=mean.tolist(), scale=scale.tolist(), source_role='train', fitting_rows=len(train)),
            optimizer_class_absolute_weight_means=class_means, mass_bin_boundaries=edges.tolist(),
            state_dict={k:v.tolist() for k,v in model.state_dict().items()}, history=history,
            selected_epoch=selected, target_lambda=target_lambda, effective_lambda=effective_lambda(selected,target_lambda),
            checkpoint_rule='fixed-epoch-200' if fixed else 'validation-absolute-auc-patience20-delta1e-4',
            validation_absolute_weight_auc=float(roc_auc_score(valid.label,scores,sample_weight=np.abs(valid.physical_weight))),
            validation_mass_slice_auc=mass_slice_auc(valid, scores, protocol['calibration']['mass_edges']),
            diagnostics=_diagnostics(valid_mass,scores[vb],valid_weights[vb],edges,threshold,layout=diagnostic_layout),
            status='trained', eligibility_gate='not_applicable_research')
        if detailed:
            result['history_contract'] = dict(
                version=protocol['diagnostics']['training'],
                classification_loss='sum_train_normalized_absolute_weight_BCE / train_rows; online pre-update batches',
                adversary_loss='sum_background_normalized_absolute_weight_CE / sum_background_weights; online pre-update batches',
                loss='unweighted mean of batch composite losses; not classifier objective under gradient reversal',
                threshold='recomputed each epoch from train background absolute-weight median; validation evaluation only',
                selection='diagnostics never select checkpoint')
    result['model_id'] = digest(result)
    return result


def predict_discriminant(artifact, frame):
    schema = artifact.get('schema_version') if isinstance(artifact, dict) else None
    if schema == 'h4l-zero-information-v1':
        validate_empty_model(artifact)
        _validate_frame(frame, ['train','validation','calibration','template','assessment'], [])
        if set(frame.dataset) != {artifact['dataset']}:
            raise ResearchError('model dataset binding mismatch')
        return np.full(len(frame), .5)
    if schema in {'research-discriminant-v2', 'h4l-capacity-discriminant-v1'}:
        raise ResearchError('v2 prediction requires a verified sample-efficiency model handle',
                            status='training_subset_binding_mismatch')
    if schema != 'research-discriminant-v1':
        raise ResearchError('unsupported model artifact schema')
    return _predict_discriminant_payload(artifact, frame)


def _predict_discriminant_payload(artifact, frame):
    content = {k:v for k,v in artifact.items() if k != 'model_id'}
    if digest(content) != artifact.get('model_id'):
        raise ResearchError('model artifact digest mismatch')
    expected = list(representation_features(artifact['representation'], groups=artifact['groups'],
                                            mass_input=artifact.get('mass_input', 'on')))
    width = 64
    if artifact.get('schema_version') in {'research-discriminant-v2', 'h4l-capacity-discriminant-v1'}:
        width = artifact['architecture'][1]
    if artifact['ordered_inputs'] != expected or artifact['architecture'] != [len(expected),width,64,32,1]:
        raise ResearchError('ordered feature or architecture binding mismatch')
    _validate_frame(frame, ['train','validation','calibration','template','assessment'], expected)
    if set(frame.dataset) != {artifact['dataset']}:
        raise ResearchError('model dataset binding mismatch')
    mean, scale = np.asarray(artifact['scaler']['mean']), np.asarray(artifact['scaler']['scale'])
    if mean.shape != (len(expected),) or scale.shape != mean.shape or not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale <= 0).any():
        raise ResearchError('invalid scaler')
    model = ResearchClassifier(len(expected), width)
    try:
        state = {k:torch.tensor(v,dtype=torch.float32) for k,v in artifact['state_dict'].items()}
        if any(not torch.isfinite(v).all() for v in state.values()):
            raise ResearchError('nonfinite model tensors')
        model.load_state_dict(state,strict=True)
    except (ValueError, RuntimeError) as exc:
        raise ResearchError('invalid model tensors') from exc
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(torch.tensor((frame[expected].to_numpy(float)-mean)/scale,dtype=torch.float32))).numpy()


def make_empty_model(protocol, prepared_id, seed):
    if type(seed) is not int or seed not in range(42,47):
        raise ResearchError("unregistered M0off seed")
    if not isinstance(prepared_id, str) or len(prepared_id) != 64:
        raise ResearchError("M0off requires prepared artifact identity")
    result = {"schema_version": "h4l-zero-information-v1", "candidate": "M0off",
              "family_id": "engineered19_raw_T1_m4l_off_attribution_v1", "dataset": protocol["dataset"], "seed": seed,
              "protocol_id": digest(protocol), "prepared_artifact_id": prepared_id,
              "mass_input": "off", "ordered_inputs": [], "state_dict": {}, "score": .5,
              "status": "deterministic", "training": "not_applicable"}
    return {**result, "model_id": digest(result)}


def validate_empty_model(model):
    fields = {"schema_version", "candidate", "family_id", "dataset", "seed", "protocol_id",
              "prepared_artifact_id", "mass_input", "ordered_inputs", "state_dict", "score",
              "status", "training", "model_id"}
    if (not isinstance(model, dict) or set(model) != fields
            or model["schema_version"] != "h4l-zero-information-v1" or model["candidate"] != "M0off"
            or model["family_id"] != "engineered19_raw_T1_m4l_off_attribution_v1" or model["mass_input"] != "off"
            or model["ordered_inputs"] != [] or model["state_dict"] != {} or model["score"] != .5
            or model["status"] != "deterministic" or model["training"] != "not_applicable"
            or model["model_id"] != digest({k:v for k,v in model.items() if k != "model_id"})):
        raise ResearchError("invalid M0off zero-information artifact")
    if type(model["seed"]) is not int or model["seed"] not in range(42,47):
        raise ResearchError("unregistered M0off seed")
