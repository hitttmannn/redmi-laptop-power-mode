const GLib = imports.gi.GLib;
const ByteArray = imports.byteArray;
const root = ARGV[0];
imports.searchPath.unshift(root + '/applet/redmi-mode@local');
const state = imports.state;
let count = 0;
function assert(v, m) { count++; if (!v) throw new Error(m); }
function throws(f) { let failed = false; try { f(); } catch (_) { failed = true; } assert(failed, 'must reject'); }
for (let [f, s, mode] of [[30,10,'eco'],[45,28,'balanced'],[50,30,'performance'],
    [28,9,'eco'],[32,11,'eco'],[43,26,'balanced'],[47,29,'balanced'],
    [48,29,'performance'],[52,32,'performance'],[45,10,'unknown'],[47.5,29,'unknown'],
    [35,20,'eco'],[60,50,'balanced'],[65,54,'performance'],
    [33,18,'eco'],[37,22,'eco'],[58,48,'balanced'],[62,52,'balanced'],
    [63,52,'performance'],[67,56,'performance'],
    [35,10,'unknown'],[30,20,'unknown'],[60,54,'unknown'],[65,50,'unknown'],
    [37.1,20,'unknown'],[60,47.9,'unknown'],[65,56.1,'unknown'],
    [35,28,'limited'],[33,26,'limited'],[37,30,'limited'],
    [32.9,28,'unknown'],[37.1,28,'unknown'],[35,25.9,'unknown'],[35,30.1,'unknown'],
    [100,80,'unknown']]) {
    assert(state.decode(JSON.stringify({version:1,timestamp:100,ok:true,fast:f,slow:s}),101).mode === mode, 'classification');
}
for (let data of [{}, null, {version:1,timestamp:50,ok:true,fast:45,slow:28},
    {version:1,timestamp:110,ok:true,fast:45,slow:28}, {version:1,timestamp:100,ok:false},
    {version:1,timestamp:100,ok:true,fast:'45',slow:28},
    {version:1,timestamp:100,ok:true,fast:0,slow:28}]) throws(() => state.decode(JSON.stringify(data),101));
throws(() => state.decode('{',101));

