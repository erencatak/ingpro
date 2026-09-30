import { useMemo, useState } from 'react'
import { DemoBadge } from '../components/DemoBadge'
import { Icon } from '../components/Icon'
import { CATEGORY_LABEL, KIND_LABEL, STAGE_LABEL, useWordNetwork, type WordNetwork, type WordNeuron } from './data'
import { demoNetwork } from './demo'
import { NeuralCanvas, type ColorMode } from './NeuralCanvas'
import './wordbrain.css'

function Meter({ label, low, high, value }: { label: string; low: string; high: string; value: number | null }) {
  const pct = value == null ? 0 : ((value - 1) / 8) * 100
  return (
    <div className="wb-meter">
      <div className="wb-meter-head"><span>{label}</span><b className="num">{value == null ? '—' : value.toFixed(1)}</b></div>
      <div className="wb-meter-bar"><i style={{ left: `${pct}%`, opacity: value == null ? 0 : 1 }} /></div>
      <div className="wb-meter-ends"><span>{low}</span><span>{high}</span></div>
    </div>
  )
}

function NeuronPanel({ n, net, onSelect }: { n: WordNeuron; net: WordNetwork; onSelect: (id: string) => void }) {
  const links = net.edges
    .filter((e) => e.a === n.id || e.b === n.id)
    .map((e) => ({ other: e.a === n.id ? e.b : e.a, kind: e.kind, weight: e.weight }))
    .sort((x, y) => y.weight - x.weight)
  return (
    <div className="wb-panel-body">
      <div className="wb-word">
        <h2 className="en">{n.id}</h2>
        <span className={`pill ${n.stage === 'entegre' ? 'pill-good' : 'pill-warn'}`}>{STAGE_LABEL[n.stage]}</span>
      </div>
      <p className="muted wb-sub">
        {n.cefr ?? '—'} · {n.category ? CATEGORY_LABEL[n.category] ?? n.category : 'Anlam grubu yok'}
      </p>
      <div className="wb-facts">
        <div><span className="num">{n.successes}</span><small>doğru kullanım</small></div>
        <div><span className="num">{n.stability.toFixed(1)}</span><small>gün kararlılık</small></div>
        <div><span className="num">{links.length}</span><small>sinaps</small></div>
      </div>
      <h3 className="wb-h3">Duygusal iz</h3>
      <Meter label="Hoşluk (valence)" low="nahoş" high="hoş" value={n.valence} />
      <Meter label="Yoğunluk (arousal)" low="sakin" high="heyecanlı" value={n.arousal} />
      <Meter label="Kontrol (dominance)" low="çaresiz" high="güçlü" value={n.dominance} />
      <p className="wb-note">
        {n.vad_source === 'dataset' ? 'Kaynak: insan puanlaması (duygu normları veri seti).' : n.vad_source === 'llm' ? 'Kaynak: model tahmini (veri setinde yok).' : 'Duygu skoru henüz hesaplanmadı.'}
      </p>
      <h3 className="wb-h3">Bağlantılar</h3>
      {links.length ? (
        <ul className="wb-links">
          {links.slice(0, 10).map((l) => (
            <li key={l.other + l.kind}>
              <button onClick={() => onSelect(l.other)}>
                <span className={`wb-dot wb-dot-${l.kind}`} />
                <span className="en">{l.other}</span>
                <small>{KIND_LABEL[l.kind]}</small>
                <span className="wb-w"><i style={{ width: `${Math.round(l.weight * 100)}%` }} /></span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted wb-note">Henüz bağı yok. Aynı cümlede başka kelimelerle birlikte kullandıkça bağlar oluşur.</p>
      )}
    </div>
  )
}

function Legend({ mode }: { mode: ColorMode }) {
  return (
    <div className="wb-panel-body">
      <h2 className="wb-h2">Nasıl okunur?</h2>
      <p className="muted wb-note">
        Her nokta bir <b>nöron</b>: konuşmada 3 kez doğru kullandığın bir kelime. Bir nörona dokun: ateşlenir ve sinyal
        bağlı olduğu kelimelere yayılır — beynin kelime hatırlarken yaptığı <b>yayılan aktivasyon</b>.
      </p>
      <div className="wb-legend">
        <div><span className="wb-ring wb-ring-fast" />Yeni kelime — Hipokampüsten henüz kalıcı belleğe geçmedi</div>
        <div><span className="wb-ring wb-ring-int" />Entegre — uykudan sonra kalıcı ağa katıldı</div>
        <div><span className="wb-line wb-line-co" />Birlikte kullanım — aynı cümlede doğru kullandıkça kalınlaşır</div>
        <div><span className="wb-line wb-line-sem" />Anlam ortaklığı — aynı anlam grubundaki kelimeler</div>
        <div><span className="wb-glow" />Parıltı hızı = kelimenin duygusal yoğunluğu</div>
      </div>
      {mode === 'emotion' ? (
        <div className="wb-scale">
          <span className="wb-scale-bar" />
          <div className="wb-meter-ends"><span>nahoş</span><span>nötr</span><span>hoş</span></div>
        </div>
      ) : (
        <div className="wb-cats">
          {Object.entries(CATEGORY_LABEL).map(([k, v]) => <span key={k} className={`wb-cat wb-cat-${k}`}>{v}</span>)}
        </div>
      )}
    </div>
  )
}

export function WordBrain() {
  const { net: real, error } = useWordNetwork()
  const [mode, setMode] = useState<ColorMode>('emotion')
  const [selected, setSelected] = useState<string | null>(null)
  const demo = useMemo(() => demoNetwork(), [])
  const isDemo = real !== null && real.nodes.length === 0
  const net = real && !isDemo ? real : isDemo ? demo : null
  const node = net && selected ? net.nodes.find((n) => n.id === selected) : undefined

  return (
    <section className="view wb" aria-labelledby="h-wb">
      <div className="hello">
        <div>
          <p className="eyebrow">Kelime beyni</p>
          <h1 id="h-wb">Kelimelerin sinir ağı</h1>
          <p>Kullandığın kelimeler anlam gruplarında kümelenir, birlikte kullandıkların arasında sinapslar güçlenir.</p>
        </div>
        <div className="stat-pills">
          {error && <span className="pill pill-bad">Sunucuya ulaşılamadı</span>}
          {isDemo && <DemoBadge />}
          {net && (
            <>
              <span className="stat-pill"><Icon name="sparkle" size="sm" />{net.stats.neurons} <small>nöron</small></span>
              <span className="stat-pill">{net.stats.synapses} <small>sinaps</small></span>
              <span className="stat-pill">{net.stats.integrated} <small>entegre</small></span>
            </>
          )}
        </div>
      </div>

      {isDemo && (
        <p className="wb-banner">
          <Icon name="bulb" size="sm" />
          Henüz kelime nöronun yok — bu bir örnek ağ. Bir ünitede Alex'le konuşurken bir kelimeyi 3 kez doğru kullandığında,
          o kelime burada kendi nöronu olarak doğar.
        </p>
      )}

      <div className="wb-grid">
        <div className="card wb-stage">
          <div className="wb-toolbar">
            <div className="seg" role="group" aria-label="Renk">
              <button aria-pressed={mode === 'emotion'} onClick={() => setMode('emotion')}>Duygu</button>
              <button aria-pressed={mode === 'category'} onClick={() => setMode('category')}>Anlam grubu</button>
            </div>
            <span className="muted wb-hint">Sürükle · tıkla ve ateşle</span>
          </div>
          {net ? (
            net.nodes.length ? <NeuralCanvas net={net} mode={mode} selected={selected} onSelect={setSelected} /> : null
          ) : (
            <div className="wb-canvas wb-loading">{error ? 'Beyin yüklenemedi.' : 'Beyin yükleniyor…'}</div>
          )}
          <span className="wb-credit">Duygu verileri: Warriner, Kuperman &amp; Brysbaert (2013), CC BY-NC-ND</span>
        </div>
        <aside className="card wb-panel" aria-live="polite">
          {node && net ? <NeuronPanel n={node} net={net} onSelect={setSelected} /> : <Legend mode={mode} />}
        </aside>
      </div>
    </section>
  )
}
