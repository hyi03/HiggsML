"""Fixed CPU learner and validation-only empirical threshold for draft-v2."""
import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.modeling.discriminants import ResearchClassifier, _predict_discriminant_payload, _validate_frame
from higgsml.modeling.representations import representation_features
from higgsml.draft_v2.protocol import candidate_key, validate_protocol


def weighted_median(scores, weights):
    scores, weights = np.asarray(scores, float), np.asarray(weights, float)
    if (scores.ndim != 1 or scores.shape != weights.shape or not len(scores)
            or not np.isfinite(scores).all() or not np.isfinite(weights).all()
            or (weights < 0).any() or not np.isfinite(weights.sum()) or weights.sum() <= 0
            or (scores < 0).any() or (scores > 1).any()):
        raise ResearchError("Weighted score median requires finite scores and nonnegative positive-total weights")
    order = np.argsort(scores, kind='stable')
    index = np.searchsorted(np.cumsum(weights[order]), weights.sum() / 2., side='left')
    return float(scores[order[index]])


def validate_model(model, protocol, *, subset=None, seed=None, prepared_id=None):
    if not isinstance(model, dict) or model.get('schema_version') != 'h4l-draft-v2-model-v1':
        raise ResearchError("Wrong draft-v2 model schema")
    if model.get('model_id') != digest_json({k: v for k, v in model.items() if k != 'model_id'}):
        raise ResearchError("Draft-v2 model seal mismatch")
    candidate_key(model.get('groups'), model.get('seed'))
    names = list(representation_features('engineered19', groups=model['groups'], mass_input='off'))
    if (model.get('protocol_id') != digest_json(protocol) or model.get('mass_input') != 'off'
            or model.get('ordered_inputs') != names or model.get('architecture') != [len(names), 64, 64, 32, 1]
            or model.get('representation') != 'engineered19' or model.get('dataset') != protocol['dataset']
            or not isinstance(model.get('threshold'), (int, float))
            or not np.isfinite(model['threshold']) or not 0 <= model['threshold'] <= 1
            or model.get('threshold_rule') != protocol['threshold']
            or model.get('source_kind') not in {'synthetic', 'controlled_mc'}
            or (subset is not None and model['groups'] != subset)
            or (seed is not None and model['seed'] != seed)
            or (prepared_id is not None and model.get('prepared_artifact_id') != prepared_id)):
        raise ResearchError("Draft-v2 model/protocol/prepared binding mismatch")
    scaler = model.get('scaler', {})
    if (scaler.get('source_role') != 'train' or type(model.get('selected_epoch')) is not int
            or not 1 <= model['selected_epoch'] <= 200):
        raise ResearchError("Invalid checkpoint/scaler binding")
    mean, scale = np.asarray(scaler.get('mean', []), float), np.asarray(scaler.get('scale', []), float)
    if (mean.shape != (len(names),) or scale.shape != mean.shape
            or not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale <= 0).any()):
        raise ResearchError('Invalid draft-v2 training scaler')
    history = model.get('history', [])
    best, selected = -np.inf, 0
    if not isinstance(history, list) or not 1 <= len(history) <= 200:
        raise ResearchError('Missing full production checkpoint history')
    for epoch, row in enumerate(history, 1):
        auc = row.get('validation_absolute_weight_auc')
        if (row.get('epoch') != epoch or type(auc) not in (int, float)
                or not np.isfinite(auc) or not 0 <= auc <= 1):
            raise ResearchError('Invalid checkpoint history')
        if auc > best + protocol['training']['minimum_improvement']:
            best, selected = auc, epoch
        if epoch - selected >= protocol['training']['patience'] and epoch != len(history):
            raise ResearchError('Checkpoint history continued past early stopping')
    if (selected != model['selected_epoch'] or model.get('validation_absolute_weight_auc') != best
            or (len(history) != 200 and len(history) != selected + 20)):
        raise ResearchError('Shortened or inconsistent production checkpoint history')
    try:
        with torch.random.fork_rng(devices=[]):
            network = ResearchClassifier(len(names))
        tensors = {key: torch.tensor(value, dtype=torch.float32) for key, value in model['state_dict'].items()}
        if any(not torch.isfinite(tensor).all() for tensor in tensors.values()):
            raise ValueError('Nonfinite tensor')
        network.load_state_dict(tensors, strict=True)
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        raise ResearchError('Invalid draft-v2 model tensors') from error


def predict(model, frame, protocol):
    validate_model(model, protocol)
    return _predict_discriminant_payload(model, frame, _roles=('train', 'validation', 'evaluation'), _digest=digest_json)


