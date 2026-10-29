/* Small, deterministic teaching helpers. No event data or inference execution. */
globalThis.DraftTeaching = (() => {
  'use strict';
  const dimensions = Object.freeze({A:8,B:4,C:2,D:5});
  const models = Object.freeze(['ABCD','BCD','ACD','ABD','ABC']);
  const examples = Object.freeze({
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
  return Object.freeze({dimensions,models,examples,dimension,weightedMedian,reduced});
})();
