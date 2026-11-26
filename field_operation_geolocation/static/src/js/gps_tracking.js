/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { Component, onWillUnmount, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// Single source of truth for the polling cadence (minutes). The server also
// returns an interval from /field_team/get_my_team; where it is available we
// use it, and everywhere else we fall back on this constant so the value is
// never hard-coded twice.
const DEFAULT_INTERVAL_MINUTES = 5;

// -------------------------------------------------------------------------
// 1. GPS SERVICE
// -------------------------------------------------------------------------
const FIELD_TEAM_GPS_SERVICE = {
    dependencies: ["notification"],

    start(env, { notification }) {
        let gpsInterval = null;
        let currentTeamId = null;
        let fallbackDeviceToken = null;
        let trackingListener = null;
        let watcherToken = 0;
        let starting = false;

        const isGeolocationSupported = () => "geolocation" in navigator;

        const notifyTrackingState = (isTracking) => {
            if (trackingListener) {
                trackingListener(isTracking);
            }
        };

        // Stable, low-entropy device identifier. Previously the whole
        // navigator.userAgent (a strong fingerprinting vector) was shipped to
        // the server on every ping. We now generate a short random token once
        // and persist it in localStorage; if storage is not usable we keep a
        // token for the current session only.
        const getDeviceId = () => {
            const storageKey = "field_operation_geolocation.device_id";
            try {
                let token = browser.localStorage.getItem(storageKey);
                if (!token) {
                    token =
                        "dev-" +
                        Math.random().toString(36).slice(2, 10) +
                        Date.now().toString(36);
                    browser.localStorage.setItem(storageKey, token);
                }
                return token;
            } catch (error) {
                if (!fallbackDeviceToken) {
                    fallbackDeviceToken =
                        "dev-" + Math.random().toString(36).slice(2, 10);
                }
                return fallbackDeviceToken;
            }
        };

        const getCurrentPosition = () => {
            return new Promise((resolve, reject) => {
                if (!isGeolocationSupported()) {
                    reject(
                        new Error(
                            _t("This browser does not support location services.")
                        )
                    );
                    return;
                }
                const options = {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0,
                };
                navigator.geolocation.getCurrentPosition(
                    resolve,
                    reject,
                    options
                );
            });
        };

        const getSignalStrength = () => {
            if ("connection" in navigator) {
                const connection = navigator.connection;
                if (connection) {
                    return connection.effectiveType === "4g" ? "4" : "3";
                }
            }
            return "3";
        };

        const sendPosition = async (teamId, position, additionalData = {}) => {
            try {
                const payload = {
                    team_id: teamId,
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    device_id: getDeviceId(),
                    signal_strength: getSignalStrength(),
                    ...additionalData,
                };

                const result = await rpc("/field_team/update_gps", payload);
                if (result && result.error) {
                    console.error("GPS update error:", result.error);
                }
                return result;
            } catch (error) {
                console.error("Failed to send GPS data:", error);
                return { error: error.message || String(error) };
            }
        };

        const stopServerTracking = async (teamId) => {
            if (!teamId) {
                return;
            }
            try {
                const result = await rpc("/field_team/stop_gps", {
                    team_id: teamId,
                });
                if (result && result.error) {
                    console.error("GPS stop error:", result.error);
                }
            } catch (error) {
                console.error("Failed to stop GPS data:", error);
            }
        };

        const onVisibilityChange = () => {
            if (document.hidden) {
                void stopGPSWatcher({ notify: false });
            }
        };

        const startGPSWatcher = async (
            teamId,
            intervalMinutes = DEFAULT_INTERVAL_MINUTES
        ) => {
            if (!isGeolocationSupported()) {
                notification.add(
                    _t("This browser does not support location services."),
                    { type: "danger" }
                );
                return false;
            }
            if (gpsInterval && currentTeamId === teamId) {
                return true;
            }

            const token = ++watcherToken;
            starting = true;
            currentTeamId = teamId;
            if (gpsInterval) {
                browser.clearInterval(gpsInterval);
                gpsInterval = null;
            }

            try {
                const position = await getCurrentPosition();
                if (token !== watcherToken) {
                    return false;
                }
                const result = await sendPosition(teamId, position, {
                    status: "working",
                });
                if (token !== watcherToken) {
                    return false;
                }
                if (result && result.error) {
                    await stopServerTracking(teamId);
                    notification.add(
                        _t(
                            "GPS tracking could not be started: %s",
                            result.error
                        ),
                        { type: "danger" }
                    );
                    currentTeamId = null;
                    notifyTrackingState(false);
                    return false;
                }

                if (document.hidden) {
                    await stopGPSWatcher({ notify: false });
                    return false;
                }
                const intervalMs = intervalMinutes * 60 * 1000;
                gpsInterval = browser.setInterval(async () => {
                    if (token !== watcherToken) {
                        return;
                    }
                    try {
                        const nextPosition = await getCurrentPosition();
                        if (token === watcherToken) {
                            await sendPosition(teamId, nextPosition);
                        }
                    } catch (error) {
                        console.error("Periodic GPS error:", error);
                    }
                }, intervalMs);
                document.addEventListener(
                    "visibilitychange",
                    onVisibilityChange
                );
                notifyTrackingState(true);
                notification.add(_t("GPS tracking started"), {
                    type: "success",
                });
                return true;
            } catch (error) {
                console.error("GPS start error:", error);
                if (token === watcherToken) {
                    currentTeamId = null;
                    notifyTrackingState(false);
                    notification.add(
                        _t(
                            "GPS tracking could not be started: %s",
                            error.message || error
                        ),
                        { type: "danger" }
                    );
                }
                return false;
            } finally {
                if (token === watcherToken) {
                    starting = false;
                }
            }
        };

        const stopGPSWatcher = async ({ notify = true } = {}) => {
            const teamId = currentTeamId;
            const wasTracking = Boolean(gpsInterval) || starting;
            ++watcherToken;
            starting = false;
            if (gpsInterval) {
                browser.clearInterval(gpsInterval);
                gpsInterval = null;
            }
            currentTeamId = null;
            document.removeEventListener(
                "visibilitychange",
                onVisibilityChange
            );
            notifyTrackingState(false);
            await stopServerTracking(teamId);
            if (notify && wasTracking) {
                notification.add(_t("GPS tracking stopped"), { type: "info" });
            }
        };

        const startMyTeamTracking = async () => {
            try {
                const teamInfo = await rpc("/field_team/get_my_team", {});
                if (teamInfo.team_id) {
                    return await startGPSWatcher(
                        teamInfo.team_id,
                        teamInfo.interval || DEFAULT_INTERVAL_MINUTES
                    );
                }
                notification.add(
                    teamInfo.error ||
                        _t("You have not been assigned to any field team."),
                    { type: "danger" }
                );
            } catch (error) {
                notification.add(
                    _t(
                        "GPS tracking could not be started: %s",
                        error.message || error
                    ),
                    { type: "danger" }
                );
            }
            return false;
        };

        return {
            startGPSWatcher,
            startMyTeamTracking,
            stopGPSWatcher,
            setTrackingListener(listener) {
                trackingListener = listener;
            },
            getTrackingStatus: () => ({ isTracking: gpsInterval !== null }),
        };
    },
};

registry.category("services").add("fieldTeamGPS", FIELD_TEAM_GPS_SERVICE);

// -------------------------------------------------------------------------
// 2. SYSTRAY
// -------------------------------------------------------------------------
class GPSSystrayItem extends Component {
    setup() {
        this.gpsService = useService("fieldTeamGPS");
        this.state = useState({ isTracking: false, color: "gray" });
        this.title = _t("Field Tracking");

        this.gpsService.setTrackingListener((isTracking) => {
            this.updateState(isTracking);
        });

        // Tracking is deliberately manual. Loading the backend must not ask for
        // geolocation permission or start sharing the worker's position.
        onWillUnmount(() => {
            this.gpsService.setTrackingListener(null);
            void this.gpsService.stopGPSWatcher({ notify: false });
        });
    }

    updateState(isTracking) {
        this.state.isTracking = isTracking;
        this.state.color = isTracking ? "#28a745" : "gray";
    }

    async onClick() {
        if (this.state.isTracking) {
            await this.gpsService.stopGPSWatcher();
        } else {
            const started = await this.gpsService.startMyTeamTracking();
            this.updateState(started);
        }
    }
}

GPSSystrayItem.template = xml`
    <div class="o_nav_entry" t-on-click="onClick" style="cursor: pointer; display: flex; align-items: center; padding: 0 10px;">
        <i class="fa fa-location-arrow fa-lg" t-attf-style="color: #{state.color};" t-att-title="title"></i>
    </div>
`;

registry.category("systray").add("field_operation_geolocation.gps_item", {
    Component: GPSSystrayItem,
});

// -------------------------------------------------------------------------
// 3. CLIENT ACTIONS
// -------------------------------------------------------------------------
registry.category("actions").add("start_gps_tracking", async (env, action) => {
    const gpsService = env.services.fieldTeamGPS;
    const teamId = action.params.team_id;

    if (teamId) {
        await gpsService.startGPSWatcher(teamId);
    } else {
        env.services.notification.add(_t("Team ID not found"), {
            type: "danger",
        });
    }

    return { type: "ir.actions.act_window_close" };
});

registry.category("actions").add("stop_gps_tracking", async (env, action) => {
    const gpsService = env.services.fieldTeamGPS;
    await gpsService.stopGPSWatcher();
    return { type: "ir.actions.act_window_close" };
});
