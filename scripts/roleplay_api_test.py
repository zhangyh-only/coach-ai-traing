#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coach 角色扮演链 · 本地业务接口测试工具（单步式）
=================================================
配合"由我逐轮扮演 SA 销售"的可循环自动测试：每轮看 AI 顾客上一句、
生成一句导购应答、喂进来、拿到 AI 顾客这轮的真实回复，自动追加存盘。一局跑完后
我再对整局做分析、把判断写进记录，最终用 build_report.py 汇成 HTML 记录浏览器。

链路（正式正价 baseId=528、正式奥莱 baseId=530、A/B 实验 baseId=531；可用环境变量切换，actionId 自动解析）：
  begin（建记录, 拿 recordId）→ 每轮 recordInput→openStream→sse → getRoleRandomData（拿这局性子/产品）

子命令：
  begin                          建一局，输出 RECORD_ID 和 JSON 路径
  step <recordId> "<SA这句话>"    跑一轮（自动算轮次、追加存盘），打印 Elena 这轮回复
  run-script <json文件>           按 JSON 话术数组自动跑完整局，遇到 END_CHAT 停止
  random-config-get <configKey>   查询角色扮演随机池配置
  random-config-set <configKey> <json文件>  更新角色扮演随机池配置
  random-config-sync <随机池md文件> [personality|product|all]  从文档同步随机池；all 同步顶层布尔开关
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
import hashlib
import time
import urllib.parse
import urllib.request
import urllib.error

# ─────────────────── 配置（来自 本地场景测试接口说明.md）───────────────────
def _env_int(name, default):
    value = os.environ.get(name)
    return int(value) if value else default


def _env_int_optional(name):
    value = os.environ.get(name)
    return int(value) if value else None


CONFI = os.environ.get("ROLEPLAY_CONFI", "http://127.0.0.1:8080")
AI = os.environ.get("ROLEPLAY_AI", "http://127.0.0.1:80")
COMPANY = os.environ.get("ROLEPLAY_COMPANY", "ruixue_dev")
CERT = os.environ.get("ROLEPLAY_CERT", "fansCertificate")

BASE_ID = _env_int("ROLEPLAY_BASE_ID", 528)
MEMBER_ID = _env_int("ROLEPLAY_MEMBER_ID", 40147)
BOT_DISPLAY_CONFIG_ID = _env_int_optional("ROLEPLAY_BOT_DISPLAY_CONFIG_ID")
ACTION_ID_INPUT = _env_int_optional("ROLEPLAY_ACTION_ID_INPUT")
FLOW_ID = _env_int_optional("ROLEPLAY_FLOW_ID")
ACTION_ID_STREAM = _env_int_optional("ROLEPLAY_ACTION_ID_STREAM")
END_TYPE = _env_int("ROLEPLAY_END_TYPE", 1)
CURRENT_SCENE_DIRS = {
    528: "场景1_质感自用Elena",
    530: "场景2_奥莱私域轻奢Bella",
    531: "场景1_质感自用Elena",
}
SCENE_DIR = os.environ.get(
    "ROLEPLAY_SCENE_DIR",
    CURRENT_SCENE_DIRS.get(BASE_ID, "场景1_质感自用Elena"),
)
ROLEPLAY_CUSTOM_CONFIG_KEY = os.environ.get("ROLEPLAY_CUSTOM_CONFIG_KEY", "nstr.bot-display.custom-config")

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
    _resolve_runtime_config()
    url = f"{CONFI}/welearning/api/nstr/mobile/data/begin?companyCode={COMPANY}&certificate={CERT}"
    body = {"memberId": MEMBER_ID, "baseId": BASE_ID,
            "botDisplayConfigId": BOT_DISPLAY_CONFIG_ID, "beginChar": 0, "beginType": 0}
    return _check(_post(url, body), "begin")["data"]["id"]


def record_input(record_id, user_input, loop_index):
    _resolve_runtime_config()
    url = f"{CONFI}/welearning/api/nstr/mobile/data/recordInput?companyCode={COMPANY}&certificate={CERT}"
    body = {"memberId": MEMBER_ID, "trainingId": BASE_ID, "recordId": record_id,
            "userInput": user_input, "loopIndex": loop_index,
            "actionId": ACTION_ID_INPUT, "audioUrl": ""}
    return _check(_post(url, body), "recordInput")["data"]["id"]


