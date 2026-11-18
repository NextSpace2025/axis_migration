/* Local WebGL relationship graph. Layout coordinates are display-only, never evidence. */
(() => {
 'use strict';
 const api=window.graphView,host=document.getElementById('graph-stage');
 const stage=document.getElementById('graph-3d-stage')||host;
 if(!api||!stage)return;
 const canvas=document.createElement('canvas'),labels=document.createElement('canvas');
 canvas.id='graph-3d';canvas.tabIndex=0;canvas.setAttribute('role','application');
 const localResult=window.APP_META?.localResult;
 const reviewing=Boolean(window.AXIS_REVIEW_BASE || localResult);
 const subject=localResult?'변환된 표의':reviewing?'제안한 표의':'파일·업체·현장의';
 canvas.setAttribute('aria-label',`3차원 ${subject} 관계도. 드래그 또는 방향키로 회전, 더하기와 빼기로 확대·축소, Home으로 회전 초기화. 자료 목록에서도 노드를 선택할 수 있습니다.`);
 labels.className='graph-3d-labels';labels.setAttribute('aria-hidden','true');
 const gl=canvas.getContext('webgl',{antialias:true,alpha:false,preserveDrawingBuffer:true});
 const notice=document.createElement('p');notice.className='graph-3d-help';
 const fallback=host.querySelector('#graph')?'기존 관계도를 표시합니다.':'파일·업체·현장 목록에서 연결을 확인할 수 있습니다.';
 if(!gl){notice.textContent='이 환경은 3D 관계도를 지원하지 않습니다. '+fallback;host.append(notice);return;}
 const ctx=labels.getContext('2d'),tau=Math.PI*2,tan=.55;
 function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
 function program(vertex,fragment){const p=gl.createProgram();gl.attachShader(p,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(p,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));return p;}
 const projection=`uniform mat3 rotation;uniform vec3 target;uniform float distance;uniform float aspect;uniform vec2 pan;
 vec4 project(vec3 p){vec3 v=rotation*(p-target);float z=distance-v.z;return vec4(v.x/(${tan.toFixed(2)}*aspect)+pan.x*z,v.y/${tan.toFixed(2)}+pan.y*z,z*1.00002-.200002,z);}`;
 let orb,wire;
 try{
  orb=program(`attribute vec3 position;uniform vec3 center;uniform float radius;uniform float viewportHeight;${projection}void main(){gl_Position=project(center+position);gl_PointSize=clamp(radius*viewportHeight/(${tan.toFixed(2)}*gl_Position.w),2.,40.);}`,
   `precision mediump float;uniform vec4 color;void main(){float r=length(gl_PointCoord-vec2(.5))*2.;if(r>1.)discard;gl_FragColor=vec4(color.rgb,color.a*(1.-smoothstep(.82,1.,r)));}`);
  wire=program(`attribute vec3 position;attribute vec4 color;varying vec4 C;${projection}void main(){C=color;gl_Position=project(position);}`,`precision mediump float;varying vec4 C;void main(){gl_FragColor=C;}`);
 }catch(error){notice.textContent='3D 초기화에 실패해 기존 관계도를 표시합니다.';stage.append(notice);console.error(error);return;}
 function buffer(values){const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);return b;}
 const sphere=buffer([0,0,0]),linePositions=gl.createBuffer(),lineColors=gl.createBuffer();
 function attribute(p,name,b,size){const location=gl.getAttribLocation(p,name);if(location<0)return;gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,size,gl.FLOAT,false,0,0);}
 function hash(s){let h=2166136261;for(const c of s)h=Math.imul(h^c.charCodeAt(0),16777619);return h>>>0;}
 const ordered=[...api.nodes.values()].sort((a,b)=>a.id.localeCompare(b.id));
 const index=new Map(ordered.map((n,i)=>[n.id,i]));
 const connections=[...api.edges.values()].filter(e=>!e.internal&&index.has(e.from)&&index.has(e.to));
 const neighbors=new Map(ordered.map(n=>[n.id,new Set()]));
 const parent=ordered.map((_,i)=>i);
 function find(i){while(parent[i]!==i){parent[i]=parent[parent[i]];i=parent[i];}return i;}
 for(const e of connections){neighbors.get(e.from).add(e.to);neighbors.get(e.to).add(e.from);parent[find(index.get(e.from))]=find(index.get(e.to));}
 const ps=ordered.map(n=>[n.x*.65,n.y*.65,(hash(n.id+'depth')/4294967295-.5)*125]);
 const sums=new Map();
 ps.forEach((p,i)=>{const root=find(i);if(!sums.has(root))sums.set(root,[0,0,0,0]);const a=sums.get(root);p.forEach((v,j)=>a[j]+=v);a[3]++;});
 const anchors=ps.map((_,i)=>{const a=sums.get(find(i));return a.slice(0,3).map(v=>v/a[3]);});
 // Existing edges alone create attraction; disconnected components keep space.
 for(let pass=0;pass<95;pass++){
  const forces=ps.map(()=>[0,0,0]);
  for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++){
   const delta=ps[i].map((v,k)=>v-ps[j][k]),force=360/(delta.reduce((a,v)=>a+v*v,0)+60);
   for(let k=0;k<3;k++){const f=delta[k]*force;forces[i][k]+=f;forces[j][k]-=f;}
  }
  for(const e of connections){const a=index.get(e.from),b=index.get(e.to),delta=ps[b].map((v,k)=>v-ps[a][k]),length=Math.hypot(...delta)||1;
   const rest=35+(hash(e.id)%55),strength=(length-rest)*.018/length;
   for(let k=0;k<3;k++){const f=delta[k]*strength;forces[a][k]+=f;forces[b][k]-=f;}
  }
  const temperature=4.2*(1-pass/95)+.2;
  ps.forEach((p,i)=>{for(let k=0;k<3;k++)forces[i][k]+=(anchors[i][k]-p[k])*.012;forces[i][2]-=p[2]*.006;
   const length=Math.hypot(...forces[i])||1,step=Math.min(temperature,length)/length;
   for(let k=0;k<3;k++)p[k]+=forces[i][k]*step;
  });
 }
 const positions=new Map(ordered.map((n,i)=>[n.id,ps[i]]));
 const colors={file:[.63,.55,.94],company:[.96,.72,.38],site:[.35,.83,.72],expected:[.72,.69,.83]};
 let width=1,height=1,yaw=.12,pitch=-.08,distance=650,fitDistance=650,target=[0,0,0],pan=[0,0],radius=210;
 let lost=false,scheduled=false,velocity=[0,0],drag=null,hovered=null,projected=[],projectedEdges=[],draws=0;
 const help=document.createElement('p');help.className='graph-3d-help';help.textContent='드래그 회전 · 휠 확대';
 const reset=document.createElement('button');reset.type='button';reset.className='graph-3d-reset';reset.textContent='회전 초기화';reset.title='방향과 확대를 초기화합니다';
 const tooltip=stage===host?document.getElementById('hover-label'):document.createElement('div');
 if(stage!==host){tooltip.className='hover-label graph-3d-hover';tooltip.hidden=true;stage.append(tooltip);}
 const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
 const glow=document.createElement('div');
 glow.className='graph-3d-click-glow';
 glow.setAttribute('aria-hidden','true');
 Object.assign(glow.style,{position:'absolute',width:'52px',height:'52px',pointerEvents:'none',opacity:'0',zIndex:'2'});
 let glowAnimation;
 function flash(x,y,tint){
  glowAnimation?.cancel();
  glow.style.left=(x-26)+'px';
  glow.style.top=(y-26)+'px';
  glow.style.background=`radial-gradient(circle, #fff 0%, rgb(${tint} / .88) 12%, rgb(${tint} / .36) 35%, transparent 70%)`;
  glowAnimation=reducedMotion.matches
   ?glow.animate([{opacity:.7},{opacity:0}],{duration:180,easing:'steps(1,end)'})
   :glow.animate([{opacity:.92,transform:'scale(.48)'},{opacity:0,transform:'scale(1.12)'}],{duration:420,easing:'cubic-bezier(.2,.65,.3,1)'});
 }
 function matrix(){const c=Math.cos(yaw),s=Math.sin(yaw),C=Math.cos(pitch),S=Math.sin(pitch);return[c,S*s,-C*s,0,C,S,s,-S*c,C*c];}
 function transform(p,m){const a=p.map((v,i)=>v-target[i]);return[m[0]*a[0]+m[3]*a[1]+m[6]*a[2],m[1]*a[0]+m[4]*a[1]+m[7]*a[2],m[2]*a[0]+m[5]*a[1]+m[8]*a[2]];}
 function project(p,m){const v=transform(p,m),z=distance-v[2],scale=height/(2*tan*z);return{x:width/2+v[0]*scale+pan[0],y:height/2-v[1]*scale+pan[1],z,scale};}
 function uniforms(p,m){gl.uniformMatrix3fv(gl.getUniformLocation(p,'rotation'),false,m);gl.uniform3fv(gl.getUniformLocation(p,'target'),target);gl.uniform1f(gl.getUniformLocation(p,'distance'),distance);gl.uniform1f(gl.getUniformLocation(p,'aspect'),width/height);gl.uniform2fv(gl.getUniformLocation(p,'pan'),[2*pan[0]/width,-2*pan[1]/height]);}
 function request(){if(lost)return;if(!scheduled){scheduled=true;requestAnimationFrame(draw);}}
 function resize(){width=Math.max(1,stage.clientWidth);height=Math.max(1,stage.clientHeight);const dpr=Math.min(window.devicePixelRatio||1,2);for(const c of [canvas,labels]){c.width=Math.round(width*dpr);c.height=Math.round(height*dpr);c.style.width=width+'px';c.style.height=height+'px';}ctx.setTransform(dpr,0,0,dpr,0,0);gl.viewport(0,0,canvas.width,canvas.height);request();}
 function fit(){const ns=api.state.visibleNodes;if(!ns.length){request();return;}const ps=ns.map(n=>positions.get(n.id));target=[0,1,2].map(i=>(Math.min(...ps.map(p=>p[i]))+Math.max(...ps.map(p=>p[i])))/2);radius=Math.max(45,...ps.map(p=>Math.hypot(...p.map((v,i)=>v-target[i]))));distance=radius/Math.sin(Math.atan(tan))*Math.max(1,height/width)*1.27;fitDistance=distance;pan=[0,0];request();}
 function zoom(factor){distance=Math.max(radius*1.04,Math.min(fitDistance*5,distance/factor));request();}
 function lines(m,palette){const values=[],shades=[];function segment(a,b,color){values.push(...a,...b);shades.push(...color,...color);}
  const selected=api.state.node,chosen=api.state.edge;
  for(const e of api.state.visibleEdges){const a=positions.get(e.from),b=positions.get(e.to);if(!a||!b)continue;const near=e.from===selected||e.to===selected,strong=e.id===chosen;
   const col=strong?palette.selected:e.status==='observed'?palette.observed:palette.candidate;const alpha=strong?.95:near?.65:selected?.055:reviewing?.75:.22;
   const color=[...col,alpha];if(e.status==='observed')segment(a,b,color);else for(let j=0;j<18;j+=2)segment(a.map((v,i)=>v+(b[i]-v)*j/18),a.map((v,i)=>v+(b[i]-v)*(j+1)/18),color);
  }
  gl.useProgram(wire);uniforms(wire,m);gl.bindBuffer(gl.ARRAY_BUFFER,linePositions);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.DYNAMIC_DRAW);attribute(wire,'position',linePositions,3);gl.bindBuffer(gl.ARRAY_BUFFER,lineColors);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(shades),gl.DYNAMIC_DRAW);attribute(wire,'color',lineColors,4);gl.depthMask(false);gl.drawArrays(gl.LINES,0,values.length/3);gl.depthMask(true);
 }
 const palettes={
  dark:{background:[.098,.110,.137],halo:'#191c23',text:'#edf0fb',ring:'#d1c5ff',
        nodes:colors,selected:[.82,.73,1],observed:[.46,.56,.69],candidate:[.57,.50,.35]},
  light:{background:[1,1,1],halo:'#fff',text:'#202738',ring:'#5941a5',
         nodes:{file:[.41,.32,.69],company:[.53,.32,.08],site:[.07,.42,.36],expected:[.50,.43,.59]},
         selected:[.35,.25,.65],observed:[.32,.40,.49],candidate:[.48,.33,.15]}
 };
 function draw(){scheduled=false;if(document.hidden||lost)return;draws++;const m=matrix();
  const palette=document.documentElement.dataset.theme==='light'?palettes.light:palettes.dark;
  gl.clearColor(...palette.background,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);lines(m,palette);
  const near=new Set([api.state.node]);for(const e of api.state.visibleEdges)if(e.from===api.state.node||e.to===api.state.node){near.add(e.from);near.add(e.to);}const chosen=api.edges.get(api.state.edge);if(chosen){near.add(chosen.from);near.add(chosen.to);}
  projected=api.state.visibleNodes.map(n=>({...project(positions.get(n.id),m),n})).sort((a,b)=>b.z-a.z);
  gl.useProgram(orb);uniforms(orb,m);attribute(orb,'position',sphere,3);gl.uniform1f(gl.getUniformLocation(orb,'viewportHeight'),gl.drawingBufferHeight);
  for(const p of projected){const selected=p.n.id===api.state.node,active=near.has(p.n.id);
   const base=((reviewing?5:1.65)+Math.min(8,Math.sqrt(neighbors.get(p.n.id).size)*.92))*(Math.min(width,height)<320?.76:1);
   const pixels=selected?Math.max(5.2,base):p.n.id===hovered?Math.max(4.5,base):base;
   const r=fitDistance*2*tan/height*pixels;p.r=r*p.scale;const depth=Math.max(.78,Math.min(1.05,distance/p.z));
   const col=palette.nodes[p.n.kind]||palette.nodes.file;gl.uniform3fv(gl.getUniformLocation(orb,'center'),positions.get(p.n.id));gl.uniform1f(gl.getUniformLocation(orb,'radius'),r);gl.uniform4fv(gl.getUniformLocation(orb,'color'),[...col.map(v=>v*depth),api.state.node&&!active?.26:.95]);gl.drawArrays(gl.POINTS,0,1);

  }
  projectedEdges=api.state.visibleEdges.map(e=>({e,a:project(positions.get(e.from),m),b:project(positions.get(e.to),m)}));
  ctx.clearRect(0,0,width,height);ctx.font='12px "Malgun Gothic", sans-serif';const placed=[];
  const candidates=projected.filter(p=>reviewing||p.n.id===api.state.node||p.n.id===hovered||p.n.id===chosen?.from||p.n.id===chosen?.to).sort((a,b)=>Number(b.n.id===api.state.node)-Number(a.n.id===api.state.node)||a.z-b.z).slice(0,reviewing?12:8);
  for(const p of candidates){let text=p.n.label;const max=Math.min(220,width-35);while(ctx.measureText(text).width>max&&text.length>3)text=text.slice(0,-2)+'…';const tw=ctx.measureText(text).width;
   const x=Math.max(10,Math.min(width-tw-14,p.x+p.r+10)),y=Math.max(47,Math.min(height-51,p.y-9));const box={x:x-5,y:y-14,w:tw+10,h:24};
   if(placed.some(b=>box.x<b.x+b.w&&box.x+box.w>b.x&&box.y<b.y+b.h&&box.y+box.h>b.y))continue;placed.push(box);ctx.lineWidth=3;ctx.strokeStyle=palette.halo;ctx.strokeText(text,x,y+3);ctx.fillStyle=palette.text;ctx.fillText(text,x,y+3);
   if(p.n.id===api.state.node){ctx.beginPath();ctx.arc(p.x,p.y,p.r+4,0,tau);ctx.strokeStyle=palette.ring;ctx.lineWidth=1.2;ctx.stroke();}
  }
  if(!drag&&(Math.abs(velocity[0])+Math.abs(velocity[1])>.0002)){yaw+=velocity[0];pitch=Math.max(-1.45,Math.min(1.45,pitch+velocity[1]));velocity=velocity.map(v=>v*.90);request();}
 }
 function hit(x,y){return projected.filter(p=>Math.hypot(p.x-x,p.y-y)<=Math.max(9,p.r+3)).sort((a,b)=>Math.hypot(a.x-x,a.y-y)-Math.hypot(b.x-x,b.y-y)||a.z-b.z)[0];}
 function edgeHit(x,y){let best=null,bestD=6;for(const p of projectedEdges){const dx=p.b.x-p.a.x,dy=p.b.y-p.a.y,len=dx*dx+dy*dy;if(!len)continue;const t=Math.max(0,Math.min(1,((x-p.a.x)*dx+(y-p.a.y)*dy)/len)),d=Math.hypot(x-p.a.x-t*dx,y-p.a.y-t*dy);if(d<bestD){best=p.e;bestD=d;}}return best;}
 const relative=event=>{const r=canvas.getBoundingClientRect();return[event.clientX-r.left,event.clientY-r.top];};
 canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;canvas.focus({preventScroll:true});canvas.setPointerCapture(e.pointerId);velocity=[0,0];drag={id:e.pointerId,last:relative(e),start:relative(e),moved:false,pan:e.shiftKey};tooltip.hidden=true;canvas.classList.add('dragging');});
 canvas.addEventListener('pointermove',e=>{const p=relative(e);if(drag&&drag.id===e.pointerId){const dx=p[0]-drag.last[0],dy=p[1]-drag.last[1];if(Math.hypot(p[0]-drag.start[0],p[1]-drag.start[1])>4)drag.moved=true;if(drag.moved){if(drag.pan){pan[0]+=dx;pan[1]+=dy;}else{velocity=[dx*.006,dy*.006];yaw+=velocity[0];pitch=Math.max(-1.45,Math.min(1.45,pitch+velocity[1]));}drag.last=p;request();}return;}
  const n=hit(...p),eHit=n?null:edgeHit(...p);hovered=n?.n.id||null;canvas.style.cursor=n||eHit?'pointer':'grab';tooltip.hidden=!(n||eHit);if(n||eHit){tooltip.textContent=n?n.n.label:api.describeEdge?.(eHit)??(eHit.label+' · '+(eHit.status==='observed'?'확인':'추정·미확정'));tooltip.style.left=Math.max(8,Math.min(width-240,p[0]+12))+'px';tooltip.style.top=Math.max(35,Math.min(height-88,p[1]-35))+'px';}request();});
 function end(e){
  if(!drag||drag.id!==e.pointerId)return;
  const [x,y]=relative(e);
  const clicked=e.type==='pointerup'&&!drag.moved&&Math.hypot(x-drag.start[0],y-drag.start[1])<=4&&x>=0&&x<width&&y>=0&&y<height;
  drag=null;canvas.classList.remove('dragging');
  if(clicked){
   const node=hit(x,y),edge=node?null:edgeHit(x,y);
   let color=colors.file;
   if(node)color=colors[node.n.kind]||colors.file;
   else if(edge)color=edge.status==='observed'?[.55,.72,1]:[.96,.72,.38];
   flash(node?.x??x,node?.y??y,color.map(value=>Math.round(value*255)).join(' '));
   if(node)api.selectNode(node.n.id,{local:false});else if(edge)api.selectEdge(edge.id);
  }
  if(e.type==='pointercancel'||reducedMotion.matches)velocity=[0,0];
  request();
 }
 canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);canvas.addEventListener('pointerleave',()=>{tooltip.hidden=true;hovered=null;request();});
 canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(Math.exp(-e.deltaY*.0015));},{passive:false});
 canvas.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','+','=','-'].includes(e.key)){e.preventDefault();velocity=[0,0];if(e.key==='Home'){yaw=.12;pitch=-.08;fit();}else if(['+','=','-'].includes(e.key))zoom(e.key==='-'?1/1.2:1.2);else{yaw+=e.key==='ArrowRight'?.12:e.key==='ArrowLeft'?-.12:0;pitch+=e.key==='ArrowDown'?.12:e.key==='ArrowUp'?-.12:0;pitch=Math.max(-1.45,Math.min(1.45,pitch));}request();}});
 reset.addEventListener('click',()=>{velocity=[0,0];yaw=.12;pitch=-.08;fit();});
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true;glowAnimation?.cancel();glow.remove();reset.remove();help.remove();if(stage!==host)tooltip.remove();host.classList.remove('has-3d');window.graph3D=null;notice.textContent='3D 관계도가 중단됐습니다. '+fallback;host.append(notice);api.fit();});
 stage.prepend(canvas,labels,glow);stage.append(help,reset);host.classList.add('has-3d');
 window.graph3D={fit,zoom,get snapshot(){return{yaw,pitch,distance,draws,visibleNodes:projected.length,webgl:true,positions:projected.map(p=>({id:p.n.id,x:p.x,y:p.y,r:p.r,z:p.z}))};}};
 document.addEventListener('axis:theme-change',request);
 document.addEventListener('axis:graph-render',request);document.addEventListener('visibilitychange',request);new ResizeObserver(()=>{resize();fit();}).observe(stage);
 api.state.local=false;document.getElementById('local').setAttribute('aria-pressed','false');api.refresh();resize();fit();
})();
