import type { IConfig, ILogger } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'
import { AnthropicProvider } from './anthropic.js'
import { GitHubCopilotProvider } from './github-copilot.js'

export function createProviders(config: IConfig, logger: ILogger): Map<string, IProvider> {
  const providers = new Map<string, IProvider>()
  const anthropicKey = config.get<string>('providers.anthropic.apiKey', '')
  if (anthropicKey) {
    providers.set('anthropic', new AnthropicProvider(anthropicKey))
    logger.info('Provider loaded: anthropic')
  }

  const copilotToken = config.get<string>('providers.githubCopilot.token', '') || process.env.GITHUB_TOKEN || process.env.COPILOT_TOKEN || ''
  if (copilotToken) {
    providers.set('github-copilot', new GitHubCopilotProvider(copilotToken))
    logger.info('Provider loaded: github-copilot')
  }

  return providers
}
