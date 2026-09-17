// ---------------------------------------------------------
// Constructor de pizzas
// Se usa igual para "Crear mi pizza" (desde cero) y para
// "Personalizar receta" (partiendo de una pizza de la carta).
// El cálculo de precios y las reglas de compatibilidad viven en el
// servidor (data.py); aquí solo dibujamos y mostramos lo que responde.
// ---------------------------------------------------------

const ING_POR_ID = {};
INGREDIENTES.forEach((i) => (ING_POR_ID[i.id] = i));

const seleccion = new Set(SELECCION_INICIAL);
let tamanoActual = TAMANO_INICIAL;
let cantidad = 1;
let similarDescartado = null;
let ultimaCotizacion = null;

const GRUPOS_TOPPING = ["carne", "vegetal", "dulce", "extra"];

function soles(valor) {
  return "S/ " + Number(valor).toFixed(2);
}

// ---------------------------------------------------------
// Vista previa: dibujamos la pizza con lo que hay seleccionado
// ---------------------------------------------------------
function semilla(texto) {
  let h = 7;
  for (let i = 0; i < texto.length; i++) h = (h * 31 + texto.charCodeAt(i)) % 9973;
  return h;
}

function mezclar(colores) {
  if (!colores.length) return "#f6e4b8";
  let r = 0, g = 0, b = 0;
  colores.forEach((c) => {
    r += parseInt(c.slice(1, 3), 16);
    g += parseInt(c.slice(3, 5), 16);
    b += parseInt(c.slice(5, 7), 16);
  });
  const n = colores.length;
  const hex = (v) => Math.round(v / n).toString(16).padStart(2, "0");
  return "#" + hex(r) + hex(g) + hex(b);
}

function dibujarPizza() {
  const elegidos = [...seleccion].map((id) => ING_POR_ID[id]).filter(Boolean);
  const masa = elegidos.find((i) => i.grupo === "masa");
  const salsa = elegidos.find((i) => i.grupo === "salsa");
  const quesos = elegidos.filter((i) => i.grupo === "queso");
  const toppings = elegidos.filter((i) => GRUPOS_TOPPING.includes(i.grupo));

  const colorMasa = masa ? masa.color : "#e6d3b3";
  const colorSalsa = salsa ? salsa.color : "#efe6d5";
  const colorQueso = quesos.length ? mezclar(quesos.map((q) => q.color)) : null;

  let partes = `
    <defs>
      <radialGradient id="borde" cx="50%" cy="45%" r="60%">
        <stop offset="60%" stop-color="${colorMasa}"/>
        <stop offset="100%" stop-color="#b98146"/>
      </radialGradient>
    </defs>
    <circle cx="160" cy="160" r="146" fill="url(#borde)"/>
    <circle cx="160" cy="160" r="128" fill="${colorSalsa}"/>`;

  if (colorQueso) {
    partes += `<circle cx="160" cy="160" r="122" fill="${colorQueso}" opacity="0.72"/>`;
    // Burbujas de queso derretido
    for (let k = 0; k < 14; k++) {
      const idx = semilla("queso" + k) + k * 13;
      const ang = idx * 2.39996;
      const rad = 18 + ((idx * 23) % 96);
      const x = 160 + Math.cos(ang) * rad;
      const y = 160 + Math.sin(ang) * rad;
      partes += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${6 + (idx % 5)}" fill="#fff8e2" opacity="0.5"/>`;
    }
  }

  // Cada ingrediente se reparte por la pizza en posiciones fijas,
  // así la vista previa no "salta" cada vez que tocas algo.
  toppings.forEach((ing) => {
    const base = semilla(ing.id);
    const copias = ing.grupo === "extra" ? 4 : 6;
    for (let k = 0; k < copias; k++) {
      const idx = base + k * 149;
      const ang = idx * 2.39996;
      const rad = 22 + ((idx * 29) % 92);
      const x = 160 + Math.cos(ang) * rad;
      const y = 160 + Math.sin(ang) * rad;
      const giro = (idx % 60) - 30;
      partes += `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" font-size="22"
        text-anchor="middle" dominant-baseline="central"
        transform="rotate(${giro} ${x.toFixed(1)} ${y.toFixed(1)})">${ing.emoji}</text>`;
    }
  });

  if (!masa) {
    partes = `<circle cx="160" cy="160" r="140" fill="#efe9f6" stroke="#ddd6ee" stroke-width="3" stroke-dasharray="10 8"/>
      <text x="160" y="168" font-size="20" text-anchor="middle" fill="#5b5670">Elige una masa</text>`;
  }

  document.getElementById("dibujo-pizza").innerHTML = partes;

  // Pie de foto en palabras
  const trozos = [];
  if (masa) trozos.push(masa.nombre.toLowerCase());
  if (salsa) trozos.push("con " + salsa.nombre.toLowerCase());
  if (quesos.length) trozos.push(quesos.length === 1 ? "1 queso" : quesos.length + " quesos");
  if (toppings.length) trozos.push(toppings.length + (toppings.length === 1 ? " ingrediente" : " ingredientes"));
  document.getElementById("pie-preview").textContent =
    trozos.length ? trozos.join(" · ") : "Empieza eligiendo la masa";
}

