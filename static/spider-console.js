document.addEventListener('DOMContentLoaded',()=>{
 const button=document.createElement('button');button.className='theme-choice';button.dataset.themeChoice='spider';
 const image=document.createElement('img');image.src='/static/previews/spider.png';image.alt='蛛网战衣仪表';
 const title=document.createElement('span');title.textContent='蛛网战衣 · 红黑科技';button.append(image,title);
 button.onclick=action(async()=>{await post('/api/appearance',{theme:'spider'});await load();notice('已切换蛛网战衣')});
 document.querySelector('#theme-gallery').prepend(button);
});
