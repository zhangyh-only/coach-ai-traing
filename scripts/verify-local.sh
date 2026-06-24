#!/usr/bin/env bash
# L0 本地自验证 —— 纯文档 / prompt 工程仓的"文档卫生检查"（本仓无 compile/test/run）。
# 被 Stop hook(verify-on-stop.sh) 调用：硬拦项(✗)任一不过 → exit 1 阻止 AI"收工"；提醒项(⚠)只打印、不阻断。
# 严格度＝平衡档（用户选定 2026-06-24）：稳定契约硬拦；迭代中易变项只提醒。改严/改松见文末。
# 注：避开 GNU-only 的 grep \b（macOS BSD grep 不支持），命名用 ERE、契约用 -F 固定串。
set -u
cd "$(dirname "$0")/.." || exit 0   # 切到项目根（不依赖调用方 cwd）

KBROOT="知识库搭建/具体KB内容"
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
PRODUCTS="陪练场景搭建/场景1_质感自用Elena/agent最新使用提示词.md
陪练场景搭建/公共_跨场景复用/随机机制/最新随机池内容.md
陪练场景搭建/公共_跨场景复用/随机机制/角色扮演随机机制说明.md
陪练场景搭建/0_提示词写作规范.md
知识库搭建/Coach陪练知识库架构设计_v2.md
知识库搭建/百炼知识库部署配置与命中测试清单.md
知识库搭建/Coach知识库文档生成Prompt模板_v1_2.md"
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
CONTRACT="陪练场景搭建/场景1_质感自用Elena/agent最新使用提示词.md
陪练场景搭建/公共_跨场景复用/随机机制/最新随机池内容.md"
# 正向：契约变量必须仍在（被改名则消失）
while IFS= read -r v; do
  [ -z "$v" ] && continue
  found=0
  while IFS= read -r cf; do
    [ -z "$cf" ] && continue
    grep -qF "$v" "$cf" 2>/dev/null && found=1
  done <<EOF
$CONTRACT
EOF
  [ "$found" = 1 ] && ok "契约变量在用：\${$v}" || bad "契约变量 \${$v} 消失（疑被改名 / 误删）"
done <<'EOF'
roleplay_personality
roleplay_product
EOF
# 反向：明确错误形式 ${persona} 不得出现
badvar=0
while IFS= read -r cf; do
  [ -z "$cf" ] && continue
  grep -nF '${persona}' "$cf" 2>/dev/null && badvar=1
done <<EOF
$CONTRACT
EOF
[ "$badvar" = 1 ] && bad "出现错误变量 \${persona}（应为 \${roleplay_personality}）"

# ─────────── 提醒 1：KB 各库篇数 vs v2 架构（3/11/18/5/5/4=46）───────────
echo "--- [提醒] KB 各库篇数 ---"
EXP="3 11 18 5 5 4"
tot=0; drift=0; i=1
for e in $EXP; do
  c=$(find "$KBROOT/KB$i" -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  tot=$((tot+c))
  [ "$c" = "$e" ] || { warn "KB$i 篇数 $c ≠ 预期 $e（v2 架构若已调整，请更新本脚本 EXP）"; drift=1; }
  i=$((i+1))
done
[ "$drift" = 0 ] && ok "KB 篇数 3/11/18/5/5/4=$tot，对齐 v2"

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
