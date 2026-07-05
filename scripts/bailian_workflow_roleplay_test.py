#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coach 角色扮演链 · 百炼 Workflow API 测试脚本
=================================================

用途：
  直接调用已发布的百炼 Workflow 应用，传入 Coach 角色扮演 5 个开始节点变量，
  输出最终顾客回复，并做一次轻量重复风险检查。

必填配置：
  DASHSCOPE_API_KEY=sk-xxx
  BAILIAN_WORKFLOW_APP_ID=app_xxx
  BAILIAN_WORKSPACE_ID=llm-xxx  # 可选；子业务空间应用必填
  也可以写到仓库根目录 .bailian-workflow.env，脚本会自动读取。

示例：
  python3 scripts/bailian_workflow_roleplay_test.py
  python3 scripts/bailian_workflow_roleplay_test.py --app-id app_xxx
  python3 scripts/bailian_workflow_roleplay_test.py --stream
  python3 scripts/bailian_workflow_roleplay_test.py --payload-json /path/to/payload.json

说明：
  - 开始节点变量通过 biz_params 传入，不写进 prompt。
  - 默认用内置 Bella 奥莱重复防护用例。
  - 不在仓库里保存 API Key。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, Optional


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_TIMEOUT = 180
LOCAL_ENV_FILE = ".bailian-workflow.env"


DEFAULT_PAYLOAD: Dict[str, str] = {
    "sceneCode": "bella_outlet",
    "userInput": (
        "这个你可以放心，我们是 Coach 官方奥莱门店，商品有吊牌、小票和门店售后，"
        "不是代购渠道。你刚才试背的时候其实比例挺好的，浅棕色也比较日常。"
        "你平时牛仔裤、针织衫、小外套都能搭，不会只能正式场合背。"
    ),
    "dialogueHistory": (
        "[SA] 你好，欢迎来到 Coach，今天想看哪类包呀？\n"
        "[AI顾客] 我朋友说奥莱这边有时候能淘到合适的 Coach 包，我想看看有没有适合日常背的，不想买回来闲置。\n\n"
        "[SA] 这款浅棕色 Tabby 风格比较轻，平时通勤和周末都能搭，价格也比正价店友好一些。\n"
        "[AI顾客] 奥莱这边的包都是正品吗？我有点怕买到那种渠道不清楚的。\n\n"
        "[SA] 这个你放心，我们是 Coach 官方奥莱门店，商品来源、吊牌、小票和售后都在门店体系内，不是外面的代购渠道。\n"
        "[AI顾客] 那还好，我主要就是怕第一次买轻奢包踩坑。如果渠道没问题，我就想看看它会不会太成熟。\n\n"
        "[SA] 不会太成熟。这个颜色比较日常，你穿牛仔裤、针织衫或者小外套都能搭，不会特别正式。你可以先试背一下，看镜子里整体比例。\n"
        "[AI顾客] 可以，我试一下。（她把包背到肩上，在镜子前看了一下）感觉还挺轻的，就是我怕自己平时背的机会不多。"
    ),
    "rolePlayPersonality": (
        "C-怕踩坑型。说话气质：谨慎、会确认安全感，但不是抬杠。"
        "最先关切：正品渠道、会不会买错、会不会闲置。"
        "证据阈值：听到官方门店、吊牌小票、售后保障后，正品渠道顾虑应收口，不再换说法重问。"
        "追问策略：同一类风险最多追一轮；被解释清楚后转向搭配、使用频率、价格是否划算。"
        "被打动信号：愿意试背、愿意看搭配、开始问价格是否值得。"
        "被推开信号：被催促下单或解释含糊时会保留。"
        "追问后的出口动作：如果正品渠道已解释清楚，下一步不要再问渠道，转向搭配闲置或价格价值。"
    ),
    "rolePlayProduct": (
        "浅棕色小号 Coach Tabby 风格肩背包。视觉特征：浅棕色、翻盖、金属扣、可肩背，整体偏日常轻熟。"
        "顾客可见信息：颜色柔和，大小适合日常出门，能放手机、纸巾、口红等小物。"
        "注意：顾客不要主动报型号、材质参数、官方卖点或库存信息。"
    ),
}