def open_stream(record_id, bind_detail_id, user_input, loop_count):
    _resolve_runtime_config()
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


def get_history(record_id):
    url = (f"{CONFI}/welearning/api/nstr/mobile/data/history?companyCode={COMPANY}"
           f"&certificate={CERT}&pageNo=1&pageSize=200")
    resp = _check(_post(url, {"recordId": record_id, "memberId": MEMBER_ID}), "history")
    data = resp.get("data") or {}
    return data.get("records") or []


def _find_bound_bot_answer(records, bind_detail_id):
    matches = [
        item for item in records
        if item.get("actionType") == "bot-answer" and item.get("bindDetailId") == bind_detail_id
    ]
    return matches[-1] if matches else None


def _recover_bot_answer_from_history(record_id, bind_detail_id):
    """SSE may be empty when async execution stalls; history tells whether bot-answer completed."""
    last_detail = None
    for _ in range(3):
        detail = _find_bound_bot_answer(get_history(record_id), bind_detail_id)
        if detail:
            last_detail = detail
            content = detail.get("content") or ""
            if content:
                return content
            if detail.get("actionStatus") == 2:
                return content
        time.sleep(2)
    if last_detail:
        raise ApiError(
            f"bot-answer未完成：recordId={record_id} bindDetailId={bind_detail_id} "
            f"detailId={last_detail.get('recordDetailId')} actionStatus={last_detail.get('actionStatus')} content为空"
        )
    raise ApiError(f"bot-answer未落记录：recordId={record_id} bindDetailId={bind_detail_id}")


def get_prompt_trace(record_id):
    url = f"{AI}/ailearning/nstr/tool/getRoleplayPromptTrace?recordId={record_id}&companyCode={COMPANY}&certificate={CERT}"
    return _check(_get(url), "getRoleplayPromptTrace").get("data") or []


def end_record(record_id):
    url = f"{CONFI}/welearning/api/nstr/mobile/data/end?companyCode={COMPANY}&certificate={CERT}"
    body = {"recordId": record_id, "endType": END_TYPE}
    return _check(_post(url, body), "end")


def random_config_query(config_key):
    url = (f"{AI}/ailearning/nstr/tool/roleplayRandomConfig/query?baseId={BASE_ID}"
           f"&configKey={urllib.parse.quote(config_key)}&companyCode={COMPANY}&certificate={CERT}")
    return _check(_get(url), "roleplayRandomConfig/query").get("data")


def random_config_update(config_key, config_value):
    url = f"{AI}/ailearning/nstr/tool/roleplayRandomConfig/update?companyCode={COMPANY}&certificate={CERT}"
    body = {"baseId": BASE_ID, "configKey": config_key, "configValue": config_value}
    return _check(_post(url, body), "roleplayRandomConfig/update").get("data")


def _resolve_runtime_config():
    """按 baseId 从 8080 侧解析角色 id 与 loop action id，避免测试脚本沿用旧场景默认值。"""
    global BOT_DISPLAY_CONFIG_ID, ACTION_ID_INPUT, ACTION_ID_STREAM, FLOW_ID
    if BOT_DISPLAY_CONFIG_ID is None:
        url = (f"{CONFI}/welearning/api/nstr/mobile/data/baseInfo?nstrBaseId={BASE_ID}"
               f"&memberId={MEMBER_ID}&withMemberUseCount=false&companyCode={COMPANY}&certificate={CERT}")
        data = _check(_post(url, {}), "baseInfo").get("data") or {}
        configs = data.get("botDisplayConfigs") or []
        if not configs:
            raise ApiError(f"baseId={BASE_ID} 未查询到可用 botDisplayConfigs")
        BOT_DISPLAY_CONFIG_ID = configs[0].get("id")
    if ACTION_ID_INPUT is None or ACTION_ID_STREAM is None or FLOW_ID is None:
        url = (f"{CONFI}/welearning/api/nstr/mobile/data/flows?nstrBaseId={BASE_ID}"
               f"&companyCode={COMPANY}&certificate={CERT}")
        flows = _check(_get(url), "flows").get("data") or []
        selected_loop = None
        for node in flows:
            loop = node.get("loop") or {}
            if not loop:
                continue
            loop_id = loop.get("id") or node.get("targetId")
            actions = loop.get("actions") or []
            action_types = {action.get("actionType") for action in actions}
            if FLOW_ID is not None and loop_id == FLOW_ID:
                selected_loop = loop
                break
            if FLOW_ID is None and {"get-input", "bot-answer"}.issubset(action_types):
                FLOW_ID = loop_id
                selected_loop = loop
                break
        if selected_loop:
            for action in selected_loop.get("actions") or []:
                action_type = action.get("actionType")
                if ACTION_ID_INPUT is None and action_type == "get-input":
                    ACTION_ID_INPUT = action.get("id")
                if ACTION_ID_STREAM is None and action_type == "bot-answer":
                    ACTION_ID_STREAM = action.get("id")
        if FLOW_ID is None:
            raise ApiError(f"baseId={BASE_ID} 未能从 flows 解析 loop.id/nstrFlowId")
        if ACTION_ID_INPUT is None or ACTION_ID_STREAM is None:
            raise ApiError(f"baseId={BASE_ID} 未能从 flows 解析 get-input/bot-answer actionId")


