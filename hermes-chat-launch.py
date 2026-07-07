#!/usr/bin/env python3
"""HERMES AGENT v3 — ChatGPT-стиль + чаты + память + скиллы."""
import os, json, base64, re, webbrowser, threading, time, uuid, datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

DIR = Path(__file__).resolve().parent
DATA = DIR / "hermes-data"
ENV = DATA / ".env"
SESSIONS_DIR = DATA / "sessions"
MEMORY_FILE = DATA / "memories" / "MEMORY.md"
SKILLS_DIR = DATA / "skills"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODELS = [
    {"id": "meta-llama/llama-3.3-70b-instruct",     "name": "Llama 3.3 70B",    "ctx": "131K", "tag": "Универсальная"},
    {"id": "qwen/qwen-2.5-coder-32b-instruct",     "name": "Qwen 2.5 Coder 32B","ctx": "128K", "tag": "Код"},
    {"id": "deepseek/deepseek-chat",                 "name": "DeepSeek Chat",    "ctx": "128K", "tag": "Умная"},
    {"id": "mistralai/mistral-large",                "name": "Mistral Large",    "ctx": "128K", "tag": "Быстрая"},
    {"id": "nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron 120B",    "ctx": "1M",   "tag": "Мощная"},
    {"id": "google/gemma-4-31b-it:free",             "name": "Gemma 4 31B",      "ctx": "262K", "tag": "Google"},
    {"id": "nvidia/nemotron-3-nano-30b-a3b:free",    "name": "Nemotron 30B",     "ctx": "256K", "tag": "Быстрая"},
]
DEFAULT = MODELS[0]["id"]

def load_key():
    if not ENV.exists(): return None
    for line in ENV.read_text().splitlines():
        m = re.match(r'\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*["\']?(.*?)["\']?\s*$', line)
        if m and m.group(1).strip(): return m.group(1).strip()
    return None
KEY = load_key()

# ─── sessions ───
def _list_sessions():
    res = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            d = json.loads(f.read_text())
            res.append({
                "id": f.stem,
                "name": d.get("name", "Чат"),
                "model": d.get("model", ""),
                "created": d.get("created", ""),
                "updated": d.get("updated", ""),
                "msg_count": len(d.get("messages", [])),
                "preview": d["messages"][-1]["content"][:70] if d.get("messages") else ""
            })
        except: pass
    return res

def _load_session(sid):
    p = SESSIONS_DIR / f"{sid}.json"
    return json.loads(p.read_text()) if p.exists() else None

def _save_session(sid, data):
    (SESSIONS_DIR / f"{sid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))

# ─── memory ───
def _read_memory():
    if MEMORY_FILE.exists():
        return MEMORY_FILE.read_text(encoding="utf-8")
    return "# Память\n\nПусто."

def _write_memory(c):
    MEMORY_FILE.write_text(c, encoding="utf-8")

# ─── skills ───
def _list_skills():
    if not SKILLS_DIR.exists(): return []
    out = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."): continue
        sf = d / "SKILL.md"
        if sf.exists():
            txt = sf.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'Use this skill when\s*(.+?)(?:\n|$)', txt, re.IGNORECASE)
            desc = m.group(1).strip() if m else txt[:120].strip()
            out.append({"name": d.name, "desc": desc[:200]})
    return out

def _get_skill(name):
    sf = SKILLS_DIR / name / "SKILL.md"
    return sf.read_text(encoding="utf-8", errors="replace") if sf.exists() else None

def _build_system(skills_enabled, use_memory):
    parts = ["Ты — Hermes Agent. Отвечай на русском языке, полезно и по делу."]
    if use_memory:
        mem = _read_memory()
        if mem.strip() and mem != "# Память\n\nПусто.":
            parts.append(f"\n## ПАМЯТЬ\n{mem[:3000]}")
    if skills_enabled:
        parts.append("\n## НАВЫКИ\nВыбери нужный навык по описанию и следуй его инструкциям:\n")
        for nm in skills_enabled:
            c = _get_skill(nm)
            if c:
                m = re.search(r'Use this skill when\s*(.+?)(?:\n|$)', c, re.IGNORECASE)
                parts.append(f"- **{nm}**: {(m.group(1).strip() if m else nm)}")
    return "\n".join(parts)

