import { describe, expect, it } from 'vitest'

const frontendSourceModules = import.meta.glob('../**/*.{ts,tsx}', {
  eager: true,
  import: 'default',
  query: '?raw',
}) as Record<string, string>

describe('frontend location API boundaries', () => {
  it('contains no direct geocoding provider URL or API key identifier', () => {
    const frontendSource = Object.entries(frontendSourceModules)
      .filter(([path]) => !path.includes('.test.'))
      .map(([, source]) => source)
      .join('\n')
    const providerApiHost = ['maps', 'googleapis', 'com'].join('.')
    const providerApiKeyIdentifier = ['GOOGLE', 'MAPS', 'API', 'KEY'].join('_')

    expect(frontendSource).not.toContain(providerApiHost)
    expect(frontendSource).not.toContain(providerApiKeyIdentifier)
  })
})
