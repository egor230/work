import io, json, copy, os, sys
ROOT = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/android-tv-emu/SmartTubeDNS"

def read(p): return io.open(p, encoding="utf-8").read()
def write(p, s): io.open(p, "w", encoding="utf-8").write(s)
def rep(p, old, new, count=1):
    s = read(p)
    if old not in s:
        print("NOT FOUND in", p, "::", old[:90]); sys.exit(1)
    write(p, s.replace(old, new, count))

# A applicationId
rep(ROOT + "/smarttubetv/build.gradle", 'applicationId "org.smarttube.stable"', 'applicationId "com.egor.youtubetv"')

# B google-services
p = ROOT + "/smarttubetv/google-services.json"
d = json.load(io.open(p, encoding="utf-8"))
if not any(c["client_info"]["android_client_info"]["package_name"] == "com.egor.youtubetv" for c in d["client"]):
    base = next(c for c in d["client"] if c["client_info"]["android_client_info"]["package_name"] == "org.smarttube.stable")
    new = copy.deepcopy(base); new["client_info"]["android_client_info"]["package_name"] = "com.egor.youtubetv"
    d["client"].append(new); json.dump(d, io.open(p, "w", encoding="utf-8"), indent=2)

# C app name
for rel in ["smarttubetv/src/main/res/values/strings.xml", "smarttubetv/src/ststable/res/values/strings.xml"]:
    p = ROOT + "/" + rel; s = read(p)
    for a, b in [("SmartTube beta", "Smart YouTube Next TV"), ("SmartTube F-Droid", "Smart YouTube Next TV"), ("SmartTube", "Smart YouTube Next TV")]:
        s = s.replace(a, b)
    write(p, s)

# D drawables
d = ROOT + "/SharedModules/sharedutils/src/main/res/drawable"
draw = {
"smart_radio_unchecked.xml": '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
<size android:width="22dp" android:height="22dp" /><stroke android:width="2dp" android:color="#FFBDBDBD" /><solid android:color="@android:color/transparent" />
</shape>''',
"smart_radio_checked.xml": '''<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
<item><shape android:shape="oval"><size android:width="22dp" android:height="22dp" /><stroke android:width="2dp" android:color="#FFFFFFFF" /><solid android:color="@android:color/transparent" /></shape></item>
<item android:bottom="5dp" android:left="5dp" android:right="5dp" android:top="5dp"><shape android:shape="oval"><solid android:color="#FFFFFFFF" /></shape></item>
</layer-list>''',
"smart_check_unchecked.xml": '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
<size android:width="22dp" android:height="22dp" /><stroke android:width="2dp" android:color="#FFBDBDBD" /><solid android:color="@android:color/transparent" />
</shape>''',
"smart_check_checked.xml": '''<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
<item><shape android:shape="rectangle"><size android:width="22dp" android:height="22dp" /><stroke android:width="2dp" android:color="#FFFFFFFF" /><solid android:color="@android:color/transparent" /></shape></item>
<item android:bottom="5dp" android:left="5dp" android:right="5dp" android:top="5dp"><shape android:shape="rectangle"><solid android:color="#FFFFFFFF" /></shape></item>
</layer-list>''',
}
for n, c in draw.items(): io.open(os.path.join(d, n), "w", encoding="utf-8").write(c)
for n, checked, unchecked in [("smart_radio_button.xml", "smart_radio_checked", "smart_radio_unchecked"),
                               ("smart_check_button.xml", "smart_check_checked", "smart_check_unchecked")]:
    io.open(os.path.join(d, n), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="utf-8"?>\n<selector xmlns:android="http://schemas.android.com/apk/res/android">'
        '<item android:drawable="@drawable/%s" android:state_checked="true" />'
        '<item android:drawable="@drawable/%s" /></selector>\n' % (checked, unchecked))
