package org.chessmate.chessmatesalarm;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.media.Ringtone;
import android.media.RingtoneManager;
import android.os.Build;
import android.os.PowerManager;
import android.net.Uri;
import android.util.Log;

import java.io.IOException;

public final class AlarmRinger {
    private static final String SYSTEM_ALARM_TOKEN = "system_alarm_tone";
    private static MediaPlayer player;
    private static Ringtone ringtone;

    private AlarmRinger() {
    }

    public static synchronized boolean start(Context context, String path) {
        stop();

        if (context == null) {
            Log.w("AlarmRinger", "start called with null context");
            return false;
        }

        if (path == null) {
            path = "";
        }

        try {
            if (SYSTEM_ALARM_TOKEN.equals(path)) {
                Log.i("AlarmRinger", "starting alarm from device alarm tone");
                if (tryStartFromSystemRingtone(context)) {
                    return true;
                }
                if (tryStartFromDefaultAlarm(context)) {
                    return true;
                }
            }
            if (tryStartFromPath(context, path)) {
                return true;
            }
            Log.w("AlarmRinger", "primary ringtone path failed, trying system alarm tone");
            if (tryStartFromDefaultAlarm(context)) {
                return true;
            }
            if (tryStartFromSystemRingtone(context)) {
                return true;
            }
        } catch (Exception ex) {
            Log.e("AlarmRinger", "unexpected failure while starting alarm", ex);
        }

        stop();
        return false;
    }

    private static boolean tryStartFromPath(Context context, String path) {
        if (path.isEmpty()) {
            Log.w("AlarmRinger", "empty ringtone path");
            return false;
        }
        try {
            if (SYSTEM_ALARM_TOKEN.equals(path)) {
                return false;
            }
            Log.i("AlarmRinger", "starting alarm from path: " + path);
            if (path.startsWith("content:") || path.startsWith("android.resource:")) {
                return tryStartFromUri(context, Uri.parse(path));
            }
            MediaPlayer mediaPlayer = configurePlayer(context);
            mediaPlayer.setDataSource(path);
            mediaPlayer.prepare();
            mediaPlayer.start();
            player = mediaPlayer;
            return true;
        } catch (IOException | IllegalArgumentException | IllegalStateException ex) {
            Log.e("AlarmRinger", "failed to start alarm from path: " + path, ex);
            stop();
            return false;
        }
    }

    private static boolean tryStartFromUri(Context context, Uri alarmUri) {
        if (alarmUri == null) {
            return false;
        }
        try {
            Log.i("AlarmRinger", "starting alarm from uri: " + alarmUri);
            MediaPlayer mediaPlayer = configurePlayer(context);
            mediaPlayer.setDataSource(context.getApplicationContext(), alarmUri);
            mediaPlayer.prepare();
            mediaPlayer.start();
            player = mediaPlayer;
            return true;
        } catch (IOException | IllegalArgumentException | IllegalStateException ex) {
            Log.e("AlarmRinger", "failed to start alarm from uri: " + alarmUri, ex);
            stop();
            return false;
        }
    }

    private static boolean tryStartFromDefaultAlarm(Context context) {
        try {
            Uri alarmUri = RingtoneManager.getActualDefaultRingtoneUri(
                    context,
                    RingtoneManager.TYPE_ALARM
            );
            if (alarmUri == null) {
                alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            }
            if (alarmUri == null) {
                Log.w("AlarmRinger", "system alarm uri is null");
                return false;
            }
            Log.i("AlarmRinger", "starting alarm from system default tone: " + alarmUri);
            MediaPlayer mediaPlayer = configurePlayer(context);
            mediaPlayer.setDataSource(context.getApplicationContext(), alarmUri);
            mediaPlayer.prepare();
            mediaPlayer.start();
            player = mediaPlayer;
            return true;
        } catch (IOException | IllegalArgumentException | IllegalStateException ex) {
            Log.e("AlarmRinger", "failed to start system default alarm tone", ex);
            stop();
            return false;
        }
    }

    private static boolean tryStartFromSystemRingtone(Context context) {
        try {
            Uri alarmUri = RingtoneManager.getActualDefaultRingtoneUri(
                    context,
                    RingtoneManager.TYPE_ALARM
            );
            if (alarmUri == null) {
                alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            }
            if (alarmUri == null) {
                Log.w("AlarmRinger", "system ringtone uri is null");
                return false;
            }

            Log.i("AlarmRinger", "starting alarm via Ringtone API: " + alarmUri);
            Ringtone r = RingtoneManager.getRingtone(context.getApplicationContext(), alarmUri);
            if (r == null) {
                Log.w("AlarmRinger", "RingtoneManager returned null ringtone");
                return false;
            }
            try {
                r.setStreamType(AudioManager.STREAM_ALARM);
            } catch (Exception ignored) {
            }
            r.play();
            ringtone = r;
            return true;
        } catch (Exception ex) {
            Log.e("AlarmRinger", "failed to start alarm via Ringtone API", ex);
            stop();
            return false;
        }
    }

    private static MediaPlayer configurePlayer(Context context) {
        MediaPlayer mediaPlayer = new MediaPlayer();
        if (Build.VERSION.SDK_INT >= 21) {
            AudioAttributes attrs = new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build();
            mediaPlayer.setAudioAttributes(attrs);
        } else {
            mediaPlayer.setAudioStreamType(AudioManager.STREAM_ALARM);
        }

        mediaPlayer.setWakeMode(context.getApplicationContext(), PowerManager.PARTIAL_WAKE_LOCK);
        mediaPlayer.setLooping(true);
        return mediaPlayer;
    }

    public static synchronized void stop() {
        if (player != null) {
            try {
                if (player.isPlaying()) {
                    player.stop();
                }
            } catch (Exception ignored) {
            }

            try {
                player.release();
            } catch (Exception ignored) {
            }

            player = null;
        }
        if (ringtone != null) {
            try {
                ringtone.stop();
            } catch (Exception ignored) {
            }
            ringtone = null;
        }
    }

    public static synchronized boolean isPlaying() {
        return (player != null && player.isPlaying()) || ringtone != null;
    }
}
