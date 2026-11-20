package com.egor.webtube;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * WebTube: YouTube (TV web interface) как нативное Android TV приложение.
 *
 * Использует https://www.youtube.com/tv — это специальный веб-интерфейс
 * YouTube, спроектированный для телевизоров и управления с пульта
 * (стрелки/OK/Back). Он же работает в браузерах Smart TV.
 *
 *  - управление с пульта: D-pad/стрелки/OK/Back обрабатывает сам сайт
 *    (это его родное поведение),
 *  - тёмная тема принудительно (кук PREF f6=400 + атрибут dark на <html>),
 *  - скорость воспроизведения запоминается и применяется к <video>,
 *  - полноэкранный плеер на весь экран.
 */
public class MainActivity extends Activity {
    private static final String TAG = "WebTube";

    // Web-интерфейс YouTube для мобильных/TV. Проверено на эмуляторе:
    // youtube.com/tv теперь делает редирект на десктопный сайт (Google закрыл
    // свободный доступ), а m.youtube.com отдаёт полноценный интерфейс.
    private static final String URL_HOME = "https://m.youtube.com/";
    private static final String PREFS = "webtube_prefs";
    private static final String KEY_SPEED = "playback_speed";
    private static final String KEY_DARK = "force_dark";

    private WebView mWebView;
    private View mCustomView;
    private WebChromeClient.CustomViewCallback mCustomViewCallback;
    private FrameLayout mRoot;
    private TextView mOsd;

    private float mSpeed = 1.0f;
    private boolean mForceDark = true;

    private SharedPreferences mPrefs;

