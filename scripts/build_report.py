#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coach 角色扮演链 · 测试记录数据汇总器
==================================================
扫 记录/接口测试输出/session_rec*.json 里**所有**测试记录 → 汇总成一个数据文件 records.js。
配套固定的查看器页面 `测试记录查看器.html`（写一次、不再变）：它 <script src=records.js> 加载本数据、
动态渲染所有局。**不再每次生成新 HTML**——新测试只增 session JSON、刷新 records.js（测试脚本会自动刷），
打开同一个查看器就能看到全部历史记录。

每条记录带：抽到的性子(A/B/C/D)+产品、SA↔Elena 全程对话气泡、我(测试者)的人工分析、规则初筛(辅助导航)。

用法：python3 scripts/build_report.py   # 重扫所有 session、刷新 records.js
"""
import json
import os
import re
import sys
import glob
import datetime
import difflib

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "陪练场景搭建", "场景1_质感自用Elena", "记录", "接口测试输出")
DATA_JS = os.path.join(OUT_DIR, "records.js")

PERSONA_MAP = [
    ("D", "心动型", ["一眼就相中", "藏不住喜欢", "热络", "话偏多"]),
    ("B", "比价型", ["别家", "拿这只跟", "凭啥这个价", "凭啥这价", "比较"]),
    ("A", "理性型", ["平稳", "偏冷静", "有条理", "看明白了再"]),
    ("C", "冷淡型", ["有点累", "话很少", "往后躲", "慢热"]),
]
CONCERN_KW = {
    "容量": ["装得下", "能装", "塞得下", "够不够装", "装下", "装不装", "塞进去", "能不能装"],
    "耐用/磨损": ["变形", "会塌", "没型", "划痕", "刮花", "刮", "耐磨", "磨损", "磨花", "掉色", "发黑", "显脏", "娇气", "印子", "细痕"],
    "重量": ["太沉", "重不重", "沉不沉", "肩膀"],
    "材质": ["什么皮", "真皮", "皮质", "牛皮", "皮料"],
    "价格/值不值": ["多少钱", "贵", "凭啥", "值不值", "性价比", "别家", "划算"],
}
CAP_KW = ["装得下", "能装", "塞得下", "够不够装", "装下", "装不装", "能不能装"]


def _split(text):
    narrs = re.findall(r"（[^）]*）|\([^)]*\)", text or "")
    core = re.sub(r"（[^）]*）|\([^)]*\)", "", text or "").strip()
    return core, narrs


def _sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def auto_screen(turns):
    """规则初筛(辅助)。返回 {loop:[(type,detail)]}。"""
    out, seen, tried, prev = {}, {}, None, None
    for t in turns:
        loop = t["loop"]
        core, narrs = _split(t.get("elena", ""))
        nt = " ".join(narrs)
        m = []
        if prev and core and _sim(core, prev) >= 0.8:
            m.append(("复读", f"与上轮相似 {_sim(core, prev):.0%}"))
        if tried is not None and re.search(r"(能上身|能试|试一下|试背|能不能试|上身试)", core):
            m.append(("重复申请动作", f"第{tried}轮已试背"))
        if re.search(r"背上了肩|背到肩上|背上肩|试背|背到了肩", nt) and tried is None:
            tried = loop
        if any(k in core for k in CAP_KW):
            m.append(("疑似目测容量", "见实物仍问能否装下"))
        for cat, kws in CONCERN_KW.items():
            if any(k in core for k in kws):
                if cat in seen and seen[cat] != loop:
                    m.append(("同类关切重复", f"『{cat}』第{seen[cat]}轮已起"))
                else:
                    seen.setdefault(cat, loop)
        if nt and len(nt) > 40:
            m.append(("旁白过长", f"{len(nt)}字"))
        if m:
            out[loop] = m
        prev = core or prev
    return out


def classify(text):
    for code, name, kws in PERSONA_MAP:
        if any(k in (text or "") for k in kws):
            return code, name
    return "?", "未识别"


def load_sessions():
    res = []
    for jp in sorted(glob.glob(os.path.join(OUT_DIR, "session_rec*.json"))):
        try:
            with open(jp, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        d["persona_code"], d["persona_name"] = classify(d.get("personality", ""))
        auto = auto_screen(d.get("turns", []))
        ana = d.get("analysis") or {}
        manual = {}
        for it in (ana.get("issues") or []):
            manual.setdefault(it["loop"], []).append((it.get("type", ""), it.get("detail", "")))
        for t in d.get("turns", []):
            core, narrs = _split(t.get("elena", ""))
            t["elena_core"] = core
            t["elena_narr"] = narrs
            t["manual"] = manual.get(t["loop"], [])
            t["auto"] = auto.get(t["loop"], [])
        d["analyzed"] = bool(d.get("analysis"))
        d["has_problem"] = ("问题" in ana.get("verdict", "")) if d["analyzed"] else (len(auto) > 0)
        res.append(d)
    return res


def build():
    sessions = load_sessions()
    by_p = {"A": 0, "B": 0, "C": 0, "D": 0, "?": 0}
    for s in sessions:
        by_p[s["persona_code"]] = by_p.get(s["persona_code"], 0) + 1
    issue_sessions = sum(1 for s in sessions if s.get("has_problem"))
    meta = {
        "total": len(sessions),
        "issueSessions": issue_sessions,
        "byPersona": by_p,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    body = ("// 自动生成、勿手改。由 scripts/build_report.py 扫所有 session_rec*.json 汇总而来。\n"
            "window.RECORDS = " + json.dumps(sessions, ensure_ascii=False) + ";\n"
            "window.RECORDS_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write(body)
    return meta


if __name__ == "__main__":
    m = build()
    print(f"✓ records.js 已刷新：{m['total']} 局 | {m['issueSessions']} 局有问题 | "
          f"A/B/C/D={m['byPersona']['A']}/{m['byPersona']['B']}/{m['byPersona']['C']}/{m['byPersona']['D']}")
