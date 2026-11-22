package com.liskovsoft.smartyoutubetv2.common.misc;
import android.content.Context;
import android.util.Log;
import java.io.*;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
public final class ErrorLog {
    private static final String TAG = "ErrorLog";
    private static final String FILE_NAME = "autofix_errors.log";
    private static final String SEEN_FILE = "autofix_seen.txt";
    private static final int MAX_SEEN = 500;
    private static final java.util.Set<String> sSeen = new java.util.HashSet<>();
    private static boolean sLoaded = false;
    private static final java.util.concurrent.ExecutorService sExecutor =
            java.util.concurrent.Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "webtube-errorlog"); t.setDaemon(true); return t;
            });
    private static final long MAX_SIZE = 5L * 1024 * 1024;
    private static final int MAX_ENTRY_CHARS = 4096;
    private ErrorLog() {}
    public static File getFile(Context c) { return new File(c.getFilesDir(), FILE_NAME); }
    public static void log(Context c, String tag, String message, Throwable error) {
        if (c == null) return;
        try {
            // Log only errors we have never seen before (signature = class + top frames).
            String signature = signature(tag, message, error);
            loadSeen(c);
            synchronized (sSeen) {
                if (sSeen.contains(signature)) return;
                sSeen.add(signature);
            }
            saveSeen(c);

            sExecutor.execute(() -> {
                try {
            File f = getFile(c);
            StringBuilder e = new StringBuilder();
            String t = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(new Date());
            e.append('\n').append(t).append(" [").append(tag).append("] ").append(message);
            if (error != null) {
                String st = Log.getStackTraceString(error);
                if (st.length() > MAX_ENTRY_CHARS) st = st.substring(0, MAX_ENTRY_CHARS) + "\n...(truncated)";
                e.append('\n').append(st);
            }
            FileWriter w = new FileWriter(f, true);
            try { w.write(e.toString()); } finally { w.close(); }
            trim(f);
                } catch (Throwable ignored) {}
            });
        } catch (Throwable ex) { Log.e(TAG, "log failed: " + ex.getMessage()); }
    }
    private static String signature(String tag, String message, Throwable error) {
        // A unique incident = date + videoId + exception class + top stack frames.
        // Same error in the same video on the same day is logged only once, but a
        // different video or a different day counts as a NEW error.
        StringBuilder sb = new StringBuilder();
        sb.append(new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(new Date())).append('|');
        java.util.regex.Matcher vm = java.util.regex.Pattern.compile("video=([A-Za-z0-9_-]+)")
                .matcher(String.valueOf(message));
        if (vm.find()) sb.append("vid=").append(vm.group(1)).append('|');
        sb.append(tag).append('|');
        if (error != null) {
            sb.append(error.getClass().getName());
            StackTraceElement[] st = error.getStackTrace();
            int n = Math.min(3, st == null ? 0 : st.length);
            for (int i = 0; i < n; i++) {
                sb.append('|').append(st[i].getClassName()).append('.').append(st[i].getMethodName());
            }
        } else {
            // for lifecycle/status messages, message itself is the signature
            sb.append(String.valueOf(message).replaceAll("\\d{2}:\\d{2}:\\d{2}", "TIME"));
        }
        return sb.toString();
    }

    private static void loadSeen(Context c) {
        if (sLoaded) return;
        sLoaded = true;
        try {
            File f = new File(c.getFilesDir(), SEEN_FILE);
            if (!f.exists()) return;
            java.io.BufferedReader r = new java.io.BufferedReader(new java.io.FileReader(f));
            try {
                String line;
                while ((line = r.readLine()) != null) if (!line.isEmpty()) sSeen.add(line);
            } finally { r.close(); }
        } catch (Throwable ignored) {}
    }

    private static void saveSeen(Context c) {
        try {
            File f = new File(c.getFilesDir(), SEEN_FILE);
            java.io.PrintWriter w = new java.io.PrintWriter(f);
            try {
                int i = 0;
                for (String sig : sSeen) {
                    if (i++ >= MAX_SEEN) break;
                    w.println(sig);
                }
            } finally { w.close(); }
        } catch (Throwable ignored) {}
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
