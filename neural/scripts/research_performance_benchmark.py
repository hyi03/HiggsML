"""Synthetic-only refactor benchmark against an immutable Git revision.

Run from neural: python -m scripts.research_performance_benchmark --output PATH
No user dataset, assessment artifact, or ROOT source is read by this command.
"""
import argparse
import importlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time
import threading
import hashlib
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

BASELINE = '66784d3af0a4b73c6001acc94404da3540040866'


def baseline_module(name, revision, directory):
    content = subprocess.check_output(['git','show',f'{revision}:neural/src/research/{name}.py'])
    path = directory/f'{name}.py'
    path.write_bytes(content)
    spec = importlib.util.spec_from_file_location(f'src.research._baseline_{name}',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure(function, repeats):
    wall, cpu, rss = [], [], []
    for _ in range(repeats):
        stop=threading.Event()
        samples=[]
        def monitor():
            while not stop.is_set():
                value=current_rss()
                if value is not None:
                    samples.append(value)
                stop.wait(.01)
        thread=threading.Thread(target=monitor,daemon=True)
        thread.start()
        start, clock = time.perf_counter(), time.process_time()
        try:
            value = function()
        finally:
            stop.set()
            thread.join()
        wall.append(time.perf_counter()-start)
        cpu.append(time.process_time()-clock)
        rss.append(max(samples) if samples else None)
    return value, dict(wall_seconds=wall, median=statistics.median(wall),
                      range=[min(wall),max(wall)],cpu_seconds=cpu,sampled_peak_rss_bytes=rss)


def current_rss():
    if platform.system()=='Windows':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[
                (name,ctypes.c_size_t) for name in ('peak','working','qpp','qp','qpnp','qnp','page','peakpage','private')]
        counters=Counters()
        counters.cb=ctypes.sizeof(counters)
        if ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(-1),ctypes.byref(counters),counters.cb):
            return counters.working
    return None


def compare(old, new, path=''):
    """Fixed tolerances declared before measurement; discrete values exact."""
    if isinstance(old,dict):
        if set(old)!=set(new):
            return [path+':keys']
        return [issue for k in old if not k.endswith('_id') for issue in compare(old[k],new[k],path+'/'+k)]
    if isinstance(old,(list,tuple,np.ndarray)):
        if len(old)!=len(new):
            return [path+':length']
        return [issue for i,(a,b) in enumerate(zip(old,new)) for issue in compare(a,b,path+f'/{i}')]
    if isinstance(old,(float,np.floating)):
        return [] if np.isclose(old,new,rtol=1e-12,atol=1e-12) else [path]
    return [] if old==new else [path]