# ══════════════════════════════════════════════════════════════════
#  HTML — ChatGPT-стиль
# ══════════════════════════════════════════════════════════════════
PAGE = r'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hermes AI</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#212121; --surface:#171717; --surface2:#2a2a2a; --surface3:#333;
  --border:#383838; --border2:#444;
  --text:#ececec; --text2:#b4b4b4; --text3:#8e8e8e; --text4:#666;
  --accent:#a78bfa; --accent2:#c4b5fd; --accent-bg:rgba(167,139,250,.08);
  --green:#4ade80; --red:#f87171;
  --r:10px; --r2:6px;
  --sidebar:280px
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,sans-serif;
  background:var(--bg);color:var(--text);height:100vh;overflow:hidden}
.app{display:flex;height:100vh}

/* ── sidebar ── */
.sb{width:var(--sidebar);background:var(--surface);display:flex;flex-direction:column;flex-shrink:0;
  border-right:1px solid var(--border)}

.sb-head{padding:14px 14px 8px;display:flex;align-items:center;gap:8px}
.sb-head .logo{width:28px;height:28px;background:linear-gradient(135deg,#a78bfa,#7c3aed);border-radius:7px;
  display:flex;align-items:center;justify-content:center;font-size:13px}
.sb-head h1{font-size:16px;font-weight:600;letter-spacing:-.3px}

.new-btn{display:flex;align-items:center;gap:8px;width:calc(100% - 16px);margin:8px 8px 4px;
  padding:9px 12px;border:none;border-radius:var(--r);background:var(--accent-bg);color:var(--accent);
  font-size:13px;font-weight:500;cursor:pointer;transition:all .12s;font-family:inherit}
.new-btn:hover{background:rgba(167,139,250,.16)}
.new-btn svg{width:16px;height:16px}

.sb-list{flex:1;overflow-y:auto;padding:2px 6px}
.sb-list::-webkit-scrollbar{width:4px}
.sb-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}

