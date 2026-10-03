const localImageModules = import.meta.glob(
  './assets/assets-categorias/**/*.{jpg,jpeg,png,webp}',
  { eager: true, import: 'default', query: '?url' },
)

const IGNORED_WORDS = new Set(['de', 'del', 'la', 'las', 'el', 'los', 'y', 'con', 'pizza'])

// Alias explícitos para nombres comerciales que no coinciden literalmente con el archivo.
const PRODUCT_IMAGE_ALIASES = {
  entradas: {
    [normalizeProductText('Bruschettas Italianas (3 unid.)')]: normalizeProductText('bruschetta italiana'),
    [normalizeProductText('Bruschettas Italianas con Queso Mozzarella (3 unid.)')]: normalizeProductText('bruschetta queso'),
    [normalizeProductText('Ensalada Clásica')]: normalizeProductText('ensalada de tomate zanahoria lechuga'),
    [normalizeProductText('Ensalada Especial')]: normalizeProductText('ensalada con atun'),
    [normalizeProductText('Pan al Ajo (5 unid.)')]: normalizeProductText('pan al ajo'),
    [normalizeProductText('Pan al Ajo Especial (Queso Mozzarella, 5 unid.)')]: normalizeProductText('pan al ajo especial'),
    [normalizeProductText('Pan de Yuca (6 unid.)')]: normalizeProductText('pan yuca'),
    [normalizeProductText('Tequeños Rellenos de Queso Mozzarella (10 unid.)')]: normalizeProductText('tequenos de queso 2'),
  },
  pizzas: {
    [normalizeProductText('Nutella')]: normalizeProductText('pizza nutela'),
    [normalizeProductText('Cuatro Estaciones')]: normalizeProductText('pizza cuatro estaciones'),
    [normalizeProductText('Paparella Napolitana')]: normalizeProductText('pizza paparella napolitana'),
    [normalizeProductText('Vegetariana')]: normalizeProductText('pizza vegetariana'),
    [normalizeProductText('Anchoas')]: normalizeProductText('pizza de atun y anchoas con aceitunas'),
    [normalizeProductText('Cuatro Quesos')]: normalizeProductText('pizza cuatro quesos'),
    [normalizeProductText('Espinaca')]: normalizeProductText('pizza espinaca'),
    [normalizeProductText('Hawaiana')]: normalizeProductText('hawaiana'),
    [normalizeProductText('Margarita')]: normalizeProductText('pizza margarita'),
    [normalizeProductText('Jamón')]: normalizeProductText('pizza jamon'),
    [normalizeProductText('Pepperoni')]: normalizeProductText('pizza peperoni'),
    [normalizeProductText('Cabanossi')]: normalizeProductText('pizza cabanossi'),
    [normalizeProductText('Tropical')]: normalizeProductText('tropical cheese 1000x1000'),
    [normalizeProductText('Salami')]: normalizeProductText('salami pizza 4'),
  },
  broaster: {
    [normalizeProductText('Pierna Deshuesada en Salsa BBQ')]: normalizeProductText('pierna deshuesada'),
    [normalizeProductText('Pollo Broaster')]: normalizeProductText('pollo broaster'),
  },
  adicionales: {
    [normalizeProductText('Carne de hamburguesa (80 g)')]: normalizeProductText('carne'),
    [normalizeProductText('Hot Dog (3 unid.)')]: normalizeProductText('hot dog'),
    [normalizeProductText('Huevo Frito')]: normalizeProductText('huevo frito'),
    [normalizeProductText('Queso Cheddar')]: normalizeProductText('queso cheddar'),
    [normalizeProductText('Presa de Pollo')]: normalizeProductText('presa de pollo'),
    [normalizeProductText('Papas Fritas')]: normalizeProductText('papas fritas'),
    [normalizeProductText('Porción de Arroz')]: normalizeProductText('porcion de arroz'),
    [normalizeProductText('Ingrediente adicional para pizza')]: normalizeProductText('ingredientes adicionales'),
    [normalizeProductText('Adicional de Anchoas para pizza')]: normalizeProductText('adicional anchoa'),
    [normalizeProductText('Borde de queso')]: normalizeProductText('borde de queso'),
    [normalizeProductText('Fruto adicional para batido')]: {
      category: 'jugosbatidoscafe',
      name: normalizeProductText('mmm'),
    },
  },
  sandwiches: {
    [normalizeProductText('Sándwich de Queso')]: normalizeProductText('Sandwich queso'),
    [normalizeProductText('Sándwich de Huevo')]: normalizeProductText('Sandwich huevo'),
    [normalizeProductText('Sándwich de Hot Dog con Huevo')]: normalizeProductText('Sandwich hotdog y huevo'),
    [normalizeProductText('Sándwich de Pollo Deshilachado')]: normalizeProductText('Sandwich pollo deshilachado'),
    [normalizeProductText('Sándwich de Jamón con Queso')]: normalizeProductText('Sandwich jamon y queso'),
    [normalizeProductText('Sándwich de Huevo Revuelto con Tocino')]: normalizeProductText('Sándwich de Huevo Revuelto con Tocino'),
  },
  jugosbatidoscafe: {
    [normalizeProductText('Fruto adicional para batido')]: normalizeProductText('mmm'),
    [normalizeProductText('Jugo de Papaya')]: normalizeProductText('jugo papaya'),
    [normalizeProductText('Jugo de Piña')]: normalizeProductText('jugo pina'),
    [normalizeProductText('Jugo de Fresa')]: normalizeProductText('jugo fresa'),
    [normalizeProductText('Jugo de Mango')]: normalizeProductText('jugo mango'),
    [normalizeProductText('Jugo de Lúcuma')]: normalizeProductText('jugo lucuma'),
    [normalizeProductText('Jugo de Maracumango')]: normalizeProductText('jugo maracumango'),
    [normalizeProductText('Jugo Combinado')]: normalizeProductText('jugo combinado'),
    [normalizeProductText('Litro de Piña')]: normalizeProductText('jarra pina'),
    [normalizeProductText('Litro de Limonada')]: normalizeProductText('jarra limonada'),
    [normalizeProductText('Litro de Limonada con Menta')]: normalizeProductText('jarra limonada menta'),
    [normalizeProductText('Litro de Maracuyá')]: normalizeProductText('jarra maracuya'),
    [normalizeProductText('Litro de Maracumango')]: normalizeProductText('jarra maracumango'),
    [normalizeProductText('Batido de Papaya')]: normalizeProductText('batido papaya'),
    [normalizeProductText('Batido de Fresa')]: normalizeProductText('batido fresa'),
    [normalizeProductText('Batido de Plátano')]: normalizeProductText('batido platano'),
    [normalizeProductText('Batido de Mango')]: normalizeProductText('batido mango'),
    [normalizeProductText('Batido de Durazno')]: normalizeProductText('batido durazno'),
    [normalizeProductText('Batido de Arándano')]: normalizeProductText('batido arandano'),
    [normalizeProductText('Batido de Maracumango')]: normalizeProductText('batido maracumango'),
    [normalizeProductText('Batido de Lúcuma')]: normalizeProductText('batido lucuma'),
    [normalizeProductText('Batido de Fresa con Mango')]: normalizeProductText('batido fresa mango'),
    [normalizeProductText('Café Instantáneo')]: normalizeProductText('cafe instantaneo'),
    [normalizeProductText('Café de Máquina')]: normalizeProductText('cafe maquina'),
    [normalizeProductText('Café con Leche')]: normalizeProductText('cafe con leche'),
    [normalizeProductText('Café Exprés')]: normalizeProductText('cafe expres'),
    [normalizeProductText('Café Cappuccino')]: normalizeProductText('cafe cappuchino'),
    [normalizeProductText('Chocolate Puro')]: normalizeProductText('chocolate puro'),
    [normalizeProductText('Chocolate con Leche')]: normalizeProductText('chocolate con leche'),
    [normalizeProductText('Taza de Leche')]: normalizeProductText('taza leche'),
    [normalizeProductText('Infusión de Anís')]: normalizeProductText('infusion anis'),
    [normalizeProductText('Infusión de Manzanilla')]: normalizeProductText('infusion manzanilla'),
    [normalizeProductText('Infusión de Hierba Luisa')]: normalizeProductText('infusion hierba luiza'),
    [normalizeProductText('Té Puro')]: normalizeProductText('te puro'),
    [normalizeProductText('Té con Canela y Clavo')]: normalizeProductText('te canela clavo'),
  },
}

