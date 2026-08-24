import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Opportunity } from '../../api/opportunities'
import OpportunityCard from './OpportunityCard'

const longDescription =
  'Construction of a new industrial manufacturing facility with electrical infrastructure, switchgear rooms, external lighting, and associated site development works.'

const opportunity: Opportunity = {
  id: 20,
  application_number: '26/1042',
  planning_authority: 'Kerry County Council',
  description: longDescription,
  address: 'Manor West Business Park, Tralee, Co. Kerry',
  application_type: 'Permission',
  application_status: 'Pending',
  decision: null,
  received_date: '2026-08-18',
  application_url: 'https://example.test/planning/26-1042',
  category: 'industrial',
  distance_km: 18.664272461619998,
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

describe('OpportunityCard', () => {
  it('renders a compact heading, human metadata, and accessible disclosures', async () => {
    render(<OpportunityCard opportunity={opportunity} />)
    const user = userEvent.setup()

    const card = screen.getByRole('article')
    const heading = within(card).getByRole('heading', { level: 3 })
    expect(heading.textContent).toMatch(/…$/)
    expect(heading).not.toHaveTextContent(longDescription)
    expect(within(card).getByText('High opportunity')).toBeInTheDocument()
    expect(within(card).getByText('82')).toBeInTheDocument()
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
    expect(
      within(card).getByRole('link', { name: 'View opportunity' }),
    ).toHaveAttribute('href', opportunity.application_url)
  })

  it('uses the application reference when no description is available', () => {
    render(
      <OpportunityCard
        opportunity={{
          ...opportunity,
          description: null,
          application_url: null,
        }}
      />,
    )

    const card = screen.getByRole('article', {
      name: 'Planning application 26/1042',
    })
    expect(
      within(card).queryByText('Planning description'),
    ).not.toBeInTheDocument()
    expect(
      within(card).queryByRole('link', { name: 'View opportunity' }),
    ).not.toBeInTheDocument()
  })
})
