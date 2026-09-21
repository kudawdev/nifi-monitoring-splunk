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
     * @param {object} globalConfig
     * @param {string} serviceName
     * @param {object} el          the DOM node UCC gives the control
     * @param {object} modelAttributes  the form's current values
     */
    constructor(globalConfig, serviceName, el, modelAttributes) {
        this.globalConfig = globalConfig;
        this.serviceName = serviceName;
        this.el = el;
        this.model = modelAttributes;
    }

    render() {
        this.el.innerHTML = '';

        this.button = document.createElement('button');
        this.button.type = 'button';
        this.button.textContent = 'Test connection';
        this.button.className = 'btn';
        this.button.style.cssText =
            'padding:6px 14px;border:1px solid #5c6773;border-radius:3px;' +
            'background:#f2f4f5;cursor:pointer;font-size:13px;';
        this.button.addEventListener('click', () => this.run());

        this.status = document.createElement('span');
        this.status.style.cssText = 'margin-left:12px;font-size:13px;';

        this.el.appendChild(this.button);
        this.el.appendChild(this.status);
        return this;
    }

    /** The values as they are on screen right now. */
    values() {
        const model = this.model || {};
        const read = (name) => {
            const value = typeof model.get === 'function' ? model.get(name) : model[name];
            if (value === undefined || value === null) return '';
            return String(value);
        };
        const body = new URLSearchParams();
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
                `${window.$C ? window.$C.MRSPARKLE_ROOT_PATH || '' : ''}` +
                    '/splunkd/__raw/servicesNS/nobody/nifi_TA_monitoring/nifi_test_connection',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-Splunk-Form-Key': this.formKey(),
                    },
                    body: this.values(),
                },
            );
            const payload = await response.json();
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

    formKey() {
        const match = document.cookie.match(/splunkweb_csrf_token_[0-9]+=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }
}

export default TestConnection;
