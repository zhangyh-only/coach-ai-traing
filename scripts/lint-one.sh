#!/usr/bin/env bash
# 语言适配器 —— 整套工作流里唯一按语言分叉的地方。
# 被全局 hook lint-changed.sh 调用：传入刚改的单个文件，跑对应语言的检查器。
# 约定：检查通过 exit 0；不通过 exit 非0 并把问题打到 stdout/stderr。
# 工具未装 / 检查器未配 / 文件不存在 → exit 0 跳过（不阻断编码）。按你的项目实际命令调整每个分支即可。

f="$1"
[ -z "$f" ] && exit 0
[ -f "$f" ] || exit 0     # 文件不存在 → 无可检，跳过

case "$f" in
  *.java)
    command -v mvn >/dev/null 2>&1 || exit 0
    # 仅当项目确实配了 checkstyle 才跑；没 pom / 没配 → 跳过、不阻断
    # （接好检查器前，别让"还没接"变成"改不了 Java"。按需替换成你项目的实际检查命令。）
    d="$(cd "$(dirname "$f")" 2>/dev/null && pwd)" || exit 0
    pom=""
    while [ -n "$d" ] && [ "$d" != "/" ]; do
      [ -f "$d/pom.xml" ] && { pom="$d/pom.xml"; break; }
      d="$(dirname "$d")"
    done
    [ -n "$pom" ] && grep -q checkstyle "$pom" 2>/dev/null || exit 0
    # 只查刚改的这个文件：checkstyle:check 默认扫【全模块】，会拦下所有存量违规、且每次编辑都全量跑，
    # 与 lint-one「只检刚改的 $f」的本意冲突（存量靠"改到即收敛"或 CI 基线，不在每次编辑批量拦）。
    # 取相对 source root 的路径喂 -Dcheckstyle.includes（假定 Maven 标准布局 src/main|test/java）。
    # presence 类规则（方法/类必有 Javadoc 等）接成靶向硬闸的范式见 rig 的 reference/recipes/java-checkstyle-javadoc.md。
    rel="${f##*src/main/java/}"; [ "$rel" = "$f" ] && rel="${f##*src/test/java/}"
    ( cd "$(dirname "$pom")" && mvn -q -o checkstyle:check -Dcheckstyle.includes="$rel" ) 2>&1
    ;;
  *.ts|*.tsx|*.js|*.jsx)
    command -v npx >/dev/null 2>&1 || exit 0
    npx --no-install eslint --version >/dev/null 2>&1 || exit 0   # eslint 没装 → 跳过
    npx --no-install eslint "$f" 2>&1
    ;;
  *.py)
    command -v ruff >/dev/null 2>&1 || exit 0
    ruff check "$f" 2>&1
    ;;
  *.go)
    command -v golangci-lint >/dev/null 2>&1 || exit 0
    golangci-lint run 2>&1
    ;;
  *)
    exit 0
    ;;
esac
