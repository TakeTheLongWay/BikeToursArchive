const tourTableBody = document.getElementById("tourTableBody");
const filterType = document.getElementById("filterType");
const filterMonth = document.getElementById("filterMonth");
const filterYear = document.getElementById("filterYear");

const btnImport = document.getElementById("btnImport");
const fileInput = document.getElementById("fileInput");

const deleteConfirmModal = document.getElementById("deleteConfirmModal");
const confirmDeleteYes = document.getElementById("confirmDeleteYes");
const confirmDeleteNo = document.getElementById("confirmDeleteNo");

const DELETE_ICON_SRC = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAABg0lEQVR4nO2WS0oDQRCGP/AJiiAk4NaduhEVNNE7eA69SERQ8XkVwTu4ia8TOC4FEdREw0jh39AOY6ZDOoI4PxRMV9dM/VVdVT1QokTv2AQSIM1Ior2BI8lx7uT+NwikklB9347SSPL3CMRIa9/HkpYE+P6Bftclgf9DYBe49NZXwDGwMEgCYwHDqAMcyTYqgXHgXM9vinYNmJDUgBOgJZuLUBJpIIED7zZc7PK9Je82PYxJoKPInfMtoOLZVaQzLCsTH8BcLAKpztawrXUTqEqa0tme4TQ0C2kPBFa9aJ3DZubZZaUm3U2vBPLwKptJTzedaUPfObI1/XMMAo85BKrqfff+HTDj7U9J/1REwFXsRhcbF6m1XegR1KW7LiKwEzBcnFifhxbhmdZ7RQRGRaLbn7Brw5b6vKgNV4A28B7ShqFoiEjikciDOX/whlc0DHujuKU+r6swTdaV9rY3ikfiuf/CkG5Bm3A/HZWl3SKP7tzHLLAP3AIv6nWrdiu4+az1J6qvJAJWa1coAAAAAElFTkSuQmCC";

let pendingDeleteTourId = null;

function num(val, fallback = 0) {
    const n = Number(val);
    return Number.isFinite(n) ? n : fallback;
}

function isAllMonthSelection(monthVal) {
    return String(monthVal || "").trim().toLowerCase() === "alle";
}

