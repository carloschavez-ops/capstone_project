// ---------------------------------------------------------
// Estado
// ---------------------------------------------------------
let pizzaActualId = PIZZAS.length ? PIZZAS[0].id : null;
let tamanoSeleccionadoId = null;
let quesoSeleccionadoId = null;
let toppingsSeleccionados = new Set();

const filtrosDieta = new Set(); // dietas activas: 'vegano', 'sin_gluten', 'sin_lactosa'
let categoriaActiva = "todas";
let textoBusqueda = "";

// ---------------------------------------------------------
// Utilidades
// ---------------------------------------------------------
function formatoSoles(valor) {
  return "S/ " + valor.toFixed(2);
}

function obtenerPizza(id) {
  return PIZZAS.find((p) => p.id === id) || null;
}

// ---------------------------------------------------------
// Render del panel personalizador
// ---------------------------------------------------------
function cargarPizzaEnPersonalizador(pizzaId) {
  const pizza = obtenerPizza(pizzaId);
  if (!pizza) return;

  pizzaActualId = pizzaId;
  const p = pizza.personalizacion;

  // Preseleccionar: primer tamaño, queso incluido, y toppings marcados por defecto
  tamanoSeleccionadoId = p.tamanos[0].id;
  const quesoIncluido = p.quesos.find((q) => q.incluido);
  quesoSeleccionadoId = quesoIncluido ? quesoIncluido.id : p.quesos[0].id;
  toppingsSeleccionados = new Set(
    p.toppings.filter((t) => t.defecto).map((t) => t.id)
  );

  document.getElementById("pers-etiqueta").textContent = p.etiqueta;
  document.getElementById("pers-nombre").textContent = pizza.nombre;
  document.getElementById("pers-tiempo").textContent = "⏱ " + p.tiempo_horneado + " horneado";
  document.getElementById("pers-kcal").textContent = "● " + p.kcal;

  // Tamaños
  const contTamanos = document.getElementById("pers-tamanos");
  contTamanos.innerHTML = "";
  p.tamanos.forEach((tam) => {
    const div = document.createElement("label");
    div.className = "opcion-tamano";
    div.innerHTML = `
      <input type="radio" name="tamano" value="${tam.id}" ${tam.id === tamanoSeleccionadoId ? "checked" : ""}>
      <div>
        <strong>${tam.nombre}</strong>
        <span class="desc-tamano">${tam.desc}</span>
        <span class="precio-tamano">${tam.extra > 0 ? "+" + formatoSoles(tam.extra) : formatoSoles(tam.precio)}</span>
      </div>
    `;
    div.querySelector("input").addEventListener("change", () => {
      tamanoSeleccionadoId = tam.id;
      actualizarResumen();
    });
    contTamanos.appendChild(div);
  });

  // Insumos base (protegidos, no editables)
  const contInsumos = document.getElementById("pers-insumos");
  contInsumos.innerHTML = "";
  p.insumos_base.forEach((ins) => {
    const div = document.createElement("div");
    div.className = "fila-insumo";
    div.innerHTML = `
      <span>🔒 ${ins.nombre}</span>
      <span class="detalle-insumo">${ins.detalle}</span>
    `;
    contInsumos.appendChild(div);
  });

  // Quesos (radio)
  const contQuesos = document.getElementById("pers-quesos");
  contQuesos.innerHTML = "";
  p.quesos.forEach((q) => {
    const div = document.createElement("label");
    div.className = "fila-opcion-radio";
    div.innerHTML = `
      <span class="radio-texto">
        <input type="radio" name="queso" value="${q.id}" ${q.id === quesoSeleccionadoId ? "checked" : ""}>
        ${q.nombre}
      </span>
      <span class="precio-opcion">${q.incluido ? "Incluido" : "+" + formatoSoles(q.extra)}</span>
    `;
    div.querySelector("input").addEventListener("change", () => {
      quesoSeleccionadoId = q.id;
      actualizarResumen();
    });
    contQuesos.appendChild(div);
  });

  // Toppings (checkbox)
  const contToppings = document.getElementById("pers-toppings");
  contToppings.innerHTML = "";
  p.toppings.forEach((t) => {
    const div = document.createElement("label");
    div.className = "fila-opcion-check";
    div.innerHTML = `
      <span class="check-texto">
        <input type="checkbox" value="${t.id}" ${toppingsSeleccionados.has(t.id) ? "checked" : ""}>
        ${t.nombre}
      </span>
      <span class="precio-opcion">+${formatoSoles(t.extra)}</span>
    `;
    div.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) {
        toppingsSeleccionados.add(t.id);
      } else {
        toppingsSeleccionados.delete(t.id);
      }
      actualizarResumen();
    });
    contToppings.appendChild(div);
  });

  actualizarResumen();
  marcarTarjetaActiva(pizzaId);
}