def _load_payload(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return dict(DEFAULT_PAYLOAD)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    required = {"sceneCode", "userInput", "dialogueHistory", "rolePlayPersonality", "rolePlayProduct"}
    missing = sorted(required - set(data))
    if missing:
        raise SystemExit(f"payload 缺少字段: {', '.join(missing)}")
    return data


def _load_local_env() -> None:
    """Load local KEY=VALUE config without overriding real environment variables."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(repo_root, LOCAL_ENV_FILE)
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _extract_text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for key in ("text", "result", "answer", "content", "output"):
            if key in obj:
                text = _extract_text(obj.get(key))
                if text:
                    return text
        choices = obj.get("choices")
        if isinstance(choices, list) and choices:
            return _extract_text(choices[0])
    if isinstance(obj, list):
        return "".join(_extract_text(item) for item in obj)
    return str(obj)


def _request_headers(api_key: str, stream: bool = False) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    workspace_id = os.environ.get("BAILIAN_WORKSPACE_ID")
    if workspace_id:
        headers["X-DashScope-WorkSpace"] = workspace_id
    if stream:
        headers["X-DashScope-SSE"] = "enable"
    return headers


def _post_json(url: str, api_key: str, body: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers=_request_headers(api_key),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {e.code}: {raw}") from e
    return json.loads(raw)


def _stream_json(url: str, api_key: str, body: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers=_request_headers(api_key, stream=True),
    )
    final_event: Dict[str, Any] = {}
    full_text = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", "ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload.lower() in {"[done]", "done"}:
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                final_event = event
                piece = _extract_text(event.get("output") or event)
                if piece:
                    if piece.startswith(full_text):
                        full_text = piece
                    elif not full_text.endswith(piece):
                        full_text += piece
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {e.code}: {raw}") from e
    if full_text:
        final_event.setdefault("output", {})["text"] = full_text
    return final_event


def _call_workflow(args: argparse.Namespace, payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY")
    app_id = args.app_id or os.environ.get("BAILIAN_WORKFLOW_APP_ID")
    if not api_key:
        raise SystemExit("缺少 API Key：请设置 DASHSCOPE_API_KEY 或传 --api-key")
    if not app_id:
        raise SystemExit("缺少 APP_ID：请设置 BAILIAN_WORKFLOW_APP_ID 或传 --app-id")

    base_url = (args.base_url or os.environ.get("DASHSCOPE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}/apps/{app_id}/completion"
    body: Dict[str, Any] = {
        "input": {
            # 工作流变量走 biz_params；prompt 只给一个普通 user message，避免空 user message 报错。
            "prompt": args.prompt or payload.get("userInput") or "开始本轮角色扮演",
            "biz_params": payload,
        },
        "parameters": {},
        "debug": {},
    }
    if args.stream:
        body["parameters"]["incremental_output"] = bool(args.incremental)
        body["parameters"]["flow_stream_mode"] = args.flow_stream_mode
        return _stream_json(url, api_key, body, args.timeout)
    return _post_json(url, api_key, body, args.timeout)


def _diagnose_repeat(text: str) -> Dict[str, Any]:
    repeat_terms = [
        "正品吗",
        "渠道靠谱吗",
        "靠不靠谱",
        "货源",
        "不是正品",
        "是不是假的",
        "专柜一样",
        "能再试",
        "再试背",
        "会不会太正式",
        "太正式",
        "只能正式",
    ]
    hits = [term for term in repeat_terms if term in text]
    return {
        "has_repeat_risk": bool(hits),
        "hit_terms": hits,
    }


def _write_artifact(payload: Dict[str, Any], response: Dict[str, Any], text: str, diagnosis: Dict[str, Any]) -> str:
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "陪练场景搭建",
        "公共_跨场景复用",
        "接口测试输出",
    )
    os.makedirs(out_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir, f"bailian_workflow_roleplay_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "createdAt": stamp,
                "payload": payload,
                "finalText": text,
                "diagnosis": diagnosis,
                "rawResponse": response,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="调用百炼 Workflow 并测试 Coach 角色扮演重复防护。")
    parser.add_argument("--app-id", help="百炼 Workflow 应用 APP_ID；也可用 BAILIAN_WORKFLOW_APP_ID")
    parser.add_argument("--api-key", help="DashScope API Key；也可用 DASHSCOPE_API_KEY")
    parser.add_argument("--base-url", default=None, help=f"DashScope API base URL，默认 {DEFAULT_BASE_URL}")
    parser.add_argument("--payload-json", help="覆盖内置用例的 JSON 文件路径")
    parser.add_argument("--prompt", help="input.prompt，默认使用 userInput")
    parser.add_argument("--stream", action="store_true", help="使用流式调用")
    parser.add_argument("--incremental", action="store_true", help="流式调用时开启增量输出")
    parser.add_argument("--flow-stream-mode", default="message_format", help="流式输出模式，默认 message_format")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--no-save", action="store_true", help="不保存原始响应 artifact")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    _load_local_env()
    args = build_parser().parse_args(argv)
    payload = _load_payload(args.payload_json)
    start = time.time()
    try:
        response = _call_workflow(args, payload)
    except RuntimeError as e:
        print("=== 百炼 Workflow 调用失败 ===")
        print(str(e))
        return 2
    elapsed_ms = int((time.time() - start) * 1000)

    output = response.get("output") if isinstance(response, dict) else response
    text = _extract_text(output or response).strip()
    diagnosis = _diagnose_repeat(text)

    print("=== 百炼 Workflow 调用完成 ===")
    print(f"耗时: {elapsed_ms} ms")
    request_id = response.get("request_id") if isinstance(response, dict) else None
    if request_id:
        print(f"request_id: {request_id}")
    print("\n--- 最终顾客回复 ---")
    print(text or "(未抽取到文本，请查看 raw response)")
    print("\n--- 重复风险初判 ---")
    print(json.dumps(diagnosis, ensure_ascii=False, indent=2))

    if not args.no_save:
        path = _write_artifact(payload, response, text, diagnosis)
        print(f"\n原始响应已保存: {os.path.abspath(path)}")
    return 1 if diagnosis["has_repeat_risk"] else 0


if __name__ == "__main__":
    sys.exit(main())
