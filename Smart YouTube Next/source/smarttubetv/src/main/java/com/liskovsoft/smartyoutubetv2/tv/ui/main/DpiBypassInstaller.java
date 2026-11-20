package com.liskovsoft.smartyoutubetv2.tv.ui.main;

import android.content.Context;
import android.util.Log;

import com.liskovsoft.smartyoutubetv2.common.misc.ErrorLog;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Installs and starts the DPI bypass engine (nfqws from zaprett) alongside the app.
 * Extracts arm64 binaries from assets on first run, writes config/strategy/lists
 * to /storage/emulated/0/zaprett and starts the service via root (Magisk su).
 */
public final class DpiBypassInstaller {
    private static final String TAG = "DpiBypass";
    private static final String MODULE = "/data/adb/modules/zaprett";
    private static final String DATA = "/storage/emulated/0/zaprett";
    private static final String BIN = MODULE + "/system/bin/zaprett";
    private static final String LIBDIR = MODULE + "/system/lib/arm64-v8a";

    private DpiBypassInstaller() {}

    public static void ensureAndStart(Context context) {
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
    }

    private static void installOnce(Context context) throws Exception {
        File marker = new File(context.getFilesDir(), "dpi_bypass_installed");
        if (marker.exists()) {
            return;
        }

        File staging = new File(context.getFilesDir(), "dpi_staging");
        copyAssets(context, "dpi", staging);

        // sdcard part: write to staging first, then copy via root (scoped storage
        // forbids direct writes to /storage/emulated/0 from a normal app).
        writeConfig(new File(staging, "config.json").getAbsolutePath());
        writeManifest(new File(staging, "manifest.json").getAbsolutePath());
        sh("mkdir -p " + DATA + "/files/bin " + DATA + "/files/lists " + DATA + "/strategies " + DATA + "/manifests/strategies");
        sh("cp " + new File(staging, "config.json").getAbsolutePath() + " " + DATA + "/config.json");
        sh("cp " + new File(staging, "manifest.json").getAbsolutePath() + " " + DATA + "/manifests/strategies/general_alt12.json");
        sh("cp " + new File(staging, "strategy.txt").getAbsolutePath() + " " + DATA + "/strategies/general_alt12.txt");
        copyDir(new File(staging, "bin"), DATA + "/files/bin");
        copyDir(new File(staging, "lists"), DATA + "/files/lists");

        // root part (Magisk module paths)
        sh("mkdir -p " + MODULE + "/system/bin " + LIBDIR);
        sh("cp " + new File(staging, "zaprett-aarch64").getAbsolutePath() + " " + BIN);
        sh("chmod 755 " + BIN);
        sh("cp " + new File(staging, "libnfqws.so").getAbsolutePath() + " " + LIBDIR + "/libnfqws.so");
        sh("cp " + new File(staging, "libnfqws2.so").getAbsolutePath() + " " + LIBDIR + "/libnfqws2.so");
        sh("chmod 644 " + LIBDIR + "/libnfqws.so " + LIBDIR + "/libnfqws2.so");

        marker.createNewFile();
        ErrorLog.log(context, TAG, "installed nfqws + general_alt12 strategy", null);
    }

    private static void writeManifest(String path) throws Exception {
        String json = "{\n"
                + "  \"schema\": 1,\n"
                + "  \"id\": \"general_alt12\",\n"
                + "  \"name\": \"general_alt12\",\n"
                + "  \"version\": \"1.0.0\",\n"
                + "  \"author\": \"egor\",\n"
                + "  \"description\": \"saved working strategy\",\n"
                + "  \"dependencies\": [],\n"
                + "  \"file\": \"" + DATA + "/strategies/general_alt12.txt\"\n"
                + "}\n";
        FileOutputStream out = new FileOutputStream(path);
        try {
            out.write(json.getBytes("UTF-8"));
        } finally {
            out.close();
        }
    }

    private static void writeConfig(String path) throws Exception {
        String json = "{\n"
                + "  \"service_type\": \"nfqws\",\n"
                + "  \"active_lists\": [],\n"
                + "  \"active_ipsets\": [],\n"
                + "  \"active_exclude_lists\": [],\n"
                + "  \"active_exclude_ipsets\": [],\n"
                + "  \"list_type\": \"whitelist\",\n"
                + "  \"strategy\": \"" + DATA + "/manifests/strategies/general_alt12.json\",\n"
                + "  \"strategy_nfqws2\": \"\",\n"
                + "  \"app_list\": \"none\",\n"
                + "  \"whitelist\": [],\n"
                + "  \"blacklist\": []\n"
                + "}\n";
        FileOutputStream out = new FileOutputStream(path);
        try {
            out.write(json.getBytes("UTF-8"));
        } finally {
            out.close();
        }
    }

    private static boolean hasRoot() {
        return runRootWithOutput("id -u").trim().equals("0");
    }

    private static boolean runRoot(String command) {
        try {
            Process p = Runtime.getRuntime().exec(new String[]{"su", "-c", command});
            return p.waitFor() == 0;
        } catch (Throwable e) {
            return false;
        }
    }

    private static String runRootWithOutput(String command) {
        try {
            Process p = Runtime.getRuntime().exec(new String[]{"su", "-c", command});
            byte[] buf = new byte[4096];
            StringBuilder sb = new StringBuilder();
            InputStream in = p.getInputStream();
            int r;
            while ((r = in.read(buf)) != -1) {
                sb.append(new String(buf, 0, r, "UTF-8"));
            }
            p.waitFor();
            return sb.toString();
        } catch (Throwable e) {
            return String.valueOf(e.getMessage());
        }
    }

    private static void sh(String command) throws Exception {
        Process p = Runtime.getRuntime().exec(new String[]{"su", "-c", command});
        int code = p.waitFor();
        if (code != 0) {
            throw new Exception("shell failed: " + command + " (code " + code + ")");
        }
    }

    private static void copyFile(File from, String to) throws Exception {
        sh("cp " + from.getAbsolutePath() + " " + to);
    }

    private static void copyDir(File from, String to) throws Exception {
        File[] files = from.listFiles();
        if (files == null) {
            return;
        }
        for (File f : files) {
            copyFile(f, to + "/" + f.getName());
        }
    }

    private static void copyAssets(Context context, String assetDir, File target) throws Exception {
        if (!target.exists() && !target.mkdirs()) {
            return;
        }
        String[] names = context.getAssets().list(assetDir);
        if (names == null) {
            return;
        }
        for (String name : names) {
            String path = assetDir + "/" + name;
            File dest = new File(target, name);
            String[] children = context.getAssets().list(path);
            if (children != null && children.length > 0) {
                copyAssets(context, path, dest);
            } else {
                InputStream in = context.getAssets().open(path);
                try {
                    OutputStream out = new FileOutputStream(dest);
                    try {
                        byte[] buf = new byte[8192];
                        int r;
                        while ((r = in.read(buf)) != -1) {
                            out.write(buf, 0, r);
                        }
                    } finally {
                        out.close();
                    }
                } finally {
                    in.close();
                }
            }
        }
    }
}
