import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Opportunity } from '../../api/opportunities'
import OpportunityCard from './OpportunityCard'

const longDescription =
  'Construction of a new industrial manufacturing facility with electrical infrastructure, switchgear rooms, external lighting, and associated site development works.'

const opportunity: Opportunity = {
  id: 20,
  application_number: '0012345',
  planning_authority: 'Kerry County Council',
  description: longDescription,
  address: 'Manor West Business Park, Tralee, Co. Kerry',
  application_type: 'Permission',
  application_status: 'Pending',
  decision: null,
  received_date: '2026-08-18',
  application_url: 'https://example.test/generic-planning-search',
  category: 'industrial',
  distance_km: 18.664272461619998,
  opportunity_score: 96,
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

describe('OpportunityCard', () => {
  it('renders a compact heading, human metadata, and score', async () => {
    const onViewOpportunity = vi.fn()
    render(
      <OpportunityCard
        opportunity={opportunity}
        onViewOpportunity={onViewOpportunity}
      />,
    )
    const user = userEvent.setup()

    const card = screen.getByRole('article')
    expect(card).toHaveClass('opportunity-card--very-high')
    const heading = within(card).getByRole('heading', { level: 3 })
    expect(heading.textContent).toMatch(/…$/)
    expect(heading).not.toHaveTextContent(longDescription)
    expect(within(card).getByText('Very high opportunity')).toBeInTheDocument()
    expect(within(card).getByText('96')).toBeInTheDocument()
    expect(within(card).getByText('Industrial')).toBeInTheDocument()
    expect(within(card).getByText('18.7 km')).toBeInTheDocument()
    expect(within(card).getByText('18 August 2026')).toBeInTheDocument()
    const signalIndicator = within(card).getByRole('img', {
      name: 'Electrical signal: confirmed',
    })
    expect(
      signalIndicator.querySelectorAll(
        '.electrical-signal-indicator__icon--active',
      ),
    ).toHaveLength(3)
    expect(
      signalIndicator.querySelectorAll(
        '.electrical-signal-indicator__icon--inactive',
      ),
    ).toHaveLength(0)
    expect(
      within(card).getByText('Confirmed electrical work'),
    ).toBeInTheDocument()
    expect(
      within(card).getByText(
        'Electrical work evidenced: electrical installation work.',
      ),
    ).toBeInTheDocument()
    expect(within(card).queryByText(/^Evidence:/)).not.toBeInTheDocument()
    expect(within(card).getByLabelText('Likely electrical work')).toHaveClass(
      'electrical-work-brief--direct',
    )
    expect(within(card).queryByText(longDescription)).not.toBeInTheDocument()
    expect(
      within(card).queryByText('Planning description'),
    ).not.toBeInTheDocument()

    expect(within(card).queryByText('Score breakdown')).not.toBeInTheDocument()
    expect(within(card).queryByText('Electrical relevance')).not.toBeInTheDocument()
    const viewOpportunityLink = within(card).getByRole('link', {
      name: 'View opportunity',
    })
    expect(viewOpportunityLink).toHaveAttribute('href', '/opportunities/20')
    expect(viewOpportunityLink).not.toHaveAttribute('target')
    expect(viewOpportunityLink).not.toHaveAttribute('rel')

    await user.click(viewOpportunityLink)
    expect(onViewOpportunity).toHaveBeenCalledOnce()
    expect(onViewOpportunity).toHaveBeenCalledWith(opportunity)
  })

  it('uses the application reference when no description is available', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          planning_authority: 'Dublin City Council',
          description: null,
          application_url: null,
        }}
      />,
    )

    const card = screen.getByRole('article', {
      name: 'Planning application 0012345',
    })
    expect(
      within(card).getByRole('link', { name: 'View opportunity' }),
    ).toHaveAttribute('href', '/opportunities/20')
  })

  it('splits a three-part location across two card lines', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          address: 'Tonbwee, Castleisland, Co. Kerry',
        }}
        onViewOpportunity={vi.fn()}
      />,
    )

    const location = screen.getByText('Tonbwee, Castleisland').parentElement
    expect(location).toHaveClass('opportunity-card__location-value')
    expect(within(location as HTMLElement).getByText('Co. Kerry')).toBeInTheDocument()
  })

  it('keeps remaining location parts together on the second card line', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          address: 'Building A, Unit 2, Tralee, Co. Kerry',
        }}
        onViewOpportunity={vi.fn()}
      />,
    )

    expect(screen.getByText('Building A, Unit 2')).toBeInTheDocument()
    expect(screen.getByText('Tralee, Co. Kerry')).toBeInTheDocument()
  })

  it.each(['Castleisland', 'Castleisland, Co. Kerry']) (
    'keeps a short location on one card line: %s',
    (address) => {
      render(
        <OpportunityCard
          opportunity={{ ...opportunity, address }}
          onViewOpportunity={vi.fn()}
        />,
      )

      const location = screen.getByText(address).parentElement
      expect(location?.querySelectorAll('span')).toHaveLength(1)
    },
  )

  it('shows Not provided when the location is null', () => {
    render(
      <OpportunityCard
        opportunity={{ ...opportunity, address: null }}
        onViewOpportunity={vi.fn()}
      />,
    )

    expect(screen.getByText('Not provided')).toBeInTheDocument()
  })

  it.each([
    ['high', 'High', 'high'],
    ['medium', 'Medium', 'medium'],
  ] as const)(
    'applies the %s priority state class',
    (opportunityLevel, label, className) => {
      render(
        <OpportunityCard
          opportunity={{
            ...opportunity,
            opportunity_level: opportunityLevel,
          }}
          onViewOpportunity={vi.fn()}
        />,
      )

      expect(screen.getByText(`${label} opportunity`)).toBeInTheDocument()
      expect(screen.getByRole('article')).toHaveClass(
        `opportunity-card--${className}`,
      )
    },
  )

  it('summarises multiple direct electrical work types without expanding the card', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          electrical_work_brief: {
            evidence_level: 'direct',
            summary:
              'Electrical work evidenced: EV charging infrastructure, renewable or solar electrical infrastructure, lighting work.',
            signals: [
              { work_type: 'ev_charging', evidence: 'ev charging' },
              { work_type: 'renewable_generation', evidence: 'solar' },
              { work_type: 'lighting', evidence: 'car park lighting' },
            ],
          },
        }}
        onViewOpportunity={vi.fn()}
      />,
    )

    expect(
      screen.getByText(
        'Electrical work evidenced: EV charging infrastructure, renewable or solar electrical infrastructure, lighting work.',
      ),
    ).toBeInTheDocument()
  })

  it('uses a restrained low-evidence state when the API has no electrical evidence', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          electrical_work_brief: {
            evidence_level: 'unavailable',
            summary:
              'Electrical work is not evidenced by the available planning data.',
            signals: [],
          },
        }}
        onViewOpportunity={vi.fn()}
      />,
    )

    const signalIndicator = screen.getByRole('img', {
      name: 'Electrical signal: no specific signal',
    })
    expect(
      signalIndicator.querySelectorAll(
        '.electrical-signal-indicator__icon--active',
      ),
    ).toHaveLength(0)
    expect(
      signalIndicator.querySelectorAll(
        '.electrical-signal-indicator__icon--inactive',
      ),
    ).toHaveLength(3)
    expect(screen.getByText('No specific electrical work')).toBeInTheDocument()
    expect(
      screen.getByText(
        'No specific electrical work identified in the planning description.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Likely electrical work')).toHaveClass(
      'electrical-work-brief--unavailable',
    )
  })

  it('presents inferred work as a likely opportunity without evidence', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          electrical_work_brief: {
            evidence_level: 'inferred',
            summary:
              'Potential electrical package associated with a substantial industrial development -- review plans for confirmation.',
            signals: [],
          },
        }}
        onViewOpportunity={vi.fn()}
      />,
    )

    const signalIndicator = screen.getByRole('img', {
      name: 'Electrical signal: likely',
    })
    expect(
      signalIndicator.querySelectorAll(
        '.electrical-signal-indicator__icon--active',
      ),
    ).toHaveLength(2)
    expect(
      signalIndicator.querySelectorAll(
        '.electrical-signal-indicator__icon--inactive',
      ),
    ).toHaveLength(1)
    expect(screen.getByText('Very likely electrical work')).toBeInTheDocument()
    expect(
      screen.getByText(/review plans for confirmation/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/^Evidence:/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Likely electrical work')).toHaveClass(
      'electrical-work-brief--inferred',
    )
  })

  it('safely falls back for a malformed electrical work brief', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          electrical_work_brief: {
            evidence_level: 'direct',
            summary: 'EV charging',
            signals: null,
          } as never,
        }}
        onViewOpportunity={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('img', {
        name: 'Electrical signal: no specific signal',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'No specific electrical work identified in the planning description.',
      ),
    ).toBeInTheDocument()
  })
})