def _extract_json_blocks_from_md(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.S)
    if not blocks:
        raise ApiError("随机池文档缺少 json 代码块")

    parsed = [json.loads(block) for block in blocks]

    # 现行格式：性格池与产品池合并在同一个 JSON 对象中。
    for data in parsed:
        if not isinstance(data, dict):
            continue
        personality_pool = data.get("rolePlayPersonality")
        product_pool = data.get("rolePlayProduct")
        if not isinstance(personality_pool, list) or not isinstance(product_pool, list):
            raise ApiError(
                "合并随机池 JSON 必须同时包含 rolePlayPersonality 和 rolePlayProduct 数组"
            )
        return data, personality_pool, product_pool

    # 兼容历史文档：前两个 JSON 代码块依次为性格池、产品池数组。
    if len(parsed) < 2 or not all(isinstance(data, list) for data in parsed[:2]):
        raise ApiError(
            "随机池 JSON 应为包含 rolePlayPersonality/rolePlayProduct 的对象，"
            "或两个依次表示性格池、产品池的数组代码块"
        )
    return {}, parsed[0], parsed[1]


def _validate_pool_items(items, name):
    if not isinstance(items, list) or not items:
        raise ApiError(f"{name} 必须是非空 JSON 数组")
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ApiError(f"{name}[{idx}] 必须是对象")
        missing = [k for k in ("name", "content", "enabled") if k not in item]
        if missing:
            raise ApiError(f"{name}[{idx}] 缺少字段: {', '.join(missing)}")
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ApiError(f"{name}[{idx}].name 必须是非空字符串")
        if not isinstance(item.get("content"), str) or not item["content"].strip():
            raise ApiError(f"{name}[{idx}].content 必须是非空字符串")
        if not isinstance(item.get("enabled"), bool):
            raise ApiError(f"{name}[{idx}].enabled 必须是布尔值")


def _split_state(text):
    """分离模型输出里的 <?STATE ...> 与 Elena 正文。
    前端虽自兼容隐藏，但测试要把盘点单独留出来调试、把正文清干净。"""
    if not text:
        return "", ""
    m = re.search(r"<\?STATE\s*(.*?)>", text, re.S)
    state = m.group(1).strip() if m else ""
    clean = re.sub(r"<\?STATE\s*.*?>", "", text, flags=re.S)
    return state, clean.strip()


