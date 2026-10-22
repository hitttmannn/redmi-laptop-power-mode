/* Pure state logic, also used by tests under CJS. */
var names = {eco: 'Экономичный', balanced: 'Сбалансированный',
    performance: 'Производительный', unknown: 'Неизвестно'};
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
    return 'unknown';
}

function decode(text, now) {
    let d;
    try { d = JSON.parse(text); } catch (_) { throw new Error('Повреждён файл состояния'); }
    if (!d || d.version !== 1 || typeof d.timestamp !== 'number' ||
        !Number.isFinite(d.timestamp) || now - d.timestamp > 20 || d.timestamp > now + 2)
        throw new Error('Данные устарели; проверьте сборщик');
    if (d.ok !== true) throw new Error('Сборщик не получил PPT; проверьте журнал службы');
    if (![d.fast, d.slow].every(v => typeof v === 'number' && Number.isFinite(v) && v > 0 && v <= 150))
        throw new Error('Некорректные значения PPT');
    return {mode: classify(d.fast, d.slow), fast: d.fast, slow: d.slow};
}
