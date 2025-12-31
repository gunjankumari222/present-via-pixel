function showToast(msg, cat) {
  const bg = (cat=="success") ? "#198754" : (cat=="error") ? "#dc3545" : (cat=="info") ? "#0d6efd" : "#6c757d";
  const toast = document.createElement("div");
  toast.style.position = "fixed";
  toast.style.right = "20px";
  toast.style.bottom = "20px";
  toast.style.background = bg;
  toast.style.color = "white";
  toast.style.padding = "12px 18px";
  toast.style.borderRadius = "8px";
  toast.style.boxShadow = "0 6px 18px rgba(0,0,0,0.12)";
  toast.style.zIndex = 9999;
  toast.innerText = msg;
  document.body.appendChild(toast);
  setTimeout(()=> {
    toast.style.transition = "opacity 0.4s";
    toast.style.opacity = 0;
    setTimeout(()=> toast.remove(), 400);
  }, 3000);
}