// Las gaseosas se resuelven estrictamente por nombre y presentación para evitar cruces.
const GASEOSA_IMAGE_MAP = {
  [normalizeProductText('Coca Cola')]: {
    [normalizeProductText('300 ML')]: normalizeProductText('coca-300ml'),
    [normalizeProductText('MEDIO LITRO')]: normalizeProductText('coca-500ml'),
    [normalizeProductText('1 LITRO')]: normalizeProductText('coca-1L'),
    [normalizeProductText('1.5 LITROS')]: normalizeProductText('coca-15L'),
  },
  [normalizeProductText('Inca Kola')]: {
    [normalizeProductText('300 ML')]: normalizeProductText('inca-kola-300ml'),
    [normalizeProductText('MEDIO LITRO')]: normalizeProductText('inca-500ml'),
    [normalizeProductText('1 LITRO')]: normalizeProductText('inca-1L'),
    [normalizeProductText('1.5 LITROS')]: normalizeProductText('inca-15L'),
  },
  [normalizeProductText('Inca Kola Gordita')]: {
    [normalizeProductText('625 ML')]: normalizeProductText('inca-gordita'),
  },
  [normalizeProductText('Fanta')]: {
    [normalizeProductText('300 ML')]: normalizeProductText('fanta-300ml'),
    [normalizeProductText('MEDIO LITRO')]: normalizeProductText('fanta-500ml'),
    [normalizeProductText('1 LITRO')]: normalizeProductText('fanta-1L'),
  },
  [normalizeProductText('Sprite')]: {
    [normalizeProductText('300 ML')]: normalizeProductText('sprite-300ml'),
  },
  [normalizeProductText('Agua Natural San Luis')]: {
    [normalizeProductText('750 ML')]: normalizeProductText('san-luis'),
  },
  [normalizeProductText('Agua con Gas San Luis')]: {
    [normalizeProductText('625 ML')]: normalizeProductText('san-luis-congas'),
  },
}

