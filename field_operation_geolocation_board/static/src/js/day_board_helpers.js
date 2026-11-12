/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Small helpers shared by the board components.
 */

const ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
};

/** Escape a value before putting it in a Leaflet popup (HTML string). */
export function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPE_MAP[char]);
}

/** "12,4 km" with the dot decimal separator Odoo uses for this locale. */
export function formatKm(value) {
    const number = Number(value || 0);
    return `${number.toFixed(1)} km`;
}

/** A short "2 min ago" label for the last known GPS position. */
export function relativeTime(minutes) {
    if (minutes === false || minutes === undefined || minutes === null) {
        return "";
    }
    if (minutes < 1) {
        return _t("just now");
    }
    if (minutes < 60) {
        return minutes === 1 ? _t("1 min ago") : `${minutes} ${_t("min ago")}`;
    }
    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
        return hours === 1 ? _t("1 hour ago") : `${hours} ${_t("hours ago")}`;
    }
    const days = Math.floor(hours / 24);
    return days === 1 ? _t("1 day ago") : `${days} ${_t("days ago")}`;
}
