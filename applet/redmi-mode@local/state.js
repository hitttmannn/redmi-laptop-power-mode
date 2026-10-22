/* Pure state logic, also used by tests under CJS. */
var names = {eco: 'Power saving', balanced: 'Balanced',
    performance: 'Performance', limited: 'Limited power', unknown: 'Unknown'};
// Empirical PPT pairs: original readings and a complete Fn+K cycle on AC.
// Match both limits within one range; never combine different power presets.
function classify(f, s) {
    const ranges = [
        ['eco', 28, 32, 9, 11],
        ['balanced', 43, 47, 26, 29],
        ['performance', 48, 52, 29, 32],
        ['eco', 33, 37, 18, 22],
        ['balanced', 58, 62, 48, 52],
        ['performance', 63, 67, 52, 56]
    ];
    for (let [mode, minFast, maxFast, minSlow, maxSlow] of ranges) {
        if (f >= minFast && f <= maxFast && s >= minSlow && s <= maxSlow)
            return mode;
    }
    // Observed 35/28 W while sharing a charger: describe the limits, not an OEM mode.
    if (f >= 33 && f <= 37 && s >= 26 && s <= 30) return 'limited';
    return 'unknown';
}

function decode(text, now) {
    let d;
    try { d = JSON.parse(text); } catch (_) { throw new Error('Status file is corrupted'); }
    if (!d || d.version !== 1 || typeof d.timestamp !== 'number' ||
        !Number.isFinite(d.timestamp) || now - d.timestamp > 20 || d.timestamp > now + 2)
        throw new Error('Readings are stale; check the collector');
    if (d.ok !== true) throw new Error('PPT reading failed; check the service log');
    if (![d.fast, d.slow].every(v => typeof v === 'number' && Number.isFinite(v) && v > 0 && v <= 150))
        throw new Error('Invalid PPT values');
    return {mode: classify(d.fast, d.slow), fast: d.fast, slow: d.slow};
}
