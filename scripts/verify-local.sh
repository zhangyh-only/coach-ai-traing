#!/usr/bin/env bash
# L0 本地自验证 —— 纯文档 / prompt 工程仓的"文档卫生检查"（本仓无 compile/test/run）。
# 被 Stop hook(verify-on-stop.sh) 调用：硬拦项(✗)任一不过 → exit 1 阻止 AI"收工"；提醒项(⚠)只打印、不阻断。
# 严格度＝平衡档（用户选定 2026-06-24）：稳定契约硬拦；迭代中易变项只提醒。改严/改松见文末。
# 注：避开 GNU-only 的 grep \b（macOS BSD grep 不支持），命名用 ERE、契约用 -F 固定串。
set -u
cd "$(dirname "$0")/.." || exit 0   # 切到项目根（不依赖调用方 cwd）

KBROOT="知识库搭建/kbase"
FAIL=0
ok(){   printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn(){ printf '  \033[33m⚠\033[0m %s\n' "$1"; }
bad(){  printf '  \033[31m✗\033[0m %s\n' "$1"; FAIL=1; }

echo "=== 文档卫生检查（纯文档项目，无编译/测试；真验收在百炼侧 T1–T21 人工跑）==="

# ─────────── 硬拦 1：KB 文件命名规范 KB[1-6]-分类-标题.md ───────────
echo "--- [硬拦] KB 文件命名 ---"
if [ -d "$KBROOT" ]; then
  n=0
  while IFS= read -r f; do
    b="$(basename "$f")"
    printf '%s' "$b" | grep -qE '^KB[1-6]-[^-]+-.+\.md$' || { bad "命名不符 KB[1-6]-分类-标题.md：$f"; n=$((n+1)); }
  done < <(find "$KBROOT" -type f -name '*.md')
  [ "$n" = 0 ] && ok "全部 KB 文件名合规"
else
  warn "$KBROOT 不存在，跳过命名检查"
fi

# ─────────── 硬拦 2：定稿 / 单一事实源产物存在且非空 ───────────
echo "--- [硬拦] 定稿产物存在性 ---"
PRODUCTS="陪练场景搭建/场景1_质感自用Elena/正价场景-最新使用提示词.md
陪练场景搭建/场景2_奥莱私域轻奢Bella/奥莱场景-最新使用提示词.md
陪练场景搭建/场景1_质感自用Elena/随机机制/最新随机池内容.md
陪练场景搭建/场景2_奥莱私域轻奢Bella/随机机制/最新随机池内容.md
陪练场景搭建/0_提示词写作规范.md
知识库搭建/Coach陪练知识库架构设计_v2.md"
miss=0
while IFS= read -r p; do
  [ -z "$p" ] && continue
  [ -s "$p" ] || { bad "缺失或空：$p"; miss=$((miss+1)); }
done <<EOF
$PRODUCTS
EOF
[ "$miss" = 0 ] && ok "定稿产物齐备"

# ─────────── 硬拦 3：百炼变量名契约（防 persona 回潮，6-24 事故根因）───────────
echo "--- [硬拦] 百炼变量名契约 ---"
PROMPT_CONTRACTS=(
  "陪练场景搭建/场景1_质感自用Elena/正价场景-最新使用提示词.md"
  "陪练场景搭建/场景2_奥莱私域轻奢Bella/奥莱场景-最新使用提示词.md"
)
POOL_CONTRACTS=(
  "陪练场景搭建/场景1_质感自用Elena/随机机制/最新随机池内容.md"
  "陪练场景搭建/场景2_奥莱私域轻奢Bella/随机机制/最新随机池内容.md"
)

# 每个场景 prompt 都必须独立保有三个精确占位，不允许跨文件串证。
for cf in "${PROMPT_CONTRACTS[@]}"; do
  for v in rolePlayPersonality rolePlayProduct rolePlayState; do
    token="{${v}}"
    if grep -qF "$token" "$cf" 2>/dev/null; then
      ok "$(basename "$cf") 契约占位在用：${token}"
    else
      bad "$(basename "$cf") 缺少精确契约占位 ${token}"
    fi
  done
done

# 每个合并随机池都必须独立保有性格池与产品池键。
for cf in "${POOL_CONTRACTS[@]}"; do
  for v in rolePlayPersonality rolePlayProduct; do
    token="\"${v}\""
    if grep -qF "$token" "$cf" 2>/dev/null; then
      ok "$(basename "$(dirname "$cf")")/$(basename "$cf") 合并池键在用：${v}"
    else
      bad "${cf} 缺少合并池键 ${v}"
    fi
  done
done

# 每个场景的 enabled 产品必须有唯一款号，且不能依赖“待补 / 按门店实物观察”这类
# 无视觉模型无法兑现的占位说法。disabled 卡保留问题与恢复线索，不参与该检查。
echo "--- [硬拦] 双场景随机产品池可用性 ---"
for ROLEPLAY_POOL in "${POOL_CONTRACTS[@]}"; do
if python3 - "$ROLEPLAY_POOL" <<'PY'
import json
import re
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.S)
objects = [json.loads(block) for block in blocks]
merged = next((item for item in objects if isinstance(item, dict) and "rolePlayProduct" in item), None)
if merged is None or not isinstance(merged.get("rolePlayProduct"), list):
    print("  未找到合法的 rolePlayProduct 数组")
    raise SystemExit(1)

