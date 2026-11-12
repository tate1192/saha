/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, onMounted, onWillUnmount, useEffect, useRef } from "@odoo/owl";

import { escapeHtml, relativeTime } from "./day_board_helpers";

/**
 * The Leaflet map of the dispatcher board.
 *
 * Leaflet itself comes from the ``soft_web_map.assets_leaflet`` lazy bundle, so
 * the board reuses the same library, CSS and tile configuration as the map view
 * of the suite instead of shipping a second copy.
 *
 * Leaflet is imperative and OWL is declarative: this component owns the map
 * instance, redraws the layers whenever the props change, and exposes the two
 * camera helpers the sidebar needs (fit all / fit one team).
 */
export class DayBoardMap extends Component {
    static template = "field_operation_geolocation_board.DayBoardMap";
    static props = {
        teams: Array,
        selected: Array,
        soloId: { type: [Number, Boolean], optional: true },
        showLive: Boolean,
        tileUrl: String,
        attribution: String,
        onOpenOperation: Function,
        onReady: Function,
    };

    setup() {
        this.mapRef = useRef("map");
        this.map = null;
        this.staticLayer = null;
        this.liveLayer = null;
        this._staticSignature = "";
        onMounted(() => {
            this._initMap();
            this.props.onReady({
                fitAll: () => this.fitAll(),
                fitTeam: (teamId) => this.fitTeam(teamId),
            });
        });
        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
                this.map = null;
            }
        });
        useEffect(
            () => this._draw(),
            () => [
                this.props.teams,
                this.props.selected,
                this.props.soloId,
                this.props.showLive,
            ]
        );
    }

    // ------------------------------------------------------------------
    // Camera
    // ------------------------------------------------------------------
    get visibleTeams() {
        if (!this.map) {
            return [];
        }
        const selected = new Set(this.props.selected);
        let teams = this.props.teams.filter((team) => selected.has(team.id));
        if (this.props.soloId) {
            teams = teams.filter((team) => team.id === this.props.soloId);
        }
        return teams;
    }

    fitAll() {
        const points = [];
        for (const team of this.visibleTeams) {
            points.push(...team.geometry);
            if (this.props.showLive && team.live) {
                points.push([team.live.lat, team.live.lon]);
            }
        }
        this._fitPoints(points);
    }

    fitTeam(teamId) {
        const team = this.props.teams.find((item) => item.id === teamId);
        if (!team) {
            return;
        }
        const points = [...team.geometry];
        if (this.props.showLive && team.live) {
            points.push([team.live.lat, team.live.lon]);
        }
        this._fitPoints(points);
    }

    _fitPoints(points) {
        if (!this.map || !points.length) {
            return;
        }
        const latLngs = points.map((point) => [point[0], point[1]]);
        if (latLngs.length === 1) {
            this.map.setView(latLngs[0], 13);
            return;
        }
        this.map.fitBounds(L.latLngBounds(latLngs), { padding: [30, 30], maxZoom: 15 });
    }

    // ------------------------------------------------------------------
    // Map lifecycle and layer drawing
    // ------------------------------------------------------------------
    _initMap() {
        this.map = L.map(this.mapRef.el, {
            zoomControl: true,
            attributionControl: true,
            minZoom: 3,
        });
        L.tileLayer(this.props.tileUrl, {
            attribution: this.props.attribution,
            maxZoom: 19,
        }).addTo(this.map);
        this.map.setView([39.9, 32.85], 5); // Turkey; fitBounds takes over
        this.staticLayer = L.layerGroup().addTo(this.map);
        this.liveLayer = L.layerGroup().addTo(this.map);
        this.map.on("popupopen", (event) => this._bindPopupButtons(event));
    }

    _draw() {
        if (!this.map || !this.staticLayer || !this.liveLayer) {
            return;
        }
        // The live layer is cheap to redraw and must follow the 45s poll.
        this.liveLayer.clearLayers();
        if (this.props.showLive) {
            for (const team of this.visibleTeams) {
                if (team.live) {
                    this._drawLive(team);
                }
            }
        }
        // The static layer (route lines and stops) is only rebuilt when the
        // visible set really changed, so an open stop popup survives the poll.
        const signature = this.visibleTeams
            .map(
                (team) =>
                    `${team.id}:` +
                    team.geometry.map((point) => point.join(",")).join(";")
            )
            .join("|");
        if (signature === this._staticSignature) {
            return;
        }
        this._staticSignature = signature;
        this.staticLayer.clearLayers();
        for (const team of this.visibleTeams) {
            this._drawPolyline(team);
            this._drawStart(team);
            for (const stop of team.stops) {
                if (stop.located) {
                    this._drawStop(team, stop);
                }
            }
        }
        this.fitAll();
    }

    _drawPolyline(team) {
        if (team.geometry.length < 2) {
            return;
        }
        L.polyline(team.geometry, {
            color: team.color,
            weight: this.props.soloId ? 6 : 4,
            opacity: this.props.soloId ? 0.95 : 0.8,
            lineJoin: "round",
        }).addTo(this.staticLayer);
    }

    _drawStart(team) {
        if (team.start.lat === false) {
            return;
        }
        const marker = L.marker([team.start.lat, team.start.lon], {
            icon: this._startIcon(team),
            zIndexOffset: 500,
        }).addTo(this.staticLayer);
        const label = team.start.label
            ? `${_t("Start")}: ${team.start.label}`
            : _t("Start");
        marker.bindTooltip(escapeHtml(label), { direction: "top" });
    }

    _drawStop(team, stop) {
        const marker = L.marker([stop.lat, stop.lon], {
            icon: this._stopIcon(team, stop),
            zIndexOffset: 1000,
        }).addTo(this.staticLayer);
        marker.bindPopup(() => this._stopPopup(team, stop), {
            maxWidth: 320,
            className: "o_board_popup_wrap",
        });
    }

    _drawLive(team) {
        const marker = L.marker([team.live.lat, team.live.lon], {
            icon: this._liveIcon(team),
            zIndexOffset: 1500,
        }).addTo(this.liveLayer);
        marker.bindPopup(() => this._livePopup(team), { maxWidth: 260 });
    }

    // ------------------------------------------------------------------
    // Icons and popups (HTML strings for Leaflet)
    // ------------------------------------------------------------------
    _stopIcon(team, stop) {
        return L.divIcon({
            className: "o_board_marker",
            html:
                `<div class="o_board_stop_pin" style="--board-color:${team.color}">` +
                `<span>${stop.seq}</span></div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13],
            popupAnchor: [0, -15],
        });
    }

    _startIcon(team) {
        return L.divIcon({
            className: "o_board_marker",
            html:
                `<div class="o_board_start_pin" style="--board-color:${team.color}">` +
                '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">' +
                '<path fill="#fff" d="M12 3 3 11h3v9h5v-6h2v6h5v-9h3z"/></svg></div>',
            iconSize: [24, 24],
            iconAnchor: [12, 12],
        });
    }

    _liveIcon(team) {
        return L.divIcon({
            className: "o_board_marker",
            html:
                `<div class="o_board_live_pin" style="--board-color:${team.color}">` +
                '<span></span></div>',
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -16],
        });
    }

    _stopPopup(team, stop) {
        const parts = [
            `<div class="o_board_popup">`,
            `<div class="o_board_popup_title">${escapeHtml(stop.label)} · ${escapeHtml(
                stop.customer
            )}</div>`,
        ];
        if (stop.subject) {
            parts.push(
                `<div class="o_board_popup_subject">${escapeHtml(stop.subject)}</div>`
            );
        }
        const meta = [stop.time, stop.district, stop.leg_km ? `${stop.leg_km} km` : ""]
            .filter(Boolean)
            .map((value) => escapeHtml(value))
            .join(" · ");
        if (meta) {
            parts.push(`<div class="o_board_popup_meta">${meta}</div>`);
        }
        if (stop.address) {
            parts.push(
                `<div class="o_board_popup_address">${escapeHtml(stop.address)}</div>`
            );
        }
        if (stop.phone) {
            parts.push(
                `<div class="o_board_popup_address">${escapeHtml(stop.phone)}</div>`
            );
        }
        parts.push(
            `<div class="o_board_popup_actions">` +
                `<button type="button" class="btn btn-sm btn-primary" data-board-action="open" data-operation-id="${stop.operation_id}">${_t(
                    "Open Job"
                )}</button>` +
                `<button type="button" class="btn btn-sm btn-outline-secondary" data-board-action="route" data-lat="${stop.lat}" data-lon="${stop.lon}">${_t(
                    "Directions"
                )}</button>` +
                `</div>`,
            `</div>`
        );
        return parts.join("");
    }

    _livePopup(team) {
        const live = team.live;
        const battery =
            live.battery === false || live.battery === undefined
                ? _t("unknown")
                : `${live.battery}%`;
        return (
            `<div class="o_board_popup">` +
            `<div class="o_board_popup_title">${escapeHtml(team.name)}</div>` +
            `<div class="o_board_popup_meta">${relativeTime(
                live.minutes_ago
            )} · ${_t("Battery")}: ${escapeHtml(battery)}</div>` +
            `</div>`
        );
    }

    _bindPopupButtons(event) {
        const element = event.popup.getElement();
        if (!element) {
            return;
        }
        for (const button of element.querySelectorAll("[data-board-action]")) {
            button.addEventListener("click", () => {
                const action = button.dataset.boardAction;
                if (action === "open") {
                    this.props.onOpenOperation(Number(button.dataset.operationId));
                    this.map.closePopup();
                } else if (action === "route") {
                    // v1 will route through the user's configured provider; the
                    // public Google Maps deep link needs no key and always opens.
                    window.open(
                        `https://www.google.com/maps/dir/?api=1&destination=${button.dataset.lat},${button.dataset.lon}`,
                        "_blank",
                        "noopener,noreferrer"
                    );
                }
            });
        }
    }
}
