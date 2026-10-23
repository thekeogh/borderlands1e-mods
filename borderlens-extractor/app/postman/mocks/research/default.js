// Local contract examples only. No claim that these are scraped production pages.
const http=require('node:http');
http.createServer((req,res)=>{const u=new URL(req.url,'http://local');
 if(u.pathname==='/robots.txt'){res.setHeader('content-type','text/plain');res.end('User-agent: *\nDisallow: /wiki/blocked\n');return;}
 if(u.pathname==='/wiki/denied'){res.writeHead(403,{'content-type':'text/html'});res.end('<html>Forbidden</html>');return;}
 if(u.pathname==='/wiki/upstream-fail'){res.writeHead(503,{'content-type':'text/html'});res.end('<html>Temporary source failure</html>');return;}
 if(u.pathname==='/api.php'){const list=u.searchParams.get('cmtitle')||'';const second=u.searchParams.has('cmcontinue');const data=list==='Category:Weapons_in_Borderlands'?second?{query:{categorymembers:[{pageid:2,ns:0,title:'Thunder'}]}}:{continue:{cmcontinue:'next'},query:{categorymembers:[{pageid:1,ns:0,title:'Hellfire (Borderlands)'}]}}:{query:{categorymembers:[]}};res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(data));return;}
 if(/^\/db\/borderlands-1\//.test(u.pathname)){res.writeHead(200,{'content-type':'text/html'});res.end('<html><main><h1>Borderlands 1 weapons</h1><a href="/weapon/hellfire-bl1"><h3>Hellfire</h3></a></main></html>');return;}
 if(u.pathname==='/wiki/Hellfire_(Borderlands)'||u.pathname==='/weapon/hellfire-bl1'){res.writeHead(200,{'content-type':'text/html'});res.end('<html><main><h1>Hellfire (Borderlands)</h1><p>Contract fixture for a Borderlands 1 Maliwan incendiary SMG. This text is test evidence only, not a real scraped article.</p></main></html>');return;}
 res.writeHead(501,{'content-type':'application/json'});res.end(JSON.stringify({error:'Endpoint not modeled by this research contract fixture.'}));
}).listen(process.env.PORT);