function normalizeCategoryText(value = '') {
  const category = normalizeProductText(value)
  return {
    broasters: 'broaster',
    jugosbatidosycafe: 'jugosbatidoscafe',
  }[category] || category
}

export function normalizeProductText(value = '') {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('es')
    .replace(/[^a-z0-9]+/g, '')
}

function significantTokens(value = '') {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('es')
    .split(/[^a-z0-9]+/)
    .filter((token) => token
      && !IGNORED_WORDS.has(token)
      && !/^\d+$/.test(token)
      && !/^\d+x\d+$/.test(token))
}

function getCandidateParts(filePath) {
  const segments = filePath.split('/')
  const rootIndex = segments.indexOf('assets-categorias')
  if (rootIndex < 0 || !segments[rootIndex + 1]) return null

  const filename = segments.at(-1).replace(/\.[^.]+$/, '')
  return {
    category: normalizeCategoryText(segments[rootIndex + 1]),
    name: normalizeProductText(filename),
    tokens: new Set(significantTokens(filename)),
  }
}

const localImageCandidates = Object.entries(localImageModules)
  .map(([filePath, src]) => ({ ...getCandidateParts(filePath), src }))
  .filter((candidate) => candidate.category && candidate.name && candidate.src)

function similarityScore(productName, candidate) {
  const productTokens = new Set(significantTokens(productName))
  const productKey = [...productTokens].sort().join('')
  const candidateKey = [...candidate.tokens].sort().join('')

  if (!productKey || !candidateKey) return 0
  if (productKey === candidateKey) return 1
  if (candidateKey.includes(productKey) || productKey.includes(candidateKey)) {
    return 0.85 + (Math.min(productKey.length, candidateKey.length) / Math.max(productKey.length, candidateKey.length)) * 0.14
  }

  const commonTokens = [...productTokens].filter((token) => candidate.tokens.has(token)).length
  if (commonTokens === 0) return 0
  return (2 * commonTokens) / (productTokens.size + candidate.tokens.size)
}

export function findProductImage(productName, category, presentation = '') {
  const categoryKey = normalizeCategoryText(category)
  if (!productName || !categoryKey) return null

  const productKey = normalizeProductText(productName)
  if (categoryKey === 'gaseosas') {
    const imageName = GASEOSA_IMAGE_MAP[productKey]?.[normalizeProductText(presentation)]
    if (!imageName) return null
    return localImageCandidates.find(
      (candidate) => candidate.category === categoryKey && candidate.name === imageName,
    )?.src || null
  }

  const alias = PRODUCT_IMAGE_ALIASES[categoryKey]?.[productKey]
  if (alias) {
    const aliasCategory = typeof alias === 'string' ? categoryKey : alias.category
    const aliasedName = typeof alias === 'string' ? alias : alias.name
    const exactAlias = localImageCandidates.find(
      (candidate) => candidate.category === aliasCategory && candidate.name === aliasedName,
    )
    if (exactAlias) return exactAlias.src
  }

  let bestCandidate = null
  let bestScore = 0
  for (const candidate of localImageCandidates) {
    if (candidate.category !== categoryKey) continue
    const score = similarityScore(productName, candidate)
    if (score > bestScore) {
      bestCandidate = candidate
      bestScore = score
    }
  }

  return bestScore >= 0.58 ? bestCandidate.src : null
}
