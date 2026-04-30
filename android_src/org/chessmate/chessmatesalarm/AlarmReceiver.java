package org.chessmate.chessmatesalarm;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class AlarmReceiver extends BroadcastReceiver {
    private static final String TAG = "AlarmReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        Log.i(TAG, "alarm broadcast received");
        boolean started = AlarmForegroundService.start(context, intent);
        if (!started) {
            Log.w(TAG, "foreground service start failed, showing alarm directly");
            AlarmNotifier.show(context, intent);
        }
    }
}