def train(frame, protocol, subset, seed, prepared_id):
    validate_protocol(protocol)
    candidate_key(subset, seed)
    if set(frame.role) != {'train', 'validation'}:
        raise ResearchError("Draft-v2 learner requires training and validation exclusively")
    names = list(representation_features('engineered19', groups=subset, mass_input='off'))
    _validate_frame(frame, ('train', 'validation'), names)
    if (set(frame.dataset) != {protocol['dataset']}
            or frame.attrs.get('source_kind') not in {'synthetic', 'controlled_mc'}):
        raise ResearchError('Learner dataset/source provenance mismatch')
    fitting, validation = frame.loc[frame.role == 'train'], frame.loc[frame.role == 'validation']
    for part in (fitting, validation):
        for label in (0, 1):
            if np.abs(part.loc[part.label == label, 'physical_weight']).sum() <= 0:
                raise ResearchStateError("Missing effective class", status='insufficient_statistics')
    values = fitting[names].to_numpy(float)
    mean, scale = values.mean(axis=0), values.std(axis=0)
    scale[scale == 0] = 1.
    x = torch.tensor((values - mean) / scale, dtype=torch.float32)
    xv = torch.tensor((validation[names].to_numpy(float) - mean) / scale, dtype=torch.float32)
    labels = fitting.label.to_numpy(int)
    y = torch.tensor(labels, dtype=torch.float32)
    absolute = np.abs(fitting.physical_weight.to_numpy(float))
    class_means = [float(absolute[labels == label].mean()) for label in (0, 1)]
    weights = torch.tensor(absolute / np.asarray(class_means)[labels], dtype=torch.float32)
    vw = np.abs(validation.physical_weight.to_numpy(float))
    cfg = protocol['training']
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        network = ResearchClassifier(len(names))
        optimizer = torch.optim.AdamW(network.parameters(), lr=cfg['learning_rate'], weight_decay=cfg['weight_decay'])
        generator = torch.Generator().manual_seed(seed)
        best, best_epoch, best_state, history = -np.inf, 0, None, []
        for epoch in range(1, cfg['max_epochs'] + 1):
            network.train()
            for indices in torch.randperm(len(fitting), generator=generator).split(cfg['batch_size']):
                optimizer.zero_grad()
                logits = network(x[indices])
                loss = (nn.functional.binary_cross_entropy_with_logits(logits, y[indices], reduction='none')
                        * weights[indices]).mean()
                if not torch.isfinite(loss):
                    raise ResearchStateError("Nonfinite training loss", status='training_failed')
                loss.backward()
                optimizer.step()
            network.eval()
            with torch.no_grad():
                scores = torch.sigmoid(network(xv)).numpy()
            auc = float(roc_auc_score(validation.label, scores, sample_weight=vw))
            if not np.isfinite(auc):
                raise ResearchStateError("Nonfinite validation AUC", status='training_failed')
            history.append(dict(epoch=epoch, validation_absolute_weight_auc=auc))
            if auc > best + cfg['minimum_improvement']:
                best, best_epoch = auc, epoch
                best_state = {k: v.detach().clone() for k, v in network.state_dict().items()}
            if epoch - best_epoch >= cfg['patience']:
                break
        network.load_state_dict(best_state)
        with torch.no_grad():
            scores = torch.sigmoid(network(xv)).numpy()
        background = validation.label.to_numpy() == 0
        threshold = weighted_median(scores[background], vw[background])
        model = dict(schema_version='h4l-draft-v2-model-v1', representation='engineered19',
            groups=subset, seed=seed, dataset=protocol['dataset'], protocol_id=digest_json(protocol),
            prepared_artifact_id=prepared_id, source_kind=frame.attrs['source_kind'], mass_input='off',
            ordered_inputs=names, architecture=[len(names), 64, 64, 32, 1],
            scaler=dict(mean=mean.tolist(), scale=scale.tolist(), source_role='train', fitting_rows=len(fitting)),
            optimizer_class_absolute_weight_means=class_means,
            state_dict={k: v.tolist() for k, v in network.state_dict().items()},
            selected_epoch=best_epoch, history=history, validation_absolute_weight_auc=best,
            threshold=threshold, threshold_rule=protocol['threshold'],
            validation_background_high_absolute_acceptance=float(vw[background & (scores >= threshold)].sum()
                                                                / vw[background].sum()))
    model['model_id'] = digest_json(model)
    return model
