const tourTableBody = document.getElementById("tourTableBody");
const filterType = document.getElementById("filterType");
const filterMonth = document.getElementById("filterMonth");
const filterYear = document.getElementById("filterYear");

const btnImport = document.getElementById("btnImport");
const fileInput = document.getElementById("fileInput");

function num(val, fallback = 0) {
    const n = Number(val);
    return Number.isFinite(n) ? n : fallback;
}

function monthNameFromValue(monthVal) {
    const m = Number(monthVal);
    const names = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
    if (Number.isInteger(m) && m >= 1 && m <= 12) return names[m - 1];
    return "";
}

/**
 * Liefert Text für "Rest bis Ziel" (km):
 * - wenn Rest >= 0: "123"
 * - wenn Rest < 0: "Übererfüllt 45"
 */
function restText(goalKm, doneKm) {
    const g = num(goalKm, 0);
    const d = num(doneKm, 0);
    const diff = g - d;

    if (diff >= 0) {
        return diff.toFixed(0);
    }
    return `Übererfüllt ${Math.abs(diff).toFixed(0)}`;
}

function remainingKm(goalKm, doneKm) {
    return Math.max(0, num(goalKm, 0) - num(doneKm, 0));
}

function getTodayDateOnly() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function getRemainingDaysUntilYearEnd(year) {
    const targetYear = Number(year);
    if (!Number.isInteger(targetYear)) return 0;

    const today = getTodayDateOnly();
    const yearStart = new Date(targetYear, 0, 1);
    const yearEnd = new Date(targetYear, 11, 31);

    if (today > yearEnd) {
        return 0;
    }

    if (today < yearStart) {
        const msPerDay = 24 * 60 * 60 * 1000;
        return Math.floor((yearEnd - yearStart) / msPerDay) + 1;
    }

    const msPerDay = 24 * 60 * 60 * 1000;
    return Math.floor((yearEnd - today) / msPerDay) + 1;
}

function getRemainingDaysUntilMonthEnd(year, month) {
    const targetYear = Number(year);
    const targetMonth = Number(month);

    if (!Number.isInteger(targetYear) || !Number.isInteger(targetMonth) || targetMonth < 1 || targetMonth > 12) {
        return 0;
    }

    const today = getTodayDateOnly();
    const monthStart = new Date(targetYear, targetMonth - 1, 1);
    const monthEnd = new Date(targetYear, targetMonth, 0);

    if (today > monthEnd) {
        return 0;
    }

    const msPerDay = 24 * 60 * 60 * 1000;

    if (today < monthStart) {
        return Math.floor((monthEnd - monthStart) / msPerDay) + 1;
    }

    return Math.floor((monthEnd - today) / msPerDay) + 1;
}

function getRemainingDaysUntilWeekEnd() {
    const today = getTodayDateOnly();
    const day = today.getDay(); // 0=So, 1=Mo, ..., 6=Sa
    const daysUntilSunday = day === 0 ? 0 : 7 - day;
    return daysUntilSunday + 1; // inkl. heute
}

function dailyKmNeeded(goalKm, doneKm, remainingDays) {
    const restKm = remainingKm(goalKm, doneKm);

    if (restKm <= 0 || remainingDays <= 0) {
        return 0;
    }

    return restKm / remainingDays;
}

function formatDailyKm(value) {
    return num(value, 0).toLocaleString("de-DE", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
    });
}

/**
 * Hauptfunktion zum Laden aller Daten (Ziele, Stats, Touren)
 */
