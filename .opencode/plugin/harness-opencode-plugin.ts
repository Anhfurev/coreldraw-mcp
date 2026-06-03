import type { Plugin } from "@opencode-ai/plugin"
import { existsSync, readFileSync } from "fs"
import { join } from "path"

// harness-kit OpenCode Plugin
// 等价于 Claude Code 的 SessionStart + Stop hook
//
// 安装：此文件由 install.sh 自动放置在 .opencode/plugin/
// OpenCode 启动时自动加载，无需任何手动操作

export const HarnessPlugin: Plugin = async ({ client }) => {
  const HARNESS_DIR = ".harness"
  const INDEX_FILE  = join(HARNESS_DIR, "registry", "_index.md")

  const harnessExists       = () => existsSync(HARNESS_DIR)
  let   sessionEndInjected  = false

  const buildStartContext = (): string => {
    const parts: string[] = []

    if (existsSync(INDEX_FILE)) {
      const recent = readFileSync(INDEX_FILE, "utf-8")
        .split("\n")
        .filter((l) => l.startsWith("[") && !l.includes("初始化日期"))
        .slice(0, 5)
      if (recent.length) parts.push("## 最近决策\n" + recent.join("\n"))
    }

    const sprintFile = join(HARNESS_DIR, "state", "current-sprint.md")
    if (existsSync(sprintFile)) {
      parts.push("## 当前阶段\n" + readFileSync(sprintFile, "utf-8").slice(0, 400))
    }

    const featFile = join(HARNESS_DIR, "state", "features.json")
    if (existsSync(featFile)) {
      try {
        const data    = JSON.parse(readFileSync(featFile, "utf-8"))
        const pending = (data.features || []).filter((f: any) => !f.passes)
        parts.push(
          `## 未完成功能（${pending.length} 个）\n` +
          pending.slice(0, 5).map((f: any) => `- ${f.id}: ${f.description}`).join("\n")
        )
      } catch {}
    }
    const startFile = join(HARNESS_DIR, "SESSION_START.md")
    if (existsSync(startFile)) {
      parts.push("---\n" + readFileSync(startFile, "utf-8"))
    }

    return parts.join("\n\n")
  }

  return {
    event: async ({ event }) => {

      // ── SessionStart 等价 ───────────────────────────────────────
      if (event.type === "session.created") {
        if (!harnessExists()) return
        const ctx = buildStartContext()
        if (!ctx) return

        await client.session.prompt({
          path: { id: event.properties.info.id },
          body: { parts: [{
            type: "text",
            text: [
              "【HARNESS SESSION START】",
              "",
              ctx,
              "",
              "---",
              "请先向用户汇报以上状态（上次完成了什么、当前未完成项、建议本次做什么），",
              "等用户确认后再开始任何实质性工作。",
            ].join("\n"),
          }] },
        })
      }

      // ── Stop 等价：session.idle = Agent 完成本轮响应 ───────────
      if (event.type === "session.idle") {
        if (!harnessExists())       return
        if (sessionEndInjected)    return

        const endFile    = join(HARNESS_DIR, "SESSION_END.md")
        const endContent = existsSync(endFile)
          ? readFileSync(endFile, "utf-8")
          : "请完成最低要求：\n1. 在 .harness/registry/sessions/ 创建今天的摘要\n2. 更新 _index.md\n3. git commit .harness/"

        sessionEndInjected = true

        await client.session.prompt({
          path: { id: event.properties.sessionID },
          body: { parts: [{
            type: "text",
            text: [
              "⚠️ 【HARNESS：SESSION_END 未完成】",
              "",
              "今天还没有执行 SESSION_END 清单。请现在执行：",
              "",
              endContent,
            ].join("\n"),
          }] },
        })
      }
    },
  }
}
