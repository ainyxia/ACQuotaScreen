(() => {
 const style=document.createElement('link');style.rel='stylesheet';style.href='/static/spider.css';document.head.insertBefore(style,document.querySelector('#theme'));
 const panel=document.createElement('section');panel.id='spider-cockpit';
 const canvas=document.createElement('canvas');canvas.width=1920;canvas.height=520;canvas.setAttribute('aria-label','蛛网战衣仪表：CPU 占用、剩余额度、GPU 占用');panel.append(canvas);
 document.querySelector('#quota').append(panel);
 const button=document.createElement('button');button.textContent='蛛网战衣';button.dataset.themeChoice='spider';
 button.onclick=()=>post('/api/appearance',{theme:'spider'}).then(update);document.querySelector('#screen-themes').prepend(button);
 const ctx=canvas.getContext('2d'), values=[null,null,null];let state={},stamp=0;
 const valid=Number.isFinite;
 document.addEventListener('screen-state',e=>{state=e.detail;canvas.setAttribute('aria-label',`CPU 占用 ${state.hardware?.cpu??'不可用'}%，剩余额度 ${state.quota?.remaining??'不可用'}，GPU 占用 ${state.hardware?.gpu??'不可用'}%`)});
 function text(s,x,y,size,color='#f5f7fa',align='center') {ctx.fillStyle=color;ctx.font=`600 ${size}px "Segoe UI","Microsoft YaHei",sans-serif`;if(size>=30){while(ctx.measureText(s).width>155&&size>14){size--;ctx.font=`600 ${size}px "Segoe UI","Microsoft YaHei",sans-serif`;}}ctx.textAlign=align;ctx.textBaseline='middle';ctx.fillText(s,x,y);}
 function line(x,y,x2,y2,color,width=1){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x2,y2);ctx.stroke()}
 function arc(x,y,r,a,b,color,width){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.arc(x,y,r,a,b);ctx.stroke()}
 function dial(x,y,r,value,label,sub,color,index,target,number){
  const start=Math.PI*.75,span=Math.PI*1.5;
  arc(x,y,r+10,0,Math.PI*2,'#34313f',1);arc(x,y,r-7,start,start+span,'#282933',12);
  for(let i=0;i<51;i++){let a=start+i/50*span;line(x+Math.cos(a)*(r-25),y+Math.sin(a)*(r-25),x+Math.cos(a)*(r-(i%5?32:40)),y+Math.sin(a)*(r-(i%5?32:40)),i/50<value?color:'#52505c',i%5?1.5:3);}
  if(valid(target))arc(x,y,r-7,start,start+span*value,color,10);
  for(let i=0;i<=4;i++){const a=start+i/4*span;text(String(i*25),x+Math.cos(a)*(r-54),y+Math.sin(a)*(r-54),9,'#8c929e')}
  if(valid(target)){const a=start+span*value;ctx.save();ctx.translate(x,y);ctx.rotate(a);ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(r-19,0);ctx.lineTo(r-43,-5);ctx.lineTo(r-43,5);ctx.closePath();ctx.fill();ctx.restore()}
  text(label,x,y-31,11,color);text(number,x,y+3,index===1?31:37);text(sub,x,y+33,10,'#969ca9');
  line(x-34,y+r-22,x+34,y+r-22,color,2);
 }
 function paint(now){
  if(document.body.dataset.theme!=='spider'||state.page!=='quota'||!panel.getClientRects().length)return;
  const mobile=innerWidth<700,w=mobile?360:960,h=mobile?810:260;
  if(canvas.width!==w*2||canvas.height!==h*2){canvas.width=w*2;canvas.height=h*2;}
  ctx.setTransform(2,0,0,2,0,0);ctx.clearRect(0,0,w,h);ctx.fillStyle='#0b0d13';ctx.fillRect(0,0,w,h);
  const cx=mobile?180:480,cy=mobile?375:130;
  // A radial web provides the suit texture, not invented sensor activity.
  for(let i=0;i<24;i++){let a=i*Math.PI/12;line(cx,cy,cx+Math.cos(a)*1000,cy+Math.sin(a)*1000,'#29202c')}
  for(let r=60;r<1050;r+=58){ctx.beginPath();ctx.strokeStyle='#29202c';ctx.lineWidth=1;for(let i=0;i<=24;i++){const a=i*Math.PI/12;const x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}ctx.stroke()}
  const motion=state.config?.motion_enabled!==false&&!matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(motion){const x=(now/30)%(w+150)-150;ctx.fillStyle='#4be3ff0a';ctx.fillRect(x,0,65,h);line(x+65,0,x+65,h,'#4be3ff22')}
  const q=state.quota,hware=state.hardware||{},window=q?.windows?.find(v=>valid(v.limit)&&v.limit>0&&valid(v.used));
  const targets=[valid(hware.cpu)?hware.cpu/100:null,window?Math.max(0,Math.min(1,1-window.used/window.limit)):null,valid(hware.gpu)?hware.gpu/100:null];
  targets.forEach((v,i)=>{values[i]=v==null?null:values[i]==null||!motion?v:values[i]+(v-values[i])*.22});
  const money=q?.remaining===-1?'不限额':valid(q?.remaining)?q.remaining.toLocaleString('en-US',{maximumFractionDigits:2}):'--';
  const positions=mobile?[[180,152,110],[180,397,124],[180,651,110]]:[[190,130,107],[480,133,119],[770,130,107]];
  positions.forEach(([x,y,r],i)=>dial(x,y,r,values[i]??0,['CPU / PROCESSOR','WEB RESERVE','GPU / GRAPHICS'][i],i===1?(state.error?'额度未同步':window?window.name+'可用 · '+Math.round(targets[1]*100)+'%':q?.unit||'USD'):(i===0?valid(hware.cpu_temp)?hware.cpu_temp+' °C':'温度不可用':valid(hware.gpu_temp)?hware.gpu_temp+' °C':'温度不可用'),['#ff455c','#f3485f','#46d9f4'][i],i,targets[i],i===1?money:valid(targets[i])?Math.round(targets[i]*100)+'%':'--'));
  // White eye lenses and red framing establish the Spider-Man visual identity.
  const ex=mobile?180:480,ey=mobile?18:12;ctx.save();ctx.translate(ex,ey);for(const sign of [-1,1]){ctx.save();ctx.scale(sign,1);ctx.fillStyle='#ecf7fc';ctx.strokeStyle='#ef364f';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(3,8);ctx.lineTo(38,0);ctx.quadraticCurveTo(29,30,8,20);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore()}ctx.restore();
  for(const x of [12,w-12]){line(x,12,x,44,'#f3485f',3);line(x,h-44,x,h-12,'#f3485f',3)}
  if(!mobile){text('SUIT / 01',27,18,9,'#858d9b','left');text('蛛网战衣',w-28,18,10,'#858d9b','right');text('内存 '+(valid(hware.memory)?hware.memory.toFixed(1)+'%':'--'),28,h-17,10,'#939aa8','left');text('↓ '+(valid(hware.download)?hware.download.toFixed(2)+' MB/s':'--'),w-28,h-17,10,'#939aa8','right')}
 }
 setInterval(()=>{stamp=performance.now();paint(stamp)},100);
})();