    private static final float[] SPEEDS = {1.0f, 1.25f, 1.5f, 1.75f, 2.0f};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        mPrefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        mSpeed = mPrefs.getFloat(KEY_SPEED, 1.0f);
        mForceDark = mPrefs.getBoolean(KEY_DARK, true);

        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);

        mRoot = new FrameLayout(this);
        mRoot.setBackgroundColor(Color.BLACK);

        mOsd = new TextView(this);
        mOsd.setTextColor(Color.WHITE);
        mOsd.setBackgroundColor(0x99000000);
        mOsd.setPadding(24, 12, 24, 12);
        mOsd.setTextSize(18);
        mOsd.setVisibility(View.GONE);
        mRoot.addView(mOsd, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.BOTTOM | android.view.Gravity.CENTER_HORIZONTAL));

        initWebView();
        mRoot.addView(mWebView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        setContentView(mRoot);
        applyDarkCookie();
        mWebView.loadUrl(URL_HOME);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void initWebView() {
        mWebView = new WebView(this);
        mWebView.setBackgroundColor(Color.BLACK);
        mWebView.setFocusable(true);
        mWebView.setFocusableInTouchMode(true);
        mWebView.requestFocus();

        WebSettings s = mWebView.getSettings();
        // Отладка через chrome://inspect / CDP (можно оставить - не влияет на release)
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setAllowFileAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        // UA телевизионного браузера на базе Chrome — TV-интерфейс YouTube
        // отдаётся именно для таких клиентов.
        s.setUserAgentString(tvUa());

        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(mWebView, true);

        mWebView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.contains("youtube.com") || url.contains("accounts.google.com")
                        || url.contains("google.com") || url.contains("youtu.be")) {
                    return false;
                }
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                Log.i(TAG, "onPageFinished: " + url);
                injectTvMode(view);
                applyDarkAndSpeed();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        android.webkit.WebResourceError error) {
                super.onReceivedError(view, request, error);
                Log.e(TAG, "onReceivedError: " + request.getUrl()
                        + " code=" + error.getErrorCode()
                        + " desc=" + error.getDescription());
                // Показываем понятное сообщение вместо чёрного экрана
                if (request.isForMainFrame()) {
                    String html = "<html><body style='background:#282828;color:#fff;"
                            + "font-family:sans-serif;padding:2rem;font-size:1.4rem'>"
                            + "<h2>Нет соединения с YouTube</h2>"
                            + "<p>Проверьте интернет-соединение на приставке.</p>"
                            + "<p style='color:#969696;font-size:1rem'>"
                            + error.getDescription() + "</p></body></html>";
                    view.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
                }
            }
        });

        mWebView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onShowCustomView(View view, CustomViewCallback callback) {
                if (mCustomView != null) {
                    callback.onCustomViewHidden();
                    return;
                }
                mCustomView = view;
                mCustomViewCallback = callback;
                mRoot.addView(mCustomView, new FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.MATCH_PARENT,
                        FrameLayout.LayoutParams.MATCH_PARENT));
                mWebView.setVisibility(View.GONE);
            }

            @Override
            public void onHideCustomView() {
                hideCustomView();
            }
        });
    }

    private String tvUa() {
        // Chrome на Android: YouTube отдаёт мобильный интерфейс (ytm-*),
        // который нормально управляется с пульта (D-pad навигация по фокусам).
        return "Mozilla/5.0 (Linux; Android 11; Build/RP1A.200720.012) AppleWebKit/537.36 "
                + "(KHTML, like Gecko) Chrome/126.0.6478.114 Mobile Safari/537.36";
    }

    /**
     * Тёмная тема: кук PREF с f6=400 (dark).
     * YouTube склеивает флаги f6, поэтому дописываем 400 в начало (см. AGENTS).
     */
    private void applyDarkCookie() {
        if (!mForceDark) {
            return;
        }
        CookieManager cm = CookieManager.getInstance();
        String existing = cm.getCookie("https://m.youtube.com/");
        String pref = null;
        if (existing != null) {
            for (String part : existing.split(";")) {
                String kv[] = part.trim().split("=");
                if (kv.length == 2 && kv[0].equals("PREF")) {
                    pref = kv[1];
                }
            }
        }
        String f6 = pref != null ? pref : "";
        if (!f6.startsWith("400")) {
            f6 = "400" + f6;
        }
        cm.setCookie("https://m.youtube.com/", "PREF=" + f6 + "; path=/; domain=.youtube.com");
        cm.flush();
    }

    /**
     * TV-режим: инъекция CSS (10-foot UI) и JS-движка (D-pad навигация).
     * Файлы лежат в assets/: tv_style.css, tv_engine.js
     */
    private void injectTvMode(WebView view) {
        try {
            java.util.Scanner sc = new java.util.Scanner(getAssets().open("tv_style.css"))
                    .useDelimiter("\\A");
            String css = sc.hasNext() ? sc.next() : "";
            sc.close();
            String jsCss = "(function(){var s=document.createElement('style');"
                    + "s.id='tv-style';"
                    + "s.textContent=" + jsString(css) + ";"
                    + "document.head.appendChild(s);})();";
            view.evaluateJavascript(jsCss, null);
        } catch (Exception e) {
            Log.e(TAG, "injectTvMode css failed", e);
        }
        try {
            java.util.Scanner sc = new java.util.Scanner(getAssets().open("tv_engine.js"))
                    .useDelimiter("\\A");
            String js = sc.hasNext() ? sc.next() : "";
            sc.close();
            view.evaluateJavascript(js, null);
        } catch (Exception e) {
            Log.e(TAG, "injectTvMode js failed", e);
        }
        // Передаём текущую скорость в движок
        view.evaluateJavascript("window.__wtSpeed=" + mSpeed + ";", null);
    }

    /** Безопасное оборачивание текста в JS-строку */
    private String jsString(String text) {
        return "\"" + text
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "")
                .replace("</script>", "<\\/script>") + "\"";
    }

    /**
     * JS-инъекция: тёмная тема + применение сохранённой скорости к <video>.
     */
    private void applyDarkAndSpeed() {
        if (mWebView == null) {
            return;
        }
        mWebView.evaluateJavascript(
                "try{"
                        + "var h=document.documentElement;"
                        + "if(!h.hasAttribute('dark')){h.setAttribute('dark','');}"
                        + "h.removeAttribute('light');"
                        + "var v=document.querySelector('video');"
                        + "if(v){v.playbackRate=" + mSpeed + ";v.defaultPlaybackRate=" + mSpeed + ";}"
                        + "window.__wtSpeed=" + mSpeed + ";"
                        + "}catch(e){}", null);
        // Видео-элемент появляется не сразу — повторяем
        mWebView.postDelayed(this::applySpeedNow, 1500);
        mWebView.postDelayed(this::applySpeedNow, 4000);
    }

    // ---------------- Обработка пульта ----------------

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_BACK:
                if (mCustomView != null) {
                    hideCustomView();
                    return true;
                }
                if (mWebView != null && mWebView.canGoBack()) {
                    mWebView.goBack();
                    return true;
                }
                break;

            // ---- Скорость: MENU / Y / зелёная ----
            case KeyEvent.KEYCODE_MENU:
            case KeyEvent.KEYCODE_BUTTON_Y:
            case KeyEvent.KEYCODE_PROG_GREEN:
                cycleSpeed();
                return true;

            // ---- Тёмная тема: INFO / X / красная ----
            case KeyEvent.KEYCODE_INFO:
            case KeyEvent.KEYCODE_BUTTON_X:
            case KeyEvent.KEYCODE_PROG_RED:
                toggleDark();
                return true;

            // ---- Пауза/плей ----
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_PLAY:
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                toggleVideoPlayback();
                return true;

            // ---- Перемотка ±10с (как кнопки пульта SmartTube) ----
            case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
                seekVideo(10_000);
                return true;
            case KeyEvent.KEYCODE_MEDIA_REWIND:
                seekVideo(-10_000);
                return true;

            // ---- Перемотка на 0%-90% (цифры, как в SmartTube) ----
            case KeyEvent.KEYCODE_0:
            case KeyEvent.KEYCODE_1:
            case KeyEvent.KEYCODE_2:
            case KeyEvent.KEYCODE_3:
            case KeyEvent.KEYCODE_4:
            case KeyEvent.KEYCODE_5:
            case KeyEvent.KEYCODE_6:
            case KeyEvent.KEYCODE_7:
            case KeyEvent.KEYCODE_8:
            case KeyEvent.KEYCODE_9:
                seekToPercent(keyCode - KeyEvent.KEYCODE_0);
                return true;

            // ---- следующее/предыдущее видео ----
            case KeyEvent.KEYCODE_MEDIA_NEXT:
                mWebView.evaluateJavascript(
                        "try{document.querySelector('[aria-label*=\"Следующее\"],"
                                + "[aria-label*=\"Next\"]').click();}catch(e){}", null);
                return true;
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                mWebView.evaluateJavascript(
                        "try{history.back();}catch(e){}", null);
                return true;

            default:
                break;
        }
        return super.onKeyDown(keyCode, event);
    }

    /** Пауза/плей через JS прямо в <video> */
    private void toggleVideoPlayback() {
        if (mWebView == null) return;
        mWebView.evaluateJavascript(
                "try{var v=document.querySelector('video');"
                        + "if(v){if(v.paused){v.play();__wtShowOsd&&__wtShowOsd('▶',1000);}"
                        + "else{v.pause();__wtShowOsd&&__wtShowOsd('⏸',1000);}}}"
                        + "catch(e){}", null);
    }

    /** Перемотка на ±миллисекунд */
    private void seekVideo(long deltaMs) {
        if (mWebView == null) return;
        double deltaSec = deltaMs / 1000.0;
        mWebView.evaluateJavascript(
                "try{var v=document.querySelector('video');"
                        + "if(v&&v.duration){v.currentTime=Math.max(0,Math.min(v.duration,"
                        + "v.currentTime+" + deltaSec + "));"
                        + "__wtShowOsd&&__wtShowOsd((v.currentTime>v.duration-1?'⏭ ':'⏩ ')"
                        + "+__wtFormatTime(v.currentTime)+' / '+__wtFormatTime(v.duration),1500);}}"
                        + "catch(e){}", null);
    }

    /** Перемотка на 0-90% ролика (цифры, как в SmartTube) */
    private void seekToPercent(int digit) {
        if (mWebView == null) return;
        final double pct = digit / 10.0;
        mWebView.evaluateJavascript(
                "try{var v=document.querySelector('video');"
                        + "if(v&&v.duration){var pos=v.duration*" + pct + ";"
                        + "v.currentTime=pos;"
                        + "__wtShowOsd&&__wtShowOsd(digit+'0%: '+__wtFormatTime(pos),1500);}}"
                        + "catch(e){}", null);
        showOsd("Перемотка: " + (digit * 10) + "%");
    }

    private void cycleSpeed() {
        int idx = 0;
        for (int i = 0; i < SPEEDS.length; i++) {
            if (Math.abs(SPEEDS[i] - mSpeed) < 0.01f) {
                idx = i;
                break;
            }
        }
        idx = (idx + 1) % SPEEDS.length;
        mSpeed = SPEEDS[idx];
        mPrefs.edit().putFloat(KEY_SPEED, mSpeed).apply();
        applySpeedNow();
        // Большой OSD на веб-странице (видно с дивана)
        if (mWebView != null) {
            mWebView.evaluateJavascript(
                    "window.__wtSpeed=" + mSpeed + ";"
                            + "try{__wtApplySpeed&&__wtApplySpeed();"
                            + "__wtShowOsd&&__wtShowOsd('Скорость: " + mSpeed + "x',2000);}"
                            + "catch(e){}", null);
        }
        showOsd("Скорость: " + mSpeed + "x");
    }

    private void applySpeedNow() {
        if (mWebView == null) {
            return;
        }
        mWebView.evaluateJavascript(
                "window.__wtSpeed=" + mSpeed + ";"
                        + "try{__wtApplySpeed&&__wtApplySpeed();"
                        + "var v=document.querySelector('video');"
                        + "if(v){v.playbackRate=" + mSpeed + ";v.defaultPlaybackRate=" + mSpeed + ";}}"
                        + "catch(e){}", null);
    }

    private void toggleDark() {
        mForceDark = !mForceDark;
        mPrefs.edit().putBoolean(KEY_DARK, mForceDark).apply();
        if (mForceDark) {
            applyDarkCookie();
        }
        applyDarkAndSpeed();
        showOsd("Тёмная тема: " + (mForceDark ? "вкл" : "выкл"));
    }

    private void showOsd(String text) {
        mOsd.setText(text);
        mOsd.setVisibility(View.VISIBLE);
        mOsd.removeCallbacks(mHideOsd);
        mOsd.postDelayed(mHideOsd, 2000);
        Toast.makeText(this, text, Toast.LENGTH_SHORT).show();
    }

    private final Runnable mHideOsd = () -> mOsd.setVisibility(View.GONE);

    private void hideCustomView() {
        if (mCustomView == null) {
            return;
        }
        mCustomView.setVisibility(View.GONE);
        mRoot.removeView(mCustomView);
        mCustomView = null;
        if (mCustomViewCallback != null) {
            mCustomViewCallback.onCustomViewHidden();
            mCustomViewCallback = null;
        }
        mWebView.setVisibility(View.VISIBLE);
        mWebView.requestFocus();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (mWebView != null) {
            mWebView.onPause();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (mWebView != null) {
            mWebView.onResume();
            mWebView.requestFocus();
        }
    }

    @Override
    protected void onDestroy() {
        mRoot.removeCallbacks(mHideOsd);
        if (mWebView != null) {
            mWebView.destroy();
            mWebView = null;
        }
        super.onDestroy();
    }
}
