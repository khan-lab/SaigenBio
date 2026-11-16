"use strict";

// Presentation aliases never change execution records. Each viewer owns its aliases.
globalThis.SaigenPaths = Object.freeze({create(getFlow,getProjectRoot){
// Path abbreviations affect presentation only; the execution record is untouched.
const externalDirectories=new Map();
const absolutePath=v=>typeof v==="string"&&/^(?:\/(?!\/)|[A-Za-z]:[\\/]|\\\\)/.test(v);
const slashPath=v=>String(v||"").replace(/\\/g,"/").replace(/\/+$/,"");
const pathBase=v=>slashPath(v).split("/").at(-1);
const pathParent=v=>slashPath(v).split("/").slice(0,-1).join("/");
const below=(path,root)=>!!root&&root!=="/"&&(path===root||path.startsWith(root+"/"));
function pathRoots(action){
 const roots=[],add=(root,alias)=>{root=slashPath(root);if(root&&root!=="/"&&!roots.some(r=>r.root===root))roots.push({root,alias});};
 const inferred=getFlow().actions.map(a=>a.cwd).find(p=>p&&slashPath(p).includes("/.saigen/runs/"));
 add(action?.cwd&&slashPath(action.cwd).includes("/.saigen/runs/")?action.cwd:"","{run}");
 add(getProjectRoot()||(inferred?slashPath(inferred).split("/.saigen/runs/")[0]:""),".");
 const repositories=[...new Set([...getFlow().actions.map(a=>a.code?.repository),...getFlow().states.map(n=>n.code?.repository)].filter(Boolean))].sort();
 repositories.forEach((root,i)=>add(root,repositories.length===1?"{source}":"{source:"+(i+1)+"}"));
 const scriptDirs=[...new Set(Object.values(getFlow().artifacts).filter(f=>f.role==="code"&&absolutePath(f.sourcePath)).map(f=>pathParent(f.sourcePath)))].sort().filter(dir=>!roots.some(r=>below(dir,r.root)));
 scriptDirs.forEach((root,i)=>add(root,scriptDirs.length===1?"{scripts}":"{scripts:"+(i+1)+"}"));
 return roots.sort((a,b)=>b.root.length-a.root.length);
}
function displayPath(value,action){
 if(!absolutePath(value))return String(value??"");
 const path=slashPath(value),match=pathRoots(action).find(r=>below(path,r.root));
 if(match)return match.alias+path.slice(match.root.length);
 const dir=pathParent(path);
 if(!externalDirectories.has(dir))externalDirectories.set(dir,externalDirectories.size+1);
 return "{external:"+externalDirectories.get(dir)+"}/"+pathBase(path);
}
function displayText(value,action){
 let out=String(value??"");
 for(const {root,alias} of pathRoots(action)){
   const escaped=root.replace(/[.*+?^$(){}|[\]\\]/g,"\\$&");
   out=out.replace(new RegExp('(^|[\\s="\\x27(])'+escaped+'(?=$|[/\\\\\\s"\\x27,;()\\]}])',"g"),(_,lead)=>lead+alias);
 }
 out=out.replace(/(["'])((?:\/(?!\/)|[A-Za-z]:[\\/])[^"'\r\n<>|;&]+)\1/g,(_,quote,path)=>quote+displayPath(path,action)+quote);
 return out.replace(/(^|[\s="'(])((?:\/(?!\/)|[A-Za-z]:[\\/])[^\s"'<>|;&)]+)/g,(_,lead,path)=>lead+displayPath(path,action));
}
function displayArgument(value,action,index){
 if(index===0&&absolutePath(value))return pathBase(value);
 if(absolutePath(value))return displayPath(value,action);
 const assignment=value.match(/^([^=]+=)((?:\/(?!\/)|[A-Za-z]:[\\/]).+)$/);
 return assignment?assignment[1]+displayPath(assignment[2],action):displayText(value,action);
}
function shellQuote(value){
 return /^[a-zA-Z0-9_./:{}=@,+%-]+$/.test(value)?value:"'"+value.replace(/'/g,"'\\''")+"'";
}
function displayCommand(action){
 if(action.terminal)return action.terminal.commands.map(c=>displayText(c.command,c)).join("\n")||"No shell commands in this saved step";
 if(!Array.isArray(action.argv)||!action.argv.length)return displayText(action.command||"Command not specified",action);
 return action.argv.map((value,i)=>{
   const prefix=i===0?"":/^--?[a-zA-Z]/.test(value)?" \\\n  ":" ";
   return prefix+shellQuote(displayArgument(value,action,i));
 }).join("");
}
function displayRecord(value,action,key=""){
 if(Array.isArray(value))return key==="argv"?value.map((v,i)=>displayArgument(v,action,i)):value.map(v=>displayRecord(v,action));
 if(value&&typeof value==="object"){
   const context=Array.isArray(value.argv)?value:action;
   return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,displayRecord(v,context,k)]));
 }
 if(typeof value==="string"){
   if(["sourcePath","cwd","repository","executable","workdir"].includes(key))return displayPath(value,action);
   if(key==="command"&&action?.argv)return displayCommand(action);
   return displayText(value,action);
 }
 return value;
}
return Object.freeze({displayPath,displayText,displayCommand,displayRecord});
}});