// Exercise the actual applet with a minimal Cinnamon surface and real Gio IO.
const Gio = imports.gi.Gio;
let loop = GLib.MainLoop.new(null, false);
let activeTimers = new Set(), removed = 0, instance;
class Base {
    constructor(...args) { this._init(...args); }
    _init() { this._menuManager = {addMenu() {}}; }
    set_applet_icon_symbolic_name(v) { this.icon = v; }
    set_applet_icon_symbolic_path(v) { this.icon = v; }
    set_applet_tooltip(v) { this.tooltip = v; }
}
class Menu {
    constructor() { this.items = []; }
    addMenuItem(item) { this.items.push(item); }
    toggle() {}
    destroy() { this.destroyed = true; }
}
class Item {
    constructor(text) { this.label = {text, set_text(v) { this.text = v; }}; }
    connect() {}
}
let temp = GLib.dir_make_tmp('redmi-test-XXXXXX');
let path = temp + '/status.json';
GLib.file_set_contents(path, JSON.stringify({version:1,timestamp:Date.now()/1000,ok:true,fast:45,slow:28}));
let mock = {
    ui: {applet: {IconApplet: Base, AppletPopupMenu: Menu}, popupMenu: {PopupMenuItem: Item}},
    gi: {GLib, Gio: {Cancellable: Gio.Cancellable, IOErrorEnum: Gio.IOErrorEnum,
        io_error_quark: Gio.io_error_quark, File: {new_for_path() {return Gio.File.new_for_path(path);}}}},
    byteArray: ByteArray, gettext: imports.gettext, state, searchPath: [],
    mainloop: {timeout_add_seconds(s, cb) {assert(s === 2, 'cheap polling'); activeTimers.add(42); return 42;},
        source_remove(id) {activeTimers.delete(id); removed++;}}
};
let source = ByteArray.toString(GLib.file_get_contents(root + '/applet/redmi-mode@local/applet.js')[1]);
Reflect.parse(source);
let factory = new Function('imports', 'require', source + '\nreturn main;')(mock, path => {
    if (path !== './state') throw new Error('unexpected module');
    return state;
});
instance = factory({path: root + '/applet/redmi-mode@local'},0,30,1);
const russian = ARGV[1] === 'ru';
assert(instance.menu.items[1].label.text === (russian ? 'Переключение: Fn+K' : 'Switch modes: Fn+K'), 'localized switch hint');
assert(instance.menu.items[2].label.text === (russian ? 'Обновить показания' : 'Refresh readings'), 'localized refresh action');
for (let [mode, en, ru] of [['eco', 'Power saving', 'Экономичный'],
    ['balanced', 'Balanced', 'Сбалансированный'], ['performance', 'Performance', 'Производительный'],
    ['unknown', 'Unknown', 'Неизвестно'], ['limited', 'Limited power', 'Ограниченная мощность']]) {
    assert(imports.gettext.dgettext('redmi-mode@local-1.0.3', state.names[mode]) === (russian ? ru : en), 'localized mode ' + mode);
}
let stage = 0;
let check = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 20, () => {
    if (instance._busy) return GLib.SOURCE_CONTINUE;
    if (stage === 0) {
        assert(instance.icon.endsWith('bars-2-symbolic.svg'), 'async read renders balanced');
        assert(instance.tooltip.startsWith(russian ? 'Сбалансированный' : 'Balanced'), 'localized tooltip mode');
        assert(instance.tooltip.includes(russian ? 'Вт' : ' W'), 'localized units');
        assert(instance.tooltip.includes(russian ? 'Оценка по лимитам' : 'Estimated from power limits'), 'localized tooltip hint');
        GLib.file_set_contents(path, JSON.stringify({version:1,timestamp:Date.now()/1000,ok:true,fast:35,slow:28}));
        instance._read(); stage++;
        return GLib.SOURCE_CONTINUE;
    }
    if (stage === 1) {
        assert(instance.icon.endsWith('bars-limited-symbolic.svg'), 'nonstandard limits have a distinct icon');
        assert(instance.tooltip.startsWith(russian ? 'Ограниченная мощность' : 'Limited power'), 'localized limited power name');
        assert(instance.tooltip.includes(russian ? 'режим Fn+K не определён' : 'Fn+K mode is not identified'), 'does not invent a firmware mode');
        assert(instance._status.label.text === instance.tooltip.split('\n')[0], 'menu agrees with limited tooltip');
        GLib.file_set_contents(path, JSON.stringify({version:1,timestamp:Date.now()/1000-30,ok:true,fast:35,slow:28}));
        instance._read(); stage++; return GLib.SOURCE_CONTINUE;
    }
    if (stage === 2) {
        assert(instance.icon === 'dialog-question', 'stale data cannot retain limited status');
        assert(instance.tooltip.includes(russian ? 'Данные устарели' : 'Readings are stale'), 'localized stale error');
        GLib.file_set_contents(path, JSON.stringify({version:1,timestamp:Date.now()/1000,ok:true,fast:65,slow:54}));
        instance._read(); stage++; return GLib.SOURCE_CONTINUE;
    }
    if (stage === 3) {
        assert(instance.icon.endsWith('bars-3-symbolic.svg'), 'normal profile recovers after power restriction');
        GLib.file_set_contents(path, '{'); instance._read(); stage++; return GLib.SOURCE_CONTINUE;
    }
    assert(instance.icon === 'dialog-question', 'corrupt read clears previous mode');
    assert(instance.tooltip.includes(russian ? 'Повреждён файл состояния' : 'Status file is corrupted'), 'localized parser error');
    GLib.unlink(path); instance._read();
    instance.on_applet_removed_from_panel();
    assert(instance._dead && instance.menu.destroyed && removed === 1 && activeTimers.size === 0, 'cleanup');
    GLib.rmdir(temp);
    loop.quit(); return GLib.SOURCE_REMOVE;
});
let watchdog = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => {throw new Error('IO test timeout');});
loop.run();
GLib.source_remove(watchdog);
print(count + ' CJS assertions passed');
