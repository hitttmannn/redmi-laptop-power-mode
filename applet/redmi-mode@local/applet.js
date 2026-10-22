const Applet = imports.ui.applet;
const PopupMenu = imports.ui.popupMenu;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const Mainloop = imports.mainloop;
const ByteArray = imports.byteArray;
const Gettext = imports.gettext;
// A new catalog name also refreshes gettext's cached misses in a running session.
const DOMAIN = 'redmi-mode@local-1.0.3';
function _(message) { return Gettext.dgettext(DOMAIN, message); }

class RedmiMode extends Applet.IconApplet {
    _init(metadata, orientation, panelHeight, instanceId) {
        super._init(orientation, panelHeight, instanceId);
        Gettext.bindtextdomain(DOMAIN, metadata.path + '/locale');
        this._state = require('./state');
        this._iconDirectory = metadata.path + "/icons/";
        this._dead = false;
        this._busy = false;
        this._cancel = new Gio.Cancellable();
        this._file = Gio.File.new_for_path('/run/redmi-mode/status.json');
        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this._menuManager.addMenu(this.menu);
        this._status = new PopupMenu.PopupMenuItem(_('Waiting for readings'), {reactive: false});
        this.menu.addMenuItem(this._status);
        this.menu.addMenuItem(new PopupMenu.PopupMenuItem(_('Switch modes: Fn+K'), {reactive: false}));
        let refresh = new PopupMenu.PopupMenuItem(_('Refresh readings'));
        refresh.connect('activate', () => this._read());
        this.menu.addMenuItem(refresh);
        this._unknown(_('The collector has not provided readings yet'));
        this._read();
        this._timer = Mainloop.timeout_add_seconds(2, () => { this._read(); return true; });
    }
    _unknown(reason) {
        this.set_applet_icon_symbolic_name('dialog-question');
        this.set_applet_tooltip(_('Redmi: unknown') + '\n' + reason);
        this._status.label.set_text(_('Unknown') + ' — ' + reason);
    }
    _read() {
        if (this._dead || this._busy) return;
        this._busy = true;
        this._file.load_contents_async(this._cancel, (file, result) => {
            this._busy = false;
            if (this._dead) return;
            try {
                let [ok, bytes] = file.load_contents_finish(result);
                if (!ok || bytes.length > 4096) throw new Error(_('Invalid status file'));
                let d = this._state.decode(ByteArray.toString(bytes), Date.now() / 1000);
                let levels = {eco: 1, balanced: 2, performance: 3};
                let detail = _(this._state.names[d.mode]) + ' — PPT Fast ' + d.fast.toFixed(1) +
                    ' / Slow ' + d.slow.toFixed(1) + ' ' + _('W');
                if (levels[d.mode])
                    this.set_applet_icon_symbolic_path(this._iconDirectory + 'bars-' + levels[d.mode] + '-symbolic.svg');
                else if (d.mode === 'limited')
                    this.set_applet_icon_symbolic_path(this._iconDirectory + 'bars-limited-symbolic.svg');
                else
                    this.set_applet_icon_symbolic_name('dialog-question');
                let hint = d.mode === 'limited'
                    ? _('Nonstandard limits; the selected Fn+K mode is not identified')
                    : _('Estimated from power limits; switch with Fn+K');
                this.set_applet_tooltip(detail + '\n' + hint);
                this._status.label.set_text(detail);
            } catch (e) {
                this._unknown(e.matches && e.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND)
                    ? _('The collector is not installed or has not started') : _(e.message));
            }
        });
    }
    on_applet_clicked() { this._read(); this.menu.toggle(); }
    on_applet_removed_from_panel() {
        this._dead = true;
        this._cancel.cancel();
        if (this._timer) Mainloop.source_remove(this._timer);
        this._timer = 0;
        this.menu.destroy();
    }
}
function main(metadata, orientation, panelHeight, instanceId) {
    return new RedmiMode(metadata, orientation, panelHeight, instanceId);
}
