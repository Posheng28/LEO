// 個股細節卡（圖像化）：vizCardHTML(code) 讀 CV（co_viz.js）回傳 HTML 字串，樣式在 viz_card.css（class 一律 vz-）
(function(){
  var C={pri:'#0e6e8c',amb:'#a96812',ink:'#1c1f26',mut:'#5b6170',rule:'#e4dfd5'};
  var MIXC=['#0e6e8c','#a96812','#5b8a9a','#c9a26a','#8a8f99','#b9c7cc','#ddd3c2'];
  var KIND={'實績':{fill:C.pri,pat:0,op:1},'預估':{fill:C.pri,pat:1,op:1},'目標':{fill:C.amb,pat:1,op:1},'推算':{fill:C.pri,pat:0,op:.32}};
  var uid=0;
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  function fmt(v){return String(v);}
  function title(b){return b.t?'<div class="vz-t">'+esc(b.t)+'</div>':'';}
  function note(b){return b.note?'<div class="vz-note">'+esc(b.note)+'</div>':'';}

  function chips(b){
    return '<div class="vz-blk">'+title(b)+b.rows.map(function(r){
      return '<div class="vz-chips">'+(r.label?'<em>'+esc(r.label)+'</em>':'')+r.items.map(function(it){
        var v=typeof it==='object'?it.v:it,em=typeof it==='object'&&it.em;
        return '<span'+(em?' class="vz-em"':'')+'>'+esc(v)+'</span>';}).join('')+'</div>';}).join('')+'</div>';
  }
  function list(b){
    return '<div class="vz-blk">'+title(b)+'<ul class="vz-list">'+b.rows.map(function(r){
      return '<li>'+(r.label?'<b>'+esc(r.label)+'</b>':'')+'<span>'+esc(r.t)+'</span></li>';}).join('')+'</ul></div>';
  }
  function ring(b){
    var r=30,cx=40,cy=40,L=2*Math.PI*r,a=Math.max(0,Math.min(100,b.v))/100*L;
    var svg='<svg class="vz-ring-svg" viewBox="0 0 80 80" role="img" aria-label="'+esc((b.big||b.v+'%')+b.label)+'">'+
      '<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="'+C.rule+'" stroke-width="11"/>'+
      '<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="'+C.pri+'" stroke-width="11" stroke-dasharray="'+a.toFixed(1)+' '+L.toFixed(1)+'" transform="rotate(-90 40 40)"/></svg>';
    return '<div class="vz-blk">'+title(b)+'<div class="vz-ring">'+svg+'<div><b class="vz-num">'+esc(b.big||b.v+'%')+'</b><span>'+esc(b.label)+'</span></div></div>'+note(b)+'</div>';
  }
  function stats(b){
    return '<div class="vz-stats">'+b.rows.map(function(r){
      return '<div class="vz-tile"><span>'+esc(r.label)+'</span><b class="vz-num">'+esc(r.v)+'</b>'+(r.sub?'<small>'+esc(r.sub)+'</small>':'')+'</div>';}).join('')+'</div>';
  }
  function series(b){
    var rows=b.rows,n=rows.length,W=300,top=30,base=118,gap=n<=3?22:12,left=4;
    var bw=Math.min(60,(W-left*2-gap*(n-1))/n),tot=n*bw+(n-1)*gap,x0=(W-tot)/2;
    var mx=Math.max.apply(null,rows.map(function(r){return r.v;}))*1.08||1;
    var id='vzh'+(++uid),idA='vza'+uid;
    var defs='<defs><pattern id="'+id+'" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#fff"/><rect width="3" height="6" fill="'+C.pri+'"/></pattern>'+
      '<pattern id="'+idA+'" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#fff"/><rect width="3" height="6" fill="'+C.amb+'"/></pattern></defs>';
    var out=[];
    rows.forEach(function(r,i){
      var k=KIND[r.k]||KIND['實績'],x=x0+i*(bw+gap),h=Math.max(3,r.v/mx*(base-top)),y=base-h;
      var fill=k.pat?('url(#'+(r.k==='目標'?idA:id)+')'):k.fill;
      out.push('<rect x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h.toFixed(1)+'" rx="2" fill="'+fill+'" fill-opacity="'+k.op+'"'+(k.pat?' stroke="'+(r.k==='目標'?C.amb:C.pri)+'" stroke-width="1"':'')+'/>');
      out.push('<text x="'+(x+bw/2).toFixed(1)+'" y="'+(y-6).toFixed(1)+'" class="vz-sv" text-anchor="middle">'+esc(fmt(r.v))+(b.unit||'')+'</text>');
      out.push('<text x="'+(x+bw/2).toFixed(1)+'" y="'+(base+17)+'" class="vz-sl" text-anchor="middle">'+esc(r.label)+'</text>');
    });
    out.push('<line x1="0" y1="'+base+'" x2="'+W+'" y2="'+base+'" stroke="'+C.rule+'"/>');
    var seen=[];rows.forEach(function(r){if(seen.indexOf(r.k)<0)seen.push(r.k);});
    var leg='<div class="vz-leg">'+seen.map(function(k){return '<span class="vz-k-'+({'實績':'a','預估':'e','目標':'g','推算':'c'})[k]+'"><i></i>'+esc(k)+'</span>';}).join('')+'</div>';
    var alt=(b.t||'')+'：'+rows.map(function(r){return r.label+' '+r.v+(b.unit||'')+'（'+r.k+'）';}).join('、');
    return '<div class="vz-blk">'+title(b)+'<svg class="vz-series" viewBox="0 0 '+W+' '+(base+24)+'" role="img" aria-label="'+esc(alt)+'">'+defs+out.join('')+'</svg>'+leg+note(b)+'</div>';
  }
  function road(b){
    return '<div class="vz-blk">'+title(b)+b.rows.map(function(r){
      return '<div class="vz-road">'+(r.label?'<em>'+esc(r.label)+'</em>':'')+r.nodes.map(function(nd){
        return '<div class="vz-node"><span'+(nd.em?' class="vz-em"':'')+'><b class="vz-num">'+esc(nd.v)+'</b>'+(nd.sub?'<small>'+esc(nd.sub)+'</small>':'')+'</span></div>';}).join('')+'</div>';}).join('')+note(b)+'</div>';
  }
  function mix(b){
    var sum=b.rows.reduce(function(a,r){return a+r[1];},0)||1;
    var bar='<div class="vz-mixbar" role="img" aria-label="'+esc((b.t||'')+'：'+b.rows.map(function(r){return r[0]+' '+r[1]+'%';}).join('、'))+'">'+b.rows.map(function(r,i){
      return '<i style="width:'+(r[1]/sum*100).toFixed(2)+'%;background:'+MIXC[i%MIXC.length]+'"></i>';}).join('')+'</div>';
    var leg='<ul class="vz-mixleg">'+b.rows.map(function(r,i){
      return '<li><i style="background:'+MIXC[i%MIXC.length]+'"></i><span>'+esc(r[0])+'</span><b>'+esc(fmt(r[1]))+'%</b></li>';}).join('')+'</ul>';
    return '<div class="vz-blk">'+title(b)+bar+leg+note(b)+'</div>';
  }
  function tl(b){
    var rows=b.rows.filter(function(r){return r.d;}).concat(b.rows.filter(function(r){return !r.d;}));
    return '<div class="vz-blk">'+title(b)+'<div class="vz-tl">'+rows.map(function(r){
      return '<div class="vz-tlr'+(r.d?'':' vz-nod')+'">'+(r.d?'<time>'+esc(r.d)+'</time>':'<time>—</time>')+'<p>'+esc(r.t)+'</p></div>';}).join('')+'</div></div>';
  }
  function gap(b){return '<div class="vz-gap"><b>數字不一致</b><span>'+esc(b.t)+'</span></div>';}
  var K={chips:chips,list:list,ring:ring,stats:stats,series:series,road:road,mix:mix,tl:tl,gap:gap};

  // 數字性質小標籤：公司資料／券商或報導＝有人給數字（實色），推算＝斜紋；樣式 vz-conf、vz-conf-a/b/c
  function confTag(c){
    if(!c)return '';
    var m={'公司資料':'a','券商或報導':'b','推算':'c'}[c]||'b';
    return '<span class="vz-conf vz-conf-'+m+'" title="數字性質">'+esc(c)+'</span>';
  }
  function sec(name,blocks,tag){
    if(!blocks||!blocks.length)return '';
    var st=blocks.filter(function(b){return b.k==='stats';}),rest=blocks.filter(function(b){return b.k!=='stats';});
    return '<section class="vz-sec"><h4 class="vz-h">'+name+(tag||'')+'</h4>'+st.concat(rest).map(function(b){return (K[b.k]||function(){return '';})(b);}).join('')+'</section>';
  }
  window.vizCardHTML=function(code){
    var d=(typeof CV!=='undefined')&&CV[code];
    if(!d)return '';
    return '<div class="vz-card"><div class="vz-grid">'+sec('產品與客戶',d.pc)+sec('量化數字',d.q,confTag(d.conf))+sec('接下來看與風險',d.nr)+'</div></div>';
  };
})();
