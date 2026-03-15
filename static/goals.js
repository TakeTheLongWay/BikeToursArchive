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
    const d = new Date(Date.UTC(year, 11, 28));
    const dayNum = (d.getUTCDay() + 6) % 7;
    d.setUTCDate(d.getUTCDate() - dayNum + 3);
    const firstThursday = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
    const firstDayNum = (firstThursday.getUTCDay() + 6) % 7;
    firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3);

    const week = 1 + Math.round((d - firstThursday) / (7 * 24 * 3600 * 1000));
    return week;
}

function toUiGoals(raw) {
    const src = raw && typeof raw === "object" ? raw : {};

    // Vorrang für kanonische DB-Keys; annual bleibt nur Fallback für Altbestand
    return {
        annual: num(src.goal_km_year, num(src.annual, 0)),
        monthly: num(src.monthly, 0),
        weekly: num(src.weekly, 0),
        daily: num(src.daily, 0),
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
            const input = item.querySelector("[data-input]");

            if (display) {
                display.textContent = value;
            }
            if (input) {
                input.value = value;
            }
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
        input.select();
        return;
    }

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
    const weeks = isoWeeksInYear(year);

    const monthly = annual / 12.0;
    const weekly = annual / weeks;
    const daily = annual / days;

    try {
        await putGoal(GOAL_UI_TO_DB_KEY.annual, annual);
        await putGoal(GOAL_UI_TO_DB_KEY.monthly, monthly);
        await putGoal(GOAL_UI_TO_DB_KEY.weekly, weekly);
        await putGoal(GOAL_UI_TO_DB_KEY.daily, daily);

        await loadGoals();
        closeAnnualEditMode(annualItem, button);

        localStorage.setItem("goals_updated", String(Date.now()));
    } catch (e) {
        console.error("[goals] Save error", e);
        alert("Speichern fehlgeschlagen: " + (e?.message || String(e)));
    }
}