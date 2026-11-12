/** @odoo-module **/

import { loadBundle } from "@web/core/assets";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    Component,
    onWillStart,
    onWillUnmount,
    useState,
} from "@odoo/owl";

import { formatKm, relativeTime } from "./day_board_helpers";
import { DayBoardMap } from "./day_board_map";

//: How often the live positions are refreshed while the tab is visible.
const LIVE_REFRESH_MS = 45000;

/**
 * "Günün Rotaları" — the dispatcher map board.
 *
 * One screen answers the morning questions: which team goes where today, in
 * which order, how many stops still lack coordinates and where each team is
 * right now. The board is read only; the pencil on a team opens the existing
 * daily plan wizard on that team and day, and the list is reloaded when the
 * dialog closes.
 */
export class DayBoardAction extends Component {
    static template = "field_operation_geolocation_board.DayBoardAction";
    static components = { DayBoardMap };
    static props = { "*": true };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.mapApi = null;
        this.liveTimer = null;
        this._loadToken = 0;
        this._visibilityHandler = () => {
            if (document.hidden) {
                this._stopLivePolling();
            } else if (this.showLiveRequested) {
                this._startLivePolling();
            }
        };
        this.state = useState({
            date: luxon.DateTime.local().toISODate(),
            loaded: false,
            busy: false,
            error: false,
            teams: [],
            selected: [],
            selectionTouched: false,
            soloId: false,
            showLive: true,
            search: "",
            onlyOnline: false,
            unsavedOnly: false,
            missingOnly: false,
            unassigned: 0,
            map: { tile_url: "", attribution: "" },
            generatedAt: false,
        });
        const initialTeam = this.props.action?.params?.team_id;
        if (initialTeam) {
            this.state.soloId = initialTeam;
        }
        onWillStart(async () => {
            await loadBundle("soft_web_map.assets_leaflet");
            await this.load();
        });
        document.addEventListener("visibilitychange", this._visibilityHandler);
        onWillUnmount(() => {
            this._stopLivePolling();
            document.removeEventListener(
                "visibilitychange",
                this._visibilityHandler
            );
        });
    }

    // ------------------------------------------------------------------
    // Loading
    // ------------------------------------------------------------------
    async load() {
        const token = ++this._loadToken;
        const date = this.state.date;
        this.state.busy = true;
        this.state.error = false;
        try {
            const result = await rpc("/field_operation_geolocation_board/day_board", {
                date,
            });
            // A slower answer of an older day must never overwrite the newer one.
            if (token !== this._loadToken || date !== this.state.date) {
                return;
            }
            const ids = result.teams.map((team) => team.id);
            if (!this.state.selectionTouched) {
                this.state.selected = ids;
            } else {
                this.state.selected = this.state.selected.filter((id) =>
                    ids.includes(id)
                );
            }
            if (this.state.soloId && !ids.includes(this.state.soloId)) {
                this.state.soloId = false;
            }
            if (this.state.soloId && !this.state.selected.includes(this.state.soloId)) {
                this.state.selected = [...this.state.selected, this.state.soloId];
            }
            this.state.teams = result.teams;
            this.state.unassigned = result.unassigned;
            this.state.map = result.map;
            this.state.generatedAt = result.generated_at;
            this.state.loaded = true;
            this._startLivePolling();
        } catch (error) {
            if (token !== this._loadToken || date !== this.state.date) {
                return;
            }
            // Do not leave the previous day's teams on screen behind the error.
            this.state.teams = [];
            this.state.selected = [];
            this.state.loaded = false;
            this.state.error = error.message || String(error);
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            if (token === this._loadToken) {
                this.state.busy = false;
            }
        }
    }

    async refresh() {
        await this.load();
    }

    // ------------------------------------------------------------------
    // Date navigation
    // ------------------------------------------------------------------
    get todayIso() {
        return luxon.DateTime.local().toISODate();
    }

    get tomorrowIso() {
        return luxon.DateTime.local().plus({ days: 1 }).toISODate();
    }

    get dateLabel() {
        const day = luxon.DateTime.fromISO(this.state.date);
        return `${day.toFormat("dd LLLL yyyy")} · ${day.toFormat("cccc")}`;
    }

    shiftDay(delta) {
        this._setDate(
            luxon.DateTime.fromISO(this.state.date).plus({ days: delta }).toISODate()
        );
    }

    goToday() {
        this._setDate(this.todayIso);
    }

    goTomorrow() {
        this._setDate(this.tomorrowIso);
    }

    onDateInput(event) {
        const value = event.target.value;
        if (value) {
            this._setDate(value);
        }
    }

    _setDate(date) {
        if (!date || date === this.state.date) {
            return;
        }
        this.state.date = date;
        this.state.selected = [];
        this.state.selectionTouched = false;
        this.state.soloId = false;
        this.state.generatedAt = false;
        this.load();
    }

    // ------------------------------------------------------------------
    // Selection and filters
    // ------------------------------------------------------------------
    get selectedTeams() {
        const selected = new Set(this.state.selected);
        return this.state.teams.filter((team) => selected.has(team.id));
    }

    get filteredTeams() {
        return this.state.teams.filter((team) => this._matchesFilters(team));
    }

    get totals() {
        const totals = {
            teams: this.selectedTeams.length,
            stops: 0,
            km: 0,
            missing: 0,
            unsaved: 0,
            online: 0,
        };
        for (const team of this.selectedTeams) {
            totals.stops += team.stops_total;
            totals.km += team.total_km;
            totals.missing += team.stops_missing;
            totals.unsaved += team.stops_total && !team.route_saved ? 1 : 0;
            totals.online += team.live && team.live.online ? 1 : 0;
        }
        return totals;
    }

    get hasStartFallback() {
        return this.selectedTeams.some((team) => team.start_fallback);
    }

    get kpis() {
        const totals = this.totals;
        return [
            { key: "teams", label: _t("team"), value: totals.teams },
            { key: "stops", label: _t("stops"), value: totals.stops },
            { key: "km", label: _t("km"), value: totals.km.toFixed(0) },
            {
                key: "missing",
                label: _t("missing"),
                value: totals.missing,
                warning: totals.missing > 0,
            },
        ];
    }

    get showLiveRequested() {
        return this.state.showLive && this.state.date === this.todayIso;
    }

    get legendTeams() {
        return this.selectedTeams.slice(0, 8);
    }

    isSelected(teamId) {
        return this.state.selected.includes(teamId);
    }

    toggleTeam(teamId) {
        this.state.selectionTouched = true;
        if (this.isSelected(teamId)) {
            this.state.selected = this.state.selected.filter((id) => id !== teamId);
            if (this.state.soloId === teamId) {
                this.state.soloId = false;
            }
        } else {
            this.state.selected = [...this.state.selected, teamId];
        }
    }

    selectAll() {
        this.state.selectionTouched = true;
        this.state.selected = this.state.teams.map((team) => team.id);
    }

    clearAll() {
        this.state.selectionTouched = true;
        this.state.selected = [];
        this.state.soloId = false;
    }

    toggleSolo(teamId) {
        if (this.state.soloId === teamId) {
            this.state.soloId = false;
            return;
        }
        if (!this.isSelected(teamId)) {
            this.state.selected = [...this.state.selected, teamId];
        }
        this.state.soloId = teamId;
        this.fitTeam(teamId);
    }

    toggleLive(event) {
        this.state.showLive = event.target.checked;
        this._startLivePolling();
    }

    toggleFilter(key) {
        this.state[key] = !this.state[key];
    }

    _matchesFilters(team) {
        const search = this.state.search.trim().toLocaleLowerCase();
        if (search) {
            const haystack = `${team.name} ${team.region}`.toLocaleLowerCase();
            if (!haystack.includes(search)) {
                return false;
            }
        }
        if (this.state.onlyOnline && !(team.live && team.live.online)) {
            return false;
        }
        if (this.state.unsavedOnly && (!team.stops_total || team.route_saved)) {
            return false;
        }
        if (this.state.missingOnly && !team.stops_missing) {
            return false;
        }
        return true;
    }

    teamSummary(team) {
        const parts = [`${team.stops_total} ${_t("stops")}`];
        if (team.total_km) {
            parts.push(formatKm(team.total_km));
        }
        if (team.live) {
            parts.push(relativeTime(team.live.minutes_ago));
        } else if (team.stops_total) {
            parts.push(_t("no position"));
        }
        return parts.join(" · ");
    }

    // ------------------------------------------------------------------
    // Labels
    // ------------------------------------------------------------------
    get labels() {
        return {
            today: _t("Today"),
            tomorrow: _t("Tomorrow"),
            live: _t("Live tracking"),
            refresh: _t("Refresh"),
            loading: _t("Loading…"),
            empty: _t("No team or route to show for this day."),
            teams: _t("Teams"),
            selectAll: _t("Select all"),
            clearAll: _t("Clear"),
            onlyOnline: _t("Online only"),
            unsavedOnly: _t("Route not saved"),
            missingOnly: _t("Missing coordinates"),
            searchPlaceholder: _t("Search team…"),
            unsaved: _t("route not saved"),
            missingShort: _t("missing"),
            noTeams: _t("No team matches the filter."),
            selected: _t("Selected"),
            stops: _t("stops"),
            team: _t("team"),
            unassigned: _t("unassigned jobs"),
            fitAll: _t("Fit all"),
            airDistance: _t("(as the crow flies)"),
            updatedAt: _t("Updated:"),
            liveOn: _t("Live tracking on"),
            showOnMap: _t("Show on map"),
            openPlan: _t("Open plan"),
            previousDay: _t("Previous day"),
            nextDay: _t("Next day"),
            noStart: _t("no start point"),
        };
    }

    get kmLabel() {
        return formatKm(this.totals.km);
    }

    onSearchInput(event) {
        this.state.search = event.target.value;
    }

    // ------------------------------------------------------------------
    // Map camera and actions
    // ------------------------------------------------------------------
    onMapReady(api) {
        this.mapApi = api;
    }

    fitAll() {
        if (this.mapApi) {
            this.mapApi.fitAll();
        }
    }

    fitTeam(teamId) {
        // The eye on a team that is currently filtered out must still work: it
        // selects the team (so the route is drawn) and centres the camera.
        if (!this.isSelected(teamId)) {
            this.state.selected = [...this.state.selected, teamId];
        }
        if (this.mapApi) {
            this.mapApi.fitTeam(teamId);
        }
    }

    async openPlan(teamId) {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Route Plan"),
                res_model: "field.operation.route.plan",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: { default_team_id: teamId, default_date: this.state.date },
            },
            // doAction resolves when the dialog mounts, not when it closes:
            // reload only after the dispatcher saved/closed the plan.
            { onClose: () => this.load() }
        );
    }

    openOperation(operationId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "field.operation",
            res_id: operationId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ------------------------------------------------------------------
    // Live positions
    // ------------------------------------------------------------------
    _startLivePolling() {
        this._stopLivePolling();
        if (!this.showLiveRequested) {
            return;
        }
        this.liveTimer = browser.setInterval(
            () => this._refreshLivePositions(),
            LIVE_REFRESH_MS
        );
    }

    _stopLivePolling() {
        if (this.liveTimer) {
            browser.clearInterval(this.liveTimer);
            this.liveTimer = null;
        }
    }

    async _refreshLivePositions() {
        if (document.hidden) {
            return;
        }
        const date = this.state.date;
        const token = this._loadToken;
        try {
            const result = await rpc("/field_operation_geolocation_board/live", {
                team_ids: this.state.teams.map((team) => team.id),
            });
            if (token !== this._loadToken || date !== this.state.date) {
                return;
            }
            this.state.teams = this.state.teams.map((team) => ({
                ...team,
                live: result.teams[team.id] || false,
            }));
        } catch {
            // A failed poll must not disturb the board; the next tick retries.
        }
    }

    get lastRefreshLabel() {
        if (!this.state.generatedAt) {
            return "";
        }
        try {
            const value = this.state.generatedAt.replace(" ", "T");
            const local = luxon.DateTime.fromISO(`${value}Z`).toLocal();
            return local.toFormat("HH:mm");
        } catch {
            return "";
        }
    }
}

registry
    .category("actions")
    .add("field_operation_geolocation_board.day_board", DayBoardAction);
