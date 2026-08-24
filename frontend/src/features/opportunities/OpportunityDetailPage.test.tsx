import { render, screen, within } from '@testing-library/react'
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
  opportunity_score: 82,
  opportunity_level: 'high',
  opportunity_breakdown: {
    project_scope: 25,
    electrical_relevance: 27,
    project_scale: 15,
    lead_timing: 8,
    category_fit: 7,
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

    const detail = await screen.findByRole('article', {
      name: 'Opportunity 0012345',
    })
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/planning-applications/20')
    expect(
      within(detail).getByRole('heading', {
        level: 2,
        name: 'Opportunity 0012345',
      }),
    ).toBeInTheDocument()
    expect(within(detail).getByText('High opportunity')).toBeInTheDocument()
    expect(within(detail).getByText('82')).toBeInTheDocument()
    expect(within(detail).getByText(fullDescription)).toBeInTheDocument()
    expect(within(detail).getByText('Industrial')).toBeInTheDocument()
    expect(within(detail).getByText('18.7 km')).toBeInTheDocument()
    expect(within(detail).getByText('18 August 2026')).toBeInTheDocument()
    expect(
      within(detail).getByText('Manor West Business Park, Tralee, Co. Kerry'),
    ).toBeInTheDocument()
    expect(within(detail).getByText('Kerry County Council')).toBeInTheDocument()
    expect(within(detail).getByText('0012345')).toBeInTheDocument()

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
  })

  it('constructs the verified Kerry link and preserves an opaque reference', async () => {
    render(<OpportunityDetailPage opportunityId={20} />)

    const officialApplicationLink = await screen.findByRole('link', {
      name: 'View official application',
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

  it('preserves a source URL as the unsupported-authority fallback', async () => {
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
      name: 'View official application',
    })
    expect(fallbackLink).toHaveAttribute('href', sourceApplicationUrl)
    expect(fallbackLink).toHaveAttribute('target', '_blank')
    expect(fallbackLink).toHaveAttribute('rel', 'noopener noreferrer')
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
      screen.queryByRole('link', { name: 'View official application' }),
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
      'This opportunity could not be found',
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
})
