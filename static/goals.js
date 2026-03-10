// static/goals.js
//
// Anforderungen:
// - Nur annual ist editierbar
// - Beim Speichern von annual werden monthly/weekly/daily neu berechnet, angezeigt und gespeichert
// - Dashboard soll automatisch aktualisieren -> localStorage.goals_updated setzen

const GOAL_UI_TO_DB_KEY = {
    annual: "goal_km_year",
    monthly: "monthly",
    weekly: "weekly",
    daily: "daily",
};

function num(val, fallback = 0) {
    const n = Number(val);
    return Number.isFinite(n) ? n : fallback;
}

function isLeapYear(year) {
    return (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0);
}

/**
 * ISO-Wochenanzahl eines Jahres (52 oder 53).
 * Regel: ISO week count = ISO-Wochennummer von 28. Dezember.
 */
function isoWeeksInYear(year) {
    const d = new Date(Date.UTC(year, 11, 28)); // 28. Dez
    // ISO week number:
    const dayNum = (d.getUTCDay() + 6) % 7; // Mon=0..Sun=6
    d.setUTCDate(d.getUTCDate() - dayNum + 3); // Donnerstag derselben Woche
    const firstThursday = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
    const firstDayNum = (firstThursday.getUTCDay() + 6) % 7;
    firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3);

    const week = 1 + Math.round((d - firstThursday) / (7 * 24 * 3600 * 1000));
    return week;
}

function toUiGoals(raw) {
    const src = raw && typeof raw === "object" ? raw : {};

    // Wenn UI-Keys vorhanden sind, verwenden
    const hasUiKeys = ["annual", "monthly", "weekly", "daily"].some(
        (k) => Object.prototype.hasOwnProperty.call(src, k)
    );

    if (hasUiKeys) {
        return {
            annual: num(src.annual, 0),
            monthly: num(src.monthly, 0),
            weekly: num(src.weekly, 0),
            daily: num(src.daily, 0),
        };
    }

    // Sonst: DB-Keys -> UI
    return {
        annual: num(src[GOAL_UI_TO_DB_KEY.annual], 0),
        monthly: num(src[GOAL_UI_TO_DB_KEY.monthly], 0),
        weekly: num(src[GOAL_UI_TO_DB_KEY.weekly], 0),
        daily: num(src[GOAL_UI_TO_DB_KEY.daily], 0),
    };
}

document.addEventListener("DOMContentLoaded", () => {
    loadGoals();
    setupAnnualEditListener();
});

async function loadGoals() {
    try {
        const resp = await fetch("/api/goals");
        const data = await resp.json();

        if (!resp.ok || data.status !== "ok") {
            alert("Fehler beim Laden der Ziele: " + (data?.message || resp.status));
            return;
        }

        const goalsUi = toUiGoals(data.goals);

        document.querySelectorAll(".goal-item").forEach((item) => {
            const key = item.dataset.key;
            const value = goalsUi[key] !== undefined ? num(goalsUi[key], 0).toFixed(2) : "0.00";

            const display = item.querySelector("[data-display]");
            const input = item.querySelector("[data-input]"); // existiert nur bei annual

            if (display) display.textContent = value;
            if (input) input.value = value;
        });
    } catch (e) {
        console.error("[goals] Load error", e);
        alert("Ein Netzwerkfehler ist aufgetreten.");
    }
}

function setupAnnualEditListener() {
    const annualItem = document.querySelector('.goal-item[data-key="annual"]');
    if (!annualItem) return;

    const btn = annualItem.querySelector("[data-button]");
    if (!btn) return;

    btn.addEventListener("click", () => {
        toggleAnnualEditMode(annualItem, btn);
    });
}

function toggleAnnualEditMode(item, button) {
    const display = item.querySelector("[data-display]");
    const input = item.querySelector("[data-input]");

    if (!display || !input) return;

    if (button.textContent === "Edit") {
        display.style.display = "none";
        input.style.display = "block";
        button.textContent = "Speichern";
        button.style.backgroundColor = "#d9534f";
        input.focus();
        return;
    }

    // Speichern
    saveAnnualAndDerived(input.value, item, button);
}

function closeAnnualEditMode(item, button) {
    const display = item.querySelector("[data-display]");
    const input = item.querySelector("[data-input]");

    if (display && input) {
        display.style.display = "block";
        input.style.display = "none";
        input.value = display.textContent;
    }

    button.textContent = "Edit";
    button.style.backgroundColor = "#4B77BE";
}

async function putGoal(dbKey, value) {
    const resp = await fetch("/api/goals", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: dbKey, value: value }),
    });
    const data = await resp.json();
    if (!resp.ok || data.status !== "ok") {
        throw new Error(data?.message || String(resp.status));
    }
    return data;
}

async function saveAnnualAndDerived(rawValue, annualItem, button) {
    const annual = parseFloat(String(rawValue).replace(",", "."));

    if (!Number.isFinite(annual) || annual < 0) {
        alert("Bitte geben Sie eine gültige positive Zahl ein.");
        return;
    }

    const year = new Date().getFullYear();
    const days = isLeapYear(year) ? 366 : 365;
    const weeks = isoWeeksInYear(year); // 52 oder 53

    const monthly = annual / 12.0;
    const weekly = annual / weeks;
    const daily = annual / days;

    try {
        // 1) Speichern: annual + derived (robust, in definierter Reihenfolge)
        await putGoal(GOAL_UI_TO_DB_KEY.annual, annual);
        await putGoal(GOAL_UI_TO_DB_KEY.monthly, monthly);
        await putGoal(GOAL_UI_TO_DB_KEY.weekly, weekly);
        await putGoal(GOAL_UI_TO_DB_KEY.daily, daily);

        // 2) UI aktualisieren (sauber: neu vom Server laden)
        await loadGoals();

        // 3) Editmode schließen
        closeAnnualEditMode(annualItem, button);

        // 4) Dashboard aktualisieren (andere Tabs / nach Rückkehr)
        localStorage.setItem("goals_updated", String(Date.now()));

    } catch (e) {
        console.error("[goals] Save error", e);
        alert("Speichern fehlgeschlagen: " + (e?.message || String(e)));
    }
}
