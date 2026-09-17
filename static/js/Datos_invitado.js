// ---------------------------------------------------------
// Datos del invitado: muestra dirección o número de mesa
// según la forma de entrega elegida.
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const campoDireccion = document.getElementById("campo-direccion");
  const campoMesa = document.getElementById("campo-mesa");

  function actualizarCampos(tipo) {
    campoDireccion.style.display = tipo === "domicilio" ? "" : "none";
    campoMesa.style.display = tipo === "mesa" ? "" : "none";
  }

  document.querySelectorAll('input[name="tipo_entrega"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      document.querySelectorAll(".opcion-entrega").forEach((o) => o.classList.remove("activo"));
      radio.closest(".opcion-entrega").classList.add("activo");
      actualizarCampos(radio.value);
    });
  });

  const seleccionado = document.querySelector('input[name="tipo_entrega"]:checked');
  actualizarCampos(seleccionado ? seleccionado.value : "domicilio");
});