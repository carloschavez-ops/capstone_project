// ---------------------------------------------------------
// Carrito: método de pago y cálculo del vuelto
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const totalEl = document.getElementById("total-pedido");
  if (!totalEl) return; // carrito vacío

  const total = parseFloat(totalEl.dataset.total);
  const input = document.getElementById("paga-con");
  const caja = document.getElementById("caja-vuelto");
  const monto = document.getElementById("monto-vuelto");
  const bloqueEfectivo = document.getElementById("bloque-efectivo");

  function soles(v) {
    return "S/ " + Number(v).toFixed(2);
  }

  function calcularVuelto() {
    const paga = parseFloat(input.value);

    if (!input.value || isNaN(paga)) {
      caja.className = "caja-vuelto";
      caja.querySelector("span").textContent = "Tu vuelto";
      monto.textContent = soles(0);
      return;
    }

    if (paga < total) {
      caja.className = "caja-vuelto falta";
      caja.querySelector("span").textContent = "Te falta";
      monto.textContent = soles(total - paga);
    } else {
      caja.className = "caja-vuelto listo";
      caja.querySelector("span").textContent =
        paga === total ? "Pago exacto, sin vuelto" : "Tu vuelto";
      monto.textContent = soles(paga - total);
    }
  }

  input.addEventListener("input", calcularVuelto);

  document.querySelectorAll(".chip-billete").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip-billete").forEach((c) => c.classList.remove("activo"));
      chip.classList.add("activo");
      input.value = chip.id === "chip-exacto" ? total.toFixed(2) : chip.dataset.monto;
      calcularVuelto();
    });
  });

  // Solo pedimos el vuelto cuando el pago es en efectivo
  document.querySelectorAll('input[name="metodo_pago"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      document.querySelectorAll(".metodo").forEach((m) => m.classList.remove("activo"));
      radio.closest(".metodo").classList.add("activo");
      const esEfectivo = radio.value === "efectivo";
      bloqueEfectivo.style.display = esEfectivo ? "" : "none";
      input.required = esEfectivo;
    });
  });

  calcularVuelto();
});