.si{padding:9px 10px;border-radius:var(--r2);cursor:pointer;transition:background .12s;margin-bottom:1px}
.si:hover{background:var(--surface2)}
.si.active{background:var(--accent-bg)}
.si .si-n{font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.si .si-m{font-size:10px;color:var(--text4);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.si:hover .si-d{opacity:1}
.si-d{float:right;width:20px;height:20px;border:none;background:transparent;color:var(--text4);
  cursor:pointer;border-radius:4px;font-size:12px;opacity:0;transition:all .12s;
  display:flex;align-items:center;justify-content:center;margin-top:-2px}
.si-d:hover{color:var(--red);background:rgba(248,113,113,.12)}

.sb-foot{padding:8px 12px;border-top:1px solid var(--border)}
.sb-foot-row{display:flex;align-items:center;gap:6px;justify-content:space-between}
.sb-foot-row .status{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text3)}
.sb-foot-row .status .dot{width:6px;height:6px;border-radius:50%}
.sb-foot-row .dot.on{background:var(--green)}
.sb-foot-row .dot.off{background:var(--red)}
.sb-foot-row button{width:30px;height:30px;border:none;background:transparent;color:var(--text3);
  border-radius:var(--r2);cursor:pointer;font-size:16px;transition:all .12s}
.sb-foot-row button:hover{background:var(--surface2);color:var(--text)}

/* ── main ── */
.main{flex:1;display:flex;flex-direction:column;min-width:0}

.top{display:flex;align-items:center;padding:6px 18px;border-bottom:1px solid var(--border);
  background:var(--surface);flex-shrink:0;gap:8px}
.top select{padding:4px 10px;background:var(--surface2);border:1px solid var(--border);color:var(--text);
  border-radius:var(--r2);font-size:12.5px;font-family:inherit;cursor:pointer;outline:none}
.top select:focus{border-color:var(--accent)}
.top .s-name{font-size:13px;font-weight:500;color:var(--text2);margin-left:4px;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.top .s-name.none{color:var(--text4);font-style:italic}

/* ── chat ── */
.chat{flex:1;overflow-y:auto;display:none;scroll-behavior:smooth}
.chat.show{display:block}
.chat::-webkit-scrollbar{width:5px}
.chat::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.chat-inner{max-width:740px;margin:0 auto;padding:12px 16px 8px}

.msg{display:flex;gap:12px;margin-bottom:16px;max-width:740px;margin-left:auto;margin-right:auto;animation:fadeIn .15s ease}
.msg.user{flex-direction:row-reverse}
.msg .av{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:12px;flex-shrink:0}
.msg.ast .av{background:linear-gradient(135deg,#a78bfa,#7c3aed);color:#fff}
.msg.user .av{background:var(--surface3);color:var(--text2)}
.msg .bub{padding:8px 14px;max-width:85%;font-size:14px;line-height:1.65;word-wrap:break-word}
.msg.ast .bub{border-radius:0 var(--r) var(--r) var(--r)}
.msg.user .bub{background:var(--accent-bg);border-radius:var(--r) 0 var(--r) var(--r);color:var(--text)}
.msg.ast .bub p{margin-bottom:6px}
.msg.ast .bub p:last-child{margin-bottom:0}
.msg.ast .bub pre{background:var(--surface);border:1px solid var(--border);border-radius:var(--r2);
  padding:9px 11px;overflow-x:auto;margin:6px 0;font-size:13px;position:relative}
.msg .bub code{background:var(--surface2);padding:1px 5px;border-radius:3px;font-size:13px}
.msg .bub pre code{background:transparent;padding:0}
.msg .bub ul,.msg .bub ol{padding-left:20px;margin:4px 0}
.msg .bub img{max-width:100%;border-radius:var(--r2);margin:4px 0;cursor:pointer}
.msg .bub table{border-collapse:collapse;width:100%;margin:6px 0;font-size:13px}
.msg .bub th,.msg .bub td{border:1px solid var(--border);padding:5px 8px;text-align:left}
.msg .bub th{background:var(--surface2)}
.msg .bub a{color:var(--accent2);text-decoration:none}
.msg .bub a:hover{text-decoration:underline}
.msg .bub blockquote{border-left:3px solid var(--accent);padding:4px 12px;margin:6px 0;color:var(--text2);
  background:var(--accent-bg);border-radius:0 var(--r2) var(--r2) 0}

/* ── welcome ── */
.welcome{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:40px 20px}
.welcome .icon{font-size:42px;margin-bottom:12px}
.welcome h2{font-size:22px;font-weight:600;margin-bottom:6px;letter-spacing:-.3px}
.welcome p{color:var(--text2);font-size:13px;max-width:380px;line-height:1.6}
.welcome .hint{margin-top:16px;display:flex;gap:6px;flex-wrap:wrap;justify-content:center}
.welcome .hint span{font-size:11px;padding:4px 10px;background:var(--surface);border:1px solid var(--border);
  border-radius:20px;color:var(--text3)}

/* ── input ── */
.inp-wrap{padding:6px 16px 14px;background:var(--bg);flex-shrink:0}
.inp-inner{max-width:740px;margin:0 auto}
.inp-row{display:flex;gap:6px;align-items:flex-end;background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:4px;transition:border-color .15s}
.inp-row:focus-within{border-color:var(--text4)}
.inp-row textarea{flex:1;padding:6px 8px;border:none;background:transparent;color:var(--text);
  font-family:inherit;font-size:14px;line-height:1.45;resize:none;min-height:28px;max-height:120px;outline:none}
.inp-row textarea::placeholder{color:var(--text4)}
.inp-row .iabtn{width:30px;height:30px;border:none;background:transparent;color:var(--text3);
  border-radius:50%;cursor:pointer;font-size:16px;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:all .12s}
.inp-row .iabtn:hover{background:var(--surface2);color:var(--text)}
.inp-row .send{width:30px;height:30px;border:none;border-radius:50%;background:var(--accent);
  color:#000;font-size:14px;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:all .12s}
.inp-row .send:hover{opacity:.85}
.inp-row .send:disabled{opacity:.2;cursor:not-allowed}
.chips{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:4px}
.chip{display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:10px;font-size:11px;
  background:var(--surface2);border:1px solid var(--border)}
.chip .x{color:var(--text4);cursor:pointer;font-size:12px;margin-left:3px}
.chip .x:hover{color:var(--red)}

.typing{display:flex;gap:4px;padding:4px 0}
.typing span{width:5px;height:5px;border-radius:50%;background:var(--text3);animation:pl 1.3s infinite}
.typing span:nth-child(2){animation-delay:.15s}
.typing span:nth-child(3){animation-delay:.3s}
@keyframes pl{0%,60%,100%{opacity:.25}30%{opacity:1}}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}

.toast{position:fixed;bottom:60px;left:50%;transform:translateX(-50%);background:var(--red);
  color:#fff;padding:6px 14px;border-radius:8px;font-size:12px;opacity:0;transition:opacity .25s;z-index:99}
.toast.show{opacity:1}

/* ── modal ── */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:200;display:flex;align-items:center;
  justify-content:center;opacity:0;pointer-events:none;transition:opacity .2s}
.modal.show{opacity:1;pointer-events:auto}
.modal img{max-width:90vw;max-height:90vh;border-radius:8px}

/* ── settings panel (dropdown) ── */
.settings-overlay{position:fixed;inset:0;z-index:100;display:none}
.settings-overlay.show{display:block}
.settings-panel{position:fixed;top:44px;right:16px;width:340px;max-height:calc(100vh - 60px);
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:12px 14px 14px;z-index:101;overflow-y:auto;display:none;box-shadow:0 8px 32px rgba(0,0,0,.5)}
.settings-panel.show{display:block}
.settings-panel::-webkit-scrollbar{width:4px}
.settings-panel::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.sp-h{font-size:13px;font-weight:600;margin-bottom:10px}
.sp-g{margin-bottom:11px}
.sp-l{font-size:10.5px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.04em;margin-bottom:5px}
.tr{display:flex;align-items:center;justify-content:space-between;padding:5px 0}
.tr span{font-size:12.5px}
.tg{width:34px;height:18px;border-radius:9px;background:var(--border2);cursor:pointer;position:relative;transition:background .12s;flex-shrink:0}
.tg.on{background:var(--accent)}
.tg .k{width:14px;height:14px;border-radius:50%;background:#fff;position:absolute;top:2px;left:2px;transition:all .12s}
.tg.on .k{left:18px}
.skill-g{max-height:160px;overflow-y:auto;margin-top:4px}
.skill-g::-webkit-scrollbar{width:3px}
.skill-g::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.sc{display:flex;align-items:center;gap:5px;padding:4px 6px;border-radius:4px;cursor:pointer;font-size:12px;transition:background .08s}
.sc:hover{background:var(--surface2)}
.sc input{accent-color:var(--accent);width:13px;height:13px;cursor:pointer;flex-shrink:0}
.sc .sc-n{font-weight:500}
.sc .sc-d{font-size:10px;color:var(--text4);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

@media(max-width:800px){
  .sb{width:220px}
}
</style>
</head>
<body>
<div class="app">
  <div class="sb">
    <div class="sb-head">
      <div class="logo">H</div>
      <h1>Hermes</h1>
    </div>
    <button class="new-btn" id="newBtn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
      Новый чат
    </button>
    <div class="sb-list" id="sbList"></div>
    <div class="sb-foot">
      <div class="sb-foot-row">
        <div class="status"><span class="dot" id="statusDot"></span><span id="statusTxt">Готов</span></div>
        <button id="settingsBtn" title="Настройки">&#9881;</button>
      </div>
    </div>
  </div>

  <div class="main">
    <div class="top">
      <select id="modelSel"></select>
      <span class="s-name none" id="sessName">Нет активного чата</span>
    </div>

    <div class="welcome" id="welcome">
      <div class="icon">&#9670;</div>
      <h2>Hermes AI</h2>
      <p>Бесплатный агент на OpenRouter. Выберите чат слева или создайте новый.</p>
      <div class="hint" id="hints"></div>
    </div>

    <div class="chat" id="chat"><div class="chat-inner" id="chatInner"></div></div>

    <div class="inp-wrap">
      <div class="inp-inner">
        <div class="chips" id="chips"></div>
        <div class="inp-row">
          <button class="iabtn" id="attBtn" title="Прикрепить">+</button>
          <textarea id="inp" rows="1" placeholder="Отправить сообщение..."></textarea>
          <button class="send" id="sendBtn">&#10140;</button>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="settings-panel" id="settingsPanel">
  <div class="sp-h">Настройки</div>
  <div class="sp-g">
    <div class="sp-l">Память</div>
    <div class="tr"><span>Использовать MEMORY.md</span><div class="tg on" id="memTg"><div class="k"></div></div></div>
  </div>
  <div class="sp-g">
    <div class="sp-l">Навыки (Skills)</div>
    <div class="tr"><span>Использовать навыки</span><div class="tg on" id="skTg"><div class="k"></div></div></div>
    <div class="skill-g" id="skillG"></div>
  </div>
</div>
<div class="settings-overlay" id="settingsOverlay"></div>

<div class="toast" id="toast"></div>
<div class="modal" id="imgModal"><img id="modalImg"></div>
<input type="file" id="fileIn" multiple hidden>

<script>
const $$=id=>document.getElementById(id);
const chat=$$('chat'),chatInner=$$('chatInner'),welcome=$$('welcome'),inp=$$('inp'),
  sendBtn=$$('sendBtn'),attBtn=$$('attBtn'),fileIn=$$('fileIn'),chips=$$('chips'),
  toast=$$('toast'),sbList=$$('sbList'),newBtn=$$('newBtn'),
  modelSel=$$('modelSel'),sessName=$$('sessName'),
  statusDot=$$('statusDot'),statusTxt=$$('statusTxt'),
  imgModal=$$('imgModal'),modalImg=$$('modalImg'),
  settingsPanel=$$('settingsPanel'),settingsOverlay=$$('settingsOverlay'),
  settingsBtn=$$('settingsBtn'),memTg=$$('memTg'),skTg=$$('skTg'),skillG=$$('skillG'),
  hints=$$('hints');

let curModel='',curSid=null,files=[],busy=false,
  useMem=true,useSk=true,selSkills={},sessions=[];

// ─── INIT ───
(async function init(){
  const r=await fetch('/api/config'),d=await r.json();
  curModel=d.default;
  modelSel.innerHTML=d.models.map(m=>`<option value="${m.id}"${m.id===d.default?' selected':''}>${m.name}</option>`).join('');
  modelSel.onchange=()=>{curModel=modelSel.value};
  hints.innerHTML=d.models.map(m=>`<span>${m.name}</span>`).join('');

  if(d.skills){
    d.skills.forEach(s=>selSkills[s.name]=true);
    skillG.innerHTML=d.skills.map(s=>
      '<label class="sc"><input type="checkbox"'+(selSkills[s.name]?' checked':'')+' data-n="'+s.name+'">'+
      '<div><span class="sc-n">'+s.name+'</span><span class="sc-d">'+esc(s.desc||'')+'</span></div></label>'
    ).join('');
    skillG.querySelectorAll('input').forEach(cb=>{cb.onchange=()=>{selSkills[cb.dataset.n]=cb.checked}});
  }

  memTg.onclick=()=>{useMem=!useMem;memTg.classList.toggle('on')};
  skTg.onclick=()=>{useSk=!useSk;skTg.classList.toggle('on')};
  settingsBtn.onclick=()=>{settingsPanel.classList.toggle('show');settingsOverlay.classList.toggle('show')};
  settingsOverlay.onclick=()=>{settingsPanel.classList.remove('show');settingsOverlay.classList.remove('show')};

  await loadSess();
  const p=new URLSearchParams(location.search);
  if(p.get('s')) await switchSess(p.get('s'));
})();

function esc(s){if(!s)return'';var d=document.createElement('div');d.textContent=s;return d.innerHTML}

// ─── SESSIONS ───
async function loadSess(){
  const r=await fetch('/api/sessions'),d=await r.json();
  sessions=d;
  if(!sessions.length){
    sbList.innerHTML='<div style="padding:20px;text-align:center;font-size:12px;color:var(--text4)">Нет чатов</div>';
    return;
  }
  sbList.innerHTML=sessions.map(s=>
    '<div class="si'+(s.id===curSid?' active':'')+'" data-id="'+s.id+'">'+
    '<div class="si-n">'+esc(s.name)+'</div>'+
    '<div class="si-m">'+s.msg_count+' сообщ.</div>'+
    '<button class="si-d" data-del="'+s.id+'">&#10005;</button></div>'
  ).join('');
  sbList.querySelectorAll('.si').forEach(el=>{el.onclick=()=>switchSess(el.dataset.id)});
  sbList.querySelectorAll('.si-d').forEach(el=>{
    el.onclick=async e=>{e.stopPropagation();
      if(!confirm('Удалить чат?'))return;
      await fetch('/api/sessions/'+el.dataset.del,{method:'DELETE'});
      if(curSid===el.dataset.del){curSid=null;showWelc()}
      await loadSess();
    }
  });
}

async function switchSess(id){
  if(busy)return;
  curSid=id;
  const r=await fetch('/api/sessions/'+id),d=await r.json();
  if(!d||d.error){toast('Ошибка');return}
  sessName.textContent=d.name||'Чат';
  sessName.className='s-name';
  chatInner.innerHTML='';
  if(d.messages)d.messages.forEach(m=>addMsg(m.role,m.content,false));
  showChat();
  await loadSess();
  scrollB();
  history.replaceState(null,'','?s='+id);
}

function showWelc(){welcome.style.display='flex';chat.classList.remove('show');curSid=null;
  sessName.textContent='Нет активного чата';sessName.className='s-name none';
  history.replaceState(null,'','/');loadSess()}
function showChat(){welcome.style.display='none';chat.classList.add('show')}

function addMsg(role,content,save){
  var d=document.createElement('div');
  d.className='msg '+role;
  var av=role==='user'?'&#128100;':'H';
  d.innerHTML='<div class="av">'+av+'</div><div class="bub">'+md(content)+'</div>';
  d.querySelectorAll('.bub img').forEach(function(img){
    img.onclick=function(){modalImg.src=this.src;imgModal.classList.add('show')};
  });
  chatInner.appendChild(d);
  if(save&&curSid)saveMsg(role,content);
  scrollB();
}

function addTyping(){
  var d=document.createElement('div');d.className='msg ast';
  d.innerHTML='<div class="av">H</div><div class="bub"><div class="typing"><span></span><span></span><span></span></div></div>';
  chatInner.appendChild(d);scrollB();
}
function rmTyping(){var e=document.getElementById('typing');if(e)e.remove()}
function scrollB(){setTimeout(function(){chat.scrollTop=chat.scrollHeight},20)}

// ─── SEND ───
sendBtn.onclick=sendMsg;
inp.onkeydown=function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg()}};

async function sendMsg(){
  if(busy||!inp.value.trim()&&!files.length)return;
  var txt=inp.value.trim();
  inp.value='';inp.style.height='auto';
  if(!curSid)await newSess();
  addMsg('user',txt||'(файлы)');
  var fd=[];
  if(files.length){
    for(var f of files){
      var b=await fileToB64(f);
      fd.push({name:f.name,mime:f.type||'application/octet-stream',data:b});
    }
    files=[];chips.innerHTML='';
  }
  addTyping();busy=true;sendBtn.disabled=true;setStat('Думаю...');

  try{
    var r=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        session_id:curSid,message:txt,model:curModel,files:fd,
        use_memory:useMem,
        skills_enabled:useSk?Object.keys(selSkills).filter(function(k){return selSkills[k]}):[]
      })
    });
    if(!r.ok){var e=await r.json();throw new Error(e.error||'Ошибка')}
    var reader=r.body.getReader(),dec=new TextDecoder();
    var reply='';rmTyping();
    var md=document.createElement('div');md.className='msg ast';
    md.innerHTML='<div class="av">H</div><div class="bub"></div>';
    chatInner.appendChild(md);var bub=md.querySelector('.bub');
    while(true){
      var v=await reader.read();
      if(v.done)break;
      reply+=dec.decode(v.value,{stream:true});
      bub.innerHTML=md(reply);
      scrollB();
    }
    if(reply&&curSid)saveMsg('ast',reply);
  }catch(e){rmTyping();toast('Ошибка: '+e.message)}
  finally{busy=false;sendBtn.disabled=false;setStat('Готов');
    if(curSid){
      try{var sr=await fetch('/api/sessions/'+curSid),sj=await sr.json();if(sj)sessName.textContent=sj.name||'Чат'}catch(e){}
    }
    await loadSess();
  }
}

