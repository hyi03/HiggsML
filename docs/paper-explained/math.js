/* Pure teaching calculations; no training or T1 scientific refits. */
globalThis.H4L = (() => {
  const D = globalThis.H4L_DATA;
  const canon = s => [...s].sort().join('');
  const median = xs => { const a = [...xs].sort((x,y)=>x-y); const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m-1]+a[m])/2; };
  const record = (s,k) => D.records.find(r=>r.subset===canon(s)&&r.seed===Number(k));
  const width = (s,k) => record(s,k).width68;
  const label = s => s || '∅ / M0off';
  const fmt = (x,n=5) => x == null ? '—' : Number(x).toFixed(n);
  const signed = (x,n=5) => (x>=0?'+':'') + fmt(x,n);
  const subsets = chars => Array.from({length:2**chars.length},(_,mask)=>[...chars].filter((_,i)=>mask&(1<<i)).join(''));
  const permutations = a => a.length ? a.flatMap((v,i)=>permutations(a.filter((_,j)=>i!==j)).map(p=>[v,...p])) : [[]];
  const orders = permutations([...'ABCD']);
  const gain = (s,g,k) => width(s,k)-width(canon(s+g),k);
  const weights = [1/4,1/12,1/12,1/4];
  const shapley = (g,k) => subsets('ABCD'.replace(g,'')).reduce((sum,s)=>sum+weights[s.length]*gain(s,g,k),0);
  const interaction = (pair,s,k) => -width(s+pair,k)+width(s+pair[0],k)+width(s+pair[1],k)-width(s,k);
  const reduction = (s,t,k) => 1-width(s,k)/width(t,k);
  const rank = (k='median',metric='width68') => D.subsets.filter(Boolean).map(s=>({subset:s,
    value:k==='median'?median(D.seeds.map(seed=>record(s,seed)[metric])):record(s,k)[metric]}))
    .sort((a,b)=>(metric==='auc'?b.value-a.value:a.value-b.value)||a.subset.length-b.subset.length||a.subset.localeCompare(b.subset));
  const mc = (estimand,match,field) => { const r=D.bootstrap_intervals.find(r=>r.estimand===estimand&&Object.entries(match).every(([k,v])=>r[k]===v));
    if(!r||r.status!=='valid') throw Error('Missing valid selected bootstrap aggregate');
    return field ? JSON.parse(r[field]).interval95 : JSON.parse(r.interval95); };
  // Synthetic fixed-template Asimov example: s=(1,3), b=(3,1), mu_true=1.
  const toyQ = (mu,split=true) => { const s=split?[1,3]:[4],b=split?[3,1]:[4];
    return 2*s.reduce((sum,sv,i)=>{const n=sv+b[i],lam=mu*sv+b[i]; return sum+lam-n+n*Math.log(n/lam);},0); };
  const crossing = (split,upper,critical=.9889464815) => {
    let lo=upper?1:0,hi=upper?20:1;
    if(!upper && toyQ(0,split)<=critical) return 0;
    if(upper && toyQ(20,split)<critical) return null;
    for(let i=0;i<70;i++){const mid=(lo+hi)/2; if((toyQ(mid,split)>critical)===upper)hi=mid;else lo=mid;}
    return (lo+hi)/2;
  };
  return {D,canon,median,record,width,label,fmt,signed,subsets,orders,gain,weights,shapley,interaction,reduction,rank,mc,toyQ,crossing};
})();
