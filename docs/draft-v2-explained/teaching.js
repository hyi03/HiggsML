/* Small, deterministic teaching helpers. No event data or inference execution. */
globalThis.DraftTeaching = (() => {
  'use strict';
  const dimensions = Object.freeze({A:8,B:4,C:2,D:5});
  const models = Object.freeze(['ABCD','BCD','ACD','ABD','ABC']);
  const examples = Object.freeze({
    report: Object.freeze([{score:0.1,weight:1},{score:0.3,weight:2},{score:0.6,weight:1},{score:0.8,weight:4},{score:0.9,weight:2}]),
    balanced: Object.freeze([{score:0.1,weight:1},{score:0.3,weight:1},{score:0.6,weight:1},{score:0.8,weight:1}]),
    ties: Object.freeze([{score:0.1,weight:1},{score:0.35,weight:2},{score:0.35,weight:2},{score:0.8,weight:1}]),
    unequal: Object.freeze([{score:0.1,weight:4},{score:0.4,weight:1},{score:0.7,weight:1},{score:0.9,weight:1}])
  });
  function dimension(model) {
    if (!models.includes(model)) throw new RangeError('Unknown representation');
    return [...model].reduce((n,g) => n + dimensions[g], 0);
  }
  function weightedMedian(rows) {
    if (!rows.length || rows.some(r => !Number.isFinite(r.score) || !Number.isFinite(r.weight) || r.weight < 0)) throw new RangeError('Finite scores and nonnegative weights are required');
    const sorted = rows.filter(r => r.weight > 0).slice().sort((a,b) => a.score-b.score);
    const total = sorted.reduce((n,r) => n+r.weight, 0);
    if (!(total > 0)) throw new RangeError('Positive total weight is required');
    let cumulative = 0;
    const threshold = sorted.find(r => (cumulative += r.weight) >= total/2).score;
    const highWeight = sorted.filter(r => r.score >= threshold).reduce((n,r) => n+r.weight, 0);
    return {threshold,total,highWeight,highFraction:highWeight/total};
  }
  function reduced(group) {
    if (!(group in dimensions)) throw new RangeError('Unknown feature group');
    return 'ABCD'.replace(group,'');
  }
  // Hand-assigned teaching function, never a trained model or physical event generator.
  const toyDefaults = Object.freeze({pt:40,phi:1.6});
  const sigmoid = value => 1 / (1 + Math.exp(-value));
  function tinyForward(pt,phi) {
    if (!Number.isFinite(pt) || !Number.isFinite(phi) || pt<0 || pt>160 || phi<0 || phi>Math.PI) {
      throw new RangeError('Teaching inputs must be finite: pT in [0,160], angle in [0,pi]');
    }
    const x=[(pt-40)/20,(phi-1.6)/0.8];
    const a=[0.6*x[0]-0.4*x[1]+0.1,-0.3*x[0]+0.8*x[1]-0.2];
    const h=a.map(value=>value*sigmoid(value));
    const z=0.9*h[0]-0.7*h[1]+0.05;
    return {x,a,h,z,score:sigmoid(z)};
  }
  // Resolve semantic destinations against the current deck, never fixed positions.
  function pageFromHash(slides, hash, current=1) {
    const clamp = n => Math.max(1, Math.min(slides.length, Math.round(n)));
    const numbered = hash.match(/^#slide-(\d+)$/);
    if (numbered) return clamp(Number(numbered[1]));
    const aliases = {spectra:'spectrum-yields',differences:'contrasts',widths:'all-results','width-widget':'metrics-widget'};
    const name = hash.replace(/^#/, '');
    const index = slides.findIndex(s => s.id === (aliases[name] || name));
    return index < 0 ? current : index + 1;
  }
  return Object.freeze({dimensions,models,examples,dimension,weightedMedian,reduced,pageFromHash,toyDefaults,tinyForward});
})();