def _state_has_required_fields(state):
    """状态标签必须各包含一次关切/动作/表态；字段缺失不能算连续性验收通过。"""
    if not state:
        return False
    return all(len(re.findall(rf"(?:^|；)\s*{field}\s*=", state)) == 1
               for field in ("关切", "动作", "表态"))


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
        build_report.configure_scene(SCENE_DIR)
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
    runtime_config = {
        "baseId": BASE_ID,
        "botDisplayConfigId": BOT_DISPLAY_CONFIG_ID,
        "flowId": FLOW_ID,
        "inputActionId": ACTION_ID_INPUT,
        "streamActionId": ACTION_ID_STREAM,
    }
    try:
        prompt_data = prompt_query()
        prompt_text = (prompt_data.get("templateValue") or "").strip()
        runtime_config["promptSha256"] = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        runtime_config["promptUpdateTime"] = prompt_data.get("updateTime")
    except Exception as e:
        print(f"(读取 prompt 版本证据失败，不阻塞建局: {e})")
    data = {"recordId": rid,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "runtimeConfig": runtime_config,
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
    if not raw:
        raw = _recover_bot_answer_from_history(record_id, bind_id)
    state, customer = _split_state(raw)
    state_missing = not bool(state)
    state_valid = _state_has_required_fields(state)
    has_end = END_TAG in (customer or "")
    turn = {
        "loop": loop,
        "sa": sa_text,
        "elena": customer,
        "state": state,
        "stateMissing": state_missing,
        "stateValid": state_valid,
    }
    if has_end:
        try:
            end_resp = end_record(record_id)
            turn["endMarked"] = True
            turn["endResponse"] = end_resp.get("data")
        except Exception as e:
            turn["endMarked"] = False
            turn["endError"] = str(e)
            print(f"(标记记录结束失败: {e})")
    data["turns"].append(turn)
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
    if state_missing:
        print("⚠ [STATE] 本轮模型未输出状态标签；该局不能判为状态连续性验收通过。")
    elif not state_valid:
        print("⚠ [STATE] 本轮状态标签未完整包含关切/动作/表态；该局不能判为状态连续性验收通过。")
    print(f"[顾客 ] {customer}")
    if loop == 0 and data.get("product"):
        print(f"[本局性子] {data['personality']}")
        print(f"[本局产品] {data['product']}")
    if has_end:
        if turn.get("endMarked"):
            print(f"⟵ AI 顾客输出了结束标签，已调用 /data/end 标记本局结束(endType={END_TYPE})。")
        else:
            print("⟵ AI 顾客输出了结束标签，但标记本局结束失败。")
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


def cmd_run_script(path):
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list) or not all(isinstance(x, str) and x.strip() for x in items):
        raise ApiError("run-script 需要一个非空字符串数组 JSON")

    rid = cmd_begin()
    model_ended = False
    for sa_text in items:
        customer = cmd_step(rid, sa_text.strip())
        if END_TAG in (customer or ""):
            model_ended = True
            break

    data = _load(rid)
    last_turn = (data.get("turns") or [{}])[-1]
    record_end_marked = bool(last_turn.get("endMarked"))
    state_complete = bool(data.get("turns")) and all(
        turn.get("stateValid") is True
        for turn in data.get("turns") or []
    )
    data["analysis"] = {
        "script": os.path.abspath(path),
        "modelEnded": model_ended,
        "recordEndMarked": record_end_marked,
        "stateComplete": state_complete,
        "ended": model_ended and record_end_marked,
        "turns": len(data.get("turns") or []),
        "baseId": BASE_ID,
        "botDisplayConfigId": BOT_DISPLAY_CONFIG_ID,
        "flowId": FLOW_ID,
        "inputActionId": ACTION_ID_INPUT,
        "streamActionId": ACTION_ID_STREAM,
    }
    _save(data)
    print(f"RUN_RECORD_ID={rid}")
    print(f"RUN_JSON={_session_path(rid)}")
    print(f"RUN_MODEL_ENDED={str(model_ended).lower()}")
    print(f"RUN_RECORD_END_MARKED={str(record_end_marked).lower()}")
    print(f"RUN_STATE_COMPLETE={str(state_complete).lower()}")
    print(f"RUN_ENDED={str(model_ended and record_end_marked).lower()}")
    if not model_ended:
        print("⚠ 脚本话术已跑完，但 AI 顾客没有输出 END_CHAT。")
    elif not record_end_marked:
        print("⚠ AI 顾客已输出 END_CHAT，但业务记录结束标记失败。")
    if not state_complete:
        print("⚠ 至少一轮缺失 STATE；该局可用于观察话术，但不能判为状态连续性验收通过。")


def cmd_prompt_trace(record_id):
    traces = get_prompt_trace(record_id)
    if not traces:
        print("暂无 prompt trace。可先用 prompt-get 回读线上内容，并核对会话 runtimeConfig 中的 "
              "promptSha256 / promptUpdateTime；trace 能力未接入时另行排查，不要求为场景调优重启服务。")
        return
    for trace in traces:
        print(f"===== loop={trace.get('loopIndex')} baseId={trace.get('baseId')} actionId={trace.get('actionId')} =====")
        print(trace.get("prompt") or "")


