import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import OpportunitiesPage from './OpportunitiesPage'

describe('OpportunitiesPage', () => {
  it('renders its headings and accessible search form', () => {
    render(<OpportunitiesPage />)

    expect(
      screen.getByRole('heading', { level: 2, name: 'Opportunities near you' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: 'Top opportunities' }),
    ).toBeInTheDocument()

    expect(
      screen.getByText(/ranks recent planning applications/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('form', { name: 'Opportunity filters' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Radius' })).toHaveValue('25')
    expect(screen.getByRole('combobox', { name: 'Recent period' })).toHaveValue(
      '30',
    )
    expect(screen.getByRole('combobox', { name: 'Category' })).toHaveValue('')
    expect(
      screen.getByRole('option', { name: 'All categories' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: 'Mixed use' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Find opportunities' }),
    ).toBeInTheDocument()
  })

  it('renders three representative opportunities as a semantic list', () => {
    render(<OpportunitiesPage />)

    const results = screen.getByRole('list', { name: 'Top opportunities' })
    const articles = within(results).getAllByRole('article')

    expect(articles).toHaveLength(3)

    const commercialOpportunity = screen.getByRole('article', {
      name: /three-storey enterprise centre/i,
    })
    expect(
      within(commercialOpportunity).getByText('88'),
    ).toBeInTheDocument()
    expect(
      within(commercialOpportunity).getByText('Very high'),
    ).toBeInTheDocument()
    expect(
      within(commercialOpportunity).getByText('Commercial'),
    ).toBeInTheDocument()
    expect(
      within(commercialOpportunity).getByText(
        'Manor West Business Park, Tralee, Co. Kerry',
      ),
    ).toBeInTheDocument()
    expect(
      within(commercialOpportunity).getByText('3.4 km'),
    ).toBeInTheDocument()
    expect(
      within(commercialOpportunity).getByText('18 August 2026'),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('heading', { name: /20 MW solar farm/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /36 houses, 24 apartments/i }),
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole('button', { name: 'View opportunity' }),
    ).toHaveLength(3)
  })
})
