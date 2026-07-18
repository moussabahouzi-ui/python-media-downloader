package com.mediahub.app.bridge

import android.content.Context
import android.util.Log
import com.mediahub.app.services.DownloadForegroundService
import com.mediahub.app.services.ServiceActions
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.BinaryMessenger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * Wires the Dart method channel [MethodChannelContract.CHANNEL] to the
 * embedded Python runtime, and forwards engine notifications to the event
 * channel [MethodChannelContract.EVENTS_CHANNEL].
 *
 * Lifecycle: registered in [com.mediahub.app.MainActivity]'s Flutter plugin
 * binding. One instance per engine attachment.
 */
class EngineMethodChannel : MethodChannel.MethodCallHandler, EventChannel.StreamHandler {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private var methodChannel: MethodChannel? = null
    private var eventChannel: EventChannel? = null
    private var eventSink: EventChannel.EventSink? = null
    private var appContext: Context? = null

    fun attach(messenger: BinaryMessenger, context: Context) {
        appContext = context.applicationContext

        methodChannel = MethodChannel(
            messenger,
            MethodChannelContract.CHANNEL,
        ).also { it.setMethodCallHandler(this) }

        eventChannel = EventChannel(
            messenger,
            MethodChannelContract.EVENTS_CHANNEL,
        ).also { it.setStreamHandler(this) }

        // Ensure the foreground service (and thus the runtime) is started.
        // Use DownloadForegroundService.start() which handles the
        // startForegroundService / startService split by API level.
        runCatching { DownloadForegroundService.start(context) }
    }

    fun detach() {
        methodChannel?.setMethodCallHandler(null)
        eventChannel?.setStreamHandler(null)
        methodChannel = null
        eventChannel = null
        appContext = null
        eventSink = null
        scope.coroutineContext[kotlinx.coroutines.Job]?.cancel()
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        if (call.method != MethodChannelContract.METHOD_INVOKE) {
            result.error(
                MethodChannelContract.Errors.UNKNOWN_METHOD,
                "Unknown channel method: ${call.method}",
                null,
            )
            return
        }

        when (val parsed = BridgeEnvelopeParser.parse(call.arguments)) {
            is ParsedCall.Invalid -> {
                result.success(BridgeEnvelopeParser.errorEnvelope("", parsed.error))
            }
            is ParsedCall.Valid -> handle(parsed, result)
        }
    }

    private fun handle(call: ParsedCall.Valid, result: MethodChannel.Result) {
        if (appContext == null) {
            result.success(
                BridgeEnvelopeParser.errorEnvelope(
                    call.callId,
                    BridgeError(MethodChannelContract.Errors.ENGINE_NOT_READY, "No context"),
                ),
            )
            return
        }

        scope.launch {
            val runtime = DownloadForegroundService.runtime()
            if (runtime == null) {
                result.success(
                    BridgeEnvelopeParser.errorEnvelope(
                        call.callId,
                        BridgeError(
                            MethodChannelContract.Errors.ENGINE_NOT_READY,
                            "Engine runtime not initialized",
                        ),
                    ),
                )
                return@launch
            }

            val response = runtime.call(call.method, call.params)
            if (response == null) {
                result.success(
                    BridgeEnvelopeParser.errorEnvelope(
                        call.callId,
                        BridgeError(
                            MethodChannelContract.Errors.ENGINE_TIMEOUT,
                            "Engine did not respond",
                        ),
                    ),
                )
                return@launch
            }

            if (response.has("error")) {
                val err = response.getJSONObject("error")
                result.success(
                    BridgeEnvelopeParser.errorEnvelope(
                        call.callId,
                        BridgeError(
                            code = err.optString("code", MethodChannelContract.Errors.INTERNAL),
                            message = err.optString("message", "Engine error"),
                            details = err.optJSONObject("data")?.toMap() ?: emptyMap(),
                        ),
                    ),
                )
            } else {
                val resData = response.optJSONObject("result")?.toMap() ?: emptyMap()
                result.success(
                    BridgeEnvelopeParser.successEnvelope(
                        BridgeSuccess(call.callId, resData),
                    ),
                )
            }
        }
    }

    // ---- Event channel ----

    private var collectorJob: kotlinx.coroutines.Job? = null

    override fun onListen(arguments: Any?, sink: EventChannel.EventSink?) {
        // Cancel any previous collector before starting a new one.
        collectorJob?.cancel()
        eventSink = sink
        collectorJob = DownloadForegroundService.runtime()?.notifications
            ?.onEach { emitNotification(it) }
            ?.launchIn(scope)
    }

    override fun onCancel(arguments: Any?) {
        collectorJob?.cancel()
        collectorJob = null
        eventSink = null
    }

    private fun emitNotification(json: JSONObject) {
        val method = json.optString("method", "")
        val params = json.optJSONObject("params")?.toMap() ?: emptyMap()
        val envelope = BridgeEnvelopeParser.eventEnvelope(method, params)
        eventSink?.success(envelope)
    }

    companion object {
        private const val TAG = "EngineMethodChannel"
    }
}

/** Converts a [JSONObject] to a plain `Map<String, Any?>`.
 * Handles [JSONObject.NULL] by converting it to Kotlin `null`. */
private fun JSONObject.toMap(): Map<String, Any?> {
    val out = mutableMapOf<String, Any?>()
    for (key in keys()) {
        out[key] = when (val v = get(key)) {
            JSONObject.NULL -> null
            is JSONObject -> v.toMap()
            is org.json.JSONArray -> v.toList()
            else -> v
        }
    }
    return out
}

/** Converts a [JSONArray] to a `List<Any?>`.
 * Handles [JSONObject.NULL] by converting it to Kotlin `null`. */
private fun org.json.JSONArray.toList(): List<Any?> {
    val out = mutableListOf<Any?>()
    for (i in 0 until length()) {
        out.add(when (val v = get(i)) {
            JSONObject.NULL -> null
            is JSONObject -> v.toMap()
            is org.json.JSONArray -> v.toList()
            else -> v
        })
    }
    return out
}
