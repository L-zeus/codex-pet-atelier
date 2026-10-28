// Offline interaction checks for the real preview script; no browser or account needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag = 'div') { this.tagName = tag.toUpperCase(); this.children = []; this.handlers = {}; this.dataset = {}; this.style = {setProperty(k,v){this[k]=v;}}; this.attrs = {}; this.hidden = false; this.textContent = ''; this.classList = {toggle(){}}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  async emit(type, extra = {}) { for (const fn of this.handlers[type] || []) await fn({target:this, currentTarget:this, preventDefault(){}, ...extra}); }
  setAttribute(k,v) { this.attrs[k] = v; }
  querySelectorAll(selector) { return this.children.flatMap(c => [...(c.tagName.toLowerCase() === selector ? [c] : []), ...c.querySelectorAll(selector)]); }
  querySelector(selector) { return this.querySelectorAll(selector)[0]; }
  focus() { document.activeElement = this; }
  getBoundingClientRect() { return {left:10, bottom:300, width:178, height:400}; }
  contains(target) { return target === this || this.children.some(c => c.contains(target)); }
  click() { this.clicked = true; }
}
const ids = ['canvas','pet','action-menu','usage-card','pet-tabs','pet-inputs','missing','current-action','play-toggle','loop','replay','idle','menu-open','scale','stage','usage-content','usage-open','usage-close','usage-import','usage-file','initial-pets'];
const els = Object.fromEntries(ids.map(id => [id,new Element()]));
els['action-menu'].hidden = els['usage-card'].hidden = true;
els.loop.checked = true;
els['initial-pets'].textContent = JSON.stringify([{src:'a.webp'},{src:'b.webp'},{src:'c.webp'}]);
let draws = [];
els.canvas.getContext = () => ({clearRect(){}, drawImage(...args){draws.push(args);}});
const bg = [new Element('button'), new Element('button')]; bg[0].dataset.bg = 'light'; bg[1].dataset.bg = 'dark';
const document = {activeElement:null, handlers:{}, getElementById:id => els[id] || null, createElement:tag => new Element(tag), querySelectorAll:selector => selector === '.bg-button' ? bg : [], addEventListener(type,fn){(this.handlers[type] ||= []).push(fn);}, async emit(type,extra={}){for(const fn of this.handlers[type]||[]) await fn({target:this,preventDefault(){},...extra});}};
let callbacks = new Map(), nextId = 0, clock = 0, lastDelay;
class FakeImage { constructor(){this.naturalWidth=1536;this.naturalHeight=1872;} set src(value){this._src=value; if(this.onload)this.onload();} }
const context = {document, Image:FakeImage, matchMedia:() => ({matches:false}), URL:{createObjectURL:()=> 'blob:asset',revokeObjectURL(){}}, performance:{now:()=>clock}, innerWidth:800, innerHeight:600, setTimeout(fn,delay){let id=++nextId;callbacks.set(id,fn);lastDelay=delay;return id;},clearTimeout(id){callbacks.delete(id);}, Date, JSON, Math, Number, String, Array};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../preview/app.js'),'utf8'), context);
function tick() { const [id,fn] = callbacks.entries().next().value; callbacks.delete(id); clock += lastDelay; fn(); }
function visibleText(node) { return node.textContent + node.children.map(visibleText).join(' '); }
(async () => {
  assert.equal(els['pet-tabs'].children.length, 3);
  assert.equal(els['action-menu'].children.length, 9);
  const timings = [[280,110,110,140,140,320], [120,120,120,120,120,120,120,220],
    [120,120,120,120,120,120,120,220], [140,140,140,280], [140,140,140,140,280],
    [140,140,140,140,140,140,140,240], [150,150,150,150,150,260],
    [120,120,120,120,120,220], [150,150,150,150,150,280]];
  for(let character=0; character<3; character++) {
    await els['pet-tabs'].children[character].emit('click');
    assert.equal(els.pet.dataset.pet, String(character));
    assert.equal(els.pet.dataset.state, 'idle');
    for(let motion=0; motion<9; motion++) {
      await els['action-menu'].children[motion].emit('click');
      assert.equal(els.pet.dataset.frame,'0');
      assert.equal(lastDelay,timings[motion][0]);
      assert.equal(draws.at(-1)[1],0);
      assert.equal(draws.at(-1)[2],motion*208);
      const before = draws.length;
      tick();
      assert.equal(els.pet.dataset.frame,'1');
      assert.equal(lastDelay,timings[motion][1]);
      assert.ok(draws.length > before);
      assert.equal(draws.at(-1)[1],192);
      for(let n=2;n<timings[motion].length;n++) { tick(); assert.equal(lastDelay,timings[motion][n]); }
      tick();
      assert.equal(els.pet.dataset.frame,'0');
      assert.equal(lastDelay,timings[motion][0]);
    }
  }
  await els.pet.emit('contextmenu',{clientX:799,clientY:599});
  assert.equal(els['action-menu'].hidden,false);
  assert.equal(els['action-menu'].style.left,'614px');
  assert.equal(els['action-menu'].style.top,'192px');
  await els['action-menu'].emit('keydown',{key:'ArrowDown'});
  assert.equal(document.activeElement, els['action-menu'].children[0]);
  await document.emit('keydown',{key:'Escape'});
  assert.equal(els['action-menu'].hidden,true);
  await els.pet.emit('contextmenu',{clientX:20,clientY:20});
  await document.emit('pointerdown',{target:new Element()});
  assert.equal(els['action-menu'].hidden,true);
  await els.pet.emit('dblclick');
  assert.equal(els['usage-card'].hidden,false);
  assert.match(visibleText(els['usage-content']),/尚未读取额度/);
  els['usage-file'].files=[{size:300,text:async()=>JSON.stringify({status:'ok',source:'Codex App Server account/rateLimits/read',fetchedAt:new Date().toISOString(),buckets:[{id:'codex',windows:[{usedPercent:25,durationMins:300,resetsAt:2000000000}]}],resetCreditsAvailable:2})}];
  await els['usage-file'].emit('change');
  assert.match(visibleText(els['usage-content']),/剩余 75%/);
  assert.match(visibleText(els['usage-content']),/已用 25%/);
  assert.match(visibleText(els['usage-content']),/重置次数：2/);
  els['usage-file'].files=[{size:300,text:async()=>JSON.stringify({status:'ok',source:'Codex App Server account/rateLimits/read',fetchedAt:'2020-01-01T00:00:00Z',buckets:[{id:'codex',windows:[{usedPercent:25,durationMins:300,resetsAt:1577836800}]}]})}];
  await els['usage-file'].emit('change');
  assert.match(visibleText(els['usage-content']),/快照已过期/);
  assert.match(visibleText(els['usage-content']),/重置时间已过/);
  await els['usage-import'].emit('click'); assert.equal(els['usage-file'].clicked,true);
  await document.emit('keydown',{key:'Escape'}); assert.equal(els['usage-card'].hidden,true);
  await els['play-toggle'].emit('click'); assert.equal(callbacks.size,0);
  await els['play-toggle'].emit('click'); assert.equal(callbacks.size,1);
  els.loop.checked = false;
  await els['action-menu'].children[3].emit('click');
  for (let i=0; i<4; i++) tick();
  assert.equal(els.pet.dataset.frame,'3'); assert.equal(callbacks.size,0);
  await els.replay.emit('click'); assert.equal(els.pet.dataset.frame,'0'); assert.equal(callbacks.size,1);
  els.loop.checked = true;
  await els.idle.emit('click'); assert.equal(els.pet.dataset.state,'idle');
  await els.scale.emit('input',{target:{value:'160'}}); assert.equal(els.pet.style['--pet-scale'],1.6);
  console.log('PASS: 3 characters × 9 rows select, draw and advance; controls, menu, and synthetic snapshot');
})().catch(error => {console.error(error); process.exitCode=1;});
