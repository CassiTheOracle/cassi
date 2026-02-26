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
    const result = await response.json() as { exitCode?: number; output?: string };
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
  intelligence: { memory: true, learn: true },
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

  // Smart suggestions based on status
  let suggestions = "";
  const staged = files.filter(f => f.startsWith("A ") || f.startsWith("M ") || f.startsWith("D ") || f.startsWith("R ") || f.startsWith("C ")).length;
  const unstaged = files.filter(f => f.startsWith(" M") || f.startsWith(" D") || f.startsWith("??")).length;

  if (staged > 0 && unstaged === 0) {
    suggestions = "\n💡 Ready to commit. Use `/git commit` or `/git commit <message>`";
  } else if (unstaged > 5) {
    suggestions = "\n💡 Many unstaged changes. Consider staging with `/git add .` or committing selectively.";
  } else if (files.some(f => f.includes("merge")) || files.some(f => f.includes("both modified"))) {
    suggestions = "\n⚠️ Merge conflicts detected! Resolve before committing.";
  } else if (staged === 0 && unstaged > 0) {
    suggestions = "\n💡 Stage changes with `/git add .` before committing.";
  }

  return {
    text: "📁 On branch " + branch + "\n" + files.map(f => "  " + f).join("\n") + suggestions,
    actions: [
      { label: "Diff all", command: "/git diff" },
      { label: staged > 0 ? "Commit" : "Stage all", command: staged > 0 ? "/git commit " : "/git add ." },
    ],
  };
}

async function gitDiff(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const file = args[0] || "";
  const result = await execGit("diff " + file, ctx);
  if (!result.output.trim()) return { text: "No changes to show" };

  let summary = "";

  // AI-powered diff summary for large diffs
  if (result.output.length > 500 && ctx.intelligence?.thinker && args.includes("--summarize")) {
    try {
      const stats = await execGit("diff --stat", ctx);
      summary = `📊 Changes: ${stats.output.split('\n').pop() || 'files modified'}`;
    } catch {
      // Ignore summary errors
    }
  }

  const diff = result.output.length > 2000 ? result.output.substring(0, 2000) + "\n... (truncated, use --summarize for AI summary)" : result.output;
  return {
    text: (summary ? summary + "\n\n" : "") + "📊 Diff:\n\`\`\`diff\n" + diff + "\n\`\`\`",
    actions: [
      { label: "Stage all", command: "/git add ." },
      { label: "Commit", command: "/git commit " },
    ],
  };
}

async function gitCommit(args: string[], ctx: CommandContext): Promise<CommandResult> {
  await execGit("add -A", ctx);
  let message = args.join(" ");

  // AI-powered commit message generation
  if (!message && ctx.intelligence?.thinker?.think) {
    try {
      // Get staged diff for context
      const diffResult = await execGit("diff --cached --stat", ctx);
      const diff = diffResult.output;

      if (diff) {
        // Generate commit message using thinker
        message = await ctx.intelligence.thinker.think('Ponder');
        // Extract first line as commit message
        message = (message || '').split('\n')[0].replace(/^["']|["']$/g, '');
      }
    } catch (err) {
      // Fall back to default message
    }
  }

  message = message || "WIP: changes";
  const result = await execGit("commit -m \"" + message + "\"", ctx);
  if (result.exitCode !== 0) return { text: "❌ Commit failed:\n" + result.output };
  const hash = await execGit("rev-parse --short HEAD", ctx);

  // Store in memory if available
  if (ctx.intelligence?.memory) {
    try {
      await ctx.intelligence.memory.store({
        type: 'fact' as any,
        content: `Git commit: ${message} (${hash.output.trim()})`,
        metadata: {
          hash: hash.output.trim(),
          projectPath: ctx.projectPath,
          timestamp: Date.now(),
        },
      });
    } catch {
      // Best-effort storage
    }
  }

  return {
    text: "✅ Committed: " + message + "\nHash: " + hash.output.trim(),
    actions: [{ label: "Push", command: "/git push" }],
  };
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
  let title = args[0];
  let body = args.slice(1).join(" ");

  // AI-powered PR generation
  if ((!title || !body) && ctx.intelligence?.memory) {
    try {
      // Get recent commits from memory
      const recentCommits = await ctx.intelligence.memory.search("git-commit", {
        limit: 5,
        type: "git-commit",
      });

      if (recentCommits.length > 0 && !title) {
        // Use most recent commit message as title
        const latestCommit = recentCommits[0].entry?.content;
        if (latestCommit) {
          title = latestCommit.replace(/\([^)]+\):/g, ":").slice(0, 72);
        }
      }

      if (recentCommits.length > 0 && !body) {
        // Build PR body from recent commits
        const commitList = recentCommits
          .slice(0, 5)
          .map((r: any, i: number) => `${i + 1}. ${r.entry?.content || "unknown"}`)
          .join("\n");
        body = `## Changes\n\n${commitList}\n\n_PR created via CassiCore_`;
      }
    } catch {
      // Fall back to defaults
    }
  }

  title = title || "WIP: New changes";
  body = body || "PR created via CassiCore";

  const result = await execGit('gh pr create --title "' + title + '" --body "' + body + '"', ctx);
  if (result.exitCode === 0) {
    const url = result.output.match(/https:\/\/github\.com\/[^\s]+/)?.[0] || "";

    // Store PR in memory
    if (ctx.intelligence?.memory) {
      try {
        await ctx.intelligence.memory.store({
          type: 'fact' as any,
          content: `PR created: ${title} - ${url}`,
          metadata: {
            url,
            projectPath: ctx.projectPath,
            timestamp: Date.now(),
          },
        });
      } catch {
        // Best-effort storage
      }
    }

    return {
      text: "🚀 PR created: " + title + (url ? "\n" + url : ""),
      actions: [{ label: "View PR", command: "open " + url }],
    };
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
