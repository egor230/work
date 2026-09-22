/** @function */
var createElement = (tag, options = {}) => {
    var element = document.createElement(tag);

    if (options.className) {
        element.className = options.className;
    }
    if (options.style) {
        element.style.cssText = options.style;
    }

    if (options.textContent) {
        element.textContent = options.textContent;
    } else if (options.children) {
        if (options.children instanceof HTMLElement) {
            element.append(options.children);
        } else if (typeof options.children[Symbol.iterator] === 'function') {
            for (var child of options.children) element.append(child);
        }
    }
    if (options.properties) {
        for (let property in options.properties) {
            element[property] = options.properties[property];
        }
    }

    return element;
};


/** @function */
var getTranslation = async (videoId) => {
    try {
        var response = await fetch('https://www.youtube.com/watch?v=' + videoId);
        var text = await response.text();

        var jsonString = text.match(/\"captions\"\:([\s\S]+?)\,"videoDetails/)?.[1];
        if (!jsonString) return null;

        jsonString = jsonString.replace('\n', '');

        return JSON.parse(jsonString)?.playerCaptionsTracklistRenderer;
    } catch (x) {
        return null;
    }
};


/** @function */
var decodeHtmlEntities = (() => {
    var textarea = document.createElement("textarea");

    return (text) => {
        textarea.innerHTML = text;
        return textarea.value;
    }
})();


var getYtVariables = () => new Promise(resolve => {
    var listener = (event) => {
        if (event.source === window && event.data?.type === 'put yt data') {
            var {clientVersion, device} = event.data.value;

            window.removeEventListener('message', listener);
            resolve({clientVersion, device});
        }
    };

    window.addEventListener('message', listener);

    window.postMessage({'type': "get yt data"}, '*');
});


/** @function */
var getEnchantedUrl = (() => {
    var extraString = '';
    var clientVersion = '';

    return async (url) => {
        if (!extraString && !clientVersion) {
            try {
                var data = await getYtVariables();

                extraString = data.device;
                clientVersion = data.clientVersion;
            } catch (x) {
            }
        }


        var urlObject = new URL(url + '&' + extraString);
        urlObject.searchParams.set('fmt', 'json3');
        urlObject.searchParams.set('xorb', '2');
        urlObject.searchParams.set('xobt', '3');
        urlObject.searchParams.set('xovt', '3');
        urlObject.searchParams.set('c', 'Web');
        urlObject.searchParams.set('cplayer', 'UNIPLAYER');
        urlObject.searchParams.set('cver', clientVersion);

        urlObject.searchParams.delete('ceng');
        urlObject.searchParams.delete('cengver');

        return urlObject.toString();
    };
})();


/** @function */
var requestTranslationTextTry = async (url) => {
    var response = await fetch(url);
    var json = await response.json();

    if (!Array.isArray(json.events) || !json.events.length) throw new Error('Empty data');

    var allEmpty = true;
    for (const item of json.events) {
        if (!Array.isArray(item.segs) || item.segs.length === 0) continue;

        for (const seg of item.segs) {
            if (seg.utf8 && seg.utf8.trim()) {
                allEmpty = false;
                break;
            }
        }
        if (!allEmpty) break;
    }

    if (allEmpty) throw new Error('Empty data');

    return json.events;
};


var requestTranslationText = (url) => {
    var broken = false;

    var promise = (async () => {
        try {
            return await requestTranslationTextTry(url);
        } catch (error) {
        }
        if (broken) return;

        await new Promise(resolve => {
            setTimeout(resolve, 5000);
        });

        try {
            return await requestTranslationTextTry(url);
        } catch (error) {
        }

        if (broken) return;

        await new Promise(resolve => {
            setTimeout(resolve, 10000);
        });

        try {
            return await requestTranslationTextTry(url);
        } catch (error) {
            throw new Error('Request failed');
        }
    })();

    return {
        promise,
        'cancel': () => {
            broken = true;
        }
    };
};


/** @function */
var getDefaultLanguage = async (language) => {
    var data = await chrome.storage.local.get(['defaultLanguage']);

    return data.defaultLanguage;
};


/** @function */
var saveDefaultLanguage = (language) => {
    return chrome.storage.local.set({'defaultLanguage': language});
};


/** @function */
var tracksToBaseUrlByLanguage = (tracks, language) => {
    var track = tracks
        .filter(({kind}) => kind !== 'asr')
        .find(({languageCode}) => languageCode === language);
    track ||= tracks
        .filter(({kind}) => kind === 'asr')
        .find(({languageCode}) => languageCode === language);

    if (track) return track.baseUrl;

    var enTracks = tracks.filter(({languageCode}) => languageCode === 'en');

    var baseUrl = enTracks.find(({kind}) => kind !== 'asr')?.baseUrl;
    baseUrl ||= enTracks.find(({kind}) => kind === 'asr')?.baseUrl;
    baseUrl ||= tracks[0]?.baseUrl;

    var urlObject = new URL(baseUrl);
    urlObject.searchParams.set('tlang', language);

    return urlObject.toString();
};


/** @function */
var adaptTranslationData = (events) => {
    var objects = [];
    for (const item of events) {
        if (!Array.isArray(item.segs) || item.segs.length === 0) continue;

        let segments = new Set();
        for (const seg of item.segs) {
            if (seg.utf8 && seg.utf8.trim()) segments.add(seg.utf8);
        }
        if (!segments.size) continue;

        let text = '';
        for (const part of segments) text += part;

        objects.push({
            'start': item.tStartMs / 1000,
            'duration': item.dDurationMs / 1000,
            'text': text
        });
    }

    const o = [];
    let i = 0;
    let a = [],
        s = 0,
        l = 0,
        u = {},
        c = {};

    var d = () => {
        i = 0;
        a = [];
        s = 0;
        l = 0;
        u = {};
    };

    Array.from(objects).forEach(((e, t, n) => {
        c.start && c.text && (u.start = c.start, a.push(c.text), c = {});
        0 == i && (u.start = c.start ? c.start : e.start);
        i++;

        const r = Math.round(u.start);
        const f = Math.round(e.start);
        if (l = f - r, s += e.text.length, a.push(e.text), t == n.length - 1) {
            u.text = a.join(" ").replace(/\n/g, " "), o.push(u), d();
            return;
        }
        if (l > 60000) {
            u.text = a.join(" ").replace(/\n/g, " "), o.push(u), d();
            return;
        }

        if (s > 300) {
            if (s < 500) {
                if (e.text.includes(".")) {
                    const t = e.text.split(".");
                    if ("" === t[t.length - 1].replace(/\s+/g, "")) {
                        u.text = a.join(" ").replace(/\n/g, " "), o.push(u), d();
                        return;
                    }
                    const n = t[t.length - 2],
                        r = e.text.indexOf(n) + n.length + 1,
                        i = e.text.substring(0, r);

                    c.text = e.text.substring(r), c.start = e.start, a.splice(a.length - 1, 1, i), u.text = a.join(" ").replace(/\n/g, " "), o.push(u), d();
                    return;
                }
                return;
            }

            u.text = a.join(" ").replace(/\n/g, " ");
            o.push(u);
            d()
        }
    }));

    return o;
};