async function saveMsg(role,content){
  await fetch('/api/sessions/'+curSid+'/messages',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({role,content})
  });
}

async function newSess(){
  var n='Чат '+(sessions.length+1);
  var r=await fetch('/api/sessions/new',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name:n,model:curModel})
  });
  var d=await r.json();
  curSid=d.id;
  showChat();sessName.textContent=n;sessName.className='s-name';
  chatInner.innerHTML='';
  history.replaceState(null,'','?s='+curSid);
  await loadSess();
  return d.id;
}

newBtn.onclick=async function(){if(!busy)await newSess()};

// ─── ATTACH ───
attBtn.onclick=function(){fileIn.click()};
fileIn.onchange=function(){
  for(var f of fileIn.files)files.push(f);
  fileIn.value='';renderChips();
};
function renderChips(){
  chips.innerHTML=files.map(function(f,i){return '<span class="chip">'+esc(f.name)+' <span class="x" data-i="'+i+'">&#10005;</span></span>'}).join('');
  chips.querySelectorAll('.x').forEach(function(el){el.onclick=function(){files.splice(+this.dataset.i,1);renderChips()}});
}

// ─── UTILS ───
function setStat(s){statusTxt.textContent=s;statusDot.className='dot '+(s==='Готов'?'on':'off')}
function toast(m){var t=$$('toast');t.textContent=m;t.classList.add('show');setTimeout(function(){t.classList.remove('show')},2500)}
function fileToB64(f){return new Promise(function(res,rej){var r=new FileReader;r.onload=function(){res(r.result.split(',')[1])};r.onerror=rej;r.readAsDataURL(f)})}