rep(ROOT + "/SharedModules/sharedutils/src/main/res/layout/dialog_check_item_single.xml", '?android:attr/listChoiceIndicatorSingle', '@drawable/smart_radio_button')
rep(ROOT + "/SharedModules/sharedutils/src/main/res/layout/dialog_check_item_multi.xml", '?android:attr/listChoiceIndicatorMultiple', '@drawable/smart_check_button')

# E ErrorLog
io.open(ROOT + "/common/src/main/java/com/liskovsoft/smartyoutubetv2/common/misc/ErrorLog.java", "w", encoding="utf-8").write('''package com.liskovsoft.smartyoutubetv2.common.misc;
import android.content.Context;
import android.util.Log;
import java.io.*;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
public final class ErrorLog {
    private static final String TAG = "ErrorLog";
    private static final String FILE_NAME = "autofix_errors.log";
    private static final long MAX_SIZE = 5L * 1024 * 1024;
    private static final int MAX_ENTRY_CHARS = 4096;
    private ErrorLog() {}
    public static File getFile(Context c) { return new File(c.getFilesDir(), FILE_NAME); }
    public static void log(Context c, String tag, String message, Throwable error) {
        if (c == null) return;
        try {
            File f = getFile(c);
            StringBuilder e = new StringBuilder();
            String t = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(new Date());
            e.append('\\n').append(t).append(" [").append(tag).append("] ").append(message);
            if (error != null) {
                String st = Log.getStackTraceString(error);
                if (st.length() > MAX_ENTRY_CHARS) st = st.substring(0, MAX_ENTRY_CHARS) + "\\n...(truncated)";
                e.append('\\n').append(st);
            }
            FileWriter w = new FileWriter(f, true);
            try { w.write(e.toString()); } finally { w.close(); }
            trim(f);
        } catch (Throwable ex) { Log.e(TAG, "log failed: " + ex.getMessage()); }
    }
    private static void trim(File f) {
        if (!f.exists() || f.length() <= MAX_SIZE) return;
        try {
            FileInputStream in = new FileInputStream(f);
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            try { byte[] ch = new byte[8192]; int r; while ((r = in.read(ch)) != -1) b.write(ch, 0, r); } finally { in.close(); }
            byte[] all = b.toByteArray(); int from = all.length - (int)(MAX_SIZE * 4 / 5);
            if (from < 0) from = 0;
            FileOutputStream out = new FileOutputStream(f);
            try { out.write(all, from, all.length - from); } finally { out.close(); }
        } catch (IOException ex) { Log.e(TAG, "trim failed: " + ex.getMessage()); }
    }
}
''')

# F ErrorFixerController
p = ROOT + "/common/src/main/java/com/liskovsoft/smartyoutubetv2/common/app/models/playback/controllers/ErrorFixerController.java"
s = read(p)
def rp(o, n):
    global s
    if o not in s: print("EF NOT FOUND", o[:80]); sys.exit(1)
    s = s.replace(o, n, 1)

rp("import com.liskovsoft.smartyoutubetv2.common.misc.BufferingDetector.OnLongBuffering;",
   "import com.liskovsoft.smartyoutubetv2.common.misc.BufferingDetector.OnLongBuffering;\nimport com.liskovsoft.smartyoutubetv2.common.misc.ErrorLog;")
