#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coach 角色扮演链 · 本地业务接口测试工具（单步式）
=================================================
配合"由我逐轮扮演 SA 销售"的可循环自动测试：每轮看 AI 顾客上一句、
生成一句导购应答、喂进来、拿到 AI 顾客这轮的真实回复，自动追加存盘。一局跑完后
我再对整局做分析、把判断写进记录，最终用 build_report.py 汇成 HTML 记录浏览器。

链路（可用环境变量切换 baseId/actionId）：
  begin（建记录, 拿 recordId）→ 每轮 recordInput→openStream→sse → getRoleRandomData（拿这局性子/产品）

子命令：
  begin                          建一局，输出 RECORD_ID 和 JSON 路径
  step <recordId> "<SA这句话>"    跑一轮（自动算轮次、追加存盘），打印 Elena 这轮回复
  show <recordId>                打印该局当前完整对话
  prompt-trace <recordId>        拉取该局每轮最终调用模型的 prompt（需 80 服务已接入 prompt trace）
  probe                          只探活 begin（排查连通/声纹）

纯标准库、无第三方依赖。
"""
import json
import sys
import datetime
import os
import re
import glob
import urllib.request
import urllib.error

# ─────────────────── 配置（来自 本地场景测试接口说明.md）───────────────────
def _env_int(name, default):
    value = os.environ.get(name)
    return int(value) if value else default


CONFI = os.environ.get("ROLEPLAY_CONFI", "http://127.0.0.1:8080")
AI = os.environ.get("ROLEPLAY_AI", "http://127.0.0.1:80")
COMPANY = os.environ.get("ROLEPLAY_COMPANY", "ruixue_dev")
CERT = os.environ.get("ROLEPLAY_CERT", "sinoStrong")

BASE_ID = _env_int("ROLEPLAY_BASE_ID", 497)
MEMBER_ID = _env_int("ROLEPLAY_MEMBER_ID", 40147)
BOT_DISPLAY_CONFIG_ID = _env_int("ROLEPLAY_BOT_DISPLAY_CONFIG_ID", 747)
ACTION_ID_INPUT = _env_int("ROLEPLAY_ACTION_ID_INPUT", 2373)
FLOW_ID = _env_int("ROLEPLAY_FLOW_ID", 1251)
ACTION_ID_STREAM = _env_int("ROLEPLAY_ACTION_ID_STREAM", 2374)
SCENE_DIR = os.environ.get("ROLEPLAY_SCENE_DIR", "场景1_质感自用Elena")

HTTP_TIMEOUT = 30
SSE_TIMEOUT = 180
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "陪练场景搭建", SCENE_DIR, "记录", "接口测试输出")
END_TAG = "<?END_CHAT>"


class ApiError(Exception):
    pass


def _post(url, body):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json; charset=utf-8"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _check(resp, who):
    code = resp.get("errorCode")
    if code not in (0, None):
        msg = resp.get("errorMassage") or resp.get("errorMessage") or ""
        raise ApiError(f"[{who}] errorCode={code} {msg} | {resp}")
    return resp


# ─────────────────── 接口封装 ───────────────────
def begin():
    url = f"{CONFI}/welearning/api/nstr/mobile/data/begin?companyCode={COMPANY}&certificate={CERT}"
    body = {"memberId": MEMBER_ID, "baseId": BASE_ID,
            "botDisplayConfigId": BOT_DISPLAY_CONFIG_ID, "beginChar": 0, "beginType": 0}
    return _check(_post(url, body), "begin")["data"]["id"]


def record_input(record_id, user_input, loop_index):
    url = f"{CONFI}/welearning/api/nstr/mobile/data/recordInput?companyCode={COMPANY}&certificate={CERT}"
    body = {"memberId": MEMBER_ID, "trainingId": BASE_ID, "recordId": record_id,
            "userInput": user_input, "loopIndex": loop_index,
            "actionId": ACTION_ID_INPUT, "audioUrl": ""}
    return _check(_post(url, body), "recordInput")["data"]["id"]


def open_stream(record_id, bind_detail_id, user_input, loop_count):
    url = f"{AI}/ailearning/nstr/call/openStream?companyCode={COMPANY}&certificate={CERT}"
    body = {"nstrBaseId": BASE_ID, "nstrResultId": record_id, "nstrFlowId": FLOW_ID,
            "nstrActionId": ACTION_ID_STREAM, "loopCount": loop_count,
            "bindDetailId": bind_detail_id, "userInput": user_input}
    return _check(_post(url, body), "openStream")["data"]


def _extract_text(payload):
    try:
        obj = json.loads(payload)
    except Exception:
        return payload
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for k in ("content", "text", "answer", "delta", "output", "msg", "data", "result"):
            v = obj.get(k)
            if isinstance(v, str) and v:
                return v
            if isinstance(v, dict):
                t = _extract_text(json.dumps(v, ensure_ascii=False))
                if t:
                    return t
        return ""
    return ""


def pull_sse(serial_id):
    url = f"{AI}/ailearning/nstr/call/sse?companyCode={COMPANY}&serialId={serial_id}&certificate={CERT}"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"}, method="GET")
    full = ""
    with urllib.request.urlopen(req, timeout=SSE_TIMEOUT) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").rstrip("\r\n")
            if not line or not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload.lower() in ("[done]", "done"):
                break
            txt = _extract_text(payload)
            if not txt:
                continue
            if txt.startswith(full):
                full = txt
            elif full.startswith(txt):
                continue
            else:
                full += txt
    return full


def get_random(record_id):
    url = f"{AI}/ailearning/nstr/tool/getRoleRandomData?recordId={record_id}&companyCode={COMPANY}&certificate={CERT}"
    resp = _check(_get(url), "getRoleRandomData")
    out = {}
    for item in resp.get("data") or []:
        out[item.get("replaceTarget")] = item.get("val")
    return out


def get_prompt_trace(record_id):
    url = f"{AI}/ailearning/nstr/tool/getRoleplayPromptTrace?recordId={record_id}&companyCode={COMPANY}&certificate={CERT}"
    return _check(_get(url), "getRoleplayPromptTrace").get("data") or []


def _split_state(text):
    """分离模型输出里的 <?STATE>自盘点<?ENDSTATE> 与 Elena 正文。
    前端虽自兼容隐藏，但测试要把盘点单独留出来调试、把正文清干净。"""
    if not text:
        return "", ""
    m = re.search(r"<\?STATE\s*(.*?)>", text, re.S)
    state = m.group(1).strip() if m else ""
    clean = re.sub(r"<\?STATE\s*.*?>", "", text, flags=re.S)
    return state, clean.strip()


# ─────────────────── 一局记录的持久化（按 recordId）───────────────────
def _session_path(record_id):
    return os.path.join(OUT_DIR, f"session_rec{record_id}.json")


def _load(record_id):
    with open(_session_path(record_id), "r", encoding="utf-8") as f:
        return json.load(f)


def _refresh_viewer():
    """每次存盘后刷新 records.js，让固定查看器（测试记录查看器.html）看到最新全部记录。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import build_report
        build_report.build()
    except Exception as e:
        print(f"(刷新 records.js 失败，可手动跑 python3 scripts/build_report.py：{e})")


