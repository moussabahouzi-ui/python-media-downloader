package com.mediahub.app

import android.app.PictureInPictureParams
import android.content.res.Configuration
import android.os.Build
import android.util.Rational
import com.mediahub.app.bridge.EngineMethodChannel
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * The single Flutter host activity.
 *
 * On engine attachment it registers the [EngineMethodChannel] which owns the
 * Dart ↔ Kotlin ↔ Python bridge, plus a Picture-in-Picture method + event
 * channel for Phase 5 video playback.
 *
 * PiP is supported on Android 8.0+ (API 26). The activity enters PiP mode when
 * the user navigates away from the video player; an event channel notifies
 * Flutter of PiP mode transitions so the UI can hide controls.
 */
class MainActivity : FlutterActivity(), MethodChannel.MethodCallHandler {

    private val bridge = EngineMethodChannel()
    private var pipEventSink: EventChannel.EventSink? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        bridge.attach(
            messenger = flutterEngine.dartExecutor.binaryMessenger,
            context = this,
        )

        // PiP method channel
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.mediahub.app/pip")
            .setMethodCallHandler(this)

        // PiP event channel — streams mode transitions to Flutter.
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, "com.mediahub.app/pip/events")
            .setStreamHandler(object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    pipEventSink = events
                    events?.success(isInPipMode())
                }
                override fun onCancel(arguments: Any?) {
                    pipEventSink = null
                }
            })
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        bridge.detach()
        super.cleanUpFlutterEngine(flutterEngine)
    }

    // ---- PiP method channel handler ----

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "isPipSupported" -> result.success(isPipSupported())
            "enterPipMode" -> result.success(enterPipMode())
            "isInPipMode" -> result.success(isInPipMode())
            else -> result.notImplemented()
        }
    }

    private fun isPipSupported(): Boolean {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && packageManager
            .hasSystemFeature(android.content.pm.PackageManager.FEATURE_PICTURE_IN_PICTURE)
    }

    private fun isInPipMode(): Boolean {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && isInPictureInPictureMode
    }

    @Suppress("DEPRECATION")
    private fun enterPipMode(): Boolean {
        if (!isPipSupported()) return false
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val params = PictureInPictureParams.Builder()
                .setAspectRatio(Rational(16, 9))
                .build()
            try {
                enterPictureInPictureMode(params)
                true
            } catch (e: IllegalStateException) {
                false
            }
        } else {
            // Legacy API (pre-O), deprecated but harmless.
            enterPictureInPictureMode()
            true
        }
    }

    // ---- PiP mode change notification ----

    override fun onPictureInPictureModeChanged(
        isInPicInPicMode: Boolean,
        newConfig: Configuration,
    ) {
        super.onPictureInPictureModeChanged(isInPicInPicMode, newConfig)
        pipEventSink?.success(isInPicInPicMode)
    }

    companion object {
        private const val TAG = "MainActivity"
    }
}