function monthNameFromValue(monthVal) {
    if (isAllMonthSelection(monthVal)) {
        return "Alle";
    }

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

function getDaysInYear(year) {
    const targetYear = Number(year);
    if (!Number.isInteger(targetYear)) {
        return 0;
    }

    const start = new Date(targetYear, 0, 1);
    const end = new Date(targetYear + 1, 0, 1);
    const msPerDay = 24 * 60 * 60 * 1000;

    return Math.round((end - start) / msPerDay);
}

function getElapsedDaysInYear(year) {
    const targetYear = Number(year);
    if (!Number.isInteger(targetYear)) {
        return 0;
    }

    const today = getTodayDateOnly();
    const yearStart = new Date(targetYear, 0, 1);
    const yearEnd = new Date(targetYear, 11, 31);
    const msPerDay = 24 * 60 * 60 * 1000;

    if (today < yearStart) {
        return 0;
    }

    if (today > yearEnd) {
        return getDaysInYear(targetYear);
    }

    return Math.floor((today - yearStart) / msPerDay) + 1;
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

function formatKmTwoDecimals(value) {
    return num(value, 0).toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function calculateExpectedYearKm(goalYear, year) {
    const totalGoal = num(goalYear, 0);
    const totalDays = getDaysInYear(year);
    const elapsedDays = getElapsedDaysInYear(year);

    if (totalGoal <= 0 || totalDays <= 0 || elapsedDays <= 0) {
        return 0;
    }

    return (totalGoal / totalDays) * elapsedDays;
}

function updateTourNameInTable(tourId, newName) {
    if (!tourTableBody) return;

    const nameSpan = tourTableBody.querySelector(`.tour-name-text[data-tour-id="${tourId}"]`);
    if (nameSpan) {
        nameSpan.textContent = newName;
    }
}

function updateYearProgress(doneYear, goalYear, year) {
    const fillEl = document.getElementById("yearProgressBarFill");
    const percentEl = document.getElementById("yearProgressPercent");
    const goalEl = document.getElementById("yearProgressGoalKm");
    const behindEl = document.getElementById("yearProgressBehind");

    if (!fillEl || !percentEl || !goalEl || !behindEl) {
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

    const expectedKm = calculateExpectedYearKm(goal, year);
    const behindKm = expectedKm - done;

    if (behindKm > 0.001) {
        behindEl.textContent = `${formatKmTwoDecimals(behindKm)} km hinter Soll`;
        behindEl.style.display = "block";
    } else {
        behindEl.textContent = "";
        behindEl.style.display = "none";
    }
}

function openDeleteConfirmModal(tourId) {
    if (!deleteConfirmModal) return;
    pendingDeleteTourId = tourId;
    deleteConfirmModal.hidden = false;
}

function closeDeleteConfirmModal() {
    pendingDeleteTourId = null;
    if (deleteConfirmModal) {
        deleteConfirmModal.hidden = true;
    }
}

async function deleteTour(tourId) {
    try {
        const resp = await fetch(`/api/tours/${tourId}`, {
            method: "DELETE"
        });

        let result = {};
        try {
            result = await resp.json();
        } catch (jsonError) {
            result = {};
        }

        if (!resp.ok || result.status !== "ok") {
            const msg = result.message || result.error || "Die Tour konnte nicht gelöscht werden.";
            alert(msg);
            return;
        }

        closeDeleteConfirmModal();
        await loadData();
    } catch (e) {
        console.error("Fehler beim Löschen der Tour:", e);
        alert("Die Tour konnte nicht gelöscht werden.");
    }
}

function buildTourNameCell(tour) {
    const td = document.createElement("td");

    const wrapper = document.createElement("span");
    wrapper.className = "tour-name-with-delete";

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "tour-delete-button";
    deleteButton.setAttribute("aria-label", "Tour löschen");
    deleteButton.title = "Tour löschen";

    deleteButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openDeleteConfirmModal(tour.id);
    });

    const icon = document.createElement("img");
    icon.src = DELETE_ICON_SRC;
    icon.alt = "Delete";
    icon.className = "tour-delete-icon";
    icon.draggable = false;

    const nameSpan = document.createElement("span");
    nameSpan.className = "tour-name-text";
    nameSpan.dataset.tourId = tour.id;
    nameSpan.textContent = tour.name || "";

    deleteButton.appendChild(icon);
    wrapper.appendChild(deleteButton);
    wrapper.appendChild(nameSpan);
    td.appendChild(wrapper);

    return td;
}

async function loadData() {
    try {
        const type = filterType ? filterType.value : "cycling";
        const month = filterMonth ? filterMonth.value : "";
        const year = filterYear ? filterYear.value : "";
        const allMonthsSelected = isAllMonthSelection(month);

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
        updateYearProgress(doneYear, goalYear, year);

        const goalYearPerDayEl = document.getElementById("goalYearPerDay");
        if (goalYearPerDayEl) {
            const remainingYearDays = getRemainingDaysUntilYearEnd(year);
            const yearDailyKm = dailyKmNeeded(goalYear, doneYear, remainingYearDays);
            goalYearPerDayEl.textContent = formatDailyKm(yearDailyKm);
        }

        const goalMonthTitleEl = document.getElementById("goalMonthTitle");
        if (goalMonthTitleEl) {
            goalMonthTitleEl.textContent = allMonthsSelected ? "Jahr bis heute" : "Monat";
        }

        const goalMonth = allMonthsSelected
            ? calculateExpectedYearKm(goalYear, year)
            : num(goals.monthly, 0);
        const doneMonth = num(stats.month_km, 0);

        document.getElementById("goalMonthDone").textContent = doneMonth.toFixed(0);
        document.getElementById("goalMonthTotal").textContent = goalMonth.toFixed(0);
        document.getElementById("goalMonthRest").textContent = restText(goalMonth, doneMonth);

        const goalMonthPerDayEl = document.getElementById("goalMonthPerDay");
        if (goalMonthPerDayEl) {
            if (allMonthsSelected) {
                goalMonthPerDayEl.textContent = "0,0";
            } else {
                const remainingMonthDays = getRemainingDaysUntilMonthEnd(year, month);
                const monthDailyKm = dailyKmNeeded(goalMonth, doneMonth, remainingMonthDays);
                goalMonthPerDayEl.textContent = formatDailyKm(monthDailyKm);
            }
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

        const monthName = stats.month_name || monthNameFromValue(month);
        document.getElementById("statsMonthTitle").textContent = `${monthName}:`;
        document.getElementById("statsMonthKm").textContent = num(stats.month_km, 0).toFixed(1);
        document.getElementById("statsMonthCount").textContent = num(stats.month_count, 0);

        document.getElementById("statsYearTitle").textContent = `Gesamtleistung ${year}:`;
        document.getElementById("statsYearKm").textContent = num(stats.year_km, 0).toFixed(1);
        document.getElementById("statsYearCount").textContent = num(stats.year_count, 0);

        document.getElementById("statsAllRidesKm").textContent = num(stats.all_rides_km, 0).toFixed(1);
        document.getElementById("statsAllRidesCount").textContent = num(stats.all_rides_count, 0);

        renderTours(Array.isArray(tours) ? tours : []);
    } catch (e) {
        console.error("Fehler beim Laden der Dashboard-Daten:", e);
    }
}

function renderTours(tours) {
    if (!tourTableBody) return;
    tourTableBody.innerHTML = "";

    if (tours.length === 0) {
        tourTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Keine Touren gefunden.</td></tr>';
        return;
    }

    tours.forEach((t) => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.addEventListener("click", () => {
            window.location.href = `/tour/${t.id}`;
        });

        const nameTd = buildTourNameCell(t);

        const bikeTd = document.createElement("td");
        bikeTd.textContent = t.bike_name || "n/a";

        const dateTd = document.createElement("td");
        dateTd.textContent = t.date_display || "";

        const durationTd = document.createElement("td");
        durationTd.textContent = t.duration_hm || "";

        const distanceTd = document.createElement("td");
        distanceTd.style.textAlign = "right";
        distanceTd.textContent = num(t.distance_km, 0).toFixed(2);

        tr.appendChild(nameTd);
        tr.appendChild(bikeTd);
        tr.appendChild(dateTd);
        tr.appendChild(durationTd);
        tr.appendChild(distanceTd);

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

if (confirmDeleteNo) {
    confirmDeleteNo.addEventListener("click", () => {
        closeDeleteConfirmModal();
    });
}

if (confirmDeleteYes) {
    confirmDeleteYes.addEventListener("click", async () => {
        if (!pendingDeleteTourId) {
            closeDeleteConfirmModal();
            return;
        }

        const tourId = pendingDeleteTourId;
        await deleteTour(tourId);
    });
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && deleteConfirmModal && !deleteConfirmModal.hidden) {
        closeDeleteConfirmModal();
    }
});

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