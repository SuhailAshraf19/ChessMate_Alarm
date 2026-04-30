package org.chessmate.chessmatesalarm;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;
import android.content.SharedPreferences;

public class AlarmForegroundService extends Service {
    public static final String ACTION_START = "org.chessmate.chessmatesalarm.action.START";
    public static final String ACTION_STOP = "org.chessmate.chessmatesalarm.action.STOP";
    private static final String TAG = "AlarmForegroundSvc";
    private static final String CHANNEL_ID = "chessmate_alarm_channel";
    private static final String CHANNEL_NAME = "ChessMate Alarms";
    private static final String PREFS_NAME = "chessmate_alarm_state";
    private static final String PREF_PLAYING = "playing";
    private static final String PREF_ALARM_ID = "alarm_id";

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "service created");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) {
            Log.w(TAG, "onStartCommand received null intent");
            return START_NOT_STICKY;
        }

        String action = intent.getAction();
        if (ACTION_STOP.equals(action)) {
            Log.i(TAG, "received stop action");
            int alarmId = intent.getIntExtra("alarm_id", 0);
            stopAlarm(alarmId);
            return START_NOT_STICKY;
        }

        if (!ACTION_START.equals(action)) {
            Log.w(TAG, "ignoring unknown action: " + action);
            return START_NOT_STICKY;
        }

        startAlarm(intent);
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        Log.i(TAG, "service destroyed");
        try {
            AlarmRinger.stop();
        } catch (Exception ignored) {
        }
        setState(false, 0);
        super.onDestroy();
    }

    private void startAlarm(Intent triggerIntent) {
        int alarmId = triggerIntent.getIntExtra("alarm_id", 1);
        String label = triggerIntent.getStringExtra("alarm_label");
        if (label == null || label.isEmpty()) {
            label = "Alarm";
        }

        Log.i(TAG, "starting alarm " + alarmId);
        createChannel();
        Notification notification = AlarmNotifier.buildNotification(this, triggerIntent, label, alarmId);
        startForeground(alarmId, notification);

        String ringtonePath = triggerIntent.getStringExtra("ringtone_path");
        boolean playing = AlarmRinger.start(getApplicationContext(), ringtonePath);
        setState(playing, alarmId);
        Log.i(TAG, "started foreground alarm service for alarm " + alarmId + ", playing=" + playing);
    }

    private void stopAlarm(int alarmId) {
        try {
            AlarmRinger.stop();
        } catch (Exception ignored) {
        }

        try {
            NotificationManager manager =
                    (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                if (alarmId > 0) {
                    manager.cancel(alarmId);
                } else {
                    manager.cancelAll();
                }
            }
        } catch (Exception ignored) {
        }

        try {
            stopForeground(true);
        } catch (Exception ignored) {
        }

        setState(false, 0);
        stopSelf();
        Log.i(TAG, "stopped foreground alarm service for alarm " + alarmId);
    }

    public static boolean isPlaying(Context context, int alarmId) {
        if (context == null) {
            return false;
        }
        try {
            SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
            return prefs.getBoolean(PREF_PLAYING, false) && prefs.getInt(PREF_ALARM_ID, 0) == alarmId;
        } catch (Exception ignored) {
            return false;
        }
    }

    private void setState(boolean playing, int alarmId) {
        try {
            SharedPreferences prefs = getApplicationContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
            SharedPreferences.Editor editor = prefs.edit();
            editor.putBoolean(PREF_PLAYING, playing);
            editor.putInt(PREF_ALARM_ID, alarmId);
            editor.apply();
        } catch (Exception ignored) {
        }
    }

    private Notification buildNotification(Intent triggerIntent, String label, int alarmId) {
        Intent fullScreenIntent = buildLaunchIntent(triggerIntent, "ringing");
        Intent contentIntent = buildLaunchIntent(triggerIntent, "puzzle");

        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }

        PendingIntent fullScreenPendingIntent = PendingIntent.getActivity(
                this,
                alarmId,
                fullScreenIntent,
                flags
        );
        PendingIntent contentPendingIntent = PendingIntent.getActivity(
                this,
                alarmId + 100000,
                contentIntent,
                flags
        );

        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= 26) {
            builder = new Notification.Builder(this, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(this);
        }

        builder.setSmallIcon(getApplicationInfo().icon);
        builder.setContentTitle("ChessMate Alarm");
        builder.setContentText(label);
        builder.setCategory(Notification.CATEGORY_ALARM);
        builder.setPriority(Notification.PRIORITY_MAX);
        builder.setVisibility(Notification.VISIBILITY_PUBLIC);
        builder.setOngoing(true);
        builder.setAutoCancel(false);
        builder.setOnlyAlertOnce(true);
        builder.setFullScreenIntent(fullScreenPendingIntent, true);
        builder.setContentIntent(contentPendingIntent);

        return builder.build();
    }

    private Intent buildLaunchIntent(Intent triggerIntent, String openScreen) {
        Intent launchIntent = new Intent();
        launchIntent.setClassName(getPackageName(), "org.kivy.android.PythonActivity");
        launchIntent.setAction(Intent.ACTION_MAIN);
        launchIntent.addCategory(Intent.CATEGORY_LAUNCHER);
        launchIntent.addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK
                        | Intent.FLAG_ACTIVITY_CLEAR_TOP
                        | Intent.FLAG_ACTIVITY_SINGLE_TOP
                        | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
        );
        if (triggerIntent != null) {
            launchIntent.putExtras(triggerIntent);
        }
        launchIntent.putExtra("open_screen", openScreen);
        return launchIntent;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < 26) {
            return;
        }

        NotificationManager manager =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }

        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
        );
        channel.setDescription("Alarm and reminder alerts");
        channel.enableVibration(true);
        channel.enableLights(true);
        manager.createNotificationChannel(channel);
    }

    public static boolean start(Context context, Intent triggerIntent) {
        if (context == null || triggerIntent == null) {
            return false;
        }

        Intent serviceIntent = new Intent(context, AlarmForegroundService.class);
        serviceIntent.setAction(ACTION_START);
        serviceIntent.putExtras(triggerIntent);

        try {
            if (Build.VERSION.SDK_INT >= 26) {
                context.startForegroundService(serviceIntent);
            } else {
                context.startService(serviceIntent);
            }
            Log.i(TAG, "start requested");
            return true;
        } catch (Exception ex) {
            Log.e(TAG, "failed to start foreground service", ex);
            return false;
        }
    }

    public static void stop(Context context, int alarmId) {
        if (context == null) {
            return;
        }

        Intent serviceIntent = new Intent(context, AlarmForegroundService.class);
        serviceIntent.setAction(ACTION_STOP);
        serviceIntent.putExtra("alarm_id", alarmId);
        context.startService(serviceIntent);
    }
}