var prmsElement = new Promise((resolve) => {
    var element = document.querySelector('#secondary.style-scope.ytd-watch-flexy');
    if (element) {
        resolve(element);
        return;
    }


    if (!element) {
        var observer = new MutationObserver(() => {
            var foundElement = document.querySelector('#secondary.style-scope.ytd-watch-flexy');
            if (foundElement) {
                observer.disconnect();
                resolve(foundElement);
            }
        });

        observer.observe(document.body, {childList: true, subtree: true});
    }
});

prmsElement.then(async (parent) => {
    // Custom elements polyfill
    (function () {
        'use strict';
        var n = window.Document.prototype.createElement, p = window.Document.prototype.createElementNS,
            aa = window.Document.prototype.importNode, ba = window.Document.prototype.prepend,
            ca = window.Document.prototype.append, da = window.DocumentFragment.prototype.prepend,
            ea = window.DocumentFragment.prototype.append, q = window.Node.prototype.cloneNode,
            r = window.Node.prototype.appendChild, t = window.Node.prototype.insertBefore,
            u = window.Node.prototype.removeChild, v = window.Node.prototype.replaceChild,
            w = Object.getOwnPropertyDescriptor(window.Node.prototype, "textContent"),
            y = window.Element.prototype.attachShadow,
            z = Object.getOwnPropertyDescriptor(window.Element.prototype, "innerHTML"),
            A = window.Element.prototype.getAttribute, B = window.Element.prototype.setAttribute,
            C = window.Element.prototype.removeAttribute, D = window.Element.prototype.toggleAttribute,
            E = window.Element.prototype.getAttributeNS, F = window.Element.prototype.setAttributeNS,
            G = window.Element.prototype.removeAttributeNS, H = window.Element.prototype.insertAdjacentElement,
            fa = window.Element.prototype.insertAdjacentHTML, ha = window.Element.prototype.prepend,
            ia = window.Element.prototype.append, ja = window.Element.prototype.before,
            ka = window.Element.prototype.after, la = window.Element.prototype.replaceWith,
            ma = window.Element.prototype.remove, na = window.HTMLElement,
            I = Object.getOwnPropertyDescriptor(window.HTMLElement.prototype, "innerHTML"),
            oa = window.HTMLElement.prototype.insertAdjacentElement,
            pa = window.HTMLElement.prototype.insertAdjacentHTML;
        var qa = new Set;
        "annotation-xml color-profile font-face font-face-src font-face-uri font-face-format font-face-name missing-glyph".split(" ").forEach(function (a) {
            return qa.add(a)
        });

        function ra(a) {
            var b = qa.has(a);
            a = /^[a-z][.0-9_a-z]*-[-.0-9_a-z]*$/.test(a);
            return !b && a
        }

        var sa = document.contains ? document.contains.bind(document) : document.documentElement.contains.bind(document.documentElement);

        function J(a) {
            var b = a.isConnected;
            if (void 0 !== b) return b;
            if (sa(a)) return !0;
            for (; a && !(a.__CE_isImportDocument || a instanceof Document);) a = a.parentNode || (window.ShadowRoot && a instanceof ShadowRoot ? a.host : void 0);
            return !(!a || !(a.__CE_isImportDocument || a instanceof Document))
        }

        function K(a) {
            var b = a.children;
            if (b) return Array.prototype.slice.call(b);
            b = [];
            for (a = a.firstChild; a; a = a.nextSibling) a.nodeType === Node.ELEMENT_NODE && b.push(a);
            return b
        }

        function L(a, b) {
            for (; b && b !== a && !b.nextSibling;) b = b.parentNode;
            return b && b !== a ? b.nextSibling : null
        }

        function M(a, b, d) {
            for (var f = a; f;) {
                if (f.nodeType === Node.ELEMENT_NODE) {
                    var c = f;
                    b(c);
                    var e = c.localName;
                    if ("link" === e && "import" === c.getAttribute("rel")) {
                        f = c.import;
                        void 0 === d && (d = new Set);
                        if (f instanceof Node && !d.has(f)) for (d.add(f), f = f.firstChild; f; f = f.nextSibling) M(f, b, d);
                        f = L(a, c);
                        continue
                    } else if ("template" === e) {
                        f = L(a, c);
                        continue
                    }
                    if (c = c.__CE_shadowRoot) for (c = c.firstChild; c; c = c.nextSibling) M(c, b, d)
                }
                f = f.firstChild ? f.firstChild : L(a, f)
            }
        };

        function N() {
            var a = !(null === O || void 0 === O || !O.noDocumentConstructionObserver),
                b = !(null === O || void 0 === O || !O.shadyDomFastWalk);
            this.m = [];
            this.g = [];
            this.j = !1;
            this.shadyDomFastWalk = b;
            this.I = !a
        }

        function P(a, b, d, f) {
            var c = window.ShadyDOM;
            if (a.shadyDomFastWalk && c && c.inUse) {
                if (b.nodeType === Node.ELEMENT_NODE && d(b), b.querySelectorAll) for (a = c.nativeMethods.querySelectorAll.call(b, "*"), b = 0; b < a.length; b++) d(a[b])
            } else M(b, d, f)
        }

        function ta(a, b) {
            a.j = !0;
            a.m.push(b)
        }

        function ua(a, b) {
            a.j = !0;
            a.g.push(b)
        }

        function Q(a, b) {
            a.j && P(a, b, function (d) {
                return R(a, d)
            })
        }

        function R(a, b) {
            if (a.j && !b.__CE_patched) {
                b.__CE_patched = !0;
                for (var d = 0; d < a.m.length; d++) a.m[d](b);
                for (d = 0; d < a.g.length; d++) a.g[d](b)
            }
        }

        function S(a, b) {
            var d = [];
            P(a, b, function (c) {
                return d.push(c)
            });
            for (b = 0; b < d.length; b++) {
                var f = d[b];
                1 === f.__CE_state ? a.connectedCallback(f) : T(a, f)
            }
        }

        function U(a, b) {
            var d = [];
            P(a, b, function (c) {
                return d.push(c)
            });
            for (b = 0; b < d.length; b++) {
                var f = d[b];
                1 === f.__CE_state && a.disconnectedCallback(f)
            }
        }

        function V(a, b, d) {
            d = void 0 === d ? {} : d;
            var f = d.J, c = d.upgrade || function (g) {
                return T(a, g)
            }, e = [];
            P(a, b, function (g) {
                a.j && R(a, g);
                if ("link" === g.localName && "import" === g.getAttribute("rel")) {
                    var h = g.import;
                    h instanceof Node && (h.__CE_isImportDocument = !0, h.__CE_registry = document.__CE_registry);
                    h && "complete" === h.readyState ? h.__CE_documentLoadHandled = !0 : g.addEventListener("load", function () {
                        var k = g.import;
                        if (!k.__CE_documentLoadHandled) {
                            k.__CE_documentLoadHandled = !0;
                            var l = new Set;
                            f && (f.forEach(function (m) {
                                return l.add(m)
                            }), l.delete(k));
                            V(a, k, {J: l, upgrade: c})
                        }
                    })
                } else e.push(g)
            }, f);
            for (b = 0; b < e.length; b++) c(e[b])
        }

        function T(a, b) {
            try {
                var d = b.ownerDocument, f = d.__CE_registry;
                var c = f && (d.defaultView || d.__CE_isImportDocument) ? W(f, b.localName) : void 0;
                if (c && void 0 === b.__CE_state) {
                    c.constructionStack.push(b);
                    try {
                        try {
                            if (new c.constructorFunction !== b) throw Error("The custom element constructor did not produce the element being upgraded.");
                        } finally {
                            c.constructionStack.pop()
                        }
                    } catch (k) {
                        throw b.__CE_state = 2, k;
                    }
                    b.__CE_state = 1;
                    b.__CE_definition = c;
                    if (c.attributeChangedCallback && b.hasAttributes()) {
                        var e = c.observedAttributes;
                        for (c = 0; c < e.length; c++) {
                            var g = e[c], h = b.getAttribute(g);
                            null !== h && a.attributeChangedCallback(b, g, null, h, null)
                        }
                    }
                    J(b) && a.connectedCallback(b)
                }
            } catch (k) {
                X(k)
            }
        }

        N.prototype.connectedCallback = function (a) {
            var b = a.__CE_definition;
            if (b.connectedCallback) try {
                b.connectedCallback.call(a)
            } catch (d) {
                X(d)
            }
        };
        N.prototype.disconnectedCallback = function (a) {
            var b = a.__CE_definition;
            if (b.disconnectedCallback) try {
                b.disconnectedCallback.call(a)
            } catch (d) {
                X(d)
            }
        };
        N.prototype.attributeChangedCallback = function (a, b, d, f, c) {
            var e = a.__CE_definition;
            if (e.attributeChangedCallback && -1 < e.observedAttributes.indexOf(b)) try {
                e.attributeChangedCallback.call(a, b, d, f, c)
            } catch (g) {
                X(g)
            }
        };

        function va(a, b, d, f) {
            var c = b.__CE_registry;
            if (c && (null === f || "http://www.w3.org/1999/xhtml" === f) && (c = W(c, d))) try {
                var e = new c.constructorFunction;
                if (void 0 === e.__CE_state || void 0 === e.__CE_definition) throw Error("Failed to construct '" + d + "': The returned value was not constructed with the HTMLElement constructor.");
                if ("http://www.w3.org/1999/xhtml" !== e.namespaceURI) throw Error("Failed to construct '" + d + "': The constructed element's namespace must be the HTML namespace.");
                if (e.hasAttributes()) throw Error("Failed to construct '" + d + "': The constructed element must not have any attributes.");
                if (null !== e.firstChild) throw Error("Failed to construct '" + d + "': The constructed element must not have any children.");
                if (null !== e.parentNode) throw Error("Failed to construct '" + d + "': The constructed element must not have a parent node.");
                if (e.ownerDocument !== b) throw Error("Failed to construct '" + d + "': The constructed element's owner document is incorrect.");
                if (e.localName !== d) throw Error("Failed to construct '" + d + "': The constructed element's local name is incorrect.");
                return e
            } catch (g) {
                return X(g), b = null === f ? n.call(b, d) : p.call(b, f, d), Object.setPrototypeOf(b, HTMLUnknownElement.prototype), b.__CE_state = 2, b.__CE_definition = void 0, R(a, b), b
            }
            b = null === f ? n.call(b, d) : p.call(b, f, d);
            R(a, b);
            return b
        }

        function X(a) {
            var b = "", d = "", f = 0, c = 0;
            a instanceof Error ? (b = a.message, d = a.sourceURL || a.fileName || "", f = a.line || a.lineNumber || 0, c = a.column || a.columnNumber || 0) : b = "Uncaught " + String(a);
            var e = void 0;
            void 0 === ErrorEvent.prototype.initErrorEvent ? e = new ErrorEvent("error", {
                cancelable: !0,
                message: b,
                filename: d,
                lineno: f,
                colno: c,
                error: a
            }) : (e = document.createEvent("ErrorEvent"), e.initErrorEvent("error", !1, !0, b, d, f), e.preventDefault = function () {
                Object.defineProperty(this, "defaultPrevented", {
                    configurable: !0, get: function () {
                        return !0
                    }
                })
            });
            void 0 === e.error && Object.defineProperty(e, "error", {
                configurable: !0,
                enumerable: !0,
                get: function () {
                    return a
                }
            });
            window.dispatchEvent(e);
            e.defaultPrevented || console.error(a)
        };

        function wa() {
            var a = this;
            this.g = void 0;
            this.F = new Promise(function (b) {
                a.l = b
            })
        }

        wa.prototype.resolve = function (a) {
            if (this.g) throw Error("Already resolved.");
            this.g = a;
            this.l(a)
        };

        function xa(a) {
            var b = document;
            this.l = void 0;
            this.h = a;
            this.g = b;
            V(this.h, this.g);
            "loading" === this.g.readyState && (this.l = new MutationObserver(this.G.bind(this)), this.l.observe(this.g, {
                childList: !0,
                subtree: !0
            }))
        }

        function ya(a) {
            a.l && a.l.disconnect()
        }

        xa.prototype.G = function (a) {
            var b = this.g.readyState;
            "interactive" !== b && "complete" !== b || ya(this);
            for (b = 0; b < a.length; b++) for (var d = a[b].addedNodes, f = 0; f < d.length; f++) V(this.h, d[f])
        };

        function Y(a) {
            this.s = new Map;
            this.u = new Map;
            this.C = new Map;
            this.A = !1;
            this.B = new Map;
            this.o = function (b) {
                return b()
            };
            this.i = !1;
            this.v = [];
            this.h = a;
            this.D = a.I ? new xa(a) : void 0
        }

        Y.prototype.H = function (a, b) {
            var d = this;
            if (!(b instanceof Function)) throw new TypeError("Custom element constructor getters must be functions.");
            za(this, a);
            this.s.set(a, b);
            this.v.push(a);
            this.i || (this.i = !0, this.o(function () {
                return Aa(d)
            }))
        };
        Y.prototype.define = function (a, b) {
            var d = this;
            if (!(b instanceof Function)) throw new TypeError("Custom element constructors must be functions.");
            za(this, a);
            Ba(this, a, b);
            this.v.push(a);
            this.i || (this.i = !0, this.o(function () {
                return Aa(d)
            }))
        };

        function za(a, b) {
            if (!ra(b)) throw new SyntaxError("The element name '" + b + "' is not valid.");
            if (W(a, b)) throw Error("A custom element with name '" + (b + "' has already been defined."));
            if (a.A) throw Error("A custom element is already being defined.");
        }

        function Ba(a, b, d) {
            a.A = !0;
            var f;
            try {
                var c = d.prototype;
                if (!(c instanceof Object)) throw new TypeError("The custom element constructor's prototype is not an object.");
                var e = function (m) {
                    var x = c[m];
                    if (void 0 !== x && !(x instanceof Function)) throw Error("The '" + m + "' callback must be a function.");
                    return x
                };
                var g = e("connectedCallback");
                var h = e("disconnectedCallback");
                var k = e("adoptedCallback");
                var l = (f = e("attributeChangedCallback")) && d.observedAttributes || []
            } catch (m) {
                throw m;
            } finally {
                a.A = !1
            }
            d = {
                localName: b,
                constructorFunction: d,
                connectedCallback: g,
                disconnectedCallback: h,
                adoptedCallback: k,
                attributeChangedCallback: f,
                observedAttributes: l,
                constructionStack: []
            };
            a.u.set(b, d);
            a.C.set(d.constructorFunction, d);
            return d
        }

        Y.prototype.upgrade = function (a) {
            V(this.h, a)
        };

        function Aa(a) {
            if (!1 !== a.i) {
                a.i = !1;
                for (var b = [], d = a.v, f = new Map, c = 0; c < d.length; c++) f.set(d[c], []);
                V(a.h, document, {
                    upgrade: function (k) {
                        if (void 0 === k.__CE_state) {
                            var l = k.localName, m = f.get(l);
                            m ? m.push(k) : a.u.has(l) && b.push(k)
                        }
                    }
                });
                for (c = 0; c < b.length; c++) T(a.h, b[c]);
                for (c = 0; c < d.length; c++) {
                    for (var e = d[c], g = f.get(e), h = 0; h < g.length; h++) T(a.h, g[h]);
                    (e = a.B.get(e)) && e.resolve(void 0)
                }
                d.length = 0
            }
        }

        Y.prototype.get = function (a) {
            if (a = W(this, a)) return a.constructorFunction
        };
        Y.prototype.whenDefined = function (a) {
            if (!ra(a)) return Promise.reject(new SyntaxError("'" + a + "' is not a valid custom element name."));
            var b = this.B.get(a);
            if (b) return b.F;
            b = new wa;
            this.B.set(a, b);
            var d = this.u.has(a) || this.s.has(a);
            a = -1 === this.v.indexOf(a);
            d && a && b.resolve(void 0);
            return b.F
        };
        Y.prototype.polyfillWrapFlushCallback = function (a) {
            this.D && ya(this.D);
            var b = this.o;
            this.o = function (d) {
                return a(function () {
                    return b(d)
                })
            }
        };

        function W(a, b) {
            var d = a.u.get(b);
            if (d) return d;
            if (d = a.s.get(b)) {
                a.s.delete(b);
                try {
                    return Ba(a, b, d())
                } catch (f) {
                    X(f)
                }
            }
        }

        Y.prototype.define = Y.prototype.define;
        Y.prototype.upgrade = Y.prototype.upgrade;
        Y.prototype.get = Y.prototype.get;
        Y.prototype.whenDefined = Y.prototype.whenDefined;
        Y.prototype.polyfillDefineLazy = Y.prototype.H;
        Y.prototype.polyfillWrapFlushCallback = Y.prototype.polyfillWrapFlushCallback;

        function Z(a, b, d) {
            function f(c) {
                return function (e) {
                    for (var g = [], h = 0; h < arguments.length; ++h) g[h] = arguments[h];
                    h = [];
                    for (var k = [], l = 0; l < g.length; l++) {
                        var m = g[l];
                        m instanceof Element && J(m) && k.push(m);
                        if (m instanceof DocumentFragment) for (m = m.firstChild; m; m = m.nextSibling) h.push(m); else h.push(m)
                    }
                    c.apply(this, g);
                    for (g = 0; g < k.length; g++) U(a, k[g]);
                    if (J(this)) for (g = 0; g < h.length; g++) k = h[g], k instanceof Element && S(a, k)
                }
            }

            void 0 !== d.prepend && (b.prepend = f(d.prepend));
            void 0 !== d.append && (b.append = f(d.append))
        };

        function Ca(a) {
            Document.prototype.createElement = function (b) {
                return va(a, this, b, null)
            };
            Document.prototype.importNode = function (b, d) {
                b = aa.call(this, b, !!d);
                this.__CE_registry ? V(a, b) : Q(a, b);
                return b
            };
            Document.prototype.createElementNS = function (b, d) {
                return va(a, this, d, b)
            };
            Z(a, Document.prototype, {prepend: ba, append: ca})
        };

        function Da(a) {
            function b(f) {
                return function (c) {
                    for (var e = [], g = 0; g < arguments.length; ++g) e[g] = arguments[g];
                    g = [];
                    for (var h = [], k = 0; k < e.length; k++) {
                        var l = e[k];
                        l instanceof Element && J(l) && h.push(l);
                        if (l instanceof DocumentFragment) for (l = l.firstChild; l; l = l.nextSibling) g.push(l); else g.push(l)
                    }
                    f.apply(this, e);
                    for (e = 0; e < h.length; e++) U(a, h[e]);
                    if (J(this)) for (e = 0; e < g.length; e++) h = g[e], h instanceof Element && S(a, h)
                }
            }

            var d = Element.prototype;
            void 0 !== ja && (d.before = b(ja));
            void 0 !== ka && (d.after = b(ka));
            void 0 !== la && (d.replaceWith = function (f) {
                for (var c = [], e = 0; e < arguments.length; ++e) c[e] = arguments[e];
                e = [];
                for (var g = [], h = 0; h < c.length; h++) {
                    var k = c[h];
                    k instanceof Element && J(k) && g.push(k);
                    if (k instanceof DocumentFragment) for (k = k.firstChild; k; k = k.nextSibling) e.push(k); else e.push(k)
                }
                h = J(this);
                la.apply(this, c);
                for (c = 0; c < g.length; c++) U(a, g[c]);
                if (h) for (U(a, this), c = 0; c < e.length; c++) g = e[c], g instanceof Element && S(a, g)
            });
            void 0 !== ma && (d.remove = function () {
                var f = J(this);
                ma.call(this);
                f && U(a, this)
            })
        };

        function Ea(a) {
            function b(c, e) {
                Object.defineProperty(c, "innerHTML", {
                    enumerable: e.enumerable,
                    configurable: !0,
                    get: e.get,
                    set: function (g) {
                        var h = this, k = void 0;
                        J(this) && (k = [], P(a, this, function (x) {
                            x !== h && k.push(x)
                        }));
                        e.set.call(this, g);
                        if (k) for (var l = 0; l < k.length; l++) {
                            var m = k[l];
                            1 === m.__CE_state && a.disconnectedCallback(m)
                        }
                        this.ownerDocument.__CE_registry ? V(a, this) : Q(a, this);
                        return g
                    }
                })
            }

            function d(c, e) {
                c.insertAdjacentElement = function (g, h) {
                    var k = J(h);
                    g = e.call(this, g, h);
                    k && U(a, h);
                    J(g) && S(a, h);
                    return g
                }
            }

            function f(c, e) {
                function g(h, k) {
                    for (var l = []; h !== k; h = h.nextSibling) l.push(h);
                    for (k = 0; k < l.length; k++) V(a, l[k])
                }

                c.insertAdjacentHTML = function (h, k) {
                    h = h.toLowerCase();
                    if ("beforebegin" === h) {
                        var l = this.previousSibling;
                        e.call(this, h, k);
                        g(l || this.parentNode.firstChild, this)
                    } else if ("afterbegin" === h) l = this.firstChild, e.call(this, h, k), g(this.firstChild, l); else if ("beforeend" === h) l = this.lastChild, e.call(this, h, k), g(l || this.firstChild, null); else if ("afterend" === h) l = this.nextSibling, e.call(this, h, k), g(this.nextSibling, l); else throw new SyntaxError("The value provided (" + String(h) + ") is not one of 'beforebegin', 'afterbegin', 'beforeend', or 'afterend'.");
                }
            }

            y && (Element.prototype.attachShadow = function (c) {
                c = y.call(this, c);
                if (a.j && !c.__CE_patched) {
                    c.__CE_patched = !0;
                    for (var e = 0; e < a.m.length; e++) a.m[e](c)
                }
                return this.__CE_shadowRoot = c
            });
            z && z.get ? b(Element.prototype, z) : I && I.get ? b(HTMLElement.prototype, I) : ua(a, function (c) {
                b(c, {
                    enumerable: !0, configurable: !0, get: function () {
                        return q.call(this, !0).innerHTML
                    }, set: function (e) {
                        var g = "template" === this.localName, h = g ? this.content : this,
                            k = p.call(document, this.namespaceURI, this.localName);
                        for (k.innerHTML = e; 0 < h.childNodes.length;) u.call(h, h.childNodes[0]);
                        for (e = g ? k.content : k; 0 < e.childNodes.length;) r.call(h, e.childNodes[0])
                    }
                })
            });
            Element.prototype.setAttribute = function (c, e) {
                if (1 !== this.__CE_state) return B.call(this, c, e);
                var g = A.call(this, c);
                B.call(this, c, e);
                e = A.call(this, c);
                a.attributeChangedCallback(this, c, g, e, null)
            };
            Element.prototype.setAttributeNS = function (c, e, g) {
                if (1 !== this.__CE_state) return F.call(this, c, e, g);
                var h = E.call(this, c, e);
                F.call(this, c, e, g);
                g = E.call(this, c, e);
                a.attributeChangedCallback(this, e, h, g, c)
            };
            Element.prototype.removeAttribute = function (c) {
                if (1 !== this.__CE_state) return C.call(this, c);
                var e = A.call(this, c);
                C.call(this, c);
                null !== e && a.attributeChangedCallback(this, c, e, null, null)
            };
            D && (Element.prototype.toggleAttribute = function (c, e) {
                if (1 !== this.__CE_state) return D.call(this, c, e);
                var g = A.call(this, c), h = null !== g;
                e = D.call(this, c, e);
                h !== e && a.attributeChangedCallback(this, c, g, e ? "" : null, null);
                return e
            });
            Element.prototype.removeAttributeNS = function (c, e) {
                if (1 !== this.__CE_state) return G.call(this, c, e);
                var g = E.call(this, c, e);
                G.call(this, c, e);
                var h = E.call(this, c, e);
                g !== h && a.attributeChangedCallback(this, e, g, h, c)
            };
            oa ? d(HTMLElement.prototype, oa) : H && d(Element.prototype, H);
            pa ? f(HTMLElement.prototype, pa) : fa && f(Element.prototype, fa);
            Z(a, Element.prototype, {prepend: ha, append: ia});
            Da(a)
        };var Fa = {};

        function Ga(a) {
            function b() {
                var d = this.constructor;
                var f = document.__CE_registry.C.get(d);
                if (!f) throw Error("Failed to construct a custom element: The constructor was not registered with `customElements`.");
                var c = f.constructionStack;
                if (0 === c.length) return c = n.call(document, f.localName), Object.setPrototypeOf(c, d.prototype), c.__CE_state = 1, c.__CE_definition = f, R(a, c), c;
                var e = c.length - 1, g = c[e];
                if (g === Fa) throw Error("Failed to construct '" + f.localName + "': This element was already constructed.");
                c[e] = Fa;
                Object.setPrototypeOf(g, d.prototype);
                R(a, g);
                return g
            }

            b.prototype = na.prototype;
            Object.defineProperty(HTMLElement.prototype, "constructor", {
                writable: !0,
                configurable: !0,
                enumerable: !1,
                value: b
            });
            window.HTMLElement = b
        };

        function Ha(a) {
            function b(d, f) {
                Object.defineProperty(d, "textContent", {
                    enumerable: f.enumerable,
                    configurable: !0,
                    get: f.get,
                    set: function (c) {
                        if (this.nodeType === Node.TEXT_NODE) f.set.call(this, c); else {
                            var e = void 0;
                            if (this.firstChild) {
                                var g = this.childNodes, h = g.length;
                                if (0 < h && J(this)) {
                                    e = Array(h);
                                    for (var k = 0; k < h; k++) e[k] = g[k]
                                }
                            }
                            f.set.call(this, c);
                            if (e) for (c = 0; c < e.length; c++) U(a, e[c])
                        }
                    }
                })
            }

            Node.prototype.insertBefore = function (d, f) {
                if (d instanceof DocumentFragment) {
                    var c = K(d);
                    d = t.call(this, d, f);
                    if (J(this)) for (f = 0; f < c.length; f++) S(a, c[f]);
                    return d
                }
                c = d instanceof Element && J(d);
                f = t.call(this, d, f);
                c && U(a, d);
                J(this) && S(a, d);
                return f
            };
            Node.prototype.appendChild = function (d) {
                if (d instanceof DocumentFragment) {
                    var f = K(d);
                    d = r.call(this, d);
                    if (J(this)) for (var c = 0; c < f.length; c++) S(a, f[c]);
                    return d
                }
                f = d instanceof Element && J(d);
                c = r.call(this, d);
                f && U(a, d);
                J(this) && S(a, d);
                return c
            };
            Node.prototype.cloneNode = function (d) {
                d = q.call(this, !!d);
                this.ownerDocument.__CE_registry ? V(a, d) : Q(a, d);
                return d
            };
            Node.prototype.removeChild = function (d) {
                var f = d instanceof Element && J(d), c = u.call(this, d);
                f && U(a, d);
                return c
            };
            Node.prototype.replaceChild = function (d, f) {
                if (d instanceof DocumentFragment) {
                    var c = K(d);
                    d = v.call(this, d, f);
                    if (J(this)) for (U(a, f), f = 0; f < c.length; f++) S(a, c[f]);
                    return d
                }
                c = d instanceof Element && J(d);
                var e = v.call(this, d, f), g = J(this);
                g && U(a, f);
                c && U(a, d);
                g && S(a, d);
                return e
            };
            w && w.get ? b(Node.prototype, w) : ta(a, function (d) {
                b(d, {
                    enumerable: !0, configurable: !0, get: function () {
                        for (var f = [], c = this.firstChild; c; c = c.nextSibling) c.nodeType !== Node.COMMENT_NODE && f.push(c.textContent);
                        return f.join("")
                    }, set: function (f) {
                        for (; this.firstChild;) u.call(this, this.firstChild);
                        null != f && "" !== f && r.call(this, document.createTextNode(f))
                    }
                })
            })
        };var O = window.customElements;

        function Ia() {
            var a = new N;
            Ga(a);
            Ca(a);
            Z(a, DocumentFragment.prototype, {prepend: da, append: ea});
            Ha(a);
            Ea(a);
            window.CustomElementRegistry = Y;
            a = new Y(a);
            document.__CE_registry = a;
            Object.defineProperty(window, "customElements", {configurable: !0, enumerable: !0, value: a})
        }

        O && !O.forcePolyfill && "function" == typeof O.define && "function" == typeof O.get || Ia();
        window.__CE_installPolyfill = Ia;
    }).call(this);


    var elementVideo = document.querySelector('#movie_player video');
    if (!elementVideo) {
        elementVideo = await new Promise(resolve => {
            var observer = new MutationObserver(() => {
                var foundElement = document.querySelector('#movie_player video');
                if (foundElement) {
                    observer.disconnect();
                    resolve(foundElement);
                }
            });
            observer.observe(document.body, {'childList': true, 'subtree': true});
        });
    }

    var videoId = new URL(location.href).searchParams.get('v');

    class YoutubeTranslator extends HTMLElement {
        constructor() {
            super();

            this.loading = true;
            this.currentLanguage = undefined;

            const shadowRoot = this.attachShadow({'mode': 'closed'});

            shadowRoot.innerHTML = `
      <style>
      :host{
        /* --- Color fallbacks (custom fix) ---
           В текущем билде YouTube переменные --yt-spec-* больше не задаются
           глобально (только в отдельных компонентах), поэтому внутри shadow-root
           var(--yt-spec-text-primary) не резолвился и текст становился чёрным
           (на тёмном фоне нечитаемо). Задаём собственные значения: в светлой
           теме — тёмный текст, в тёмной теме (html[dark]) — светлый. */
        --secondary-text-color: rgba(0, 0, 0, 0.2);
        --yt-spec-base-background: #ffffff;
        --yt-spec-text-primary: #0f0f0f;
        --yt-spec-menu-background: #ffffff;
        --yt-spec-outline: rgba(0, 0, 0, 0.12);
        --yt-spec-10-percent-layer: rgba(0, 0, 0, 0.10);
        --yt-spec-raised-background: #f2f2f2;
      }
      :host-context(html[dark]){
        --secondary-text-color: rgba(255, 255, 255, 0.2);
        --yt-spec-base-background: #0f0f0f;
        --yt-spec-text-primary: #f1f1f1;
        --yt-spec-menu-background: #282828;
        --yt-spec-outline: rgba(255, 255, 255, 0.3);
        --yt-spec-10-percent-layer: rgba(255, 255, 255, 0.10);
        --yt-spec-raised-background: #212121;
      }
      :host{
        display: block;
        border-bottom: 10px solid transparent;
      }
      :host > .In{
        /*background: var(--yt-spec-badge-chip-background);*/
        background: rgba(0, 0, 0, 0);
        border-radius: 12px;
        display: flex;
        flex-direction: column;
      }
      .Head{
        padding: 8px 0;
        margin: 0 5px;
        color: var(--yt-spec-text-primary);
        border-bottom: 1px solid var(--secondary-text-color);
        display: flex;
        order: -1;
      }

      .LangSelector{
        flex-shrink: 0;
        min-width: 60px;
      }
      .LangSelector.hidden{
        visibility: hidden;
      }
      .LangSelector > .In{
        display: inline-block;
        vertical-align: top;
        position: relative;
        padding: 0 0 0 5px;
        width: 100%;
      }
      .LangSelector.opened > .In{
        z-index: 301;
      }
      
      .LangSelector_Current{
        text-transform: uppercase;
        font-size: 1.5rem;
        line-height: 1.4;
        border: 1px solid var(--secondary-text-color);
        padding: 0 7px;
        border-radius: 6px;
        /*background: var(--yt-spec-base-background);*/
        background-color: var(--yt-spec-outline);
        /*background: var(--secondary-text-color);*/
        cursor: pointer;
        background-color: none;
      }
      .LangSelector_Current::after{
        content: '';
        display: inline-block;
        vertical-align: top;
        width: 0;
        height: 0;
        overflow: hidden;
        border: 5px solid transparent;
        border-top-color: var(--yt-spec-text-primary);
        margin: 7px 0 0 5px;
      }
      .LangSelector_List{
        display: none;
        position: absolute;
        top: 22px;
        left: 5px;
        max-height: 230px;
        overflow: auto;
        /*background: var(--yt-spec-base-background);*/
        background: var(--yt-spec-menu-background);
        border: 1px solid var(--secondary-text-color);
        font-size: 1.3rem;
        border-radius: 10px;
        padding: 5px;
      }
      .LangSelector_List.visible{
        display: block;
      }
      .LangSelector_List > .E{
        padding: 2px 4px;
        cursor: pointer;
        white-space: nowrap;
      }
      .LangSelector_List > .E:hover{
/*        background: var(--yt-spec-text-primary);
        color: var(--yt-spec-base-background);*/
        background-color: var(--yt-spec-10-percent-layer);
      }

      .Title{
        flex-grow: 1;
        text-align: center;
        font-size: 2rem;
        display: flex;
        flex-direction: row;
        align-items: center;
        /*justify-content: center;*/
        line-height: 2.8rem;
        font-weight: 700;
      }
      .Title > img{
        margin-right: 8px;
      }
      .Copy_Out{
        flex-shrink: 0;
        width: 65px;
      }
      .Copy{
        width: 24px;
        height: 24px;
        overflow: hidden;
        text-indent: -9999px;
        font-size:0;
        background-image: url("data:image/svg+xml,%3Csvg width='24' height='24' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M7 6.6V5C7 4.44772 7.44772 4 8 4H18C18.5523 4 19 4.44772 19 5V16C19 16.5523 18.5523 17 18 17H16.2308' stroke='%23828282' stroke-width='1.5'%3E%3C/path%3E%3Crect x='4.75' y='6.75' width='11.5' height='13.5' rx='1.25' stroke='%23828282' stroke-width='1.5'%3E%3C/rect%3E%3C/svg%3E");
        background-position: 50% 50%;
        background-repeat: no-repeat;
        cursor: pointer;
        margin: 0 5px 0 auto;
      }
      .Copy:hover{
        opacity: 0.7;
      }
      
      .Loading{
        height: 80px;
        display: flex;
        align-items: center;
        font-size: 1.4rem;
        text-align: center;
      }
      .Loading > .In{
        flex-grow: 1;
      }
      
      .Translation_Out{
        color: var(--yt-spec-text-primary);
      }
      .Translation{
        display: none;
        max-height: 80px;
        overflow: hidden;
        -webkit-mask-image: linear-gradient(to bottom, white 0%, transparent 100%);
        -webkit-mask-size: 100% 100%;
        -webkit-mask-position: 0 0;
      }
      .Translation .Table{
        font-size: 1.4rem;
        display: grid;
        grid-template-columns: auto auto;
        grid-gap: 12px;
        padding: 15px 15px;
      }
      .Translation .Table a{
        text-decoration: none;
        color: #3ea6ff;
      }
      
      .Translation_Out.full .Translation{
        max-height: 365px;
        overflow: auto;
        -webkit-mask-image: none;
      }
      .Translation_Out.empty .Translation{
        height: 80px;
        overflow: hidden;
        -webkit-mask-image: none;
        display: flex;
        align-items: center;
        font-size: 1.4rem;
      }
      .Translation_Out.empty .Translation > .In{
        flex-grow: 1;
        text-align: center;
        padding: 0 15px;
      }
      
      .Global:not(.loading) .Loading{
        display: none;
      }
      .Global:not(.loading) .Translation{
        display: flex;
      }
      
      .Global.loading .Translation{
        display: none!important;
      }
      
      .Resize_Out{
        border-top: 1px solid var(--secondary-text-color);
        margin: 0 5px;
      }
      .Resize{
        cursor: pointer;
        padding: 5px 0;
      }
      .Resize_Out.hidden .Resize{
        visibility: hidden;
      }
      .Resize > .In{
        width: 40px;
        height: 40px;
        margin: 0 auto;
        border-radius: 50%;
        /*border: 1px solid var(--secondary-text-color);*/
        display: flex;
        /*background: #888;*/
        background: var(--yt-spec-raised-background);
        box-shadow: 0 4px 4px rgba(0, 0, 0, .3), 0 0 4px rgba(0, 0, 0, .2);
      }
      .Resize:hover > .In{
        background-color: var(--yt-spec-outline);
        /*opacity: 0.2;*/
        /*border-color: transparent;*/
      }
      .Resize > .In > .In{
        border: 1px solid transparent;
        border-width: 2px 0 0;
        /*
        background: url("data:image/svg+xml,%3Csvg width='12' height='7' viewBox='0 0 12 7' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cg transform='translate(-5.5 -8.6)'%3E%3Cpath d='M16.2447 9.9588C16.5376 9.6659 16.5376 9.19103 16.2447 8.89814C15.9518 8.60524 15.4769 8.60524 15.184 8.89814L16.2447 9.9588ZM6.81611 8.89814C6.52322 8.60524 6.04835 8.60524 5.75545 8.89814C5.46256 9.19103 5.46256 9.6659 5.75545 9.9588L6.81611 8.89814ZM11.7425 14.461L16.2447 9.9588L15.184 8.89814L10.6819 13.4003L11.7425 14.461ZM11.3183 13.4003L6.81611 8.89814L5.75545 9.9588L10.2576 14.461L11.3183 13.4003ZM10.6819 13.4003C10.8576 13.2246 11.1425 13.2246 11.3183 13.4003L10.2576 14.461C10.6677 14.871 11.3325 14.871 11.7425 14.461L10.6819 13.4003Z' fill='%23fff'%3E%3C/path%3E%3C/g%3E%3C/svg%3E") 0 0 no-repeat;
        */
        width: 24px;
        height: 24px;
        margin: auto;
        transform: none;
      }
      .Resize > .In > .In > .In > svg{
        /*fill: var(--secondary-text-color);*/
        fill: var(--yt-spec-text-primary);
        transform: rotate( 90deg );
        transition: tranform 0.2s linear;
      }
      .Resize.opened > .In > .In{
        transform: rotate( 180deg );
      }
      </style>
      
      <div class="In Global loading">
        <div class="Translation_Out">
          <div class="Translation" data-role="translation text"></div>
          <div class="Loading"><div class="In">Loading...</div></div>
        </div>
        <div class="Resize_Out">
          <div class="Resize"><div class="In"><div class="In"><div class="In">
          <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" style="pointer-events: none; display: inherit; width: 100%; height: 100%;"><path d="m9.4 18.4-.7-.7 5.6-5.6-5.7-5.7.7-.7 6.4 6.4-6.3 6.3z"></path></svg>
</div></div></div></div>
        </div>
        <div class="Head">
            <div class="Title"><img src="` + chrome.runtime.getURL("icons/128x128.png") + `" style="width: 24px; height: 24px"><div>Youtube Transcript</div></div>
          <div class="LangSelector"><div class="In">
            <div class="LangSelector_Current"></div>
            <div class="LangSelector_List" data-role="language selector"></div>
          </div></div>
          
          <div class="Copy_Out"><div class="Copy" data-role="Copy" title="Copy"></div></div>
        </div>

      </div>`;

            // Elements
            this.elementCurrentLanguage = shadowRoot.querySelector('.LangSelector_Current');
            this.elementGlobal = shadowRoot.querySelector('.Global');
            this.elementLanguagesParent = shadowRoot.querySelector('.LangSelector');
            this.elementLanguages = shadowRoot.querySelector('[data-role="language selector"]');
            this.elementResizeParent = shadowRoot.querySelector('.Resize_Out');
            this.elementResize = shadowRoot.querySelector('.Resize');
            this.elementTranslationParent = shadowRoot.querySelector('.Translation_Out')
            this.elementTranslation = shadowRoot.querySelector('[data-role="translation text"]');
            this.elementCopy = shadowRoot.querySelector('[data-role="Copy"]');

            // Event listeners
            this.langListVisible = false;

            this.documentClick = (event) => {
                if (event.target === this) return;

                this.elementLanguagesParent.classList.remove('opened');
                this.elementLanguages.classList.remove('visible');
                this.langListVisible = false;

                document.removeEventListener('click', this.documentClick);
            };
            this.thisClick = (event) => {
                this.elementLanguagesParent.classList.remove('opened');
                this.elementLanguages.classList.remove('visible');
                this.langListVisible = false;

                document.removeEventListener('click', this.documentClick);
                shadowRoot.removeEventListener('click', this.thisClick);
            };

            this.elementCurrentLanguage.addEventListener('click', (event) => {
                if (!this.langListVisible) {
                    this.elementLanguagesParent.classList.add('opened');
                    this.elementLanguages.classList.add('visible');
                    this.langListVisible = true;
                    event.stopPropagation();

                    document.addEventListener('click', this.documentClick);
                    shadowRoot.addEventListener('click', this.thisClick);
                } else {
                    this.elementLanguages.classList.remove('visible');
                    this.langListVisible = false;

                    document.removeEventListener('click', this.documentClick);
                    shadowRoot.removeEventListener('click', this.thisClick);
                }
            });

            this.elementCopy.addEventListener('click', () => {
                //var clipboardText = document.title + '\n' + location.href + '\n\nTranscript:\n';
                var clipboardText = '';
                for (var {start, text} of this.translationText) {
                    start = Math.round(start);
                    let seconds = start % 60;
                    start -= seconds;
                    let secondsString = String(seconds).padStart(2, '0');

                    let minutes = start / 60;

                    //clipboardText += `(${minutes}:${secondsString}) ${text}\n`;
                    clipboardText += `${text}\n`;
                }

                navigator.clipboard.writeText(clipboardText);
            });

            this.elementResize.addEventListener('click', () => {
                if (!this.extended) {
                    this.elementTranslationParent.classList.add('full');
                    this.elementResize.classList.add('opened');
                } else {
                    this.elementTranslationParent.classList.remove('full');
                    this.elementResize.classList.remove('opened');
                    this.elementTranslation.scrollTop = 0;
                }

                this.extended = !this.extended;
            });
        }

        /** @method */
        applyLanguages(defaultLanguage, languages) {
            this.currentLanguage = defaultLanguage;
            this.languages = languages;

            this.renderLanguages();
        }

        /** @method */
        applyTranslation({translation, translationText/*, languageCode*/}) {
            this.loading = false;

            this.translationObjects = translation?.captionTracks || null;
            this.translationText = translationText;
            // this.currentLanguage = languageCode;
            // this.languages = translation?.translationLanguages;

            this.renderLanguages();
            this.renderTranslation();
        }

        /** @method */
        renderLanguages() {
            if (!this.currentLanguage || !this.translationObjects) {
                this.elementLanguagesParent.classList.add('hidden');
                return;
            }

            this.elementLanguagesParent.classList.remove('hidden');
            this.elementCurrentLanguage.textContent = this.currentLanguage;

            this.elementLanguages.innerHTML = '';

            var pureTranslations = this.translationObjects.filter(({kind}) => kind !== 'asr');
            var autoTranslations = this.translationObjects.filter(({kind}) => kind === 'asr');
            for (const translation of pureTranslations) {
                let div = createElement('div', {
                    'className': 'E',
                    'textContent': translation.name.simpleText
                });

                div.addEventListener('click', async () => {
                    this._currentRequestObject?.cancel?.();
                    this.setLoading();

                    var url = await getEnchantedUrl(translation.baseUrl);
                    var requestObject = requestTranslationText(url);
                    this._currentRequestObject = requestObject;
                    var data = await requestObject.promise;

                    var translationText = adaptTranslationData(data);
                    this.translationText = translationText;
                    this.currentLanguage = translation.languageCode;

                    saveDefaultLanguage(translation.languageCode);

                    this.loading = false;

                    this.renderLanguages();
                    this.renderTranslation();
                });

                this.elementLanguages.append(div);
            }
            for (const translation of autoTranslations) {
                let div = createElement('div', {
                    'className': 'E',
                    'textContent': translation.name.simpleText
                });

                div.addEventListener('click', async () => {
                    this._currentRequestObject?.cancel?.();
                    this.setLoading();

                    var url = await getEnchantedUrl(translation.baseUrl);
                    var requestObject = requestTranslationText(url);
                    this._currentRequestObject = requestObject;
                    var data = await requestObject.promise;

                    var translationText = adaptTranslationData(data);

                    this.translationText = translationText;
                    this.currentLanguage = translation.languageCode;

                    saveDefaultLanguage(translation.languageCode);

                    this.loading = false;

                    this.renderLanguages();
                    this.renderTranslation();
                });

                this.elementLanguages.append(div);
            }
            for (const language of this.languages) {
                let div = createElement('div', {
                    'className': 'E',
                    'textContent': language.text
                });

                div.addEventListener('click', async () => {
                    var enTRanslationObjects = this.translationObjects.filter(({languageCode}) => languageCode === 'en');

                    var baseUrl = enTRanslationObjects.find(({kind}) => kind !== 'asr')?.baseUrl;
                    baseUrl ||= enTRanslationObjects.find(({kind}) => kind === 'asr')?.baseUrl;
                    baseUrl ||= this.translationObjects[0]?.baseUrl;
                    if (!baseUrl) throw new Error('To pure translation object');

                    var urlObject = new URL(baseUrl);
                    urlObject.searchParams.set('tlang', language.code);

                    this._currentRequestObject?.cancel?.();
                    this.setLoading();

                    var url = await getEnchantedUrl(urlObject.toString());
                    var requestObject = requestTranslationText(url);
                    this._currentRequestObject = requestObject;
                    var data = await requestObject.promise;

                    var translationText = adaptTranslationData(data);
                    this.currentLanguage = language.code;
                    this.translationText = translationText;

                    saveDefaultLanguage(language.code);

                    this.loading = false;

                    this.renderLanguages();
                    this.renderTranslation();
                });

                this.elementLanguages.append(div);
            }
        }

        /** @method */
        renderTranslation() {
            var classList = this.elementTranslationParent.classList;

            if (this.loading) {
                this.elementGlobal.classList.add('loading');
            } else {
                this.elementGlobal.classList.remove('loading');
            }

            if (this.translationText) {
                classList.remove('empty');
                this.elementTranslation.innerHTML = '';

                var div = createElement('div', {'className': 'Table'});

                for (let {start, text} of this.translationText) {
                    let originalStart = start;
                    start = Math.round(start);

                    let seconds = start % 60;
                    start -= seconds;
                    let secondsString = String(seconds).padStart(2, '0');

                    let minutes = start / 60;

                    let timeString = String(minutes) + ':' + secondsString;

                    var link = createElement('a', {'textContent': timeString});
                    link.href = (() => {
                        var urlObject = new URL(location.href);
                        urlObject.searchParams.set('t', Math.round(originalStart) + 's');

                        return urlObject.toString();
                    })();

                    link.addEventListener('click', (event) => {
                        event.preventDefault();
                        elementVideo.currentTime = originalStart;
                    });

                    var startDiv = createElement('div', {
                        'className': 'Start',
                        'children': link
                    });

                    var textDiv = createElement('div', {
                        'className': 'RowText',
                        'textContent': text
                    });

                    div.append(startDiv, textDiv);
                }
                this.elementTranslation.append(div);

                this.elementResizeParent.classList.remove('hidden');
                return;
            }

            classList.add('empty');
            this.elementTranslation.innerHTML = '';

            var div = createElement('div', {
                'className': 'In',
                'textContent': 'No Transcription Available... 😢'
            });

            this.elementTranslation.append(div);
            this.elementResizeParent.classList.add('hidden');
        }

        /** @method */
        setLoading() {
            this.loading = true;

            this.renderLanguages();
            this.renderTranslation();
        }
    };
    customElements.define('youtube-translator', YoutubeTranslator);

    var elementTranslator = document.createElement('youtube-translator'); // new YoutubeTranslator();

    parent.prepend(elementTranslator);


    var translation = videoId ? await getTranslation(videoId) : undefined;

    var videoChanges = new class {
        #listeners;

        constructor() {
            this.#listeners = [];

            var observer = new MutationObserver((mutations) => {
                for (var mutation of mutations) {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
                        for (var listener of this.#listeners) listener();
                    }
                }
            });

            observer.observe(elementVideo, {attributes: true});
        }

        /** @method */
        addListener(listener) {
            this.#listeners.push(listener);
        }
    }();

    videoChanges.addListener(async () => {
        var videoId = new URL(location.href).searchParams.get('v');
        if (!videoId) return;

        elementTranslator.setLoading();

        var translation = await getTranslation(videoId);

        if (!translation) {
            elementTranslator.applyTranslation({
                'translation': null,
                'translationText': undefined
            });
        } else {
            var languages = translation.translationLanguages.map(item => ({
                'code': item.languageCode,
                'text': item.languageName.simpleText
            }));

            let track = translation.captionTracks.find(({kind}) => kind !== 'asr');
            track ||= translation.captionTracks[0];

            let language = await getDefaultLanguage() || track.languageCode;
            var baseUrl = tracksToBaseUrlByLanguage(translation.captionTracks, language);

            (async () => {
                let url = await getEnchantedUrl(baseUrl);
                var requestObject = requestTranslationText(url);
                var data = await requestObject.promise;

                elementTranslator.applyLanguages(language, languages);

                var translationText = adaptTranslationData(data);
                //languageCode = track.languageCode;
                elementTranslator.applyTranslation({
                    translation,
                    translationText
                    //,languageCode
                });
            })();
        }
    });


    // On start action:
    if (videoId) {
        if (!translation) {
            elementTranslator.applyTranslation({
                'translation': null,
                'translationText': undefined
            });
        } else {
            let languages = translation.translationLanguages.map(item => ({
                'code': item.languageCode,
                'text': item.languageName.simpleText
            }));

            let track = translation.captionTracks.find(({kind}) => kind !== 'asr');
            track ||= translation.captionTracks[0];

            let language = await getDefaultLanguage() || track.languageCode;
            let baseUrl = tracksToBaseUrlByLanguage(translation.captionTracks, language);

            elementTranslator.applyLanguages(language, languages);

            (async () => {
                var url = await getEnchantedUrl(baseUrl);
                var requestObject = requestTranslationText(url);
                var data = await requestObject.promise;

                var translationText = adaptTranslationData(data);
                //languageCode = track.languageCode;
                elementTranslator.applyTranslation({
                    translation,
                    translationText
                });
            })();
        }
    }
});