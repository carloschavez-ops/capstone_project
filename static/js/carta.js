// ---------------------------------------------------------
// Carta digital
// Selección de pizzas, filtros y panel de resumen.
// ---------------------------------------------------------

let pizzaActualId = null;
let tamanoActual = "mediana";

const filtrosDieta = new Set();
let categoriaActiva = "todas";
let textoBusqueda = "";

function soles(valor) {
  return "S/ " + Number(valor).toFixed(2);
}

function obtenerPizza(id) {
  return PIZZAS.find((p) => p.id === id) || null;
}

// ---------------------------------------------------------
// Panel de resumen
// ---------------------------------------------------------
function seleccionarPizza(pizzaId) {
  const pizza = obtenerPizza(pizzaId);
  if (!pizza) return;

  pizzaActualId = pizzaId;

  document.getElementById("res-nombre").textContent = pizza.nombre;
  document.getElementById("res-descripcion").textContent = pizza.descripcion;
  document.getElementById("res-etiqueta").textContent = pizza.badge;
  document.getElementById("link-personalizar").href = URL_PERSONALIZAR.replace("__ID__", pizza.id);

  // Tamaños disponibles con su precio real
  const cont = document.getElementById("res-tamanos");
  cont.innerHTML = "";
  TAMANOS.forEach((t) => {
    const label = document.createElement("label");
    label.className = "opcion-tamano" + (t.id === tamanoActual ? " activo" : "");
    label.innerHTML = `
      <input type="radio" name="tamano-res" value="${t.id}" ${t.id === tamanoActual ? "checked" : ""}>
      <div>
        <strong>${t.nombre}</strong>
        <span class="desc-tamano">${t.desc}</span>
        <span class="precio-tamano">${soles(pizza.precios[t.id])}</span>
      </div>`;
    label.querySelector("input").addEventListener("change", () => {
      tamanoActual = t.id;
      seleccionarPizza(pizzaActualId);
    });
    cont.appendChild(label);
  });

  // Ingredientes de la receta
  document.getElementById("res-ingredientes").innerHTML = pizza.receta
    .map(
      (i) => `<div class="fila-receta">
        <span>${i.emoji} ${i.nombre}</span>
        <span class="precio-incluido">Incluido</span>
      </div>`
    )
    .join("");

  marcarTarjetaActiva(pizzaId);
  cotizar(pizza);
}

function cotizar(pizza) {
  fetch("/api/cotizar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pizza_id: pizza.id,
      tamano_id: tamanoActual,
      ingredientes: pizza.ingredientes,
    }),
  })
    .then((r) => r.json())
    .then((datos) => {
      document.getElementById("res-desglose").innerHTML = datos.desglose
        .map(
          (f) => `<div class="fila-desglose">
            <span>${f.etiqueta}</span><span>${soles(f.valor)}</span>
          </div>`
        )
        .join("");
      document.getElementById("res-total").textContent = soles(datos.total);
      document.getElementById("res-total-boton").textContent = soles(datos.total);
      document.getElementById("res-tiempo").textContent = `⏱ ${datos.minutos} min de horno`;
      document.getElementById("res-kcal").textContent = `${datos.kcal} kcal aprox.`;
      document.getElementById("btn-agregar-carrito").disabled = false;
    });
}

function marcarTarjetaActiva(pizzaId) {
  document.querySelectorAll(".tarjeta-pizza").forEach((tarjeta) => {
    const meta = tarjeta.querySelector(".meta-pizza");
    const activa = tarjeta.dataset.id === pizzaId;
    tarjeta.classList.toggle("tarjeta-activa", activa);
    meta.textContent = activa ? "Seleccionada · mírala en el panel" : meta.dataset.metaDefault;
  });
}

// ---------------------------------------------------------
// Agregar al carrito directo desde la carta
// ---------------------------------------------------------
function agregarAlCarrito() {
  const pizza = obtenerPizza(pizzaActualId);
  if (!pizza) return;

  const boton = document.getElementById("btn-agregar-carrito");
  const textoOriginal = boton.innerHTML;
  boton.disabled = true;
  boton.innerHTML = "Agregando…";

  fetch("/carrito/agregar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pizza_id: pizza.id,
      tamano_id: tamanoActual,
      ingredientes: pizza.ingredientes,
      cantidad: 1,
      nombre: pizza.nombre,
    }),
  })
    .then((r) => r.json())
    .then((datos) => {
      if (datos.cantidad !== undefined) {
        document.getElementById("contador-carrito").textContent = datos.cantidad;
      }
      boton.innerHTML = "Agregada al carrito";
      setTimeout(() => {
        boton.innerHTML = textoOriginal;
        boton.disabled = false;
      }, 1400);
    })
    .catch(() => {
      boton.innerHTML = "No se pudo agregar, intenta de nuevo";
      setTimeout(() => {
        boton.innerHTML = textoOriginal;
        boton.disabled = false;
      }, 1600);
    });
}

// ---------------------------------------------------------
// Filtros
// ---------------------------------------------------------
function aCamel(str) {
  return str.replace(/_([a-z])/g, (m, c) => c.toUpperCase());
}

function aplicarFiltros() {
  let visibles = 0;

  document.querySelectorAll(".tarjeta-pizza").forEach((tarjeta) => {
    const coincideCategoria =
      categoriaActiva === "todas" || tarjeta.dataset.categoria === categoriaActiva;

    const coincideTexto =
      textoBusqueda === "" ||
      tarjeta.dataset.nombre.includes(textoBusqueda) ||
      tarjeta.dataset.descripcion.includes(textoBusqueda) ||
      tarjeta.dataset.ingredientes.includes(textoBusqueda);

    let coincideDieta = true;
    filtrosDieta.forEach((d) => {
      if (tarjeta.dataset[aCamel(d)] !== "si") coincideDieta = false;
    });

    const visible = coincideCategoria && coincideTexto && coincideDieta;
    tarjeta.style.display = visible ? "" : "none";
    if (visible) visibles++;
  });

  document.getElementById("sin-resultados").style.display = visibles === 0 ? "block" : "none";
}

// ---------------------------------------------------------
// Eventos
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  // Toda la tarjeta selecciona la pizza (menos el enlace de personalizar)
  document.querySelectorAll(".tarjeta-pizza").forEach((tarjeta) => {
    tarjeta.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      seleccionarPizza(tarjeta.dataset.id);
    });
    tarjeta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        seleccionarPizza(tarjeta.dataset.id);
      }
    });
  });

  if (PIZZAS.length) seleccionarPizza(PIZZAS[0].id);

  document.getElementById("btn-agregar-carrito").addEventListener("click", agregarAlCarrito);

  document.querySelectorAll(".tab-categoria").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab-categoria").forEach((t) => t.classList.remove("activo"));
      tab.classList.add("activo");
      categoriaActiva = tab.dataset.categoria;
      aplicarFiltros();
    });
  });

  document.getElementById("buscador-input").addEventListener("input", (e) => {
    textoBusqueda = e.target.value.trim().toLowerCase();
    aplicarFiltros();
  });

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