// ---------------------------------------------------------
// Pintar lo que responde el servidor
// ---------------------------------------------------------
function pintarAvisos(errores, advertencias) {
  const zona = document.getElementById("avisos");
  let html = "";

  errores.forEach((e) => {
    html += `<div class="aviso aviso-error">
      <strong>${e.titulo}</strong>
      <span>${e.detalle}</span>
    </div>`;
  });

  advertencias.forEach((a) => {
    html += `<div class="aviso aviso-ojo">
      <strong>${a.titulo}</strong>
      <span>${a.detalle}</span>
    </div>`;
  });

  zona.innerHTML = html;
}

function pintarBloqueados(bloqueados) {
  document.querySelectorAll(".tarjeta-ing").forEach((tarjeta) => {
    const id = tarjeta.dataset.id;
    const motivo = bloqueados[id];
    const input = tarjeta.querySelector("input");

    if (motivo && !seleccion.has(id)) {
      tarjeta.classList.add("bloqueado");
      input.disabled = true;
      tarjeta.querySelector(".motivo-bloqueo").textContent = motivo;
    } else {
      tarjeta.classList.remove("bloqueado");
      input.disabled = false;
      tarjeta.querySelector(".motivo-bloqueo").textContent = "";
    }
    tarjeta.classList.toggle("activo", seleccion.has(id));
  });
}

function pintarDieta(dieta) {
  const zona = document.getElementById("etiquetas-dieta");
  const etiquetas = [];
  if (dieta.vegano) etiquetas.push("🌱 Vegana");
  if (dieta.sin_gluten) etiquetas.push("🌾 Sin gluten");
  if (dieta.sin_lactosa) etiquetas.push("🥛 Sin lactosa");
  zona.innerHTML = etiquetas.map((e) => `<span class="chip-dieta-resultado">${e}</span>`).join("");
}

function pintarSimilar(similares) {
  const caja = document.getElementById("tarjeta-similar");
  const similar = similares && similares.length ? similares[0] : null;

  if (!similar || similar.id === similarDescartado) {
    caja.hidden = true;
    return;
  }

  document.getElementById("similar-nombre").textContent = similar.nombre;
  document.getElementById("similar-coincidencia").textContent =
    `Se parece en un ${similar.coincidencia}% a lo que estás armando · desde ${soles(similar.precio)}`;

  const partes = [];
  if (similar.faltan.length) partes.push("Ella lleva además: " + similar.faltan.join(", ") + ".");
  if (similar.sobran.length) partes.push("Tu versión suma: " + similar.sobran.join(", ") + ".");
  document.getElementById("similar-detalle").textContent = partes.join(" ");

  document.getElementById("similar-usar").href = URL_PERSONALIZAR.replace("__ID__", similar.id);
  caja.dataset.similarId = similar.id;
  caja.hidden = false;
}

function pintarPrecios(datos) {
  const desglose = datos.desglose
    .map(
      (f) => `<div class="fila-desglose">
        <span>${f.etiqueta}</span>
        <span>${f.tipo === "extra" ? "+ " : ""}${soles(f.valor)}</span>
      </div>`
    )
    .join("");

  const quitados = datos.quitados.length
    ? `<div class="fila-desglose fila-quitados"><span>Sin: ${datos.quitados
        .map((q) => q.nombre)
        .join(", ")}</span><span>S/ 0.00</span></div>`
    : "";

  document.getElementById("desglose").innerHTML = desglose + quitados;
  document.getElementById("total").textContent = soles(datos.total * cantidad);
  document.getElementById("total-boton").textContent = soles(datos.total * cantidad);
  document.getElementById("tiempo-horno").textContent = `⏱ ${datos.minutos} min de horno`;
  document.getElementById("kcal").textContent = `${datos.kcal} kcal aprox.`;
}

