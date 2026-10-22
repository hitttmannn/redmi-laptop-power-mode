/* Pure state logic, also used by tests under CJS. */
var names = {eco: 'Экономичный', balanced: 'Сбалансированный',
    performance: 'Производительный', unknown: 'Неизвестно'};
function classify(f, s) {
    if (f >= 28 && f <= 32 && s >= 9 && s <= 11) return 'eco';
    if (f >= 43 && f <= 47 && s >= 26 && s <= 29) return 'balanced';
    if (f >= 48 && f <= 52 && s >= 29 && s <= 32) return 'performance';
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
