import io, sys
ROOT = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/android-tv-emu/SmartTubeDNS"
p = ROOT + "/smarttubetv/src/main/java/com/liskovsoft/smartyoutubetv2/tv/ui/main/DpiBypassInstaller.java"
s = io.open(p, encoding="utf-8").read()

def rep(o, n):
    global s
    if o not in s:
        print("NOT FOUND:", o[:90]); sys.exit(1)
    s = s.replace(o, n, 1)

# make installOnce callable from Application and add start/stop API
rep("    private static void installOnce(Context context) throws Exception {",
    "    public static void installOnce(Context context) throws Exception {")

rep("""    public static void ensureAndStart(Context context) {
        try {
            if (!hasRoot()) {
                ErrorLog.log(context, TAG, "no root available — DPI bypass skipped", null);
                return;
            }
            installOnce(context);
            String status = runRootWithOutput("LD_LIBRARY_PATH=" + LIBDIR + " " + BIN + " status");
            if (status == null || !status.contains("working")) {
                String out = runRootWithOutput("LD_LIBRARY_PATH=" + LIBDIR + " " + BIN + " start");
                ErrorLog.log(context, TAG, "nfqws start: " + out.trim(), null);
            }
        } catch (Throwable e) {
            ErrorLog.log(context, TAG, "DPI bypass failed", e);
        }
    }""",
"""    /** Start the bypass. Called when the app comes to foreground. */
    public static void start(Context context) {
        try {
            if (!hasRoot()) {
                ErrorLog.log(context, TAG, "no root available — DPI bypass skipped", null);
                return;
            }
            installOnce(context);
            String status = runRootWithOutput("LD_LIBRARY_PATH=" + LIBDIR + " " + BIN + " status");
            if (status == null || !status.contains("working")) {
                String out = runRootWithOutput("LD_LIBRARY_PATH=" + LIBDIR + " " + BIN + " start");
                ErrorLog.log(context, TAG, "nfqws START (app foreground): " + out.trim(), null);
            }
        } catch (Throwable e) {
            ErrorLog.log(context, TAG, "DPI bypass start failed", e);
        }
    }

    /** Stop the bypass. Called when the app goes to background. */
    public static void stop(Context context) {
        try {
            if (!hasRoot()) {
                return;
            }
            String status = runRootWithOutput("LD_LIBRARY_PATH=" + LIBDIR + " " + BIN + " status");
            if (status != null && status.contains("working")) {
                String out = runRootWithOutput("LD_LIBRARY_PATH=" + LIBDIR + " " + BIN + " stop");
                ErrorLog.log(context, TAG, "nfqws STOP (app background): " + out.trim(), null);
            }
        } catch (Throwable e) {
            ErrorLog.log(context, TAG, "DPI bypass stop failed", e);
        }
    }""")
io.open(p, "w", encoding="utf-8").write(s)

# MainApplication: install once + lifecycle callbacks
p = ROOT + "/smarttubetv/src/main/java/com/liskovsoft/smartyoutubetv2/tv/ui/main/MainApplication.java"
s = io.open(p, encoding="utf-8").read()
s = s.replace("import android.os.Build.VERSION;",
              "import android.app.Activity;\nimport android.app.Application;\nimport android.os.Build.VERSION;\nimport android.os.Bundle;", 1)
s = s.replace("""        applyDefaultSettings();
        DpiBypassInstaller.ensureAndStart(this);
""",
"""        applyDefaultSettings();
        // DPI bypass follows the app lifecycle: only while YouTube is open.
        try {
            if (android.os.Process.myUid() == 0 || isRootAvailable()) {
                DpiBypassInstaller.installOnce(this);
            }
        } catch (Throwable ignored) {}
        registerActivityLifecycleCallbacks(new ActivityLifecycleCallbacks() {
            private int mResumed = 0;
            @Override public void onActivityResumed(Activity activity) {
                if (mResumed++ == 0) { DpiBypassInstaller.start(activity); }
            }
            @Override public void onActivityPaused(Activity activity) {
                if (--mResumed <= 0) { mResumed = 0; DpiBypassInstaller.stop(activity); }
            }
            @Override public void onActivityCreated(Activity a, Bundle b) {}
            @Override public void onActivityStarted(Activity a) {}
            @Override public void onActivityStopped(Activity a) {}
            @Override public void onActivitySaveInstanceState(Activity a, Bundle b) {}
            @Override public void onActivityDestroyed(Activity a) {}
        });
""", 1)
s = s.replace("    private void applyDefaultSettings() {",
"""    private boolean isRootAvailable() {
        try {
            Process p = Runtime.getRuntime().exec(new String[]{"su", "-c", "id -u"});
            byte[] b = new byte[32];
            int n = p.getInputStream().read(b);
            p.waitFor();
            return n > 0 && new String(b, 0, n).trim().startsWith("0");
        } catch (Throwable e) {
            return false;
        }
    }

    private void applyDefaultSettings() {""", 1)
io.open(p, "w", encoding="utf-8").write(s)
print("LIFECYCLE PATCHED")
