import OpportunitiesPage from './features/opportunities/OpportunitiesPage'

function App() {
  return (
    <>
      <header className="site-header">
        <div className="app-container site-header__inner">
          <h1 className="site-brand">GroundSignal</h1>
        </div>
      </header>

      <main className="site-main">
        <div className="app-container">
          <OpportunitiesPage />
        </div>
      </main>

      <footer className="site-footer">
        <div className="app-container site-footer__inner">
          <p>GroundSignal planning intelligence.</p>
        </div>
      </footer>
    </>
  )
}

export default App
