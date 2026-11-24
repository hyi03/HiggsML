/* Accessible vector figures authored for this teaching presentation. */
globalThis.V = (() => {
  const colors={A:'#2374ab',B:'#c66b16',C:'#16836b',D:'#8b5db5',signal:'#16836b',background:'#8b9ba9'};
  const esc = s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const text=(x,y,s,cls='label',anchor='middle',color='')=>`<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}"${color?` style="fill:${color}"`:''}>${esc(s)}</text>`;
  const line=(x1,y1,x2,y2,cls='link',extra='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="${cls}" ${extra}/>`;
  const circle=(x,y,r,color='#126e89')=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${color}"/>`;
  const box=(x,y,w,h,title,sub='',color='#126e89')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="7" fill="${color}0d" stroke="${color}"/>${text(x+w/2,y+h/2+(sub?-4:6),title,'large')}${sub?text(x+w/2,y+h/2+23,sub,'tiny'):''}`;
  const svg=(body,label,w=720,h=360)=>`<div class="figure-scroll" tabindex="0" aria-label="${esc(label)}; scroll horizontally on narrow screens"><svg class="figure" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${body}</svg></div><span class="mobile-figure-hint">Scroll the figure horizontally to see all labels.</span>`;
  const flow=(items,start=1)=>`<div class="flow">${items.map((v,i)=>`${i?'<span class="arrow" aria-hidden="true">→</span>':''}<div class="step"><span class="number">${String(i+start).padStart(2,'0')}</span><strong>${v[0]}</strong><span>${v[1]}</span></div>`).join('')}</div>`;
  const shapleyBasics=()=>{
    let out=text(310,24,'Entry order changes the marginal gain','large');
    for(const [y,first,middle,firstGain,lastGain] of [[93,'A','1.6','0.4','0.1'],[244,'B','1.8','0.2','0.3']]){
      const last=first==='A'?'B':'A';
      out+=box(20,y,120,64,'Empty','W = 2.0')+box(250,y,120,64,`${first} only`,`W = ${middle}`,colors[first])+box(480,y,120,64,'A + B','W = 1.5');
      out+=line(148,y+32,235,y+32,'axis')+text(235,y+40,'›','large')+line(378,y+32,465,y+32,'axis')+text(465,y+40,'›','large');
      out+=text(195,y-18,`Add ${first}: +${firstGain}`,'label','middle',colors[first])+text(425,y-18,`Add ${last}: +${lastGain}`,'label','middle',colors[last]);
    }
    return svg(out,'Two-group teaching example: widths 2.0, 1.6, 1.8, 1.5 for empty, A, B, AB. A then B gains 0.4 and 0.1; B then A gains 0.2 and 0.3.',620,330);
  };
  const intervalBasics=()=>{
    const x=v=>100+230*v;
    let out=text(330,24,'Two teaching intervals on the same μ axis','large');
    for(const [y,lo,hi,label,color] of [[92,.3,1.7,'Method I','#16836b'],[200,.1,1.9,'Method II','#2374ab']]){
      out+=text(86,y+6,label,'label','end')+`<line x1="${x(lo)}" y1="${y}" x2="${x(hi)}" y2="${y}" stroke="${color}" stroke-width="10" stroke-linecap="round"/>`;
      out+=text(x(lo),y+32,String(lo),'label')+text(x(hi),y+32,String(hi),'label');
      out+=`<path d="M${x(lo)} ${y-15} v30 M${x(hi)} ${y-15} v30" stroke="${color}" stroke-width="3"/>`;
    }
    out+=line(x(1),52,x(1),248,'axis','stroke-dasharray="5 5"')+line(x(0),270,x(2),270,'axis');
    for(const v of [0,.5,1,1.5,2])out+=line(x(v),270,x(v),278,'axis')+text(x(v),300,String(v),'label');
    out+=text(595,275,'μ','large');
    return svg(out,'Common mu axis: Method I is 0.3 to 1.7, width 1.4; Method II is 0.1 to 1.9, width 1.8. Hand-written intervals, not fits to the preceding counts.',660,315);
  };
  // Explicit operators render reliably in MathML Core (mfenced is deprecated).
  const math=(inner,label)=>`<div class="formula"><math xmlns="http://www.w3.org/1998/Math/MathML" display="block" aria-label="${esc(label)}">${inner.replaceAll('<mfenced>','<mrow><mo>(</mo>').replaceAll('</mfenced>','<mo>)</mo></mrow>')}</math></div>`;
  const mi=s=>`<mi>${esc(s)}</mi>`, mn=s=>`<mn>${s}</mn>`, mo=s=>`<mo>${esc(s)}</mo>`, mt=s=>`<mtext>${esc(s)}</mtext>`;
  const sub=(a,b)=>`<msub>${mi(a)}${typeof b==='number'?mn(b):mi(b)}</msub>`;
  const decay=()=>svg(`${line(80,180,275,90)}${line(80,180,275,270)}${line(325,90,545,40)}${line(325,90,545,135)}${line(325,270,545,220)}${line(325,270,545,315)}${circle(80,180,40)}${text(80,189,'H','large','middle','white')}${circle(300,90,30,colors.B)}${circle(300,270,30,colors.C)}${text(300,97,'Z₁','large','middle','white')}${text(300,277,'Z₂*','large','middle','white')}${[['e⁻',40],['e⁺',135],['μ⁻',220],['μ⁺',315]].map(([s,y])=>circle(560,y,20,'#dae7ee')+text(560,y+6,s,'large')).join('')}${text(135,320,'Decay schematic; not a detector event display','tiny','start')}`,'H decays to two Z systems, then two electrons and two muons; the star denotes an off-shell Z system',640,360);
  const geometry=()=>svg(`${line(100,270,610,270,'axis')}${line(100,270,100,40,'axis')}${line(100,270,430,65,'axis')}${line(100,270,430,270,'link','stroke-dasharray="6 5"')}${line(430,65,430,270,'link','stroke-dasharray="6 5"')}${text(620,275,'Transverse','tiny')}${text(100,25,'Beam z','tiny')}${text(260,252,'pT: transverse momentum','label')}${text(340,120,'Lepton momentum p','large')}${text(450,200,'η: direction','label')}${text(340,330,'ΔR = √[(Δη)² + (Δφ)²]','large')}`,'Momentum components relative to the beam; lepton angular distance Delta R',680,360);
  const angles=()=>svg(`<path d="M140 230 L330 110 L580 200 L370 310 Z" fill="${colors.D}22" stroke="${colors.D}"/><path d="M160 140 L370 310 L590 80 L360 35 Z" fill="${colors.C}13" stroke="${colors.C}"/>${line(110,260,620,70,'axis')}${text(200,95,'Z₁ decay plane','label')}${text(515,285,'Z₂ decay plane','label')}${text(390,180,'φ','large')}${text(350,350,'Three polar cosines + two oriented plane angles','label')}`,'Schematic dilepton decay planes for group D; orientations follow the paper',700,380);
  function network(groups='BC') {
    const d=[...groups].reduce((s,g)=>s+({A:8,B:4,C:2,D:5}[g]),0);
    if(!d)return svg(`${box(70,110,190,90,'No inputs','∅ / M0off')}${line(260,155,360,155,'axis')}${box(360,110,180,90,'Constant 0.5','No training')}${text(315,265,'All accepted events → one inclusive count','label')}`,'Empty subset: no network, score 0.5 and one inclusive event count',650,320);
    let body=''; const xs=[65,230,395,560,705]; const counts=[Math.min(d,6),6,6,5,1];
    const ys=counts.map(n=>Array.from({length:n},(_,i)=>160+(i-(n-1)/2)*29));
    for(let j=0;j<4;j++) for(const y of ys[j]) for(const yy of ys[j+1])body+=line(xs[j],y,xs[j+1],yy);
    const inputColors=[...groups].flatMap(g=>Array({A:8,B:4,C:2,D:5}[g]).fill(colors[g]));
    for(let j=0;j<5;j++){for(const [i,y] of ys[j].entries())body+=circle(xs[j],y,j===4?14:9,j===0?inputColors[Math.floor(i*d/counts[0])]:'#126e89');body+=text(xs[j],35,[`${d} inputs`,'64','64','32','1 logit'][j],'large');}
    body+=text(395,295,'Each hidden layer: Linear → LayerNorm → SiLU','label');
    body+=text(310,325,'Dropout (p = 0.1) after the first two hidden layers','label');
    body+=text(690,260,'sigmoid → score 0–1','tiny');body+=text(65,260,groups,'large');
    return svg(body,'Network: '+d+' inputs; hidden layers 64, 64, 32; one logit then sigmoid. Circles are schematic.',800,355);
  }
  const categories=()=>{const samples=H4L.D.example_model_spec.channels[0].samples;let b=samples.find(s=>s.name==='0').data,s=samples.find(s=>s.name==='1').data;let out='';for(let c=0;c<2;c++){let x=150+c*300;out+=`<rect x="${x}" y="${290-b[c]*65}" width="60" height="${b[c]*65}" fill="${colors.background}"/><rect x="${x+75}" y="${290-s[c]*65}" width="60" height="${s[c]*65}" fill="${colors.signal}"/>`;out+=text(x+30,280-b[c]*65,H4L.fmt(b[c]),'tiny')+text(x+105,280-s[c]*65,H4L.fmt(s[c]),'tiny')+text(x+65,322,c?'High-score category':'Low-score category','label');}out+=line(90,290,650,290,'axis');return svg(out,'BC seed 42: background and signal expectations in two categories',720,350);};
  const dotPlot=(rows,domain,title,zero=false)=>{const [lo,hi]=domain,x=v=>145+(v-lo)/(hi-lo)*485;const ht=rows.length*42+62;let out='';for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;out+=line(x(v),12,x(v),ht-40,'grid')+text(x(v),ht-17,H4L.fmt(v,2),'tiny');}if(zero&&lo<0&&hi>0)out+=line(x(0),12,x(0),ht-40,'axis','stroke-dasharray="4 4"');rows.forEach((r,i)=>{const y=30+i*42;out+=text(130,y+5,r.label,'label','end');if(r.interval)out+=`<line x1="${x(r.interval[0])}" y1="${y}" x2="${x(r.interval[1])}" y2="${y}" stroke="${r.color||'#126e89'}" stroke-width="4"/>`;if(r.points)r.points.forEach((v,j)=>out+=circle(x(v),y+(j-2)*4,3.5,['#0072B2','#D55E00','#009E73','#CC79A7','#E69F00'][j]));out+=circle(x(r.value),y,5,r.color||'#182b42');out+=text(655,y+5,H4L.signed(r.value),'tiny','start');});return svg(out,title,760,ht);};
  const aucPlot=()=>{let out='';const x=v=>80+(v-.5)/.4*530,y=v=>290-(v-1.48)/.2*240;for(let i=0;i<5;i++){const a=.5+i*.1;out+=line(x(a),35,x(a),290,'grid')+text(x(a),317,a.toFixed(1),'tiny');}for(let i=0;i<5;i++){const a=1.48+i*.05;out+=line(80,y(a),610,y(a),'grid')+text(65,y(a)+5,a.toFixed(2),'tiny','end');}H4L.rank().forEach(r=>{const a=H4L.median(H4L.D.seeds.map(k=>H4L.record(r.subset,k).auc));out+=circle(x(a),y(r.value),['AC','BC','ABCD'].includes(r.subset)?6:4,['AC','BC','ABCD'].includes(r.subset)?'#16836b':'#9baab7');if(['AC','BC','ABCD','D'].includes(r.subset))out+=text(x(a)+9,y(r.value)+(r.subset==='AC'?-10:5),r.subset,'tiny','start');});out+=text(350,350,'Validation absolute-weight AUC (larger is better)','label')+text(135,18,'W68 (smaller is better)','tiny');return svg(out,'Median AUC and interval width for 15 subsets: AC has highest AUC, BC smallest width',700,375);};
  const coverage=()=>{let out='';const stages=['model-self','assessment','t2'],names=['Model-self','assessment','T2'],cs=['#2374ab','#c66b16','#16836b'];const y=v=>260-(v-.59)/.12*220;for(let i=0;i<=4;i++){let a=.60+i*.025;out+=line(75,y(a),650,y(a),'grid')+text(62,y(a)+4,a.toFixed(3),'tiny','end');}out+=line(75,y(.68),650,y(.68),'axis','stroke-dasharray="5 4"')+text(650,y(.68)-8,'Nominal 68%','tiny','end');['','AC','BC','ABCD'].forEach((s,j)=>{const cx=140+j*145;out+=text(cx,300,s||'M0off','label');stages.forEach((stage,i)=>{const row=H4L.D.diagnostics.find(r=>r.stage===stage&&r.subset===s&&Number(r.confidence_level)===.68);const vals=JSON.parse(row.per_seed).map(v=>v.value),xx=cx+(i-1)*22;out+=`<line x1="${xx}" x2="${xx}" y1="${y(Math.min(...vals))}" y2="${y(Math.max(...vals))}" stroke="${cs[i]}" stroke-width="2"/>`+circle(xx,y(+row.median),5,cs[i]);});});names.forEach((s,i)=>out+=circle(140+i*200,340,5,cs[i])+text(153+i*200,345,s,'tiny','start'));return svg(out,'Conditional coverage of nominal 68% intervals: dots are five-seed medians, lines are seed min–max ranges',720,365);};
  return {colors,esc,text,line,circle,box,svg,flow,shapleyBasics,intervalBasics,math,mi,mn,mo,mt,sub,decay,geometry,angles,network,categories,dotPlot,aucPlot,coverage};
})();
