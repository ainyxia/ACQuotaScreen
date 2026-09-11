(() => {
  const body = document.body, dial = document.querySelector('#time-dial');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const histories = new Map();
  const fields = ['cpu_temp','cpu','cpu_fan','cpu_freq','gpu_temp','gpu','mb_temp','mem_temp','memory','gpu_power','upload','download'];
  let state = {}, previousView = '', previousMinute = '', lastPaint = 0;
  const motion = () => state.config?.motion_enabled !== false && !reduced.matches;
  function icon(button, name) {
    const image = document.createElement('img');
    image.src = '/static/icons/' + name + '.svg'; image.alt = '';
    button.prepend(image);
  }
  document.querySelectorAll('nav [data-page]').forEach((b,i)=>icon(b,['wallet','activity','sliders-horizontal'][i]));
  document.querySelectorAll('[data-power]').forEach((b,i)=>icon(b,['power','rotate-cw','moon'][i]));
  const label=document.createElement('label'),toggle=document.createElement('input');
  label.className='check';toggle.type='checkbox';toggle.id='motion-toggle';toggle.checked=true;
  label.append(toggle,document.createTextNode('界面动效'));document.querySelector('#appearance-dialog').append(label);
  toggle.onchange = async e => {
    try { await post('/api/appearance', {motion_enabled:e.target.checked}); await update(); }
    catch { document.querySelector('#updated').textContent='动效设置保存失败'; }
  };
  document.querySelector('#refresh').addEventListener('click',e=>{
    const button=e.currentTarget; button.classList.add('busy');setTimeout(()=>button.classList.remove('busy'),1800);
  });
  function colors() {
    const style=getComputedStyle(body);
    return ['--accent','--blue','--line','--text','--muted','--signal'].map(key=>style.getPropertyValue(key).trim());
  }
  function chart(canvas, values, color, line) {
    canvas.width=256;canvas.height=80;
    const ctx=canvas.getContext('2d');ctx.strokeStyle=line;ctx.lineWidth=1;
    for(let y=20;y<80;y+=25){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(256,y);ctx.stroke();}
    const valid=values.filter(Number.isFinite);
    if(!valid.length)return;
    const max=Math.max(1,...valid)*1.12,min=Math.min(0,...valid);
    ctx.strokeStyle=color;ctx.lineWidth=3;ctx.lineJoin='round';ctx.beginPath();let active=false;
    values.forEach((v,i)=>{if(!Number.isFinite(v)){active=false;return;}const x=4+i*248/29,y=74-(v-min)/(max-min)*66; if(active)ctx.lineTo(x,y);else ctx.moveTo(x,y);active=true;});ctx.stroke();
    const v=values.at(-1);if(Number.isFinite(v)){ctx.fillStyle=color;ctx.beginPath();ctx.arc(4+(values.length-1)*248/29,74-(v-min)/(max-min)*66,3.5,0,Math.PI*2);ctx.fill();}
  }
  document.addEventListener('screen-state', e => {
    state=e.detail;
    body.dataset.motion=motion()?'on':'off';toggle.checked=state.config.motion_enabled!==false;
    const view=state.page+body.dataset.layout+body.dataset.theme;
    if(view!==previousView){
      const main=document.querySelector('#'+state.page);
      main.classList.remove('page-enter');void main.offsetWidth;main.classList.add('page-enter');previousView=view;
    }
    const [accent,blue,line,,,signal]=colors();
    document.querySelectorAll('.sensor').forEach((el,i)=>{
      const value=state.hardware?.[fields[i]], values=histories.get(fields[i])||[];
      values.push(Number.isFinite(value)?value:null);if(values.length>30)values.shift();histories.set(fields[i],values);
      el.dataset.missing=String(!Number.isFinite(value));
      const canvas=document.createElement('canvas');canvas.setAttribute('aria-label',el.querySelector('small').textContent+'趋势');el.append(canvas);
      chart(canvas,values,i%3===2?signal:i%2?blue:accent,line);
    });
    const window=(state.quota?.windows||[]).find(w=>Number.isFinite(w.limit)&&w.limit>0&&Number.isFinite(w.used));
    document.querySelector('.balance').dataset.unavailable=String(!window);
    document.querySelector('#quota-meter-fill').style.width=window?Math.max(0,Math.min(100,(1-window.used/window.limit)*100))+'%':'0%';
    document.querySelector('#quota-meter-label').textContent=window?window.name+'可用 '+Math.round(Math.max(0,1-window.used/window.limit)*100)+'%':state.quota?'暂无周期限额':'等待额度数据';
  });
  function paint() {
    if(!dial.getClientRects().length)return;
    const ctx=dial.getContext('2d'),[accent,blue,line,textColor,muted,signal]=colors();
    const d=new Date(),seconds=d.getSeconds()+(motion()?d.getMilliseconds()/1000:0);
    ctx.clearRect(0,0,440,440);ctx.save();ctx.translate(220,220);
    const arc=(radius,start,end,color,width)=>{ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.arc(0,0,radius,start,end);ctx.stroke();};
    arc(192,0,Math.PI*2,line,1);
    for(let i=0;i<60;i++){const a=i*Math.PI/30-Math.PI/2;ctx.strokeStyle=i%5?line:muted;ctx.lineWidth=i%5?2:3;ctx.beginPath();ctx.moveTo(Math.cos(a)*(i%5?180:170),Math.sin(a)*(i%5?180:170));ctx.lineTo(Math.cos(a)*186,Math.sin(a)*186);ctx.stroke();}
    arc(158,-Math.PI/2,seconds/60*Math.PI*2-Math.PI/2,accent,5);
    ctx.fillStyle=textColor;ctx.font='500 24px Segoe UI';ctx.textAlign='center';ctx.textBaseline='middle';
    for(const [label,x,y] of [['12',0,-132],['3',132,0],['6',0,132],['9',-132,0]])ctx.fillText(label,x,y);
    const hand=(angle,len,color,width)=>{ctx.rotate(angle);ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.moveTo(0,12);ctx.lineTo(0,-len);ctx.stroke();ctx.rotate(-angle);};
    hand((d.getHours()%12+d.getMinutes()/60)*Math.PI/6,70,textColor,8);
    hand((d.getMinutes()+seconds/60)*Math.PI/30,110,blue,5);
    hand(seconds*Math.PI/30,137,accent,2);
    ctx.fillStyle=signal;ctx.beginPath();ctx.arc(0,0,7,0,Math.PI*2);ctx.fill();ctx.restore();
    const minute=d.getHours()+':'+d.getMinutes();
    if(minute!==previousMinute){const clock=document.querySelector('#big-clock');clock.classList.remove('changed');void clock.offsetWidth;clock.classList.add('changed');previousMinute=minute;}
  }
  // Match the USB display's modest refresh budget rather than rendering at 60 Hz.
  setInterval(()=>{const now=Date.now();if(!motion()&&now-lastPaint<1000)return;lastPaint=now;paint();},100);
  paint();
})();