async function loadData() {
    try {
        const type = filterType ? filterType.value : "cycling";
        const month = filterMonth ? filterMonth.value : "";
        const year = filterYear ? filterYear.value : "";

        // 1. Ziele laden
        const respGoals = await fetch("/api/goals");
        const goalsData = await respGoals.json();
        const goals = goalsData.status === "ok" ? goalsData.goals : {};

        // 2. Statistiken laden (Monat, Jahr, Woche)
        const respStats = await fetch(`/api/stats?type=${type}&month=${month}&year=${year}`);
        const stats = await respStats.json();

        // 3. Tourenliste laden
        const respTours = await fetch(`/api/tours?type=${type}&month=${month}&year=${year}`);
        const tours = await respTours.json();

        // --- UI AKTUALISIEREN: ZIELE / FORTSCHRITT ---

        // Anzeige Jahr
        const goalYear = num(goals.goal_km_year, 0);
        const doneYear = num(stats.year_km, 0);
        document.getElementById("goalYearDone").textContent = doneYear.toFixed(0);
        document.getElementById("goalYearTotal").textContent = goalYear.toFixed(0);
        document.getElementById("goalYearRest").textContent = restText(goalYear, doneYear);

        const goalYearPerDayEl = document.getElementById("goalYearPerDay");
        if (goalYearPerDayEl) {
            const remainingYearDays = getRemainingDaysUntilYearEnd(year);
            const yearDailyKm = dailyKmNeeded(goalYear, doneYear, remainingYearDays);
            goalYearPerDayEl.textContent = formatDailyKm(yearDailyKm);
        }

        // Anzeige Monat
        const goalMonth = num(goals.monthly, 0);
        const doneMonth = num(stats.month_km, 0);
        document.getElementById("goalMonthDone").textContent = doneMonth.toFixed(0);
        document.getElementById("goalMonthTotal").textContent = goalMonth.toFixed(0);
        document.getElementById("goalMonthRest").textContent = restText(goalMonth, doneMonth);

        const goalMonthPerDayEl = document.getElementById("goalMonthPerDay");
        if (goalMonthPerDayEl) {
            const remainingMonthDays = getRemainingDaysUntilMonthEnd(year, month);
            const monthDailyKm = dailyKmNeeded(goalMonth, doneMonth, remainingMonthDays);
            goalMonthPerDayEl.textContent = formatDailyKm(monthDailyKm);
        }

        // Anzeige Woche (Montag bis heute)
        const goalWeek = num(goals.weekly, 0);
        const doneWeek = num(stats.week_km, 0);
        if (document.getElementById("goalWeekDone")) {
            document.getElementById("goalWeekDone").textContent = doneWeek.toFixed(0);
            document.getElementById("goalWeekTotal").textContent = goalWeek.toFixed(0);
            document.getElementById("goalWeekRest").textContent = restText(goalWeek, doneWeek);

            const goalWeekPerDayEl = document.getElementById("goalWeekPerDay");
            if (goalWeekPerDayEl) {
                const remainingWeekDays = getRemainingDaysUntilWeekEnd();
                const weekDailyKm = dailyKmNeeded(goalWeek, doneWeek, remainingWeekDays);
                goalWeekPerDayEl.textContent = formatDailyKm(weekDailyKm);
            }
        }

        // --- UI AKTUALISIEREN: RECHTE BOX (STATS) ---
        const monthName = monthNameFromValue(month);
        document.getElementById("statsMonthTitle").textContent = `Monat: ${monthName}`;
        document.getElementById("statsMonthKm").textContent = num(stats.month_km, 0).toFixed(1);
        document.getElementById("statsMonthCount").textContent = num(stats.month_count, 0);

        document.getElementById("statsYearTitle").textContent = `Gesamtleistung ${year}:`;
        document.getElementById("statsYearKm").textContent = num(stats.year_km, 0).toFixed(1);
        document.getElementById("statsYearCount").textContent = num(stats.year_count, 0);

        // --- UI AKTUALISIEREN: TOUREN-TABELLE ---
        renderTours(Array.isArray(tours) ? tours : []);
    } catch (e) {
        console.error("Fehler beim Laden der Dashboard-Daten:", e);
    }
}

function renderTours(tours) {
    if (!tourTableBody) return;
    tourTableBody.innerHTML = "";

    if (tours.length === 0) {
        tourTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Keine Touren gefunden.</td></tr>';
        return;
    }

    tours.forEach(t => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.onclick = () => {
            window.location.href = `/tour/${t.id}`;
        };

        tr.innerHTML = `
            <td>${t.name}</td>
            <td>${t.date_display}</td>
            <td>${t.duration_hm}</td>
            <td style="text-align:right;">${num(t.distance_km, 0).toFixed(2)}</td>
        `;
        tourTableBody.appendChild(tr);
    });
}

/**
 * Upload-Logik
 */
async function uploadGpxFiles(files) {
    if (!files || files.length === 0) return;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
    }

    try {
        const resp = await fetch("/import", {
            method: "POST",
            body: formData
        });

        const result = await resp.json();

        if (!resp.ok || !result.ok) {
            const msg = result?.error ? result.error : "Import fehlgeschlagen.";
            alert(msg);
            return;
        }

        if (result.errors && result.errors.length > 0) {
            alert(`Import abgeschlossen (${result.imported_count}).\nEinige Dateien konnten nicht importiert werden.`);
        }

        await loadData();
    } catch (e) {
        console.error("Import Fehler:", e);
        alert("Import fehlgeschlagen (Netzwerk/Server).");
    } finally {
        if (fileInput) fileInput.value = "";
    }
}

// Event Listener für Import
if (btnImport && fileInput) {
    btnImport.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async (e) => {
        const files = e.target.files;
        await uploadGpxFiles(files);
    });
}

// Filteränderungen (Typ, Monat, Jahr) lösen Neuladen aus
[filterType, filterMonth, filterYear].forEach(el => {
    if (el) el.addEventListener("change", loadData);
});

// Aktualisieren, wenn Ziele in anderem Tab geändert wurden
window.addEventListener("storage", (e) => {
    if (e && e.key === "goals_updated") {
        loadData();
    }
});

// Initiales Laden beim Start
document.addEventListener("DOMContentLoaded", loadData);