rp("""    private static final int MAX_SABR_ERROR_FIX_ATTEMPTS = 1;
    private final BufferingDetector mBufferingDetector = new BufferingDetector(this);
    private VideoLoaderController mVideoLoaderController;
    private String mSabrErrorFixVideoId;""",
"""    private static final int MAX_SABR_ERROR_FIX_ATTEMPTS = 1;
    private static final String PREFS_AUTO_DNS = "autodns_fix";
    private static final String KEY_DNS_STEP = "dns_step";
    private static final String KEY_DNS_LAST_MS = "dns_last_ms";
    private static final long AUTO_DNS_RETRY_DELAY_MS = 15_000;
    private static final int[] DNS_FALLBACK_ORDER = {
            PlayerTweaksData.DNS_TYPE_GOOGLE, PlayerTweaksData.DNS_TYPE_IPV4, PlayerTweaksData.DNS_TYPE_SYSTEM
    };
    private final BufferingDetector mBufferingDetector = new BufferingDetector(this);
    private VideoLoaderController mVideoLoaderController;
    private final android.os.Handler mStuckHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private static final long STUCK_PLAYBACK_TIMEOUT_MS = 30_000;
    private final Runnable mStuckWatchdog = () -> {
        boolean playing = getPlayer() != null && getPlayer().getPositionMs() > 0;
        if (!playing && !getPlayerTweaksData().isNetworkErrorFixingDisabled()) {
            Log.w(TAG, "Auto-fix: playback stuck (no error). Switching YouTube client…");
            MessageHelpers.showLongMessage(getContext(), "Auto-fix: stalled client, switching…");
            ErrorLog.log(getContext(), TAG, "watchdog: stalled playback, switching client", null);
            YouTubeServiceManager.instance().switchNextClientNow();
            mVideoLoaderController.reloadVideo();
        }
    };
    private String mSabrErrorFixVideoId;""")
rp("""        Log.e(TAG, "Player error occurred: %s. Trying to fix…", type);

        mBufferingDetector.reset();""",
"""        Log.e(TAG, "Player error occurred: %s. Trying to fix…", type);
        logError("onEngineError type=" + type + " renderer=" + rendererIndex, error);

        mBufferingDetector.reset();""")
rp("""    public void onPlay() {
        mBufferingDetector.onStopBuffering();
        mSabrErrorFixAttempts = 0;
    }""",
"""    public void onPlay() {
        mBufferingDetector.onStopBuffering();
        mSabrErrorFixAttempts = 0;
        mStuckHandler.removeCallbacks(mStuckWatchdog);
        resetAutoDnsStep();
    }""")
rp("""    public void onNewVideo(Video item) {
        mBufferingDetector.start();
    }""",
"""    public void onNewVideo(Video item) {
        mBufferingDetector.start();
        mStuckHandler.removeCallbacks(mStuckWatchdog);
        mStuckHandler.postDelayed(mStuckWatchdog, STUCK_PLAYBACK_TIMEOUT_MS);
        resetAutoDnsStep();
    }""")
rp("""    public void onFinish() {
        mBufferingDetector.reset();
    }""",
"""    public void onFinish() {
        mBufferingDetector.reset();
        mStuckHandler.removeCallbacks(mStuckWatchdog);
    }""")
rp("""        if (Helpers.startsWithAny(errorContent, "Unable to connect to")) {
            // No internet connection or WRONG DATE on the device
            // Recently this message starting to show for other unknown reasons
            if (!getPlayerTweaksData().isNetworkErrorFixingDisabled()) {
                switchNextEngine();
            }
        } else if""",
"""        if (Helpers.startsWithAny(errorContent, "Unable to connect to")) {
            if (!getPlayerTweaksData().isNetworkErrorFixingDisabled()) {
                applyAutoDnsFix();
            }
        } else if""")
rp("""        String fullMsg = String.format("loadFormatInfo error: %s: %s", className, Utils.getStackTraceAsString(error));
        Log.e(TAG, fullMsg);""",
"""        String fullMsg = String.format("loadFormatInfo error: %s: %s", className, Utils.getStackTraceAsString(error));
        Log.e(TAG, fullMsg);
        logError("loadFormatInfo", error);""")