enabled = [item for item in merged["rolePlayProduct"] if item.get("enabled") is True]
errors = []
expected_counts = (44, 16) if "场景1_" in path else (13, 12)
actual_counts = (len(merged["rolePlayProduct"]), len(enabled))
if actual_counts != expected_counts:
    errors.append(
        f"产品池规模漂移：总数/启用应为 {expected_counts[0]}/{expected_counts[1]}，"
        f"实际为 {actual_counts[0]}/{actual_counts[1]}"
    )
seen = {}
for item in enabled:
    name = item.get("name", "")
    content = item.get("content", "")
    if re.search(r"待补|按门店实物观察", name + content):
        errors.append(f"enabled 产品仍含无法兑现的占位说法：{name}")
    sku_matches = re.findall(r"\[款号\s+([^\]]+)\]", content)
    if len(sku_matches) != 1:
        errors.append(f"enabled 产品款号数量不是 1：{name}")
        continue
    sku = sku_matches[0]
    if sku in seen:
        errors.append(f"enabled 产品重复款号 {sku}：{seen[sku]} / {name}")
    else:
        seen[sku] = name

expected_skus = (
    {
        "CY920", "CW628", "CAM91", "CT721", "CW604", "CAM98", "CAM84", "CW620",
        "CW631", "CY201", "CP149", "CI032", "CCC12", "CCX04", "CCW92", "CZ747",
    }
    if "场景1_" in path
    else {
        "CI032", "CW631", "CP149", "CY919", "CW620", "CY201",
        "CY920", "CAM98", "CCC12", "CW628", "CAM92", "CBA26",
    }
)
if set(seen) != expected_skus:
    errors.append(
        "enabled 产品清单漂移："
        f"缺少 {sorted(expected_skus - set(seen))}，"
        f"多出 {sorted(set(seen) - expected_skus)}"
    )

if errors:
    for error in errors:
        print(f"  {error}")
    raise SystemExit(1)
print(f"  enabled 产品 {len(enabled)} 张，款号唯一且无待补占位")
PY
then
  ok "$(basename "$(dirname "$ROLEPLAY_POOL")")/$(basename "$ROLEPLAY_POOL") 可用性通过"
else
  bad "${ROLEPLAY_POOL} 存在 enabled 问题卡"
fi
done

# 双场景性格池稳定口径：正价启用 A / D，奥莱启用 C / D。
echo "--- [硬拦] 双场景随机性格池启用口径 ---"
for ROLEPLAY_POOL in "${POOL_CONTRACTS[@]}"; do
if python3 - "$ROLEPLAY_POOL" <<'PY'
import json
import re
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.S)
objects = [json.loads(block) for block in blocks]
merged = next((item for item in objects if isinstance(item, dict) and "rolePlayPersonality" in item), None)
if merged is None or not isinstance(merged.get("rolePlayPersonality"), list):
    print("  未找到合法的 rolePlayPersonality 数组")
    raise SystemExit(1)

