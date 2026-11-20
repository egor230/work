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
            e.append('\n').append(t).append(" [").append(tag).append("] ").append(message);
            if (error != null) {
                String st = Log.getStackTraceString(error);
                if (st.length() > MAX_ENTRY_CHARS) st = st.substring(0, MAX_ENTRY_CHARS) + "\n...(truncated)";
                e.append('\n').append(st);
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