// ---------------------------------------------------------
// Pedir la cotización al servidor
// ---------------------------------------------------------
let temporizador = null;

function actualizar() {
  dibujarPizza();
  clearTimeout(temporizador);
  temporizador = setTimeout(cotizar, 90);
}

function cotizar() {
  fetch("/api/cotizar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pizza_id: PIZZA_ID,
      tamano_id: tamanoActual,
      ingredientes: [...seleccion],
    }),
  })
    .then((r) => r.json())
    .then((datos) => {
      ultimaCotizacion = datos;
      pintarPrecios(datos);
      pintarAvisos(datos.errores, datos.advertencias);
      pintarBloqueados(datos.bloqueados);
      pintarDieta(datos.dieta);
      pintarSimilar(datos.similares);

      const boton = document.getElementById("btn-agregar");
      boton.disabled = !datos.ok;
      document.getElementById("nota-agregar").textContent = datos.ok
        ? ""
        : "Corrige los avisos de arriba para poder enviar esta pizza a cocina.";
    })
    .catch(() => {
      document.getElementById("nota-agregar").textContent =
        "No pudimos calcular el precio. Revisa tu conexión y vuelve a intentar.";
    });
}

// ---------------------------------------------------------
// Agregar al carrito
// ---------------------------------------------------------
function agregarAlCarrito() {
  const boton = document.getElementById("btn-agregar");
  boton.disabled = true;
  const textoOriginal = boton.innerHTML;
  boton.innerHTML = "Agregando…";

  fetch("/carrito/agregar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pizza_id: PIZZA_ID,
      tamano_id: tamanoActual,
      ingredientes: [...seleccion],
      cantidad: cantidad,
      nombre: document.getElementById("nombre-pizza").value.trim(),
    }),
  })
    .then((r) => r.json().then((d) => ({ ok: r.ok, datos: d })))
    .then(({ ok, datos }) => {
      if (!ok) {
        boton.innerHTML = textoOriginal;
        boton.disabled = false;
        document.getElementById("nota-agregar").textContent =
          datos.mensaje || "Esa combinación no se puede preparar.";
        return;
      }
      boton.innerHTML = "Listo, vamos al carrito";
      window.location.href = URL_CARRITO;
    })
    .catch(() => {
      boton.innerHTML = textoOriginal;
      boton.disabled = false;
      document.getElementById("nota-agregar").textContent =
        "No pudimos agregar la pizza. Intenta otra vez.";
    });
}

// ---------------------------------------------------------
// Eventos
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  // Ingredientes
  document.querySelectorAll(".tarjeta-ing input").forEach((input) => {
    input.addEventListener("change", () => {
      const tarjeta = input.closest(".tarjeta-ing");
      const id = tarjeta.dataset.id;
      const grupo = tarjeta.dataset.grupo;
      const esUnico = input.type === "radio";

      if (esUnico) {
        // Masa y salsa: solo una. Sacamos la anterior del grupo.
        document.querySelectorAll(`.tarjeta-ing[data-grupo="${grupo}"]`).forEach((t) => {
          if (t.dataset.id !== id) seleccion.delete(t.dataset.id);
        });
        seleccion.add(id);
      } else if (input.checked) {
        seleccion.add(id);
      } else {
        seleccion.delete(id);
      }

      similarDescartado = null;
      actualizar();
    });
  });

  // Tamaño
  document.querySelectorAll('input[name="tamano"]').forEach((input) => {
    input.addEventListener("change", () => {
      tamanoActual = input.value;
      document.querySelectorAll(".tarjeta-tamano").forEach((t) => t.classList.remove("activo"));
      input.closest(".tarjeta-tamano").classList.add("activo");
      actualizar();
    });
  });

  // Cantidad
  document.getElementById("mas").addEventListener("click", () => {
    cantidad = Math.min(20, cantidad + 1);
    document.getElementById("cantidad").textContent = cantidad;
    if (ultimaCotizacion) pintarPrecios(ultimaCotizacion);
  });
  document.getElementById("menos").addEventListener("click", () => {
    cantidad = Math.max(1, cantidad - 1);
    document.getElementById("cantidad").textContent = cantidad;
    if (ultimaCotizacion) pintarPrecios(ultimaCotizacion);
  });

  // Pizza parecida
  document.getElementById("similar-seguir").addEventListener("click", () => {
    similarDescartado = document.getElementById("tarjeta-similar").dataset.similarId;
    document.getElementById("tarjeta-similar").hidden = true;
  });

  document.getElementById("btn-agregar").addEventListener("click", agregarAlCarrito);

  actualizar();
});