// Formular zum Anlegen/Bearbeiten einer Sammlung (templates/_collection_form.html).
// onCancel wird nach "Abbrechen" aufgerufen; liefert show() zum Einblenden des Formulars.
function initCollectionForm(onCancel) {
    const wrapper = document.getElementById("collectionFormWrapper");
    const form = document.getElementById("collectionForm");
    const nameInput = document.getElementById("collection-name");
    const imageInput = document.getElementById("collection-image");
    const imageUrlInput = document.getElementById("collection-image-url");
    const removeImage = document.getElementById("collection-remove-image");
    const preview = document.getElementById("collectionPreview");
    // Bisheriges Bild beim Bearbeiten; wird gezeigt, solange kein neues gewählt ist
    const currentImage = form.dataset.currentImage || null;
    // Vorschau-URL einer gewählten Datei, wird beim Wechsel wieder freigegeben
    let fileObjectUrl = null;

    function showPreview(src) {
        if (fileObjectUrl && src !== fileObjectUrl) {
            URL.revokeObjectURL(fileObjectUrl);
            fileObjectUrl = null;
        }
        if (src) {
            preview.src = src;
            preview.style.display = "block";
        } else {
            preview.removeAttribute("src");
            preview.style.display = "none";
        }
    }

    // Nicht ladbare URL: keine leere Vorschau zeigen, der Server meldet den Fehler beim Speichern
    preview.addEventListener("error", () => {
        preview.style.display = "none";
    });

    function updatePreview() {
        if (imageInput.files.length) return;
        const url = imageUrlInput.value.trim();
        if (/^https?:\/\/\S+$/i.test(url)) {
            showPreview(url);
        } else {
            showPreview(!url && currentImage && !(removeImage && removeImage.checked) ? currentImage : null);
        }
    }

    document.getElementById("collectionBrowse").addEventListener("click", () => imageInput.click());

    // Gewählte Datei: Dateiname im Eingabefeld, Vorschau aus der Datei
    imageInput.addEventListener("change", () => {
        const file = imageInput.files[0];
        if (!file) return;
        imageUrlInput.value = file.name;
        fileObjectUrl = URL.createObjectURL(file);
        showPreview(fileObjectUrl);
    });

    // Eingabe im Feld ersetzt eine zuvor gewählte Datei durch die URL
    imageUrlInput.addEventListener("input", () => {
        if (imageInput.files.length) {
            imageInput.value = "";
        }
        updatePreview();
    });

    if (removeImage) {
        removeImage.addEventListener("change", updatePreview);
    }

    document.getElementById("collectionCancel").addEventListener("click", () => {
        form.reset();
        nameInput.value = form.dataset.initialName || "";
        imageUrlInput.value = "";
        imageInput.value = "";
        updatePreview();
        form.querySelector(".msg-error")?.remove();
        wrapper.hidden = true;
        onCancel();
    });

    // Nach einem Fehler steht das Formular offen und die URL wieder im Feld
    updatePreview();
    if (!wrapper.hidden) {
        nameInput.focus();
    }

    return {
        show() {
            wrapper.hidden = false;
            nameInput.focus();
        }
    };
}
