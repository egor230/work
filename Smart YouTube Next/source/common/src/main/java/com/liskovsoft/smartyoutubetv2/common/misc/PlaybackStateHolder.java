package com.liskovsoft.smartyoutubetv2.common.misc;

/** Shared flag: is a video currently playing (including background playback). */
public final class PlaybackStateHolder {
    private static volatile boolean sActive = false;
    private static volatile Runnable sListener = null;
    private PlaybackStateHolder() {}
    public static boolean isActive() { return sActive; }
    public static void setActive(boolean active) {
        sActive = active;
        Runnable l = sListener;
        if (l != null) { try { l.run(); } catch (Throwable ignored) {} }
    }
    public static void setListener(Runnable listener) { sListener = listener; }
}