rp("""    private void switchNextEngine() {
        getPlayerTweaksData().setPlayerDataSource(getNextEngine());
    }""",
"""    private void logError(String where, Throwable error) {
        String vid = getVideo() != null ? getVideo().videoId : "null";
        long pos = getPlayer() != null ? getPlayer().getPositionMs() : -1;
        String format = getPlayer() != null && getPlayer().getVideoFormat() != null
                ? String.valueOf(getPlayer().getVideoFormat().getTitle()) : "null";
        String info = String.format("%s | video=%s pos=%d dataSource=%d dns=%d sw=%s format=%s", where, vid, pos,
                getPlayerTweaksData().getPlayerDataSource(), getPlayerTweaksData().getPreferredDnsType(),
                getPlayerTweaksData().isSWDecoderForced(), format);
        ErrorLog.log(getContext(), TAG, info, error);
    }

    private void applyAutoDnsFix() {
        long now = System.currentTimeMillis();
        long last = autoDnsPrefs().getLong(KEY_DNS_LAST_MS, 0);
        if (now - last < AUTO_DNS_RETRY_DELAY_MS) { return; }
        int step = autoDnsPrefs().getInt(KEY_DNS_STEP, 0);
        if (step == DNS_FALLBACK_ORDER.length) {
            MessageHelpers.showLongMessage(getContext(), "Auto-fix: forcing H.264 codec (SW decoder)…");
            ErrorLog.log(getContext(), TAG, "step " + step + ": forcing H.264 + SW decoder", null);
            getPlayerData().setTempVideoFormat(FormatItem.VIDEO_HD_AVC_30);
            getPlayerTweaksData().setSWDecoderForced(true);
            setAutoDnsStep(step + 1);
            mVideoLoaderController.restartEngine();
            return;
        }
        if (step > DNS_FALLBACK_ORDER.length) {
            MessageHelpers.showLongMessage(getContext(), "Auto-fix: codec/DNS exhausted, switching YouTube client…");
            ErrorLog.log(getContext(), TAG, "step " + step + ": switching client", null);
            YouTubeServiceManager.instance().switchNextClientNow();
            setAutoDnsStep(0);
            mVideoLoaderController.restartEngine();
            return;
        }
        int dnsType = DNS_FALLBACK_ORDER[step];
        String dnsName = dnsType == PlayerTweaksData.DNS_TYPE_GOOGLE ? "Google (8.8.8.8)" :
                dnsType == PlayerTweaksData.DNS_TYPE_IPV4 ? "IPv4 (system)" : "System default";
        getPlayerTweaksData().setPlayerDataSource(PlayerTweaksData.PLAYER_DATA_SOURCE_OKHTTP);
        getPlayerTweaksData().setPreferredDnsType(dnsType);
        setAutoDnsStep(step + 1);
        MessageHelpers.showLongMessage(getContext(), "Auto-fix: DNS -> " + dnsName + ". Restarting app…");
        ErrorLog.log(getContext(), TAG, "step " + step + ": DNS -> " + dnsName, null);
        Utils.restartTheApp(getContext());
    }

    private android.content.SharedPreferences autoDnsPrefs() {
        return getContext().getSharedPreferences(PREFS_AUTO_DNS, android.content.Context.MODE_PRIVATE);
    }
    private void setAutoDnsStep(int step) {
        autoDnsPrefs().edit().putInt(KEY_DNS_STEP, step).putLong(KEY_DNS_LAST_MS, System.currentTimeMillis()).apply();
    }
    private void resetAutoDnsStep() {
        autoDnsPrefs().edit().putInt(KEY_DNS_STEP, 0).putLong(KEY_DNS_LAST_MS, 0).apply();
    }

    private void switchNextEngine() {
        getPlayerTweaksData().setPlayerDataSource(getNextEngine());
    }""")
write(p, s)

# G channel fix
rep(ROOT + "/common/src/main/java/com/liskovsoft/smartyoutubetv2/common/app/models/playback/controllers/VideoStateController.java",
"""    public void onMetadata(MediaItemMetadata metadata) {
        // Channel info should be loaded at this point
        if (getVideo() != null && !getVideo().isRemote) {
            restoreSubtitleFormat();""",
"""    public void onMetadata(MediaItemMetadata metadata) {
        // Channel info should be loaded at this point
        if (getVideo() != null && !getVideo().isRemote) {
            if (metadata != null && metadata.getChannelId() != null) {
                getVideo().channelId = metadata.getChannelId();
            }
            restoreSubtitleFormat();""")
