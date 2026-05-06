"""
FlyCat Chat - 手機版 Claude 網頁介面
啟動後用手機瀏覽器連 http://100.122.13.69:5000
"""
import os, json
from flask import Flask, request, jsonify, Response, stream_with_context
import anthropic
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "chat.env"))

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>FlyCat Chat</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; height: 100dvh; display: flex; flex-direction: column; }
  #header { padding: 12px 16px; background: #16213e; font-size: 16px; font-weight: bold; color: #e94560; border-bottom: 1px solid #333; display: flex; align-items: center; justify-content: space-between; }
  #clear-btn { font-size: 13px; color: #888; background: none; border: 1px solid #444; border-radius: 6px; padding: 4px 10px; cursor: pointer; }
  #messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .msg { max-width: 88%; padding: 10px 14px; border-radius: 16px; font-size: 15px; line-height: 1.5; word-break: break-word; white-space: pre-wrap; }
  .user { background: #e94560; color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }
  .assistant { background: #16213e; color: #eee; align-self: flex-start; border-bottom-left-radius: 4px; border: 1px solid #333; }
  .thinking { color: #888; font-size: 13px; font-style: italic; }
  #input-area { padding: 10px 12px; background: #16213e; border-top: 1px solid #333; display: flex; gap: 8px; align-items: flex-end; }
  #input { flex: 1; background: #0f3460; color: #eee; border: 1px solid #444; border-radius: 12px; padding: 10px 14px; font-size: 15px; resize: none; max-height: 120px; outline: none; font-family: inherit; }
  #send-btn { background: #e94560; color: #fff; border: none; border-radius: 12px; padding: 10px 16px; font-size: 15px; cursor: pointer; flex-shrink: 0; }
  #send-btn:disabled { background: #555; }
  code { background: #0f3460; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 13px; }
  pre { background: #0f3460; padding: 10px; border-radius: 8px; overflow-x: auto; margin: 4px 0; }
  pre code { background: none; padding: 0; }
</style>
</head>
<body>
<div id="header">
  <span>FlyCat Chat</span>
  <button id="clear-btn" onclick="clearChat()">清除對話</button>
</div>
<div id="messages"></div>
<div id="input-area">
  <textarea id="input" placeholder="輸入訊息..." rows="1" oninput="autoResize(this)" onkeydown="handleKey(event)"></textarea>
  <button id="send-btn" onclick="send()">送出</button>
</div>
<script>
let history = [];

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey && window.innerWidth > 600) {
    e.preventDefault();
    send();
  }
}

function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  document.getElementById('messages').appendChild(div);
  div.scrollIntoView({ behavior: 'smooth' });
  return div;
}

async function send() {
  const input = document.getElementById('input');
  const btn = document.getElementById('send-btn');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  input.style.height = 'auto';
  btn.disabled = true;

  addMsg('user', text);
  history.push({ role: 'user', content: text });

  const replyDiv = addMsg('assistant', '...');

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let full = '';
    replyDiv.textContent = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.text) {
              full += data.text;
              replyDiv.textContent = full;
              replyDiv.scrollIntoView({ behavior: 'smooth' });
            }
          } catch {}
        }
      }
    }
    history.push({ role: 'assistant', content: full });
  } catch (e) {
    replyDiv.textContent = '⚠️ 連線錯誤：' + e.message;
  }

  btn.disabled = false;
  input.focus();
}

function clearChat() {
  history = [];
  document.getElementById('messages').innerHTML = '';
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

@app.route("/chat", methods=["POST"])
def chat():
    messages = request.json.get("messages", [])

    def generate():
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=messages
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

if __name__ == "__main__":
    print("FlyCat Chat 啟動中...")
    print("手機連：http://100.122.13.69:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