def root_probe(directory,repeats):
    """Real uproot I/O over an explicitly synthetic file, including mixed baskets."""
    import awkward as ak
    import uproot
    from uproot.interpretation.numerical import AsDtype
    from src.research.data import iter_development_events
    path=directory/'synthetic.root'
    size=1000
    values={'eventNumber':np.arange(size,dtype=np.int64),'channelNumber':np.ones(size,dtype=np.int64),
            'payload':np.arange(size,dtype=float),'vector':ak.Array([[float(i),1.] for i in range(size)])}
    with uproot.recreate(path) as root:
        tree=root.mktree('events',{'eventNumber':'int64','channelNumber':'int64','payload':'float64','vector':'var * float64'})
        tree.extend(values)
    branches={name:name for name in values}
    mask=np.random.default_rng(42).random(size)<.8
    def read(optimized):
        with uproot.open(path) as root:
            tree=root['events']
            identities=tree.arrays(['eventNumber','channelNumber'],library='np')
            if optimized:
                return list(iter_development_events(tree,branches,identities,mask))
            result=[]
            for i in np.flatnonzero(mask):
                array=tree.arrays(list(branches),entry_start=int(i),entry_stop=int(i)+1,library='ak')
                event={name:array[name][0].to_list() if hasattr(array[name][0],'to_list') else array[name][0] for name in branches}
                result.append((int(i),event))
            return result
    before,bt=measure(lambda:read(False),repeats)
    after,at=measure(lambda:read(True),repeats)
    arrays=[]
    def hook(self,**kwargs):
        arrays.append(len(kwargs['output']))
    with patch.object(AsDtype,'hook_after_basket_array',hook):
        with uproot.open(path) as root:
            root['events'].arrays(['payload'],entry_start=0,entry_stop=1,library='np')
    return dict(baseline=bt,optimized=at,speedup=bt['median']/at['median'],
                numerical_equivalence=before==after,entries=size,
                interpretation_probe={'requested':1,'basket_array_lengths':arrays,
                    'meaning':'Whole-basket numerical views exist before final_array slices; this does not prove a strict no-interpretation contract for bound ROOT branch types'},
                scope='synthetic scalar/jagged ROOT reader, excludes selection and feature reconstruction')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',default=BASELINE)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args(argv)
    if args.repeats<3:
        parser.error('at least three repeats required')
    torch.set_num_threads(1)
    from src.research.protocol import load_protocol
    from src.research.representations import representation_features
    from src.research.data import development_spans
    p=load_protocol().to_dict()
    n=14000
    rng=np.random.default_rng(42)
    calibration=pd.DataFrame(dict(m4l=np.repeat(np.arange(107.5,140,5),n//7),label=0,
        role='calibration',dataset='atlas2020_4lep',physical_weight=1.,yield_weight=2.,
        event_group_id=[str(i) for i in range(n)]))
    scores=np.tile((np.arange(n//7)+.5)/(n//7),7)
    template=calibration.assign(role='template',category=rng.integers(0,2,n),label=np.arange(n)%2)
    train=pd.DataFrame({name:rng.normal(size=72) for name in representation_features('engineered19')})
    train['m4l']=np.tile(np.linspace(105.1,139.9,36),2)
    train['label']=np.tile(np.repeat([0,1],18),2)
    train['role']=['train']*36+['validation']*36
    train['dataset']='atlas2020_4lep'
    train['event_group_id']=[str(i) for i in range(72)]
    train['physical_weight']=np.tile([1.,2.],36)
    one={'status':'valid','active_bins':[0],'mapping_id':'m','candidate_id':'synthetic',
         'samples':[dict(name='s',is_signal=True,yield_=[10.]),dict(name='b',is_signal=False,yield_=[20.])]}
    for sample in one['samples']:
        sample.update({'yield':sample.pop('yield_'),'variance':[1.],'covariance':[[1.]]})
    results={}
    with tempfile.TemporaryDirectory(prefix='higgsml-benchmark-') as directory:
        for name in ('calibration','templates','inference','discriminants'):
            old=baseline_module(name,args.baseline,Path(directory))
            new=importlib.import_module('src.research.'+name)
            if name=='calibration':
                mapping=old.fit_calibration(calibration,scores,p,model_id='m')
                masses=rng.uniform(105,140,200000); score=rng.uniform(-.2,1.2,len(masses))
                operations={'cdf_interpolation':lambda mod:mod.apply_calibration(mapping,masses,score,model_id='m'),
                            'calibration_fit':lambda mod:mod.fit_calibration(calibration,scores,p,model_id='m')}
            elif name=='templates':
                operations={'common_grid':lambda mod:mod.common_mass_grid({'A':template,'B':template},mass_edges=list(range(105,141)),thresholds=p['templates'])}
            elif name=='inference':
                # Includes model construction, MLE and roots for three injections.
                operations={'asimov':lambda mod:mod.run_asimov(one)}
            else:
                operations={'training_200_epochs':lambda mod:mod.train_discriminant(train,p,'M6',target_lambda=.2)}
            for label,operation in operations.items():
                before,bt=measure(lambda:operation(old),args.repeats)
                after,at=measure(lambda:operation(new),args.repeats)
                differences=compare(before,after)
                from src.research.discriminants import digest
                results[label]=dict(baseline=bt,optimized=at,speedup=bt['median']/at['median'],
                                    numerical_equivalence=not differences,differences=differences[:20])
                if isinstance(before,dict):
                    results[label]['payload_digest_equal']=digest(before)==digest(after)
                    if label=='training_200_epochs':
                        results[label]['checkpoint_exact']=before['state_dict']==after['state_dict']
                        results[label]['selected_epoch_exact']=before['selected_epoch']==after['selected_epoch']
                print(label,round(results[label]['speedup'],3),'equivalent',not differences,flush=True)
        # Actual operation counts on the same synthetic inference fixture.
        old=baseline_module('inference',args.baseline,Path(directory))
        new=importlib.import_module('src.research.inference')
        import pyhf
        fit=pyhf.infer.mle.fit
        counts=[]
        for module in (old,new):
            with patch.object(pyhf.infer.mle,'fit',wraps=fit) as spy:
                module.run_asimov(one)
                counts.append(sum(len(c.args)==2 and 'fixed_params' not in c.kwargs for c in spy.call_args_list))
        results['unconditional_mle_calls']={'baseline':counts[0],'optimized':counts[1]}
        results['synthetic_root_reader']=root_probe(Path(directory),args.repeats)
    mask=np.random.default_rng(42).random(100000)<.8
    spans=list(development_spans(mask,4096))
    lengths=[b-a for a,b in spans]
    results['root_request_model']=dict(entries=len(mask),development_entries=int(mask.sum()),
        baseline_requests=int(mask.sum()),optimized_requests=len(spans),max_span=max(lengths),
        median_span=statistics.median(lengths),scope='synthetic request count, no ROOT throughput claim')
    report=dict(baseline=args.baseline,platform=platform.platform(),python=platform.python_version(),
        implementation_sha256={path.name:hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in sorted(Path('src/research').glob('*.py'))},
        packages={n:importlib.metadata.version(n) for n in ('numpy','pandas','torch','scipy','uproot','pyhf')},
        resources={'workers':1,'torch_threads':1},input='synthetic only',cache='in-process repeated, OS cache not flushed',
        tolerance={'rtol':1e-12,'atol':1e-12,'discrete':'exact'},results=results,
        limitations=['Not bound MC or ARM64 authority validation',
                     'RSS sampled every 10ms in one process, includes retained allocations; not isolated per-operation high-water marks',
                     'Production end-to-end and worker memory acceptance require representative measurement'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
    return 0 if all(v.get('numerical_equivalence',True) for v in results.values()) else 1


if __name__=='__main__':
    raise SystemExit(main())