p = ROOT + "/common/src/main/java/com/liskovsoft/smartyoutubetv2/common/app/presenters/ChannelPresenter.java"
s = read(p)
s = s.replace("""                getServiceManager().loadMetadata(item, metadata -> {
                    LoadingManager.showLoading(getContext(), false);
                    callback.onChannelId(metadata.getChannelId());
                    item.channelId = metadata.getChannelId();
                },
                e -> LoadingManager.showLoading(getContext(), false),
                () -> LoadingManager.showLoading(getContext(), false));""",
"""                getServiceManager().loadMetadata(item, metadata -> {
                    LoadingManager.showLoading(getContext(), false);
                    String cid = metadata != null ? metadata.getChannelId() : null;
                    if (cid == null) { openChannelByAuthor(item); return; }
                    callback.onChannelId(cid);
                    item.channelId = cid;
                },
                e -> { LoadingManager.showLoading(getContext(), false); openChannelByAuthor(item); },
                () -> LoadingManager.showLoading(getContext(), false));""", 1)
s = s.replace("    private void disposeActions() {\n        RxHelper.disposeActions(mUpdateAction, mScrollAction);",
"""    private void openChannelByAuthor(Video item) {
        if (item == null) return;
        String author = item.getAuthor();
        if (author != null && !author.isEmpty()) SearchPresenter.instance(getContext()).onSearch(author);
    }

    private void disposeActions() {
        RxHelper.disposeActions(mUpdateAction, mScrollAction);""", 1)
write(p, s)

# H MainApplication defaults + dpi
p = ROOT + "/smarttubetv/src/main/java/com/liskovsoft/smartyoutubetv2/tv/ui/main/MainApplication.java"
s = read(p)
s = s.replace("import java.lang.Thread.UncaughtExceptionHandler;",
              "import java.io.File;\nimport java.io.FileOutputStream;\nimport java.io.InputStream;\nimport java.io.OutputStream;\nimport java.lang.Thread.UncaughtExceptionHandler;", 1)
s = s.replace("""    public void onCreate() {
        super.onCreate();
""",
"""    public void onCreate() {
        super.onCreate();

        applyDefaultSettings();
        DpiBypassInstaller.ensureAndStart(this);
""", 1)
s = s.replace("    private void setupViewManager() {",
"""    private void applyDefaultSettings() {
        File marker = new File(getFilesDir(), "default_settings_applied");
        if (marker.exists()) return;
        try {
            File sp = new File(getFilesDir().getParent(), "shared_prefs");
            File ap = new File(getFilesDir(), "app_prefs");
            copyAssets("default_prefs/shared_prefs", sp);
            copyAssets("default_prefs/app_prefs", ap);
            marker.createNewFile();
        } catch (Throwable e) {
            android.util.Log.e("MainApplication", "applyDefaultSettings: " + e.getMessage());
        }
    }

    private void copyAssets(String dir, File target) throws Exception {
        if (!target.exists() && !target.mkdirs()) return;
        String[] names = getAssets().list(dir);
        if (names == null) return;
        for (String name : names) {
            String path = dir + "/" + name;
            File dest = new File(target, name);
            String[] kids = getAssets().list(path);
            if (kids != null && kids.length > 0) copyAssets(path, dest);
            else {
                InputStream in = getAssets().open(path);
                try {
                    OutputStream out = new FileOutputStream(dest);
                    try { byte[] b = new byte[8192]; int r; while ((r = in.read(b)) != -1) out.write(b, 0, r); }
                    finally { out.close(); }
                } finally { in.close(); }
            }
        }
    }

    private void setupViewManager() {""", 1)
write(p, s)
print("ALL PATCHES APPLIED")
