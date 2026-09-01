import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { OpportunityDetail } from '../../api/opportunities'
import OpportunityDetailPage from './OpportunityDetailPage'

const fullDescription =
  'Construction of a new industrial manufacturing facility with electrical infrastructure, switchgear rooms, external lighting, and associated site development works.'

const opportunity: OpportunityDetail = {
  id: 20,
  application_number: '0012345',
  planning_authority: 'Kerry County Council',
  description: fullDescription,
  address: 'Manor West Business Park, Tralee, Co. Kerry',
  application_type: 'Permission',
  application_status: 'Pending',
  decision: null,
  received_date: '2026-08-18',
  application_url: 'https://example.test/generic-planning-search',
  category: 'industrial',
  opportunity_score: 96,
  raw_opportunity_score: 96,
  opportunity_level: 'very_high',
  opportunity_breakdown: {
    project_scope: 30,
    electrical_relevance: 30,
    project_scale: 16,
    lead_timing: 10,
    category_fit: 10,
  },
  opportunity_score_components: [
    {
      name: 'project_scope',
      points_awarded: 30,
      maximum_points: 30,
      explanation: 'New industrial development indicators were identified.',
    },
    {
      name: 'electrical_relevance',
      points_awarded: 30,
      maximum_points: 30,
      explanation:
        'The planning description includes "electrical infrastructure", a strong electrical indicator.',
    },
    {
      name: 'project_scale',
      points_awarded: 16,
      maximum_points: 20,
      explanation:
        'A floor area of 2,500 square metres was identified, indicating a large development.',
    },
    {
      name: 'lead_timing',
      points_awarded: 10,
      maximum_points: 10,
      explanation:
        'The application was received 6 days ago, within the last 14 days.',
    },
    {
      name: 'category_fit',
      points_awarded: 10,
      maximum_points: 10,
      explanation:
        'The application is classified as Industrial, which receives 10 points for category fit.',
    },
  ],
  electrical_work_brief: {
    evidence_level: 'direct',
    summary: 'Electrical work evidenced: electrical installation work.',
    signals: [
      {
        work_type: 'electrical_installation',
        evidence: 'electrical infrastructure',
      },
    ],
  },
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

describe('OpportunityDetailPage', () => {
  let fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(jsonResponse(opportunity))
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('retrieves and renders the complete opportunity with search distance', async () => {
    render(<OpportunityDetailPage opportunityId={20} distanceKm={18.664272} />)

    expect(screen.getByRole('status')).toHaveTextContent('Loading opportunity')

    const detail = await screen.findByRole('article')
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/planning-applications/20')
    expect(
      within(detail).getByRole('heading', {
        level: 2,
        name: 'Opportunity 0012345 details',
      }),
    ).toBeInTheDocument()
    expect(within(detail).getByText('Very high opportunity')).toBeInTheDocument()
    expect(within(detail).getByText('96')).toBeInTheDocument()
    expect(within(detail).getByText(fullDescription)).toBeInTheDocument()
    expect(within(detail).getByText('Industrial')).toBeInTheDocument()
    expect(within(detail).getByText('18.7 km')).toBeInTheDocument()
    expect(within(detail).getByText('18 August 2026')).toBeInTheDocument()
    expect(
      within(detail).getByText('Manor West Business Park, Tralee, Co. Kerry'),
    ).toBeInTheDocument()
    expect(within(detail).getByText('Kerry County Council')).toBeInTheDocument()
    expect(within(detail).getByText('Pending')).toBeInTheDocument()
    expect(within(detail).getByText('0012345')).toBeInTheDocument()
    expect(
      within(detail).getByRole('heading', {
        level: 3,
        name: 'Confirmed electrical work',
      }),
    ).toBeInTheDocument()
    const signalIndicator = within(detail).getByRole('img', {
      name: 'Electrical signal: confirmed electrical work',
    })
    expect(
      signalIndicator.querySelectorAll(
        '.electrical-signal-indicator__icon--active',
      ),
    ).toHaveLength(3)
    expect(
      within(detail).queryByText('Evidence: electrical infrastructure'),
    ).not.toBeInTheDocument()

    const breakdown = within(detail)
      .getByRole('heading', { level: 3, name: 'Score breakdown' })
      .closest('section')
    expect(breakdown).not.toBeNull()
    expect(within(breakdown as HTMLElement).getByText('Project scope')).toBeInTheDocument()
    expect(
      within(breakdown as HTMLElement).getByText('Electrical relevance'),
    ).toBeInTheDocument()
    expect(within(breakdown as HTMLElement).getByText('Project scale')).toBeInTheDocument()
    expect(within(breakdown as HTMLElement).getByText('Lead timing')).toBeInTheDocument()
    expect(within(breakdown as HTMLElement).getByText('Category fit')).toBeInTheDocument()
    expect(within(breakdown as HTMLElement).getAllByText('30 / 30')).toHaveLength(2)
    expect(within(breakdown as HTMLElement).getByText('16 / 20')).toBeInTheDocument()
    expect(
      within(breakdown as HTMLElement).getByText(
        'The planning description includes "electrical infrastructure", a strong electrical indicator.',
      ),
    ).toBeInTheDocument()
    expect(
      within(breakdown as HTMLElement).getByText(
        'The application is classified as Industrial, which receives 10 points for category fit.',
      ),
    ).toBeInTheDocument()
  })

  it('constructs the verified Kerry link and preserves an opaque reference', async () => {
    render(<OpportunityDetailPage opportunityId={20} />)

    const officialApplicationLink = await screen.findByRole('link', {
      name: 'View official application (opens in a new tab)',
    })
    expect(officialApplicationLink).toHaveAttribute(
      'href',
      'https://www.eplanning.ie/KerryCC/AppFileRefDetails/0012345/0',
    )
    expect(officialApplicationLink).toHaveAttribute('target', '_blank')
    expect(officialApplicationLink).toHaveAttribute(
      'rel',
      'noopener noreferrer',
    )
  })

  it('explains when a substantial development is an inferred opportunity', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...opportunity,
        electrical_work_brief: {
          evidence_level: 'inferred',
          summary:
            'Potential electrical package associated with a substantial industrial development -- review plans for confirmation.',
          signals: [],
        },
      }),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    expect(
      await screen.findByText('Implied electrical work'),
    ).toBeInTheDocument()
  })

  it.each([
    [
      'unavailable',
      70,
      39,
      'Raw score: 70. Final score capped at 39 because no specific electrical opportunity was identified.',
    ],
    [
      'possible',
      70,
      59,
      'Raw score: 70. Final score capped at 59 because electrical work is possible but not strongly evidenced.',
    ],
    [
      'inferred',
      85,
      79,
      'Raw score: 85. Final score capped at 79 because electrical work is inferred rather than directly evidenced.',
    ],
  ])(
    'explains the applied %s score cap',
    async (evidenceLevel, rawScore, effectiveScore, expectedMessage) => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({
          ...opportunity,
          opportunity_score: effectiveScore,
          raw_opportunity_score: rawScore,
          electrical_work_brief: {
            evidence_level: evidenceLevel,
            summary: 'Test electrical work brief.',
            signals: [],
          },
        }),
      )
      render(<OpportunityDetailPage opportunityId={20} />)

      expect(await screen.findByText(expectedMessage)).toBeInTheDocument()
    },
  )

  it.each([
    ['direct electrical evidence is uncapped', 'direct', 85, 85],
    ['raw and final scores are equal', 'unavailable', 39, 39],
  ])(
    'does not show a cap explanation when %s',
    async (_description, evidenceLevel, rawScore, effectiveScore) => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({
          ...opportunity,
          opportunity_score: effectiveScore,
          raw_opportunity_score: rawScore,
          electrical_work_brief: {
            evidence_level: evidenceLevel,
            summary: 'Test electrical work brief.',
            signals: [],
          },
        }),
      )
      render(<OpportunityDetailPage opportunityId={20} />)

      await screen.findByRole('heading', { level: 3, name: 'Score breakdown' })
      expect(screen.queryByText(/^Raw score:/)).not.toBeInTheDocument()
    },
  )

  it('does not render a cap explanation for an invalid raw score response value', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...opportunity,
        opportunity_score: 39,
        raw_opportunity_score: '70',
        electrical_work_brief: {
          evidence_level: 'unavailable',
          summary: 'Test electrical work brief.',
          signals: [],
        },
      }),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    await screen.findByRole('heading', { level: 3, name: 'Score breakdown' })
    expect(screen.queryByText(/^Raw score:/)).not.toBeInTheDocument()
  })

  it.each([
    null,
    { evidence_level: 'direct', summary: 'EV charging', signals: null },
    { evidence_level: 'direct', summary: 'EV charging', signals: 'EV charging' },
    { evidence_level: 'direct', summary: 'EV charging', signals: {} },
    { evidence_level: 'unsupported', summary: 'EV charging', signals: [] },
    { evidence_level: 'direct', signals: [] },
    { evidence_level: 'direct', summary: 'EV charging', signals: [null] },
  ])('safely falls back for a malformed electrical work brief: %j', async (brief) => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ...opportunity, electrical_work_brief: brief }),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    expect(
      await screen.findByText('No specific electrical work'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'No specific electrical work identified in the planning description.',
      ),
    ).toBeInTheDocument()
  })

  it('preserves an allowed HTTPS source URL as the unsupported-authority fallback', async () => {
    const sourceApplicationUrl =
      'https://planning.example.test/applications/reference/0012345'
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...opportunity,
        planning_authority: 'Dublin City Council',
        application_url: sourceApplicationUrl,
      }),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    const fallbackLink = await screen.findByRole('link', {
      name: 'View official application (opens in a new tab)',
    })
    expect(fallbackLink).toHaveAttribute('href', sourceApplicationUrl)
    expect(fallbackLink).toHaveAttribute('target', '_blank')
    expect(fallbackLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('preserves an allowed HTTP eplanning.ie source URL', async () => {
    const sourceApplicationUrl =
      'http://www.eplanning.ie/SomeAuthority/AppFileRefDetails/0012345/0'
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...opportunity,
        planning_authority: 'Another Planning Authority',
        application_url: sourceApplicationUrl,
      }),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    expect(
      await screen.findByRole('link', {
        name: 'View official application (opens in a new tab)',
      }),
    ).toHaveAttribute('href', sourceApplicationUrl)
  })

  it.each([
    "javascript:alert('unsafe')",
    'data:text/html,unsafe',
    'not a valid URL',
  ])('does not render an unsafe application URL: %s', async (applicationUrl) => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...opportunity,
        planning_authority: 'Another Planning Authority',
        application_url: applicationUrl,
      }),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    expect(
      await screen.findByText(
        'Official application link is not available for this authority.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('link', {
        name: 'View official application (opens in a new tab)',
      }),
    ).not.toBeInTheDocument()
  })

  it('does not invent an official URL for an unsupported authority', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...opportunity,
        planning_authority: 'Dublin City Council',
        application_url: null,
      }),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    expect(
      await screen.findByText(
        'Official application link is not available for this authority.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('link', {
        name: 'View official application (opens in a new tab)',
      }),
    ).not.toBeInTheDocument()
  })

  it('shows an accessible not-found state for a missing opportunity', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Planning application not found.' }, 404),
    )
    render(<OpportunityDetailPage opportunityId={999} />)

    expect(
      await screen.findByRole('heading', {
        level: 2,
        name: 'Opportunity not found',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'This opportunity may no longer be available',
    )
    expect(screen.getByRole('link', { name: 'Back to opportunities' })).toHaveAttribute(
      'href',
      '/',
    )
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/planning-applications/999')
  })

  it('shows a safe service error without exposing response details', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Internal upstream failure' }, 503),
    )
    render(<OpportunityDetailPage opportunityId={20} />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not load this opportunity',
    )
    expect(screen.queryByText('Internal upstream failure')).not.toBeInTheDocument()
  })

  it('retries a failed detail request', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 503))
    render(<OpportunityDetailPage opportunityId={20} />)

    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('article')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
