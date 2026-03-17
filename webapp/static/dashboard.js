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
    const names = [
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember"
    ];
    if (Number.isInteger(m) && m >= 1 && m <= 12) {
        return names[m - 1];
    }
    return "";
}

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
    if (!Number.isInteger(targetYear)) {
        return 0;
    }

    const today = getTodayDateOnly();
    const yearStart = new Date(targetYear, 0, 1);
    const yearEnd = new Date(targetYear, 11, 31);
    const msPerDay = 24 * 60 * 60 * 1000;

    if (today > yearEnd) {
        return 0;
    }

    if (today < yearStart) {
        return Math.floor((yearEnd - yearStart) / msPerDay) + 1;
    }

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
    const msPerDay = 24 * 60 * 60 * 1000;

    if (today > monthEnd) {
        return 0;
    }

    if (today < monthStart) {
        return Math.floor((monthEnd - monthStart) / msPerDay) + 1;
    }

    return Math.floor((monthEnd - today) / msPerDay) + 1;
}

function getRemainingDaysUntilWeekEnd(referenceDate = null) {
    const baseDate = referenceDate instanceof Date ? referenceDate : getTodayDateOnly();
    const day = baseDate.getDay();
    const daysUntilSunday = day === 0 ? 0 : 7 - day;
    return daysUntilSunday + 1;
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

function formatPercent(value) {
    return num(value, 0).toLocaleString("de-DE", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
    });
}

function updateTourNameInTable(tourId, newName) {
    if (!tourTableBody) return;

    const nameCell = tourTableBody.querySelector(`td[data-tour-id="${tourId}"]`);
    if (nameCell) {
        nameCell.textContent = newName;
    }
}

function updateYearProgress(doneYear, goalYear) {
    const fillEl = document.getElementById("yearProgressBarFill");
    const percentEl = document.getElementById("yearProgressPercent");
    const goalEl = document.getElementById("yearProgressGoalKm");

    if (!fillEl || !percentEl || !goalEl) {
        return;
    }

    const goal = num(goalYear, 0);
    const done = num(doneYear, 0);
    const rawPercent = goal > 0 ? (done / goal) * 100 : 0;
    const barPercent = Math.max(0, Math.min(rawPercent, 100));

    fillEl.style.width = `${barPercent}%`;
    fillEl.setAttribute("aria-valuenow", formatPercent(rawPercent));
    percentEl.textContent = `${formatPercent(rawPercent)} %`;
    goalEl.textContent = goal.toFixed(0);
}

async function loadData() {
    try {
        const type = filterType ? filterType.value : "cycling";
        const month = filterMonth ? filterMonth.value : "";
        const year = filterYear ? filterYear.value : "";

        const respGoals = await fetch("/api/goals");
        const goalsData = await respGoals.json();
        const goals = goalsData.status === "ok" ? goalsData.goals : {};

        const respStats = await fetch(`/api/stats?type=${encodeURIComponent(type)}&month=${encodeURIComponent(month)}&year=${encodeURIComponent(year)}`);
        const stats = await respStats.json();

        const respTours = await fetch(`/api/tours?type=${encodeURIComponent(type)}&month=${encodeURIComponent(month)}&year=${encodeURIComponent(year)}`);
        const tours = await respTours.json();

        const goalYear = num(goals.goal_km_year, 0);
        const doneYear = num(stats.year_km, 0);
        document.getElementById("goalYearDone").textContent = doneYear.toFixed(0);
        document.getElementById("goalYearTotal").textContent = goalYear.toFixed(0);
        document.getElementById("goalYearRest").textContent = restText(goalYear, doneYear);
        updateYearProgress(doneYear, goalYear);

        const goalYearPerDayEl = document.getElementById("goalYearPerDay");
        if (goalYearPerDayEl) {
            const remainingYearDays = getRemainingDaysUntilYearEnd(year);
            const yearDailyKm = dailyKmNeeded(goalYear, doneYear, remainingYearDays);
            goalYearPerDayEl.textContent = formatDailyKm(yearDailyKm);
        }

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

        const monthName = monthNameFromValue(month);
        document.getElementById("statsMonthTitle").textContent = `Monat: ${monthName}`;
        document.getElementById("statsMonthKm").textContent = num(stats.month_km, 0).toFixed(1);
        document.getElementById("statsMonthCount").textContent = num(stats.month_count, 0);

        document.getElementById("statsYearTitle").textContent = `Gesamtleistung ${year}:`;
        document.getElementById("statsYearKm").textContent = num(stats.year_km, 0).toFixed(1);
        document.getElementById("statsYearCount").textContent = num(stats.year_count, 0);

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

    tours.forEach((t) => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.onclick = () => {
            window.location.href = `/tour/${t.id}`;
        };

        tr.innerHTML = `
            <td data-tour-id="${t.id}">${t.name}</td>
            <td>${t.date_display}</td>
            <td>${t.duration_hm}</td>
            <td style="text-align:right;">${num(t.distance_km, 0).toFixed(2)}</td>
        `;
        tourTableBody.appendChild(tr);
    });
}

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

if (btnImport && fileInput) {
    btnImport.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async (e) => {
        const files = e.target.files;
        await uploadGpxFiles(files);
    });
}

[filterType, filterMonth, filterYear].forEach((el) => {
    if (el) el.addEventListener("change", loadData);
});

window.addEventListener("storage", (e) => {
    if (!e) return;

    if (e.key === "goals_updated") {
        loadData();
        return;
    }

    if (e.key === "tour_name_updated" && e.newValue) {
        try {
            const payload = JSON.parse(e.newValue);
            if (payload && payload.tourId && payload.name) {
                updateTourNameInTable(payload.tourId, payload.name);
            }
        } catch (err) {
            console.error("Fehler beim Aktualisieren des Tournamens:", err);
        }
    }
});

window.addEventListener("pageshow", () => {
    loadData();
});

document.addEventListener("DOMContentLoaded", loadData);