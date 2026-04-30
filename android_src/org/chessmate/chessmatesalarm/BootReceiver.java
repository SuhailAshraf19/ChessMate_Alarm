package org.chessmate.chessmatesalarm;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

public class BootReceiver extends BroadcastReceiver {
    private static final String TAG = "ChessMateBoot";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (context == null || intent == null) {
            return;
        }

        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)) {
            return;
        }

        try {
            boolean started = false;
            try {
                Class<?> serviceClass = Class.forName(
                        "org.chessmate.chessmatesalarm.ServiceAlarmservice"
                );
                serviceClass.getMethod("start", Context.class, String.class)
                        .invoke(null, context, "");
                started = true;
            } catch (Exception ignored) {
                // Fall through to explicit service start below.
            }

            if (!started) {
                Intent serviceIntent = new Intent(context, ServiceAlarmservice.class);
                if (Build.VERSION.SDK_INT >= 26) {
                    context.startForegroundService(serviceIntent);
                } else {
                    context.startService(serviceIntent);
                }
            }

            Log.i(TAG, "BootReceiver started alarm service after boot");
        } catch (Exception ex) {
            Log.e(TAG, "Failed to start alarm service after boot", ex);
        }
    }
}
