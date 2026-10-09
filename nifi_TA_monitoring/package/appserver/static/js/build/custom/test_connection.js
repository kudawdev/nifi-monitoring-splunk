/*
 * The "Test connection" control on the input form.
 *
 * A custom entity rather than a validator: validation runs on save and can
 * only reject, while the point here is to answer a question before saving --
 * four things have to be right at once (URL, scheme, certificate,
 * credentials) and without this they all fail the same way, minutes later,
 * in splunkd.log.
 *
 * Plain ES module, no bundler: UCC serves this file as-is. It reads the form
 * values currently on screen, not the saved ones, so it tests what the
 * operator is about to save.
 */

const FIELDS = ['api_url', 'auth_type', 'username', 'password', 'verify_tls', 'ca_bundle'];

class TestConnection {
    /**
     * The signature UCC 6 calls a custom control with. An earlier draft took
     * (globalConfig, serviceName, el, model), which is the custom *cell*
     * signature: `el` then arrived as the second argument, render() threw
     * "this.el.appendChild is not a function", and the form showed
     * "Loading..." where the button should be, for ever.
     *
     * @param {object} globalConfig
     * @param {HTMLElement} el      the node UCC gives the control
     * @param {object} data         {value, mode, serviceName} -- this control only
     * @param {function} setValue   unused: the button holds no value
     * @param {object} util         UCC's form helpers; setState reads the form
     */
    constructor(globalConfig, el, data, setValue, util) {
        this.globalConfig = globalConfig;
        this.el = el;
        this.data = data || {};
        this.util = util || {};
    }

    render() {
        this.el.innerHTML = '';

        this.button = document.createElement('button');
        this.button.type = 'button';
        this.button.textContent = 'Test connection';
        this.button.className = 'btn';
        this.button.style.cssText =
            'padding:6px 14px;border:1px solid #5c6773;border-radius:3px;' +
            'background:#f2f4f5;color:#1a1c20;cursor:pointer;font-size:13px;';
        this.button.addEventListener('click', () => this.run());

        this.status = document.createElement('span');
        this.status.style.cssText = 'margin-left:12px;font-size:13px;';

        this.el.appendChild(this.button);
        this.el.appendChild(this.status);
        return this;
    }

    /**
     * The values as they are on screen right now.
     *
     * UCC hands a custom control only its own value. The rest of the form
     * lives in the form's React state, which the control can reach only
     * through util.setState: the updater receives that state, and returning
     * it unchanged leaves the form as it was.
     */
    formData() {
        return new Promise((resolve) => {
            if (typeof this.util.setState !== 'function') {
                resolve({});
                return;
            }
            this.util.setState((state) => {
                resolve((state && state.data) || {});
                return state;
            });
        });
    }

    async values() {
        const data = await this.formData();
        const read = (name) => {
            const entry = data[name];
            const value = entry && typeof entry === 'object' ? entry.value : entry;
            if (value === undefined || value === null) return '';
            return String(value);
        };
        const body = new URLSearchParams();
        // splunkd refuses a create without a target name ("Cannot perform
        // action POST without a target name to act on"). The handler writes
        // nothing, so any name will do.
        body.append('name', 'test');
        FIELDS.forEach((name) => body.append(name, read(name)));
        body.append('output_mode', 'json');
        return body;
    }

    say(text, ok) {
        this.status.textContent = text;
        this.status.style.color = ok === undefined ? '#5c6773' : (ok ? '#1a7f37' : '#a41e11');
    }

    async run() {
        this.button.disabled = true;
        this.say('Testing…');
        try {
            const response = await fetch(
                this.endpoint(),
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-Splunk-Form-Key': this.formKey(),
                    },
                    body: await this.values(),
                },
            );
            // A reply that is not JSON is Splunk Web's own page -- a login
            // redirect, a 404 -- and parsing it would surface as "Unexpected
            // token '<'", which says nothing about what went wrong.
            let payload = null;
            try {
                payload = await response.json();
            } catch (error) {
                this.say(`The add-on's test endpoint answered HTTP ${response.status}, `
                    + 'not a result. Reload the page and try again.', false);
                return;
            }
            const result = this.unwrap(payload);
            if (!result) {
                this.say(`The add-on answered HTTP ${response.status} without a result.`, false);
                return;
            }
            this.say(result.message, Boolean(result.success));
        } catch (error) {
            // A failure here is the browser's, not NiFi's: say so rather than
            // letting it read as "NiFi is unreachable".
            this.say(`The test could not be run: ${error.message}`, false);
        } finally {
            this.button.disabled = false;
        }
    }

    /** splunkd wraps a single-model reply in entry[0].content.result. */
    unwrap(payload) {
        try {
            const content = payload.entry[0].content;
            const raw = content.result !== undefined ? content.result : content;
            return typeof raw === 'string' ? JSON.parse(raw) : raw;
        } catch (error) {
            return null;
        }
    }

    /**
     * Splunk Web serves splunkd's REST API only under the locale prefix:
     * /en-US/splunkd/__raw/... Without it the request is redirected, the POST
     * comes back as a 405 on a GET, and the button reported a JSON parse
     * error. MRSPARKLE_ROOT_PATH covers a Splunk Web behind a root path.
     */
    endpoint() {
        const config = window.$C || {};
        const locale = config.LOCALE
            || window.location.pathname.split('/').filter(Boolean)[0]
            || 'en-US';
        return `${config.MRSPARKLE_ROOT_PATH || ''}/${locale}`
            + '/splunkd/__raw/servicesNS/nobody/nifi_TA_monitoring/nifi_test_connection';
    }

    formKey() {
        const match = document.cookie.match(/splunkweb_csrf_token_[0-9]+=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }
}

export default TestConnection;
