import { useState } from 'react'

const normalizeCategory = (category = '') => category
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase('es')

function CategoryArtwork({ type }) {
  switch (type) {
    case 'pizzas':
      return <><circle cx="50" cy="50" r="35" fill="#d99a43" /><circle cx="50" cy="50" r="29" fill="#f2d27e" /><path d="M50 21v58M21 50h58M29 29l42 42M71 29 29 71" stroke="#d99a43" strokeWidth="2" opacity=".65" />{[[40,39],[59,38],[48,57],[64,58],[35,61]].map(([cx, cy]) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="4.2" fill="#bd4d36" />)}</>
    case 'salchipapas':
      return <><path d="m27 49 46 0-7 31H34z" fill="#bd4d36" /><path d="m31 49 5-27m5 27 1-32m8 32 4-29m5 29 7-25" stroke="#f2c66d" strokeWidth="7" strokeLinecap="round" /><path d="M32 50h39" stroke="#f7f5ec" strokeWidth="3" opacity=".8" /></>
    case 'cocteles':
      return <><path d="M24 24h52L53 54v20" fill="#dbe8d5" stroke="#355e45" strokeWidth="3" strokeLinejoin="round" /><path d="M50 54v20m-13 4h27" stroke="#355e45" strokeWidth="3" strokeLinecap="round" /><path d="M31 31h38L52 49z" fill="#ce2b37" opacity=".8" /><circle cx="67" cy="24" r="5" fill="#009246" /><path d="m64 19 9-7" stroke="#355e45" strokeWidth="2" strokeLinecap="round" /></>
    case 'bebidas':
      return <><path d="M34 20h32l-3 61H37z" fill="#fff" stroke="#355e45" strokeWidth="3" strokeLinejoin="round" /><path d="M37 49h26l-2 27H39z" fill="#82b7a0" /><path d="M48 17 60 8" stroke="#bd4d36" strokeWidth="3" strokeLinecap="round" /><path d="M41 56h18" stroke="#f7f5ec" strokeWidth="3" strokeLinecap="round" /></>
    case 'hamburguesas':
      return <><path d="M24 45c0-17 12-27 26-27s26 10 26 27z" fill="#e8ad55" /><path d="M25 49h50v8H25z" fill="#68a052" /><path d="M23 59c0-3 3-5 6-5h42c4 0 6 2 6 5v8H23z" fill="#704231" /><path d="M24 69h52c0 8-7 12-14 12H38c-8 0-14-4-14-12" fill="#e8ad55" /><path d="M41 29h1m10-4h1m9 7h1" stroke="#fff0c4" strokeWidth="3" strokeLinecap="round" /></>
    case 'sandwiches':
      return <><path d="m25 67 14-43c2-7 8-7 11 0l25 43z" fill="#e8ad55" stroke="#c48436" strokeWidth="2" /><path d="m31 57 38 0-3 7H29z" fill="#68a052" /><path d="m34 48 29 0-3 7H32z" fill="#bd4d36" /><path d="m37 40 22 0-3 6H35z" fill="#f2d27e" /><path d="M25 69h51" stroke="#c48436" strokeWidth="3" strokeLinecap="round" /></>
    case 'broasters':
      return <><path d="M31 31c8-9 20-8 27 0l12 14c5 6 4 15-2 20s-14 5-20-1L33 48c-5-5-6-12-2-17" fill="#d99a43" /><path d="m30 30-8-8m9 14-12-2m48 34 8 8m-14-7 2 12" stroke="#f2d27e" strokeWidth="6" strokeLinecap="round" /><path d="m38 38 20 20m-7-26 15 15" stroke="#f7f5ec" strokeWidth="3" opacity=".8" /></>
    case 'alitas':
      return <><path d="M22 63c10-25 21-39 33-38 9 1 11 11 5 20 14-8 23-2 18 9-4 9-20 18-43 25-10 3-17-6-13-16" fill="#d99a43" /><path d="m47 45 11 6m-20 8 11 5" stroke="#f2d27e" strokeWidth="5" strokeLinecap="round" /><circle cx="71" cy="31" r="5" fill="#ce2b37" /></>
    case 'jugos':
    case 'batidos':
    case 'gaseosas':
      return <><path d="M34 20h32l-3 61H37z" fill="#fff" stroke="#355e45" strokeWidth="3" strokeLinejoin="round" /><path d="M37 47h26l-2 29H39z" fill={type === 'jugos' ? '#e9a644' : type === 'batidos' ? '#d98b9a' : '#82b7a0'} /><path d="M48 17 60 8" stroke="#bd4d36" strokeWidth="3" strokeLinecap="round" /><circle cx="49" cy="58" r="3" fill="#f7f5ec" opacity=".8" /></>
    case 'entradas':
    case 'adicionales':
    default:
      return <><circle cx="50" cy="50" r="34" fill="#fff" stroke="#355e45" strokeWidth="3" /><circle cx="50" cy="50" r="24" fill="#e9eadb" /><path d="M38 43c5-8 19-8 24 0l-3 16H41z" fill="#d99a43" /><path d="M36 63h28" stroke="#bd4d36" strokeWidth="3" strokeLinecap="round" /><path d="M18 35v18m-5-18v9m10-9v9m-5 9v21m54-38v38m-5-38v14c0 5 10 5 10 0V35" fill="none" stroke="#728270" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></>
  }
}

export default function CategoryPlaceholder({ categoria }) {
  const normalized = normalizeCategory(categoria)
  const type = normalized.includes('pizza') ? 'pizzas'
    : normalized.includes('salchipapa') ? 'salchipapas'
      : normalized.includes('coctel') ? 'cocteles'
        : normalized.includes('jugo') ? 'jugos'
          : normalized.includes('batido') ? 'batidos'
            : normalized.includes('gaseosa') ? 'gaseosas'
              : normalized.includes('bebida') ? 'bebidas'
                : normalized.includes('hamburguesa') ? 'hamburguesas'
                  : normalized.includes('sandwich') ? 'sandwiches'
                    : normalized.includes('broaster') ? 'broasters'
                      : normalized.includes('alita') ? 'alitas'
                        : normalized.includes('entrada') ? 'entradas'
                          : normalized.includes('adicional') ? 'adicionales'
                            : 'default'

  return (
    <div className={`menu-product-visual menu-product-placeholder placeholder-${type}`} role="img" aria-label={`Ilustración de ${categoria || 'producto'}`}>
      <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
        <rect x="3" y="3" width="94" height="94" rx="14" fill="currentColor" opacity=".08" />
        <CategoryArtwork type={type} />
      </svg>
    </div>
  )
}

export function ProductVisual({ image, categoria, alt }) {
  const [imageFailed, setImageFailed] = useState(false)
  if (!image || imageFailed) return <CategoryPlaceholder categoria={categoria} />

  return (
    <img
      className="menu-product-visual menu-product-image"
      src={image}
      alt={alt}
      loading="lazy"
      onError={() => setImageFailed(true)}
    />
  )
}
