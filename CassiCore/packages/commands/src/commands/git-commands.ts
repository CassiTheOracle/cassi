// Git Command Handlers for Universal Processor

import type { CommandContext, CommandResult } from "./universal-processor.js";
import { processor } from "./universal-processor.js";

async function execGit(command: string, ctx: CommandContext): Promise<{ exitCode: number; output: string }> {
  try {
    const response = await fetch("http://localhost:7432/tools/bash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command: "cd " + (ctx.projectPath || ".") + " && git " + command,
        timeout: 30000
      })
    });
    const result = await response.json();
    return { exitCode: result.exitCode ?? 0, output: result.output || "" };
  } catch {
    return { exitCode: 1, output: "Git command failed" };
  }
}

processor.register({
  name: "/git",
  aliases: ["/g"],
  category: "git",
  description: "Git operations: status, diff, commit, branch, pr, review",
  handler: async (args, ctx) => {
    const subcmd = args[0] || "status";
    const gitArgs = args.slice(1);
    switch (subcmd) {
      case "status": return gitStatus(ctx);
      case "diff": return gitDiff(gitArgs, ctx);
      case "commit": return gitCommit(gitArgs, ctx);
      case "branch": return gitBranch(gitArgs, ctx);
      case "checkout": return gitCheckout(gitArgs, ctx);
      case "merge": return gitMerge(gitArgs, ctx);
      case "pr": return gitPullRequest(gitArgs, ctx);
      case "review": return gitReview(gitArgs, ctx);
      case "log": return gitLog(gitArgs, ctx);
      case "push": return gitPush(gitArgs, ctx);
      case "pull": return gitPull(gitArgs, ctx);
      default: return { text: "Unknown git command. Try: /git status" };
    }
  }
});

async function gitStatus(ctx: CommandContext): Promise<CommandResult> {
  const result = await execGit("status --short --branch", ctx);
  if (!result.output.trim()) {
    return { text: "✅ Working tree clean", actions: [{ label: "View log", command: "/git log" }] };
  }
  const lines = result.output.split("\n");
  const branch = lines[0].replace("## ", "");
  const files = lines.slice(1).filter(l => l.trim());
  return { text: "📁 On branch " + branch + "\n" + files.map(f => "  " + f).join("\n"), actions: [{ label: "Diff all", command: "/git diff" }, { label: "Commit", command: "/git commit " }] };
}

async function gitDiff(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const file = args[0] || "";
  const result = await execGit("diff " + file, ctx);
  if (!result.output.trim()) return { text: "No changes to show" };
  const diff = result.output.length > 2000 ? result.output.substring(0, 2000) + "\n... (truncated)" : result.output;
  return { text: "📊 Diff:\n\`\`\`diff\n" + diff + "\n\`\`\`", actions: [{ label: "Stage all", command: "/git add ." }, { label: "Commit", command: "/git commit " }] };
}

async function gitCommit(args: string[], ctx: CommandContext): Promise<CommandResult> {
  await execGit("add -A", ctx);
  const message = args.join(" ") || "WIP: changes";
  const result = await execGit("commit -m \"" + message + "\"", ctx);
  if (result.exitCode !== 0) return { text: "❌ Commit failed:\n" + result.output };
  const hash = await execGit("rev-parse --short HEAD", ctx);
  return { text: "✅ Committed: " + message + "\nHash: " + hash.output.trim(), actions: [{ label: "Push", command: "/git push" }] };
}

async function gitBranch(args: string[], ctx: CommandContext): Promise<CommandResult> {
  if (args.length === 0) {
    const result = await execGit("branch -vv", ctx);
    return { text: "🌿 Branches:\n" + result.output };
  }
  const branchName = args[0];
  const result = await execGit("checkout -b " + branchName, ctx);
  return { text: result.exitCode === 0 ? "✅ Created and switched to branch: " + branchName : "❌ Failed:\n" + result.output };
}

async function gitCheckout(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const branch = args[0];
  const result = await execGit("checkout " + branch, ctx);
  return { text: result.exitCode === 0 ? "✅ Switched to " + branch : "❌ " + result.output };
}

async function gitMerge(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const branch = args[0];
  const result = await execGit("merge " + branch, ctx);
  return { text: result.exitCode === 0 ? "✅ Merged " + branch : "❌ Merge conflict!\n" + result.output };
}

async function gitPullRequest(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const title = args[0] || "WIP: New changes";
  const body = args.slice(1).join(" ") || "PR created via CassiCore";
  const result = await execGit("gh pr create --title \"" + title + "\" --body \"" + body + "\"", ctx);
  if (result.exitCode === 0) {
    const url = result.output.match(/https:\/\/github\.com\/[^\s]+/)?.[0] || "";
    return { text: "🚀 PR created: " + title, actions: [{ label: "View PR", command: "open " + url }] };
  }
  return { text: "❌ PR creation failed:\n" + result.output };
}

async function gitReview(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const result = await execGit("gh pr list", ctx);
  return { text: "🔍 Open PRs:\n" + result.output };
}

async function gitLog(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const n = args[0] || "10";
  const result = await execGit("log --oneline -" + n, ctx);
  return { text: "📜 Last " + n + " commits:\n" + result.output };
}

async function gitPush(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const result = await execGit("push", ctx);
  return { text: result.exitCode === 0 ? "✅ Pushed to remote" : "❌ Push failed:\n" + result.output };
}

async function gitPull(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const result = await execGit("pull", ctx);
  return { text: result.exitCode === 0 ? "✅ Pulled latest changes" : "❌ Pull failed:\n" + result.output };
}
