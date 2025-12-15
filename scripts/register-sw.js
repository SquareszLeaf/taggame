'use strict'; {
    window.C3_RegisterSW = async function C3_RegisterSW() {
        if (!navigator.serviceWorker) return;
        const params = new URLSearchParams(location.search);
        const disableSW = params.has("nosw") || params.has("disable-sw") || params.has("disableSW");
        if (disableSW) {
            try {
                const regs = await navigator.serviceWorker.getRegistrations();
                await Promise.all(regs.map(r => r.unregister()));
                console.info("Service worker disabled (URL flag).")
            } catch (err) {
                console.warn("Failed to unregister service workers: ", err)
            }
            return;
        }
        try {
            const reg = await navigator.serviceWorker.register("sw.js", {
                scope: "./"
            });
            console.info("Registered service worker on " + reg.scope)
        } catch (err) {
            console.warn("Failed to register service worker: ", err)
        }
    }
};
