document.addEventListener('DOMContentLoaded',()=>{
 const section=document.createElement('section');section.id='desktop-settings';
 const title=document.createElement('h2');title.textContent='桌面应用';section.append(title);
 const label=document.createElement('label'),startup=document.createElement('input');label.className='check';startup.type='checkbox';label.append(startup,document.createTextNode('开机自启并启动副屏'));section.append(label);
 const protocol=document.createElement('button');section.append(protocol);
 document.querySelector('main.console').append(section);
 let installed={};
 async function sync(){installed=await(await fetch('/api/desktop/settings')).json();startup.checked=installed.autostart;protocol.textContent=installed.ccs_default?'恢复原 CCS 接收应用':'设为 CCS 导入接收应用';startup.disabled=protocol.disabled=!installed.installed;}
 startup.onchange=action(async()=>{await post('/api/desktop/settings',{autostart:startup.checked});await sync();notice(startup.checked?'已开启开机自启':'已关闭开机自启')});
 protocol.onclick=action(async()=>{const enable=!installed.ccs_default;if(!confirm(enable?'将网站的 CCS 导入链接交给 AC 副屏？原接收应用的关联会备份，可以恢复。':'恢复原来的 CCS 接收应用？'))return;await post('/api/desktop/settings',{ccs_default:enable});await sync();notice('已更新导入关联')});
 const dialog=document.createElement('dialog'),heading=document.createElement('h2'),name=document.createElement('p'),endpoint=document.createElement('p'),ok=document.createElement('button'),cancel=document.createElement('button');
 heading.textContent='导入中转站配置';ok.textContent='确认导入';cancel.textContent='取消';endpoint.style.overflowWrap='anywhere';dialog.style.maxWidth='480px';dialog.append(heading,name,endpoint,ok,cancel);document.body.append(dialog);
 let pending=null,busy=false;
 async function finish(action){if(!pending)return;await post('/api/desktop/import/'+action,{id:pending.id});dialog.close();pending=null;await load(true);}
 ok.onclick=action(()=>finish('confirm'));cancel.onclick=action(()=>finish('cancel'));dialog.oncancel=e=>{e.preventDefault();finish('cancel').catch(()=>notice('取消失败'))};
 async function events(){if(busy)return;busy=true;try{const data=await(await fetch('/api/desktop/events')).json();if(data.pending&&data.pending.id!==pending?.id){pending=data.pending;name.textContent=pending.name;endpoint.textContent=pending.base_url;if(!dialog.open)dialog.showModal();}else if(!data.pending){pending=null;if(dialog.open)dialog.close();}}finally{busy=false}}
 sync().catch(()=>notice('桌面设置读取失败'));events().catch(()=>{});setInterval(()=>events().catch(()=>{}),1000);
});
