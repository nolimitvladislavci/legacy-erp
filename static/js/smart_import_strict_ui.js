/* smart_import_strict_ui.js - Sustav povratnih informacija za Visković Group Premium */
document.addEventListener("DOMContentLoaded", function() {
    
    // 1. Hvatanje standardnih formi (Upload)
    const forms = document.querySelectorAll("form");
    forms.forEach(form => {
        form.addEventListener("submit", function() {
            const submitBtns = form.querySelectorAll("button[type='submit']");
            submitBtns.forEach(btn => {
                btn.disabled = true;
                btn.dataset.originalText = btn.innerHTML;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="margin-right: 8px;"></span> Obrada u tijeku...';
                btn.style.opacity = "0.7";
                btn.style.cursor = "not-allowed";
            });
        });
    });

    // 2. Strict Wrapper za AJAX/Fetch pozive
    window.strictAjaxSubmit = async function(url, formData, triggerButton) {
        let originalText = "";
        if (triggerButton) {
            triggerButton.disabled = true;
            originalText = triggerButton.innerHTML;
            triggerButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="margin-right: 8px;"></span> Slanje...';
        }

        try {
            const response = await fetch(url, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });
            
            const data = await response.json();

            if (!response.ok || data.error) {
                showPremiumToast("GREŠKA: " + (data.error || "Sustav nije odgovorio (Status: " + response.status + ")"), "error");
            } else {
                showPremiumToast("Akcija uspješno izvršena.", "success");
            }
            return data;
            
        } catch (error) {
            showPremiumToast("Kritična greška: Neuspješna komunikacija sa serverom.", "error");
            console.error(error);
            throw error;
        } finally {
            if (triggerButton) {
                triggerButton.disabled = false;
                triggerButton.innerHTML = originalText;
            }
        }
    };

    // 3. Premium Toast Notifikacije
    function showPremiumToast(message, type) {
        const toast = document.createElement("div");
        toast.style.position = "fixed";
        toast.style.bottom = "30px";
        toast.style.right = "30px";
        toast.style.padding = "16px 24px";
        toast.style.borderRadius = "8px";
        toast.style.color = "#ffffff";
        toast.style.fontWeight = "600";
        toast.style.zIndex = "99999";
        toast.style.boxShadow = "0 10px 25px rgba(0,0,0,0.2)";
        toast.style.transition = "all 0.3s ease";
        toast.style.fontFamily = "system-ui, -apple-system, sans-serif";

        if (type === "error") {
            toast.style.backgroundColor = "#dc3545";
            toast.style.borderLeft = "6px solid #8b0000";
        } else {
            toast.style.backgroundColor = "#1e1e1e";
            toast.style.border = "1px solid #d4af37";
            toast.style.borderLeft = "6px solid #d4af37";
        }

        toast.innerText = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(20px)";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
});