def cmd_random_config_get(config_key):
    data = random_config_query(config_key)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_random_config_set(config_key, json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _validate_pool_items(data, "随机池配置")
    config_value = json.dumps(data, ensure_ascii=False)
    updated = random_config_update(config_key, config_value)
    print(f"✓ 已更新 baseId={BASE_ID} configKey={config_key} items={len(data)}")
    print(json.dumps(updated, ensure_ascii=False, indent=2))


def cmd_random_config_sync(md_path, target):
    if "ROLEPLAY_BASE_ID" not in os.environ:
        raise ApiError("为避免误写默认场景，random-config-sync 必须显式设置 ROLEPLAY_BASE_ID（正价=528，奥莱=530，实验=531）")
    source_config, personality_pool, product_pool = _extract_json_blocks_from_md(md_path)
    _validate_pool_items(personality_pool, "性格池")
    _validate_pool_items(product_pool, "产品池")
    current = random_config_query(ROLEPLAY_CUSTOM_CONFIG_KEY) or {}
    try:
        custom_config = json.loads(current.get("configValue") or "{}")
    except Exception as e:
        raise ApiError(f"当前 {ROLEPLAY_CUSTOM_CONFIG_KEY} 不是合法 JSON，不能安全合并: {e}")
    if target in ("personality", "all"):
        custom_config["rolePlayPersonality"] = personality_pool
    if target in ("product", "all"):
        custom_config["rolePlayProduct"] = product_pool
    if target == "all":
        for key in ("openThinking", "replaceHistoryState"):
            if key in source_config:
                if not isinstance(source_config[key], bool):
                    raise ApiError(f"随机池文档 {key} 必须是布尔值")
                custom_config[key] = source_config[key]
    if target not in ("personality", "product", "all"):
        raise ApiError("target 只能是 personality、product 或 all")
    config_value = json.dumps(custom_config, ensure_ascii=False)
    updated = random_config_update(ROLEPLAY_CUSTOM_CONFIG_KEY, config_value)
    readback = random_config_query(ROLEPLAY_CUSTOM_CONFIG_KEY) or {}
    try:
        persisted_config = json.loads(readback.get("configValue") or "{}")
    except Exception as e:
        raise ApiError(f"同步后回读的 {ROLEPLAY_CUSTOM_CONFIG_KEY} 不是合法 JSON: {e}")
    verify_keys = []
    if target in ("personality", "all"):
        verify_keys.append("rolePlayPersonality")
    if target in ("product", "all"):
        verify_keys.append("rolePlayProduct")
    if target == "all":
        verify_keys.extend(key for key in ("openThinking", "replaceHistoryState") if key in source_config)
    mismatched = [key for key in verify_keys if persisted_config.get(key) != custom_config.get(key)]
    if mismatched:
        raise ApiError(f"同步接口已返回，但立即回读不一致: {', '.join(mismatched)}")
    print(f"✓ 已同步 baseId={BASE_ID} configKey={ROLEPLAY_CUSTOM_CONFIG_KEY} "
          f"personality={len(custom_config.get('rolePlayPersonality') or [])} "
          f"product={len(custom_config.get('rolePlayProduct') or [])} "
          f"id={updated.get('id') if updated else ''}")
    print(f"✓ 已回读校验: {', '.join(verify_keys)}")
    print("⚠ AI 运行侧对此配置有最长约 2 分钟缓存；等待缓存过期后新建 record，"
          "并以 getRoleRandomData / prompt trace 的实际注入内容确认生效。")


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
        elif cmd == "run-script":
            if len(args) < 2:
                print("用法：run-script <SA话术数组.json>"); sys.exit(1)
            cmd_run_script(args[1])
        elif cmd == "prompt-trace":
            if len(args) < 2:
                print("用法：prompt-trace <recordId>"); sys.exit(1)
            cmd_prompt_trace(int(args[1]))
        elif cmd == "random-config-get":
            if len(args) < 2:
                print("用法：random-config-get <configKey>"); sys.exit(1)
            cmd_random_config_get(args[1])
        elif cmd == "random-config-set":
            if len(args) < 3:
                print("用法：random-config-set <configKey> <json文件>"); sys.exit(1)
            cmd_random_config_set(args[1], args[2])
        elif cmd == "random-config-sync":
            if len(args) < 2:
                print("用法：random-config-sync <随机池md文件> [personality|product|all]"); sys.exit(1)
            cmd_random_config_sync(args[1], args[2] if len(args) > 2 else "all")
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