// ---------------------------------------------------------
// Cálculo y render del total
// ---------------------------------------------------------
function actualizarResumen() {
  const pizza = obtenerPizza(pizzaActualId);
  if (!pizza) return;
  const p = pizza.personalizacion;

  const tamano = p.tamanos.find((t) => t.id === tamanoSeleccionadoId) || p.tamanos[0];
  const queso = p.quesos.find((q) => q.id === quesoSeleccionadoId) || p.quesos[0];
  const toppingsElegidos = p.toppings.filter((t) => toppingsSeleccionados.has(t.id));

  let total = tamano.precio;
  const filas = [];
  filas.push({ etiqueta: `Base ${pizza.nombre.split(" ")[0]} ${tamano.nombre.split(" ")[1] || ""}:`, valor: tamano.precio });

  if (!queso.incluido) {
    total += queso.extra;
    filas.push({ etiqueta: `Extra ${queso.nombre}:`, valor: queso.extra, extra: true });
  }

  toppingsElegidos.forEach((t) => {
    total += t.extra;
    filas.push({ etiqueta: `Extra ${t.nombre}:`, valor: t.extra, extra: true });
  });

  const contDesglose = document.getElementById("pers-desglose");
  contDesglose.innerHTML = filas
    .map(
      (f) => `
      <div class="fila-desglose">
        <span>${f.etiqueta}</span>
        <span>${f.extra ? "+" : ""}${formatoSoles(f.valor)}</span>
      </div>`
    )
    .join("");

  document.getElementById("pers-total").innerHTML = formatoSoles(total);
  document.getElementById("pers-total-boton").textContent = formatoSoles(total);
}

// ---------------------------------------------------------
// Marcar visualmente la tarjeta que se está editando
// ---------------------------------------------------------
function marcarTarjetaActiva(pizzaId) {
  document.querySelectorAll(".tarjeta-pizza").forEach((tarjeta) => {
    const metaSpan = tarjeta.querySelector(".meta-pizza");
    if (tarjeta.dataset.id === pizzaId) {
      tarjeta.classList.add("tarjeta-activa");
      metaSpan.textContent = "🔴 Editando en panel interactivo";
    } else {
      tarjeta.classList.remove("tarjeta-activa");
      metaSpan.textContent = metaSpan.dataset.metaDefault;
    }
  });
}

// ---------------------------------------------------------
// Agregar al carrito (llama al backend Flask)
// ---------------------------------------------------------
function agregarAlCarrito() {
  const pizza = obtenerPizza(pizzaActualId);
  if (!pizza) return;

  const totalTexto = document.getElementById("pers-total-boton").textContent.replace("S/", "").trim();
  const total = parseFloat(totalTexto);

  const payload = {
    pizza_id: pizzaActualId,
    tamano_id: tamanoSeleccionadoId,
    queso_id: quesoSeleccionadoId,
    toppings: Array.from(toppingsSeleccionados),
    total: total,
  };

  const boton = document.getElementById("btn-agregar-carrito");
  const textoOriginal = boton.innerHTML;
  boton.disabled = true;
  boton.innerHTML = "Agregando...";

  fetch("/carrito/agregar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.cantidad !== undefined) {
        document.getElementById("contador-carrito").textContent = data.cantidad;
      }
      boton.innerHTML = "✅ Añadida al carrito";
      setTimeout(() => {
        boton.innerHTML = textoOriginal;
        boton.disabled = false;
      }, 1400);
    })
    .catch(() => {
      boton.innerHTML = "Error, intenta de nuevo";
      setTimeout(() => {
        boton.innerHTML = textoOriginal;
        boton.disabled = false;
      }, 1400);
    });
}

// ---------------------------------------------------------
// Filtros: categoría, búsqueda y dieta
// ---------------------------------------------------------
function aplicarFiltros() {
  let visibles = 0;
  document.querySelectorAll(".tarjeta-pizza").forEach((tarjeta) => {
    const coincideCategoria = categoriaActiva === "todas" || tarjeta.dataset.categoria === categoriaActiva;
    const coincideTexto =
      textoBusqueda === "" ||
      tarjeta.dataset.nombre.includes(textoBusqueda) ||
      tarjeta.dataset.descripcion.includes(textoBusqueda);

    let coincideDieta = true;
    filtrosDieta.forEach((d) => {
      if (tarjeta.dataset[toCamel(d)] !== "si") {
        coincideDieta = false;
      }
    });

    const visible = coincideCategoria && coincideTexto && coincideDieta;
    tarjeta.style.display = visible ? "" : "none";
    if (visible) visibles++;
  });

  document.getElementById("sin-resultados").style.display = visibles === 0 ? "block" : "none";
}

function toCamel(str) {
  return str.replace(/_([a-z])/g, (m, c) => c.toUpperCase());
}

// ---------------------------------------------------------
// Listeners generales
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  // Botones "Personalizar Receta"
  document.querySelectorAll(".btn-personalizar").forEach((btn) => {
    btn.addEventListener("click", () => cargarPizzaEnPersonalizador(btn.dataset.id));
  });

  // Cargar la primera pizza al abrir la página
  if (pizzaActualId) {
    cargarPizzaEnPersonalizador(pizzaActualId);
  }

  // Botón agregar al carrito
  document.getElementById("btn-agregar-carrito").addEventListener("click", agregarAlCarrito);

  // Tabs de categoría
  document.querySelectorAll(".tab-categoria").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab-categoria").forEach((t) => t.classList.remove("activo"));
      tab.classList.add("activo");
      categoriaActiva = tab.dataset.categoria;
      aplicarFiltros();
    });
  });

  // Buscador
  document.getElementById("buscador-input").addEventListener("input", (e) => {
    textoBusqueda = e.target.value.trim().toLowerCase();
    aplicarFiltros();
  });

  // Chips de dieta
  document.querySelectorAll(".chip-dieta").forEach((chip) => {
    chip.addEventListener("click", () => {
      const dieta = chip.dataset.dieta;
      if (filtrosDieta.has(dieta)) {
        filtrosDieta.delete(dieta);
        chip.classList.remove("activo");
      } else {
        filtrosDieta.add(dieta);
        chip.classList.add("activo");
      }
      aplicarFiltros();
    });
  });
});