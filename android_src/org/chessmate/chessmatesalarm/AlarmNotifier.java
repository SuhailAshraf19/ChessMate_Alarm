package org.chessmate.chessmatesalarm;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

public final class AlarmNotifier {
    private static final String CHANNEL_ID = "chessmate_alarm_channel";
    private static final String CHANNEL_NAME = "ChessMate Alarms";
    private static final String TAG = "AlarmNotifier";

    private AlarmNotifier() {
    }

    public static void show(Context context, Intent triggerIntent) {
        if (context == null || triggerIntent == null) {
            return;
        }
        Log.i(TAG, "showing alarm notification directly");
        String ringtonePath = triggerIntent.getStringExtra("ringtone_path");
        AlarmRinger.start(context.getApplicationContext(), ringtonePath);

        int alarmId = triggerIntent.getIntExtra("alarm_id", 0);
        String label = triggerIntent.getStringExtra("alarm_label");
        if (label == null || label.isEmpty()) {
            label = "Alarm";
        }

        Notification notification = buildNotification(context, triggerIntent, label, alarmId);
        NotificationManager manager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(alarmId, notification);
        }
    }

    public static Notification buildNotification(Context context, Intent triggerIntent, String label, int alarmId) {
        createChannel(context);

        Intent fullScreenIntent = buildLaunchIntent(context, triggerIntent, "ringing");
        Intent contentIntent = buildLaunchIntent(context, triggerIntent, "puzzle");

        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }

        PendingIntent fullScreenPendingIntent = PendingIntent.getActivity(
                context,
                alarmId,
                fullScreenIntent,
                flags
        );
        PendingIntent contentPendingIntent = PendingIntent.getActivity(
                context,
                alarmId + 100000,
                contentIntent,
                flags
        );

        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= 26) {
            builder = new Notification.Builder(context, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(context);
        }

        builder.setSmallIcon(context.getApplicationInfo().icon);
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

    private static Intent buildLaunchIntent(Context context, Intent triggerIntent, String openScreen) {
        Intent launchIntent = new Intent();
        launchIntent.setClassName(context.getPackageName(), "org.kivy.android.PythonActivity");
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

    public static void cancel(Context context, int alarmId) {
        if (context == null) {
            return;
        }
        NotificationManager manager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.cancel(alarmId);
        }
    }

    private static void createChannel(Context context) {
        if (Build.VERSION.SDK_INT < 26) {
            return;
        }

        NotificationManager manager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
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
}