def _save(data):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(_session_path(data["recordId"]), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _refresh_viewer()


# ─────────────────── 子命令 ───────────────────
def cmd_begin():
    rid = begin()
    data = {"recordId": rid,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "personality": "", "product": "", "turns": [], "analysis": None}
    _save(data)
    print(f"RECORD_ID={rid}")
    print(f"CONFIG baseId={BASE_ID} botDisplayConfigId={BOT_DISPLAY_CONFIG_ID} flowId={FLOW_ID} "
          f"inputActionId={ACTION_ID_INPUT} streamActionId={ACTION_ID_STREAM}")
    print(f"JSON={_session_path(rid)}")
    print("（下一步：python3 scripts/roleplay_api_test.py step %s \"SA第一句话\"）" % rid)
    return rid


def cmd_step(record_id, sa_text):
    data = _load(record_id)
    loop = len(data["turns"])
    bind_id = record_input(record_id, sa_text, loop)
    serial = open_stream(record_id, bind_id, sa_text, loop)
    raw = pull_sse(serial)
    state, customer = _split_state(raw)
    data["turns"].append({"loop": loop, "sa": sa_text, "elena": customer, "state": state})
    if loop == 0 and not data.get("product"):
        try:
            rand = get_random(record_id)
            data["personality"] = rand.get("rolePlayPersonality") or rand.get("roleplay_personality", "")
            data["product"] = rand.get("rolePlayProduct") or rand.get("roleplay_product", "")
        except Exception as e:
            print(f"(取随机池失败: {e})")
    _save(data)
    print(f"───── 第 {loop} 轮 ─────")
    print(f"[SA   ] {sa_text}")
    if state:
        print(f"[盘点 ] {state}")
    print(f"[顾客 ] {customer}")
    if loop == 0 and data.get("product"):
        print(f"[本局性子] {data['personality']}")
        print(f"[本局产品] {data['product']}")
    if END_TAG in (customer or ""):
        print("⟵ AI 顾客输出了结束标签，本局自然收尾。")
    return customer


def cmd_show(record_id):
    data = _load(record_id)
    print(f"# recordId={record_id} | {data['timestamp']}")
    print(f"性子：{data.get('personality','')}")
    print(f"产品：{data.get('product','')}")
    for t in data["turns"]:
        print(f"\n[{t['loop']}] SA   : {t['sa']}")
        print(f"[{t['loop']}] Elena: {t['elena']}")
    if data.get("analysis"):
        print(f"\n分析：{json.dumps(data['analysis'], ensure_ascii=False, indent=2)}")


def cmd_prompt_trace(record_id):
    traces = get_prompt_trace(record_id)
    if not traces:
        print("暂无 prompt trace。请确认 80 服务已重启到包含 trace 的版本，并至少跑过一轮 bot-answer。")
        return
    for trace in traces:
        print(f"===== loop={trace.get('loopIndex')} baseId={trace.get('baseId')} actionId={trace.get('actionId')} =====")
        print(trace.get("prompt") or "")


def prompt_query():
    url = f"{CONFI}/welearning/api/nstr/tool/prompt/query?companyCode={COMPANY}&certificate={CERT}"
    return _check(_post(url, {"baseId": BASE_ID, "type": "bot_display"}), "prompt/query")["data"]


def prompt_update(text, remark=""):
    url = f"{CONFI}/welearning/api/nstr/tool/prompt/update?companyCode={COMPANY}&certificate={CERT}"
    body = {"baseId": BASE_ID, "type": "bot_display", "remark": remark[:200], "prompt": text}
    try:
        return _check(_post(url, body), "prompt/update")
    except urllib.error.HTTPError as e:
        # 该接口偶发写库成功却返回非 2xx，回读确认是否已生效，生效则不算失败
        live = (prompt_query().get("templateValue") or "").strip()
        if live == text.strip():
            return {"errorCode": 0, "_note": f"update 返回 HTTP{e.code}，但回读确认已生效"}
        raise


def probe():
    print("▶ 探活 begin ...")
    try:
        print(f"✓ begin 通，recordId={begin()}")
    except Exception as e:
        print(f"✗ {e}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    try:
        if cmd == "begin":
            cmd_begin()
        elif cmd == "step":
            if len(args) < 3:
                print('用法：step <recordId> "<SA这句话>"'); sys.exit(1)
            cmd_step(int(args[1]), args[2])
        elif cmd == "show":
            cmd_show(int(args[1]))
        elif cmd == "prompt-trace":
            if len(args) < 2:
                print("用法：prompt-trace <recordId>"); sys.exit(1)
            cmd_prompt_trace(int(args[1]))
        elif cmd == "prompt-get":
            d = prompt_query()
            v = d.get("templateValue", "")
            print(f"线上 prompt：{len(v)} 字 ｜ 更新于 {d.get('updateTime')}")
            print(v)
        elif cmd == "prompt-set":
            if len(args) < 2:
                print('用法：prompt-set <提示词文件> ["<remark>"]'); sys.exit(1)
            with open(args[1], "r", encoding="utf-8") as f:
                text = f.read()
            remark = args[2] if len(args) > 2 else ""
            prompt_update(text, remark)
            print(f"✓ 已灌线上：{len(text)} 字 ｜ remark={remark}")
        elif cmd == "probe":
            probe()
        else:
            print(f"未知命令：{cmd}"); print(__doc__)
    except ApiError as e:
        print(f"✗ 业务层报错：{e}"); sys.exit(2)
    except urllib.error.URLError as e:
        print(f"✗ 连不上服务：{e}"); sys.exit(3)


if __name__ == "__main__":
    main()
