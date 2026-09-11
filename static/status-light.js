(() => {
 const style=document.createElement('link');style.rel='stylesheet';style.href='/static/status-light.css';document.head.append(style);
 const edge=document.createElement('div');edge.id='codex-edge';edge.setAttribute('aria-hidden','true');
 for(const side of ['top','right','bottom','left']){const strip=document.createElement('i');strip.className=side;edge.append(strip)}
 document.body.append(edge);
 const badge=document.createElement('span');badge.id='codex-status';badge.setAttribute('role','status');
 document.querySelector('header').insertBefore(badge,document.querySelector('.screen-tools'));
 const label=document.createElement('label'),toggle=document.createElement('input');label.className='check';toggle.type='checkbox';toggle.checked=true;
 label.append(toggle,document.createTextNode('Codex 工作状态灯'));document.querySelector('#appearance-dialog').append(label);
 toggle.onchange=async()=>{try{await post('/api/appearance',{status_light_enabled:toggle.checked});await update()}catch{badge.textContent='设置失败'}};
 const labels={working:'工作中',waiting:'等待确认',complete:'已完成',error:'任务出错',idle:'待机',unknown:'状态未知'};
 let last=Date.now();
 function show(value){edge.dataset.status=value;badge.dataset.status=value;badge.textContent='Codex · '+labels[value]}
 document.addEventListener('screen-state',e=>{
   last=Date.now();const data=e.detail,enabled=data.config.status_light_enabled!==false;
   toggle.checked=enabled;edge.hidden=!enabled;badge.hidden=!enabled;
   const status=data.codex?.status;show(Object.hasOwn(labels,status)?status:'unknown');
   badge.title='本机任务事件；'+(data.codex?.active_tasks||0)+' 个活跃任务';
 });
 // A disconnected local service must never leave a stale green or working light.
 setInterval(()=>{if(Date.now()-last>6000)show('unknown')},2000);show('unknown');
})();
