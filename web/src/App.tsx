import { Icon, Sprite } from './components/Icon'
import { useRoute, VIEWS, type ViewId } from './components/useRoute'
import { useTheme } from './components/useTheme'
import { Chat } from './views/Chat'
import { Errors } from './views/Errors'
import { Grammar } from './views/Grammar'
import { Home } from './views/Home'
import { Practice } from './views/Practice'
import { Progress } from './views/Progress'
import { Vocab } from './views/Vocab'
import { WordBrain } from './wordbrain/WordBrain'

function ThemeButton({ onClick }: { onClick: () => void }) {
  return (
    <button className="icon-btn theme-btn" type="button" aria-label="Temayı değiştir" onClick={onClick}>
      <Icon name="sun" className="i-sun" />
      <Icon name="moon" className="i-moon" />
    </button>
  )
}

export default function App() {
  const { view, go } = useRoute()
  const { toggle } = useTheme()
  const nav = (id: ViewId) => go(id)

  return (
    <>
      <Sprite />
      <div className="app">
        <aside className="sidebar" aria-label="Ana gezinme">
          <a className="logo" href="#bugun" onClick={(e) => { e.preventDefault(); nav('home') }} aria-label="ingpro ana sayfa">
            <span className="logo-mark" aria-hidden="true" />
            <span>ing<b>pro</b></span>
          </a>
          <nav className="nav">
            {VIEWS.map((v) => (
              <button key={v.id} className="nav-btn" aria-current={view === v.id ? 'page' : undefined} onClick={() => nav(v.id)}>
                <Icon name={v.icon} />
                {v.label}
              </button>
            ))}
          </nav>
          <div className="sidebar-foot">
            <div className="theme-row">
              <span>Tema</span>
              <ThemeButton onClick={toggle} />
            </div>
          </div>
        </aside>

        <header className="topbar">
          <a className="logo" href="#bugun" onClick={(e) => { e.preventDefault(); nav('home') }}>
            <span className="logo-mark" aria-hidden="true" />
            <span>ing<b>pro</b></span>
          </a>
          <div className="right">
            <ThemeButton onClick={toggle} />
          </div>
        </header>

        <main id="main">
          {view === 'home' && <Home go={nav} />}
          {view === 'chat' && <Chat />}
          {view === 'practice' && <Practice go={nav} />}
          {view === 'grammar' && <Grammar />}
          {view === 'vocab' && <Vocab />}
          {view === 'wordbrain' && <WordBrain />}
          {view === 'errors' && <Errors go={nav} />}
          {view === 'progress' && <Progress />}
        </main>

        <nav className="tabbar" aria-label="Sekmeler">
          {VIEWS.map((v) => (
            <button key={v.id} className="tab" aria-current={view === v.id ? 'page' : undefined} onClick={() => nav(v.id)}>
              <Icon name={v.icon} />
              <span>{v.label}</span>
            </button>
          ))}
        </nav>
      </div>
    </>
  )
}