imgModal.onclick=function(){imgModal.classList.remove('show')};

function md(s){
  if(!s)return'';
  var r=esc(s);
  // code blocks
  r=r.replace(/```(\w*)\n?([\s\S]*?)```/g,function(m,l,c){return'<pre><code>'+(c.replace(/</g,'&lt;'))+'</code></pre>'});
  // inline code
  r=r.replace(/`([^`]+)`/g,'<code>$1</code>');
  // images
  r=r.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,'<img src="$2" alt="$1">');
  // links
  r=r.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  // bold+italic
  r=r.replace(/\*\*\*(.+?)\*\*\*/g,'<strong><em>$1</em></strong>');
  r=r.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  r=r.replace(/\*(.+?)\*/g,'<em>$1</em>');
  // blockquote
  r=r.replace(/^> (.+)$/gm,'<blockquote>$1</blockquote>');
  // lists
  r=r.replace(/^[\s]*[-*]\s+(.+)$/gm,'<li>$1</li>');
  r=r.replace(/(<li>.*<\/li>\n?)+/g,'<ul>$&</ul>');
  r=r.replace(/^[\s]*\d+\.\s+(.+)$/gm,'<li>$1</li>');
  r=r.replace(/(<li>.*<\/li>\n?)+/g,'<ol>$&</ol>');
  // paragraphs
  r=r.replace(/\n\n/g,'</p><p>');
  if(!r.startsWith('<'))r='<p>'+r;
  if(!r.endsWith('>'))r+='</p>';
  return r;
}
</script>
</body>
</html>'''

# ══════════════════════════════════════════════════════════════════
#  API
# ══════════════════════════════════════════════════════════════════

@app.get("/")
async def index():
    return HTMLResponse(PAGE)

@app.get("/api/config")
async def get_config():
    return {"models": MODELS, "default": DEFAULT, "key_ok": KEY is not None, "skills": _list_skills()}

@app.get("/api/sessions")
async def get_sessions():
    return _list_sessions()

@app.post("/api/sessions/new")
async def create_session(data: dict):
    sid = uuid.uuid4().hex[:12]
    now = datetime.datetime.now().isoformat(timespec="minutes")
    session = {
        "id": sid, "name": data.get("name", "Новый чат"),
        "model": data.get("model", DEFAULT), "created": now, "updated": now,
        "messages": []
    }
    _save_session(sid, session)
    return {"id": sid, "name": session["name"]}

@app.get("/api/sessions/{sid}")
async def get_session(sid: str):
    s = _load_session(sid)
    return s if s else {"error": "Not found"}

@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str):
    p = SESSIONS_DIR / f"{sid}.json"
    if p.exists(): p.unlink()
    return {"ok": True}

@app.post("/api/sessions/{sid}/messages")
async def add_message(sid: str, data: dict):
    s = _load_session(sid)
    if not s: return {"error": "Not found"}
    s["messages"].append({"role": data.get("role", "user"), "content": data.get("content", "")})
    s["updated"] = datetime.datetime.now().isoformat(timespec="minutes")
    if len(s["messages"]) == 1 and data.get("role") == "user":
        name = (data.get("content", "") or "")[:50].strip()
        if name: s["name"] = name
    _save_session(sid, s)
    return {"ok": True}

@app.post("/api/sessions/{sid}/clear")
async def clear_session(sid: str):
    s = _load_session(sid)
    if s:
        s["messages"] = []
        s["updated"] = datetime.datetime.now().isoformat(timespec="minutes")
        _save_session(sid, s)
    return {"ok": True}

@app.get("/api/memory")
async def get_memory():
    return {"content": _read_memory()}

@app.post("/api/memory")
async def set_memory(data: dict):
    _write_memory(data.get("content", ""))
    return {"ok": True}

@app.post("/api/chat")
async def chat(data: dict):
    session_id = data.get("session_id")
    message = data.get("message", "")
    model = data.get("model", DEFAULT)
    files = data.get("files", [])
    use_memory = data.get("use_memory", True)
    skills_enabled = data.get("skills_enabled", [])

    if not KEY:
        return JSONResponse({"error": "API-ключ не найден. Проверь hermes-data/.env"}, status_code=400)

    system_prompt = _build_system(skills_enabled, use_memory)
    msgs = [{"role": "system", "content": system_prompt}]

    if session_id:
        s = _load_session(session_id)
        if s:
            for m in s["messages"][-30:]:
                msgs.append({"role": m["role"], "content": m["content"]})

    user_content = message
    if files:
        parts = []
        if message: parts.append({"type": "text", "text": message})
        for f in files:
            ext = Path(f["name"]).suffix.lower()
            if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                parts.append({"type": "image_url", "image_url": {"url": f"data:{f['mime']};base64,{f['data']}"}})
            else:
                parts.append({"type": "text", "text": f"\n[{f['name']}] (файл прикреплён)"})
        user_content = parts if len(parts) > 1 else message
    msgs.append({"role": "user", "content": user_content})

    headers = {
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:9120",
        "X-Title": "Hermes Agent"
    }
    payload = {
        "model": model, "messages": msgs, "stream": True,
        "max_tokens": 4096, "temperature": 0.7
    }

    async def stream():
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                async with client.stream("POST", "https://openrouter.ai/api/v1/chat/completions",
                                           json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        yield f"\n\nОшибка {resp.status_code}: {err[:200].decode()}"
                        return
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "): continue
                        j = line[6:].strip()
                        if not j or j == "[DONE]": continue
                        try:
                            obj = json.loads(j)
                            delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "") or ""
                            if delta: yield delta
                        except: pass
            except Exception as e:
                yield f"\n\nОшибка соединения: {e}"
    return stream()

# ══════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    port = 9120
    print(f"Hermes AI -> http://localhost:{port}")
    threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")