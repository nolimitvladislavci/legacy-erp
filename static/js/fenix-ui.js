/* Fenix UI — global utilities */
(function(){
  // Toast notifications
  window.fenixToast = function(msg, type, duration) {
    type = type || "info";
    duration = duration || (type === "error" ? 8000 : type === "warning" ? 6000 : 3000);
    var el = document.createElement("div");
    el.className = "fenix-toast " + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function(){ el.classList.add("show"); }, 10);
    if (type !== "error") {
      setTimeout(function(){ el.classList.remove("show"); setTimeout(function(){ el.remove(); }, 300); }, duration);
    } else {
      el.style.cursor = "pointer";
      el.onclick = function(){ el.remove(); };
    }
  };

  // Button loading state
  window.btnLoading = function(btn, loading) {
    if (loading) {
      btn.dataset.originalText = btn.textContent;
      btn.classList.add("btn-loading");
      btn.textContent = "Obrada...";
    } else {
      btn.classList.remove("btn-loading");
      btn.textContent = btn.dataset.originalText || "OK";
    }
  };

  // Page enter animation
  document.addEventListener("DOMContentLoaded", function() {
    var main = document.querySelector(".main-content, .content, main, [class*=\"page\"]");
    if (main) main.classList.add("page-enter");
  });

  // Auto-dismiss Django messages after 5s
  document.addEventListener("DOMContentLoaded", function() {
    var msgs = document.querySelectorAll(".messages .alert, .django-message");
    msgs.forEach(function(m) {
      setTimeout(function() { m.style.transition = "opacity .3s"; m.style.opacity = "0"; setTimeout(function(){ m.remove(); }, 300); }, 5000);
    });
  });
})();
