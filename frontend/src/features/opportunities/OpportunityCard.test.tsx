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
}

describe('OpportunityCard', () => {
  it('renders a compact heading, human metadata, and accessible disclosures', async () => {
    const onViewOpportunity = vi.fn()
    render(
      <OpportunityCard
        opportunity={opportunity}
        onViewOpportunity={onViewOpportunity}
      />,
    )
    const user = userEvent.setup()

    const card = screen.getByRole('article')
    const heading = within(card).getByRole('heading', { level: 3 })
    expect(heading.textContent).toMatch(/…$/)
    expect(heading).not.toHaveTextContent(longDescription)
    expect(within(card).getByText('Very high opportunity')).toBeInTheDocument()
    expect(within(card).getByText('96')).toBeInTheDocument()
    expect(within(card).getByText('Industrial')).toBeInTheDocument()
    expect(within(card).getByText('18.7 km')).toBeInTheDocument()
    expect(within(card).getByText('18 August 2026')).toBeInTheDocument()
    expect(within(card).getByText(longDescription)).toBeInTheDocument()

    const descriptionSummary = within(card).getByText('Planning description')
    const descriptionDetails = descriptionSummary.closest('details')
    expect(descriptionDetails).not.toHaveAttribute('open')
    await user.click(descriptionSummary)
    expect(descriptionDetails).toHaveAttribute('open')

    const breakdownSummary = within(card).getByText('Score breakdown')
    const breakdownDetails = breakdownSummary.closest('details')
    expect(breakdownDetails).not.toHaveAttribute('open')
    await user.click(breakdownSummary)
    expect(breakdownDetails).toHaveAttribute('open')
    expect(within(card).getByText('Electrical relevance')).toBeInTheDocument()
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
      within(card).queryByText('Planning description'),
    ).not.toBeInTheDocument()
    expect(
      within(card).getByRole('link', { name: 'View opportunity' }),
    ).toHaveAttribute('href', '/opportunities/20')
  })
})