enabled = [item.get("name", "") for item in merged["rolePlayPersonality"] if item.get("enabled") is True]
expected = {"C-怕踩坑型", "D-心动型"} if "场景2_奥莱" in path else {"A-价值型", "D-心动型"}
if set(enabled) != expected:
    print(f"  enabled 性格应为 {sorted(expected)}，实际为 {enabled}")
    raise SystemExit(1)
print(f"  enabled 性格稳定口径通过：{enabled}")
PY
then
  ok "$(basename "$(dirname "$ROLEPLAY_POOL")")/$(basename "$ROLEPLAY_POOL") 性格池通过"
else
  bad "${ROLEPLAY_POOL} 性格池启用口径不符"
fi
done

# 反向：明确错误的旧占位不得出现。
for cf in "${PROMPT_CONTRACTS[@]}" "${POOL_CONTRACTS[@]}"; do
  for token in '{persona}' '{roleplay_personality}' '{roleplay_product}' '{roleplay_state}'; do
    grep -qF "$token" "$cf" 2>/dev/null && bad "${cf} 出现错误旧占位 ${token}"
  done
done

# ─────────── 提醒 1：KB 各库篇数 vs v2 架构（3/11/18/5/5/4=46）───────────
echo "--- [提醒] KB 各库篇数 ---"
EXP=(3 11 18 5 5 4)
tot=0; drift=0; i=1
for e in "${EXP[@]}"; do
  c=$(find "$KBROOT/KB$i" -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  tot=$((tot+c))
  [ "$c" = "$e" ] || { warn "KB$i 篇数 $c ≠ 预期 ${e}（v2 架构若已调整，请更新本脚本 EXP）"; drift=1; }
  i=$((i+1))
done
[ "$drift" = 0 ] && ok "KB 篇数 3/11/18/5/5/4=${tot}，对齐 v2"

# ─────────── 提醒 2：markdown 相对链接死链 ](xxx.md) ───────────
# 注：不查 Obsidian [[双链]]——按项目约定 [[未建笔记]] 是合法占位（标记待写）。
echo "--- [提醒] 相对 .md 链接死链 ---"
tmp_dead="$(mktemp 2>/dev/null || echo /tmp/.coach_dead.$$)"
: > "$tmp_dead"
while IFS= read -r md; do
  d="$(dirname "$md")"
  grep -oE '\]\([^)]+\.md[^)]*\)' "$md" 2>/dev/null | while IFS= read -r m; do
    tgt="${m#](}"; tgt="${tgt%)}"; tgt="${tgt%%#*}"
    [ -z "$tgt" ] && continue
    case "$tgt" in http*|//*|/*) continue ;; esac
    [ -e "$d/$tgt" ] || [ -e "$tgt" ] || printf '      %s → %s\n' "$md" "$tgt" >> "$tmp_dead"
  done
done < <(find . -name '*.md' -not -path './tmp/*' -not -path './.git/*' 2>/dev/null)
if [ -s "$tmp_dead" ]; then
  warn "发现相对 .md 链接死链（首 10 条；不阻断收工）："
  head -10 "$tmp_dead"
else
  ok "未发现相对 .md 链接死链"
fi
rm -f "$tmp_dead"

# ─────────── 提醒 3：KB 元信息（抽检头部是否含元信息标签）───────────
echo "--- [提醒] KB 元信息五字段抽检 ---"
missmeta=0
while IFS= read -r f; do
  head -40 "$f" | grep -qE '文档编号|所属知识库' || { warn "疑缺元信息：$f"; missmeta=$((missmeta+1)); }
done < <(find "$KBROOT" -type f -name '*.md' 2>/dev/null)
[ "$missmeta" = 0 ] && ok "KB 元信息抽检通过"

echo
if [ "$FAIL" = 0 ]; then
  echo "=== ✓ 硬拦项全过（提醒项见上，可改完一并处理）==="
  exit 0
else
  echo "=== ✗ 有硬拦项未过，请修复后再收工 ==="
  exit 1
fi

# ── 调严：把某个 warn 改成 bad（如把篇数 / 死链升为硬拦）。调松：把 bad 改成 warn。
# ── 明确不做（脚本不伪装能验）：prompt 行为质量、百炼 T1–T21 命中测试（需登录百炼控制台真跑）、
#    画像映射【待人工确认】、待客户补充门店主数据的真实性——只能人工 / 平台侧验收。
