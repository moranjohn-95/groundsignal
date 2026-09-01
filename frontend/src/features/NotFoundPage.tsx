import { useEffect, useRef, type MouseEvent } from 'react'

interface NotFoundPageProps {
  onBackToOpportunities: (event: MouseEvent<HTMLAnchorElement>) => void
}

function NotFoundPage({ onBackToOpportunities }: NotFoundPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <section className="not-found-page" aria-labelledby="not-found-heading">
      <span className="not-found-page__accent" aria-hidden="true" />
      <h2 id="not-found-heading" ref={headingRef} tabIndex={-1}>
        Page not found
      </h2>
      <p>We couldn't find the page you're looking for.</p>
      <p className="not-found-page__hint">
        Check the address or return to the main search.
      </p>
      <a
        className="button button--primary not-found-page__action"
        href="/"
        onClick={onBackToOpportunities}
      >
        Back to opportunities
      </a>
    </section>
  )
}

export default NotFoundPage
